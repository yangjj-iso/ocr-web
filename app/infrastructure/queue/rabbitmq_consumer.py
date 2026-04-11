from __future__ import annotations

import logging
import socket
import time
from typing import Any

from config import (
    MQ_BROKER_URL,
    MQ_COMMAND_DLQ,
    MQ_COMMAND_DLX,
    MQ_COMMAND_EXCHANGE,
    MQ_PREFETCH_COUNT,
    MQ_COMMAND_QUEUE,
    MQ_COMMAND_ROUTING_KEY,
)
from app.infrastructure.metrics import set_queue_depth

from .contracts import OcrTaskCommand
from .worker_executor import process_task_command_sync


logger = logging.getLogger(__name__)
QUEUE_DEPTH_REFRESH_INTERVAL_SECONDS = 2.0
CONSUMER_DRAIN_TIMEOUT_SECONDS = 1.0


def run_command_consumer() -> None:
    try:
        from kombu import Connection, Consumer, Exchange, Queue
    except ImportError as exc:  # pragma: no cover - depends on optional runtime extras
        raise RuntimeError("RabbitMQ consumer requires kombu/celery to be installed.") from exc

    exchange = Exchange(MQ_COMMAND_EXCHANGE, type="direct", durable=True)
    dead_letter_exchange = Exchange(MQ_COMMAND_DLX, type="direct", durable=True)
    queue = Queue(
        MQ_COMMAND_QUEUE,
        exchange=exchange,
        routing_key=MQ_COMMAND_ROUTING_KEY,
        durable=True,
        queue_arguments={"x-dead-letter-exchange": MQ_COMMAND_DLX},
    )
    dead_letter_queue = Queue(
        MQ_COMMAND_DLQ,
        exchange=dead_letter_exchange,
        routing_key=MQ_COMMAND_DLQ,
        durable=True,
    )

    with Connection(MQ_BROKER_URL) as connection:
        with connection.channel() as channel:
            queue(channel).declare()
            dead_letter_queue(channel).declare()

        last_queue_depth_refresh = 0.0

        def _maybe_refresh_queue_depth(force: bool = False) -> None:
            nonlocal last_queue_depth_refresh
            now = time.monotonic()
            if force or (now - last_queue_depth_refresh) >= QUEUE_DEPTH_REFRESH_INTERVAL_SECONDS:
                _refresh_queue_depth(connection, queue)
                last_queue_depth_refresh = now

        def _handle_message(body: dict[str, Any], message) -> None:
            try:
                command = OcrTaskCommand.model_validate(body)
                logger.info(
                    "RabbitMQ consumer received task command: task_id=%s, batch_id=%s",
                    command.task_id,
                    command.batch_id,
                )
                process_task_command_sync(command.model_dump(mode="json"))
            except Exception:
                logger.exception("Command consumer failed; message will be requeued.")
                message.reject(requeue=True)
                return
            message.ack()

        with Consumer(
            connection,
            queues=[queue],
            callbacks=[_handle_message],
            accept=["json"],
            prefetch_count=MQ_PREFETCH_COUNT,
        ):
            logger.info(
                "RabbitMQ command consumer started: broker=%s, queue=%s, routing_key=%s, prefetch=%s",
                MQ_BROKER_URL,
                MQ_COMMAND_QUEUE,
                MQ_COMMAND_ROUTING_KEY,
                MQ_PREFETCH_COUNT,
            )
            _maybe_refresh_queue_depth(force=True)
            try:
                while True:
                    try:
                        connection.drain_events(timeout=CONSUMER_DRAIN_TIMEOUT_SECONDS)
                    except socket.timeout:
                        pass
                    _maybe_refresh_queue_depth()
            except KeyboardInterrupt:
                logger.info("RabbitMQ command consumer interrupted by user; shutting down gracefully.")


def _refresh_queue_depth(connection, declared_queue) -> None:
    try:
        with connection.channel() as metrics_channel:
            result = declared_queue(metrics_channel).queue_declare(passive=True)
            message_count = int(result[1] if isinstance(result, tuple) else getattr(result, "message_count", 0))
        set_queue_depth(MQ_COMMAND_QUEUE, message_count)
    except Exception:
        logger.debug("Failed to refresh RabbitMQ queue depth metric.", exc_info=True)
