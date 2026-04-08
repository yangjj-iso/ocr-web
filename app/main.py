import logging

import uvicorn

from app.bootstrap import create_service_app
from app.interfaces.api.v1 import include_v1_routers


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


app = create_service_app(
    service_name="ocr-backend-all",
    title="OCR Combined Service",
    description="Combined backend API for business flows and AI document processing.",
    version="2.2.0",
    router_loader=include_v1_routers,
    start_worker=True,
    preload_vl_pipeline=True,
)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
