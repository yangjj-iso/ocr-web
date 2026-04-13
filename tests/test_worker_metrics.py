import unittest

from app.infrastructure.metrics import worker_metrics


def _sample_value(metric, sample_suffix: str, labels: dict[str, str]) -> float:
    sample_name = f"{metric._name}{sample_suffix}"
    for family in metric.collect():
        for sample in family.samples:
            if sample.name != sample_name:
                continue
            if all(sample.labels.get(key) == value for key, value in labels.items()):
                return float(sample.value)
    return 0.0


class WorkerMetricsTests(unittest.TestCase):
    def setUp(self):
        if worker_metrics._QUEUE_DEPTH is None:
            self.skipTest("prometheus_client is not installed in the active Python environment.")

    def test_queue_depth_gauge_updates(self):
        worker_metrics.set_queue_depth("ocr.task.command.queue", 7)
        value = _sample_value(
            worker_metrics._QUEUE_DEPTH,
            "",
            {"queue": "ocr.task.command.queue"},
        )
        self.assertEqual(value, 7.0)

    def test_inflight_task_gauge_round_trips(self):
        labels = {"mode": "layout"}
        before = _sample_value(worker_metrics._INFLIGHT_TASKS, "", labels)
        worker_metrics.task_started("layout")
        during = _sample_value(worker_metrics._INFLIGHT_TASKS, "", labels)
        worker_metrics.task_finished("layout")
        after = _sample_value(worker_metrics._INFLIGHT_TASKS, "", labels)

        self.assertEqual(during, before + 1.0)
        self.assertEqual(after, before)

    def test_pause_counter_increments(self):
        labels = {"mode": "layout"}
        before = _sample_value(worker_metrics._PAUSED_TASKS_TOTAL, "_total", labels)
        worker_metrics.increment_paused_tasks("layout")
        after = _sample_value(worker_metrics._PAUSED_TASKS_TOTAL, "_total", labels)
        self.assertEqual(after, before + 1.0)

    def test_page_histogram_records_observation(self):
        labels = {"mode": "layout"}
        before = _sample_value(worker_metrics._PAGE_PROCESSING_SECONDS, "_count", labels)
        worker_metrics.observe_page_processing_seconds("layout", 1.25)
        after = _sample_value(worker_metrics._PAGE_PROCESSING_SECONDS, "_count", labels)
        self.assertEqual(after, before + 1.0)

    def test_gpu_cache_clear_counter_increments(self):
        labels = {"backend": "torch"}
        before = _sample_value(worker_metrics._GPU_CACHE_CLEARS_TOTAL, "_total", labels)
        worker_metrics.increment_gpu_cache_clears("torch")
        after = _sample_value(worker_metrics._GPU_CACHE_CLEARS_TOTAL, "_total", labels)
        self.assertEqual(after, before + 1.0)


if __name__ == "__main__":
    unittest.main()
