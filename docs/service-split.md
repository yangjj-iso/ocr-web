# 服务拆分说明

## 目标

将当前单体后端按职责拆成两类服务：

- `business-api`
  - 鉴权
  - 归档记录
  - 文件夹扫描
  - 批次建档
- `ai-document-service`
  - OCR 上传与任务管理
  - 文档边界识别
  - 批次智能整合
  - 批次 QA / 评测
  - 文件预览与缩略图

## 当前入口

- 兼容单体：[`app/main.py`](/D:/Code/work/OCR-WEB-main/app/main.py)
- 业务服务：[`app/main_business.py`](/D:/Code/work/OCR-WEB-main/app/main_business.py)
- AI 服务：[`app/main_ai.py`](/D:/Code/work/OCR-WEB-main/app/main_ai.py)

## 路由边界

业务服务路由注册：

- [`app/interfaces/api/business/router_registry.py`](/D:/Code/work/OCR-WEB-main/app/interfaces/api/business/router_registry.py)

AI 服务路由注册：

- [`app/interfaces/api/ai/router_registry.py`](/D:/Code/work/OCR-WEB-main/app/interfaces/api/ai/router_registry.py)

## 关键拆分点

### 业务侧

- 鉴权：[`app/api/auth_routes.py`](/D:/Code/work/OCR-WEB-main/app/api/auth_routes.py)
- 归档：[`app/api/archives.py`](/D:/Code/work/OCR-WEB-main/app/api/archives.py)
- 批次管理：[`app/api/business_batches.py`](/D:/Code/work/OCR-WEB-main/app/api/business_batches.py)

### AI 侧

- 任务：[`app/api/tasks.py`](/D:/Code/work/OCR-WEB-main/app/api/tasks.py)
- 批次 AI：[`app/api/ai_batches.py`](/D:/Code/work/OCR-WEB-main/app/api/ai_batches.py)
- QA：[`app/api/qa.py`](/D:/Code/work/OCR-WEB-main/app/api/qa.py)
- 评测：[`app/api/evaluation.py`](/D:/Code/work/OCR-WEB-main/app/api/evaluation.py)
- 文件预览：[`app/api/files.py`](/D:/Code/work/OCR-WEB-main/app/api/files.py)

新增边界分析接口：

- `GET /api/ocr/batches/{batch_id}/boundary-analysis`
- `GET /api/ocr/batches/{batch_id}/boundary-truth`
- `PUT /api/ocr/batches/{batch_id}/boundary-truth`

该接口会返回：

- 页面序列 `sequences`
- 相邻页边界判定 `decisions`
- 全局切分结果 `groups`
- `task_to_group` 映射

其中 `boundary-truth` 用于保存人工确认后的 `task_id -> doc_key` 映射。
保存后会立即覆盖当前批次的自动归并结果，并派生相邻页 `same/different` 边界反馈样本。
这些反馈样本会继续聚合成 `family + page_gap` 先验，供后续批次的边界评分参考，实现“人工修正后，下一批相似材料更容易判对”。

## 前端联调

前端现在支持分别配置业务和 AI 服务地址，见：

- [`frontend/src/api/runtime.js`](/D:/Code/work/OCR-WEB-main/frontend/src/api/runtime.js)
- [`frontend/src/api/auth.js`](/D:/Code/work/OCR-WEB-main/frontend/src/api/auth.js)
- [`frontend/src/api/ocr.js`](/D:/Code/work/OCR-WEB-main/frontend/src/api/ocr.js)

推荐环境变量：

```text
VITE_BUSINESS_API_BASE_URL=http://localhost:8000
VITE_AI_API_BASE_URL=http://localhost:8001
VITE_AI_FILE_BASE_URL=http://localhost:8001
```

## 下一步建议

1. 先按当前 Python 双服务方式部署稳定运行。
2. 再把 `business-api` 逐步替换为 Java 服务。
3. Java 服务通过 HTTP / 消息队列调用 `ai-document-service`。
4. 在样本量上来后，把当前的轻量先验升级成可训练的边界分类器。

## 已落库的边界诊断表

- `batch_page_sequences`
- `batch_boundary_decisions`
- `batch_document_groups`
- `batch_boundary_truth_task_map`
- `batch_boundary_feedback`

这些表由 [`document_boundary_store.py`](/D:/Code/work/OCR-WEB-main/app/services/document_boundary_store.py) 维护，当前在批次整合和边界分析计算后自动刷新。
人工校正真值由 [`document_boundary_feedback_service.py`](/D:/Code/work/OCR-WEB-main/app/services/document_boundary_feedback_service.py) 维护。
历史反馈样本的轻量学习逻辑位于 [`document_boundary_feedback_learning.py`](/D:/Code/work/OCR-WEB-main/app/services/document_boundary_feedback_learning.py)。
