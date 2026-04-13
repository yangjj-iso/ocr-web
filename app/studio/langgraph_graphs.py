"""LangGraph Studio exports for archive workflow debugging via `langgraph dev`."""

from __future__ import annotations

from app.services.archive_workflow import (
    archive_draft_subgraph as _archive_draft_subgraph,
    archive_final_subgraph as _archive_final_subgraph,
    archive_main_graph as _archive_main_graph,
    archive_resume_subgraph as _archive_resume_subgraph,
)

# Export compiled graphs for LangGraph Studio / local agent server.
archive_main_graph = _archive_main_graph
archive_draft_graph = _archive_draft_subgraph
archive_final_graph = _archive_final_subgraph
archive_resume_graph = _archive_resume_subgraph
