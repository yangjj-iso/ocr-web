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
