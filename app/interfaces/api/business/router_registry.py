"""Business service router registry."""

from fastapi import FastAPI

from app.api.archives import router as archives_router
from app.api.auth_routes import router as auth_router
from app.api.business_batches import router as business_batches_router


BUSINESS_ROUTERS = (
    auth_router,
    archives_router,
    business_batches_router,
)


def include_business_routers(app: FastAPI) -> None:
    for router in BUSINESS_ROUTERS:
        app.include_router(router)
