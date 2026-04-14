"""
Database Models (Entities)
使用 SQLAlchemy 2.0 风格 (Mapped/mapped_column) 定义的底层实体模型。

架构说明：
这些是贫血模型（Anemic Domain Model），仅负责与关系型数据库（PostgreSQL/MySQL 等）建立映射关系。
业务逻辑（Business Rules）不应该写在这些模型中，而应放在 `app.domains` 或 `app.services` 中。
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class Tenant(Base):
    """租户（机构/组织）— 多租户隔离的顶层单元。"""
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)          # slug 形式，如 "default" / "org_abc"
    name: Mapped[str] = mapped_column(String(120), nullable=False)          # 显示名称，如 "默认机构"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active / disabled
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending/active/rejected
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # role: admin / tenant_admin / member  (operator/searcher 已降格为岗位能力标签)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="member")
    # capabilities: 租户成员的岗位能力标签，逗号分隔，如 'operator'/'searcher'/'operator,searcher'
    capabilities: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # 所属租户（多租户隔离键）
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class UserQuota(Base):
    """Per-operator file processing quota."""
    __tablename__ = "user_quotas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    quota_per_import: Mapped[int] = mapped_column(Integer, nullable=False, default=200)
    quota_total: Mapped[int] = mapped_column(Integer, nullable=False, default=2000)
    quota_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reset_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class BatchAssignment(Base):
    """Admin assigns a batch (or subset of files) to an operator."""
    __tablename__ = "batch_assignments"
    __table_args__ = (
        Index("ix_batch_assignments_operator_id", "operator_id"),
        Index("ix_batch_assignments_batch_id", "batch_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    admin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    operator_id: Mapped[int] = mapped_column(Integer, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class OperationLog(Base):
    """Immutable audit trail — one row per user action."""
    __tablename__ = "operation_logs"
    __table_args__ = (
        Index("ix_operation_logs_user_id", "user_id"),
        Index("ix_operation_logs_created_at", "created_at"),
        Index("ix_operation_logs_action_type", "action_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OCRTask(Base):
    __tablename__ = "ocr_tasks"
    __table_args__ = (
        Index("ix_ocr_tasks_status", "status"),
        Index("ix_ocr_tasks_file_path", "file_path"),
        Index("ix_ocr_tasks_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    storage_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_object_key: Mapped[str | None] = mapped_column(String(700), nullable=True)
    file_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mode: Mapped[str] = mapped_column(String(20), default="layout")  # vl/layout/ocr
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/processing/done/failed
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # OCR 结果 JSON
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    # 档案工作流字段 / archive workflow fields
    batch_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    assignee_username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    submitter_username: Mapped[str | None] = mapped_column(String(120), nullable=True)
    submission_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    progress_percent: Mapped[float | None] = mapped_column(Float, nullable=True, default=0.0)
    processed_pages: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    total_pages: Mapped[int | None] = mapped_column(Integer, nullable=True, default=0)
    review_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ArchiveRecord(Base):
    __tablename__ = "archive_records"
    __table_args__ = (
        Index("ix_archive_records_batch_id", "batch_id"),
        Index("ix_archive_records_task_id", "task_id"),
        Index("ix_archive_records_batch_folder", "batch_folder"),
        Index("ix_archive_records_tenant_id", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="default")
    task_id: Mapped[int | None] = mapped_column(Integer, nullable=True)           # 关联 ocr_tasks.id，外部导入时为 NULL
    batch_id: Mapped[str | None] = mapped_column(String(100), nullable=True)      # 批次标识，前端生成
    batch_folder: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 源文件夹路径
    archive_no: Mapped[str | None] = mapped_column(String(200), nullable=True)    # 档号
    doc_no: Mapped[str | None] = mapped_column(String(200), nullable=True)        # 文号
    responsible: Mapped[str | None] = mapped_column(String(500), nullable=True)   # 责任者
    title: Mapped[str | None] = mapped_column(String(1000), nullable=True)        # 题名
    date: Mapped[str | None] = mapped_column(String(50), nullable=True)           # 日期
    pages: Mapped[str | None] = mapped_column(String(20), nullable=True)          # 页数
    classification: Mapped[str | None] = mapped_column(String(50), nullable=True) # 密级
    remarks: Mapped[str | None] = mapped_column(String(1000), nullable=True)      # 备注
    storage_path: Mapped[str | None] = mapped_column(String(1000), nullable=True) # 存放路径（需求11）
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BatchTruthTaskMap(Base):
    __tablename__ = "batch_truth_task_map"
    __table_args__ = (UniqueConstraint("batch_id", "task_id", name="uq_batch_truth_task_map_batch_task"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_key: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class BatchTruthDocumentField(Base):
    __tablename__ = "batch_truth_document_fields"
    __table_args__ = (UniqueConstraint("batch_id", "doc_key", name="uq_batch_truth_document_fields_batch_doc"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    doc_key: Mapped[str] = mapped_column(String(120), nullable=False)
    archive_no: Mapped[str | None] = mapped_column(String(200), nullable=True)
    doc_no: Mapped[str | None] = mapped_column(String(200), nullable=True)
    responsible: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    date: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pages: Mapped[str | None] = mapped_column(String(20), nullable=True)
    classification: Mapped[str | None] = mapped_column(String(50), nullable=True)
    remarks: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class BatchQARecord(Base):
    __tablename__ = "batch_qa_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[list | dict] = mapped_column(JSONB, nullable=False, default=list)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="minimax")
    model: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    raw_usage: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    support_level: Mapped[str] = mapped_column(String(20), nullable=False, default="insufficient")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    citations_json: Mapped[list | dict] = mapped_column(JSONB, nullable=False, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class BatchQAFeedback(Base):
    __tablename__ = "batch_qa_feedback"
    __table_args__ = (
        UniqueConstraint("batch_id", "qa_record_id", name="uq_batch_qa_feedback_batch_qa"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    qa_record_id: Mapped[int] = mapped_column(Integer, nullable=False)
    rating: Mapped[str] = mapped_column(String(20), nullable=False)  # helpful / not_helpful
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_evidence_json: Mapped[list | dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class BatchPageSequence(Base):
    __tablename__ = "batch_page_sequences"
    __table_args__ = (
        UniqueConstraint("batch_id", "prefix", name="uq_batch_page_sequences_batch_prefix"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    prefix: Mapped[str] = mapped_column(String(255), nullable=False)
    task_ids_json: Mapped[list | dict] = mapped_column(JSONB, nullable=False, default=list)
    filenames_json: Mapped[list | dict] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class BatchBoundaryDecision(Base):
    __tablename__ = "batch_boundary_decisions"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "left_task_id",
            "right_task_id",
            name="uq_batch_boundary_decisions_batch_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    left_task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    right_task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    prefix: Mapped[str] = mapped_column(String(255), nullable=False)
    left_page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    right_page_no: Mapped[int] = mapped_column(Integer, nullable=False)
    same_document_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    should_merge: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_ambiguous: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    strong_split: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    signals_json: Mapped[list | dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class BatchDocumentGroup(Base):
    __tablename__ = "batch_document_groups"
    __table_args__ = (
        UniqueConstraint("batch_id", "group_key", name="uq_batch_document_groups_batch_group"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    group_key: Mapped[str] = mapped_column(String(120), nullable=False)
    prefix: Mapped[str] = mapped_column(String(255), nullable=False)
    task_ids_json: Mapped[list | dict] = mapped_column(JSONB, nullable=False, default=list)
    filenames_json: Mapped[list | dict] = mapped_column(JSONB, nullable=False, default=list)
    start_page: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reasons_json: Mapped[list | dict] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class BatchBoundaryTruthTaskMap(Base):
    __tablename__ = "batch_boundary_truth_task_map"
    __table_args__ = (UniqueConstraint("batch_id", "task_id", name="uq_batch_boundary_truth_task_map_batch_task"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    doc_key: Mapped[str] = mapped_column(String(120), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="human")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class BatchBoundaryFeedback(Base):
    __tablename__ = "batch_boundary_feedback"
    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "left_task_id",
            "right_task_id",
            name="uq_batch_boundary_feedback_batch_pair",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    left_task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    right_task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(20), nullable=False)  # same / different
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="human")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# 档案智能整理系统 — 核心实体模型（Phase 3 架构）
# ---------------------------------------------------------------------------


class PolicySnapshot(Base):
    """规则快照：工作流启动时生成，后续整卷按同一版规则执行。"""

    __tablename__ = "policy_snapshots"
    __table_args__ = (
        Index("ix_policy_snapshots_tenant_id", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    version_tag: Mapped[str] = mapped_column(String(100), nullable=False, default="v1")
    # 规则配置快照（JSON），包含分件规则、排序规则、编号规则、保存期限规则、著录字段规则、审核阈值等
    rules_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BatchRecord(Base):
    """批次/卷宗对象：系统业务处理的主要输入单位。"""

    __tablename__ = "batch_records"
    __table_args__ = (
        Index("ix_batch_records_tenant_id_status", "tenant_id", "status"),
        Index("ix_batch_records_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="upload")  # upload / scan / api
    import_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 整体状态
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")  # pending/processing/done/failed
    # Draft 轨状态
    draft_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")  # pending/running/done/blocked/failed
    # Final 轨状态
    final_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")  # pending/running/blocked/done/failed
    # 审核状态
    review_status: Mapped[str] = mapped_column(String(30), nullable=False, default="none")  # none/pending/in_review/resolved
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    policy_snapshot_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 导出状态
    export_status: Mapped[str] = mapped_column(String(30), nullable=False, default="none")  # none/pending/generating/done/failed
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class PageRecord(Base):
    """页面级对象：整卷按页并行处理的基本单元。"""

    __tablename__ = "page_records"
    __table_args__ = (
        Index("ix_page_records_batch_id_page_index", "batch_id", "page_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    page_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    page_index: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-based
    # 存储路径
    image_uri: Mapped[str | None] = mapped_column(String(700), nullable=True)   # 原图 MinIO 路径
    preview_uri: Mapped[str | None] = mapped_column(String(700), nullable=True)  # 预览图路径
    # OCR 结果
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_blocks_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # 块级 OCR 结果
    # 版面分析
    layout_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # text/table/figure/mixed
    rotation: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 感知特征
    phash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duplicate_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    first_page_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 候选字段（从 OCR 中提取的标题/日期/文号候选）
    candidates_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # 特征版本（用于缓存失效判断）
    feature_version: Mapped[str] = mapped_column(String(30), nullable=False, default="v1")
    # 页面关系分析结果
    page_relation_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class DocUnit(Base):
    """件实体：档案中一件的稳定身份标识，跨版本保持不变。"""

    __tablename__ = "doc_units"
    __table_args__ = (
        Index("ix_doc_units_batch_id_status", "batch_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    doc_kind: Mapped[str] = mapped_column(String(50), nullable=False, default="main")  # main/attachment
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")  # draft/review/final/archived
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class DocVersion(Base):
    """件版本：某件在某次草稿/正式/返工后的具体版本快照。"""

    __tablename__ = "doc_versions"
    __table_args__ = (
        Index("ix_doc_versions_doc_id_is_current", "doc_id", "is_current"),
        Index("ix_doc_versions_batch_id", "batch_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_version_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    doc_id: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version_type: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")  # draft/final/rework
    start_page: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_page: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    page_ids_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    sort_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 件在卷中的排序位置
    archive_no: Mapped[str | None] = mapped_column(String(200), nullable=True)  # 正式档号（Final 阶段才赋值）
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)  # 题名/日期/文号/责任者等
    tags_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)      # 标签数组
    confidence_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict) # 各字段置信度
    # quality scores：ocr_confidence / boundary_confidence / metadata_confidence /
    #                 rule_match_score / final_readiness_score  (Develop.md §19.1)
    quality_scores_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class WorkflowRun(Base):
    """工作流执行记录：每次启动/恢复/返工都产生一条记录。"""

    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_runs_batch_id", "batch_id"),
        Index("ix_workflow_runs_run_status", "run_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    run_type: Mapped[str] = mapped_column(String(30), nullable=False, default="normal")  # normal/resume/rework
    run_status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")  # running/paused/blocked/done/failed
    current_stage: Mapped[str] = mapped_column(String(100), nullable=False, default="ingest_batch")
    # 工作流状态快照
    state_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # 阻塞原因列表
    blocked_reasons_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    policy_snapshot_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class WorkflowCheckpoint(Base):
    """工作流检查点：用于故障恢复和局部重跑。"""

    __tablename__ = "workflow_checkpoints"
    __table_args__ = (
        Index("ix_workflow_checkpoints_run_id", "run_id"),
        Index("ix_workflow_checkpoints_batch_id_stage", "batch_id", "stage_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    checkpoint_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    run_id: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    stage_name: Mapped[str] = mapped_column(String(100), nullable=False)  # after_ocr/after_split/etc.
    # 轻量状态快照（不含大对象正文，只含引用地址和版本号）
    state_snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReviewTask(Base):
    """人工审核任务：边界审核/著录审核/放行审核。"""

    __tablename__ = "review_tasks"
    __table_args__ = (
        Index("ix_review_tasks_batch_id_status", "batch_id", "status"),
        Index("ix_review_tasks_assignee_user_id", "assignee_user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_task_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 审核类型：boundary（分件/边界）/ ordering（排序/归属）/ metadata（字段/著录）/ final_release（放行）
    task_type: Mapped[str] = mapped_column(String(30), nullable=False, default="boundary")
    # 涉及的页面和件
    affected_page_ids_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    affected_doc_ids_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # 系统生成的原因和证据
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # 置信度
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # 分配与状态
    assignee_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")  # pending/claimed/submitted/resolved/skipped
    # 审核结果（人工提交后填写）
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ReviewActionLog(Base):
    """审核动作日志：每次审核操作的不可变记录。"""

    __tablename__ = "review_action_logs"
    __table_args__ = (
        Index("ix_review_action_logs_review_task_id", "review_task_id"),
        Index("ix_review_action_logs_batch_id", "batch_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_task_id: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    operator_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # claim/submit/skip/rework
    before_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReworkTask(Base):
    """返工任务：检录员发现问题后提交，租户管理员受理后进入返工流程。"""

    __tablename__ = "rework_tasks"
    __table_args__ = (
        Index("ix_rework_tasks_batch_id_status", "batch_id", "status"),
        Index("ix_rework_tasks_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rework_task_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    record_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False, default="boundary")  # boundary/ordering/metadata/other
    # 返工范围（页级或全卷）
    affected_scope_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # 问题描述
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reported_by: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 检录员 user_id
    accepted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 租户管理员 user_id
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")  # pending/accepted/rejected/in_rework/done
    rework_level: Mapped[str] = mapped_column(String(30), nullable=False, default="partial")  # partial/full_rework
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ArtifactFile(Base):
    """产物文件：所有中间产物和导出结果的统一登记表。

    artifact_type: raw_image / page_preview / draft_catalog / final_catalog /
                   draft_searchable_pdf / final_searchable_pdf / export_zip
    Develop.md §16.2
    """

    __tablename__ = "artifact_files"
    __table_args__ = (
        Index("ix_artifact_files_batch_id", "batch_id"),
        Index("ix_artifact_files_doc_id", "doc_id"),
        Index("ix_artifact_files_run_id", "created_by_run_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    artifact_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    doc_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    artifact_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    storage_uri: Mapped[str] = mapped_column(String(700), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by_run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # pending_upload / uploaded / replaced / deleted
    upload_status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploaded")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# 补充模型（Develop.md §16）
# ---------------------------------------------------------------------------

class SourceFile(Base):
    """源文件：每批次中的原始上传文件记录。Develop.md §16.1"""

    __tablename__ = "source_files"
    __table_args__ = (
        Index("ix_source_files_batch_id", "batch_id"),
        Index("ix_source_files_tenant_id", "tenant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    batch_id: Mapped[str] = mapped_column(String(100), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(700), nullable=False)  # MinIO raw path
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # pending / processing / done / failed
    process_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    uploaded_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class AuditLog(Base):
    """审计日志：关键操作的不可变记录。Develop.md §19.3

    涵盖动作：batch_import / workflow_start / review_submit / rework_request /
              rework_accept / rework_reject / final_release / archive_store /
              export_download
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_id_occurred_at", "tenant_id", "occurred_at"),
        Index("ix_audit_logs_operator_user_id", "operator_user_id"),
        Index("ix_audit_logs_target_type_id", "target_type", "target_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    operator_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    operator_username: Mapped[str] = mapped_column(String(120), nullable=False, default="system")
    # action 枚举值：batch_import/workflow_start/review_submit/rework_request/
    #               rework_accept/rework_reject/final_release/archive_store/export_download
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # batch/doc/review_task/etc.
    target_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    before_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# DocVersion 补充字段（quality scores，Develop.md §19.1）
# 由于 SQLAlchemy 不支持在类外直接追加字段，在此通过表级 DDL migration 处理，
# 同时在 _run_schema_migrations 中添加 ADD COLUMN IF NOT EXISTS。
# quality_scores_json 结构：
#   { "ocr_confidence": float, "boundary_confidence": float,
#     "metadata_confidence": float, "rule_match_score": float,
#     "final_readiness_score": float }
# ---------------------------------------------------------------------------
