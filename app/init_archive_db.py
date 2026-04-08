"""
一次性脚本：将现有 Excel 归档文件目录写入 archive_records 数据库表。
运行方式：D:\OCR\.venv\Scripts\python.exe init_archive_db.py
"""
import asyncio
import os
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
sys.path.insert(0, str(Path(__file__).parent))

EXCEL_PATH = sys.argv[1] if len(sys.argv) > 1 else os.getenv(
    "INIT_ARCHIVE_EXCEL_PATH",
    r"D:\GOOLGE\软件著录\归档文件目录（所需字段）.xls"
)
BATCH_ID = os.getenv("INIT_ARCHIVE_BATCH_ID", "init_import")


async def main():
    from app.db.database import init_db, async_session
    from app.services.archive_service import import_from_excel

    print(f"[init_archive_db] 正在初始化数据库表...")
    await init_db()
    print(f"[init_archive_db] 数据库表就绪")

    print(f"[init_archive_db] 读取 Excel: {EXCEL_PATH}")
    async with async_session() as db:
        try:
            count = await import_from_excel(db, EXCEL_PATH, batch_id=BATCH_ID)
            print(f"[init_archive_db] 成功导入 {count} 条归档记录 ✓")
        except FileNotFoundError as e:
            print(f"[init_archive_db] 错误：文件不存在 -> {e}")
            sys.exit(1)
        except (ValueError, ImportError) as e:
            print(f"[init_archive_db] 错误：{e}")
            sys.exit(1)
        except Exception as e:
            print(f"[init_archive_db] 导入失败：{e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
