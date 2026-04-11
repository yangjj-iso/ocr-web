# 档案自动化著录系统 — 差距分析与实施方案

## 一、现有项目能力盘点

### ✅ 已实现
| 需求项 | 现有实现 | 所在模块 |
|--------|---------|---------|
| OCR引擎集成 | PaddleOCR + Baidu VL 两种模式 | `app/ocr/`, Worker |
| 字段自动提取 | 规则引擎（评分卡）+ LLM（MiniMax）双轨提取 | `app/services/excel_export.py`, `llm_field_extraction_service.py` |
| 8大标准字段 | 档号/文号/责任者/题名/日期/页数/密级/备注 | `extract_fields()` |
| 档号解析 | 从文件名+路径自动解析 WS·2024·D10-0311 | `_extract_archive_number()` |
| Excel导出 | 归档文件目录.xlsx 标准表头 | `excel_export.py`, Java `ArchiveRecordService.exportRecords()` |
| Excel导入 | 模板Excel目录导入 | Java `ArchiveRecordService.importRecords()` |
| 批次处理 | 批量上传→OCR→合并→提取→导出 | `batch_merge_extraction_service.py` |
| 文档边界检测 | 基于视觉哈希+规则+LLM的智能分件 | `image_sequence_pdf.py`, `batch_merge` |
| 简单PDF合并 | 图片序列→PDF（单层，非双层） | `save_group_as_pdf()` |
| 角色控制 | admin/operator/searcher 三角色 | `app/core/auth.py`, `admin_users.py` |
| 操作日志 | 管理操作审计记录 | `_write_log()`, `operation_logs` 表 |
| 基础搜索 | 文件名/正文关键词搜索 | `SearchPage.vue`, `/tasks/search` API |
| 文件夹扫描 | 扫描本地目录获取图片列表 | Java `scanFolder()` |
| 微服务架构 | Java控制面(8080)+Python AI(8001)+Worker+Vue前端(3000) | 全栈 |
| Docker中间件 | PostgreSQL/Redis/RabbitMQ/MinIO | `compose.middleware.yaml` |

### 🟡 部分实现（需增强）
| 需求项 | 现状 | 差距 |
|--------|------|------|
| 存放路径 | DB有`storage_path`字段，但未自动生成 | 需根据档号自动生成 `/WS/2024/D10/0001` |
| 日期格式 | 当前 YYYY-MM-DD | 甲方要求 YYYYMMDD（整数格式） |
| 全文检索 | 简单 LIKE 查询 | 需 GIN 索引+分词+高亮+筛选 |
| 批量编辑 | 无 | 需支持批量替换/补全责任者、密级等 |
| 页数计算 | 单页图片=1，合并文档已统计 | 基本满足，需确保准确 |

### ❌ 未实现
| 需求项 | 优先级 | 复杂度 |
|--------|--------|--------|
| **5级文件夹自动创建**（根/类别/年度/期限/件号） | P0 | 中 |
| **图片批量挂接**（自动归入对应件号文件夹） | P0 | 中 |
| **路径回写**（存储路径写入著录目录） | P0 | 低 |
| **归档章自动识别**（首页归档章→分件依据） | P1 | 高 |
| **双层PDF生成**（图片+隐藏文字层，可搜索） | P1 | 高 |
| **全文索引构建**（PostgreSQL GIN + 中文分词） | P1 | 高 |
| **关键词高亮** | P1 | 中 |
| **高级筛选**（年度/期限/文号/关键词组合） | P1 | 中 |
| **搜索结果→文件夹定位** | P2 | 低 |
| **CSV导出** | P2 | 低 |
| **批量字段编辑 UI** | P2 | 中 |

---

## 二、分阶段实施方案

### Phase 1：著录字段完善与数据规范化（1-2周）
**目标**：确保所有字段符合甲方规范，补齐存放路径自动生成

#### 1.1 存放路径自动生成
- **逻辑**：从档号 `WS·2024·D10-0001` 解析生成 `/WS/2024/D10/0001`
- **改动点**：
  - `excel_export.py` → `extract_fields()` 新增 `存放路径` 字段
  - Java `ArchiveRecordEntity` 已有 `storagePath`，确保回写
  - 前端著录表增加存放路径列展示

#### 1.2 日期格式规范化
- **逻辑**：内部存储 YYYYMMDD 整数格式，显示时可转换
- **改动点**：`extract_fields()` 中日期输出格式从 `YYYY-MM-DD` → `YYYYMMDD`

#### 1.3 批量字段编辑 API
- **逻辑**：支持选中多条记录批量更新 责任者/密级/备注
- **改动点**：
  - Java `ArchiveController` 新增 `PUT /api/ocr/archive-records/batch-update`
  - 前端著录表增加多选+批量编辑按钮

#### 1.4 字段长度与类型校验
- 对照甲方规范（文号≤100，责任者≤200，题名≤500 等）检查现有约束
- Java `ArchiveRecordEntity` 已有长度限制，需与规范对齐

---

### Phase 2：文件夹自动生成与路径回写（1-2周）
**目标**：实现5级目录结构自动创建、图片自动归档

#### 2.1 5级文件夹自动创建
- **输入**：档号 `WS·2024·D10-0001` + 根目录（可配置）
- **输出**：创建 `D:\档案\WS\2024\D10\0001\`
- **改动点**：
  - Java/Python 新增 `FolderService.ensureFolderStructure(archiveNo, rootDir)`
  - 批处理完成后自动触发文件夹创建

#### 2.2 图片批量挂接（归入文件夹）
- **逻辑**：根据档号将扫描图片复制/移动到对应件号文件夹
- **改动点**：
  - 新增 API `POST /api/ocr/archive-records/organize-files`
  - 根据 file_path → 解析档号 → 移入目标文件夹

#### 2.3 路径回写
- **逻辑**：文件归档后将 `storage_path` 写入 `archive_records` 表
- **改动点**：organize-files 完成后自动回写

#### 2.4 归档章识别（增强分件）
- **逻辑**：检测首页归档章（特征：全宗号/年度/件号/保管期限标签）
- **现有基础**：`_looks_like_archive_stamp_code()` 已能检测归档章文本
- **改动点**：将归档章检测集成到边界引擎，作为文档首页信号

---

### Phase 3：全文检索增强（2-3周）
**目标**：建立真正的全文索引，支持高级筛选和关键词高亮

#### 3.1 PostgreSQL 全文索引
- **方案**：使用 `pg_trgm` + `tsvector` (中文用 `zhparser` 或 `pg_jieba` 扩展)
- **改动点**：
  - 新建 `fulltext_index` 表：`task_id, archive_no, full_text_tsvector`
  - OCR 完成后自动建立索引记录
  - 新增 GIN 索引

#### 3.2 高级搜索 API
- **改动点**：
  - `GET /api/ocr/search` 支持参数：`q`(关键词), `year`, `retention`(D10/D30), `doc_no`, `responsible`
  - 返回结果包含 `highlights`（匹配片段高亮）

#### 3.3 搜索结果展示增强
- **前端改动**：
  - 增加左侧筛选面板（年度、保管期限、密级下拉）
  - 搜索结果中高亮关键词（`<mark>` 标签）
  - 显示存放路径，点击可定位到文件夹

---

### Phase 4：双层PDF生成（1-2周）
**目标**：生成可检索的双层PDF文件

#### 4.1 双层PDF引擎
- **技术方案**：使用 `reportlab` + `PyMuPDF(fitz)` 在图片上叠加透明文字层
- **改动点**：
  - 新增 `app/utils/searchable_pdf.py`
  - 输入：图片路径列表 + OCR文字坐标
  - 输出：双层PDF（图像层+透明文字层）

#### 4.2 命名规范
- 命名格式：`WS·2019-D10-0001.pdf`
- 从档号自动生成

#### 4.3 批量导出
- **改动点**：
  - `POST /api/ocr/archive-records/export-pdf` 批量生成
  - 前端增加「导出双层PDF」按钮

---

### Phase 5：安全与管理增强（1周）
**目标**：完善权限控制和审计

#### 5.1 角色权限细化
- 现有：admin/operator/searcher
- 对应甲方：管理员/著录员/检索者
- **改动**：增加「审核员(reviewer)」角色，可审核但不可修改

#### 5.2 审计日志完善
- 现有 `operation_logs` 已覆盖管理操作
- **改动**：增加搜索操作日志、著录修改日志

#### 5.3 多格式导出
- **改动**：增加 CSV 导出选项
- Java `ArchiveRecordService` 增加 `exportRecordsCsv()`

---

## 三、技术栈确认

| 组件 | 技术 |
|------|------|
| 后端控制面 | Java Spring Boot 3 |
| AI/OCR服务 | Python FastAPI + PaddleOCR |
| 消息队列 | RabbitMQ |
| 数据库 | PostgreSQL 16 |
| 全文检索 | PostgreSQL GIN + pg_trgm (或 Elasticsearch 备选) |
| 双层PDF | ReportLab + PyMuPDF |
| 前端 | Vue 3 + TailwindCSS |
| 对象存储 | MinIO (可选) |

## 四、风险与依赖

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 中文全文检索分词质量 | 检索准确率 | 先用 pg_trgm 三元组模糊匹配，后期可升级 Elasticsearch |
| 双层PDF坐标对齐 | PDF文字层与图像不重合 | 使用OCR返回的bbox精确定位 |
| 大量图片文件移动 | 磁盘IO/中断风险 | 先复制后删除，支持断点续传 |
| 归档章种类多样 | 识别准确率 | 结合表格检测+文本特征，逐步积累模式库 |
