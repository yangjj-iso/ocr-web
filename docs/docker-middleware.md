# Docker Middleware for Local OCR Development

This repository now includes a Docker-based middleware stack for local Windows development.

## Files added

- `compose.middleware.yaml`
- `.env.docker`
- `scripts/dev-middleware.ps1`

## Host data layout

All runtime data stays inside the project on `D:`:

- `D:\OCR_WEB\ocr\docker-data\postgres`
- `D:\OCR_WEB\ocr\docker-data\rabbitmq`
- `D:\OCR_WEB\ocr\docker-data\redis`
- `D:\OCR_WEB\ocr\docker-data\minio\data`

The existing native installs under `D:\postgresql`, `D:\RabbitMQ`, `D:\Redis`, and `D:\MinIO` are intentionally left untouched for rollback.

## What the stack contains

- PostgreSQL 17
- RabbitMQ 4.x Management
- Redis 7
- MinIO

MinIO bucket bootstrap is handled by the `minio-init` setup profile and creates `ocr-source` if it does not exist.

## Recommended workflow

Validate the compose file first:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-middleware.ps1 -Action Validate
```

Start the full middleware stack and stop the known native PostgreSQL and RabbitMQ services first:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-middleware.ps1 -Action Up -StopLocalServices
```

Run that command from an elevated PowerShell session if local Windows `RabbitMQ` is installed. The script now stops the service and disables its startup so Docker can own `5672/15672`.

Inspect current status:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-middleware.ps1 -Action Status
```

Stop containers but keep data:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-middleware.ps1 -Action Down
```

Stop containers and remove Docker volumes for a clean reset:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\dev-middleware.ps1 -Action Down -DestroyData
```

## Effective local endpoints

- PostgreSQL: `127.0.0.1:5432`
- RabbitMQ AMQP: `127.0.0.1:5672`
- RabbitMQ UI: `http://127.0.0.1:15672`
- Redis: `127.0.0.1:6379`
- MinIO API: `http://127.0.0.1:9000`
- MinIO Console: `http://127.0.0.1:9001`

## Default local credentials

- PostgreSQL: `postgres / 123456`
- RabbitMQ: `ocr_admin / ocr_password123`
- MinIO: `admin / admin123456`

## App-facing environment values

The Docker stack intentionally keeps the same local defaults already used by the codebase, so most app processes do not need code changes when native services are stopped and Docker takes over the default ports.

Key values are declared in `.env.docker`:

```text
DATABASE_URL=postgresql+asyncpg://postgres:123456@127.0.0.1:5432/ocr_db
REDIS_URL=redis://127.0.0.1:6379/0
MQ_BROKER_URL=amqp://ocr_admin:ocr_password123@127.0.0.1:5672/%2F
CELERY_BROKER_URL=amqp://ocr_admin:ocr_password123@127.0.0.1:5672/%2F
OCR_STORAGE_ENDPOINT=http://127.0.0.1:9000
OCR_STORAGE_BUCKET=ocr-source
OCR_STORAGE_ACCESS_KEY=admin
OCR_STORAGE_SECRET_KEY=admin123456
```

## Notes

- `scripts/dev-middleware.ps1` now fails fast when the local Windows `RabbitMQ` service is still running or when host-side `127.0.0.1:15672` does not authenticate as the Docker user.
- `-StopLocalServices` only stops the known native PostgreSQL and RabbitMQ Windows services plus local Redis/MinIO processes when they are the direct port owners.
- Docker Desktop must run Linux containers. The script attempts to start Docker Desktop automatically if the daemon is not ready.
