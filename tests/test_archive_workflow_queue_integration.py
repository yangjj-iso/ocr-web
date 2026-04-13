import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.archive_workflow import router as archive_workflow_router
from app.api.internal.workflow import router as internal_workflow_router
from app.core.auth import require_auth
from app.db.database import get_db
from app.infrastructure.callback import workflow_events
from app.infrastructure.queue import archive_publisher, archive_worker
from app.services import archive_workflow as workflow_service


class ArchivePublisherTests(unittest.IsolatedAsyncioTestCase):
    async def test_enqueue_workflow_start_includes_workflow_context(self):
        publish = AsyncMock()

        with patch("app.infrastructure.queue.archive_publisher._publish_to_queue", new=publish):
            await archive_publisher.enqueue_workflow_start(
                run_id="wf_batch_a",
                batch_id="batch-a",
                tenant_id="tenant-a",
                policy_snapshot_id="policy-v1",
                source_file_uris=["s3://bucket/doc-1.pdf"],
                page_count=12,
                submitted_by="java-control-plane",
                run_mode="normal",
                request_id="req-123",
                pages=[{"page_id": "page-1", "image_uri": "s3://bucket/page-1.png"}],
                extra={"priority": "high"},
            )

        queue_name, payload = publish.await_args.args
        self.assertEqual(queue_name, archive_publisher.QUEUE_INGEST)
        self.assertEqual(payload["run_id"], "wf_batch_a")
        self.assertEqual(payload["request_id"], "req-123")
        self.assertEqual(payload["policy_snapshot_id"], "policy-v1")
        self.assertEqual(payload["source_file_uris"], ["s3://bucket/doc-1.pdf"])
        self.assertEqual(payload["page_count"], 12)
        self.assertEqual(payload["submitted_by"], "java-control-plane")
        self.assertEqual(payload["run_mode"], "normal")
        self.assertEqual(payload["pages"][0]["page_id"], "page-1")
        self.assertEqual(payload["extra"], {"priority": "high"})

    async def test_enqueue_workflow_rework_carries_source_run_and_scope(self):
        publish = AsyncMock()

        with patch("app.infrastructure.queue.archive_publisher._publish_to_queue", new=publish):
            await archive_publisher.enqueue_workflow_rework(
                run_id="wf_existing",
                source_run_id="wf_existing",
                batch_id="batch-a",
                tenant_id="tenant-a",
                reason="rework_requested",
                rework_level="partial",
                affected_scope={"doc_ids": ["doc-1"], "invalidate_catalog": True},
                resume_from_checkpoint="build_catalog_final",
            )

        queue_name, payload = publish.await_args.args
        self.assertEqual(queue_name, archive_publisher.QUEUE_REWORK)
        self.assertEqual(payload["source_run_id"], "wf_existing")
        self.assertEqual(payload["tenant_id"], "tenant-a")
        self.assertEqual(payload["affected_scope"]["doc_ids"], ["doc-1"])
        self.assertEqual(payload["rework_scope"]["doc_ids"], ["doc-1"])
        self.assertEqual(payload["resume_from_checkpoint"], "build_catalog_final")

    async def test_enqueue_draft_pipeline_includes_stage_context(self):
        publish = AsyncMock()

        with patch("app.infrastructure.queue.archive_publisher._publish_to_queue", new=publish):
            await archive_publisher.enqueue_draft_pipeline(
                run_id="wf_existing",
                source_run_id="wf_existing",
                batch_id="batch-a",
                tenant_id="tenant-a",
                current_stage="run_draft_subgraph",
                affected_scope={"doc_ids": ["doc-1"]},
                resume_from_checkpoint="run_draft_subgraph",
                recompute_targets=["draft", "catalog"],
            )

        queue_name, payload = publish.await_args.args
        self.assertEqual(queue_name, archive_publisher.QUEUE_DRAFT_PIPELINE)
        self.assertEqual(payload["command"], "RUN_DRAFT_PIPELINE")
        self.assertEqual(payload["tenant_id"], "tenant-a")
        self.assertEqual(payload["current_stage"], "run_draft_subgraph")
        self.assertEqual(payload["affected_scope"]["doc_ids"], ["doc-1"])
        self.assertEqual(payload["recompute_targets"], ["draft", "catalog"])

    async def test_enqueue_workflow_resume_includes_review_result(self):
        publish = AsyncMock()

        with patch("app.infrastructure.queue.archive_publisher._publish_to_queue", new=publish):
            await archive_publisher.enqueue_workflow_resume(
                run_id="wf_existing",
                batch_id="batch-a",
                reason="review_submitted",
                affected_scope={"invalidate_catalog": True},
                resume_from_checkpoint="build_catalog_final",
                review_result={"result_type": "field_corrected", "field_updates": {"doc-1": {"title": "修正题名"}}},
            )

        queue_name, payload = publish.await_args.args
        self.assertEqual(queue_name, archive_publisher.QUEUE_REVIEW_RESUME)
        self.assertEqual(payload["review_result"]["result_type"], "field_corrected")
        self.assertEqual(payload["resume_from_checkpoint"], "build_catalog_final")

    async def test_enqueue_final_pipeline_includes_resume_context(self):
        publish = AsyncMock()

        with patch("app.infrastructure.queue.archive_publisher._publish_to_queue", new=publish):
            await archive_publisher.enqueue_final_pipeline(
                run_id="wf_existing",
                source_run_id="wf_existing",
                batch_id="batch-a",
                tenant_id="tenant-a",
                current_stage="build_catalog_final",
                affected_scope={"invalidate_catalog": True},
                resume_from_checkpoint="build_catalog_final",
            )

        queue_name, payload = publish.await_args.args
        self.assertEqual(queue_name, archive_publisher.QUEUE_FINAL_PIPELINE)
        self.assertEqual(payload["command"], "RUN_FINAL_PIPELINE")
        self.assertEqual(payload["current_stage"], "build_catalog_final")
        self.assertEqual(payload["tenant_id"], "tenant-a")
        self.assertTrue(payload["affected_scope"]["invalidate_catalog"])
        self.assertEqual(payload["resume_from_checkpoint"], "build_catalog_final")


class ArchiveWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_handle_ingest_fanouts_page_preprocess_when_pages_present(self):
        upsert = AsyncMock(return_value=["page-1", "page-2"])
        persist = AsyncMock()
        init_progress = AsyncMock()
        fanout = AsyncMock()
        run_workflow = AsyncMock()

        with patch("app.infrastructure.queue.archive_worker._upsert_page_records", new=upsert), patch(
            "app.infrastructure.queue.archive_worker._persist_workflow_progress",
            new=persist,
        ), patch(
            "app.infrastructure.queue.archive_worker._initialize_queue_progress",
            new=init_progress,
        ), patch("app.infrastructure.queue.archive_publisher.fanout_page_preprocess", new=fanout), patch(
            "app.services.archive_workflow.run_archive_workflow",
            new=run_workflow,
        ):
            await archive_worker._handle_ingest(
                {
                    "run_id": "wf_existing",
                    "batch_id": "batch-a",
                    "tenant_id": "tenant-a",
                    "policy_snapshot_id": "policy-v1",
                    "run_mode": "normal",
                    "pages": [
                        {"page_id": "page-1", "page_index": 0, "image_uri": "s3://bucket/page-1.png"},
                        {"page_id": "page-2", "page_index": 1, "image_uri": "s3://bucket/page-2.png"},
                    ],
                }
            )

        upsert.assert_awaited_once()
        persist.assert_awaited_once()
        persist_kwargs = persist.await_args.kwargs
        self.assertEqual(persist_kwargs["run_id"], "wf_existing")
        self.assertEqual(persist_kwargs["current_stage"], "preprocess_pages")
        self.assertEqual(len(persist_kwargs["state"]["pages"]), 2)
        init_progress.assert_awaited_once_with(run_id="wf_existing", total_pages=2)
        fanout.assert_awaited_once_with(run_id="wf_existing", batch_id="batch-a", page_ids=["page-1", "page-2"])
        run_workflow.assert_not_awaited()

    async def test_handle_ingest_falls_back_to_main_graph_without_pages(self):
        run_workflow = AsyncMock(return_value={"final_status": "done"})

        with patch("app.services.archive_workflow.run_archive_workflow", new=run_workflow):
            await archive_worker._handle_ingest(
                {
                    "run_id": "wf_existing",
                    "batch_id": "batch-a",
                    "tenant_id": "tenant-a",
                    "policy_snapshot_id": "policy-v1",
                    "run_mode": "normal",
                    "pages": [],
                }
            )

        run_workflow.assert_awaited_once_with(
            task_id="wf_existing",
            batch_id="batch-a",
            tenant_id="tenant-a",
            policy_snapshot_id="policy-v1",
            pages=[],
            run_mode="normal",
        )

    async def test_handle_rework_prefers_source_run_id_and_affected_scope(self):
        resume = AsyncMock(return_value={"final_status": "done"})

        with patch("app.services.archive_workflow.resume_archive_workflow", new=resume):
            await archive_worker._handle_rework(
                {
                    "run_id": "wf_shadow",
                    "source_run_id": "wf_existing",
                    "batch_id": "batch-a",
                    "reason": "rework_requested",
                    "affected_scope": {"doc_ids": ["doc-1"], "invalidate_catalog": True},
                    "resume_from_checkpoint": "build_catalog_final",
                }
            )

        resume.assert_awaited_once_with(
            task_id="wf_existing",
            batch_id="batch-a",
            reason="rework_requested",
            affected_scope={"doc_ids": ["doc-1"], "invalidate_catalog": True},
            resume_from_checkpoint="build_catalog_final",
        )

    async def test_handle_review_resume_passes_review_result(self):
        resume = AsyncMock(return_value={"final_status": "done"})

        with patch("app.services.archive_workflow.resume_archive_workflow", new=resume):
            await archive_worker._handle_review_resume(
                {
                    "run_id": "wf_existing",
                    "batch_id": "batch-a",
                    "reason": "review_submitted",
                    "affected_scope": {"invalidate_catalog": True},
                    "resume_from_checkpoint": "build_catalog_final",
                    "review_result": {"result_type": "field_corrected"},
                }
            )

        resume.assert_awaited_once_with(
            task_id="wf_existing",
            batch_id="batch-a",
            reason="review_submitted",
            affected_scope={"invalidate_catalog": True},
            resume_from_checkpoint="build_catalog_final",
            review_result={"result_type": "field_corrected"},
        )

    async def test_handle_page_preprocess_enqueues_ocr_for_same_chunk(self):
        preprocess = AsyncMock()
        enqueue_ocr = AsyncMock()
        advance_progress = AsyncMock()

        with patch("app.domains.page_processing.page_service.preprocess_pages", new=preprocess), patch(
            "app.infrastructure.queue.archive_publisher.enqueue_ocr_pages",
            new=enqueue_ocr,
        ), patch(
            "app.infrastructure.queue.archive_worker._advance_queue_progress",
            new=advance_progress,
        ):
            await archive_worker._handle_page_preprocess(
                {
                    "run_id": "wf_existing",
                    "batch_id": "batch-a",
                    "page_ids": ["page-1", "page-2"],
                }
            )

        preprocess.assert_awaited_once_with(batch_id="batch-a", page_ids=["page-1", "page-2"])
        self.assertEqual(advance_progress.await_count, 2)
        enqueue_ocr.assert_awaited_once_with(run_id="wf_existing", batch_id="batch-a", page_ids=["page-1", "page-2"])

    async def test_handle_ocr_enqueues_page_features_for_same_chunk(self):
        run_ocr = AsyncMock()
        enqueue_features = AsyncMock()
        advance_progress = AsyncMock()

        with patch("app.domains.page_processing.page_service.run_ocr_pages", new=run_ocr), patch(
            "app.infrastructure.queue.archive_publisher.enqueue_page_features",
            new=enqueue_features,
        ), patch(
            "app.infrastructure.queue.archive_worker._advance_queue_progress",
            new=advance_progress,
        ):
            await archive_worker._handle_ocr(
                {
                    "run_id": "wf_existing",
                    "batch_id": "batch-a",
                    "page_ids": ["page-1", "page-2"],
                }
            )

        run_ocr.assert_awaited_once_with(batch_id="batch-a", page_ids=["page-1", "page-2"])
        self.assertEqual(advance_progress.await_count, 2)
        enqueue_features.assert_awaited_once_with(run_id="wf_existing", batch_id="batch-a", page_ids=["page-1", "page-2"])

    async def test_handle_page_features_queues_relation_once_batch_ready(self):
        extract = AsyncMock()
        maybe_enqueue = AsyncMock(return_value=True)
        advance_progress = AsyncMock()

        with patch("app.domains.page_processing.page_service.extract_page_features", new=extract), patch(
            "app.infrastructure.queue.archive_worker._maybe_enqueue_relation_analysis",
            new=maybe_enqueue,
        ), patch(
            "app.infrastructure.queue.archive_worker._advance_queue_progress",
            new=advance_progress,
        ):
            await archive_worker._handle_page_features(
                {
                    "run_id": "wf_existing",
                    "batch_id": "batch-a",
                    "tenant_id": "tenant-a",
                    "page_ids": ["page-1", "page-2"],
                }
            )

        extract.assert_awaited_once_with(batch_id="batch-a", page_ids=["page-1", "page-2"])
        advance_progress.assert_awaited_once_with(run_id="wf_existing", stage="page_features", completed_delta=2)
        maybe_enqueue.assert_awaited_once_with(run_id="wf_existing", batch_id="batch-a", tenant_id="tenant-a")

    async def test_handle_relation_analysis_updates_state_and_enqueues_draft(self):
        config = {"configurable": {"thread_id": "wf_existing"}}
        initial_state = {
            "task_id": "wf_existing",
            "batch_id": "batch-a",
            "tenant_id": "tenant-a",
            "pages": [{"page_id": "page-1"}],
            "draft_docs": [],
            "final_docs": [],
            "blocked_reasons": [],
        }
        analyze = AsyncMock(return_value={"pages": [{"page_id": "page-1", "page_relation_json": {"is_new_doc_start": True}}], "current_stage": "split_documents"})
        split = AsyncMock(return_value={"draft_docs": [{"tmp_doc_id": "doc-1"}], "current_stage": "assess_split_risk"})
        assess = AsyncMock(return_value={"blocked_reasons": [], "current_stage": "run_draft_subgraph"})
        save_state = AsyncMock()
        persist = AsyncMock()
        enqueue_draft = AsyncMock()

        with patch("app.infrastructure.queue.archive_worker._load_workflow_state", new=AsyncMock(return_value=(config, dict(initial_state)))), patch(
            "app.services.archive_workflow.node_analyze_page_relations",
            new=analyze,
        ), patch(
            "app.services.archive_workflow.node_split_documents",
            new=split,
        ), patch(
            "app.services.archive_workflow.node_assess_split_risk",
            new=assess,
        ), patch("app.infrastructure.queue.archive_worker._save_checkpoint_state", new=save_state), patch(
            "app.infrastructure.queue.archive_worker._persist_workflow_progress",
            new=persist,
        ), patch("app.infrastructure.queue.archive_publisher.enqueue_draft_pipeline", new=enqueue_draft):
            await archive_worker._handle_relation_analysis(
                {
                    "run_id": "wf_existing",
                    "batch_id": "batch-a",
                    "tenant_id": "tenant-a",
                }
            )

        analyze.assert_awaited_once()
        split.assert_awaited_once()
        assess.assert_awaited_once()
        save_state.assert_awaited_once()
        persist.assert_awaited_once()
        enqueue_draft.assert_awaited_once_with(
            run_id="wf_existing",
            source_run_id="wf_existing",
            batch_id="batch-a",
            tenant_id="tenant-a",
            current_stage="run_draft_subgraph",
        )

    async def test_handle_draft_pipeline_blocks_when_review_needed(self):
        config = {"configurable": {"thread_id": "wf_existing"}}
        initial_state = {
            "task_id": "wf_existing",
            "batch_id": "batch-a",
            "tenant_id": "tenant-a",
            "draft_docs": [{"tmp_doc_id": "doc-1"}],
            "blocked_reasons": [],
        }
        draft_graph = SimpleNamespace(
            ainvoke=AsyncMock(
                return_value={
                    "current_stage": "wait_for_review",
                    "blocked_reasons": ["metadata missing"],
                    "review_tasks": ["rt_1"],
                }
            )
        )
        save_state = AsyncMock()
        mark_blocked = AsyncMock()
        persist = AsyncMock()
        enqueue_final = AsyncMock()

        with patch("app.infrastructure.queue.archive_worker._load_workflow_state", new=AsyncMock(return_value=(config, dict(initial_state)))), patch(
            "app.services.archive_workflow.archive_draft_subgraph",
            new=draft_graph,
        ), patch("app.infrastructure.queue.archive_worker._save_checkpoint_state", new=save_state), patch(
            "app.infrastructure.queue.archive_worker._mark_workflow_blocked",
            new=mark_blocked,
        ), patch("app.infrastructure.queue.archive_worker._persist_workflow_progress", new=persist), patch(
            "app.infrastructure.queue.archive_publisher.enqueue_final_pipeline",
            new=enqueue_final,
        ):
            await archive_worker._handle_draft_pipeline(
                {
                    "run_id": "wf_existing",
                    "batch_id": "batch-a",
                    "tenant_id": "tenant-a",
                    "current_stage": "run_draft_subgraph",
                }
            )

        save_state.assert_awaited_once()
        mark_blocked.assert_awaited_once()
        persist.assert_not_awaited()
        enqueue_final.assert_not_awaited()

    async def test_handle_draft_pipeline_enqueues_final_when_ready(self):
        config = {"configurable": {"thread_id": "wf_existing"}}
        initial_state = {
            "task_id": "wf_existing",
            "batch_id": "batch-a",
            "tenant_id": "tenant-a",
            "draft_docs": [{"tmp_doc_id": "doc-1"}],
            "blocked_reasons": [],
        }
        draft_graph = SimpleNamespace(
            ainvoke=AsyncMock(
                return_value={
                    "current_stage": "sort_documents_final",
                    "blocked_reasons": [],
                    "affected_scope": {"doc_ids": ["doc-1"]},
                }
            )
        )
        save_state = AsyncMock()
        mark_blocked = AsyncMock()
        persist = AsyncMock()
        enqueue_final = AsyncMock()

        with patch("app.infrastructure.queue.archive_worker._load_workflow_state", new=AsyncMock(return_value=(config, dict(initial_state)))), patch(
            "app.services.archive_workflow.archive_draft_subgraph",
            new=draft_graph,
        ), patch("app.infrastructure.queue.archive_worker._save_checkpoint_state", new=save_state), patch(
            "app.infrastructure.queue.archive_worker._mark_workflow_blocked",
            new=mark_blocked,
        ), patch("app.infrastructure.queue.archive_worker._persist_workflow_progress", new=persist), patch(
            "app.infrastructure.queue.archive_publisher.enqueue_final_pipeline",
            new=enqueue_final,
        ):
            await archive_worker._handle_draft_pipeline(
                {
                    "run_id": "wf_existing",
                    "batch_id": "batch-a",
                    "tenant_id": "tenant-a",
                    "current_stage": "run_draft_subgraph",
                }
            )

        mark_blocked.assert_not_awaited()
        persist.assert_awaited_once()
        enqueue_final.assert_awaited_once_with(
            run_id="wf_existing",
            source_run_id="wf_existing",
            batch_id="batch-a",
            tenant_id="tenant-a",
            current_stage="sort_documents_final",
            affected_scope={"doc_ids": ["doc-1"]},
            resume_from_checkpoint=None,
        )

    async def test_handle_draft_pipeline_routes_final_checkpoint_to_final_handler(self):
        forward_to_final = AsyncMock()

        with patch("app.infrastructure.queue.archive_worker._handle_final_pipeline", new=forward_to_final):
            await archive_worker._handle_draft_pipeline(
                {
                    "run_id": "wf_existing",
                    "batch_id": "batch-a",
                    "tenant_id": "tenant-a",
                    "resume_from_checkpoint": "build_catalog_final",
                }
            )

        forward_to_final.assert_awaited_once_with(
            {
                "run_id": "wf_existing",
                "batch_id": "batch-a",
                "tenant_id": "tenant-a",
                "resume_from_checkpoint": "build_catalog_final",
                "source_run_id": "wf_existing",
            }
        )

    async def test_handle_final_pipeline_persists_done_state(self):
        config = {"configurable": {"thread_id": "wf_existing"}}
        initial_state = {
            "task_id": "wf_existing",
            "batch_id": "batch-a",
            "tenant_id": "tenant-a",
            "final_docs": [{"tmp_doc_id": "doc-1"}],
            "artifacts": {},
        }
        final_graph = SimpleNamespace(
            ainvoke=AsyncMock(
                return_value={
                    "current_stage": "done",
                    "final_status": "done",
                    "artifacts": {"final_pdf_path": "tenant/tenant-a/batch/batch-a/final.pdf"},
                }
            )
        )
        save_state = AsyncMock()
        persist = AsyncMock()

        with patch("app.infrastructure.queue.archive_worker._load_workflow_state", new=AsyncMock(return_value=(config, dict(initial_state)))), patch(
            "app.services.archive_workflow.archive_final_subgraph",
            new=final_graph,
        ), patch("app.infrastructure.queue.archive_worker._save_checkpoint_state", new=save_state), patch(
            "app.infrastructure.queue.archive_worker._persist_workflow_progress",
            new=persist,
        ):
            await archive_worker._handle_final_pipeline(
                {
                    "run_id": "wf_existing",
                    "batch_id": "batch-a",
                    "tenant_id": "tenant-a",
                    "current_stage": "sort_documents_final",
                }
            )

        save_state.assert_awaited_once()
        persist.assert_awaited_once()
        persist_kwargs = persist.await_args.kwargs
        self.assertEqual(persist_kwargs["run_id"], "wf_existing")
        self.assertEqual(persist_kwargs["current_stage"], "done")
        self.assertEqual(persist_kwargs["run_status"], "done")


class _DummyDB:
    pass


class _ScalarResult:
    def __init__(self, values):
        self._values = list(values)

    def scalar_one_or_none(self):
        return self._values[0] if self._values else None

    def scalars(self):
        return self

    def all(self):
        return list(self._values)


class _ArchiveRouteDB:
    def __init__(self, *results):
        self._results = list(results)
        self.commit = AsyncMock()
        self.added: list[object] = []

    async def execute(self, *_args, **_kwargs):
        if self._results:
            return self._results.pop(0)
        return _ScalarResult([])

    def add(self, obj):
        self.added.append(obj)


class _ScalarOneOrNoneResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeAsyncSession:
    def __init__(self, existing_run):
        self._existing_run = existing_run
        self.execute = AsyncMock(return_value=_ScalarOneOrNoneResult(existing_run))
        self.commit = AsyncMock()
        self.rollback = AsyncMock()
        self.added: list[object] = []

    def add(self, obj):
        self.added.append(obj)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeHttpResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


class _FakeHttpClient:
    def __init__(self, calls: list[dict[str, object]], response: _FakeHttpResponse):
        self._calls = calls
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json, headers):
        self._calls.append({"url": url, "json": json, "headers": headers})
        return self._response


class ArchiveWorkflowRuntimeGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_node_ingest_batch_reuses_existing_workflow_run(self):
        existing_run = SimpleNamespace(
            batch_id="batch-a",
            tenant_id="tenant-a",
            run_type="normal",
            run_status="blocked",
            current_stage="wait_for_review",
            blocked_reasons_json=["stale"],
            policy_snapshot_id=None,
            state_json={"request_id": "req-1"},
        )
        fake_session = _FakeAsyncSession(existing_run)
        emit_started = AsyncMock()

        with patch("app.db.database.async_session", return_value=fake_session), patch(
            "app.infrastructure.callback.workflow_events.emit_workflow_started",
            new=emit_started,
        ):
            result = await workflow_service.node_ingest_batch(
                {
                    "task_id": "wf_existing",
                    "batch_id": "batch-a",
                    "tenant_id": "tenant-a",
                    "run_mode": "normal",
                    "policy_snapshot_id": "policy-v1",
                    "pages": [{"page_id": "page-1"}],
                }
            )

        self.assertEqual(fake_session.added, [])
        self.assertEqual(existing_run.run_status, "running")
        self.assertEqual(existing_run.current_stage, "ingest_batch")
        self.assertEqual(existing_run.blocked_reasons_json, [])
        self.assertEqual(existing_run.policy_snapshot_id, "policy-v1")
        fake_session.commit.assert_awaited_once()
        emit_started.assert_awaited_once()
        self.assertEqual(result["current_stage"], "load_policy_snapshot")

    async def test_workflow_event_404_disables_repeated_sends_for_same_endpoint(self):
        calls: list[dict[str, object]] = []
        fake_response = _FakeHttpResponse(404, '{"error":"Not Found"}')

        def fake_async_client(*args, **kwargs):
            return _FakeHttpClient(calls, fake_response)

        workflow_events._DISABLED_WORKFLOW_EVENT_URLS.clear()
        try:
            with patch.dict(
                os.environ,
                {
                    "CONTROL_PLANE_BASE_URL": "http://127.0.0.1:8080",
                    "CONTROL_PLANE_INTERNAL_TOKEN": "internal-token",
                    "CONTROL_PLANE_WORKFLOW_EVENTS_PATH": "/internal/events/workflow",
                    "CONTROL_PLANE_CALLBACK_TIMEOUT_SECONDS": "3",
                    "CONTROL_PLANE_VERIFY_TLS": "false",
                },
                clear=False,
            ), patch(
                "app.infrastructure.callback.workflow_events.httpx.AsyncClient",
                side_effect=fake_async_client,
            ):
                await workflow_events.emit_workflow_started(
                    task_id="wf_existing",
                    batch_id="batch-a",
                    tenant_id="tenant-a",
                    page_count=1,
                )
                await workflow_events.emit_workflow_started(
                    task_id="wf_existing",
                    batch_id="batch-a",
                    tenant_id="tenant-a",
                    page_count=1,
                )
        finally:
            workflow_events._DISABLED_WORKFLOW_EVENT_URLS.clear()

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["url"], "http://127.0.0.1:8080/internal/events/workflow")
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer internal-token")
        self.assertEqual(calls[0]["headers"]["X-Internal-Token"], "internal-token")

    async def test_build_workflow_pages_from_ocr_tasks_restores_text_pages(self):
        task = SimpleNamespace(
            id=7,
            result_json=[
                {
                    "page_num": 1,
                    "regions": [{"type": "text", "content": "标题"}],
                    "lines": [{"line_num": 1, "text": "标题", "confidence": 0.99, "bbox": []}],
                },
                {
                    "page_num": 2,
                    "regions": [],
                    "lines": [{"line_num": 1, "text": "正文", "confidence": 0.95, "bbox": []}],
                },
            ],
            full_text="标题\n正文",
        )

        pages = __import__("app.api.archive_workflow", fromlist=["_build_workflow_pages_from_ocr_tasks"])._build_workflow_pages_from_ocr_tasks([task], "batch-a")

        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0]["page_index"], 0)
        self.assertEqual(pages[0]["ocr_text"], "标题")
        self.assertEqual(pages[1]["ocr_text"], "正文")
        self.assertEqual(pages[0]["layout_type"], "text")


class ArchiveWorkflowRouteTests(unittest.TestCase):
    def setUp(self):
        self.db = _ArchiveRouteDB(_ScalarResult([]))
        self.app = FastAPI()
        self.app.include_router(archive_workflow_router)

        async def override_get_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_get_db
        self.app.dependency_overrides[require_auth] = lambda: {
            "username": "tester",
            "is_admin": True,
            "user_status": "active",
            "user_id": 1,
            "role": "admin",
            "capabilities": "operator",
            "tenant_id": "default",
        }
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()

    def test_start_batch_workflow_uses_prepared_pages(self):
        batch = SimpleNamespace(
            batch_id="batch-a",
            tenant_id="default",
            status="draft",
            draft_status="pending",
            page_count=0,
            policy_snapshot_id="policy-v1",
        )
        enqueue = AsyncMock()

        with patch("app.api.archive_workflow._find_batch", new=AsyncMock(return_value=batch)), patch(
            "app.api.archive_workflow._resolve_batch_start_inputs",
            new=AsyncMock(return_value=([
                {"page_id": "page-1", "page_index": 0, "ocr_text": "第一页", "ocr_blocks": {}, "layout_type": "text"}
            ], [], 1, "ocr_tasks")),
        ), patch("app.api.archive_workflow.enqueue_workflow_start", new=enqueue):
            response = self.client.post("/api/archive/batches/batch-a/start", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "processing")
        self.assertEqual(batch.status, "processing")
        self.assertEqual(batch.page_count, 1)
        enqueue.assert_awaited_once()
        self.assertEqual(enqueue.await_args.kwargs["pages"][0]["ocr_text"], "第一页")

    def test_start_batch_workflow_rejects_empty_inputs(self):
        batch = SimpleNamespace(
            batch_id="batch-a",
            tenant_id="default",
            status="draft",
            draft_status="pending",
            page_count=0,
            policy_snapshot_id=None,
        )

        with patch("app.api.archive_workflow._find_batch", new=AsyncMock(return_value=batch)), patch(
            "app.api.archive_workflow._resolve_batch_start_inputs",
            new=AsyncMock(return_value=([], [], 0, "empty")),
        ):
            response = self.client.post("/api/archive/batches/batch-a/start", json={})

        self.assertEqual(response.status_code, 400)
        self.assertIn("Batch has no source files or completed OCR task results", response.json()["detail"])

    def test_get_dashboard_stats_handles_naive_and_aware_datetimes(self):
        self.db = _ArchiveRouteDB(
            _ScalarResult([
                SimpleNamespace(created_at=datetime(2026, 4, 13, 9, 0, 0), status="processing"),
            ]),
            _ScalarResult([]),
            _ScalarResult([]),
            _ScalarResult([
                SimpleNamespace(created_at=datetime(2026, 4, 10, 12, 0, 0)),
                SimpleNamespace(created_at=datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)),
            ]),
            _ScalarResult([]),
            _ScalarResult([SimpleNamespace(id="default")]),
        )

        async def override_get_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_get_db

        with patch("app.api.archive_workflow._utc_now", return_value=datetime(2026, 4, 13, 12, 0, 0, tzinfo=timezone.utc)):
            response = self.client.get("/api/archive/dashboard/stats")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["todayTasks"], 1)
        self.assertEqual(payload["recentArchived"], 1)

    def test_submit_review_enqueues_resume_only_when_workflow_unblocked(self):
        task = SimpleNamespace(
            review_task_id="rt-1",
            task_type="metadata",
            affected_doc_ids_json=["doc-1"],
            batch_id="batch-a",
            run_id="wf-1",
            reason="metadata review",
        )
        workflow_run = SimpleNamespace(run_id="wf-1", run_status="running", current_stage="resume_from_review")
        self.db = _ArchiveRouteDB(_ScalarResult([workflow_run]))

        async def override_get_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_get_db
        enqueue = AsyncMock()

        with patch("app.api.archive_workflow._find_review_task", new=AsyncMock(return_value=task)), patch(
            "app.api.archive_workflow.submit_review_result",
            new=AsyncMock(return_value=True),
        ), patch("app.api.archive_workflow.enqueue_workflow_resume", new=enqueue):
            response = self.client.post(
                "/api/archive/tasks/rt-1/submit",
                json={"decision": "approve", "metadata": {"title": "修正题名"}},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["resumed"])
        kwargs = enqueue.await_args.kwargs
        self.assertEqual(kwargs["run_id"], "wf-1")
        self.assertEqual(kwargs["batch_id"], "batch-a")
        self.assertEqual(kwargs["resume_from_checkpoint"], "build_catalog_final")
        self.assertEqual(kwargs["review_result"]["result_type"], "field_corrected")
        self.assertEqual(kwargs["review_result"]["field_updates"]["doc-1"]["title"], "修正题名")

    def test_submit_review_skips_resume_when_other_tasks_still_pending(self):
        task = SimpleNamespace(
            review_task_id="rt-1",
            task_type="boundary",
            affected_doc_ids_json=["doc-1"],
            batch_id="batch-a",
            run_id="wf-1",
            reason="boundary review",
        )
        workflow_run = SimpleNamespace(run_id="wf-1", run_status="blocked", current_stage="wait_for_review")
        self.db = _ArchiveRouteDB(_ScalarResult([workflow_run]))

        async def override_get_db():
            yield self.db

        self.app.dependency_overrides[get_db] = override_get_db
        enqueue = AsyncMock()

        with patch("app.api.archive_workflow._find_review_task", new=AsyncMock(return_value=task)), patch(
            "app.api.archive_workflow.submit_review_result",
            new=AsyncMock(return_value=True),
        ), patch("app.api.archive_workflow.enqueue_workflow_resume", new=enqueue):
            response = self.client.post(
                "/api/archive/tasks/rt-1/submit",
                json={"decision": "approve"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["resumed"])
        enqueue.assert_not_awaited()


class InternalWorkflowRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(internal_workflow_router)

        async def override_get_db():
            yield _DummyDB()

        self.app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()

    def test_recompute_route_reuses_existing_run_and_normalizes_scope(self):
        enqueue_resume = AsyncMock()

        with patch.dict(os.environ, {"CONTROL_PLANE_INTERNAL_TOKEN": "internal-token"}, clear=False), patch(
            "app.api.internal.workflow._find_latest_batch_run",
            new=AsyncMock(return_value=SimpleNamespace(run_id="wf_existing")),
        ), patch("app.infrastructure.queue.archive_publisher.enqueue_workflow_resume", new=enqueue_resume):
            response = self.client.post(
                "/internal/recompute/affected-scope",
                headers={"x-internal-token": "internal-token"},
                json={
                    "batch_id": "batch-a",
                    "tenant_id": "tenant-a",
                    "affected_scope": {
                        "doc_ids": ["doc-1"],
                        "regenerate_catalog": True,
                    },
                    "recompute_targets": ["catalog"],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["run_id"], "wf_existing")

        kwargs = enqueue_resume.await_args.kwargs
        self.assertEqual(kwargs["run_id"], "wf_existing")
        self.assertEqual(kwargs["batch_id"], "batch-a")
        self.assertEqual(kwargs["reason"], "recompute_affected_scope")
        self.assertEqual(kwargs["resume_from_checkpoint"], "build_catalog_final")
        self.assertEqual(kwargs["affected_scope"]["doc_ids"], ["doc-1"])
        self.assertTrue(kwargs["affected_scope"]["regenerate_catalog"])
        self.assertTrue(kwargs["affected_scope"]["invalidate_catalog"])
        self.assertEqual(kwargs["affected_scope"]["recompute_targets"], ["catalog"])


if __name__ == "__main__":
    unittest.main()