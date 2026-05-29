"""
LLM 熔断器 — 防止故障级联

状态机: CLOSED → OPEN → HALF_OPEN → CLOSED
- CLOSED: 正常放行，记录失败次数
- OPEN: 拒绝所有请求，等待恢复时间
- HALF_OPEN: 允许单个探测请求，成功则恢复，失败则重新打开

配置:
    LLM_CB_FAILURE_THRESHOLD — 连续失败多少次后打开熔断器 (默认 5)
    LLM_CB_RECOVERY_SECONDS — 熔断器打开后多久进入半开状态 (默认 60)
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """线程安全的熔断器实现"""

    def __init__(
        self,
        name: str = "llm",
        failure_threshold: int = 5,
        recovery_seconds: float = 60.0,
    ):
        self.name = name
        self.failure_threshold = max(1, failure_threshold)
        self.recovery_seconds = max(1.0, recovery_seconds)

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def allow_request(self) -> bool:
        """判断当前是否允许发起请求"""
        with self._lock:
            self._maybe_transition_to_half_open()
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.HALF_OPEN:
                return True
            return False

    def record_success(self) -> None:
        """记录一次成功调用"""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info(
                    "Circuit breaker [%s] recovered: HALF_OPEN → CLOSED",
                    self.name,
                )
            self._state = CircuitState.CLOSED
            self._failure_count = 0

    def record_failure(self) -> None:
        """记录一次失败调用"""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker [%s] re-opened: HALF_OPEN → OPEN (probe failed)",
                    self.name,
                )
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.failure_threshold
            ):
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker [%s] tripped: CLOSED → OPEN "
                    "(failures=%d, threshold=%d)",
                    self.name,
                    self._failure_count,
                    self.failure_threshold,
                )

    def reset(self) -> None:
        """手动重置熔断器（用于测试或运维干预）"""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0.0

    def _maybe_transition_to_half_open(self) -> None:
        """内部：检查是否应从 OPEN 转为 HALF_OPEN（需持有锁）"""
        if self._state != CircuitState.OPEN:
            return
        elapsed = time.monotonic() - self._last_failure_time
        if elapsed >= self.recovery_seconds:
            self._state = CircuitState.HALF_OPEN
            logger.info(
                "Circuit breaker [%s] recovery window elapsed (%.1fs): OPEN → HALF_OPEN",
                self.name,
                elapsed,
            )
