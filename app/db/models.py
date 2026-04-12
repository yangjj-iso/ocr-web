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


class AppUser(Base):
    __tablename__ = "app_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending/active/rejected
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # role: admin / operator / searcher
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="operator")
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
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
    mode: Mapped[str] = mapped_column(String(20), default="layout")  # vl/layout/ocr
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/processing/done/failed
    result_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # OCR 结果 JSON
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
