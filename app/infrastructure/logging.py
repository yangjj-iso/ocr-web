"""
结构化日志基础设施

支持两种输出格式:
- text: 传统文本格式（开发环境）
- json: JSON 结构化格式（生产环境，便于 ELK/Loki 采集）

自动注入上下文字段: trace_id, task_id, batch_id, node_name
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextvars import ContextVar
from typing import Any

# 上下文变量 — 在 async 任务中自动传播
_trace_id: ContextVar[str] = ContextVar("trace_id", default="")
_task_id: ContextVar[str] = ContextVar("task_id", default="")
_batch_id: ContextVar[str] = ContextVar("batch_id", default="")
_node_name: ContextVar[str] = ContextVar("node_name", default="")


def set_trace_context(
    *,
    trace_id: str = "",
    task_id: str = "",
    batch_id: str = "",
    node_name: str = "",
) -> None:
    """设置当前协程的追踪上下文"""
    if trace_id:
        _trace_id.set(trace_id)
    if task_id:
        _task_id.set(task_id)
    if batch_id:
        _batch_id.set(batch_id)
    if node_name:
        _node_name.set(node_name)


def new_trace_id() -> str:
    """生成新的 trace ID"""
    tid = uuid.uuid4().hex[:16]
    _trace_id.set(tid)
    return tid


def get_trace_context() -> dict[str, str]:
    """获取当前追踪上下文"""
    return {
        "trace_id": _trace_id.get(),
        "task_id": _task_id.get(),
        "batch_id": _batch_id.get(),
        "node_name": _node_name.get(),
    }


class JsonFormatter(logging.Formatter):
    """JSON 结构化日志 formatter — 每行一个 JSON 对象"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 注入追踪上下文
        trace_id = _trace_id.get()
        if trace_id:
            log_entry["trace_id"] = trace_id
        task_id = _task_id.get()
        if task_id:
            log_entry["task_id"] = task_id
        batch_id = _batch_id.get()
        if batch_id:
            log_entry["batch_id"] = batch_id
        node_name = _node_name.get()
        if node_name:
            log_entry["node_name"] = node_name

        # 附加 extra 字段
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        if hasattr(record, "confidence"):
            log_entry["confidence"] = record.confidence
        if hasattr(record, "retry_count"):
            log_entry["retry_count"] = record.retry_count
        if hasattr(record, "error_type"):
            log_entry["error_type"] = record.error_type

        # 异常信息
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


def configure_logging(log_format: str = "text", level: int = logging.INFO) -> None:
    """
    配置全局日志格式。

    Args:
        log_format: "text" 或 "json"
        level: 日志级别
    """
    root = logging.getLogger()
    root.setLevel(level)

    # 清除已有 handler
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    handler.setLevel(level)

    if log_format == "json":
        handler.setFormatter(JsonFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))

    root.addHandler(handler)


class NodeTimer:
    """Agent 节点计时器上下文管理器 — 自动记录耗时和结构化日志"""

    def __init__(self, node_name: str, logger_instance: logging.Logger | None = None):
        self.node_name = node_name
        self._logger = logger_instance or logging.getLogger("agent.node")
        self._start: float = 0.0
        self.duration_ms: float = 0.0

    def __enter__(self) -> "NodeTimer":
        _node_name.set(self.node_name)
        self._start = time.perf_counter()
        self._logger.debug("Node [%s] started", self.node_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.duration_ms = (time.perf_counter() - self._start) * 1000
        if exc_type:
            self._logger.warning(
                "Node [%s] failed after %.1fms: %s",
                self.node_name,
                self.duration_ms,
                exc_val,
                extra={"duration_ms": self.duration_ms, "error_type": exc_type.__name__},
            )
        else:
            self._logger.info(
                "Node [%s] completed in %.1fms",
                self.node_name,
                self.duration_ms,
                extra={"duration_ms": self.duration_ms},
            )
        _node_name.set("")
        return None
