from __future__ import annotations

import json

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.studio.workflow_topology import get_workflow_topology, workflow_graph_ids
from config import CONTROL_PLANE_BASE_URL, CONTROL_PLANE_INTERNAL_TOKEN, CONTROL_PLANE_VERIFY_TLS


app = FastAPI(title="OCR-WEB LangGraph Studio")


FLOW_PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>OCR Workflow Studio</title>
</head>
<body>
__FLOW_BODY__
</body>
</html>
"""


FLOW_BODY_TEMPLATE = """
<style>
  :root {
    --bg: #f3f6fb;
    --card: rgba(255, 255, 255, 0.96);
    --line: #d3ddea;
    --text: #102038;
    --muted: #5f738d;
    --primary: #2254f4;
    --primary-soft: rgba(34, 84, 244, 0.12);
    --success: #178d51;
    --warning: #c97b07;
    --danger: #cf4250;
    --shadow: 0 20px 42px rgba(15, 23, 42, 0.08);
    --radius: 18px;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    color: var(--text);
    background:
      radial-gradient(circle at top left, rgba(34, 84, 244, 0.12), transparent 32%),
      radial-gradient(circle at top right, rgba(23, 141, 81, 0.10), transparent 24%),
      linear-gradient(180deg, #f7fbff 0%, var(--bg) 100%);
  }
  code {
    padding: 2px 6px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.06);
    font-family: Consolas, monospace;
  }
  .page {
    width: min(1500px, calc(100vw - 40px));
    margin: 24px auto 40px;
    display: grid;
    gap: 20px;
  }
  .hero, .panel {
    background: var(--card);
    backdrop-filter: blur(16px);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
  }
  .hero {
    padding: 26px 30px;
    display: grid;
    gap: 14px;
  }
  .hero h1, .panel h2 {
    margin: 0;
  }
  .hero h1 {
    font-size: 32px;
    line-height: 1.12;
  }
  .hero p, .panel p {
    margin: 0;
    color: var(--muted);
    line-height: 1.6;
  }
  .meta, .legend, .status-line {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .chip, .status-pill, .graph-badge, .event-type {
    display: inline-flex;
    align-items: center;
    padding: 8px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 700;
  }
  .chip, .graph-badge, .event-type {
    background: var(--primary-soft);
    color: var(--primary);
  }
  .status-pill {
    background: rgba(15, 23, 42, 0.06);
    color: var(--text);
  }
  .status-pill.ok {
    background: rgba(23, 141, 81, 0.12);
    color: var(--success);
  }
  .status-pill.warn {
    background: rgba(201, 123, 7, 0.12);
    color: var(--warning);
  }
  .status-pill.danger {
    background: rgba(207, 66, 80, 0.12);
    color: var(--danger);
  }
  .panel {
    padding: 22px 24px 24px;
  }
  .workflow-layout {
    display: grid;
    grid-template-columns: minmax(0, 1.85fr) minmax(340px, 0.95fr);
    gap: 20px;
    align-items: start;
  }
  .graph-stack, .timeline-panel, .task-form, .status-box, .timeline {
    display: grid;
    gap: 16px;
  }
  .timeline-panel {
    position: sticky;
    top: 20px;
  }
  .graph-card, .control-box {
    padding: 18px;
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.22);
    background: linear-gradient(180deg, rgba(255,255,255,0.97), rgba(248,250,252,0.97));
  }
  .graph-head, .event-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    align-items: flex-start;
  }
  .graph-head {
    margin-bottom: 14px;
  }
  .graph-head h3, .control-box h3 {
    margin: 0 0 6px;
    font-size: 18px;
  }
  .graph-head p, .control-box p {
    margin: 0;
    font-size: 13px;
  }
  .graph-canvas {
    position: relative;
    overflow: auto;
    padding: 12px;
    border-radius: 14px;
    background:
      linear-gradient(180deg, rgba(248, 250, 252, 0.85), rgba(241, 245, 249, 0.94)),
      linear-gradient(90deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px),
      linear-gradient(0deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px);
    background-size: auto, 32px 32px, 32px 32px;
    border: 1px solid rgba(148, 163, 184, 0.18);
  }
  .graph-board {
    position: relative;
    min-width: 100%;
    min-height: 320px;
  }
  .graph-svg {
    position: absolute;
    inset: 0;
    overflow: visible;
    pointer-events: none;
  }
  .graph-node {
    position: absolute;
    width: 176px;
    min-height: 90px;
    padding: 14px 14px 12px;
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.28);
    background: rgba(255,255,255,0.97);
    box-shadow: 0 10px 24px rgba(15, 23, 42, 0.08);
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, background 0.18s ease;
  }
  .graph-node.kind-terminal { background: #f8fafc; }
  .graph-node.kind-process { background: #eef4ff; }
  .graph-node.kind-decision { background: #fff7e8; }
  .graph-node.kind-warning { background: #fff8e6; }
  .graph-node.kind-danger { background: #fff1f0; }
  .graph-node.kind-success { background: #eefdf2; }
  .graph-node.executed {
    border-color: rgba(34, 84, 244, 0.64);
    box-shadow: 0 18px 32px rgba(34, 84, 244, 0.16);
  }
  .graph-node.active {
    transform: translateY(-4px) scale(1.02);
    border-color: var(--primary);
    box-shadow: 0 24px 40px rgba(34, 84, 244, 0.24);
    background: #f6f9ff;
  }
  .graph-node h4 {
    margin: 0 0 6px;
    font-size: 16px;
  }
  .graph-node .node-id {
    display: inline-flex;
    margin-bottom: 8px;
    padding: 4px 8px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.06);
    color: var(--muted);
    font-size: 12px;
    font-family: Consolas, monospace;
  }
  .graph-node p, .event-summary, .timeline-empty, .timeline-error {
    font-size: 13px;
    line-height: 1.55;
  }
  .edge {
    fill: none;
    stroke: rgba(71, 85, 105, 0.42);
    stroke-width: 2.2;
    stroke-linecap: round;
    stroke-linejoin: round;
    transition: stroke 0.18s ease, stroke-width 0.18s ease;
  }
  .edge.executed {
    stroke: rgba(34, 84, 244, 0.54);
  }
  .edge.active {
    stroke: var(--primary);
    stroke-width: 3.2;
  }
  .edge-label {
    position: absolute;
    padding: 4px 8px;
    border-radius: 999px;
    background: rgba(255,255,255,0.95);
    border: 1px solid rgba(148, 163, 184, 0.2);
    color: var(--muted);
    font-size: 11px;
    font-weight: 600;
    transform: translate(-50%, -50%);
    white-space: nowrap;
    pointer-events: none;
  }
  .nested-callout, .timeline-empty, .timeline-error {
    padding: 14px;
    border-radius: 14px;
    border: 1px dashed rgba(148, 163, 184, 0.3);
    background: rgba(255,255,255,0.96);
    color: var(--muted);
  }
  .nested-callout {
    margin-top: 12px;
    border-color: rgba(34, 84, 244, 0.28);
    background: rgba(34, 84, 244, 0.06);
    color: #2a4db5;
    font-size: 13px;
  }
  .timeline-error {
    color: var(--danger);
    border-color: rgba(207, 66, 80, 0.32);
    background: rgba(255, 241, 240, 0.92);
  }
  .task-row {
    display: flex;
    gap: 10px;
  }
  .task-row input {
    flex: 1;
    height: 42px;
    border-radius: 12px;
    border: 1px solid rgba(148, 163, 184, 0.24);
    padding: 0 14px;
    font-size: 14px;
    background: rgba(255,255,255,0.98);
  }
  .task-row button {
    height: 42px;
    border: 0;
    border-radius: 12px;
    padding: 0 14px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 700;
    transition: transform 0.18s ease, box-shadow 0.18s ease;
  }
  .task-row button:hover {
    transform: translateY(-1px);
  }
  .btn-primary {
    color: #fff;
    background: linear-gradient(135deg, #2254f4, #4f7bff);
    box-shadow: 0 12px 24px rgba(34, 84, 244, 0.24);
  }
  .btn-secondary {
    color: var(--text);
    background: rgba(15, 23, 42, 0.06);
  }
  .summary-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
  .summary-item {
    padding: 12px;
    border-radius: 12px;
    background: rgba(255,255,255,0.95);
    border: 1px solid rgba(148, 163, 184, 0.18);
  }
  .summary-item strong {
    display: block;
    font-size: 18px;
    margin-bottom: 4px;
  }
  .summary-item span, .event-meta, .muted {
    color: var(--muted);
    font-size: 12px;
  }
  .legend span {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--muted);
  }
  .legend i {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 999px;
  }
  .event-card {
    padding: 14px;
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.18);
    background: rgba(255,255,255,0.96);
    cursor: pointer;
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
  }
  .event-card:hover {
    transform: translateY(-1px);
    box-shadow: 0 16px 28px rgba(15, 23, 42, 0.08);
  }
  .event-card.active {
    border-color: rgba(34, 84, 244, 0.54);
    box-shadow: 0 18px 30px rgba(34, 84, 244, 0.16);
    background: #f7faff;
  }
  .event-title {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
  }
  .empty-note {
    margin-top: 6px;
    font-size: 13px;
    color: var(--muted);
  }
  @media (max-width: 1180px) {
    .workflow-layout { grid-template-columns: 1fr; }
    .timeline-panel { position: static; }
  }
</style>

<div class="page">
  <section class="hero">
    <div class="meta">
      <span class="chip">LangGraph Studio</span>
      <span class="chip">Full topology</span>
      <span class="chip">Task trace replay</span>
    </div>
    <div>
      <h1>OCR full workflow graph</h1>
      <p>
        This page shows the complete <code>batch_supervisor</code> and <code>page_agent</code>
        graphs, plus the real runtime trace of a task when you provide <code>taskId</code>.
      </p>
    </div>
    <div class="status-line">
      <span class="status-pill ok">/studio/flow is the workflow view</span>
      <span class="status-pill">/health/live is only a liveness check</span>
      <span class="status-pill">control plane base: __CONTROL_PLANE_BASE_URL__</span>
    </div>
  </section>

  <section class="panel">
    <h2>Topology and runtime trace</h2>
    <p>
      Open this page without parameters to inspect the complete graph, or use
      <code>?taskId=123</code> to overlay the real event timeline for a task.
    </p>

    <div class="workflow-layout">
      <div class="graph-stack" id="graphMount"></div>

      <aside class="timeline-panel">
        <div class="control-box">
          <h3>Load task trace</h3>
          <p>
            Enter a task id to fetch workflow events from the control plane and highlight
            the executed nodes and edges.
          </p>
          <form class="task-form" id="taskForm">
            <div class="task-row">
              <input id="taskIdInput" type="text" inputmode="numeric" placeholder="Example: 42" value="__REQUESTED_TASK_ID__" />
              <button type="submit" class="btn-primary">Load trace</button>
              <button type="button" id="clearSelection" class="btn-secondary">Clear</button>
            </div>
          </form>
          <div class="status-box">
            <div class="status-line">
              <span class="status-pill" id="taskStatusPill">Topology only</span>
              <span class="status-pill" id="threadStatusPill">no thread</span>
            </div>
            <div class="summary-grid" id="summaryGrid">
              <div class="summary-item"><strong>0</strong><span>events</span></div>
              <div class="summary-item"><strong>0</strong><span>executed nodes</span></div>
            </div>
            <div class="legend">
              <span><i style="background:#2254f4;"></i>active step</span>
              <span><i style="background:rgba(34, 84, 244, 0.45);"></i>executed path</span>
              <span><i style="background:#fff7e8;"></i>decision node</span>
              <span><i style="background:#eefdf2;"></i>success node</span>
            </div>
          </div>
        </div>

        <div class="control-box">
          <h3>Timeline</h3>
          <p>Click an event to focus the corresponding node or route on the graph.</p>
          <div class="timeline" id="timelineMount">
            <div class="timeline-empty">
              Add a <code>taskId</code> to replay a real OCR task trace here.
            </div>
          </div>
        </div>
      </aside>
    </div>
  </section>
</div>

__FLOW_SCRIPT__
"""


FLOW_SCRIPT_TEMPLATE = """
<script>
  const TOPOLOGY = __TOPOLOGY_JSON__;
  const INITIAL_TASK_ID = __REQUESTED_TASK_ID_JSON__;

  const graphNodeRefs = new Map();
  const edgeRefs = new Map();
  let currentWorkflow = null;
  let activeEventIndex = -1;

  function graphKey(graphId, nodeId) {
    return `${graphId}:${nodeId}`;
  }

  function edgeKey(graphId, source, target) {
    return `${graphId}:${source}->${target}`;
  }

  function createElement(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (typeof text === "string") node.textContent = text;
    return node;
  }

  function ensureArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function formatTime(value) {
    if (!value) return "n/a";
    try {
      return new Date(value).toLocaleString();
    } catch (error) {
      return String(value);
    }
  }

  function summarizeEvent(event) {
    const payload = event.payload || {};
    const summary = payload.summary || payload.decision || payload.note || payload.message;
    if (summary) return String(summary);
    if (event.eventType === "NODE_ENTER") return "Entered node.";
    if (event.eventType === "NODE_EXIT") return "Finished node.";
    if (event.eventType === "ROUTE_DECISION") return "Evaluated route decision.";
    if (event.eventType === "PAGE_COMPLETED") return "Completed one page.";
    if (event.eventType === "HUMAN_REVIEW_REQUIRED") return "Raised human review requirement.";
    return "Workflow event.";
  }

  function compactPayload(payload) {
    const pageNo = payload.page_no || payload.pageNo;
    const retryCount = payload.retry_count || payload.retryCount;
    const graphId = payload.graph_id || payload.graphId;
    const nodeId = payload.node_id || payload.nodeId;
    const fromNode = payload.from_node || payload.fromNode;
    const toNode = payload.to_node || payload.toNode;
    const parts = [];
    if (graphId && nodeId) parts.push(`${graphId}.${nodeId}`);
    if (graphId && fromNode && toNode) parts.push(`${graphId}: ${fromNode} -> ${toNode}`);
    if (pageNo !== undefined && pageNo !== null) parts.push(`page ${pageNo}`);
    if (retryCount !== undefined && retryCount !== null) parts.push(`retry ${retryCount}`);
    return parts.join(" | ");
  }

  function drawEdge(svg, graphId, edge, nodePositions) {
    const source = nodePositions[edge.source];
    const target = nodePositions[edge.target];
    if (!source || !target) return null;

    const startX = source.x + source.width;
    const startY = source.y + source.height / 2;
    const endX = target.x;
    const endY = target.y + target.height / 2;

    let pathData = "";
    let labelX = (startX + endX) / 2;
    let labelY = (startY + endY) / 2 - 12;

    if (edge.source === edge.target || edge.kind === "loop") {
      const loopX = source.x + source.width / 2;
      const loopTop = source.y - 64;
      pathData = [
        `M ${loopX} ${source.y}`,
        `C ${loopX + 70} ${loopTop}, ${loopX - 70} ${loopTop}, ${loopX} ${source.y}`
      ].join(" ");
      labelX = loopX;
      labelY = loopTop - 8;
    } else {
      const delta = Math.max(80, Math.abs(endX - startX) / 2);
      pathData = [
        `M ${startX} ${startY}`,
        `C ${startX + delta} ${startY}, ${endX - delta} ${endY}, ${endX} ${endY}`
      ].join(" ");
    }

    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", pathData);
    path.setAttribute("class", "edge");
    path.setAttribute("marker-end", "url(#arrowhead)");
    svg.appendChild(path);
    edgeRefs.set(edgeKey(graphId, edge.source, edge.target), path);

    return { labelX, labelY };
  }

  function renderGraphs() {
    const mount = document.getElementById("graphMount");
    mount.innerHTML = "";
    graphNodeRefs.clear();
    edgeRefs.clear();

    const graphs = ensureArray(TOPOLOGY.graphs);
    graphs.forEach((graph) => {
      const card = createElement("section", "graph-card");
      const head = createElement("div", "graph-head");
      const left = createElement("div");
      left.appendChild(createElement("h3", "", graph.title));
      left.appendChild(createElement("p", "", graph.description || ""));
      head.appendChild(left);
      head.appendChild(createElement("span", "graph-badge", graph.id));
      card.appendChild(head);

      const canvas = createElement("div", "graph-canvas");
      const board = createElement("div", "graph-board");
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("class", "graph-svg");
      board.appendChild(svg);

      const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
      const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
      marker.setAttribute("id", "arrowhead");
      marker.setAttribute("markerWidth", "10");
      marker.setAttribute("markerHeight", "8");
      marker.setAttribute("refX", "8");
      marker.setAttribute("refY", "4");
      marker.setAttribute("orient", "auto");
      const arrowPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
      arrowPath.setAttribute("d", "M 0 0 L 10 4 L 0 8 z");
      arrowPath.setAttribute("fill", "rgba(71, 85, 105, 0.55)");
      marker.appendChild(arrowPath);
      defs.appendChild(marker);
      svg.appendChild(defs);

      const nodePositions = {};
      const columnWidth = 220;
      const rowHeight = 170;
      const nodeWidth = 176;
      const nodeHeight = 96;
      const baseX = 30;
      const baseY = 36;
      const minRow = Math.min(...ensureArray(graph.nodes).map((node) => node.row || 0));
      const maxRow = Math.max(...ensureArray(graph.nodes).map((node) => node.row || 0));
      const width = (graph.layout?.columns || 6) * columnWidth + 140;
      const height = (maxRow - minRow + 1) * rowHeight + 140;
      board.style.width = `${width}px`;
      board.style.height = `${height}px`;
      svg.setAttribute("width", String(width));
      svg.setAttribute("height", String(height));

      ensureArray(graph.nodes).forEach((node) => {
        const x = baseX + (node.column || 0) * columnWidth;
        const y = baseY + ((node.row || 0) - minRow) * rowHeight;
        nodePositions[node.id] = { x, y, width: nodeWidth, height: nodeHeight };

        const box = createElement("article", `graph-node kind-${node.kind || "process"}`);
        box.style.left = `${x}px`;
        box.style.top = `${y}px`;
        box.appendChild(createElement("div", "node-id", node.id));
        box.appendChild(createElement("h4", "", node.label || node.id));
        if (node.subtitle) box.appendChild(createElement("p", "", node.subtitle));
        board.appendChild(box);
        graphNodeRefs.set(graphKey(graph.id, node.id), box);
      });

      ensureArray(graph.edges).forEach((edge) => {
        const info = drawEdge(svg, graph.id, edge, nodePositions);
        if (info && edge.label) {
          const label = createElement("div", "edge-label", edge.label);
          label.style.left = `${info.labelX}px`;
          label.style.top = `${info.labelY}px`;
          board.appendChild(label);
        }
      });

      canvas.appendChild(board);
      card.appendChild(canvas);

      ensureArray(graph.subgraphs).forEach((subgraph) => {
        const callout = createElement(
          "div",
          "nested-callout",
          `${graph.id}.${subgraph.source} calls ${subgraph.target_graph}. The batch flow continues after the page graph returns.`
        );
        card.appendChild(callout);
      });

      mount.appendChild(card);
    });
  }

  function applyWorkflowHighlight() {
    graphNodeRefs.forEach((node) => node.classList.remove("executed", "active"));
    edgeRefs.forEach((edge) => edge.classList.remove("executed", "active"));
    if (!currentWorkflow || !Array.isArray(currentWorkflow.events)) return;

    const executedNodeKeys = new Set();
    const executedEdgeKeys = new Set();

    currentWorkflow.events.forEach((event) => {
      const payload = event.payload || {};
      const graphId = payload.graph_id || payload.graphId;
      const nodeId = payload.node_id || payload.nodeId;
      const fromNode = payload.from_node || payload.fromNode;
      const toNode = payload.to_node || payload.toNode;
      if (graphId && nodeId) {
        executedNodeKeys.add(graphKey(graphId, nodeId));
      }
      if (graphId && fromNode && toNode) {
        executedEdgeKeys.add(edgeKey(graphId, fromNode, toNode));
        executedNodeKeys.add(graphKey(graphId, fromNode));
        executedNodeKeys.add(graphKey(graphId, toNode));
      }
    });

    executedNodeKeys.forEach((key) => graphNodeRefs.get(key)?.classList.add("executed"));
    executedEdgeKeys.forEach((key) => edgeRefs.get(key)?.classList.add("executed"));

    if (activeEventIndex < 0 || activeEventIndex >= currentWorkflow.events.length) return;
    const activeEvent = currentWorkflow.events[activeEventIndex];
    const payload = activeEvent.payload || {};
    const graphId = payload.graph_id || payload.graphId;
    const nodeId = payload.node_id || payload.nodeId;
    const fromNode = payload.from_node || payload.fromNode;
    const toNode = payload.to_node || payload.toNode;

    if (graphId && nodeId) {
      graphNodeRefs.get(graphKey(graphId, nodeId))?.classList.add("active");
    }
    if (graphId && fromNode && toNode) {
      graphNodeRefs.get(graphKey(graphId, fromNode))?.classList.add("active");
      graphNodeRefs.get(graphKey(graphId, toNode))?.classList.add("active");
      edgeRefs.get(edgeKey(graphId, fromNode, toNode))?.classList.add("active");
    }
  }

  function renderSummary(workflow) {
    const statusPill = document.getElementById("taskStatusPill");
    const threadPill = document.getElementById("threadStatusPill");
    const summaryGrid = document.getElementById("summaryGrid");

    if (!workflow) {
      statusPill.textContent = "Topology only";
      statusPill.className = "status-pill";
      threadPill.textContent = "no thread";
      threadPill.className = "status-pill";
      summaryGrid.innerHTML =
        '<div class="summary-item"><strong>0</strong><span>events</span></div>' +
        '<div class="summary-item"><strong>0</strong><span>executed nodes</span></div>';
      return;
    }

    const events = ensureArray(workflow.events);
    const nodeKeys = new Set();
    events.forEach((event) => {
      const payload = event.payload || {};
      const graphId = payload.graph_id || payload.graphId;
      const nodeId = payload.node_id || payload.nodeId;
      if (graphId && nodeId) nodeKeys.add(graphKey(graphId, nodeId));
    });

    statusPill.textContent = workflow.taskStatus
      ? `task ${workflow.taskId} | ${workflow.taskStatus}`
      : `task ${workflow.taskId}`;
    statusPill.className = `status-pill ${events.length ? "ok" : "warn"}`;
    threadPill.textContent = workflow.workflowThreadId
      ? `thread: ${workflow.workflowThreadId}`
      : "no thread";
    threadPill.className = `status-pill ${workflow.workflowThreadId ? "ok" : "warn"}`;
    summaryGrid.innerHTML =
      `<div class="summary-item"><strong>${events.length}</strong><span>events</span></div>` +
      `<div class="summary-item"><strong>${nodeKeys.size}</strong><span>executed nodes</span></div>`;
  }

  function renderTimeline(workflow) {
    const mount = document.getElementById("timelineMount");
    mount.innerHTML = "";

    if (!workflow) {
      mount.innerHTML = '<div class="timeline-empty">Add a <code>taskId</code> to load the runtime trace.</div>';
      return;
    }

    const events = ensureArray(workflow.events);
    if (!events.length) {
      mount.innerHTML =
        '<div class="timeline-empty">This task does not have workflow events yet. ' +
        'It may not have entered the LangGraph path, or the control plane has not received node-level callbacks.</div>';
      return;
    }

    events.forEach((event, index) => {
      const payload = event.payload || {};
      const card = createElement("article", "event-card");
      if (index === activeEventIndex) card.classList.add("active");
      card.addEventListener("click", () => {
        activeEventIndex = index;
        renderTimeline(currentWorkflow);
        applyWorkflowHighlight();
      });

      const head = createElement("div", "event-head");
      const title = createElement("div", "event-title");
      title.appendChild(createElement("span", "event-type", event.eventType || "EVENT"));
      title.appendChild(createElement("span", "muted", compactPayload(payload) || "workflow"));
      head.appendChild(title);

      const meta = createElement("div", "event-meta");
      meta.appendChild(createElement("span", "", formatTime(event.occurredAt || event.createdAt)));
      head.appendChild(meta);
      card.appendChild(head);

      card.appendChild(createElement("div", "event-summary", summarizeEvent(event)));

      const progress = event.progress || {};
      const progressParts = [];
      if (progress.current !== undefined && progress.total !== undefined) {
        progressParts.push(`progress ${progress.current}/${progress.total}`);
      }
      if (workflow.mode) progressParts.push(`mode ${workflow.mode}`);
      if (workflow.filename) progressParts.push(workflow.filename);
      if (progressParts.length) {
        card.appendChild(createElement("div", "empty-note", progressParts.join(" | ")));
      }

      mount.appendChild(card);
    });
  }

  async function loadWorkflow(taskId) {
    const mount = document.getElementById("timelineMount");

    if (!taskId) {
      currentWorkflow = null;
      activeEventIndex = -1;
      renderSummary(null);
      renderTimeline(null);
      applyWorkflowHighlight();
      const url = new URL(window.location.href);
      url.searchParams.delete("taskId");
      window.history.replaceState({}, "", url.toString());
      return;
    }

    mount.innerHTML = '<div class="timeline-empty">Loading workflow trace...</div>';
    try {
      const response = await fetch(`/studio/tasks/${encodeURIComponent(taskId)}/workflow-events`, {
        headers: { "Accept": "application/json" }
      });
      if (!response.ok) {
        let detail = `HTTP ${response.status}`;
        try {
          const body = await response.json();
          detail = body.detail || detail;
        } catch (error) {}
        throw new Error(detail);
      }

      currentWorkflow = await response.json();
      activeEventIndex = currentWorkflow.events && currentWorkflow.events.length
        ? currentWorkflow.events.length - 1
        : -1;
      renderSummary(currentWorkflow);
      renderTimeline(currentWorkflow);
      applyWorkflowHighlight();

      const url = new URL(window.location.href);
      url.searchParams.set("taskId", String(taskId));
      window.history.replaceState({}, "", url.toString());
    } catch (error) {
      currentWorkflow = null;
      activeEventIndex = -1;
      renderSummary(null);
      mount.innerHTML = `<div class="timeline-error">Failed to load trace: ${error.message}</div>`;
      applyWorkflowHighlight();
    }
  }

  function bindEvents() {
    const form = document.getElementById("taskForm");
    const input = document.getElementById("taskIdInput");
    const clearButton = document.getElementById("clearSelection");

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      loadWorkflow(input.value.trim());
    });

    clearButton.addEventListener("click", () => {
      input.value = "";
      loadWorkflow("");
    });
  }

  function init() {
    renderGraphs();
    renderSummary(null);
    renderTimeline(null);
    bindEvents();
    if (INITIAL_TASK_ID) {
      document.getElementById("taskIdInput").value = INITIAL_TASK_ID;
      loadWorkflow(INITIAL_TASK_ID);
    }
  }

  init();
</script>
"""


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/studio/info")
def studio_info(request: Request) -> dict[str, object]:
    recommended_base_url = str(request.base_url).rstrip("/")
    return {
        "service": "ocr-web-langgraph-studio",
        "graphs": workflow_graph_ids(),
        "recommended_base_url": recommended_base_url,
    }


@app.get("/studio/topology")
def studio_topology() -> dict[str, object]:
    return get_workflow_topology()


async def _fetch_control_plane_workflow_events(task_id: int) -> dict[str, object]:
    headers = {"Accept": "application/json"}
    if CONTROL_PLANE_INTERNAL_TOKEN:
        headers["Authorization"] = f"Bearer {CONTROL_PLANE_INTERNAL_TOKEN}"

    path = f"/internal/api/v1/ocr/tasks/{task_id}/workflow-events"
    async with httpx.AsyncClient(
        base_url=CONTROL_PLANE_BASE_URL,
        verify=CONTROL_PLANE_VERIFY_TLS,
        timeout=15.0,
    ) as client:
        response = await client.get(path, headers=headers)

    if response.status_code == 404:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    if response.status_code == 401:
        raise HTTPException(status_code=502, detail="Control plane rejected workflow-events proxy request.")
    if response.is_error:
        raise HTTPException(
            status_code=502,
            detail=f"Control plane workflow-events request failed: HTTP {response.status_code}",
        )

    return response.json()


@app.get("/studio/tasks/{task_id}/workflow-events")
async def studio_workflow_events(task_id: int) -> dict[str, object]:
    return await _fetch_control_plane_workflow_events(task_id)


@app.get("/studio/flow", response_class=HTMLResponse)
def studio_flow(request: Request) -> str:
    requested_task_id = request.query_params.get("taskId", "").strip()
    topology_json = json.dumps(get_workflow_topology(), ensure_ascii=False).replace("</", "<\\/")
    requested_task_json = json.dumps(requested_task_id, ensure_ascii=False)
    flow_script = FLOW_SCRIPT_TEMPLATE.replace("__TOPOLOGY_JSON__", topology_json).replace(
        "__REQUESTED_TASK_ID_JSON__", requested_task_json
    )
    flow_body = (
        FLOW_BODY_TEMPLATE.replace("__FLOW_SCRIPT__", flow_script)
        .replace("__REQUESTED_TASK_ID__", requested_task_id)
        .replace("__CONTROL_PLANE_BASE_URL__", CONTROL_PLANE_BASE_URL)
    )
    return FLOW_PAGE_TEMPLATE.replace("__FLOW_BODY__", flow_body)
