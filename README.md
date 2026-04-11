# OCR 文档识别归档系统

> 面向人社档案、文书归档与批量材料整理场景的**本地化文档识别系统**。
> 基于 PaddleOCR 3.x，集成三种识别能力（基础 OCR / 版面解析 / 视觉语言模型），
> 支持图片 & PDF 识别、批量导入、LLM 智能字段提取、合并文档归档导出与全文检索。

---

## 系统架构

```
┌──────────────┐       ┌───────────────────┐       ┌──────────────────┐
│   Vue 3 前端  │──────▶│  Java 控制面 :8080  │──────▶│ Python AI API    │
│   Vite :3000  │◀──────│  (Spring Boot)     │◀──────│ :8001 (FastAPI)  │
└──────────────┘       └────────┬──────────┘       └────────┬─────────┘
                                │ RabbitMQ                   │
                                ▼                            ▼
                       ┌────────────────┐          ┌─────────────────┐
                       │  Python Worker  │          │  LLM (MiniMax)  │
                       │  (OCR 计算)     │          │  字段提取 / QA   │
                       └────────────────┘          └─────────────────┘
```

| 层级 | 职责 |
|------|------|
| **Java 控制面** | 认证、上传、任务生命周期、RabbitMQ 投递、状态查询、文件代理 |
| **Python AI API** | AI 批次分析、LLM 字段提取、合并文档导出、QA、评测 |
| **Python Worker** | PaddleOCR、Vision LLM、LangGraph、规则引擎、Prometheus 指标 |
| **前端** | Vue 3 + TailwindCSS + Vite，工作台 / 结果页 / 搜索页 |

详细拆分说明见 [`docs/control-plane-compute-plane.md`](./docs/control-plane-compute-plane.md)。

---

## 技术栈

| 组件 | 技术 |
|------|------|
| OCR 引擎 | PaddleOCR 3.x + PaddlePaddle（CPU / GPU） |
| 视觉语言模型 | PaddleOCR-VL-1.5 / 百度 AI Cloud API |
| 版面分析 | PP-StructureV3 (17 类版面检测 + 表格识别) |
| LLM 智能提取 | MiniMax-M2.7（OpenAI 兼容接口，可切换 Ollama / vLLM） |
| 控制面 | Java 21 + Spring Boot 3.3 |
| AI API | Python 3.13 + FastAPI + Uvicorn |
| 数据库 | PostgreSQL 14+ (asyncpg) |
| 缓存 | Redis |
| 消息队列 | RabbitMQ |
| 对象存储 | MinIO (S3 兼容) |
| 前端 | Vue 3 + Vite + TailwindCSS |
| Excel | openpyxl |
| PDF | PyMuPDF (fitz) |

---

## 核心功能

| 功能 | 说明 |
|------|------|
| 三模型识别 | VL / 版面解析 / 基础 OCR，前端一键切换 |
| 批量文件夹识别 | 选择本地文件夹上传，或输入服务器路径递归扫描 |
| 合并文档归档导出 | 多页自动分组为逻辑文档，LLM 提取归档字段，导出 Excel |
| 全文搜索 | 关键词全文匹配，返回高亮片段 |
| 批次智能整合 | 同文档分组 + 推荐字段 + 冲突项核对 |
| 批次质量概览 | 分组质量、一致性、字段覆盖统计 |
| 批次知识问答 | 基于批次材料的证据可追溯 QA |
| 版面解析 + 表格 | 17 类版面检测，表格转 HTML 还原行列 |
| Bbox 区块高亮 | 点击区块在源图上高亮检测框 |
| Redis 多级缓存 | 任务详情、列表、搜索结果缓存，Redis 不可用时降级 |

---

## 项目结构

```
D:\OCR_WEB\ocr\
├── .env                           # 本地环境变量（git 忽略）
├── .env.example                   # 环境变量模板
├── compose.middleware.yaml        # Docker 中间件（PG/RabbitMQ/Redis/MinIO）
├── requirements.txt               # Python 依赖
├── app/
│   ├── main_ai.py                 # Python AI API 入口
│   ├── main_worker.py             # Python Worker 入口
│   ├── api/                       # REST API 路由层
│   │   ├── ai_batches.py          #   AI 批次路由（合并抽取/导出）
│   │   ├── tasks.py               #   任务 CRUD
│   │   ├── qa.py                  #   知识问答
│   │   └── evaluation.py          #   评测
│   ├── application/workflows/     # 业务编排层
│   ├── domains/                   # 领域服务层
│   ├── services/                  # 基础服务层
│   │   ├── batch_merge_extraction_service.py  # 合并文档抽取+导出
│   │   ├── llm_field_extraction_service.py    # LLM 字段提取
│   │   └── ocr_service.py                     # OCR 业务逻辑
│   ├── core/                      # 基础设施（OCR 引擎/缓存/认证）
│   ├── db/                        # 数据库连接 & ORM
│   └── infrastructure/queue/      # RabbitMQ 消费者
├── java-control-plane/            # Java 控制面 (Spring Boot)
│   ├── src/main/java/com/ocrweb/controlplane/
│   │   ├── task/                  #   任务管理 & AI 代理
│   │   └── storage/               #   MinIO 存储
│   └── pom.xml
├── frontend/                      # Vue 3 前端
│   ├── src/
│   │   ├── features/              #   页面模块（workbench/result/search）
│   │   ├── composables/           #   组合式函数（useBatchUpload 等）
│   │   ├── api/ocr.js             #   API 调用封装
│   │   └── utils/                 #   工具函数
│   └── package.json
├── scripts/                       # 运维/工具脚本
├── docs/                          # 详细设计文档
└── tests/                         # 测试用例
```

---

## 快速启动

### 前置条件

| 依赖 | 版本要求 |
|------|----------|
| Docker Desktop | 已安装并启动 |
| Python | 3.13+（`D:\python 3.13`） |
| Java JDK | 21+ |
| Node.js | 18+ |
| Maven | 3.9+（`D:\apache-maven-3.9.11-bin`） |

### 第 1 步：配置环境变量

```powershell
# 复制模板并编辑
copy .env.example .env
# 必须配置：DATABASE_URL、LLM_API_KEY、BAIDU_API_KEY
```

> `.env` 文件按分组整理，详见文件内注释。**不要提交到 Git**。

### 第 2 步：启动 Docker 中间件

```powershell
cd D:\OCR_WEB\ocr
docker compose -f compose.middleware.yaml up -d
```

首次运行需初始化 MinIO bucket：
```powershell
docker compose -f compose.middleware.yaml --profile setup run --rm minio-init
```

验证：`docker ps` 应看到 4 个容器（ocr-postgres / ocr-rabbitmq / ocr-redis / ocr-minio）。

### 第 3 步：启动 Java 控制面（:8080）

```powershell
cd D:\OCR_WEB\ocr\java-control-plane
java -jar target\java-control-plane-0.0.1-SNAPSHOT.jar
```

> 如需重新编译：`& "D:\apache-maven-3.9.11-bin\apache-maven-3.9.11\bin\mvn.cmd" package -DskipTests -q`

验证：http://localhost:8080/api/health

### 第 4 步：启动 Python AI API（:8001）

```powershell
cd D:\OCR_WEB\ocr
python -m app.main_ai
```

验证：http://localhost:8001/api/health

### 第 5 步：启动 Python Worker

**不启动 Worker，上传的文件会永远卡在"处理中"。**

```powershell
cd D:\OCR_WEB\ocr
python -m app.main_worker
```

验证：`docker exec ocr-rabbitmq rabbitmqctl list_queues name messages consumers`
→ `ocr.task.command.queue` 的 consumers 应 ≥ 1。

### 第 6 步：启动前端（:3000）

```powershell
cd D:\OCR_WEB\ocr\frontend
npm run dev
```

访问：http://localhost:3000

### 服务端口汇总

| 服务 | 端口 | 说明 |
|------|------|------|
| 前端 Vite | 3000 | 开发服务器 |
| Java 控制面 | 8080 | API 网关、任务管理 |
| Python AI API | 8001 | AI 分析、字段提取 |
| PostgreSQL | 5432 | 数据库 |
| RabbitMQ | 5672 / 15672 | 消息队列 / 管理界面 |
| Redis | 6379 | 缓存 |
| MinIO | 9000 / 9001 | 对象存储 / 控制台 |
| Worker Metrics | 9108 | Prometheus 指标 |

---

## REST API 概览

### Java 控制面 (:8080)

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ocr/upload` | 上传文件并创建识别任务 |
| GET | `/api/ocr/tasks` | 任务列表（分页、文件夹过滤） |
| GET | `/api/ocr/tasks/{id}` | 任务详情 |
| PUT | `/api/ocr/tasks/{id}` | 更新识别结果 |
| DELETE | `/api/ocr/tasks/{id}` | 删除任务 |
| GET | `/api/ocr/tasks/{id}/file` | 获取源文件 |
| GET | `/api/ocr/tasks/folders` | 历史文件夹分组 |
| GET | `/api/ocr/tasks/search?q=...` | 全文搜索 |
| GET | `/api/ocr/scan-folder?path=...` | 扫描服务器文件夹 |

### Python AI API (:8001) — 经 Java 控制面代理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ocr/tasks/{id}/ai-extract-fields` | 单任务 LLM 字段提取 |
| POST | `/api/ocr/batches/{batchId}/ai-merge-extract` | 合并文档字段提取 |
| GET | `/api/ocr/batches/{batchId}/ai-merge-export` | 合并文档归档 Excel 导出 |
| GET | `/api/ocr/batches/{batchId}/boundary-analysis` | 文档边界分析 |
| POST | `/api/ocr/batches/{batchId}/qa/ask` | 批次知识问答 |

---

## 数据库表

### `ocr_tasks`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 主键 |
| filename | VARCHAR | 原始文件名 |
| file_path | VARCHAR | 存储路径 |
| batch_id | VARCHAR | 批次 ID |
| file_type | VARCHAR | .jpg / .pdf 等 |
| mode | VARCHAR | vl / layout / ocr |
| status | VARCHAR | pending / processing / done / failed |
| result_json | JSONB | 完整识别结果 |
| full_text | TEXT | 识别全文 |
| page_count | INTEGER | 页数 |
| error_message | TEXT | 错误信息 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

---

## 使用流程

1. 打开 http://localhost:3000，选择识别模型
2. 选择文件夹上传或输入服务器路径批量导入
3. 等待 Worker 完成 OCR 识别
4. 进入结果页查看识别内容，左侧切换文件
5. 系统自动按合并文档分组，LLM 提取归档字段
6. 点击「导出」下载归档 Excel（档号 / 文号 / 责任者 / 题名 / 日期 / 页数 / 密级 / 备注）

---

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| 任务卡在"处理中" | 检查 Worker 是否启动：`docker exec ocr-rabbitmq rabbitmqctl list_queues` |
| LLM 字段提取 503 | 检查 `.env` 中 `LLM_API_KEY` 是否配置 |
| 前端 404 / 连接错误 | 确认 Java 控制面 (:8080) 和 AI API (:8001) 在运行 |
| 中文路径无法读取 | 已内置 numpy+imdecode 兼容，无需额外处理 |
| 批量识别内存溢出 | 已内置大图自动缩放（>2500px），每任务后 GC + GPU 缓存清理 |
| Worker 启动 ModuleNotFoundError | `pip install -r requirements.txt` |

---

## LangGraph Studio（可选）

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start_langgraph_studio.ps1 -NoBrowser
```

- 健康检查：http://127.0.0.1:8123/health/live
- 工作流可视化：http://127.0.0.1:8123/studio/flow

---

## 更多文档

- [控制面/计算面拆分说明](./docs/control-plane-compute-plane.md)
- [Docker 中间件说明](./docs/docker-middleware.md)
- [LangGraph 流程图](./docs/langgraph-flow.md)
- [服务拆分说明](./docs/service-split.md)
- [更新日志](./CHANGELOG.md)
