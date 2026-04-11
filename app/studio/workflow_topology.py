from __future__ import annotations

from copy import deepcopy


WORKFLOW_TOPOLOGY_VERSION = "2026-04-10"


_BATCH_GRAPH = {
    "id": "batch_supervisor",
    "title": "Batch Supervisor",
    "description": (
        "Coordinates the document-level flow: split pages, call the page graph, "
        "run cross-page checks, route for human review when needed, and archive the result."
    ),
    "layout": {"columns": 9, "row_height": 1},
    "nodes": [
        {"id": "__start__", "label": "Start", "kind": "terminal", "column": 0, "row": 0},
        {
            "id": "node_prepare_batch",
            "label": "Prepare Batch",
            "kind": "process",
            "column": 1,
            "row": 0,
            "subtitle": "Split pages and initialize batch state",
        },
        {
            "id": "node_process_next_page",
            "label": "Process Next Page",
            "kind": "process",
            "column": 2,
            "row": 0,
            "subtitle": "Invoke page_agent for each page",
        },
        {
            "id": "node_cross_page_consistency",
            "label": "Cross-page Check",
            "kind": "process",
            "column": 3,
            "row": 0,
            "subtitle": "Merge title, file no, owner, and page-level facts",
        },
        {
            "id": "node_rag_retrieve",
            "label": "RAG Retrieve",
            "kind": "process",
            "column": 4,
            "row": 0,
            "subtitle": "Load related examples and historical context",
        },
        {
            "id": "node_human_router",
            "label": "Human Router",
            "kind": "decision",
            "column": 5,
            "row": 0,
            "subtitle": "Choose auto-approve, pending review, or interrupt",
        },
        {
            "id": "node_pending_human_review",
            "label": "Pending Review",
            "kind": "warning",
            "column": 6,
            "row": -1,
            "subtitle": "Keep the task open with candidate output",
        },
        {
            "id": "node_pause_for_human_review",
            "label": "Pause for Review",
            "kind": "danger",
            "column": 6,
            "row": 1,
            "subtitle": "Interrupt and wait for resume",
        },
        {
            "id": "node_final_archiver_and_quality",
            "label": "Archive and Quality",
            "kind": "success",
            "column": 7,
            "row": 0,
            "subtitle": "Finalize archive payload and quality summary",
        },
        {"id": "__end__", "label": "End", "kind": "terminal", "column": 8, "row": 0},
    ],
    "edges": [
        {"source": "__start__", "target": "node_prepare_batch"},
        {"source": "node_prepare_batch", "target": "node_process_next_page", "label": "has pages"},
        {"source": "node_prepare_batch", "target": "node_cross_page_consistency", "label": "empty batch"},
        {"source": "node_process_next_page", "target": "node_process_next_page", "label": "next page", "kind": "loop"},
        {"source": "node_process_next_page", "target": "node_cross_page_consistency", "label": "all pages done"},
        {"source": "node_process_next_page", "target": "node_pause_for_human_review", "label": "page review required"},
        {"source": "node_cross_page_consistency", "target": "node_rag_retrieve"},
        {"source": "node_rag_retrieve", "target": "node_human_router"},
        {"source": "node_human_router", "target": "node_pending_human_review", "label": "needs review but no interrupt"},
        {"source": "node_human_router", "target": "node_pause_for_human_review", "label": "interrupt for review"},
        {"source": "node_human_router", "target": "node_final_archiver_and_quality", "label": "auto approve"},
        {"source": "node_pending_human_review", "target": "node_final_archiver_and_quality", "label": "keep candidate output"},
        {"source": "node_pause_for_human_review", "target": "node_process_next_page", "label": "resume page flow"},
        {"source": "node_pause_for_human_review", "target": "node_cross_page_consistency", "label": "resume batch flow"},
        {"source": "node_pause_for_human_review", "target": "node_final_archiver_and_quality", "label": "resume finalization"},
        {"source": "node_final_archiver_and_quality", "target": "__end__"},
    ],
    "subgraphs": [
        {
            "source": "node_process_next_page",
            "target_graph": "page_agent",
            "label": "call page_agent",
            "return_targets": [
                "node_process_next_page",
                "node_cross_page_consistency",
                "node_pause_for_human_review",
            ],
        }
    ],
}


_PAGE_GRAPH = {
    "id": "page_agent",
    "title": "Page Agent",
    "description": (
        "Handles page-level planning, OCR/VL execution, evaluation, retry decisions, "
        "and page finalization."
    ),
    "layout": {"columns": 7, "row_height": 1},
    "nodes": [
        {"id": "__start__", "label": "Start", "kind": "terminal", "column": 0, "row": 0},
        {
            "id": "node_page_plan",
            "label": "Page Plan",
            "kind": "process",
            "column": 1,
            "row": 0,
            "subtitle": "Estimate complexity and choose a strategy",
        },
        {
            "id": "node_ocr",
            "label": "OCR",
            "kind": "process",
            "column": 2,
            "row": 0,
            "subtitle": "Run the classic OCR path",
        },
        {
            "id": "node_ppocr_vl",
            "label": "Vision Model",
            "kind": "process",
            "column": 3,
            "row": 0,
            "subtitle": "Run PP-OCR-VL or Baidu VL",
        },
        {
            "id": "node_evaluate_and_merge",
            "label": "Evaluate and Merge",
            "kind": "decision",
            "column": 4,
            "row": 0,
            "subtitle": "Score output, merge signals, decide next step",
        },
        {
            "id": "node_adjust_strategy",
            "label": "Adjust Strategy",
            "kind": "danger",
            "column": 4,
            "row": 1,
            "subtitle": "Change preprocessing or retry policy",
        },
        {
            "id": "node_finalize_page",
            "label": "Finalize Page",
            "kind": "success",
            "column": 5,
            "row": 0,
            "subtitle": "Return page_output",
        },
        {"id": "__end__", "label": "End", "kind": "terminal", "column": 6, "row": 0},
    ],
    "edges": [
        {"source": "__start__", "target": "node_page_plan"},
        {"source": "node_page_plan", "target": "node_ocr"},
        {"source": "node_ocr", "target": "node_ppocr_vl", "label": "need second path"},
        {"source": "node_ocr", "target": "node_evaluate_and_merge", "label": "skip second path"},
        {"source": "node_ppocr_vl", "target": "node_evaluate_and_merge"},
        {"source": "node_evaluate_and_merge", "target": "node_adjust_strategy", "label": "quality not enough"},
        {"source": "node_evaluate_and_merge", "target": "node_finalize_page", "label": "pass"},
        {"source": "node_adjust_strategy", "target": "node_page_plan", "label": "retry", "kind": "loop"},
        {"source": "node_finalize_page", "target": "__end__"},
    ],
}


def workflow_graph_ids() -> list[str]:
    return [_BATCH_GRAPH["id"], _PAGE_GRAPH["id"]]


def get_workflow_topology() -> dict[str, object]:
    return {
        "version": WORKFLOW_TOPOLOGY_VERSION,
        "title": "OCR Full Workflow",
        "graphs": [deepcopy(_BATCH_GRAPH), deepcopy(_PAGE_GRAPH)],
        "view": {
            "id": "ocr_full_workflow",
            "title": "OCR Full Workflow Topology",
            "primary_graph": _BATCH_GRAPH["id"],
            "nested_graphs": [
                {
                    "graph_id": _PAGE_GRAPH["id"],
                    "triggered_by": f"{_BATCH_GRAPH['id']}:node_process_next_page",
                    "label": "node_process_next_page calls page_agent",
                }
            ],
        },
    }
