import os
from pathlib import Path


def _env_flag(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_choice(name: str, default: str, allowed: set[str]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value in allowed:
        return value
    return default


def _env_csv(name: str, default: str = "") -> tuple[str, ...]:
    raw_value = os.getenv(name, default)
    values: list[str] = []
    for item in raw_value.split(","):
        value = item.strip()
        if value:
            values.append(value)
    return tuple(values)


def _build_path_roots(raw_value: str, defaults: list[Path]) -> tuple[Path, ...]:
    roots: list[Path] = []
    for item in raw_value.split(","):
        value = item.strip()
        if not value:
            continue
        roots.append(Path(value).expanduser().resolve(strict=False))
    if not roots:
        roots = [path.resolve(strict=False) for path in defaults]

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        normalized = os.path.normcase(str(root))
        if normalized not in seen:
            unique.append(root)
            seen.add(normalized)
    return tuple(unique)


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent


def _load_local_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ[key] = value
    except OSError:
        return


def _mask_secret(value: str, visible_prefix: int = 8, visible_suffix: int = 6) -> str:
    secret = (value or "").strip()
    if not secret:
        return "<empty>"
    if len(secret) <= visible_prefix + visible_suffix:
        return "*" * min(len(secret), 8)
    return f"{secret[:visible_prefix]}...{secret[-visible_suffix:]}"


_load_local_env_file(PROJECT_ROOT / ".env")
_load_local_env_file(BASE_DIR / ".env")

# Cache and model download directories
CACHE_DIR = Path(os.getenv("CACHE_DIR", str(BASE_DIR / ".cache"))).resolve(strict=False)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("HF_HOME", str(CACHE_DIR / "huggingface"))
os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(CACHE_DIR / "paddlex"))
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "bos")
os.environ.setdefault("FLAGS_json_format_model", "0")

# Database and Redis
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:123456@localhost:5432/ocr_db",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
APP_ENV = os.getenv("APP_ENV", "production").strip().lower()

# File storage
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))).resolve(strict=False)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".pdf"}
MAX_FILE_SIZE = 50 * 1024 * 1024

# OCR runtime
OCR_USE_GPU = _env_flag("OCR_USE_GPU", True)
OCR_DEVICE = os.getenv("OCR_DEVICE", "gpu:0" if OCR_USE_GPU else "cpu")
OCR_LANG = os.getenv("OCR_LANG", "ch")
OCR_VL_BACKEND = _env_choice(
    "OCR_VL_BACKEND",
    "api" if APP_ENV in {"test", "testing", "staging", "uat"} else "auto",
    {"auto", "local", "baidu", "api"},
)
OCR_LAYOUT_BACKEND = _env_choice(
    "OCR_LAYOUT_BACKEND",
    "api" if APP_ENV in {"test", "testing", "staging", "uat"} else "local",
    {"local", "api"},
)
OCR_LAYOUT_API_URL = os.getenv("OCR_LAYOUT_API_URL", "").strip()
OCR_LAYOUT_API_TOKEN = os.getenv("OCR_LAYOUT_API_TOKEN", "").strip()
OCR_LAYOUT_API_TIMEOUT_SECONDS = float(os.getenv("OCR_LAYOUT_API_TIMEOUT_SECONDS", "120"))
OCR_LAYOUT_API_USE_DOC_ORIENTATION_CLASSIFY = _env_flag(
    "OCR_LAYOUT_API_USE_DOC_ORIENTATION_CLASSIFY",
    False,
)
OCR_LAYOUT_API_USE_DOC_UNWARPING = _env_flag("OCR_LAYOUT_API_USE_DOC_UNWARPING", False)
OCR_LAYOUT_API_USE_CHART_RECOGNITION = _env_flag("OCR_LAYOUT_API_USE_CHART_RECOGNITION", False)
ENABLE_HIERARCHICAL_AGENT = _env_flag("ENABLE_HIERARCHICAL_AGENT", False)
MAX_RETRIES = max(0, int(os.getenv("MAX_RETRIES", "2")))
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.85"))
HUMAN_REVIEW_MIN_CONFIDENCE = float(os.getenv("HUMAN_REVIEW_MIN_CONFIDENCE", "0.60"))
HUMAN_REVIEW_MAX_CONFIDENCE = float(os.getenv("HUMAN_REVIEW_MAX_CONFIDENCE", "0.85"))
VISION_ROUTE_COMPLEXITY_THRESHOLD = float(os.getenv("VISION_ROUTE_COMPLEXITY_THRESHOLD", "0.45"))

# Auth
AUTH_ENABLED = _env_flag("AUTH_ENABLED", False)
AUTH_USERNAME = os.getenv("AUTH_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("AUTH_PASSWORD", "change-me")
AUTH_SECRET = os.getenv("AUTH_SECRET", "change-this-secret")
AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "ocr_session")
AUTH_COOKIE_SECURE = _env_flag("AUTH_COOKIE_SECURE", False)
AUTH_COOKIE_SAMESITE = _env_choice("AUTH_COOKIE_SAMESITE", "lax", {"lax", "strict", "none"})
AUTH_SESSION_TTL = int(os.getenv("AUTH_SESSION_TTL", "28800"))

# API access
CORS_ALLOW_ORIGINS = _env_csv(
    "CORS_ALLOW_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:4173,http://127.0.0.1:4173",
)

# MiniMax field extraction
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")
MINIMAX_TIMEOUT_SECONDS = float(os.getenv("MINIMAX_TIMEOUT_SECONDS", "60"))
MINIMAX_MAX_INPUT_CHARS = int(os.getenv("MINIMAX_MAX_INPUT_CHARS", "12000"))
MINIMAX_BATCH_CONCURRENCY = max(1, int(os.getenv("MINIMAX_BATCH_CONCURRENCY", "20")))
MINIMAX_ENABLED = _env_flag("MINIMAX_ENABLED", bool(MINIMAX_API_KEY.strip()))

# Baidu AI Cloud API (文档解析 PaddleOCR-VL)
BAIDU_API_KEY = os.getenv("BAIDU_API_KEY", "")
BAIDU_SECRET_KEY = os.getenv("BAIDU_SECRET_KEY", "")

# Local filesystem access
LOCAL_PATH_ROOTS = _build_path_roots(
    os.getenv("LOCAL_PATH_ROOTS", ""),
    defaults=[UPLOAD_DIR, BASE_DIR],
)
