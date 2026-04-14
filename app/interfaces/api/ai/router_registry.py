"""AI document service router registry."""

from fastapi import FastAPI

from app.api.ai_batches import router as ai_batches_router
from app.api.archive_workflow import router as archive_workflow_router
from app.api.evaluation import router as evaluation_router
from app.api.files import router as files_router
from app.api.qa import router as qa_router
from app.api.tasks import router as tasks_router
from app.api.internal.workflow import router as internal_workflow_router


AI_ROUTERS = (
    tasks_router,
    ai_batches_router,
    archive_workflow_router,
    qa_router,
    evaluation_router,
    files_router,
    internal_workflow_router,
)


def include_ai_routers(app: FastAPI) -> None:
    for router in AI_ROUTERS:
        app.include_router(router)
