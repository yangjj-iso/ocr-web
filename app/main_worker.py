import asyncio
import logging
import threading

from config import MQ_BROKER_URL
from app.infrastructure.metrics import start_worker_metrics_server
from app.infrastructure.queue.archive_worker import run_archive_worker
from app.infrastructure.queue.rabbitmq_consumer import run_command_consumer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


def _run_archive_worker_sync() -> None:
    asyncio.run(run_archive_worker(MQ_BROKER_URL))


def start_background_archive_worker() -> threading.Thread:
    thread = threading.Thread(
        target=_run_archive_worker_sync,
        name="archive-workflow-consumer",
        daemon=True,
    )
    thread.start()
    logger.info("Archive workflow consumer thread started.")
    return thread


def main() -> None:
    start_worker_metrics_server()
    start_background_archive_worker()
    run_command_consumer()


if __name__ == "__main__":
    main()
