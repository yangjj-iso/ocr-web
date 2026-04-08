"""CLI wrapper for rebuilding logical PDF files from sequential images."""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.utils.image_sequence_pdf import main


if __name__ == "__main__":
    raise SystemExit(main())
