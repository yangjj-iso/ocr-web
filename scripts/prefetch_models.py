"""
在 Docker 构建阶段预下载所有 OCR 模型，确保镜像可离线运行。
用法: python scripts/prefetch_models.py
"""
import os
import sys

os.environ["FLAGS_json_format_model"] = "0"
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "bos")

DEVICE = "cpu"  # 构建阶段无 GPU，仅下载模型文件

print("=" * 60)
print("  模型预下载 — 确保 Docker 镜像可离线运行")
print("=" * 60)

# ---------- 1. PP-OCRv5 ----------
print("\n[1/3] 下载 PP-OCRv5 模型...")
try:
    from paddleocr import PaddleOCR
    _ocr = PaddleOCR(
        lang="ch",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        device=DEVICE,
    )
    print("  ✓ PP-OCRv5 下载完成")
except Exception as e:
    print(f"  ✗ PP-OCRv5 下载失败: {e}", file=sys.stderr)
    sys.exit(1)

# ---------- 2. PP-StructureV3 (layout_parsing) ----------
print("\n[2/3] 下载 PP-StructureV3 版面解析模型...")
try:
    from paddlex import create_pipeline
    _layout = create_pipeline(pipeline="layout_parsing", device=DEVICE)
    print("  ✓ PP-StructureV3 下载完成")
except Exception as e:
    print(f"  ✗ PP-StructureV3 下载失败: {e}", file=sys.stderr)
    sys.exit(1)

# ---------- 3. PaddleOCR-VL-1.5 ----------
print("\n[3/3] 下载 PaddleOCR-VL-1.5 视觉语言模型...")
try:
    # VL 管线的 PP-DocLayoutV3 需要 JSON 格式模型，临时移除标志
    old_flag = os.environ.pop("FLAGS_json_format_model", None)
    _vl = create_pipeline(pipeline="PaddleOCR-VL-1.5", device=DEVICE)
    if old_flag is not None:
        os.environ["FLAGS_json_format_model"] = old_flag
    print("  ✓ PaddleOCR-VL-1.5 下载完成")
except Exception as e:
    print(f"  ✗ PaddleOCR-VL-1.5 下载失败: {e}", file=sys.stderr)
    sys.exit(1)

print("\n" + "=" * 60)
print("  全部 3 个模型预下载完成！镜像可离线运行。")
print("=" * 60)
