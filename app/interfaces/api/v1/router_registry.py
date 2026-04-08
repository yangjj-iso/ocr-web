"""V1 router registry.

This combined registry keeps the legacy single-process deployment available
while the runtime is being split into separate business and AI services.
"""

from fastapi import FastAPI

from app.interfaces.api.ai import include_ai_routers
from app.interfaces.api.business import include_business_routers


def include_v1_routers(app: FastAPI) -> None:
    """Attach all public v1 routers to the FastAPI app."""
    include_business_routers(app)
    include_ai_routers(app)
