from __future__ import annotations

from fastapi import FastAPI, Request

app = FastAPI(title="OCR-WEB LangGraph Studio")


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/studio/info")
def studio_info(request: Request) -> dict[str, object]:
    recommended_base_url = str(request.base_url).rstrip("/")
    return {
        "service": "ocr-web-langgraph-studio",
        "graphs": ["batch_supervisor", "page_agent"],
        "recommended_base_url": recommended_base_url,
    }
