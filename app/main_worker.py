import logging

from app.config import LOG_FORMAT
from app.infrastructure.logging import configure_logging
from app.infrastructure.metrics import start_worker_metrics_server
from app.infrastructure.queue.rabbitmq_consumer import run_command_consumer


configure_logging(log_format=LOG_FORMAT, level=logging.INFO)


if __name__ == "__main__":
    start_worker_metrics_server()
    run_command_consumer()
