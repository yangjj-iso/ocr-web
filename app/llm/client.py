"""
LLM 客户端工厂 — 根据配置创建对应的 Provider 实例

支持主备 fallback 链：主 provider 熔断时自动切换到备用 provider。

优先读取新配置 (LLM_*), 兼容旧配置 (MINIMAX_*)
切换 Provider 只需改 .env, 无需改代码。

.env 配置示例:
    # MiniMax 云端
    LLM_BASE_URL=https://api.minimaxi.com/v1
    LLM_API_KEY=your-minimax-key
    LLM_MODEL=MiniMax-M2.7

    # Ollama 本地
    LLM_BASE_URL=http://localhost:11434/v1
    LLM_API_KEY=
    LLM_MODEL=qwen2.5:14b

    # vLLM 本地
    LLM_BASE_URL=http://localhost:8000/v1
    LLM_API_KEY=token-abc123
    LLM_MODEL=Qwen/Qwen2.5-14B-Instruct

    # Fallback (备用 provider)
    LLM_FALLBACK_BASE_URL=http://localhost:11434/v1
    LLM_FALLBACK_API_KEY=
    LLM_FALLBACK_MODEL=qwen2.5:7b
"""
import logging
import os

import config as _config  # noqa: F401  # ensure .env is loaded before reading os.getenv

from app.llm.base import LLMMessage, LLMProvider, LLMResponse
from app.llm.circuit_breaker import CircuitBreaker
from app.llm.errors import LLMCircuitOpenError, LLMError
from app.llm.providers.openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)

_instance: LLMProvider | None = None
_vision_instance: LLMProvider | None = None
_primary_circuit_breaker: CircuitBreaker | None = None
_vision_circuit_breaker: CircuitBreaker | None = None


def _resolve_config(*, vision: bool = False) -> dict[str, str]:
    """
    通过读取环境变量解析并组装大模型的配置信息（请求基础 URL、鉴权密钥、模型名称）。
    
    设计意图：为了让项目能够无缝对接任何兼容 OpenAI API 规范的大模型底座 
    (如 Ollama, vLLM, FastChat 甚至直接对接 OpenAI 或各种国产大模型)。
    对于普通的 LLM 和带有视觉分析能力的 Vision LLM，可以通过不同的环境变量前缀 (`VISION_LLM_` 和 `LLM_`) 进行配置解耦。
    """
    prefix = "VISION_LLM_" if vision else "LLM_"
    base_url = os.getenv(f"{prefix}BASE_URL", "").strip()
    api_key = os.getenv(f"{prefix}API_KEY", "").strip()
    model = os.getenv(f"{prefix}MODEL", "").strip()
    timeout = os.getenv(f"{prefix}TIMEOUT_SECONDS", "").strip()
    max_input = os.getenv("LLM_MAX_INPUT_CHARS", "").strip()

    # 视觉模型必须显式配置，避免静默回退到纯文本模型后返回无关内容。
    if vision:
        if not timeout:
            timeout = os.getenv("VISION_LLM_TIMEOUT_SECONDS", os.getenv("MINIMAX_TIMEOUT_SECONDS", "60")).strip()
    else:
        # 回退到旧配置
        if not base_url:
            base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1").strip()
        if not api_key:
            api_key = os.getenv("MINIMAX_API_KEY", "").strip()
        if not model:
            model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7").strip()
        if not timeout:
            timeout = os.getenv("MINIMAX_TIMEOUT_SECONDS", "60").strip()
    if not max_input:
        max_input = os.getenv("MINIMAX_MAX_INPUT_CHARS", "12000").strip()

    return {
        "base_url": base_url,
        "api_key": api_key,
        "model": model,
        "timeout_seconds": timeout,
        "max_input_chars": max_input,
    }


def vision_endpoint_supports_image_inputs() -> bool:
    """
    当前实现走的是 OpenAI-compatible `/chat/completions`。
    MiniMax 官方文档明确说明其兼容 OpenAI / Anthropic 文本接口暂不支持 image input，
    因此这里直接将该接口视为不可用于视觉节点，避免返回与图片无关的幻觉结果。
    """
    config = _resolve_config(vision=True)
    base_url = config["base_url"].strip().lower()
    model = config["model"].strip()
    if not base_url or not model:
        return False
    if "minimax" in base_url or "minimaxi" in base_url:
        return False
    return True


class FallbackProvider(LLMProvider):
    """主备 fallback 链 — 主 provider 失败（熔断/异常）时自动切换到备用"""

    def __init__(self, primary: OpenAICompatibleProvider, fallback: OpenAICompatibleProvider | None):
        self._primary = primary
        self._fallback = fallback

    @property
    def provider_name(self) -> str:
        return self._primary.provider_name

    @property
    def default_model(self) -> str:
        return self._primary.default_model

    def is_available(self) -> bool:
        return self._primary.is_available() or (self._fallback is not None and self._fallback.is_available())

    async def chat_completion(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        response_format: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        try:
            return await self._primary.chat_completion(
                messages,
                model=model,
                temperature=temperature,
                response_format=response_format,
                timeout_seconds=timeout_seconds,
            )
        except LLMCircuitOpenError:
            if self._fallback and self._fallback.is_available():
                logger.warning("Primary LLM circuit open, switching to fallback provider.")
                return await self._fallback.chat_completion(
                    messages,
                    model=None,  # 使用 fallback 自身的默认模型
                    temperature=temperature,
                    response_format=response_format,
                    timeout_seconds=timeout_seconds,
                )
            raise
        except LLMError as exc:
            if not exc.retryable:
                raise
            # 可重试错误已在 provider 内部重试过，到这里说明全部失败
            if self._fallback and self._fallback.is_available():
                logger.warning(
                    "Primary LLM failed (%s), switching to fallback provider.",
                    type(exc).__name__,
                )
                return await self._fallback.chat_completion(
                    messages,
                    model=None,
                    temperature=temperature,
                    response_format=response_format,
                    timeout_seconds=timeout_seconds,
                )
            raise


def _get_circuit_breaker(name: str) -> CircuitBreaker:
    """创建或获取熔断器实例"""
    from app.config import LLM_CB_FAILURE_THRESHOLD, LLM_CB_RECOVERY_SECONDS
    return CircuitBreaker(
        name=name,
        failure_threshold=LLM_CB_FAILURE_THRESHOLD,
        recovery_seconds=LLM_CB_RECOVERY_SECONDS,
    )


def _build_fallback_provider() -> OpenAICompatibleProvider | None:
    """构建备用 provider（如果配置了 LLM_FALLBACK_* 环境变量）"""
    from app.config import LLM_FALLBACK_BASE_URL, LLM_FALLBACK_API_KEY, LLM_FALLBACK_MODEL
    if not LLM_FALLBACK_BASE_URL or not LLM_FALLBACK_MODEL:
        return None
    return OpenAICompatibleProvider(
        base_url=LLM_FALLBACK_BASE_URL,
        api_key=LLM_FALLBACK_API_KEY,
        model=LLM_FALLBACK_MODEL,
    )


def get_llm_client(*, vision: bool = False) -> LLMProvider:
    """
    获取 LLM Provider 实例（含 fallback 链和熔断器）。

    使用单例模式以避免重复创建底层 HTTP session/client。
    支持 vision 隔离实例用于多模态图文对话。
    """
    global _instance, _vision_instance, _primary_circuit_breaker, _vision_circuit_breaker
    current = _vision_instance if vision else _instance
    if current is not None:
        return current

    config = _resolve_config(vision=vision)
    cb_name = "vision-llm" if vision else "llm"

    # 创建熔断器
    cb = _get_circuit_breaker(cb_name)
    if vision:
        _vision_circuit_breaker = cb
    else:
        _primary_circuit_breaker = cb

    logger.info(
        "Initializing %sLLM provider: base_url=%s, model=%s, api_key=%s",
        "vision-" if vision else "",
        config["base_url"],
        config["model"],
        "***" if config["api_key"] else "<empty>",
    )

    primary = OpenAICompatibleProvider(
        base_url=config["base_url"],
        api_key=config["api_key"],
        model=config["model"],
        timeout_seconds=float(config["timeout_seconds"]),
        circuit_breaker=cb,
    )

    # 构建 fallback（仅非 vision 模式）
    fallback = _build_fallback_provider() if not vision else None
    provider: LLMProvider = FallbackProvider(primary, fallback)

    if vision:
        _vision_instance = provider
    else:
        _instance = provider
    return provider


def get_primary_circuit_breaker() -> CircuitBreaker | None:
    """获取主 LLM 熔断器实例（用于指标暴露）"""
    return _primary_circuit_breaker


def reset_llm_client() -> None:
    """重置单例（用于测试或动态切换配置）"""
    global _instance, _vision_instance, _primary_circuit_breaker, _vision_circuit_breaker
    _instance = None
    _vision_instance = None
    _primary_circuit_breaker = None
    _vision_circuit_breaker = None
