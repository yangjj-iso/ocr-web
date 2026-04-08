# OCR 文档识别归档系统

## 项目简介

本项目是面向人社档案、文书归档与批量材料整理场景的本地化文档识别系统。基于 **PaddleOCR 3.x**，集成三种识别能力（基础 OCR、版面解析、视觉语言模型），支持图片/PDF 识别、批量导入、结构化提取、结果核对、归档导出与全文检索。

系统采用 **Vue 3 + FastAPI + PostgreSQL + Redis** 技术栈，支持内网部署，识别链路与数据存储在本地完成。

当前仓库已支持两种后端运行方式：

- `app/main.py`：单体兼容模式，业务接口与 AI 接口一起启动
- `app/main_business.py` + `app/main_ai.py`：拆分模式，分别启动业务服务和 AI 文档服务

### 对外汇报口径（甲方版）

系统主链路为本地部署，材料从导入、识别、校核到归档都在本地闭环完成。外部增强能力仅作可选项，可按策略关闭，不影响本地核心流程。

---

## 核心能力

| 能力 | 说明 |
|------|------|
| **三模型识别** | VL 视觉语言模型 / 版面解析 / 基础文字识别，前端一键切换 |
| **批量文件夹识别** | 支持直接选择本地文件夹上传，或输入服务器路径递归扫描并批量识别 |
| **识别历史按文件夹分组** | 首页历史按源目录聚合显示，点击目录直接进入该批次结果 |
| **文件夹级历史删除** | 历史列表支持按文件夹批量删除识别记录 |
| **结果页文件侧边栏** | 进入目录后左侧显示当前文件夹全部文件，可快速切换查看 |
| **识别结果目录导出** | 批量识别时自动将 JSON + TXT 结果保存到指定目录 |
| **归档 Excel 自动写入** | 识别完成后自动提取档号、文号、责任者、题名、日期、页数、密级等字段写入 Excel，支持“目录或文件路径”两种输入 |
| **全文搜索** | 在已识别文档中按关键词搜索，支持文本、表格、JSON 全匹配，返回高亮片段 |
| **批次智能整合（可选）** | 按批次识别同文档分组，输出推荐字段与冲突项，便于人工核对 |
| **批次质量概览（可选）** | 提供分组质量、一致性、字段覆盖等统计结果，支撑运营评估 |
| **批次知识问答（可选）** | 基于批次材料做证据可追溯问答，回答附来源片段与材料定位 |
| **版面解析 + 表格识别** | 17 类版面检测，表格转 HTML 渲染，还原行列结构 |
| **Bbox 区块高亮** | 点击识别区块在源图上高亮对应检测框，支持编辑保存 |
| **PDF 预览** | iframe 内嵌浏览器原生 PDF 预览，识别结果连续滚动展示 |
| **Redis 缓存** | 任务详情、列表、搜索结果多级缓存，显著提升响应速度 |
| **大图自动缩放** | 超大图片自动缩放后再送入 OCR，防止显存溢出 |
| **中文路径支持** | 使用 numpy+imdecode 读写图片，解决 OpenCV 中文路径问题 |

---

## 技术栈

| 组件 | 技术 |
|------|------|
| OCR 引擎 | PaddleOCR 3.x + PaddlePaddle GPU |
| 视觉语言模型 | PaddleOCR-VL-1.5 |
| 版面分析 | PP-StructureV3 (PaddleX layout_parsing) |
| 后端框架 | FastAPI + Uvicorn (Python 3.12) |
| 数据库 | PostgreSQL + SQLAlchemy (asyncpg 异步) |
| 缓存 | Redis (redis-py) |
| 前端 | Vue 3 + Vite + TailwindCSS + Axios |
| Excel 导出 | openpyxl |
| PDF 处理 | PyMuPDF (fitz) |
| GPU 加速 | NVIDIA CUDA 12.x |

---

## 集成模型

| 模型 | 用途 | 管线 |
|------|------|------|
| PaddleOCR-VL-1.5 | 视觉语言理解，识别质量最佳 | VL |
| RT-DETR-H_layout_17cls | 17 类版面检测 | PP-StructureV3 |
| SLANet_plus | 表格结构识别 | PP-StructureV3 |
| PP-OCRv4_server_det/rec | 版面内文字检测识别 | PP-StructureV3 |
| PP-OCRv4_server_seal_det | 印章检测 | PP-StructureV3 |
| PP-LCNet_x1_0_doc_ori | 文档方向分类 | PP-StructureV3 |
| UVDoc | 文档校正展开 | PP-StructureV3 |
| PP-OCRv5_server_det/rec | 快速文字检测识别 | PP-OCRv5 |

---

## 项目结构

```
d:\OCR\
├── main.py                        # 后端 API 入口（FastAPI）
├── config.py                      # 配置（数据库、Redis、上传目录等）
├── requirements.txt               # Python 依赖
├── extract_fields.py              # 独立脚本：从数据库批量提取字段写入 Excel
├── check_tasks.py                 # 独立脚本：查询任务状态统计
├── app/
│   ├── api/                       # 分模块 REST API 路由
│   ├── bootstrap/                 # FastAPI 应用工厂与共享启动逻辑
│   ├── core/
│   │   ├── ocr_engine.py          # 三模型 OCR 引擎（含大图缩放/中文路径修复）
│   │   └── redis_cache.py         # Redis 缓存封装（get/set/invalidate）
│   ├── db/
│   │   ├── database.py            # 异步数据库连接
│   │   └── models.py              # ORM 模型（ocr_tasks 表）
│   ├── schemas/
│   │   └── ocr_schemas.py         # Pydantic 响应模型
│   ├── interfaces/api/v1/         # API 路由注册入口
│   ├── interfaces/api/business/   # 业务服务路由注册入口
│   ├── interfaces/api/ai/         # AI 服务路由注册入口
│   └── services/
│       ├── ocr_service.py         # OCR 业务逻辑（创建任务/运行/搜索）
│       └── excel_export.py        # 归档字段提取与 Excel 写入服务
├── frontend/                      # Vue 3 前端源码
│   ├── src/
│   │   ├── features/
│   │   │   ├── workbench/         # 工作台页（上传、批次入口、历史）
│   │   │   ├── result/            # 结果页与字段提取页
│   │   │   └── search/            # 全文搜索页
│   │   ├── router.js              # 前端路由入口
│   │   └── components/
│   │       ├── BufferZone.vue     # 批量上传区（文件/路径/Excel导出/结果目录）
│   │       └── HistoryList.vue    # 历史目录列表（分组查看/批量删除）
│   ├── dist/                      # 前端独立构建产物（执行 build 后生成）
│   └── package.json
├── uploads/                       # 上传文件存储（自动创建）
└── .cache/                        # 模型缓存目录（首次使用时自动下载）
```

---

## REST API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/ocr/upload?mode=vl\|layout\|ocr&excel_path=...&excel_init=1&output_dir=...` | 上传文件并识别；支持 `relative_path` 字段保留本地文件夹层级 |
| GET | `/api/ocr/scan-folder?path=...` | 扫描服务器本地文件夹，返回文件列表 |
| POST | `/api/ocr/upload-from-path?mode=vl&excel_path=...&excel_init=1&output_dir=...` | 按服务器路径识别，可自动写 Excel 和保存结果文件 |
| GET | `/api/ocr/tasks/folders` | 获取历史源文件夹分组列表 |
| GET | `/api/ocr/tasks?page=1&page_size=20&folder=...` | 任务列表（支持文件夹过滤，`page_size` 最大 1000） |

---

## 独立脚本：按图片序列重建 PDF

当扫描件被导出成连续图片时，可用 [`scripts/rebuild_pdfs_from_images.py`](/D:/Code/work/OCR-WEB-main/scripts/rebuild_pdfs_from_images.py) 自动按相邻页 pHash 差异切分逻辑文件，并为每组输出独立 PDF。

```powershell
.\.venv\Scripts\python.exe .\scripts\rebuild_pdfs_from_images.py D:\scans --output-dir D:\scans\rebuilt_pdfs --similarity-threshold 12
```

- `similarity_threshold` 推荐从 `8` 到 `15` 之间开始调。
- 数值越小越严格，越容易把相邻页切成多个文件。
- 数值越大越宽松，越容易把相近版式合并到同一个文件。
- 脚本默认同时参考 `pHash + 版式哈希 + 横纵投影轮廓`，不是只看单一指纹。
- 如果遇到“同类表格/证照版式太像”的批次，可再加 `--enable-ocr-text` 启用 OCR 文本辅助判断。
- 启用 OCR 辅助后，还可以用 `--text-similarity-threshold 0.35` 微调文本差异敏感度。
- 不确定阈值时，可直接加 `--auto-threshold`，脚本会根据相邻页差异自动给出并使用建议值。
- 如果需要复核切分过程，可加 `--report-json D:\scans\split_report.json` 导出结构化报告。
| GET | `/api/ocr/tasks/{id}` | 任务详情（Redis 缓存） |
| GET | `/api/ocr/tasks/search?q=关键词` | 全文搜索（Redis 缓存） |
| PUT | `/api/ocr/tasks/{id}` | 更新识别结果（编辑后保存） |
| GET | `/api/ocr/tasks/{id}/file` | 获取源文件（图片/PDF 预览） |
| GET | `/api/ocr/tasks/{id}/export?fmt=txt\|json` | 导出识别结果 |
| DELETE | `/api/ocr/tasks/{id}` | 删除任务 |
| DELETE | `/api/ocr/tasks/by-folder?folder=...` | 删除某个历史文件夹下的全部任务 |

---

## 数据库设计

### `ocr_tasks` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 主键 |
| filename | VARCHAR | 原始文件名 |
| file_path | VARCHAR | 服务器存储路径（本地路径保留原路径） |
| file_type | VARCHAR | 文件类型（.jpg/.pdf 等） |
| mode | VARCHAR | 使用的识别模型（vl/layout/ocr） |
| status | VARCHAR | pending / processing / done / failed |
| result_json | JSONB | 完整识别结果（含 regions/lines/bbox） |
| full_text | TEXT | 识别全文（用于搜索） |
| page_count | INTEGER | 页数 |
| error_message | TEXT | 错误信息 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |

---

## 快速启动

### 环境要求
- Python 3.10 ~ 3.12（不支持 3.13）
- PostgreSQL 14+
- Redis（本地 `D:\Redis\redis-server.exe`）
- Node.js 18+（前端开发）
- NVIDIA GPU + CUDA 12.x（推荐）

### 1. 安装依赖

```bash
# Python 后端
pip install -r requirements.txt

# 前端
cd frontend && npm install
```

### 2. 配置数据库

```bash
psql -U postgres -c "CREATE DATABASE ocr_db ENCODING 'UTF8';"
```

编辑 `config.py` 确认数据库密码与 Redis 地址。

### 3. 启动 Redis

```powershell
Start-Process "D:\Redis\redis-server.exe"
```

### 4. 启动后端

单体兼容模式：

```powershell
D:\OCR-WEB-main\.venv\Scripts\python.exe app\main.py
```

拆分模式：

```powershell
# 业务服务（鉴权 / 归档 / 扫描 / 批次建档）
D:\OCR-WEB-main\.venv\Scripts\python.exe app\main_business.py

# AI 文档服务（OCR / 文档边界识别 / QA / 评测）
D:\OCR-WEB-main\.venv\Scripts\python.exe app\main_ai.py
```

说明：

- `main.py` 适合本地开发和兼容现有部署。
- `main_business.py` 不启动 OCR worker。
- `main_ai.py` 会启动 OCR worker，并负责文档边界识别、批次整合、QA 和评测链路。
- Windows 环境下默认不启用热重载，避免重载子进程引用错误 Python 解释器导致服务异常。

### 5. 启动前端（端口 3000）

```powershell
cd D:\OCR\frontend
npm run dev -- --host 0.0.0.0 --port 3000
```

如需以前后端分离方式联调，可在 `frontend/.env.local` 中设置：

```text
VITE_API_BASE_URL=http://localhost:8000
```

### 6. 访问

- 前端开发环境：http://localhost:3000
- 后端 API 文档：http://localhost:8000/docs
- 前端生产构建目录：`frontend/dist`（由 Nginx 或任意静态文件服务托管）

---

## 批量识别与归档导出

### 前端操作流程

1. 打开 http://localhost:3000，选择识别模型（VL/版面解析/基础OCR）
2. 选择导入方式：
    - 点击 `选文件夹`，直接从资源管理器选择本地文件夹批量上传
    - 或在「文件夹路径」框输入服务器路径，例如 `D:\GOOLGE\软件著录\模版文件`，再点击「导入」
3. （可选）在「归档Excel路径」框输入目录或完整文件路径，例如 `D:\GOOLGE\软件著录` 或 `D:\GOOLGE\软件著录\归档文件目录.xlsx`
4. （可选）在「识别结果输出目录」框输入目录路径，识别后自动保存 `.json` + `.txt`
5. 点击「立即批量识别」，批次第一个成功任务会先清空 Excel 旧数据行，再写入当前批次结果
6. 首页「识别历史」按源文件夹分组显示，点击目录进入结果页，左侧侧边栏可切换当前目录下文件
7. 鼠标悬停历史目录可按文件夹批量删除记录
8. 纯 Web 前端受浏览器安全限制，当前仅“源文件夹”支持直接点选；`归档Excel路径` 与 `识别结果输出目录` 仍需手动输入真实路径

### 命令行提取字段写入 Excel

批量识别完成后，直接运行：

```powershell
D:\OCR\.venv\Scripts\python.exe D:\OCR\extract_fields.py
```

脚本会：
- 查询数据库中 `D:\GOOLGE\软件著录\模版文件` 路径下的所有已完成任务
- 提取档号、文号、责任者、题名、日期、页数、密级、备注
- 档号优先从文件名提取，并尽量保留完整编号，例如 `KJ-JJ-2017-02-001-025`、`WS·2024·D30-0156-001`
- 写入 `D:\GOOLGE\软件著录\归档文件目录（所需字段）.xls`

---

## Redis 缓存策略

| 缓存键 | TTL | 说明 |
|--------|-----|------|
| `task:{id}` | 1 小时 | 单任务详情缓存 |
| `list:{page}:{size}:{folder}` | 30 秒 | 任务列表缓存（含文件夹过滤） |
| `search:{q}:{page}:{size}` | 2 分钟 | 搜索结果缓存 |
| `folders` | 30 秒 | 历史文件夹分组缓存 |

上传/更新/删除操作会自动失效相关缓存。Redis 不可用时自动降级为直接查数据库。

---

## 常见问题

**Q: `RequestsDependencyWarning: urllib3...` 警告**  
A: 不影响运行，是 urllib3 版本兼容性提示，忽略即可。

**Q: CUDNN 版本不匹配警告**  
A: Paddle 编译版本与本机 CUDNN 版本差异导致，不影响识别功能，建议后续对齐版本。

**Q: 批量识别时内存溢出**  
A: 系统已内置大图自动缩放（超过 2500×2500 自动缩放），并在每个任务后执行 GC + GPU 缓存清理。

**Q: 中文文件夹路径无法读取？**  
A: 系统已使用 `numpy.fromfile + cv2.imdecode` 替代 `cv2.imread`，支持中文路径。

**Q: 归档 Excel 路径填目录还是文件？**  
A: 两种都支持。若填写目录如 `D:\GOOLGE\软件著录`，系统会自动写入 `D:\GOOLGE\软件著录\归档文件目录.xlsx`；若填写 `.xls`，会自动转换为 `.xlsx`。

**Q: 为什么现在导出的档号会保留末尾流水号？**  
A: 系统已将档号提取调整为优先保留完整文件编号，避免同一批 `KJ`/`WS` 文件仅因前缀相同而被误写成同一个档号。

**Q: 三个路径都能像资源管理器那样直接选择吗？**  
A: 目前纯 Web 前端只支持“源文件夹”通过 `选文件夹` 直接选择。本地 `归档Excel路径` 和 `识别结果输出目录` 需要后端拿到真实 Windows 路径，但浏览器默认不会暴露这类绝对路径，因此这两个字段仍需手动输入。

---

## 2026-04 Local Dev Baseline (Authoritative)

- Local backend entrypoint: `D:\OCR\.venv\Scripts\python.exe main.py`
- Do not mix system Python with `.venv` during local debugging.
- Local frontend build: `npm --prefix frontend run build` (outputs to `frontend/dist` by default).
- Frontend Docker image build command: `docker build -f frontend/Dockerfile .` (root context, Docker output uses `dist`).

### One-command local API sanity check

```powershell
powershell -ExecutionPolicy Bypass -File D:\OCR\scripts\selfcheck-local.ps1
```

Optional parameters:

```powershell
powershell -ExecutionPolicy Bypass -File D:\OCR\scripts\selfcheck-local.ps1 -BaseUrl http://localhost:8000 -TaskId 123 -BatchId batch_xxx
```
