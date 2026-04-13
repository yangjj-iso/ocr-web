# Archive LangGraph Workflow View

This repository now keeps only the archive workflow defined in Develop.md.

## Endpoints

- `http://127.0.0.1:8123/health/live`
  - Liveness only.

- `http://127.0.0.1:8123/studio/info`
  - Lists the exposed archive graph ids.
  - Expected graphs: `archive_main`, `archive_draft`, `archive_final`, `archive_resume`.

- `http://127.0.0.1:8123/studio/topology`
  - Returns the topology JSON for the archive workflow.

- `http://127.0.0.1:8123/studio/flow`
  - Displays the archive workflow topology page.

## Graph scope

The Studio view visualizes only the Develop.md archive workflow:

- `archive_main`
  - `ingest_batch`
  - `load_policy_snapshot`
  - `preprocess_pages`
  - `run_ocr`
  - `extract_page_features`
  - `analyze_page_relations`
  - `split_documents`
  - `assess_split_risk`
  - `draft_subgraph`
  - `wait_for_review`
  - `resume_subgraph`
  - `final_subgraph`

- `archive_draft`
  - `run_draft_subgraph`
  - `create_review_tasks`
  - `gate_final_subgraph`

- `archive_resume`
  - `resume_from_review`

- `archive_final`
  - `sort_documents_final`
  - `assign_archive_numbers`
  - `extract_metadata_final`
  - `build_catalog_final`
  - `export_searchable_pdf_final`
  - `persist_record_and_index`

## Removed workflows

The old `batch_supervisor`, `page_agent`, and `agent_ocr_workflow.py` based hierarchical OCR workflow have been removed from the repository to keep the codebase aligned with Develop.md only.
