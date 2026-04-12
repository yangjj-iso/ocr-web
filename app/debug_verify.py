"""Verify fix: test extract_fields from excel_export for both doc types."""
import asyncio
import json
import sys
sys.path.insert(0, ".")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text as sa_text

DB_URL = "postgresql+asyncpg://postgres:123456@127.0.0.1:5432/ocr_db"

from app.services.excel_export import extract_fields, _extract_from_table_data

async def main():
    engine = create_async_engine(DB_URL)
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as s:
        # Test 1: D10-0311 (公文处理单 - single page with table)
        r = await s.execute(sa_text(
            "SELECT id, filename, full_text, result_json, page_count "
            "FROM ocr_tasks WHERE filename LIKE '%D10-0311-001%' ORDER BY id LIMIT 1"
        ))
        row = r.fetchone()
        if row:
            tid, fname, ft, rj, pc = row
            if isinstance(rj, str): rj = json.loads(rj)
            print("=== Test 1: D10-0311-001 (公文处理单) ===")
            table_f = _extract_from_table_data(rj)
            print(f"  Table fallback: {table_f}")
            fields = extract_fields(fname, ft or "", rj, pc)
            print(f"  Final:")
            for k, v in fields.items(): print(f"    {k}: {v}")
            # For this doc, scoring extracts nothing useful from text, table fills gaps
            print(f"  题名 OK: {fields['题名'] == '国资周情'}")
            print(f"  责任者 OK: {fields['责任者'] == '重庆市国资委办公室'}")

        # Test 2: D30-0156 (5 pages merged - 会议纪要 with archive page)
        r = await s.execute(sa_text(
            "SELECT DISTINCT ON (filename) id, filename, full_text, result_json, page_count "
            "FROM ocr_tasks WHERE filename LIKE '%D30-0156%' ORDER BY filename, id"
        ))
        rows = r.fetchall()
        if rows:
            all_pages = []
            merged_text_parts = []
            for row in rows:
                tid, fname, ft, rj, pc = row
                if isinstance(rj, str): rj = json.loads(rj)
                if ft: merged_text_parts.append(ft)
                if isinstance(rj, list): all_pages.extend(rj)
                elif isinstance(rj, dict): all_pages.append(rj)
            merged_text = "\n".join(merged_text_parts)
            print(f"\n=== Test 2: D30-0156 merged ({len(rows)} pages) ===")
            table_f = _extract_from_table_data(all_pages)
            print(f"  Table fallback: {table_f}")
            fields = extract_fields(rows[0][1], merged_text, all_pages, len(all_pages))
            print(f"  Final:")
            for k, v in fields.items(): print(f"    {k}: {v}")
            print(f"  责任者 OK: {'综合部' in fields.get('责任者', '')}")
            print(f"  Expected: 重庆两江新区文化传媒集团有限公司综合部")

    await engine.dispose()

asyncio.run(main())
