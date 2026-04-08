import logging

import uvicorn

from app.bootstrap import create_service_app
from app.interfaces.api.ai import include_ai_routers


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


app = create_service_app(
    service_name="ai-document-service",
    title="OCR AI Document Service",
    description="AI-facing API for OCR tasks, document boundary recognition, QA, and evaluation. Heavy OCR execution is delegated to external workers.",
    version="2.2.0",
    router_loader=include_ai_routers,
    start_worker=False,
    preload_vl_pipeline=True,
)


if __name__ == "__main__":
    uvicorn.run("main_ai:app", host="0.0.0.0", port=8001, reload=False)
