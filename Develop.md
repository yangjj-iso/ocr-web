可以。我把你这个系统的**技术路线**按“目标 → 架构 → 核心流程 → 关键模块 → 实施阶段”梳理成一版，尽量贴近你现在的实际方向。你们当前讨论的业务边界，核心是先做**A4、规则明确的文书档案**，以**自动分件、自动排序、自动著录，人工校正兜底**为主。

# 一、总体目标

把你现有 OCR 系统，升级成一个**文书档案智能整理系统**。

第一阶段先解决这三件事：

* 整卷扫描后，自动分件
* 按规则自动排序，并支持人工校正
* 自动著录并生成目录

自动编号要放在**分件和排序基本确认后**，不能太早做。

---

# 二、整体技术路线一句话版

**Java 控制面 + Python 计算面 + MinIO 文件底座 + PostgreSQL 状态与结果存储 + Redis 队列/缓存 + LangGraph 编排 + OCR/版面/CV/LLM 混合处理 + 人工审核前端 + 双轨机制（Draft/Final）**

---

# 三、架构分层

## 1. 接入层

负责把文件送进系统。

包括：

* Web 前端
* 批量导入接口
* 扫描上传接口
* 批次管理

建议流程是：

**批量导入 → 文件进 MinIO → 建 batch/卷宗记录 → 进入工作流**

---

## 2. 控制面（Java）

负责“管理、治理、状态、权限、任务”。

建议放在 Java 的内容：

* 租户管理
* 用户/角色/权限
* 批次管理
* 工作流任务创建
* 规则管理与版本管理
* 人工审核任务管理
* Draft/Final 状态管理
* 返工任务与版本控制
* 导出任务管理
* 审计日志

Java 不负责重计算，负责“调度和业务控制”。

---

## 3. 计算面（Python）

负责“识别、推理、处理”。

建议放在 Python 的内容：

* 图像预处理
* OCR
* 版面识别
* pHash / 页面相似度
* 页面关系分析
* 自动分件
* 件级排序
* 自动编号
* 字段提取/著录
* 标签生成
* 保存期限判定
* 目录生成
* searchable PDF / 双层 PDF 导出
* 局部重跑

Python 是执行引擎。

---

## 4. 存储层

建议这样拆：

### MinIO

存：

* 原始文件
* 预处理后的页图
* 双层 PDF
* 导出结果
* 缩略图

### PostgreSQL

存：

* batch
* 卷宗 record
* page/doc/batch 结构化数据
* OCR/分件/排序/著录结果
* 审核任务
* 返工任务
* 规则快照
* 状态流转
* 审计日志

### Redis

存：

* 异步任务队列
* 缓存
* 临时状态
* 恢复事件

---

# 四、核心处理链路

## 阶段 0：规则准备

由 Java 控制面完成。

内容包括：

* 档案类型规则
* 分件规则
* 排序规则
* 编号规则
* 保存期限规则
* 著录字段规则
* 标签规则
* 审核阈值

任务开始时生成：

**policy_snapshot（规则快照）**

后续整卷都按这一版规则执行，不中途乱变。

---

## 阶段 1：整卷接入

输入单位建议是：

**整卷作为业务输入单位**

不是单页直接作为业务单位。

因为：

* 分件要看上下文
* 排序要看整卷
* 编号要看整卷件数和顺序

但在执行层内部，可以按页并行。

---

## 阶段 2：页级处理

这一层全卷统一跑，尽量并行。

步骤：

1. 图像预处理
2. OCR
3. 版面识别
4. pHash / 相似度
5. 页面特征提取

输出是：

**page schema**

即每页一个 page object，至少包含：

* page_id
* page_index
* image_path
* ocr_text
* bbox / blocks / lines
* layout_type
* phash
* first_page_score
* duplicate_score
* title/date/doc_no candidates

这时还是“按页”，还不是“按件”。

---

## 阶段 3：页面关系分析

这是你现有能力最适合放的位置。

核心任务：

* 相邻页是否连续
* 是否像新件开始
* 是否像前件续页
* 是否像附件
* 是否重复页
* 是否目录/封面页

输出建议不要只是“排序结果”，而要输出中间结果：

* page_similarity_matrix
* boundary_candidates
* duplicate_pages
* first_page_candidates
* page_relation_scores

这是后续分件的基础层。

---

## 阶段 4：自动分件

根据：

* OCR 文本
* 版面结构
* 页面关系
* 标题/日期/文号候选
* 规则快照

生成初步件集合。

输出：

**doc schema（草稿件）**

例如：

* tmp_doc_id
* start_page
* end_page
* pages
* confidence
* boundary_reason
* status

这是系统的第一核心能力。

---

## 阶段 5：件级排序

在分件后，对件进行业务排序。

建议文书档案第一版优先用：

* 形成时间
* 文号
* 附件跟随主件

注意：

你现在用的 pHash/版面识别不冲突，它们是**页面结构恢复层**；这里是**件级业务排序层**。

---

## 阶段 6：双轨分流

从分件后开始，正式进入双轨机制。

### Draft 轨

继续跑：

* 草稿字段提取
* 草稿标签
* 草稿目录
* 风险标记
* searchable PDF 草稿版
* 局部审核任务生成

### Final 轨

只在关键条件满足后继续跑：

* 正式排序
* 正式编号
* 正式目录
* 正式入库
* 正式 PDF 导出

如果某段边界不确定，比如 007–009，需要生成局部审核任务，则：

* Draft 轨继续
* Final 轨挂起在正式件级处理前

---

## 阶段 7：人工审核

中断点主要有几类：

* 分件/边界审核
* 排序/归属审核
* 字段/著录审核
* 标签/保存期限审核
* 最终放行审核

你前端最好拆成三类工作台：

### 结构审核台

看分件、页归属、附件、顺序

### 著录审核台

看题名、日期、责任者、标签、保存期限

### 放行控制台

看整卷状态、返工、入库、导出

人工不是从零做，而是：

**看系统建议 + 快速纠偏**

---

## 阶段 8：局部恢复

人工审核完成后，不整卷重跑。

而是：

1. 回写审核结果
2. 标记受影响结果失效
3. 局部重跑受影响节点
4. 恢复 Final 轨

比如边界改了：

* 不重跑 OCR
* 不重跑预处理
* 只重跑受影响 doc 的排序/字段/编号/目录

---

## 阶段 9：自动编号

编号必须放在：

**分件确认 + 顺序基本确认之后**

不能 OCR 完就做。

建议：

* 内部用 tmp_doc_id 追踪
* Final 阶段再生成正式 archive_no

这样返工时不会把内部引用搞乱。

---

## 阶段 10：自动著录与标签

字段提取建议采用混合策略：

### 规则优先

* 日期
* 文号
* 页数
* 固定格式字段

### 模型优先

* 题名
* 责任者
* 主题标签
* 摘要类字段

### 人工兜底

* 人名潦草
* 多候选冲突
* 保存期限例外
* 标签不确定

标签建议分层：

* 文种标签
* 主题标签
* 状态标签
* 风险标签

先生成候选标签，再人工确认，最后写入正式索引。

---

## 阶段 11：目录生成

在 Final 阶段生成：

* 卷内目录
* 件级目录
* 清单
* 导出结构

目录是正式归档的关键成果之一。

---

## 阶段 12：双层 PDF 导出

建议做成：

* Draft searchable PDF
* Final searchable PDF

方案是：

* 底图：原始扫描图
* 文字层：OCR 坐标生成隐藏文字层

这样既保留原貌，又支持搜索。

---

## 阶段 13：入库与检索

Final 结果入库后：

* 写正式卷宗记录
* 写目录
* 写标签
* 写全文索引
* 写 PDF 路径
* 建检索能力

---

# 五、核心数据模型

这是你现在必须尽快定下来的。

## 1. Page

每页对象。

字段建议：

* page_id
* batch_id
* page_index
* image_path
* ocr_text
* ocr_blocks
* layout_type
* phash
* first_page_score
* duplicate_score
* candidates

---

## 2. Doc

每件对象。

字段建议：

* tmp_doc_id
* batch_id
* pages
* start_page
* end_page
* confidence
* doc_type_guess
* sort_key
* metadata_results
* tags
* status

---

## 3. Batch / Record

整卷对象。

字段建议：

* batch_id
* tenant_id
* policy_snapshot_id
* page_count
* draft_status
* final_status
* review_status
* current_version
* export_status

---

## 4. ReviewTask

审核任务对象。

字段建议：

* review_task_id
* batch_id
* type
* affected_pages
* affected_docs
* reason
* assignee
* status
* result

---

## 5. ReworkTask

返工任务对象。

字段建议：

* rework_task_id
* record_id
* record_version
* issue_type
* affected_scope
* reported_by
* status

---

# 六、角色与权限路线

你现在的角色设计建议这样落地：

## 公司管理员

管平台，不碰日常卷宗。

## 租户管理员

两条链都能看：

* 生产链
* 检索链

负责：

* 批量导入
* 分配任务
* 最终放行
* 导出
* 规则管理

## 导入员

只走生产链，不看正式检索库。

负责：

* 批量导入
* 发起工作流
* 看处理中卷宗
* 处理审核任务
* 提交入库申请

## 检录员

只走检索链，不做导入。

负责：

* 检索正式卷宗
* 核验目录/PDF/字段
* 发现问题后提交返工申请

这个角色边界是合理的，因为本质上你在分离：

* 造档
* 查档

---

# 七、返工路线

返工不要直接改正式库。

应该做成：

**问题提报 → 返工任务 → 局部/整卷返工 → 新版本生效**

建议：

* 检录员有发现权和提报权
* 没有直接修改正式结果的权力
* 租户管理员决定是否受理返工
* 返工后生成新版本替换旧版本

这样审计才稳。

---

# 八、性能路线

你最该提效的地方，不是单点算法，而是整链。

建议：

* 页级并行
* 规则优先
* 模型只处理难点
* 候选缓存复用
* 局部重跑
* 双轨机制
* 问题片段化审核
* 队列分级

核心目标不是“每卷秒出”，而是：

**大多数卷走快通道，少数问题只做局部人工和局部重跑**

---

# 九、实现阶段建议

## 第一阶段：MVP

先跑通最小闭环：

* 批量导入
* OCR
* 页面关系分析
* 自动分件
* 人工分件/排序审核
* 自动著录
* 目录生成
* searchable PDF
* 最终入库

## 第二阶段：增强版

补：

* 双轨机制
* 局部审核
* 局部恢复
* 自动编号
* 标签体系
* 保存期限规则化
* 返工流程

## 第三阶段：成熟版

再补：

* 复杂档案类型
* 更强规则引擎
* 模板体系
* 自动任务分发
* 统计报表
* RAG / 知识库能力

---

# 十、你现在最适合的技术栈落地

按你目前方向，我建议就是：

* **Java**：Spring Boot 控制面
* **Python**：FastAPI + LangGraph 计算面
* **PostgreSQL**：状态、结果、规则、审计
* **Redis**：队列、缓存、恢复事件
* **MinIO**：原始文件、页图、PDF、导出物
* **OCR 服务**：独立
* **前端**：审核台 + 批次台 + 放行台

---

# 十一、最后给你一个技术路线总结

你这个系统的正确路线，不是“把 OCR 做得更像 OCR”，而是：

**以整卷为单位接入，按页并行完成感知处理；以页面关系分析为基础完成自动分件；以规则驱动和人工纠偏完成件级排序、编号、著录、标签与目录生成；通过 Draft/Final 双轨、局部审核、局部恢复、版本化返工和 searchable PDF 导出，最终形成可入库、可检索、可追溯的档案处理闭环。**

你们现阶段最该优先打通的 4 个东西是：

* page/doc/batch 数据模型
* 自动分件 + 人工结构审核
* Draft/Final 双轨 + 局部恢复
* 正式编号 + 目录 + 双层 PDF 导出

你要的话，我下一条可以直接继续给你整理成两种形式之一：

1. **Mermaid 技术架构图**
2. **分阶段开发清单（按周排优先级）**

---

# 十二、业务共识补充

结合前面讨论，第一阶段的业务边界建议再明确成下面几点：

* **先聚焦文书档案**，优先处理 **A4、规则明确、近一二十年形成的规范材料**，把复杂纸型、老资料、人事档案、工程图纸先放在后续阶段。
* **业务输入单位仍然是整卷/整批散文件**。即便拿到的是“27 份尚未整理好的散文件”，系统也应先站在整卷视角做自动分件、自动排序和后续著录；内部执行上仍然可以按页并行。
* **自动编号必须晚于分件和排序确认**。不能 OCR 完就编号，而要等整卷件数、顺序和边界基本稳定后，再给每件首页生成正式电子档案号。
* **保存期限优先走规则自动判定**。人工不应先逐件区分保存期限，而是由租户配置保存期限规则，系统自动给出候选或最终结果，例外情况再人工确认。
* **标签的本质是分类标记，不是额外负担**。它用于告诉系统“这是什么文件、怎么处理、后续怎么检索”，第一版先保留文种标签、主题标签、状态标签、风险标签四类即可。
* **物理页码/角标打印属于后续增强能力**。第一版先解决电子整理闭环，后续再考虑结合打印设备完成 A4 文书的页码、角标打印。

---

# 十三、人工中断点与前端形态补充

你们的中断点越来越清晰后，人工审核最好按“问题类型”拆开，而不是所有事情都塞进一个页面。

## 1. 关键中断点

建议至少保留 4 类中断点：

* **分件/边界中断点**：判断某页是否为新件开始、续页、附件或重复页。
* **排序/归属中断点**：判断件与件的先后顺序、附件挂接关系、是否需要拖拽调整。
* **字段/标签/保存期限中断点**：判断题名、日期、责任者、标签、保存期限是否正确。
* **Final 放行中断点**：判断这卷是否允许正式编号、正式目录、正式 PDF 导出和正式入库。

## 2. 人工审核需要的能力

不同中断点需要的人不一样，建议按能力拆分：

* **结构审核能力**：会判断新件首页、续页、附件归属、件级顺序，适合处理分件和排序问题。
* **内容审核能力**：会核对题名、日期、责任者、标签和保存期限，适合处理著录和分类问题。
* **放行判断能力**：会判断是否允许进入 Final、是否需要返工、是局部返工还是整卷返工。

## 3. 前端最好拆成 3 类工作台

### 结构审核台

用于处理分件、边界、顺序、附件归属。

推荐布局：

* 左侧：卷宗/件列表，显示件范围、页数、置信度、风险标记
* 中间：问题片段页视图，展示相邻页缩略图与原图
* 右侧：系统证据面板，展示 OCR 标题候选、日期候选、边界原因、置信度

关键操作：

* 合并到前件
* 拆分为新件
* 作为后一件首页
* 拖拽调整顺序
* 标记升级处理

### 著录审核台

用于处理字段、标签、保存期限。

推荐布局：

* 左侧：字段表单，重点高亮低置信字段
* 中间：原图预览，可缩放定位
* 右侧：OCR 文本与候选值，支持一键采用候选

关键操作：

* 点击候选填充字段
* 定位字段对应原图区域
* 确认高置信字段
* 从词表补充标签
* 查看保存期限规则命中说明

### 放行控制台

用于处理 Final 放行、返工判断、入库确认、导出确认。

推荐布局：

* 顶部：整卷总览，展示页数、件数、待审片段、返工状态
* 中间：风险汇总，展示未关闭问题、低置信字段、未确认标签
* 底部：放行操作区，提供 Final、返工、指派、入库、导出等动作

---

# 十四、角色协同补充

结合你们已经明确的岗位边界，推荐这样落地：

* **公司管理员**：负责平台、租户、资源、全局模板，默认不参与日常卷宗加工和检索。
* **租户管理员**：同时拥有生产链和检索链权限，负责批量导入、任务分配、规则配置、Final 放行和导出。
* **导入员**：负责“文档上传到入库申请”的整条生产链，但**没有检索卷宗库权限**。
* **检录员**：负责正式卷宗的检索、核验、利用和问题发现，但**没有导入权限**。

返工链路建议固定为：

**检录员发现问题并提交返工申请 → 租户管理员判断是否受理 → 导入链路接手局部/整卷返工 → 新版本 Final 生效替换旧版本**

这样可以把“造档”和“查档”严格分开，同时保留可追溯、可返工、可审计的闭环。

---

# 十五、LangGraph 工作流落地细节

如果后面你们准备正式落地 LangGraph，建议不要把它只当“流程图工具”，而要把它当成**可恢复的状态机执行器**来设计。

## 1. 建议的 Graph 分层

建议拆成 4 层：

* **main graph**：负责整卷主流程，从接入到分件、分流、定稿、导出。
* **draft subgraph**：负责草稿字段、草稿标签、草稿目录、草稿 searchable PDF、审核任务生成。
* **final subgraph**：负责正式排序、正式编号、正式著录、正式目录、正式导出、正式入库。
* **resume/rework subgraph**：负责人工审核后恢复、返工后重跑、局部失效传播与下游重算。

这样拆的好处是：

* Draft 和 Final 逻辑不会混在一个超长链里
* 审核恢复和返工恢复可以复用一套增量重跑机制
* 每条子图都可以单独调试、单独压测

## 2. 建议的 State 结构

LangGraph state 不要只存“当前节点名”，而要同时存：

* **业务主键**
* **中间结果引用**
* **阻塞点**
* **恢复范围**
* **checkpoint**
* **产物地址**

建议最少包含下面这些字段：

```json
{
  "task_id": "wf_20260413_001",
  "batch_id": "batch_001",
  "tenant_id": "tenant_a",
  "policy_snapshot_id": "policy_v12",
  "run_mode": "normal",
  "current_stage": "split_documents",
  "draft_status": "running",
  "final_status": "blocked",
  "review_status": "pending",
  "pages": [],
  "draft_docs": [],
  "final_docs": [],
  "review_tasks": [],
  "blocked_reasons": [],
  "affected_scope": {
    "page_ids": [],
    "doc_ids": [],
    "renumber_from_order_index": null
  },
  "checkpoints": {
    "after_ocr": "ckpt_ocr_001",
    "after_page_analysis": "ckpt_rel_001",
    "after_split": "ckpt_split_001"
  },
  "artifacts": {
    "draft_catalog_path": null,
    "draft_pdf_path": null,
    "final_catalog_path": null,
    "final_pdf_path": null
  },
  "metrics": {
    "page_count": 0,
    "draft_doc_count": 0,
    "review_task_count": 0
  }
}
```

## 3. 建议的主节点清单

你们这条链建议至少拆成这些节点：

1. `ingest_batch`
2. `load_policy_snapshot`
3. `preprocess_pages`
4. `run_ocr`
5. `extract_page_features`
6. `analyze_page_relations`
7. `split_documents`
8. `assess_split_risk`
9. `run_draft_subgraph`
10. `create_review_tasks`
11. `gate_final_subgraph`
12. `wait_for_review`
13. `resume_from_review`
14. `sort_documents_final`
15. `assign_archive_numbers`
16. `extract_metadata_final`
17. `build_catalog_final`
18. `export_searchable_pdf_final`
19. `persist_record_and_index`

## 4. 条件路由建议

几个关键路由条件最好提前写死，不要运行时临时判断：

* 如果 `split_documents` 后没有阻塞点，则 Draft 和 Final 都可继续。
* 如果存在 `boundary_review`、`order_review` 等影响正式结果的任务，则 Draft 继续，Final 进入 `blocked`。
* 如果只是字段低置信，但不影响件级结构，则 Final 可以继续到编号前或著录前的指定关口。
* 如果审核结果回写后 `blocked_reasons` 清空，则进入 `resume_from_review`。
* 如果返工级别为 `full_rework`，则跳转到 `load_policy_snapshot` 或 `split_documents` 之前的指定 checkpoint。

## 5. Checkpoint 建议

建议至少在这些节点后保存 checkpoint：

* `after_ocr`
* `after_page_analysis`
* `after_split`
* `after_draft_metadata`
* `after_final_sort`
* `after_final_catalog`

checkpoint 里不要塞大对象正文，建议只保存：

* state 的轻量快照
* 结构化结果的数据库版本号
* 大对象在 MinIO 或 PostgreSQL 中的引用地址

## 6. 恢复策略建议

恢复时不要只写“从某节点恢复”，而要同时确定：

* 从哪个 checkpoint 恢复
* 恢复哪个 scope
* 失效哪些结果
* 是否需要重新编号
* 是否需要重建目录和 PDF

建议恢复入口统一成一个内部动作：

`resume_workflow(task_id, reason, affected_scope, resume_from_checkpoint)`

---

# 十六、数据库与对象存储设计补充

前面已经定义了 page/doc/batch 这几个核心对象，后面为了可恢复、可追溯、可返工，建议把物理表再明确一层。

## 1. 建议的核心表

建议至少有下面这些表：

* `tenant`
* `user_account`
* `role_binding`
* `batch_record`
* `source_file`
* `page`
* `doc_unit`
* `doc_version`
* `policy_snapshot`
* `workflow_run`
* `workflow_checkpoint`
* `review_task`
* `review_action_log`
* `rework_task`
* `artifact_file`
* `audit_log`

## 2. 表职责建议

### `batch_record`

表示整卷或整批处理对象，建议存：

* `batch_id`
* `tenant_id`
* `source_type`
* `import_user_id`
* `page_count`
* `status`
* `draft_status`
* `final_status`
* `review_status`
* `current_version`
* `policy_snapshot_id`
* `created_at`
* `updated_at`

### `page`

表示页面级对象，建议存：

* `page_id`
* `batch_id`
* `page_index`
* `image_uri`
* `preview_uri`
* `ocr_text`
* `ocr_blocks_json`
* `layout_type`
* `rotation`
* `phash`
* `duplicate_score`
* `first_page_score`
* `feature_version`

### `doc_unit`

表示一件档案的稳定实体，建议只存“稳定身份”和当前关系：

* `doc_id`
* `batch_id`
* `doc_kind`
* `current_version`
* `status`
* `created_at`

### `doc_version`

表示某件在某次草稿/正式/返工后的具体版本，建议存：

* `doc_version_id`
* `doc_id`
* `version_no`
* `version_type`
* `start_page`
* `end_page`
* `page_ids_json`
* `sort_index`
* `archive_no`
* `metadata_json`
* `tags_json`
* `confidence_json`
* `is_current`

这种拆法很适合返工，因为返工通常不是“修改一条记录”，而是“生成新版本”。

### `artifact_file`

所有导出和中间产物都建议统一登记：

* `artifact_id`
* `batch_id`
* `doc_id`
* `artifact_type`
* `artifact_version`
* `storage_uri`
* `file_hash`
* `created_by_run_id`

`artifact_type` 建议至少包含：

* `raw_image`
* `page_preview`
* `draft_catalog`
* `final_catalog`
* `draft_searchable_pdf`
* `final_searchable_pdf`
* `export_zip`

## 3. 推荐索引

建议优先建这些索引：

* `batch_record(tenant_id, status, created_at desc)`
* `page(batch_id, page_index)`
* `doc_unit(batch_id, status)`
* `doc_version(doc_id, is_current)`
* `review_task(batch_id, status, assignee_user_id)`
* `rework_task(record_id, status, created_at desc)`
* `workflow_run(batch_id, run_status, created_at desc)`

如果后面检索量上来，再考虑：

* `ocr_text` 全文索引
* 标签字段 GIN 索引
* JSONB 规则命中字段索引

## 4. MinIO 路径建议

对象路径最好从一开始就按租户、批次、版本分层：

```text
tenant/{tenant_id}/batch/{batch_id}/raw/{file_name}
tenant/{tenant_id}/batch/{batch_id}/pages/{page_index}.png
tenant/{tenant_id}/batch/{batch_id}/ocr/{page_id}.json
tenant/{tenant_id}/batch/{batch_id}/draft/catalog_v1.json
tenant/{tenant_id}/batch/{batch_id}/draft/searchable_v1.pdf
tenant/{tenant_id}/batch/{batch_id}/final/catalog_v2.json
tenant/{tenant_id}/batch/{batch_id}/final/searchable_v2.pdf
```

这样后面做版本切换、返工回溯、产物替换都会清楚很多。

---

# 十七、控制面与计算面接口契约补充

Java 和 Python 之间最好不要只有“发起一个任务”这么粗，要尽量明确命令、事件、状态回传。

## 1. Java 控制面对外接口建议

建议至少有这些业务接口：

* `POST /api/batches/import`
* `POST /api/batches/{batchId}/start`
* `GET /api/batches/{batchId}`
* `GET /api/batches/{batchId}/tasks`
* `POST /api/review-tasks/{reviewTaskId}/claim`
* `POST /api/review-tasks/{reviewTaskId}/submit`
* `POST /api/rework-tasks/{reworkTaskId}/accept`
* `POST /api/rework-tasks/{reworkTaskId}/reject`
* `POST /api/batches/{batchId}/finalize`
* `POST /api/batches/{batchId}/export/final-pdf`

## 2. Java 调 Python 的内部接口建议

建议至少拆成这些内部执行接口：

* `POST /internal/workflow/start`
* `POST /internal/workflow/resume`
* `POST /internal/workflow/rework`
* `POST /internal/export/searchable-pdf`
* `POST /internal/recompute/affected-scope`

例如恢复接口可以这样：

```json
{
  "task_id": "wf_20260413_001",
  "batch_id": "batch_001",
  "reason": "review_resolved",
  "resume_from_checkpoint": "ckpt_split_001",
  "affected_scope": {
    "page_ids": ["p007", "p008", "p009"],
    "doc_ids": ["doc_003", "doc_004"],
    "renumber_from_order_index": 3,
    "regenerate_catalog": true,
    "regenerate_pdf": true
  }
}
```

## 3. Python 回调或事件建议

Python 计算面在关键节点应主动回传状态事件：

* `WORKFLOW_STARTED`
* `NODE_COMPLETED`
* `REVIEW_TASK_CREATED`
* `WORKFLOW_BLOCKED`
* `WORKFLOW_RESUMED`
* `EXPORT_READY`
* `WORKFLOW_FAILED`

每个事件最好至少带这些字段：

* `task_id`
* `batch_id`
* `tenant_id`
* `event_type`
* `stage`
* `status`
* `payload`
* `occurred_at`

## 4. 幂等性建议

这块很关键，尤其是恢复和导出：

* 每次 `start/resume/rework/export` 请求都应带 `request_id`
* Java 侧保存请求流水，避免用户重复点击造成重复执行
* Python 侧按 `request_id + action_type + batch_id` 做幂等判断
* 导出成功后重复请求应直接返回已有 `artifact_id`

---

# 十八、队列、并发与失败恢复补充

你这个系统后面一定是长任务系统，所以队列和恢复设计要尽早进入文档，不然后面很容易全堆在一个 worker 上。

## 1. 建议的队列拆分

建议至少拆成这些队列：

* `ingest_queue`
* `page_preprocess_queue`
* `ocr_queue`
* `page_feature_queue`
* `relation_analysis_queue`
* `draft_pipeline_queue`
* `final_pipeline_queue`
* `review_resume_queue`
* `rework_queue`
* `export_queue`

如果资源允许，进一步区分：

* CPU 队列
* GPU 队列
* 人工恢复优先队列

## 2. 并发原则

建议遵循这几个原则：

* **页级任务并行**：OCR、版面分析、pHash、特征提取按页并行。
* **卷级节点聚合**：分件、排序、编号、Final 定稿按卷聚合。
* **恢复任务优先级高于新任务**：因为恢复任务通常只差最后几步，优先完成体验更好。
* **导出任务独立队列**：不要让 PDF 导出堵住识别流程。

## 3. 重试策略

不是所有失败都该同一种重试。

建议分成：

* **瞬时失败**：网络、对象存储超时、模型服务偶发异常，可自动重试 2 到 3 次。
* **数据失败**：文件损坏、页面不可读、OCR 返回空结构，不要无限重试，直接挂人工或异常队列。
* **业务阻塞**：边界不确定、保存期限冲突，这不是失败，而是进入 review/block 状态。

## 4. 死信与补偿

建议每条关键链路都要有：

* **dead letter queue**
* **失败原因分类**
* **人工重试入口**
* **补偿动作**

例如：

* searchable PDF 导出失败，可以保留 Final 结果并允许单独重试导出
* OCR 某几页失败，可以只补跑失败页，而不是整卷重来
* MinIO 写入失败，可以让 `artifact_file` 先保持 `pending_upload`

## 5. 失效传播建议

人工改动后，系统要明确哪些结果过期了。

建议按下面粒度做失效：

* 改页归属：失效受影响 doc 的字段、排序、编号、目录、PDF
* 改字段：失效目录、索引、导出，不失效 OCR 和分件
* 改标签或保存期限：失效检索索引、目录展示、统计，不失效分件
* 改排序：失效从排序断点之后的编号和目录

---

# 十九、质量控制与可观测性补充

如果你们后面真的要持续优化，必须从第一版开始就把“质量分”和“监控指标”埋进去。

## 1. 建议的质量分层

建议至少做 4 个置信度：

* `ocr_confidence`
* `boundary_confidence`
* `metadata_confidence`
* `final_readiness_score`

可以先用简单加权方式：

```text
final_readiness_score =
0.30 * ocr_confidence +
0.35 * boundary_confidence +
0.20 * metadata_confidence +
0.15 * rule_match_score
```

这不是最终算法，但足够支撑第一版的审核阈值。

## 2. 建议监控的核心指标

建议至少监控这些：

* 每卷平均页数
* 每页 OCR 平均耗时
* 每卷页面关系分析耗时
* 每卷自动分件耗时
* 每卷 LLM 调用次数
* 每卷 review task 数量
* review task 平均解决时长
* 审核后恢复耗时
* draft 首次产出时间
* final 完成时间
* searchable PDF 导出耗时
* 全卷重跑比例

## 3. 审计日志建议

建议这些动作必须落审计：

* 批量导入
* 工作流启动
* 审核提交
* 返工申请
* 返工受理/驳回
* Final 放行
* 正式入库
* 导出下载

审计字段建议至少包含：

* `tenant_id`
* `operator_user_id`
* `target_type`
* `target_id`
* `action`
* `before_snapshot`
* `after_snapshot`
* `occurred_at`

## 4. 告警建议

建议先做最关键的几个告警：

* OCR 服务不可用
* 某租户任务堆积超过阈值
* review task 长时间无人处理
* export_queue 堵塞
* 同一批次反复失败超过阈值

---

# 二十、安全与租户隔离补充

你们是多租户系统，这部分最好提前落到文档里，而不是等上线前再补。

## 1. 租户隔离原则

建议遵循：

* 数据表记录全部带 `tenant_id`
* 所有查询都按 `tenant_id` 强制过滤
* MinIO 路径按租户前缀隔离
* 导出链接使用短时有效签名 URL
* Python 回调到 Java 时必须校验任务与租户绑定关系

## 2. 角色和数据域隔离

建议明确两条域：

* **生产加工域**：导入、处理中卷宗、Draft/Final 处理中结果
* **档案检索域**：已正式入库卷宗、正式目录、正式 searchable PDF、检索索引

角色映射建议就是：

* 导入员：生产加工域
* 检录员：档案检索域
* 租户管理员：两域

## 3. 文件访问控制

对于 MinIO 中的对象，建议不要直接暴露原始路径，而统一通过：

* Java 控制面鉴权
* 生成短时访问令牌
* 审计下载行为

尤其是正式卷宗 PDF、目录、导出 ZIP，最好全部走受控下载。
