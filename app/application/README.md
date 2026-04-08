# Application Layer

The application layer orchestrates cross-domain business flows.

Rules:
- No direct HTTP handling here.
- No direct low-level SDK calls here.
- Compose domain services into use-case workflows.

Current workflows:
- `workflows/tasks.py`: upload/path submit, queue submit, delete with cache context, edit orchestration.
- `workflows/batches.py`: batch scan, batch binding, task-level AI extraction, batch merge extraction.
- `workflows/archives.py`: archive list/export/import/delete orchestration.
- `workflows/qa.py`: batch QA ask/history/feedback/metrics orchestration.
- `workflows/evaluation.py`: truth/metrics/report orchestration.
