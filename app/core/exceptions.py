"""
统一异常定义
所有业务异常继承自 AppError，API 层统一捕获处理
"""
from fastapi import status as http_status


class AppError(Exception):
    """应用基础异常"""
    status_code: int = http_status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Internal server error."

    def __init__(self, detail: str | None = None, *, status_code: int | None = None):
        if detail is not None:
            self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = http_status.HTTP_404_NOT_FOUND
    detail = "Resource not found."


class BadRequestError(AppError):
    status_code = http_status.HTTP_400_BAD_REQUEST
    detail = "Bad request."


class ConflictError(AppError):
    status_code = http_status.HTTP_409_CONFLICT
    detail = "Conflict."


class ForbiddenError(AppError):
    status_code = http_status.HTTP_403_FORBIDDEN
    detail = "Forbidden."


class ServiceUnavailableError(AppError):
    status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Service temporarily unavailable."


class LLMServiceError(ServiceUnavailableError):
    """LLM 调用失败"""
    detail = "LLM service error."


class OCREngineError(ServiceUnavailableError):
    """OCR 引擎异常"""
    detail = "OCR engine error."


class PathSecurityError(AppError):
    """路径安全校验失败"""
    status_code = http_status.HTTP_403_FORBIDDEN
    detail = "Path access denied."


class ResultValidationError(BadRequestError):
    """OCR 结果校验失败"""
    detail = "Invalid OCR result format."
