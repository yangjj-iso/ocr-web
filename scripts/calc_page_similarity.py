import asyncio
import os
import sys
import argparse

# Add project root to sys.path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import async_session
from app.db.models import OCRTask


def get_char_ngrams(text: str, n: int = 2) -> set:
    """提取字符级 n-gram 集合"""
    if not text:
        return set()
    text = text.replace(" ", "").replace("\n", "").replace("\r", "").replace("\t", "")
    if len(text) < n:
        return {text}
    return set(text[i:i+n] for i in range(len(text)-n+1))


def calculate_jaccard_similarity(text1: str, text2: str, n: int = 2) -> float:
    """
    计算基于 n-gram 的 Jaccard 文本相似度
    适用于中文文本的快速特征重合度计算（无需分词库）
    """
    if not text1 and not text2:
        return 1.0
    if not text1 or not text2:
        return 0.0

    set1 = get_char_ngrams(text1, n)
    set2 = get_char_ngrams(text2, n)
    
    intersection = set1.intersection(set2)
    union = set1.union(set2)
    
    if not union:
        return 0.0
    return len(intersection) / len(union)


async def analyze_batch_similarity(batch_id_or_folder: str, n_gram: int = 2):
    """查询同批次/同文件夹下的任务，按文件名排序，计算相邻页相似度"""
    async with async_session() as db:
        # 查询任务，按文件名排序以确保按页码（如 001, 002, 003）顺序计算
        stmt = (
            select(OCRTask)
            .where(OCRTask.file_path.ilike(f"%{batch_id_or_folder}%"))
            .order_by(OCRTask.filename.asc())
        )
        
        result = await db.execute(stmt)
        tasks = result.scalars().all()

        if not tasks:
            print(f"未找到路径或批次中包含 '{batch_id_or_folder}' 的任务。")
            return

        print(f"\n找到 {len(tasks)} 个按文件名排序的任务，开始计算相邻页相似度 (N-Gram={n_gram})：")
        print("-" * 80)
        
        for i in range(len(tasks) - 1):
            current_task = tasks[i]
            next_task = tasks[i+1]
            
            text_curr = current_task.full_text or ""
            text_next = next_task.full_text or ""
            
            # 过滤掉极短的空白页
            if len(text_curr) < 10 or len(text_next) < 10:
                similarity = 0.0
            else:
                similarity = calculate_jaccard_similarity(text_curr, text_next, n=n_gram)
            
            # 打印格式化结果
            curr_name = current_task.filename
            next_name = next_task.filename
            
            # 设定一个阈值预警，例如相似度 > 0.05 或 0.1 通常意味着有连贯的长文本或相同表头
            is_linked = "🔗 [可能连页]" if similarity > 0.08 else "✂️ [独立文档]"
            
            print(f"{curr_name} -> {next_name}")
            print(f"  相似度: {similarity:.4f}  |  状态: {is_linked}")
        print("-" * 80)
        print("计算完成。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="计算相邻 OCR 任务（页）的文本相似度")
    parser.add_argument("folder_keyword", type=str, help="数据库 file_path 包含的文件夹关键词或 batch_id (如: '预算材料' 或 '2023-batch-001')")
    parser.add_argument("--ngram", type=int, default=2, help="N-Gram 大小 (默认 2，即相邻2个汉字组合)")
    args = parser.parse_args()

    asyncio.run(analyze_batch_similarity(args.folder_keyword, args.ngram))
