from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    # Ensure all model classes are registered on Base.metadata before create_all.
    from app.db import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _run_schema_migrations()


async def _run_schema_migrations() -> None:
    """Idempotent DDL migrations for columns added after initial schema creation."""
    import logging
    from sqlalchemy import text

    log = logging.getLogger(__name__)
    _col_stmts = [
        # app_users: add role column (default 'operator')
        "ALTER TABLE app_users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'operator'",
        # app_users: add display_name column
        "ALTER TABLE app_users ADD COLUMN IF NOT EXISTS display_name VARCHAR(120)",
        # Back-fill is_admin=true rows to role='admin'
        "UPDATE app_users SET role = 'admin' WHERE is_admin = TRUE AND role = 'operator'",
        # app_users: add capabilities column (岗位能力标签)
        "ALTER TABLE app_users ADD COLUMN IF NOT EXISTS capabilities VARCHAR(100)",
        # Migrate old operator/searcher top-level roles to member + capability tag
        "UPDATE app_users SET capabilities = role, role = 'member' WHERE role IN ('operator', 'searcher')",
        # doc_versions: quality scores (Develop.md §19.1)
        "ALTER TABLE doc_versions ADD COLUMN IF NOT EXISTS quality_scores_json JSONB NOT NULL DEFAULT '{}'",
        # ── 多租户迁移 ──────────────────────────────────────────────────────────
        # 创建租户表
        """CREATE TABLE IF NOT EXISTS tenants (
            id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(120) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )""",
        # 初始化默认租户
        "INSERT INTO tenants (id, name) VALUES ('default', '默认机构') ON CONFLICT DO NOTHING",
        # app_users: 添加 tenant_id
        "ALTER TABLE app_users ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(64) NOT NULL DEFAULT 'default'",
        # ocr_tasks: 添加 tenant_id
        "ALTER TABLE ocr_tasks ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(64) NOT NULL DEFAULT 'default'",
        # batch_assignments: 添加 tenant_id
        "ALTER TABLE batch_assignments ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(64) NOT NULL DEFAULT 'default'",
        # ── 档案工作流字段迁移 ────────────────────────────────────────────────────
        # ocr_tasks: 批次/指派/提交/进度/审核字段（与 Java 控制平面 OcrTaskEntity 对齐）
        "ALTER TABLE ocr_tasks ADD COLUMN IF NOT EXISTS batch_id VARCHAR(120)",
        "ALTER TABLE ocr_tasks ADD COLUMN IF NOT EXISTS assignee_username VARCHAR(120)",
        "ALTER TABLE ocr_tasks ADD COLUMN IF NOT EXISTS submitter_username VARCHAR(120)",
        "ALTER TABLE ocr_tasks ADD COLUMN IF NOT EXISTS submission_name VARCHAR(255)",
        "ALTER TABLE ocr_tasks ADD COLUMN IF NOT EXISTS progress_percent FLOAT DEFAULT 0.0",
        "ALTER TABLE ocr_tasks ADD COLUMN IF NOT EXISTS processed_pages INTEGER DEFAULT 0",
        "ALTER TABLE ocr_tasks ADD COLUMN IF NOT EXISTS total_pages INTEGER DEFAULT 0",
        "ALTER TABLE ocr_tasks ADD COLUMN IF NOT EXISTS review_status VARCHAR(50)",
        "ALTER TABLE ocr_tasks ADD COLUMN IF NOT EXISTS review_reason TEXT",
        # 索引
        "CREATE INDEX IF NOT EXISTS ix_ocr_tasks_batch_id ON ocr_tasks (batch_id)",
        "CREATE INDEX IF NOT EXISTS ix_ocr_tasks_assignee_username ON ocr_tasks (assignee_username)",
    ]
    async with engine.begin() as conn:
        for stmt in _col_stmts:
            try:
                await conn.execute(text(stmt))
            except Exception as exc:
                log.warning("Migration stmt skipped (%s): %s", type(exc).__name__, stmt[:80])


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
