"""LangGraph Studio exports for local debugging via `langgraph dev`."""

from __future__ import annotations

from app.services.agent_ocr_workflow import (
    get_batch_supervisor_graph_for_studio,
    get_page_agent_graph,
)

# Export compiled graphs for LangGraph Studio / local agent server.
batch_supervisor_graph = get_batch_supervisor_graph_for_studio()
page_agent_graph = get_page_agent_graph()
