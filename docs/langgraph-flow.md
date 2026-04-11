# LangGraph Workflow View

This document explains the local LangGraph debugging entrypoints for OCR-WEB and, most importantly, where to see the full workflow instead of a health page.

## What each URL is for

- `http://127.0.0.1:8123/health/live`
  - Liveness only.
  - Expected response: `{"status":"ok"}`.
  - This is not the workflow page.

- `http://127.0.0.1:8123/studio/info`
  - Lists the exposed graph ids.
  - Expected graphs: `batch_supervisor`, `page_agent`.

- `http://127.0.0.1:8123/studio/topology`
  - Returns the topology JSON used by the Studio page.
  - Use this when you want to inspect the graph data structure directly.

- `http://127.0.0.1:8123/studio/flow`
  - The actual full workflow page.
  - Shows both the batch-level graph and the page-level graph.

- `http://127.0.0.1:8123/studio/flow?taskId=<taskId>`
  - Same page, but with the real runtime event trace overlaid for one OCR task.
  - The executed nodes and edges are highlighted.

## Workflow scope

The Studio view visualizes two graphs:

- `batch_supervisor`
  - `node_prepare_batch`
  - `node_process_next_page`
  - `node_cross_page_consistency`
  - `node_rag_retrieve`
  - `node_human_router`
  - `node_pending_human_review`
  - `node_pause_for_human_review`
  - `node_final_archiver_and_quality`

- `page_agent`
  - `node_page_plan`
  - `node_ocr`
  - `node_ppocr_vl`
  - `node_evaluate_and_merge`
  - `node_adjust_strategy`
  - `node_finalize_page`

The batch graph calls the page graph from `node_process_next_page`, and the page graph can loop through `node_adjust_strategy -> node_page_plan` when it decides to retry.

## Runtime trace source

The runtime trace shown in `/studio/flow?taskId=<taskId>` is not coming from LangSmith.

It is built from the existing OCR runtime callback chain:

- worker executes the LangGraph workflow
- worker emits node-level events
- control plane stores callback events
- Studio page fetches the stored events and replays them on top of the topology

The node-level events now include:

- `NODE_ENTER`
- `NODE_EXIT`
- `ROUTE_DECISION`

Existing business events such as `PAGE_COMPLETED` and `HUMAN_REVIEW_REQUIRED` are still preserved.

## Start the local Studio service

```powershell
cd D:\OCR_WEB\ocr
powershell -ExecutionPolicy Bypass -File .\scripts\start_langgraph_studio.ps1 -NoBrowser
```

If port `8123` is already occupied, start on another port:

```powershell
cd D:\OCR_WEB\ocr
powershell -ExecutionPolicy Bypass -File .\scripts\start_langgraph_studio.ps1 -Port 8124 -NoBrowser
```

## Related files

- [`D:\OCR_WEB\ocr\app\studio\webapp.py`](/D:/OCR_WEB/ocr/app/studio/webapp.py)
- [`D:\OCR_WEB\ocr\app\studio\workflow_topology.py`](/D:/OCR_WEB/ocr/app/studio/workflow_topology.py)
- [`D:\OCR_WEB\ocr\app\services\agent_ocr_workflow.py`](/D:/OCR_WEB/ocr/app/services/agent_ocr_workflow.py)
- [`D:\OCR_WEB\ocr\langgraph.json`](/D:/OCR_WEB/ocr/langgraph.json)
