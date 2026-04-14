from __future__ import annotations

from copy import deepcopy


WORKFLOW_TOPOLOGY_VERSION = "2026-04-13"


_ARCHIVE_MAIN_GRAPH = {
    "id": "archive_main",
    "title": "Archive Main Graph",
    "description": "Develop.md 定义的整卷主流程，负责接入、分件、进入 Draft/Resume/Final 子图。",
    "layout": {"columns": 12, "row_height": 1},
    "nodes": [
        {"id": "__start__", "label": "Start", "kind": "terminal", "column": 0, "row": 0},
        {"id": "ingest_batch", "label": "Ingest Batch", "kind": "process", "column": 1, "row": 0, "subtitle": "接收批次与卷宗上下文"},
        {"id": "load_policy_snapshot", "label": "Load Policy Snapshot", "kind": "process", "column": 2, "row": 0, "subtitle": "加载规则快照"},
        {"id": "preprocess_pages", "label": "Preprocess Pages", "kind": "process", "column": 3, "row": 0, "subtitle": "页面预处理准备"},
        {"id": "run_ocr", "label": "Run OCR", "kind": "process", "column": 4, "row": 0, "subtitle": "OCR 结果进入工作流"},
        {"id": "extract_page_features", "label": "Extract Page Features", "kind": "process", "column": 5, "row": 0, "subtitle": "候选字段 / pHash / 首页得分"},
        {"id": "analyze_page_relations", "label": "Analyze Page Relations", "kind": "process", "column": 6, "row": 0, "subtitle": "相邻页关系与新件信号"},
        {"id": "split_documents", "label": "Split Documents", "kind": "decision", "column": 7, "row": 0, "subtitle": "分件生成草稿件"},
        {"id": "assess_split_risk", "label": "Assess Split Risk", "kind": "warning", "column": 8, "row": 0, "subtitle": "评估边界风险"},
        {"id": "draft_subgraph", "label": "Draft Subgraph", "kind": "process", "column": 9, "row": -1, "subtitle": "草稿著录 / 标签 / 审核任务"},
        {"id": "wait_for_review", "label": "Wait For Review", "kind": "danger", "column": 10, "row": 0, "subtitle": "人工审核中断点"},
        {"id": "resume_subgraph", "label": "Resume Subgraph", "kind": "warning", "column": 9, "row": 1, "subtitle": "审核恢复 / 返工回退"},
        {"id": "final_subgraph", "label": "Final Subgraph", "kind": "success", "column": 11, "row": -1, "subtitle": "正式排序 / 导出 / 入库"},
        {"id": "__end__", "label": "End", "kind": "terminal", "column": 12, "row": -1},
    ],
    "edges": [
        {"source": "__start__", "target": "ingest_batch"},
        {"source": "ingest_batch", "target": "load_policy_snapshot"},
        {"source": "load_policy_snapshot", "target": "preprocess_pages"},
        {"source": "preprocess_pages", "target": "run_ocr"},
        {"source": "run_ocr", "target": "extract_page_features"},
        {"source": "extract_page_features", "target": "analyze_page_relations"},
        {"source": "analyze_page_relations", "target": "split_documents"},
        {"source": "split_documents", "target": "assess_split_risk"},
        {"source": "assess_split_risk", "target": "draft_subgraph", "label": "进入 Draft"},
        {"source": "draft_subgraph", "target": "wait_for_review", "label": "需要审核"},
        {"source": "draft_subgraph", "target": "final_subgraph", "label": "直接进入 Final"},
        {"source": "wait_for_review", "target": "resume_subgraph", "label": "审核完成"},
        {"source": "resume_subgraph", "target": "draft_subgraph", "label": "回退 Draft"},
        {"source": "resume_subgraph", "target": "final_subgraph", "label": "继续 Final"},
        {"source": "final_subgraph", "target": "__end__"},
    ],
    "subgraphs": [
        {"source": "draft_subgraph", "target_graph": "archive_draft", "label": "run draft subgraph", "return_targets": ["wait_for_review", "final_subgraph"]},
        {"source": "resume_subgraph", "target_graph": "archive_resume", "label": "run resume subgraph", "return_targets": ["draft_subgraph", "final_subgraph"]},
        {"source": "final_subgraph", "target_graph": "archive_final", "label": "run final subgraph", "return_targets": ["__end__"]},
    ],
}


_ARCHIVE_DRAFT_GRAPH = {
    "id": "archive_draft",
    "title": "Draft Subgraph",
    "description": "草稿轨：字段提取、标签生成、草稿目录、Draft searchable PDF、审核任务。",
    "layout": {"columns": 4, "row_height": 1},
    "nodes": [
        {"id": "__start__", "label": "Start", "kind": "terminal", "column": 0, "row": 0},
        {"id": "run_draft_subgraph", "label": "Run Draft Subgraph", "kind": "process", "column": 1, "row": 0, "subtitle": "草稿著录与产物生成"},
        {"id": "create_review_tasks", "label": "Create Review Tasks", "kind": "warning", "column": 2, "row": -1, "subtitle": "创建 boundary/metadata/order/final_release"},
        {"id": "gate_final_subgraph", "label": "Gate Final Subgraph", "kind": "decision", "column": 2, "row": 1, "subtitle": "决定进入审核或 Final"},
        {"id": "__end__", "label": "End", "kind": "terminal", "column": 3, "row": 0},
    ],
    "edges": [
        {"source": "__start__", "target": "run_draft_subgraph"},
        {"source": "run_draft_subgraph", "target": "create_review_tasks", "label": "存在阻塞"},
        {"source": "run_draft_subgraph", "target": "gate_final_subgraph", "label": "直接门控"},
        {"source": "create_review_tasks", "target": "__end__", "label": "进入 wait_for_review"},
        {"source": "gate_final_subgraph", "target": "__end__", "label": "进入 wait_for_review / final_subgraph"},
    ],
}


_ARCHIVE_RESUME_GRAPH = {
    "id": "archive_resume",
    "title": "Resume Subgraph",
    "description": "审核恢复与返工重算入口，应用修正并确定最早失效阶段。",
    "layout": {"columns": 3, "row_height": 1},
    "nodes": [
        {"id": "__start__", "label": "Start", "kind": "terminal", "column": 0, "row": 0},
        {"id": "resume_from_review", "label": "Resume From Review", "kind": "warning", "column": 1, "row": 0, "subtitle": "应用字段修正与失效传播"},
        {"id": "__end__", "label": "End", "kind": "terminal", "column": 2, "row": 0},
    ],
    "edges": [
        {"source": "__start__", "target": "resume_from_review"},
        {"source": "resume_from_review", "target": "__end__", "label": "返回 Draft 或 Final"},
    ],
}


_ARCHIVE_FINAL_GRAPH = {
    "id": "archive_final",
    "title": "Final Subgraph",
    "description": "正式轨：排序、编号、正式著录、正式目录、可检索 PDF、正式入库。",
    "layout": {"columns": 8, "row_height": 1},
    "nodes": [
        {"id": "__start__", "label": "Start", "kind": "terminal", "column": 0, "row": 0},
        {"id": "sort_documents_final", "label": "Sort Documents Final", "kind": "process", "column": 1, "row": 0, "subtitle": "件级排序"},
        {"id": "assign_archive_numbers", "label": "Assign Archive Numbers", "kind": "process", "column": 2, "row": 0, "subtitle": "生成正式档号"},
        {"id": "extract_metadata_final", "label": "Extract Metadata Final", "kind": "process", "column": 3, "row": 0, "subtitle": "正式著录"},
        {"id": "build_catalog_final", "label": "Build Catalog Final", "kind": "process", "column": 4, "row": 0, "subtitle": "正式目录"},
        {"id": "export_searchable_pdf_final", "label": "Export Searchable PDF Final", "kind": "success", "column": 5, "row": 0, "subtitle": "正式 PDF 导出"},
        {"id": "persist_record_and_index", "label": "Persist Record And Index", "kind": "success", "column": 6, "row": 0, "subtitle": "入库与索引更新"},
        {"id": "__end__", "label": "End", "kind": "terminal", "column": 7, "row": 0},
    ],
    "edges": [
        {"source": "__start__", "target": "sort_documents_final"},
        {"source": "sort_documents_final", "target": "assign_archive_numbers"},
        {"source": "assign_archive_numbers", "target": "extract_metadata_final"},
        {"source": "extract_metadata_final", "target": "build_catalog_final"},
        {"source": "build_catalog_final", "target": "export_searchable_pdf_final"},
        {"source": "export_searchable_pdf_final", "target": "persist_record_and_index"},
        {"source": "persist_record_and_index", "target": "__end__"},
    ],
}


def workflow_graph_ids() -> list[str]:
    return [
        _ARCHIVE_MAIN_GRAPH["id"],
        _ARCHIVE_DRAFT_GRAPH["id"],
        _ARCHIVE_FINAL_GRAPH["id"],
        _ARCHIVE_RESUME_GRAPH["id"],
    ]


def get_workflow_topology() -> dict[str, object]:
    return {
        "version": WORKFLOW_TOPOLOGY_VERSION,
        "title": "Archive Workflow Topology",
        "graphs": [
            deepcopy(_ARCHIVE_MAIN_GRAPH),
            deepcopy(_ARCHIVE_DRAFT_GRAPH),
            deepcopy(_ARCHIVE_FINAL_GRAPH),
            deepcopy(_ARCHIVE_RESUME_GRAPH),
        ],
        "view": {
            "id": "archive_workflow",
            "title": "Archive Workflow",
            "primary_graph": _ARCHIVE_MAIN_GRAPH["id"],
            "nested_graphs": [
                {"graph_id": _ARCHIVE_DRAFT_GRAPH["id"], "triggered_by": "archive_main:draft_subgraph", "label": "Draft 子图"},
                {"graph_id": _ARCHIVE_RESUME_GRAPH["id"], "triggered_by": "archive_main:resume_subgraph", "label": "Resume 子图"},
                {"graph_id": _ARCHIVE_FINAL_GRAPH["id"], "triggered_by": "archive_main:final_subgraph", "label": "Final 子图"},
            ],
        },
    }
