import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    engine = create_async_engine("postgresql+asyncpg://postgres:123456@localhost:5432/ocr_db")
    async with engine.begin() as conn:
        r = await conn.execute(text(
            "SELECT MIN(id), MAX(id), COUNT(*), "
            "COUNT(*) FILTER (WHERE status='done') "
            "FROM ocr_tasks WHERE id >= 170"
        ))
        row = r.fetchone()
        print(f"Tasks >=170: ID {row[0]}-{row[1]}, total: {row[2]}, done: {row[3]}")

        # Sample a few filenames
        r2 = await conn.execute(text(
            "SELECT id, filename, status, page_count, LEFT(full_text, 200) "
            "FROM ocr_tasks WHERE id >= 170 AND status='done' "
            "ORDER BY id LIMIT 5"
        ))
        for row in r2:
            print(f"\n[{row[0]}] {row[1]} (pages={row[3]})")
            print(f"  Text: {(row[4] or '')[:150]}")

    await engine.dispose()

asyncio.run(main())
