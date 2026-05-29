# ─── Python base ────────────────────────────────────────────────────
FROM python:3.11-slim AS python-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps for PaddleOCR / image processing / PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxrender1 libxext6 \
    libpq-dev gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config.py ./config.py

# ─── AI Service target ──────────────────────────────────────────────
FROM python-base AS ai-service

EXPOSE 8001

CMD ["uvicorn", "app.main_ai:app", "--host", "0.0.0.0", "--port", "8001"]

# ─── Worker target ──────────────────────────────────────────────────
FROM python-base AS worker

CMD ["python", "-m", "app.main_worker"]
