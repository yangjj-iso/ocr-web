"""
LLM 错误分类体系

根据 HTTP 状态码和异常类型将 LLM 调用失败分为可重试和不可重试两类，
供熔断器和 fallback 链做出正确的降级决策。
"""


class LLMError(Exception):
    """LLM 调用基础异常"""

    retryable: bool = False

    def __init__(self, message: str = "", *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class LLMTimeoutError(LLMError):
    """请求超时 — 可重试"""

    retryable = True


class LLMRateLimitError(LLMError):
    """429 限流 — 可重试（需退避）"""

    retryable = True


class LLMServerError(LLMError):
    """5xx 上游服务异常 — 可重试"""

    retryable = True


class LLMAuthError(LLMError):
    """401/403 认证失败 — 不可重试"""

    retryable = False


class LLMNotFoundError(LLMError):
    """404 模型或端点不存在 — 不可重试"""

    retryable = False


class LLMContentFilterError(LLMError):
    """内容安全过滤 — 不可重试"""

    retryable = False


class LLMCircuitOpenError(LLMError):
    """熔断器打开 — 不可重试（应切换 fallback）"""

    retryable = False
