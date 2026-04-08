"""
LLM Provider 抽象接口

所有 LLM Provider 必须实现此接口。
新增 Provider 只需：
  1. 继承 LLMProvider
  2. 实现 chat_completion()
  3. 在 client.py 注册
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: Any


@dataclass(slots=True)
class LLMResponse:
    """LLM 调用统一返回"""
    content: str                          # 文本内容
    provider: str                         # provider 标识 (e.g. "openai_compatible")
    model: str                            # 实际使用的模型名
    raw_usage: dict[str, Any] = field(default_factory=dict)  # token 用量
    raw_response: dict[str, Any] = field(default_factory=dict)  # 原始响应（调试用）


class LLMProvider(ABC):
    """LLM Provider 抽象基类"""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider 标识名"""
        ...

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[LLMMessage],
        *,
        model: str | None = None,
        temperature: float = 0.1,
        response_format: dict[str, str] | None = None,
        timeout_seconds: float | None = None,
    ) -> LLMResponse:
        """
        调用 LLM chat completion

        Args:
            messages: 对话消息列表
            model: 模型名（None 则用默认）
            temperature: 采样温度
            response_format: 响应格式 (e.g. {"type": "json_object"})
            timeout_seconds: 超时秒数
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """检查 Provider 是否可用（配置是否完整）"""
        ...
