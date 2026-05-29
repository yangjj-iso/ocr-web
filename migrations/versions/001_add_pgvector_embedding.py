"""add pgvector embedding column to archive_records

Revision ID: 001_add_pgvector_embedding
Create Date: 2026-05-29

Adds:
- pgvector extension
- embedding column (vector(1024)) to archive_records
- IVFFlat index for cosine similarity search
"""

# This migration can be run manually via psql or integrated with Alembic.
# For manual execution, run the SQL below against your PostgreSQL database.

UPGRADE_SQL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column
ALTER TABLE archive_records
    ADD COLUMN IF NOT EXISTS embedding vector(1024);

-- Create IVFFlat index for cosine similarity search
-- Note: IVFFlat requires at least some data to build the index effectively.
-- For small datasets (<1000 rows), consider using HNSW instead.
CREATE INDEX IF NOT EXISTS idx_archive_embedding
    ON archive_records
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
"""

DOWNGRADE_SQL = """
DROP INDEX IF EXISTS idx_archive_embedding;
ALTER TABLE archive_records DROP COLUMN IF EXISTS embedding;
-- Note: We don't drop the vector extension as other tables might use it.
"""


async def upgrade(db_url: str | None = None) -> None:
    """Run the migration programmatically."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    if db_url is None:
        from app.config import DATABASE_URL
        db_url = DATABASE_URL

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        for statement in UPGRADE_SQL.strip().split(";"):
            statement = statement.strip()
            if statement:
                await conn.execute(text(statement))
    await engine.dispose()
    print("Migration complete: pgvector embedding column added.")


async def downgrade(db_url: str | None = None) -> None:
    """Revert the migration."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    if db_url is None:
        from app.config import DATABASE_URL
        db_url = DATABASE_URL

    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        for statement in DOWNGRADE_SQL.strip().split(";"):
            statement = statement.strip()
            if statement:
                await conn.execute(text(statement))
    await engine.dispose()
    print("Downgrade complete: embedding column removed.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(upgrade())
