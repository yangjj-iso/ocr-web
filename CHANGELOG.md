# 更新日志 (CHANGELOG)

所有重要的项目变更都记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## [Unreleased]

---

## [2.4.0] - 2026-04-11

### 新增

- **历史"查看结果"弹窗**：点击历史记录的"查看结果"按钮，弹出智能整合结果面板（MergeResultModal），不再跳转批次概览页
- **检索链路增强**：
  - Java 搜索 SQL 扩展到 archive_records 表（档号/文号/责任者/题名均可搜索）
  - 新增 `SearchResponse` / `SearchResultResponse` DTO，返回完整档案级字段
  - 前端 SearchPage 搜索结果展示档号、文号、责任者、日期、密级、存放路径
- **归档模型 storage_path 字段**：Python ArchiveRecord + Java ArchiveRecordEntity + DB 迁移
- **操作日志扩展**：AI 字段提取、Excel 导出、边界真值保存均记录审计日志
- **登录/注册页面视觉升级**：
  - 引入 Noto Serif SC + Playfair Display 字体
  - 品牌标题改用衬线体、加大字号、深蓝渐变背景 + 网格纹理
  - 右侧表单标题同步使用衬线体

### 修复

- **[P0] 个人中心/退出按钮消失**：`App.vue` 用户菜单的 `v-if` 条件改为 `isAuthenticated || !isAuthEnabled`，修复 `AUTH_ENABLED=false` 时用户菜单不渲染的问题
- **[P0] 仪表板数据造假**：趋势图 `Math.random()` 和任务状态图硬编码值全部替换为真实 API 数据；新增 Java `GET /api/ocr/dashboard/stats` 端点返回 taskCounts + dailyCounts
- **[P0] 检索者首页搜索失败**：`SearcherHomePage.vue` 误用 Python AI API 搜索，改为 Java 控制面 `searchTasks` 接口
- **[P0] 责任者提取误填**：`excel_export.py` 重写 `_extract_responsible_candidates` 返回 `(candidate, source_type)` 元组；评分增加强正信号（甲方/乙方 +25、盖章 +18、发文单位 +15）、负信号（标题位置 -12、fragment-only -5）、最低分阈值 ≥3
- **[P0] 规则/LLM 冲突**：从 `_LLM_PREFERRED_FIELDS` 移除"责任者"，规则提取优先
- **[P0] Worker token 固化**：`worker_executor.py` 改用 `getattr(_app_config, 'CONTROL_PLANE_INTERNAL_TOKEN', '')` 惰性读取，运行时环境变量覆盖生效
- **Java 启动崩溃**：`OcrTaskService.searchTasks` 中 `getStatus()` 返回 String 而非 enum，移除 `.name()` 调用
- **ProfilePage/DashboardPage 相对导入**：统一改为 `@/api/*` 别名导入

### 变更

- `AdminCenterPage.vue` 相对导入改为 `@/api/*` 别名导入
- 新增 `docs/requirements-progress.md` 甲方需求 vs 项目进度对照表
- 仪表板 Python 健康检查改为基于 admin API 调用结果判定

### 涉及文件

| 文件 | 变更 |
|------|------|
| `frontend/src/components/MergeResultModal.vue` | 新建：可复用的智能整合结果弹窗组件 |
| `frontend/src/features/workbench/WorkbenchPage.vue` | 接入 MergeResultModal，重写 handleHistoryViewBatch |
| `frontend/src/features/search/SearchPage.vue` | 展示档案级字段 + 兼容新 SearchResponse |
| `frontend/src/features/auth/LoginPage.vue` | 视觉升级：衬线字体 + 深蓝渐变 |
| `frontend/src/features/auth/RegisterPage.vue` | 同步视觉升级 |
| `frontend/src/features/admin/AdminCenterPage.vue` | 修复相对导入 |
| `frontend/index.html` | 添加 Google Fonts 预连接 |
| `app/services/excel_export.py` | 重写责任者候选+评分逻辑 |
| `app/services/llm_field_extraction_service.py` | 责任者移出 LLM 优先字段 |
| `app/infrastructure/queue/worker_executor.py` | token 惰性读取 |
| `app/db/models.py` | ArchiveRecord 增加 storage_path |
| `app/api/ai_batches.py` | 添加操作日志 |
| `java-control-plane/.../ArchiveRecordEntity.java` | 增加 storagePath 字段 |
| `java-control-plane/.../ArchiveDtos.java` | DTO 增加 storagePath |
| `java-control-plane/.../ArchiveRecordService.java` | toResponse 映射 + findByTaskIds |
| `java-control-plane/.../ArchiveRecordRepository.java` | 新增 findByTaskIdIn |
| `java-control-plane/.../OcrTaskRepository.java` | 新增 searchWithArchive JPQL |
| `java-control-plane/.../OcrTaskService.java` | searchTasks 返回 SearchResponse + HashMap import |
| `java-control-plane/.../OcrTaskController.java` | search 端点返回类型更新 |
| `java-control-plane/.../TaskDtos.java` | 新增 SearchResultResponse / SearchResponse |

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
