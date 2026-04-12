"""Debug: understand why _extract_responsible picks wrong candidate for D30-0156."""
import asyncio
import json
import sys
sys.path.insert(0, ".")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text as sa_text

DB_URL = "postgresql+asyncpg://postgres:123456@127.0.0.1:5432/ocr_db"

from app.services.excel_export import (
    _collect_items, _extract_responsible, _extract_responsible_candidates,
    extract_fields, ISSUED_BY_PATTERN,
)

async def main():
    engine = create_async_engine(DB_URL)
    sf = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as s:
        # Load all pages of D30-0156
        r = await s.execute(sa_text(
            "SELECT id, filename, full_text, result_json, page_count "
            "FROM ocr_tasks WHERE filename LIKE '%D30-0156%' ORDER BY filename"
        ))
        rows = r.fetchall()
        print(f"Found {len(rows)} pages for D30-0156\n")

        # Simulate merged extraction like the batch merge does
        all_texts = []
        all_pages = []
        for row in rows:
            tid, fname, ft, rj, pc = row
            print(f"  Page: {fname}")
            if isinstance(rj, str):
                rj = json.loads(rj)
            if ft:
                all_texts.append(ft)
            if isinstance(rj, list):
                all_pages.extend(rj)
            elif isinstance(rj, dict):
                all_pages.append(rj)

        merged_text = "\n".join(all_texts)
        merged_page_count = len(all_pages)
        print(f"\nMerged: {merged_page_count} pages, {len(merged_text)} chars")

        # Collect items and score responsible candidates
        items = _collect_items(all_pages, merged_text)
        print(f"Total items: {len(items)}")

        # Show top 责任者 candidates with scores
        print("\n=== Top 责任者 candidates (all items) ===")
        candidates_with_scores = []
        for item in items:
            for candidate, source_type in _extract_responsible_candidates(item['text']):
                score = 0
                if source_type == 'party': score += 25
                if source_type == 'issued': score += 20
                if item['type'] == 'seal': score += 18
                if any(w in item['text'] for w in ('盖章', '印章', '公章')): score += 15
                if any(w in item['text'] for w in ('发文单位', '发文机关', '主送')): score += 15
                if any(w in item['text'] for w in ('印发', '发布', '下发')): score += 10
                if item['page_index'] == item['page_total'] - 1 and item['y_ratio'] > 0.55: score += 12
                if item['page_index'] == 0 and item['y_ratio'] < 0.35: score += 4
                if source_type == 'head': score += 6
                if source_type == 'full': score += 4
                if source_type == 'fragment': score -= 5
                if 4 <= len(candidate) <= 24: score += 3
                if len(candidate) > 32: score -= 2
                candidates_with_scores.append((candidate, score, source_type, item['page_index'], item['type'], item['text'][:80]))

        candidates_with_scores.sort(key=lambda x: -x[1])
        for cand, sc, st, pi, it, txt in candidates_with_scores[:15]:
            print(f"  score={sc:3d} type={st:8s} page={pi} item_type={it:15s} candidate={cand}")
            print(f"           text={txt}")

        # Check ISSUED_BY_PATTERN matches
        print("\n=== ISSUED_BY_PATTERN matches ===")
        for item in items:
            m = ISSUED_BY_PATTERN.search(item['text'])
            if m:
                print(f"  page={item['page_index']} match={m.group(0)[:80]}")

        # Final extraction result
        fields = extract_fields(rows[0][1], merged_text, all_pages, merged_page_count)
        print(f"\n=== Final fields ===")
        for k, v in fields.items():
            print(f"  {k}: {v}")

    await engine.dispose()

asyncio.run(main())
