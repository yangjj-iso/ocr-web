# OmniScan · 智能文档识别平台

上传文档，AI 自动完成识别与结构化抽取。面向人社档案、文书归档与批量材料整理场景的本地化文档识别系统。

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Next.js 前端 (port 3000)                   │
│         React 19 · shadcn/ui · Framer Motion · Tailwind      │
└────────────────────────────┬────────────────────────────────┘
                             │ /api/* 代理
┌────────────────────────────▼────────────────────────────────┐
│              Java 控制面 (Spring Boot, port 8080)              │
│    认证 · 任务管理 · 归档 · 批次分析 · MQ 投递 · MinIO 存储    │
└────────────────────────────┬────────────────────────────────┘
                             │ RabbitMQ
┌────────────────────────────▼────────────────────────────────┐
│              Python 计算面 (FastAPI, port 8001)                │
│     PaddleOCR · Vision LLM · LangGraph · 规则引擎 · GPU       │
└─────────────────────────────────────────────────────────────┘
```

| 层 | 技术栈 |
|---|---|
| 前端 | Next.js 15 · React 19 · TypeScript · Tailwind CSS · shadcn/ui · Framer Motion |
| 控制面 | Java 17 · Spring Boot 3 · PostgreSQL · Redis · RabbitMQ · MinIO |
| 计算面 | Python 3.12 · FastAPI · PaddleOCR 3.x · PaddlePaddle · LangGraph |

---

## 核心功能

- **三模型识别** — VL 视觉语言模型 / 版面解析 / 基础文字识别，前端一键切换
- **批量文件夹识别** — 拖拽上传或输入服务器路径递归扫描
- **归档 Excel 自动写入** — 识别完成后自动提取档号、文号、责任者等字段
- **全文搜索** — 按关键词搜索已识别文档，返回高亮片段
- **批次智能整合** — 同文档分组，输出推荐字段与冲突项
- **批次知识问答** — 基于批次材料做证据可追溯问答
- **版面解析 + 表格识别** — 17 类版面检测，表格转 HTML
- **组织架构管理** — 用户注册审批、管理员权限分配
- **Cookie 会话认证** — 可选开启，支持多用户隔离

---

## 项目结构

```
OCR-WEB-main/
├── frontend-next/              # Next.js 前端（主力）
│   ├── app/                    # App Router 页面
│   │   ├── page.tsx            # 首页
│   │   ├── workbench/          # 工作台（上传 + 批量识别）
│   │   ├── chat/               # 问答台
│   │   ├── search/             # 信息检索
│   │   ├── org/                # 组织架构管理
│   │   ├── result/[id]/        # 识别结果详情
│   │   ├── batch-insights/     # 批次分析
│   │   ├── login/              # 登录
│   │   └── register/           # 注册
│   ├── components/             # UI 组件
│   ├── hooks/                  # 业务 hooks
│   ├── api/                    # Axios API 层
│   └── lib/                    # 工具函数
├── java-control-plane/         # Java Spring Boot 控制面
│   └── src/main/java/com/ocrweb/controlplane/
│       ├── auth/               # 认证模块
│       ├── task/               # 任务管理
│       ├── batch/              # 批次分析
│       └── archive/            # 归档管理
├── app/                        # Python 计算面
│   ├── main_ai.py              # AI API 入口
│   ├── main_worker.py          # 计算 Worker
│   └── core/ocr_engine.py      # OCR 引擎
├── frontend/                   # 旧 Vue 前端（保留参考）
└── scripts/                    # 工具脚本
```

---

## 快速启动

### 环境要求

- Node.js 18+
- Java 17+
- Python 3.10–3.12
- PostgreSQL 14+
- Redis
- MinIO（S3 兼容存储）
- NVIDIA GPU + CUDA 12.x（推荐）

### 1. 前端

```bash
cd frontend-next
npm install
npm run dev        # http://localhost:3000
```

### 2. Java 控制面

```bash
cd java-control-plane
mvn spring-boot:run    # http://localhost:8080
```

默认 `AUTH_ENABLED=false`，所有接口无需登录即可访问。设置 `AUTH_ENABLED=true` 启用认证。

### 3. Python 计算面

```bash
# AI API
.venv/Scripts/python app/main_ai.py     # http://localhost:8001

# Worker（消费 RabbitMQ 任务）
.venv/Scripts/python app/main_worker.py
```

### 4. 访问

| 地址 | 说明 |
|---|---|
| http://localhost:3000 | 前端 |
| http://localhost:8080/swagger-ui.html | 控制面 API 文档 |
| http://localhost:8001/docs | 计算面 API 文档 |

---

## 前端页面

| 路由 | 功能 |
|---|---|
| `/` | 首页，功能入口导航 |
| `/workbench` | 工作台 — 文件上传、批量识别、进度追踪、历史记录 |
| `/chat` | 问答台 — 基于文档的智能问答（待接入 RAG） |
| `/search` | 信息检索 — 全文搜索 + 字段过滤 |
| `/result/:id` | 识别结果 — 原文预览 + OCR 文本 + 区域高亮 |
| `/batch-insights/:batchId` | 批次分析 — 智能整合、质量评估、边界分析、知识问答 |
| `/org` | 组织架构 — 用户审批、管理员管理（需管理员权限） |
| `/login` | 登录 |
| `/register` | 注册申请 |

---

## API 概览

### 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/auth/me` | 当前认证状态 |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/auth/users` | 用户列表（管理员） |
| POST | `/api/auth/users/:id/approve` | 审批通过 |
| POST | `/api/auth/users/:id/reject` | 审批拒绝 |

### OCR 任务

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/ocr/upload` | 上传文件识别 |
| POST | `/api/ocr/upload-from-path` | 按服务器路径识别 |
| GET | `/api/ocr/scan-folder` | 扫描文件夹 |
| GET | `/api/ocr/tasks` | 任务列表（分页 + 过滤） |
| GET | `/api/ocr/tasks/:id` | 任务详情 |
| PUT | `/api/ocr/tasks/:id` | 更新任务 |
| DELETE | `/api/ocr/tasks/:id` | 删除任务 |
| GET | `/api/ocr/tasks/search` | 全文搜索 |
| POST | `/api/ocr/tasks/:id/ai-extract-fields` | AI 字段提取 |

### 批次分析

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/ocr/batches/:id/ai-merge-extract` | 智能整合 |
| GET | `/api/ocr/batches/:id/evaluation-metrics` | 质量评估 |
| GET | `/api/ocr/batches/:id/boundary-analysis` | 边界分析 |
| POST | `/api/ocr/batches/:id/qa` | 知识问答 |

---

## 认证机制

- Cookie 会话认证（`ocr_session`，HttpOnly，SameSite=Lax，8 小时有效）
- 默认关闭（`AUTH_ENABLED=false`），所有接口直接可用
- 开启后支持：注册申请 → 管理员审批 → 正常使用
- 前端通过 Next.js rewrites 代理到后端，Cookie 自动透传

---

## 集成模型

| 模型 | 用途 |
|---|---|
| PaddleOCR-VL-1.5 | 视觉语言理解，识别质量最佳 |
| RT-DETR-H_layout_17cls | 17 类版面检测 |
| SLANet_plus | 表格结构识别 |
| PP-OCRv4/v5 server | 文字检测与识别 |
| LangGraph | 多步骤 AI 工作流编排 |

---

## 开发说明

```bash
# 前端构建
cd frontend-next && npm run build

# 前端类型检查
cd frontend-next && npx tsc --noEmit

# Java 构建
cd java-control-plane && mvn package -DskipTests
```

### 环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `AUTH_ENABLED` | `false` | 是否启用认证 |
| `OCR_STORAGE_BACKEND` | `s3` | 存储后端（s3/local） |
| `NEXT_PUBLIC_API_BASE_URL` | （空，使用同源代理） | 前端 API 地址 |

---

## License

Private — 内部使用。
