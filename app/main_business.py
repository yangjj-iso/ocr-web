import logging

import uvicorn

from app.bootstrap import create_service_app
from app.interfaces.api.business import include_business_routers


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


app = create_service_app(
    service_name="business-api",
    title="OCR Business Service",
    description="Business-facing API for auth, archives, and batch administration.",
    version="2.2.0",
    router_loader=include_business_routers,
    start_worker=False,
    preload_vl_pipeline=False,
)


if __name__ == "__main__":
    uvicorn.run("main_business:app", host="0.0.0.0", port=8000, reload=False)
