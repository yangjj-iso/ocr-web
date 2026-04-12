"""AI document service router registry."""

from fastapi import FastAPI

from app.api.admin_users import operator_router, router as admin_router
from app.api.ai_batches import router as ai_batches_router
from app.api.evaluation import router as evaluation_router
from app.api.files import router as files_router
from app.api.qa import router as qa_router
from app.api.tasks import router as tasks_router
from app.api.worker_metrics import router as worker_metrics_router


AI_ROUTERS = (
    tasks_router,
    ai_batches_router,
    qa_router,
    evaluation_router,
    files_router,
    admin_router,
    operator_router,
    worker_metrics_router,
)


def include_ai_routers(app: FastAPI) -> None:
    for router in AI_ROUTERS:
        app.include_router(router)
