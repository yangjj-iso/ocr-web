from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.auth import effective_role, require_auth
from app.db.models import (
    AppUser,
    ArchiveRecord,
    ArtifactFile,
    BatchRecord,
    DocUnit,
    DocVersion,
    PageRecord,
    PolicySnapshot,
    ReworkTask,
    ReviewActionLog,
    ReviewTask,
    SourceFile,
    Tenant,
    WorkflowRun,
)
from app.domains.archive.archive_service import resume_archive_workflow
from app.domains.review.review_service import submit_review_result
from app.infrastructure.queue.archive_publisher import enqueue_workflow_start

router = APIRouter(prefix="/api/archive", tags=["archive-workflow"], dependencies=[Depends(require_auth)])

_BATCH_ID_RE = re.compile(r"[^a-zA-Z0-9_-]+")


class BatchCreateRequest(BaseModel):
    name: str | None = None
    policy_snapshot_id: str | None = None
    notes: str | None = None


class BatchStartRequest(BaseModel):
    policy_snapshot_id: str | None = None


class TaskAssignRequest(BaseModel):
    task_id: str | None = None
    task_ids: list[str] = Field(default_factory=list)
    assignee_id: int | None = None
    assignee_username: str | None = None
    notes: str | None = None


class ReviewSubmitRequest(BaseModel):
    decision: str = "approve"
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    doc_id: str | None = None
    rework: dict[str, Any] = Field(default_factory=dict)


class DocMetadataUpdateRequest(BaseModel):
    title: str | None = None
    responsible: str | None = None
    responsible_party: str | None = None
    doc_no: str | None = None
    date: str | None = None
    preservation_period: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class ReworkCreateRequest(BaseModel):
    record_id: str | None = None
    batch_id: str | None = None
    record_version: int | None = None
    issue_type: str = "other"
    affected_scope: str | dict[str, Any] | None = None
    description: str = ""
    priority: str = "normal"
    rework_level: str = "partial"


class PolicySnapshotCreateRequest(BaseModel):
    version_tag: str | None = None
    rules_json: dict[str, Any] = Field(default_factory=dict)


class PolicySnapshotUpdateRequest(BaseModel):
    version_tag: str | None = None
    rules_json: dict[str, Any] | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _role(current: dict[str, Any]) -> str:
    return effective_role(current)


def _is_platform_admin(current: dict[str, Any]) -> bool:
    return _role(current) == "admin"


def _tenant_id(current: dict[str, Any]) -> str:
    return str(current.get("tenant_id") or "default")


def _normalize_status(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"pending", "draft", "none"}:
        return "pending"
    if normalized in {"running", "processing", "claimed", "accepted", "in_rework", "in_review"}:
        return "processing"
    if normalized in {"done", "resolved", "submitted", "completed", "archived"}:
        return "done"
    if normalized in {"failed", "error"}:
        return "failed"
    if normalized in {"rejected", "cancelled"}:
        return "rejected"
    return normalized or "pending"


def _normalize_review_filter(value: str | None) -> set[str]:
    normalized = str(value or "").strip().lower()
    if normalized in {"", "all"}:
        return set()
    if normalized == "human_review":
        return {"pending", "claimed"}
    if normalized == "pending":
        return {"pending"}
    if normalized == "processing":
        return {"claimed"}
    if normalized == "done":
        return {"submitted", "resolved"}
    if normalized == "failed":
        return {"failed"}
    return {normalized}


def _normalize_review_type(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    aliases = {
        "boundary_review": "boundary",
        "metadata_review": "metadata",
        "order_review": "ordering",
        "ordering_review": "ordering",
    }
    return aliases.get(normalized, normalized)


def _normalize_issue_type(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    mapping = {
        "boundary_error": "boundary",
        "metadata_error": "metadata",
        "ordering_error": "ordering",
        "missing_page": "boundary",
        "pdf_quality": "other",
    }
    return mapping.get(normalized, normalized or "other")


def _normalize_rework_status(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"accepted", "in_rework"}:
        return "processing"
    if normalized == "rejected":
        return "rejected"
    if normalized == "done":
        return "done"
    return "pending"


def _make_batch_id(name: str | None) -> str:
    raw = str(name or "").strip()
    if not raw:
        return f"batch_{_utc_now().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:6]}"
    slug = _BATCH_ID_RE.sub("_", raw).strip("_")[:48]
    if not slug:
        slug = "batch"
    return f"{slug}_{uuid4().hex[:6]}"


def _matches_keyword(values: list[Any], keyword: str) -> bool:
    lowered = keyword.strip().lower()
    if not lowered:
        return True
    return any(lowered in str(value or "").lower() for value in values)


def _paginate(items: list[dict[str, Any]], page: int, page_size: int) -> dict[str, Any]:
    safe_page = max(1, page)
    safe_page_size = max(1, page_size)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return {"items": items[start:end], "total": len(items)}


async def _users_by_id(db: AsyncSession, user_ids: list[int]) -> dict[int, AppUser]:
    unique_ids = sorted({user_id for user_id in user_ids if user_id})
    if not unique_ids:
        return {}
    users = (await db.execute(select(AppUser).where(AppUser.id.in_(unique_ids)))).scalars().all()
    return {user.id: user for user in users}


async def _policies_by_snapshot_id(db: AsyncSession, snapshot_ids: list[str]) -> dict[str, PolicySnapshot]:
    unique_ids = sorted({snapshot_id for snapshot_id in snapshot_ids if snapshot_id})
    if not unique_ids:
        return {}
    snapshots = (await db.execute(select(PolicySnapshot).where(PolicySnapshot.snapshot_id.in_(unique_ids)))).scalars().all()
    return {snapshot.snapshot_id: snapshot for snapshot in snapshots}


async def _latest_runs_by_batch(db: AsyncSession, batch_ids: list[str]) -> dict[str, WorkflowRun]:
    unique_ids = sorted({batch_id for batch_id in batch_ids if batch_id})
    if not unique_ids:
        return {}
    runs = (
        await db.execute(
            select(WorkflowRun)
            .where(WorkflowRun.batch_id.in_(unique_ids))
            .order_by(desc(WorkflowRun.created_at))
        )
    ).scalars().all()
    grouped: dict[str, WorkflowRun] = {}
    for run in runs:
        grouped.setdefault(run.batch_id, run)
    return grouped


async def _source_counts_by_batch(db: AsyncSession, batch_ids: list[str]) -> dict[str, int]:
    unique_ids = sorted({batch_id for batch_id in batch_ids if batch_id})
    if not unique_ids:
        return {}
    rows = (await db.execute(select(SourceFile).where(SourceFile.batch_id.in_(unique_ids)))).scalars().all()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.batch_id] = counts.get(row.batch_id, 0) + 1
    return counts


async def _doc_counts_by_batch(db: AsyncSession, batch_ids: list[str]) -> tuple[dict[str, int], dict[str, int]]:
    unique_ids = sorted({batch_id for batch_id in batch_ids if batch_id})
    if not unique_ids:
        return {}, {}
    docs = (await db.execute(select(DocUnit).where(DocUnit.batch_id.in_(unique_ids)))).scalars().all()
    total_counts: dict[str, int] = {}
    done_counts: dict[str, int] = {}
    for doc in docs:
        total_counts[doc.batch_id] = total_counts.get(doc.batch_id, 0) + 1
        if str(doc.status or "").lower() in {"final", "archived"}:
            done_counts[doc.batch_id] = done_counts.get(doc.batch_id, 0) + 1
    return total_counts, done_counts


async def _review_counts_by_batch(db: AsyncSession, batch_ids: list[str]) -> dict[str, dict[str, int]]:
    unique_ids = sorted({batch_id for batch_id in batch_ids if batch_id})
    if not unique_ids:
        return {}
    tasks = (await db.execute(select(ReviewTask).where(ReviewTask.batch_id.in_(unique_ids)))).scalars().all()
    grouped: dict[str, dict[str, int]] = {}
    for task in tasks:
        bucket = grouped.setdefault(task.batch_id, {"pending": 0, "claimed": 0, "submitted": 0, "final_release": 0})
        status_key = str(task.status or "").lower()
        if status_key in bucket:
            bucket[status_key] += 1
        if str(task.task_type or "") == "final_release" and status_key in {"pending", "claimed"}:
            bucket["final_release"] += 1
    return grouped


async def _batch_pdf_urls_by_batch(db: AsyncSession, batch_ids: list[str]) -> dict[str, str]:
    unique_ids = sorted({batch_id for batch_id in batch_ids if batch_id})
    if not unique_ids:
        return {}
    artifacts = (
        await db.execute(
            select(ArtifactFile)
            .where(ArtifactFile.batch_id.in_(unique_ids))
            .order_by(desc(ArtifactFile.created_at))
        )
    ).scalars().all()
    urls: dict[str, str] = {}
    preferred = {"final_searchable_pdf", "draft_searchable_pdf"}
    for artifact in artifacts:
        if artifact.batch_id in urls:
            continue
        if artifact.artifact_type in preferred and artifact.storage_uri:
            urls[artifact.batch_id] = artifact.storage_uri
    return urls


def _workflow_stages(batch: BatchRecord, latest_run: WorkflowRun | None, review_counts: dict[str, int], total_docs: int, done_docs: int) -> list[dict[str, Any]]:
    review_pending = review_counts.get("pending", 0) + review_counts.get("claimed", 0)
    review_status = "pending" if review_pending else ("done" if review_counts.get("submitted", 0) else "pending")
    if str(batch.review_status or "").lower() in {"pending", "in_review"}:
        review_status = "processing" if review_counts.get("claimed", 0) else "pending"
    if review_pending == 0 and str(batch.review_status or "").lower() == "resolved":
        review_status = "done"

    def stage_status(raw: str | None) -> str:
        normalized = str(raw or "").strip().lower()
        if normalized in {"running", "processing", "blocked", "in_review", "pending"}:
            return "processing" if normalized in {"running", "processing", "in_review"} else "pending"
        if normalized in {"done", "resolved", "completed"}:
            return "done"
        if normalized == "failed":
            return "failed"
        return "pending"

    stages = [
        {"name": "ingest", "label": "批次建立", "status": "done", "count": None},
        {"name": "draft", "label": "草稿处理", "status": stage_status(batch.draft_status), "count": total_docs or None},
        {"name": "review", "label": "人工审核", "status": review_status, "count": review_pending or None},
        {"name": "final", "label": "正式编目", "status": stage_status(batch.final_status), "count": done_docs or None},
        {"name": "export", "label": "导出归档", "status": stage_status(batch.export_status), "count": None},
    ]
    if latest_run and str(latest_run.run_status or "").lower() == "failed":
        for stage in stages:
            if stage["status"] == "processing":
                stage["status"] = "failed"
                break
    return stages


def _batch_ui_status(batch: BatchRecord, latest_run: WorkflowRun | None, review_counts: dict[str, int]) -> str:
    values = [
        str(batch.status or "").lower(),
        str(batch.draft_status or "").lower(),
        str(batch.final_status or "").lower(),
        str(batch.export_status or "").lower(),
        str(latest_run.run_status or "").lower() if latest_run else "",
    ]
    if "failed" in values:
        return "failed"
    if review_counts.get("pending", 0) or review_counts.get("claimed", 0) or str(batch.review_status or "").lower() in {"pending", "in_review"}:
        return "review_required"
    if str(batch.final_status or "").lower() == "done" or str(batch.status or "").lower() == "done":
        return "done"
    if any(value in {"processing", "running", "blocked"} for value in values):
        return "processing"
    return "draft"


def _serialize_batch(
    batch: BatchRecord,
    *,
    latest_run: WorkflowRun | None,
    source_count: int,
    total_docs: int,
    done_docs: int,
    review_counts: dict[str, int],
    created_by: str,
    policy_version: str,
) -> dict[str, Any]:
    file_count = source_count or total_docs or batch.page_count or 0
    return {
        "id": batch.id,
        "batch_id": batch.batch_id,
        "status": _batch_ui_status(batch, latest_run, review_counts),
        "file_count": file_count,
        "page_count": batch.page_count,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "updated_at": batch.updated_at.isoformat() if batch.updated_at else None,
        "created_by": created_by,
        "policy_snapshot_id": batch.policy_snapshot_id,
        "policy_snapshot_version": policy_version,
        "draft_status": batch.draft_status,
        "final_status": batch.final_status,
        "review_status": batch.review_status,
        "export_status": batch.export_status,
        "current_stage": latest_run.current_stage if latest_run else None,
        "run_status": latest_run.run_status if latest_run else None,
        "workflow_stages": _workflow_stages(batch, latest_run, review_counts, total_docs, done_docs),
        "total_docs": total_docs,
        "done_docs": done_docs,
    }


async def _find_batch(db: AsyncSession, batch_id: str, current: dict[str, Any]) -> BatchRecord | None:
    batch = (
        await db.execute(select(BatchRecord).where(BatchRecord.batch_id == batch_id).limit(1))
    ).scalar_one_or_none()
    if not batch:
        return None
    if not _is_platform_admin(current) and batch.tenant_id != _tenant_id(current):
        return None
    return batch


async def _find_review_task(db: AsyncSession, task_id: str, current: dict[str, Any]) -> ReviewTask | None:
    task: ReviewTask | None = None
    if task_id.isdigit():
        task = (await db.execute(select(ReviewTask).where(ReviewTask.id == int(task_id)).limit(1))).scalar_one_or_none()
    if not task:
        task = (
            await db.execute(select(ReviewTask).where(ReviewTask.review_task_id == task_id).limit(1))
        ).scalar_one_or_none()
    if not task:
        return None
    if not _is_platform_admin(current) and task.tenant_id != _tenant_id(current):
        return None
    return task


async def _find_policy_snapshot(db: AsyncSession, snapshot_id: str, current: dict[str, Any]) -> PolicySnapshot | None:
    snapshot: PolicySnapshot | None = None
    if snapshot_id.isdigit():
        snapshot = (
            await db.execute(select(PolicySnapshot).where(PolicySnapshot.id == int(snapshot_id)).limit(1))
        ).scalar_one_or_none()
    if not snapshot:
        snapshot = (
            await db.execute(select(PolicySnapshot).where(PolicySnapshot.snapshot_id == snapshot_id).limit(1))
        ).scalar_one_or_none()
    if not snapshot:
        return None
    if not _is_platform_admin(current) and snapshot.tenant_id != _tenant_id(current):
        return None
    return snapshot


async def _current_doc_versions_by_batch(db: AsyncSession, batch_id: str) -> dict[str, DocVersion]:
    stmt = select(DocVersion).where(DocVersion.batch_id == batch_id, DocVersion.is_current.is_(True))
    versions = (await db.execute(stmt)).scalars().all()
    return {version.doc_id: version for version in versions}


async def _page_records_by_ids(db: AsyncSession, page_ids: list[str]) -> dict[str, PageRecord]:
    unique_ids = sorted({page_id for page_id in page_ids if page_id})
    if not unique_ids:
        return {}
    pages = (await db.execute(select(PageRecord).where(PageRecord.page_id.in_(unique_ids)))).scalars().all()
    return {page.page_id: page for page in pages}


def _batch_pdf_url_for_storage(storage_uri: str | None) -> str | None:
    if not storage_uri:
        return None
    if storage_uri.startswith("/"):
        return storage_uri
    return storage_uri


async def _serialize_doc_versions(db: AsyncSession, batch_id: str, doc_ids: list[str] | None = None) -> list[dict[str, Any]]:
    versions = await _current_doc_versions_by_batch(db, batch_id)
    selected = list(versions.values())
    if doc_ids is not None:
        selected = [version for version in selected if version.doc_id in set(doc_ids)]
    selected.sort(key=lambda version: (version.sort_index, version.created_at or _utc_now()))
    page_id_pool = [page_id for version in selected for page_id in (version.page_ids_json or [])]
    page_map = await _page_records_by_ids(db, page_id_pool)
    batch_pdf_urls = await _batch_pdf_urls_by_batch(db, [batch_id])
    batch_pdf_url = _batch_pdf_url_for_storage(batch_pdf_urls.get(batch_id))

    items: list[dict[str, Any]] = []
    for version in selected:
        metadata = dict(version.metadata_json or {})
        page_ids = list(version.page_ids_json or [])
        page_records = [page_map[page_id] for page_id in page_ids if page_id in page_map]
        items.append(
            {
                "id": version.doc_id,
                "doc_id": version.doc_id,
                "name": metadata.get("title") or f"文档 {version.sort_index + 1}",
                "title": metadata.get("title") or f"文档 {version.sort_index + 1}",
                "status": "done" if version.version_type == "final" else "pending",
                "page_count": len(page_ids) or max(0, int(version.end_page or 0) - int(version.start_page or 0) + 1),
                "pages": len(page_ids) or max(0, int(version.end_page or 0) - int(version.start_page or 0) + 1),
                "metadata": {
                    **metadata,
                    "responsible": metadata.get("responsible") or metadata.get("responsible_party") or "",
                },
                "fields": {
                    **metadata,
                    "responsible": metadata.get("responsible") or metadata.get("responsible_party") or "",
                },
                "pdf_url": batch_pdf_url,
                "preview_url": batch_pdf_url,
                "ocr_pages": [
                    {
                        "page_no": index + 1,
                        "page": index + 1,
                        "text": page.ocr_text or "",
                    }
                    for index, page in enumerate(page_records)
                ],
                "risk_level": "medium"
                if not (metadata.get("title") and metadata.get("date"))
                else "",
            }
        )
    return items


def _archive_record_to_output(record: ArchiveRecord, *, last_rework_status: str | None = None) -> dict[str, Any]:
    file_url = f"/api/ocr/tasks/{record.task_id}/file" if record.task_id else None
    return {
        "id": record.id,
        "record_id": record.id,
        "task_id": record.task_id,
        "batch_id": record.batch_id,
        "folder": record.batch_folder,
        "archive_no": record.archive_no,
        "doc_no": record.doc_no,
        "responsible": record.responsible,
        "title": record.title,
        "date": record.date,
        "pages": record.pages,
        "classification": record.classification,
        "remarks": record.remarks,
        "storage_path": record.storage_path,
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "status": "archived",
        "file_url": file_url,
        "pdf_url": file_url,
        "preservation_period": None,
        "last_rework_status": last_rework_status,
    }


def _review_task_item(task: ReviewTask, users: dict[int, AppUser]) -> dict[str, Any]:
    assignee = users.get(task.assignee_user_id or 0)
    task_type = {
        "boundary": "boundary_review",
        "metadata": "metadata_review",
        "ordering": "order_review",
    }.get(task.task_type, task.task_type)
    return {
        "id": task.review_task_id,
        "review_task_id": task.review_task_id,
        "type": task_type,
        "task_type": task_type,
        "batch_id": task.batch_id,
        "status": _normalize_status(task.status),
        "assignee": assignee.username if assignee else None,
        "assignee_name": (assignee.display_name or assignee.username) if assignee else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
        "title": task.reason or task.review_task_id,
        "reason": task.reason,
        "confidence": task.confidence,
        "doc_count": len(task.affected_doc_ids_json or []),
    }


def _build_review_result(task: ReviewTask, body: ReviewSubmitRequest) -> dict[str, Any]:
    doc_ids = [doc_id for doc_id in (task.affected_doc_ids_json or []) if doc_id]
    metadata = dict(body.metadata or {})
    decision = str(body.decision or "approve").strip().lower()
    if decision == "reject":
        return {
            "result_type": "boundary_rejected",
            "affected_doc_ids": doc_ids,
            "reason": body.reason or "人工驳回，待返工处理。",
        }

    if task.task_type == "metadata":
        updates = metadata or {}
        field_updates = {doc_id: updates for doc_id in doc_ids} if doc_ids else {}
        return {
            "result_type": "field_corrected",
            "affected_doc_ids": doc_ids,
            "changed_fields": list(updates.keys()),
            "field_updates": field_updates,
        }

    if task.task_type == "ordering":
        return {
            "result_type": "order_adjusted",
            "affected_doc_ids": doc_ids,
            "from_order_index": 0,
        }

    return {
        "result_type": "boundary_confirmed",
        "affected_doc_ids": doc_ids,
    }


async def _create_rework_task(
    db: AsyncSession,
    *,
    current: dict[str, Any],
    batch_id: str,
    record_id: str | None,
    record_version: int | None,
    issue_type: str,
    description: str,
    priority: str,
    rework_level: str,
    affected_scope: dict[str, Any],
) -> ReworkTask:
    rework = ReworkTask(
        rework_task_id=f"rw_{batch_id}_{uuid4().hex[:8]}",
        batch_id=batch_id,
        tenant_id=_tenant_id(current),
        record_version=record_version or 1,
        issue_type=_normalize_issue_type(issue_type),
        affected_scope_json={
            **affected_scope,
            "record_id": record_id,
            "priority": priority,
        },
        description=description.strip(),
        reported_by=current.get("user_id"),
        status="pending",
        rework_level=rework_level or "partial",
    )
    db.add(rework)
    await db.commit()
    await db.refresh(rework)
    return rework


@router.get("/dashboard/stats")
async def get_dashboard_stats(
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    tenant_id = _tenant_id(current)
    is_platform_admin = _is_platform_admin(current)

    batch_stmt = select(BatchRecord).order_by(desc(BatchRecord.created_at))
    review_stmt = select(ReviewTask).order_by(desc(ReviewTask.created_at))
    rework_stmt = select(ReworkTask).order_by(desc(ReworkTask.created_at))
    policy_stmt = select(PolicySnapshot).order_by(desc(PolicySnapshot.created_at))
    if not is_platform_admin:
        batch_stmt = batch_stmt.where(BatchRecord.tenant_id == tenant_id)
        review_stmt = review_stmt.where(ReviewTask.tenant_id == tenant_id)
        rework_stmt = rework_stmt.where(ReworkTask.tenant_id == tenant_id)
        policy_stmt = policy_stmt.where(PolicySnapshot.tenant_id == tenant_id)

    batches = (await db.execute(batch_stmt)).scalars().all()
    review_tasks = (await db.execute(review_stmt)).scalars().all()
    rework_tasks = (await db.execute(rework_stmt)).scalars().all()
    archive_records = (await db.execute(select(ArchiveRecord).order_by(desc(ArchiveRecord.created_at)))).scalars().all()
    policies = (await db.execute(policy_stmt)).scalars().all()

    today_key = _utc_now().date()
    today_batches = [batch for batch in batches if batch.created_at and batch.created_at.date() == today_key]
    failed_today = [batch for batch in today_batches if str(batch.status or "").lower() == "failed"]
    my_user_id = current.get("user_id")

    return {
        "tenants": len((await db.execute(select(Tenant))).scalars().all()) if is_platform_admin else None,
        "todayTasks": len(today_batches),
        "processingTasks": len([batch for batch in batches if str(batch.status or "").lower() == "processing"]),
        "failRate": round((len(failed_today) / len(today_batches)) * 100, 1) if today_batches else 0,
        "pendingBatches": len([batch for batch in batches if _batch_ui_status(batch, None, {}) == "draft"]),
        "pendingRelease": len([task for task in review_tasks if task.task_type == "final_release" and task.status in {"pending", "claimed"}]),
        "reworking": len([task for task in rework_tasks if task.status in {"accepted", "in_rework"}]),
        "recentArchived": len([record for record in archive_records if record.created_at and (_utc_now() - record.created_at).days <= 7]),
        "myReworks": len([task for task in rework_tasks if my_user_id and task.reported_by == my_user_id]),
        "pendingReworks": len([task for task in rework_tasks if task.status in {"pending", "accepted", "in_rework"}]),
        "totalArchived": len(archive_records),
        "myPendingTasks": len([task for task in review_tasks if my_user_id and task.assignee_user_id == my_user_id and task.status in {"pending", "claimed"}]),
        "boundaryTasks": len([task for task in review_tasks if task.task_type == "boundary" and task.status in {"pending", "claimed"}]),
        "metadataTasks": len([task for task in review_tasks if task.task_type == "metadata" and task.status in {"pending", "claimed"}]),
        "rejectedTasks": len([task for task in rework_tasks if my_user_id and task.reported_by == my_user_id and task.status == "rejected"]),
        "policySnapshots": len(policies),
    }


@router.get("/policy-snapshots")
async def list_policy_snapshots(
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(PolicySnapshot).order_by(desc(PolicySnapshot.created_at))
    if not _is_platform_admin(current):
        stmt = stmt.where(PolicySnapshot.tenant_id == _tenant_id(current))
    snapshots = (await db.execute(stmt)).scalars().all()
    items = [
        {
            "id": snapshot.snapshot_id,
            "snapshot_id": snapshot.snapshot_id,
            "version": snapshot.version_tag,
            "created_by": snapshot.created_by,
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        }
        for snapshot in snapshots
    ]
    return {"items": items, "total": len(items)}


@router.get("/policy-snapshots/{snapshot_id}")
async def get_policy_snapshot(
    snapshot_id: str,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    snapshot = await _find_policy_snapshot(db, snapshot_id, current)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Policy snapshot not found.")
    return {
        "id": snapshot.snapshot_id,
        "snapshot_id": snapshot.snapshot_id,
        "version": snapshot.version_tag,
        "created_by": snapshot.created_by,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "rules": snapshot.rules_json or {},
        "rules_json": snapshot.rules_json or {},
    }


@router.get("/batches")
async def list_batches(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    status_filter: str | None = Query(None, alias="status"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(BatchRecord).order_by(desc(BatchRecord.created_at))
    if not _is_platform_admin(current):
        stmt = stmt.where(BatchRecord.tenant_id == _tenant_id(current))
    batches = (await db.execute(stmt)).scalars().all()
    batch_ids = [batch.batch_id for batch in batches]
    latest_runs = await _latest_runs_by_batch(db, batch_ids)
    source_counts = await _source_counts_by_batch(db, batch_ids)
    total_docs, done_docs = await _doc_counts_by_batch(db, batch_ids)
    review_counts = await _review_counts_by_batch(db, batch_ids)
    policies = await _policies_by_snapshot_id(db, [batch.policy_snapshot_id or "" for batch in batches])
    users = await _users_by_id(db, [batch.import_user_id or 0 for batch in batches])

    items = [
        _serialize_batch(
            batch,
            latest_run=latest_runs.get(batch.batch_id),
            source_count=source_counts.get(batch.batch_id, 0),
            total_docs=total_docs.get(batch.batch_id, 0),
            done_docs=done_docs.get(batch.batch_id, 0),
            review_counts=review_counts.get(batch.batch_id, {}),
            created_by=(users.get(batch.import_user_id or 0).display_name or users.get(batch.import_user_id or 0).username) if users.get(batch.import_user_id or 0) else "",
            policy_version=policies.get(batch.policy_snapshot_id or "").version_tag if policies.get(batch.policy_snapshot_id or "") else "",
        )
        for batch in batches
    ]

    normalized_status = str(status_filter or "").strip().lower()
    if normalized_status:
        items = [item for item in items if item["status"] == normalized_status]

    if date_from:
        items = [item for item in items if str(item.get("created_at") or "")[:10] >= date_from]
    if date_to:
        items = [item for item in items if str(item.get("created_at") or "")[:10] <= date_to]

    return _paginate(items, page, page_size)


@router.post("/batches", status_code=status.HTTP_201_CREATED)
async def create_batch(
    body: BatchCreateRequest,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    batch_id = _make_batch_id(body.name)
    while (await db.execute(select(BatchRecord).where(BatchRecord.batch_id == batch_id).limit(1))).scalar_one_or_none():
        batch_id = _make_batch_id(body.name)

    batch = BatchRecord(
        batch_id=batch_id,
        tenant_id=_tenant_id(current),
        source_type="api",
        import_user_id=current.get("user_id"),
        page_count=0,
        status="pending",
        draft_status="pending",
        final_status="pending",
        review_status="none",
        policy_snapshot_id=body.policy_snapshot_id,
    )
    db.add(batch)
    await db.commit()
    await db.refresh(batch)
    return {
        "id": batch.id,
        "batch_id": batch.batch_id,
        "status": "draft",
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "policy_snapshot_id": batch.policy_snapshot_id,
    }


@router.get("/batches/{batch_id}")
async def get_batch(
    batch_id: str,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    batch = await _find_batch(db, batch_id, current)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")

    latest_runs = await _latest_runs_by_batch(db, [batch_id])
    source_counts = await _source_counts_by_batch(db, [batch_id])
    total_docs, done_docs = await _doc_counts_by_batch(db, [batch_id])
    review_counts = await _review_counts_by_batch(db, [batch_id])
    policies = await _policies_by_snapshot_id(db, [batch.policy_snapshot_id or ""])
    users = await _users_by_id(db, [batch.import_user_id or 0])
    return _serialize_batch(
        batch,
        latest_run=latest_runs.get(batch_id),
        source_count=source_counts.get(batch_id, 0),
        total_docs=total_docs.get(batch_id, 0),
        done_docs=done_docs.get(batch_id, 0),
        review_counts=review_counts.get(batch_id, {}),
        created_by=(users.get(batch.import_user_id or 0).display_name or users.get(batch.import_user_id or 0).username) if users.get(batch.import_user_id or 0) else "",
        policy_version=policies.get(batch.policy_snapshot_id or "").version_tag if policies.get(batch.policy_snapshot_id or "") else "",
    )


@router.get("/batches/{batch_id}/status")
async def get_batch_status(
    batch_id: str,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    batch = await get_batch(batch_id, current=current, db=db)
    return {
        "batch_id": batch.get("batch_id"),
        "status": batch.get("status"),
        "current_stage": batch.get("current_stage"),
        "run_status": batch.get("run_status"),
    }


@router.post("/batches/{batch_id}/start")
async def start_batch_workflow(
    batch_id: str,
    body: BatchStartRequest | None = None,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    batch = await _find_batch(db, batch_id, current)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")

    existing_run = (
        await db.execute(
            select(WorkflowRun)
            .where(WorkflowRun.batch_id == batch_id, WorkflowRun.run_status.in_(["running", "done"]))
            .order_by(desc(WorkflowRun.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing_run:
        return {
            "success": True,
            "run_id": existing_run.run_id,
            "batch_id": batch_id,
            "status": "processing" if existing_run.run_status == "running" else "done",
            "message": "workflow_already_exists",
        }

    policy_snapshot_id = body.policy_snapshot_id if body else None
    if policy_snapshot_id:
        batch.policy_snapshot_id = policy_snapshot_id
    batch.status = "processing"
    batch.draft_status = "running"

    run_id = f"wf_{batch_id}_{uuid4().hex[:8]}"
    workflow = WorkflowRun(
        run_id=run_id,
        batch_id=batch_id,
        tenant_id=batch.tenant_id,
        run_type="normal",
        run_status="running",
        current_stage="ingest_batch",
        policy_snapshot_id=batch.policy_snapshot_id,
        state_json={
            "request_id": str(uuid4()),
            "submitted_by": current.get("username") or "",
            "extra": {},
        },
    )
    db.add(workflow)
    await db.commit()

    queued = True
    try:
        await enqueue_workflow_start(run_id=run_id, batch_id=batch_id, tenant_id=batch.tenant_id)
    except Exception:
        queued = False

    return {
        "success": True,
        "run_id": run_id,
        "batch_id": batch_id,
        "status": "processing",
        "queued": queued,
    }


@router.get("/tasks")
async def list_review_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    task_type: str | None = Query(None, alias="type"),
    status_filter: str | None = Query(None, alias="status"),
    keyword: str | None = Query(None, alias="q"),
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    normalized_type = _normalize_review_type(task_type)
    stmt = select(ReviewTask).order_by(desc(ReviewTask.created_at))
    if not _is_platform_admin(current):
        stmt = stmt.where(ReviewTask.tenant_id == _tenant_id(current))
    tasks = (await db.execute(stmt)).scalars().all()

    allowed_statuses = _normalize_review_filter(status_filter)
    items = []
    users = await _users_by_id(db, [task.assignee_user_id or 0 for task in tasks])
    for task in tasks:
        if normalized_type and task.task_type != normalized_type:
            continue
        if allowed_statuses and str(task.status or "").lower() not in allowed_statuses:
            continue
        if keyword and not _matches_keyword([task.review_task_id, task.batch_id, task.reason, *(task.affected_doc_ids_json or [])], keyword):
            continue
        items.append(_review_task_item(task, users))

    return _paginate(items, page, page_size)


@router.get("/tasks/my-assigned")
async def list_my_assigned_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    status_filter: str | None = Query(None, alias="status"),
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    user_id = current.get("user_id")
    if not user_id:
        return {"items": [], "total": 0}
    stmt = select(ReviewTask).where(ReviewTask.assignee_user_id == user_id).order_by(desc(ReviewTask.created_at))
    if not _is_platform_admin(current):
        stmt = stmt.where(ReviewTask.tenant_id == _tenant_id(current))
    tasks = (await db.execute(stmt)).scalars().all()
    allowed_statuses = _normalize_review_filter(status_filter)
    users = await _users_by_id(db, [user_id])
    items = [
        _review_task_item(task, users)
        for task in tasks
        if not allowed_statuses or str(task.status or "").lower() in allowed_statuses
    ]
    return _paginate(items, page, page_size)


@router.post("/tasks/assign")
async def assign_review_task(
    body: TaskAssignRequest,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    task_ids = list(body.task_ids or [])
    if body.task_id:
        task_ids.append(body.task_id)
    if not task_ids:
        raise HTTPException(status_code=400, detail="No task selected.")

    assignee_user: AppUser | None = None
    if body.assignee_id:
        assignee_user = (
            await db.execute(select(AppUser).where(AppUser.id == body.assignee_id).limit(1))
        ).scalar_one_or_none()
    elif body.assignee_username:
        assignee_user = (
            await db.execute(select(AppUser).where(AppUser.username == body.assignee_username).limit(1))
        ).scalar_one_or_none()
    if not assignee_user:
        raise HTTPException(status_code=404, detail="Assignee not found.")

    affected = 0
    for raw_task_id in task_ids:
        task = await _find_review_task(db, str(raw_task_id), current)
        if not task:
            continue
        task.assignee_user_id = assignee_user.id
        if task.status == "pending":
            task.status = "pending"
        affected += 1

    await db.commit()
    return {
        "affected": affected,
        "message": f"已分配 {affected} 个任务",
    }


@router.get("/tasks/{task_id}")
async def get_review_task(
    task_id: str,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    task = await _find_review_task(db, task_id, current)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found.")
    docs = await _serialize_doc_versions(db, task.batch_id, list(task.affected_doc_ids_json or []))
    return {
        **_review_task_item(task, await _users_by_id(db, [task.assignee_user_id or 0])),
        "docs": docs,
        "doc_units": docs,
        "batch_id": task.batch_id,
        "reason": task.reason,
        "evidence": task.evidence_json or {},
        "confidence": task.confidence,
        "review_result": task.result_json or {},
    }


@router.get("/tasks/{task_id}/workflow-events")
async def get_review_task_workflow_events(
    task_id: str,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    task = await _find_review_task(db, task_id, current)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found.")
    logs = (
        await db.execute(
            select(ReviewActionLog)
            .where(ReviewActionLog.review_task_id == task.review_task_id)
            .order_by(desc(ReviewActionLog.occurred_at))
        )
    ).scalars().all()
    users = await _users_by_id(db, [log.operator_user_id or 0 for log in logs])
    items = [
        {
            "id": log.id,
            "action": log.action,
            "operator": (users.get(log.operator_user_id or 0).display_name or users.get(log.operator_user_id or 0).username)
            if users.get(log.operator_user_id or 0)
            else None,
            "note": log.note,
            "before": log.before_snapshot_json or {},
            "after": log.after_snapshot_json or {},
            "occurred_at": log.occurred_at.isoformat() if log.occurred_at else None,
        }
        for log in logs
    ]
    return {"items": items, "total": len(items)}


@router.post("/tasks/{task_id}/submit")
async def submit_review(
    task_id: str,
    body: ReviewSubmitRequest,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    task = await _find_review_task(db, task_id, current)
    if not task:
        raise HTTPException(status_code=404, detail="Review task not found.")

    review_result = _build_review_result(task, body)
    await submit_review_result(
        db,
        review_task_id=task.review_task_id,
        user_id=int(current.get("user_id") or 0),
        result=review_result,
        note=body.reason or (body.metadata or {}).get("notes", ""),
    )

    rework: ReworkTask | None = None
    if str(body.decision or "approve").strip().lower() == "reject":
        rework_payload = dict(body.rework or {})
        rework = await _create_rework_task(
            db,
            current=current,
            batch_id=task.batch_id,
            record_id=str(rework_payload.get("record_id") or body.doc_id or "") or None,
            record_version=rework_payload.get("record_version") or 1,
            issue_type=rework_payload.get("issue_type") or task.task_type,
            description=rework_payload.get("description") or body.reason or task.reason or "人工驳回",
            priority=rework_payload.get("priority") or "normal",
            rework_level=rework_payload.get("rework_level") or "partial",
            affected_scope={
                "doc_ids": list(task.affected_doc_ids_json or []),
                "page_ids": list(task.affected_page_ids_json or []),
                "source_review_task_id": task.review_task_id,
                "source_review_type": task.task_type,
            },
        )
        return {
            "id": task.review_task_id,
            "submitted": True,
            "rework_id": rework.rework_task_id,
        }

    resumed = False
    if task.run_id:
        try:
            await resume_archive_workflow(
                task_id=task.run_id,
                batch_id=task.batch_id,
                reason="review_submitted",
                review_result=review_result,
            )
            resumed = True
        except Exception:
            resumed = False
    return {
        "id": task.review_task_id,
        "submitted": True,
        "resumed": resumed,
    }


@router.get("/batches/{batch_id}/docs")
async def list_doc_units(
    batch_id: str,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    batch = await _find_batch(db, batch_id, current)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")
    items = await _serialize_doc_versions(db, batch_id)
    return {"items": items, "total": len(items)}


@router.get("/batches/{batch_id}/docs/{doc_id}")
async def get_doc_unit(
    batch_id: str,
    doc_id: str,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    batch = await _find_batch(db, batch_id, current)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")
    items = await _serialize_doc_versions(db, batch_id, [doc_id])
    if not items:
        raise HTTPException(status_code=404, detail="Document unit not found.")
    return items[0]


@router.patch("/batches/{batch_id}/docs/{doc_id}/metadata")
async def update_doc_metadata(
    batch_id: str,
    doc_id: str,
    body: DocMetadataUpdateRequest,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    batch = await _find_batch(db, batch_id, current)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")

    version = (
        await db.execute(
            select(DocVersion).where(DocVersion.batch_id == batch_id, DocVersion.doc_id == doc_id, DocVersion.is_current.is_(True)).limit(1)
        )
    ).scalar_one_or_none()
    if not version:
        raise HTTPException(status_code=404, detail="Document version not found.")

    metadata = dict(version.metadata_json or {})
    payload = body.model_dump(exclude_none=True)
    if "responsible" in payload and "responsible_party" not in payload:
        payload["responsible_party"] = payload["responsible"]
    metadata.update(payload)
    version.metadata_json = metadata
    await db.commit()
    return {
        "id": doc_id,
        "metadata": metadata,
        "fields": metadata,
    }


@router.get("/archive-records")
async def list_archive_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    keyword: str | None = Query(None, alias="q"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    batch_id: str | None = Query(None),
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    records_stmt = select(ArchiveRecord).order_by(desc(ArchiveRecord.created_at))
    if not _is_platform_admin(current):
        records_stmt = records_stmt.where(ArchiveRecord.tenant_id == _tenant_id(current))
    records = (await db.execute(records_stmt)).scalars().all()

    items: list[dict[str, Any]] = []
    for record in records:
        output = _archive_record_to_output(record)
        if batch_id and str(record.batch_id or "") != batch_id:
            continue
        if keyword and not _matches_keyword([record.title, record.doc_no, record.responsible, record.archive_no, record.storage_path], keyword):
            continue
        created_key = str(output.get("created_at") or "")[:10]
        if date_from and created_key and created_key < date_from:
            continue
        if date_to and created_key and created_key > date_to:
            continue
        items.append(output)

    return _paginate(items, page, page_size)


@router.get("/archive-records/{record_id}")
async def get_archive_record(
    record_id: int,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    record = (await db.execute(select(ArchiveRecord).where(ArchiveRecord.id == record_id).limit(1))).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Archive record not found.")
    if not _is_platform_admin(current) and record.tenant_id != _tenant_id(current):
        raise HTTPException(status_code=404, detail="Archive record not found.")

    reworks = (await db.execute(select(ReworkTask).where(ReworkTask.batch_id == (record.batch_id or "")).order_by(desc(ReworkTask.created_at)))).scalars().all()
    last_rework_status = None
    for rework in reworks:
        scope = dict(rework.affected_scope_json or {})
        if str(scope.get("record_id") or "") == str(record.id):
            last_rework_status = _normalize_rework_status(rework.status)
            break
    return _archive_record_to_output(record, last_rework_status=last_rework_status)


@router.get("/rework-tasks")
async def list_rework_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    status_filter: str | None = Query(None, alias="status"),
    keyword: str | None = Query(None, alias="q"),
    mine: bool | None = Query(None),
    reporter: str | None = Query(None),
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    stmt = select(ReworkTask).order_by(desc(ReworkTask.created_at))
    if not _is_platform_admin(current):
        stmt = stmt.where(ReworkTask.tenant_id == _tenant_id(current))
    tasks = (await db.execute(stmt)).scalars().all()
    users = await _users_by_id(db, [task.reported_by or 0 for task in tasks])
    items: list[dict[str, Any]] = []
    normalized_filter = str(status_filter or "").strip().lower()
    for task in tasks:
        reporter_user = users.get(task.reported_by or 0)
        if mine or (reporter and reporter_user and reporter_user.username == reporter):
            if task.reported_by != current.get("user_id"):
                continue
        reporter_name = (reporter_user.display_name or reporter_user.username) if reporter_user else ""
        output = {
            "id": task.rework_task_id,
            "rework_task_id": task.rework_task_id,
            "record_id": (task.affected_scope_json or {}).get("record_id"),
            "batch_id": task.batch_id,
            "issue_type": task.issue_type,
            "priority": (task.affected_scope_json or {}).get("priority", "normal"),
            "status": _normalize_rework_status(task.status),
            "created_at": task.created_at.isoformat() if task.created_at else None,
            "description": task.description,
            "reported_by": reporter_name,
            "affected_scope": task.affected_scope_json or {},
        }
        if normalized_filter and output["status"] != normalized_filter:
            continue
        if keyword and not _matches_keyword([output["id"], output["record_id"], output["batch_id"], output["description"]], keyword):
            continue
        items.append(output)
    return _paginate(items, page, page_size)


@router.post("/rework-tasks", status_code=status.HTTP_201_CREATED)
async def create_rework_task(
    body: ReworkCreateRequest,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    batch_id = str(body.batch_id or "").strip()
    record_id = str(body.record_id or "").strip() or None
    if record_id and not batch_id:
        record = None
        if record_id.isdigit():
            record = (await db.execute(select(ArchiveRecord).where(ArchiveRecord.id == int(record_id)).limit(1))).scalar_one_or_none()
        if record:
            batch_id = str(record.batch_id or "").strip()
    if not batch_id:
        batch_id = f"record_{record_id or uuid4().hex[:8]}"

    affected_scope = body.affected_scope if isinstance(body.affected_scope, dict) else {"label": body.affected_scope or ""}
    rework = await _create_rework_task(
        db,
        current=current,
        batch_id=batch_id,
        record_id=record_id,
        record_version=body.record_version,
        issue_type=body.issue_type,
        description=body.description,
        priority=body.priority,
        rework_level=body.rework_level,
        affected_scope=affected_scope,
    )
    return {
        "id": rework.rework_task_id,
        "status": _normalize_rework_status(rework.status),
        "batch_id": rework.batch_id,
    }


@router.get("/rework-tasks/{task_id}")
async def get_rework_task(
    task_id: str,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    task = (
        await db.execute(select(ReworkTask).where(ReworkTask.rework_task_id == task_id).limit(1))
    ).scalar_one_or_none()
    if not task or (not _is_platform_admin(current) and task.tenant_id != _tenant_id(current)):
        raise HTTPException(status_code=404, detail="Rework task not found.")
    return {
        "id": task.rework_task_id,
        "rework_task_id": task.rework_task_id,
        "record_id": (task.affected_scope_json or {}).get("record_id"),
        "batch_id": task.batch_id,
        "issue_type": task.issue_type,
        "priority": (task.affected_scope_json or {}).get("priority", "normal"),
        "status": _normalize_rework_status(task.status),
        "description": task.description,
        "affected_scope": task.affected_scope_json or {},
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


# ── Audit logs ──────────────────────────────────────────────────────────────


@router.get("/audit-logs")
async def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    action: str | None = Query(None),
    batch_id: str | None = Query(None),
    operator_user_id: int | None = Query(None),
    q: str | None = Query(None),
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """审阅记录列表：返回当前租户（或全平台）的审核动作日志。"""
    stmt = select(ReviewActionLog).order_by(desc(ReviewActionLog.occurred_at))

    if not _is_platform_admin(current):
        tenant_id = _tenant_id(current)
        tenant_batch_ids_stmt = select(BatchRecord.batch_id).where(BatchRecord.tenant_id == tenant_id)
        tenant_batch_ids = (await db.execute(tenant_batch_ids_stmt)).scalars().all()
        if tenant_batch_ids:
            stmt = stmt.where(ReviewActionLog.batch_id.in_(tenant_batch_ids))
        else:
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

    if action:
        stmt = stmt.where(ReviewActionLog.action == action)
    if batch_id:
        stmt = stmt.where(ReviewActionLog.batch_id == batch_id)
    if operator_user_id:
        stmt = stmt.where(ReviewActionLog.operator_user_id == operator_user_id)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            ReviewActionLog.note.ilike(pattern)
            | ReviewActionLog.review_task_id.ilike(pattern)
            | ReviewActionLog.batch_id.ilike(pattern)
        )

    all_logs = (await db.execute(stmt)).scalars().all()
    total = len(all_logs)
    start = (page - 1) * page_size
    page_logs = all_logs[start : start + page_size]

    user_ids = {log.operator_user_id for log in page_logs if log.operator_user_id}
    user_map: dict[int, str] = {}
    if user_ids:
        users = (await db.execute(select(AppUser).where(AppUser.id.in_(user_ids)))).scalars().all()
        user_map = {u.id: u.display_name or u.username for u in users}

    items = []
    for log in page_logs:
        items.append({
            "id": log.id,
            "review_task_id": log.review_task_id,
            "batch_id": log.batch_id,
            "action": log.action,
            "operator_user_id": log.operator_user_id,
            "operator_name": user_map.get(log.operator_user_id) or "" if log.operator_user_id else "",
            "note": log.note,
            "before_snapshot": log.before_snapshot_json,
            "after_snapshot": log.after_snapshot_json,
            "occurred_at": log.occurred_at.isoformat() if log.occurred_at else None,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


# ── Policy snapshot CRUD ─────────────────────────────────────────────────────


@router.post("/policy-snapshots", status_code=status.HTTP_201_CREATED)
async def create_policy_snapshot(
    body: PolicySnapshotCreateRequest,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not _is_platform_admin(current):
        raise HTTPException(status_code=403, detail="Only admins can create policy snapshots.")
    tenant_id = _tenant_id(current)
    snapshot_id = f"ps_{tenant_id}_{uuid4().hex[:8]}"
    version_tag = (body.version_tag or "").strip() or f"v{_utc_now().strftime('%Y%m%d%H%M%S')}"
    snapshot = PolicySnapshot(
        snapshot_id=snapshot_id,
        tenant_id=tenant_id,
        version_tag=version_tag,
        rules_json=body.rules_json or {},
        created_by=current.get("username") or str(current.get("user_id", "")),
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return {
        "id": snapshot.snapshot_id,
        "snapshot_id": snapshot.snapshot_id,
        "version": snapshot.version_tag,
        "created_by": snapshot.created_by,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "rules_json": snapshot.rules_json or {},
    }


@router.put("/policy-snapshots/{snapshot_id}")
async def update_policy_snapshot(
    snapshot_id: str,
    body: PolicySnapshotUpdateRequest,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not _is_platform_admin(current):
        raise HTTPException(status_code=403, detail="Only admins can update policy snapshots.")
    snapshot = await _find_policy_snapshot(db, snapshot_id, current)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Policy snapshot not found.")
    if body.version_tag is not None:
        snapshot.version_tag = body.version_tag.strip() or snapshot.version_tag
    if body.rules_json is not None:
        snapshot.rules_json = body.rules_json
    await db.commit()
    await db.refresh(snapshot)
    return {
        "id": snapshot.snapshot_id,
        "snapshot_id": snapshot.snapshot_id,
        "version": snapshot.version_tag,
        "created_by": snapshot.created_by,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "rules_json": snapshot.rules_json or {},
    }


# ── Batch file management ────────────────────────────────────────────────────


@router.get("/batches/{batch_id}/files")
async def list_batch_files(
    batch_id: str,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    batch = await _find_batch(db, batch_id, current)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")
    files = (
        await db.execute(
            select(SourceFile)
            .where(SourceFile.batch_id == batch_id)
            .order_by(SourceFile.created_at)
        )
    ).scalars().all()
    items = [
        {
            "id": f.file_id,
            "file_id": f.file_id,
            "name": f.original_filename,
            "file_name": f.original_filename,
            "original_filename": f.original_filename,
            "size": f.file_size_bytes,
            "file_size": f.file_size_bytes,
            "file_size_bytes": f.file_size_bytes,
            "mime_type": f.mime_type,
            "content_type": f.mime_type,
            "page_count": f.page_count,
            "process_status": f.process_status,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in files
    ]
    return {"items": items, "total": len(items)}


@router.post("/batches/{batch_id}/files", status_code=status.HTTP_201_CREATED)
async def upload_batch_files(
    batch_id: str,
    files: list[UploadFile] = File(...),
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    batch = await _find_batch(db, batch_id, current)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")
    if batch.status not in {"pending", "draft", "created"}:
        raise HTTPException(status_code=400, detail="Batch is not in an uploadable state.")

    from app.config import ALLOWED_EXTENSIONS, UPLOAD_DIR

    uploaded = []
    for upload_file in files:
        filename = upload_file.filename or "unknown"
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type '{ext}' is not allowed. Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )
        content = await upload_file.read()
        file_hash = hashlib.sha256(content).hexdigest()
        file_id = f"sf_{batch_id}_{uuid4().hex[:8]}"
        save_dir = UPLOAD_DIR / "batches" / batch_id
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / f"{file_id}{ext}"
        save_path.write_bytes(content)

        sf = SourceFile(
            file_id=file_id,
            batch_id=batch_id,
            tenant_id=_tenant_id(current),
            original_filename=filename,
            storage_uri=str(save_path),
            file_size_bytes=len(content),
            mime_type=upload_file.content_type or "application/octet-stream",
            file_hash=file_hash,
            uploaded_by=current.get("user_id"),
            process_status="pending",
        )
        db.add(sf)
        uploaded.append({
            "file_id": file_id,
            "original_filename": filename,
            "file_size_bytes": len(content),
        })
    await db.commit()
    return {"uploaded": uploaded, "count": len(uploaded)}


# ── Rework task accept / reject ──────────────────────────────────────────────


@router.post("/rework-tasks/{task_id}/accept")
async def accept_rework_task(
    task_id: str,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not _is_platform_admin(current):
        raise HTTPException(status_code=403, detail="Only admins can accept rework tasks.")
    task = (
        await db.execute(select(ReworkTask).where(ReworkTask.rework_task_id == task_id).limit(1))
    ).scalar_one_or_none()
    if not task or (not _is_platform_admin(current) and task.tenant_id != _tenant_id(current)):
        raise HTTPException(status_code=404, detail="Rework task not found.")
    if task.status != "pending":
        raise HTTPException(status_code=400, detail=f"Task is '{task.status}', expected 'pending'.")
    task.status = "accepted"
    task.accepted_by = current.get("user_id")
    await db.commit()
    await db.refresh(task)
    return {
        "id": task.rework_task_id,
        "status": _normalize_rework_status(task.status),
    }


@router.post("/rework-tasks/{task_id}/reject")
async def reject_rework_task(
    task_id: str,
    body: dict[str, Any] | None = None,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not _is_platform_admin(current):
        raise HTTPException(status_code=403, detail="Only admins can reject rework tasks.")
    task = (
        await db.execute(select(ReworkTask).where(ReworkTask.rework_task_id == task_id).limit(1))
    ).scalar_one_or_none()
    if not task or (not _is_platform_admin(current) and task.tenant_id != _tenant_id(current)):
        raise HTTPException(status_code=404, detail="Rework task not found.")
    if task.status != "pending":
        raise HTTPException(status_code=400, detail=f"Task is '{task.status}', expected 'pending'.")
    reason = str((body or {}).get("reason", "")).strip()
    task.status = "rejected"
    task.accepted_by = current.get("user_id")
    scope = dict(task.affected_scope_json or {})
    scope["reject_reason"] = reason
    task.affected_scope_json = scope
    await db.commit()
    await db.refresh(task)
    return {
        "id": task.rework_task_id,
        "status": _normalize_rework_status(task.status),
    }


# ── Archive PDF download ─────────────────────────────────────────────────────


@router.get("/archive-records/{record_id}/pdf")
async def download_archive_pdf(
    record_id: str,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    record: ArchiveRecord | None = None
    if record_id.isdigit():
        record = (await db.execute(select(ArchiveRecord).where(ArchiveRecord.id == int(record_id)).limit(1))).scalar_one_or_none()
    if not record:
        record = (
            await db.execute(select(ArchiveRecord).where(ArchiveRecord.archive_no == record_id).limit(1))
        ).scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Archive record not found.")

    batch_id = str(record.batch_id or "")
    # Look for a final searchable PDF artifact
    artifact = (
        await db.execute(
            select(ArtifactFile)
            .where(
                ArtifactFile.batch_id == batch_id,
                ArtifactFile.artifact_type.in_(["final_searchable_pdf", "draft_searchable_pdf", "export_zip"]),
            )
            .order_by(desc(ArtifactFile.created_at))
            .limit(1)
        )
    ).scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="No PDF artifact found for this record.")

    file_path = Path(artifact.storage_uri)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found on disk.")

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=f"archive_{record_id}.pdf",
    )


@router.post("/batches/{batch_id}/export/final-pdf")
async def export_batch_final_pdf(
    batch_id: str,
    current: dict[str, Any] = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    batch = await _find_batch(db, batch_id, current)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found.")
    # Mark the batch export status as pending; the worker will pick it up
    batch.export_status = "pending"
    await db.commit()
    return {
        "batch_id": batch_id,
        "export_status": "pending",
        "message": "Final PDF export has been queued.",
    }