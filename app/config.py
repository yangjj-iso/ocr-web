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
MQ_BROKER_URL = os.getenv(
    "MQ_BROKER_URL",
    os.getenv("RABBITMQ_URL", "amqp://ocr_admin:ocr_password123@127.0.0.1:5672//"),
).strip()
MQ_COMMAND_EXCHANGE = os.getenv("MQ_COMMAND_EXCHANGE", "ocr.task.command.exchange").strip()
MQ_COMMAND_QUEUE = os.getenv("MQ_COMMAND_QUEUE", "ocr.task.command.queue").strip()
MQ_COMMAND_ROUTING_KEY = os.getenv("MQ_COMMAND_ROUTING_KEY", "ocr.task.submit.v1").strip()
MQ_COMMAND_DLX = os.getenv("MQ_COMMAND_DLX", "ocr.task.command.dlx").strip()
MQ_COMMAND_DLQ = os.getenv("MQ_COMMAND_DLQ", "ocr.task.command.dlq").strip()
MQ_PUBLISH_RETRY_MAX = max(0, int(os.getenv("MQ_PUBLISH_RETRY_MAX", "3")))
MQ_PREFETCH_COUNT = max(1, int(os.getenv("MQ_PREFETCH_COUNT", "1")))
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", MQ_BROKER_URL).strip()
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "").strip() or None
CELERY_TASK_EXCHANGE = os.getenv("CELERY_TASK_EXCHANGE", "ocr.compute.internal.exchange").strip()
CELERY_TASK_QUEUE = os.getenv("CELERY_TASK_QUEUE", "ocr.compute.internal.queue").strip()
CELERY_TASK_ROUTING_KEY = os.getenv("CELERY_TASK_ROUTING_KEY", "ocr.compute.execute.v1").strip()
CONTROL_PLANE_BASE_URL = os.getenv("CONTROL_PLANE_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
CONTROL_PLANE_INTERNAL_TOKEN = os.getenv(
    "CONTROL_PLANE_INTERNAL_TOKEN",
    os.getenv("OCR_INTERNAL_API_TOKEN", "change-this-internal-token"),
).strip()
CONTROL_PLANE_CALLBACK_TIMEOUT_SECONDS = float(os.getenv("CONTROL_PLANE_CALLBACK_TIMEOUT_SECONDS", "15"))
CONTROL_PLANE_VERIFY_TLS = _env_flag("CONTROL_PLANE_VERIFY_TLS", True)
COMPUTE_WORKER_ID = os.getenv("COMPUTE_WORKER_ID", "py-compute-worker").strip() or "py-compute-worker"
CALLBACK_INLINE_RESULT_MAX_BYTES = max(32768, int(os.getenv("CALLBACK_INLINE_RESULT_MAX_BYTES", str(1024 * 1024))))
LANGGRAPH_CHECKPOINTER_BACKEND = _env_choice(
    "LANGGRAPH_CHECKPOINTER_BACKEND",
    "memory",
    {"memory", "postgres", "redis"},
)
LANGGRAPH_CHECKPOINTER_DSN = os.getenv("LANGGRAPH_CHECKPOINTER_DSN", "").strip()
LANGGRAPH_CHECKPOINTER_REDIS_URL = os.getenv("LANGGRAPH_CHECKPOINTER_REDIS_URL", "").strip()
LANGGRAPH_HITL_ENABLED = _env_flag("LANGGRAPH_HITL_ENABLED", True)
LANGGRAPH_HUMAN_REVIEW_INTERRUPT_THRESHOLD = float(
    os.getenv("LANGGRAPH_HUMAN_REVIEW_INTERRUPT_THRESHOLD", "0.70")
)
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "").strip()
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "ocr-web-compute").strip() or "ocr-web-compute"
LANGCHAIN_ENDPOINT = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com").strip()
LANGCHAIN_TRACING_V2 = _env_flag("LANGCHAIN_TRACING_V2", bool(LANGCHAIN_API_KEY))
if LANGCHAIN_API_KEY and LANGCHAIN_TRACING_V2:
    os.environ.setdefault("LANGCHAIN_API_KEY", LANGCHAIN_API_KEY)
    os.environ.setdefault("LANGCHAIN_PROJECT", LANGCHAIN_PROJECT)
    os.environ.setdefault("LANGCHAIN_ENDPOINT", LANGCHAIN_ENDPOINT)
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")

# File storage
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", str(BASE_DIR / "uploads"))).resolve(strict=False)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
WORKER_TEMP_DIR = Path(os.getenv("WORKER_TEMP_DIR", str(CACHE_DIR / "worker-temp"))).resolve(strict=False)
WORKER_TEMP_DIR.mkdir(parents=True, exist_ok=True)

# MinIO / S3 object storage (Worker download/upload)
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000").strip()
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin").strip()
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin").strip()
MINIO_SECURE = _env_flag("MINIO_SECURE", False)
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "ocr-files").strip()
WORKER_METRICS_ENABLED = _env_flag("WORKER_METRICS_ENABLED", True)
WORKER_METRICS_HOST = os.getenv("WORKER_METRICS_HOST", "0.0.0.0").strip() or "0.0.0.0"
WORKER_METRICS_PORT = int(os.getenv("WORKER_METRICS_PORT", "9108"))
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
OCR_PREPROCESS_COMPLEXITY_THRESHOLD = float(os.getenv("OCR_PREPROCESS_COMPLEXITY_THRESHOLD", "0.35"))
VISION_ROUTE_COMPLEXITY_THRESHOLD = float(os.getenv("VISION_ROUTE_COMPLEXITY_THRESHOLD", "0.45"))
BOUNDARY_SIMILARITY_THRESHOLD = max(1, int(os.getenv("BOUNDARY_SIMILARITY_THRESHOLD", "12")))
BOUNDARY_GROUP_PDF_OUTPUT_DIRNAME = (
    os.getenv("BOUNDARY_GROUP_PDF_OUTPUT_DIRNAME", "grouped_pdfs").strip() or "grouped_pdfs"
)

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
MINIMAX_API_HOST = os.getenv("MINIMAX_API_HOST", "https://api.minimaxi.com").rstrip("/")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
MINIMAX_MODEL = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")
MINIMAX_TIMEOUT_SECONDS = float(os.getenv("MINIMAX_TIMEOUT_SECONDS", "60"))
MINIMAX_MAX_INPUT_CHARS = int(os.getenv("MINIMAX_MAX_INPUT_CHARS", "12000"))
MINIMAX_BATCH_CONCURRENCY = max(1, int(os.getenv("MINIMAX_BATCH_CONCURRENCY", "20")))
MINIMAX_ENABLED = _env_flag("MINIMAX_ENABLED", bool(MINIMAX_API_KEY.strip()))

# Baidu AI Cloud API (文档解析 PaddleOCR-VL)
BAIDU_API_KEY = os.getenv("BAIDU_API_KEY", "")
BAIDU_SECRET_KEY = os.getenv("BAIDU_SECRET_KEY", "")

# Embedding (RAG vector search)
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", os.getenv("LLM_BASE_URL", "")).strip()
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", os.getenv("LLM_API_KEY", "")).strip()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small").strip()
EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "1024"))
EMBEDDING_BATCH_SIZE = max(1, int(os.getenv("EMBEDDING_BATCH_SIZE", "32")))

# LLM Circuit Breaker
LLM_CB_FAILURE_THRESHOLD = max(1, int(os.getenv("LLM_CB_FAILURE_THRESHOLD", "5")))
LLM_CB_RECOVERY_SECONDS = max(1.0, float(os.getenv("LLM_CB_RECOVERY_SECONDS", "60")))

# LLM Fallback
LLM_FALLBACK_BASE_URL = os.getenv("LLM_FALLBACK_BASE_URL", "").strip()
LLM_FALLBACK_API_KEY = os.getenv("LLM_FALLBACK_API_KEY", "").strip()
LLM_FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "").strip()

# Agent timeouts
PAGE_AGENT_TIMEOUT_SECONDS = float(os.getenv("PAGE_AGENT_TIMEOUT_SECONDS", "120"))
OCR_NODE_TIMEOUT_SECONDS = float(os.getenv("OCR_NODE_TIMEOUT_SECONDS", "90"))

# Structured logging
LOG_FORMAT = _env_choice("LOG_FORMAT", "text", {"text", "json"})

# Local filesystem access
LOCAL_PATH_ROOTS = _build_path_roots(
    os.getenv("LOCAL_PATH_ROOTS", ""),
    defaults=[UPLOAD_DIR, BASE_DIR],
)
