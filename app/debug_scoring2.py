"""Debug: find 综合部 and 印发 items for D30-0156."""
import asyncio
import json
import sys
import re
sys.path.insert(0, ".")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text as sa_text

DB_URL = "postgresql+asyncpg://postgres:123456@127.0.0.1:5432/ocr_db"

from app.services.excel_export import (
    _collect_items, ISSUED_BY_PATTERN, _extract_responsible_candidates,
)

async def main():
    engine = create_async_engine(DB_URL)
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as s:
        # Load ONLY DISTINCT pages (avoid duplicates)
        r = await s.execute(sa_text(
            "SELECT DISTINCT ON (filename) id, filename, full_text, result_json, page_count "
            "FROM ocr_tasks WHERE filename LIKE '%D30-0156%' ORDER BY filename, id"
        ))
        rows = r.fetchall()
        print(f"Found {len(rows)} distinct pages\n")

        all_pages = []
        merged_text_parts = []
        for row in rows:
            tid, fname, ft, rj, pc = row
            print(f"  {fname} (task {tid})")
            if isinstance(rj, str):
                rj = json.loads(rj)
            if ft:
                merged_text_parts.append(ft)
            if isinstance(rj, list):
                all_pages.extend(rj)
            elif isinstance(rj, dict):
                all_pages.append(rj)

        merged_text = "\n".join(merged_text_parts)
        items = _collect_items(all_pages, merged_text)
        print(f"\nTotal items: {len(items)}, pages: {len(all_pages)}")

        # Find items containing 综合部 or 印发
        print("\n=== Items containing '综合部' ===")
        for item in items:
            if '综合部' in item['text']:
                cands = _extract_responsible_candidates(item['text'])
                issued_m = ISSUED_BY_PATTERN.search(item['text'])
                print(f"  page={item['page_index']} type={item['type']:15s} y={item['y_ratio']:.2f}")
                print(f"  text={item['text'][:120]}")
                print(f"  candidates={[(c,t) for c,t in cands]}")
                print(f"  ISSUED_BY match={issued_m.group(0)[:80] if issued_m else 'NONE'}")
                print()

        print("\n=== Items containing '印发' ===")
        for item in items:
            if '印发' in item['text']:
                issued_m = ISSUED_BY_PATTERN.search(item['text'])
                print(f"  page={item['page_index']} type={item['type']:15s} y={item['y_ratio']:.2f}")
                print(f"  text={item['text'][:120]}")
                print(f"  ISSUED_BY match={issued_m.group(0)[:80] if issued_m else 'NONE'}")
                print()

        # Check table regions for archive page (page 4/5)
        print("\n=== Table regions ===")
        for pi, page in enumerate(all_pages):
            if not isinstance(page, dict):
                continue
            for region in page.get("regions", []):
                if region.get("type") == "table" and region.get("table_data"):
                    print(f"  Page {pi}: table_data rows:")
                    for ri, row in enumerate(region["table_data"][:8]):
                        print(f"    [{ri}] {json.dumps(row, ensure_ascii=False)[:150]}")

    await engine.dispose()

asyncio.run(main())
