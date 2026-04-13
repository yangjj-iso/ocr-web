from __future__ import annotations

import json

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from app.studio.workflow_topology import get_workflow_topology, workflow_graph_ids


app = FastAPI(title="OCR-WEB Archive Workflow Studio")


FLOW_TEMPLATE = """<!doctype html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Archive Workflow Studio</title>
  <style>
    :root {
      --bg: #f4f7fb;
      --panel: #ffffff;
      --line: #d7e0ea;
      --text: #17283a;
      --muted: #60758f;
      --accent: #2155f5;
      --success: #178d51;
      --warn: #c77a07;
      --danger: #c94151;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: \"Segoe UI\", \"Microsoft YaHei\", sans-serif; background: linear-gradient(180deg, #f9fbff, var(--bg)); color: var(--text); }
    .page { width: min(1400px, calc(100vw - 32px)); margin: 24px auto 40px; display: grid; gap: 18px; }
    .hero, .panel { background: var(--panel); border: 1px solid rgba(148, 163, 184, 0.2); border-radius: 18px; box-shadow: 0 18px 36px rgba(15, 23, 42, 0.08); }
    .hero { padding: 24px 28px; display: grid; gap: 12px; }
    .hero h1, .panel h2, .panel h3 { margin: 0; }
    .hero p, .panel p { margin: 0; color: var(--muted); line-height: 1.6; }
    .chips { display: flex; flex-wrap: wrap; gap: 8px; }
    .chip { padding: 7px 12px; border-radius: 999px; background: rgba(33, 85, 245, 0.1); color: var(--accent); font-size: 12px; font-weight: 700; }
    .panel { padding: 20px 24px; }
    .graph-grid { display: grid; gap: 16px; }
    .graph-card { border: 1px solid var(--line); border-radius: 16px; padding: 16px; background: linear-gradient(180deg, #fff, #f8fbff); }
    .graph-meta { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 14px; }
    .badge { padding: 6px 10px; border-radius: 999px; background: rgba(23, 141, 81, 0.10); color: var(--success); font-size: 12px; font-weight: 700; }
    .lists { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }
    .list-box { border: 1px solid var(--line); border-radius: 14px; padding: 14px; background: rgba(255,255,255,0.9); }
    .list-box ul { margin: 10px 0 0; padding-left: 18px; }
    .list-box li { margin: 6px 0; color: var(--muted); }
    code { padding: 2px 6px; border-radius: 999px; background: rgba(15, 23, 42, 0.06); }
  </style>
</head>
<body>
  <div class=\"page\">
    <section class=\"hero\">
      <div class=\"chips\">
        <span class=\"chip\">LangGraph Studio</span>
        <span class=\"chip\">Archive Only</span>
        <span class=\"chip\">Develop.md Aligned</span>
      </div>
      <div>
        <h1>Archive workflow topology</h1>
        <p>当前 Studio 仅保留 Develop.md 定义的档案整理工作流，包括 main、draft、resume、final 四层子图。旧的 hierarchical OCR / batch_supervisor / page_agent 工作流已移除。</p>
      </div>
    </section>
    <section class=\"panel\">
      <h2>Topology</h2>
      <p>以下内容来自服务端内置拓扑定义，用于本地检查 LangGraph 图结构和节点划分。</p>
      <div id=\"graphMount\" class=\"graph-grid\"></div>
    </section>
  </div>
  <script>
    const TOPOLOGY = __TOPOLOGY_JSON__;
    const mount = document.getElementById('graphMount');
    const escapeHtml = (value) => String(value ?? '').replace(/[&<>\"]/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[ch] || ch));
    const renderList = (title, items, mapper) => {
      const box = document.createElement('div');
      box.className = 'list-box';
      const heading = document.createElement('h3');
      heading.textContent = title;
      box.appendChild(heading);
      const ul = document.createElement('ul');
      items.forEach((item) => {
        const li = document.createElement('li');
        li.innerHTML = mapper(item);
        ul.appendChild(li);
      });
      box.appendChild(ul);
      return box;
    };
    (TOPOLOGY.graphs || []).forEach((graph) => {
      const card = document.createElement('article');
      card.className = 'graph-card';
      card.innerHTML = `
        <h3>${escapeHtml(graph.title)}</h3>
        <p>${escapeHtml(graph.description || '')}</p>
        <div class=\"graph-meta\">
          <span class=\"badge\">graph id: ${escapeHtml(graph.id)}</span>
          <span class=\"badge\">nodes: ${(graph.nodes || []).length}</span>
          <span class=\"badge\">edges: ${(graph.edges || []).length}</span>
        </div>
      `;
      const lists = document.createElement('div');
      lists.className = 'lists';
      lists.appendChild(renderList('Nodes', graph.nodes || [], (node) => `<code>${escapeHtml(node.id)}</code> · ${escapeHtml(node.label)}`));
      lists.appendChild(renderList('Edges', graph.edges || [], (edge) => `<code>${escapeHtml(edge.source)}</code> → <code>${escapeHtml(edge.target)}</code>${edge.label ? ` · ${escapeHtml(edge.label)}` : ''}`));
      if (Array.isArray(graph.subgraphs) && graph.subgraphs.length) {
        lists.appendChild(renderList('Subgraphs', graph.subgraphs, (item) => `<code>${escapeHtml(item.source)}</code> → <code>${escapeHtml(item.target_graph)}</code>`));
      }
      card.appendChild(lists);
      mount.appendChild(card);
    });
  </script>
</body>
</html>
"""


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/studio/info")
def studio_info() -> dict[str, object]:
    topology = get_workflow_topology()
    return {
        "title": topology.get("title", "Archive Workflow Topology"),
        "graphs": workflow_graph_ids(),
        "view": topology.get("view", {}),
    }


@app.get("/studio/topology")
def studio_topology() -> dict[str, object]:
    return get_workflow_topology()


@app.get("/studio/flow", response_class=HTMLResponse)
def studio_flow(request: Request) -> HTMLResponse:
    del request
    topology_json = json.dumps(get_workflow_topology(), ensure_ascii=False).replace("</", "<\\/")
    return HTMLResponse(FLOW_TEMPLATE.replace("__TOPOLOGY_JSON__", topology_json))
