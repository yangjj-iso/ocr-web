"""
OpenAI 兼容 Provider — 支持 MiniMax / Ollama / vLLM / LocalAI 等所有兼容 OpenAI API 的服务

配置方式 (.env):
    LLM_BASE_URL=https://api.minimaxi.com/v1      # MiniMax
    LLM_BASE_URL=http://localhost:11434/v1          # Ollama
    LLM_BASE_URL=http://localhost:8080/v1           # vLLM / LocalAI
    LLM_API_KEY=your-api-key                        # 部分本地服务不需要
    LLM_MODEL=MiniMax-M2.7                          # 或 qwen2.5:14b 等
"""
import asyncio
import logging
import re
from typing import Any

from app.llm.base import LLMMessage, LLMProvider, LLMResponse

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)


class OpenAICompatibleProvider(LLMProvider):
    """OpenAI 兼容协议 LLM Provider"""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        model: str = "",
        timeout_seconds: float = 60.0,
        max_retries: int = 3,
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    @property
    def default_model(self) -> str:
        return self._model

    def is_available(self) -> bool:
        return bool(self._base_url and self._model)

    async def chat_completion(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        response_format: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        if httpx is None:
            raise RuntimeError("httpx is required for LLM integration. Install: pip install httpx")

        if not self.is_available():
            raise RuntimeError("LLM provider is not configured. Check LLM_BASE_URL and LLM_MODEL in .env")

        actual_model = model or self._model
        actual_timeout = timeout_seconds or self._timeout_seconds

        payload: dict[str, Any] = {
            "model": actual_model,
            "temperature": temperature,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if response_format:
            payload["response_format"] = response_format

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        url = f"{self._base_url}/chat/completions"
        response = await self._post_with_retry(url, headers, payload, actual_timeout)

        try:
            response_json = response.json()
        except ValueError as exc:
            raise RuntimeError("LLM returned a non-JSON response.") from exc

        content = self._extract_content(response_json)
        return LLMResponse(
            content=content,
            provider=self.provider_name,
            model=response_json.get("model") or actual_model,
            raw_usage=response_json.get("usage") or {},
            raw_response=response_json,
        )

    async def _post_with_retry(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ):
        """带重试的 HTTP POST"""
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)
            except httpx.TimeoutException as exc:
                raise RuntimeError("LLM request timed out.") from exc
            except httpx.HTTPError as exc:
                raise RuntimeError(f"LLM request failed: {exc}") from exc

            if response.status_code >= 500 and attempt < self._max_retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue

            if response.status_code >= 400:
                self._raise_http_error(response)

            return response

        raise RuntimeError("LLM request failed after all retries.")

    @staticmethod
    def _raise_http_error(response) -> None:
        """将 HTTP 错误转为可读的 RuntimeError"""
        text = (response.text or "")[:200]
        text = re.sub(r"\s+", " ", text)

        if response.status_code in {401, 403}:
            detail = f"LLM HTTP {response.status_code}: 认证失败，请检查 LLM_API_KEY 配置。"
        elif response.status_code == 404:
            detail = f"LLM HTTP {response.status_code}: 接口地址或模型名称错误，请检查 LLM_BASE_URL 和 LLM_MODEL。"
        else:
            detail = f"LLM HTTP {response.status_code}: 上游服务异常。"

        if text:
            detail = f"{detail} Upstream: {text}"
        raise RuntimeError(detail)

    @staticmethod
    def _extract_content(response_json: dict[str, Any]) -> str:
        """从 OpenAI 格式响应中提取文本内容"""
        choices = response_json.get("choices") or []
        if not choices:
            raise RuntimeError("LLM response did not include any choices.")

        content = (((choices[0] or {}).get("message") or {}).get("content"))
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("content") or ""
                    if text:
                        parts.append(str(text))
            return "\n".join(parts).strip()
        raise RuntimeError("LLM response content was not a text payload.")
