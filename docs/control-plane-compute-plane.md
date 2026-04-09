# Control Plane / Compute Plane 拆分

## 目标

- Java Spring Boot 负责控制面：上传、任务生命周期、MQ 投递、状态查询、内部回调落库
- Python 负责计算面：OCR、Vision LLM、LangGraph、规则引擎、显存清理
- Java 与 Python 通过 RabbitMQ 命令队列 + 内部 REST 回调异步解耦

## Python 侧

### 入口

- AI API 兼容入口：[`app/main_ai.py`](/D:/Code/work/OCR-WEB-main/app/main_ai.py)
- 原生 MQ Worker：[`app/main_worker.py`](/D:/Code/work/OCR-WEB-main/app/main_worker.py)
- Celery 配置：[`app/infrastructure/queue/celery_app.py`](/D:/Code/work/OCR-WEB-main/app/infrastructure/queue/celery_app.py)
- Celery 任务：[`app/infrastructure/queue/celery_tasks.py`](/D:/Code/work/OCR-WEB-main/app/infrastructure/queue/celery_tasks.py)

### 关键模块

- MQ 契约：[`app/infrastructure/queue/contracts.py`](/D:/Code/work/OCR-WEB-main/app/infrastructure/queue/contracts.py)
- 控制面回调客户端：[`app/infrastructure/queue/callback_client.py`](/D:/Code/work/OCR-WEB-main/app/infrastructure/queue/callback_client.py)
- 命令发布适配器：[`app/infrastructure/queue/publisher.py`](/D:/Code/work/OCR-WEB-main/app/infrastructure/queue/publisher.py)
- RabbitMQ 原生消费者：[`app/infrastructure/queue/rabbitmq_consumer.py`](/D:/Code/work/OCR-WEB-main/app/infrastructure/queue/rabbitmq_consumer.py)
- 共享执行器：[`app/infrastructure/queue/worker_executor.py`](/D:/Code/work/OCR-WEB-main/app/infrastructure/queue/worker_executor.py)

### 运行方式

```powershell
D:\Code\work\OCR-WEB-main\.venv\Scripts\python.exe D:\Code\work\OCR-WEB-main\app\main_worker.py
```

或：

```powershell
celery -A app.infrastructure.queue.celery_app:celery_app worker -l info
```

### ACK 语义

- Java 只负责投递命令，不等待 OCR 执行完成
- Python Worker 只有在控制面 `completion/failure` 回调返回 `persisted=true` 后才允许 ACK
- 如果 LangGraph 因低置信字段进入 `interrupt()`，Worker 会先把暂停状态通过 `pause` 回调安全写回控制面，再 ACK 当前命令；后续由控制面重新投递 `OCR_TASK_RESUME`
- 原生 RabbitMQ Consumer 当前通过 `message.ack()` / `message.reject(requeue=True)` 保证不丢任务
- Celery Worker 通过 `task_acks_late=true`、`task_reject_on_worker_lost=true`、`task_acks_on_failure_or_timeout=false` 保证晚 ACK

### LangGraph 持久化与人工续跑

- 批次主图现在带 `checkpointer` 编译，默认回退 `InMemorySaver`
- 可通过环境变量切换：
  - `LANGGRAPH_CHECKPOINTER_BACKEND=memory|postgres|redis`
  - `LANGGRAPH_CHECKPOINTER_DSN`
  - `LANGGRAPH_CHECKPOINTER_REDIS_URL`
- 当页级 Arbiter 结果低于 `LANGGRAPH_HUMAN_REVIEW_INTERRUPT_THRESHOLD`，或批次级一致性/关键字段检查需要人工介入时，工作流会触发 `interrupt()`
- 控制面收到 `pause` 回调后，会保存：
  - `workflow_thread_id`
  - `human_review_payload`
  - 当前部分结果 `result_json/full_text`
- 人工修改完成后，通过 `POST /api/ocr/tasks/{taskId}/human-review/resume` 投递 `OCR_TASK_RESUME`，计算面会使用同一个 `thread_id` 继续图执行

### 存储解耦

- MQ 中传递的输入文件不再默认使用 `file:///D:/...` 本地绝对路径
- Java 控制面现在会下发内部文件下载 URL：
  - `GET /internal/api/v1/ocr/tasks/{taskId}/source-file`
- Python Worker 下载时会自动附带 `OCR_INTERNAL_API_TOKEN`
- Java `TaskStorageService` 已支持：
  - `local` 本地目录
  - `s3` S3 兼容对象存储（MinIO / OSS / 其他兼容网关）
- 当前默认配置：
  - `OCR_STORAGE_BACKEND=s3`
  - `OCR_STORAGE_ENDPOINT=http://127.0.0.1:9000`
  - `OCR_STORAGE_BUCKET=ocr-source`
  - `OCR_STORAGE_ACCESS_KEY=admin`
  - `OCR_STORAGE_SECRET_KEY=admin123456`
  - `OCR_STORAGE_REGION=us-east-1`
  - `OCR_STORAGE_PATH_STYLE=true`
- 控制面数据库现在保存的是：
  - 逻辑源路径 `file_path`
  - 对象存储定位元数据 `storage_provider/storage_bucket/storage_object_key`
- Worker 继续只认内部下载 URL，不需要感知对象存储凭据

### LangSmith / Tracing

- 当设置 `LANGCHAIN_API_KEY` 且 `LANGCHAIN_TRACING_V2=true` 时，计算面会自动开启 LangSmith tracing
- LangGraph 运行配置里会附带：
  - `task_id`
  - `batch_id`
  - `thread_id`
  - `component=langgraph-batch-supervisor`
- 这样可以在 LangSmith 中直接看到同一批任务的图节点流转与恢复链路

### Prometheus 指标

- Worker 默认在 `http://0.0.0.0:9108/metrics` 导出 Prometheus 指标
- 关键指标包括：
  - `ocr_compute_worker_queue_depth`
  - `ocr_compute_worker_inflight_tasks`
  - `ocr_compute_worker_paused_tasks_total`
  - `ocr_compute_worker_page_processing_seconds`
  - `ocr_compute_worker_gpu_cache_clears_total`
- 可通过环境变量调整：
  - `WORKER_METRICS_ENABLED`
  - `WORKER_METRICS_HOST`
  - `WORKER_METRICS_PORT`

## Java 控制面

### 模块位置

- Maven 项目：[`java-control-plane/pom.xml`](/D:/Code/work/OCR-WEB-main/java-control-plane/pom.xml)
- 主程序：[`ControlPlaneApplication.java`](/D:/Code/work/OCR-WEB-main/java-control-plane/src/main/java/com/ocrweb/controlplane/ControlPlaneApplication.java)
- RabbitMQ 配置：[`RabbitMqConfig.java`](/D:/Code/work/OCR-WEB-main/java-control-plane/src/main/java/com/ocrweb/controlplane/config/RabbitMqConfig.java)
- 任务控制器：[`OcrTaskController.java`](/D:/Code/work/OCR-WEB-main/java-control-plane/src/main/java/com/ocrweb/controlplane/task/web/OcrTaskController.java)
- 内部回调控制器：[`InternalTaskCallbackController.java`](/D:/Code/work/OCR-WEB-main/java-control-plane/src/main/java/com/ocrweb/controlplane/task/web/InternalTaskCallbackController.java)

当前 Java 控制面已经覆盖：

- 上传提交
- 路径提交
- 任务列表 / 文件夹列表 / 进度
- 任务搜索
- 任务详情
- 任务结果编辑保存
- 任务删除
- 结果导出
- 原始文件访问
- 缩略图 / PDF 页预览代理
- 规则字段提取 / AI 字段提取代理
- 批次整合 / 边界分析 / QA / 评测代理
- Worker 内部状态回调
- 人工审查续跑入口

### 控制面保护

- `/internal/api/v1/**` 继续使用 `OCR_INTERNAL_API_TOKEN` 做内部回调鉴权
- `/api/**` 默认要求携带 `Authorization` 或 `Cookie`，可通过 `OCR_REQUIRE_USER_AUTH=false` 关闭
- 高成本接口启用了内存级限流：
  - 上传
  - 批次 AI
  - 缩略图 / PDF 预览
- AI 代理链加入了轻量熔断：
  - 连续失败达到 `OCR_AI_CIRCUIT_FAILURE_THRESHOLD` 后短暂打开熔断
  - 打开期间直接返回 `503`
  - 超时返回 `504`
- 上游不可达返回 `502`

### Trace 贯通

- 控制面会自动生成或透传 `X-Trace-Id`
- Java 提交 MQ 命令时会复用当前请求 trace，并写入消息里的 `trace_id`
- Python Worker 回调 `events/completion/failure` 时可继续复用同一条 `trace_id`
- Python Worker 回调 `pause`、后续 `resume` 命令也会延续同一个 `trace_id`
- 控制面响应也会带回 `X-Trace-Id`，便于前端、Java、Python 三端串联排障

常用开关：

- `OCR_REQUIRE_USER_AUTH`
- `OCR_RATE_LIMIT_ENABLED`
- `OCR_RATE_LIMIT_WINDOW_SECONDS`
- `OCR_RATE_LIMIT_UPLOAD_MAX_REQUESTS`
- `OCR_RATE_LIMIT_BATCH_AI_MAX_REQUESTS`
- `OCR_RATE_LIMIT_PREVIEW_MAX_REQUESTS`
- `OCR_AI_BASE_URL`
- `OCR_AI_CONNECT_TIMEOUT_SECONDS`
- `OCR_AI_READ_TIMEOUT_SECONDS`
- `OCR_AI_CIRCUIT_FAILURE_THRESHOLD`
- `OCR_AI_CIRCUIT_OPEN_SECONDS`

### 启动

```powershell
cd D:\Code\work\OCR-WEB-main\java-control-plane
mvn spring-boot:run
```

## 当前迁移策略

- 现有 Python `app/domains/`、`app/extraction/`、[`app/services/agent_ocr_workflow.py`](/D:/Code/work/OCR-WEB-main/app/services/agent_ocr_workflow.py) 保持不拆、不改规则
- Python Web 侧已经收敛为 AI API，不再承载业务/控制面职责
- Web 侧已经不再启动本地 `asyncio.Queue`
- 任务生产入口以 Java 控制面为准，Python 旧上传接口仅保留 AI 兼容能力
