from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="OCR-WEB LangGraph Studio")


@app.get("/health/live")
def health_live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/studio/info")
def studio_info(request: Request) -> dict[str, object]:
    recommended_base_url = str(request.base_url).rstrip("/")
    return {
        "service": "ocr-web-langgraph-studio",
        "graphs": ["batch_supervisor", "page_agent"],
        "recommended_base_url": recommended_base_url,
    }


@app.get("/studio/flow", response_class=HTMLResponse)
def studio_flow() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>OCR-WEB LangGraph 流转图</title>
  <style>
    body {
      margin: 0;
      padding: 32px;
      font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
      background: #f6f8fb;
      color: #1f2937;
    }
    h1, h2 {
      margin: 0 0 16px;
    }
    .section {
      background: #ffffff;
      border-radius: 16px;
      padding: 24px;
      margin-bottom: 24px;
      box-shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
    }
    .flow {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      align-items: center;
      margin: 12px 0 20px;
    }
    .node {
      min-width: 180px;
      max-width: 240px;
      background: #eef4ff;
      border: 1px solid #bfd3ff;
      border-radius: 14px;
      padding: 12px 14px;
      line-height: 1.5;
    }
    .decision {
      background: #fff7e8;
      border-color: #ffd591;
    }
    .danger {
      background: #fff1f0;
      border-color: #ffb3b3;
    }
    .success {
      background: #f6ffed;
      border-color: #b7eb8f;
    }
    .arrow {
      font-size: 22px;
      color: #64748b;
      padding: 0 4px;
    }
    .hint {
      color: #475569;
      margin-top: 8px;
    }
    code {
      background: #f1f5f9;
      padding: 2px 6px;
      border-radius: 6px;
    }
    ul {
      margin: 8px 0 0;
      padding-left: 20px;
    }
    li {
      margin: 6px 0;
    }
  </style>
</head>
<body>
  <div class="section">
    <h1>OCR-WEB 简化流转图</h1>
    <div class="hint">先看这张图，再去看 LangSmith/LangGraph 原始节点图，会轻松很多。</div>
  </div>

  <div class="section">
    <h2>整份文件主流程</h2>
    <div class="flow">
      <div class="node">1. 准备批次<br /><code>node_prepare_batch</code><br />拆页、初始化状态</div>
      <div class="arrow">→</div>
      <div class="node">2. 逐页处理<br /><code>node_process_next_page</code><br />进入当前页子流程</div>
      <div class="arrow">→</div>
      <div class="node">3. 跨页一致性检查<br /><code>node_cross_page_consistency</code><br />看题名/文号/责任者是否打架</div>
      <div class="arrow">→</div>
      <div class="node">4. 检索历史样本<br /><code>node_rag_retrieve</code><br />拉相似材料辅助判断</div>
      <div class="arrow">→</div>
      <div class="decision node">5. 人工审核路由<br /><code>node_human_router</code><br />决定自动通过还是转人工</div>
      <div class="arrow">→</div>
      <div class="success node">6. 最终归档与质量汇总<br /><code>node_final_archiver_and_quality</code></div>
    </div>
    <div class="flow">
      <div class="decision node">如果低置信/冲突明显</div>
      <div class="arrow">→</div>
      <div class="danger node">暂停等待人工<br /><code>node_pause_for_human_review</code></div>
      <div class="arrow">→</div>
      <div class="success node">人工确认后继续执行<br />resume 到后续节点</div>
    </div>
  </div>

  <div class="section">
    <h2>单页处理子流程</h2>
    <div class="flow">
      <div class="node">A. 页级计划<br /><code>node_page_plan</code><br />判断复杂度、决定是否启用双路</div>
      <div class="arrow">→</div>
      <div class="node">B. PP-OCRv5<br /><code>node_ocr</code><br />主路文字识别</div>
      <div class="arrow">→</div>
      <div class="node">C. PaddleOCR-VL-1.5<br /><code>node_ppocr_vl</code><br />复杂页或重试时参与</div>
      <div class="arrow">→</div>
      <div class="decision node">D. 仲裁合并<br /><code>node_evaluate_and_merge</code><br />综合两路结果打分</div>
      <div class="arrow">→</div>
      <div class="success node">E. 完成单页<br /><code>node_finalize_page</code></div>
    </div>
    <div class="flow">
      <div class="decision node">如果分数不够</div>
      <div class="arrow">→</div>
      <div class="danger node">切换预处理策略重试<br /><code>node_adjust_strategy</code></div>
      <div class="arrow">→</div>
      <div class="node">回到 <code>node_page_plan</code></div>
    </div>
  </div>

  <div class="section">
    <h2>最值得盯的 4 个节点</h2>
    <ul>
      <li><code>node_ocr</code>：看 PP-OCRv5 主路有没有读到字、有没有图片路径问题。</li>
      <li><code>node_ppocr_vl</code>：看 PaddleOCR-VL-1.5 第二路有没有参与、有没有返回空结果。</li>
      <li><code>node_evaluate_and_merge</code>：看最终 <code>confidence</code>、<code>issues</code>、<code>human_review</code>。</li>
      <li><code>node_human_router</code>：看为什么被送人工，重点看 <code>review_reason</code>。</li>
    </ul>
  </div>
</body>
</html>
"""
