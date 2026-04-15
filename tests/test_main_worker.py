from unittest.mock import MagicMock, patch

from app import main_worker


def test_start_background_archive_worker_starts_daemon_thread():
    fake_thread = MagicMock()

    with patch("app.main_worker.threading.Thread", return_value=fake_thread) as thread_cls:
        returned = main_worker.start_background_archive_worker()

    thread_cls.assert_called_once_with(
        target=main_worker._run_archive_worker_sync,
        name="archive-workflow-consumer",
        daemon=True,
    )
    fake_thread.start.assert_called_once_with()
    assert returned is fake_thread


def test_main_starts_metrics_archive_worker_and_command_consumer():
    with patch("app.main_worker.start_worker_metrics_server") as start_metrics, patch(
        "app.main_worker.start_background_archive_worker"
    ) as start_archive_worker, patch("app.main_worker.run_command_consumer") as run_consumer:
        main_worker.main()

    start_metrics.assert_called_once_with()
    start_archive_worker.assert_called_once_with()
    run_consumer.assert_called_once_with()