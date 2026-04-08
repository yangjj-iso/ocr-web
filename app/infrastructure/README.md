# Infrastructure Layer

The infrastructure layer encapsulates low-level integrations.

Folders:
- `persistence`: database wiring and persistence adapters
- `cache`: cache adapters
- `queue`: queue/worker adapters
- `storage`: file storage/path/security adapters
- `ocr_runtime`: OCR runtime adapters
- `llm_clients`: LLM provider clients

Goal:
- Keep technical dependencies isolated from route and domain code.
