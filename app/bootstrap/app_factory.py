from __future__ import annotations

import logging
import sys
import traceback
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.db.database import init_db
from config import (
    CORS_ALLOW_ORIGINS,
    DATABASE_URL,
    MINIMAX_API_KEY,
    MINIMAX_BASE_URL,
    MINIMAX_ENABLED,
    MINIMAX_MODEL,
    MQ_BROKER_URL,
    OCR_VL_BACKEND,
    REDIS_URL,
    _mask_secret,
)


logger = logging.getLogger(__name__)


async def _check_dependencies() -> dict:
    """Check connectivity to database, RabbitMQ, and Redis."""
    checks: dict = {}

    # Database
    try:
        from sqlalchemy import text
        from app.db.database import async_session
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = {"status": "up"}
    except Exception as exc:
        checks["database"] = {"status": "down", "error": str(exc)[:200]}

    # RabbitMQ
    try:
        import socket as _socket
        from urllib.parse import urlparse
        parsed = urlparse(MQ_BROKER_URL.replace("amqp://", "http://"))
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 5672
        sock = _socket.create_connection((host, port), timeout=3)
        sock.close()
        checks["rabbitmq"] = {"status": "up"}
    except Exception as exc:
        checks["rabbitmq"] = {"status": "down", "error": str(exc)[:200]}

    # Redis
    try:
        import aiohttp
        from urllib.parse import urlparse
        parsed = urlparse(REDIS_URL)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 6379
        import socket as _socket
        sock = _socket.create_connection((host, port), timeout=3)
        sock.close()
        checks["redis"] = {"status": "up"}
    except ImportError:
        checks["redis"] = {"status": "unknown", "error": "aiohttp not installed"}
    except Exception as exc:
        checks["redis"] = {"status": "down", "error": str(exc)[:200]}

    return checks


def create_service_app(
    *,
    service_name: str,
    title: str,
    description: str,
    version: str,
    router_loader: Callable[[FastAPI], None],
    start_worker: bool,
    preload_vl_pipeline: bool,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        logger.info("Starting service bootstrap for %s...", service_name)
        logger.info(
            "Python runtime: executable=%s, prefix=%s, base_prefix=%s",
            sys.executable,
            sys.prefix,
            sys.base_prefix,
        )
        logger.info(
            "MiniMax config: enabled=%s, base_url=%s, model=%s, api_key=%s",
            MINIMAX_ENABLED,
            MINIMAX_BASE_URL,
            MINIMAX_MODEL,
            _mask_secret(MINIMAX_API_KEY),
        )
        logger.info("Startup checkpoint: init_db begin")
        await init_db()
        logger.info("Startup checkpoint: init_db complete")
        if preload_vl_pipeline and OCR_VL_BACKEND == "local":
            logger.info("Startup checkpoint: vl pipeline preload begin")
            from app.core.ocr_engine import get_vl_pipeline

            get_vl_pipeline()
            logger.info("Startup checkpoint: vl pipeline preload complete")
        else:
            logger.info(
                "Startup checkpoint: vl pipeline preload skipped (service=%s, OCR_VL_BACKEND=%s)",
                service_name,
                OCR_VL_BACKEND,
            )

        if start_worker:
            logger.warning(
                "Startup checkpoint: in-process task worker has been retired. "
                "Use RabbitMQ producer + app/main_worker.py or Celery worker for compute tasks."
            )
        else:
            logger.info("Startup checkpoint: task worker skipped for service=%s", service_name)

        logger.info("Service is ready: %s", service_name)
        try:
            yield
        finally:
            logger.info("Initiating graceful shutdown for %s ...", service_name)
            try:
                from app.db.database import engine
                if engine is not None:
                    await engine.dispose()
                    logger.info("Database connection pool disposed.")
            except Exception:
                logger.debug("Database cleanup skipped.", exc_info=True)
            logger.info("Service shutdown complete: %s", service_name)

    app = FastAPI(
        title=title,
        description=description,
        version=version,
        lifespan=lifespan,
    )

    if CORS_ALLOW_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(CORS_ALLOW_ORIGINS),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    router_loader(app)

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        traceback_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        logger.error("Unhandled exception on %s:\n%s", request.url.path, "".join(traceback_lines))
        return JSONResponse(status_code=500, content={"detail": "Internal server error."})

    @app.get("/api/health")
    async def health():
        checks = await _check_dependencies()
        overall = "ok" if all(c["status"] == "up" for c in checks.values()) else "degraded"
        return {"status": overall, "service": service_name, "components": checks}

    @app.get("/health/live")
    async def health_live():
        return {"status": "up", "service": service_name}

    @app.get("/health/ready")
    async def health_ready():
        checks = await _check_dependencies()
        if all(c["status"] == "up" for c in checks.values()):
            return {"status": "up", "service": service_name, "components": checks}
        from fastapi.responses import JSONResponse as _JSONResponse
        return _JSONResponse(
            status_code=503,
            content={"status": "not_ready", "service": service_name, "components": checks},
        )

    @app.get("/")
    async def api_root():
        return {
            "service": service_name,
            "docs": "/docs",
            "health": "/api/health",
            "live": "/health/live",
            "ready": "/health/ready",
        }

    return app


__all__ = ["create_service_app"]
