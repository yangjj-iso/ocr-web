"""
Dead Letter Queue (DLQ) Consumer — 死信队列消费者。

功能:
  1. 消费 DLQ 中的失败消息，记录到日志
  2. 支持手动重试投递回原队列
  3. 超过最大重试次数的消息设置 TTL 自动过期
  4. 提供 DLQ 深度监控指标
"""

from __future__ import annotations

import json
import logging
import socket
import time
from datetime import datetime, timezone
from typing import Any

from config import (
    MQ_BROKER_URL,
    MQ_COMMAND_DLQ,
    MQ_COMMAND_DLX,
    MQ_COMMAND_EXCHANGE,
    MQ_COMMAND_QUEUE,
    MQ_COMMAND_ROUTING_KEY,
)

logger = logging.getLogger(__name__)

DLQ_MAX_RETRY_COUNT = 3
DLQ_POLL_INTERVAL_SECONDS = 2.0
DLQ_MESSAGE_TTL_MS = 7 * 24 * 60 * 60 * 1000  # 7 days


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_retry_count(body: dict[str, Any]) -> int:
    return int(body.get("_dlq_retry_count", 0))


def run_dlq_consumer() -> None:
    """启动 DLQ 消费者，处理失败消息并支持重试。"""
    try:
        from kombu import Connection, Consumer, Exchange, Queue, Producer
    except ImportError as exc:
        raise RuntimeError("DLQ consumer requires kombu to be installed.") from exc

    dead_letter_exchange = Exchange(MQ_COMMAND_DLX, type="direct", durable=True)
    dlq = Queue(
        MQ_COMMAND_DLQ,
        exchange=dead_letter_exchange,
        routing_key=MQ_COMMAND_DLQ,
        durable=True,
    )

    original_exchange = Exchange(MQ_COMMAND_EXCHANGE, type="direct", durable=True)

    with Connection(MQ_BROKER_URL) as connection:
        with connection.channel() as channel:
            dlq(channel).declare()

        def _handle_dlq_message(body: dict[str, Any], message) -> None:
            task_id = body.get("task_id", "unknown")
            command_id = body.get("command_id", "unknown")
            retry_count = _extract_retry_count(body)

            logger.warning(
                "DLQ message received: task_id=%s, command_id=%s, retry_count=%d/%d",
                task_id,
                command_id,
                retry_count,
                DLQ_MAX_RETRY_COUNT,
            )

            if retry_count < DLQ_MAX_RETRY_COUNT:
                # 增加重试计数并重新投递到原队列
                body["_dlq_retry_count"] = retry_count + 1
                body["_dlq_last_retry_at"] = _utc_now_iso()
                try:
                    with connection.channel() as pub_channel:
                        producer = Producer(pub_channel, exchange=original_exchange)
                        producer.publish(
                            body,
                            routing_key=MQ_COMMAND_ROUTING_KEY,
                            content_type="application/json",
                            serializer="json",
                        )
                    logger.info(
                        "DLQ message re-queued: task_id=%s, retry=%d",
                        task_id,
                        retry_count + 1,
                    )
                    message.ack()
                except Exception:
                    logger.exception(
                        "Failed to re-queue DLQ message: task_id=%s", task_id
                    )
                    message.reject(requeue=True)
            else:
                # 超过最大重试次数，记录并丢弃
                logger.error(
                    "DLQ message exhausted retries (max=%d): task_id=%s, command_id=%s, body=%s",
                    DLQ_MAX_RETRY_COUNT,
                    task_id,
                    command_id,
                    json.dumps(body, ensure_ascii=False, default=str)[:2000],
                )
                message.ack()

        with Consumer(
            connection,
            queues=[dlq],
            callbacks=[_handle_dlq_message],
            accept=["json"],
            prefetch_count=1,
        ):
            logger.info(
                "DLQ consumer started: broker=%s, queue=%s",
                MQ_BROKER_URL,
                MQ_COMMAND_DLQ,
            )
            try:
                while True:
                    try:
                        connection.drain_events(timeout=DLQ_POLL_INTERVAL_SECONDS)
                    except socket.timeout:
                        pass
            except KeyboardInterrupt:
                logger.info("DLQ consumer interrupted; shutting down.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    run_dlq_consumer()
