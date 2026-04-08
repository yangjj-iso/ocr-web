"""
LLM 客户端工厂 — 根据配置创建对应的 Provider 实例

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
"""
import logging
import os

import config as _config  # noqa: F401  # ensure .env is loaded before reading os.getenv

from app.llm.base import LLMProvider
from app.llm.providers.openai_compatible import OpenAICompatibleProvider

logger = logging.getLogger(__name__)

_instance: LLMProvider | None = None
_vision_instance: LLMProvider | None = None


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


def get_llm_client(*, vision: bool = False) -> LLMProvider:
    """
    获取单例的 LLM Provider 实例，支持普通的纯文本大模型（vision=False）或多模态视觉大模型（vision=True）。
    
    使用单例模式（基于全局变量缓存）以避免在每次调用时重复创建底层 HTTP session/client 带来过大开销。
    因为可能需要多模态图文对话（如 GPT-4o, Qwen-VL）用于双路 OCR 校验，这里支持 `vision` 隔离实例。
    """
    global _instance, _vision_instance
    current = _vision_instance if vision else _instance
    if current is not None:
        return current

    config = _resolve_config(vision=vision)
    logger.info(
        "Initializing %sLLM provider: base_url=%s, model=%s, api_key=%s",
        "vision-" if vision else "",
        config["base_url"],
        config["model"],
        "***" if config["api_key"] else "<empty>",
    )

    provider = OpenAICompatibleProvider(
        base_url=config["base_url"],
        api_key=config["api_key"],
        model=config["model"],
        timeout_seconds=float(config["timeout_seconds"]),
    )
    if vision:
        _vision_instance = provider
    else:
        _instance = provider
    return provider


def reset_llm_client() -> None:
    """重置单例（用于测试或动态切换配置）"""
    global _instance, _vision_instance
    _instance = None
    _vision_instance = None
