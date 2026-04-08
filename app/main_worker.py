import logging

from app.infrastructure.metrics import start_worker_metrics_server
from app.infrastructure.queue.rabbitmq_consumer import run_command_consumer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


if __name__ == "__main__":
    start_worker_metrics_server()
    run_command_consumer()
