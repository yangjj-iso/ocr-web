"""
批量回填 embedding 脚本

扫描所有 embedding IS NULL 的 ArchiveRecord，批量调用 embedding API 生成向量并写入。
支持断点续传（按 ID 排序，从上次中断处继续）。

用法:
    python scripts/backfill_embeddings.py [--batch-size 32] [--start-id 0]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _record_text(record) -> str:
    """拼接所有字段作为 embedding 输入"""
    parts = [
        str(record.archive_no or ""),
        str(record.doc_no or ""),
        str(record.responsible or ""),
        str(record.title or ""),
        str(record.date or ""),
        str(record.pages or ""),
        str(record.classification or ""),
        str(record.remarks or ""),
    ]
    return " ".join(p for p in parts if p).strip()


async def backfill(batch_size: int = 32, start_id: int = 0) -> None:
    from sqlalchemy import select, update
    from app.db.database import async_session
    from app.db.models import ArchiveRecord
    from app.services.embedding_service import embed_texts, is_embedding_available

    if not is_embedding_available():
        logger.error("Embedding service is not configured. Set EMBEDDING_BASE_URL and EMBEDDING_MODEL.")
        return

    total_processed = 0
    current_id = start_id

    while True:
        async with async_session() as db:
            # 获取下一批未嵌入的记录
            stmt = (
                select(ArchiveRecord)
                .where(ArchiveRecord.id > current_id)
                .where(ArchiveRecord.embedding.is_(None))
                .order_by(ArchiveRecord.id)
                .limit(batch_size)
            )
            records = (await db.execute(stmt)).scalars().all()

            if not records:
                break

            # 准备文本
            texts = []
            valid_records = []
            for record in records:
                text = _record_text(record)
                if text:
                    texts.append(text)
                    valid_records.append(record)
                current_id = record.id

            if not texts:
                continue

            # 批量生成 embedding
            vectors = await embed_texts(texts)

            # 写入数据库
            update_count = 0
            for record, vector in zip(valid_records, vectors):
                if vector is not None:
                    await db.execute(
                        update(ArchiveRecord)
                        .where(ArchiveRecord.id == record.id)
                        .values(embedding=vector)
                    )
                    update_count += 1

            await db.commit()
            total_processed += update_count
            logger.info(
                "Batch complete: processed %d/%d records (last_id=%d, total=%d)",
                update_count,
                len(valid_records),
                current_id,
                total_processed,
            )

    logger.info("Backfill complete. Total records embedded: %d", total_processed)


def main():
    parser = argparse.ArgumentParser(description="Backfill embeddings for archive records")
    parser.add_argument("--batch-size", type=int, default=32, help="Records per API call")
    parser.add_argument("--start-id", type=int, default=0, help="Resume from this record ID")
    args = parser.parse_args()

    asyncio.run(backfill(batch_size=args.batch_size, start_id=args.start_id))


if __name__ == "__main__":
    main()
