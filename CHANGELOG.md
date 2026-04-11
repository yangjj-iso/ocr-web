# 更新日志 (CHANGELOG)

所有重要的项目变更都记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## [Unreleased]

---

## [2.3.0] - 2026-04-10

### 新增 - 合并文档归档导出

- **合并文档字段提取**：结果页字段显示改为调用 `/batches/{batchId}/ai-merge-extract`，按合并文档（而非单页）维度展示归档字段
- **合并文档 Excel 导出**：
  - Python AI API 新增 `GET /api/ocr/batches/{batchId}/ai-merge-export` 导出端点
  - Java 控制面新增代理端点，支持二进制文件转发
  - 前端导出按钮改为调用合并文档导出接口
  - Excel 表头：档号 / 文号 / 责任者 / 题名 / 日期 / 页数 / 密级 / 备注
  - 每行对应一个合并文档，优先使用 `recommended_fields`，回退 `rule_fields`
- **单文件批次支持**：放开单文件批次的导出按钮，单文件也走合并文档口径
- **前端缓存优化**：结果页缓存已加载的合并字段，避免重复请求

### 修复

- 修复 `batch_ai_service` 代理层缺少 `similarity_threshold` 参数透传，导致合并抽取 TypeError
- 修复 `batch_ai_service` 代理层未处理上游返回 `None` 导致 AttributeError
- 修复 `useBatchUpload.js` 中 `batchDone` 条件要求 `requestedCount > 1`，导致单文件批次无法导出
- 修复 MQ_BROKER_URL 使用 `%2F` 编码导致 Python Worker 连接异常（改为 `//`）

### 变更

- `.env` 文件重新整理，按功能分组并添加中文注释
- `MINIMAX_API_KEY` 补齐配置，与 `LLM_API_KEY` 保持一致

### 涉及文件

| 文件 | 变更 |
|------|------|
| `app/services/batch_merge_extraction_service.py` | 新增 `export_batch_merge_extract_excel` 导出函数 |
| `app/application/workflows/batches.py` | 新增 `export_batch_ai_merge_excel` workflow |
| `app/api/ai_batches.py` | 新增 `GET /ai-merge-export` 端点 |
| `app/domains/batch_ai/batch_ai_service.py` | 补齐 `similarity_threshold` 参数 + None guard |
| `java-control-plane/.../AiProxyService.java` | 新增导出代理路径 |
| `java-control-plane/.../BatchAiProxyController.java` | 新增导出代理端点 |
| `frontend/src/api/ocr.js` | 新增 `exportBatchMergeArchiveRecords` |
| `frontend/src/composables/useBatchUpload.js` | 导出改用合并口径，放开单文件限制 |
| `frontend/src/features/result/ResultPage.vue` | 字段显示改用合并文档数据源 |

---

## [2.2.0] - 2026-04-08

### 新增

- 批次文档边界智能分析（pHash + 版式哈希 + 投影轮廓）
- 批次知识问答（QA）功能，支持证据可追溯
- 批次质量评测与 AI 报告
- LangGraph Studio 本地调试支持
- Prometheus Worker 指标导出

### 变更

- 架构拆分为 Java 控制面 + Python AI 计算面
- 文件存储统一迁移至 MinIO (S3 兼容)
- Worker 通过 RabbitMQ 消费任务，不再直接处理 HTTP 请求

---

## [2.1.0] - 2026-03-25

### 新增

- 三模型识别切换（VL / 版面解析 / 基础 OCR）
- 批量文件夹识别（本地选择 + 服务器路径扫描）
- 归档 Excel 自动写入（档号 / 文号 / 责任者 / 题名 / 日期 / 页数 / 密级 / 备注）
- 全文搜索功能
- Redis 多级缓存
- 版面解析 17 类检测 + 表格 HTML 还原

---

## [2.0.0] - 2026-03-15

### 新增

- Vue 3 + Vite 前端重写
- FastAPI 异步后端
- PostgreSQL + asyncpg 数据层
- PaddleOCR 3.x 引擎集成
- Bbox 区块高亮与编辑
- PDF 预览支持

---

## [1.0.0] - 2026-02-01

### 新增

- 初始版本：基础 OCR 识别 + 结果展示
- 单文件上传识别
- 简单文本导出
