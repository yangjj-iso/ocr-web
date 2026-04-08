# OCR Frontend

## 概述

本目录为 OCR 文档识别归档系统的前端工程，基于 **Vue 3 + Vite + TailwindCSS + Axios** 构建。

前端负责以下核心交互：

- 三种识别模式切换：`vl` / `layout` / `ocr`
- 单文件上传、拖拽上传、多文件批量上传
- 直接从资源管理器选择本地文件夹批量上传
- 输入服务器路径导入文件夹并批量识别
- 归档 Excel 路径与结果输出目录配置
- 历史按文件夹分组展示与批量删除
- 结果页文件侧边栏切换、原文预览、结果编辑保存
- 全文搜索与结果跳转

生产环境下，前端构建产物默认输出到 `dist/`，由 Nginx 或任意静态文件服务独立托管。

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 框架 | Vue 3 (`<script setup>`) |
| 构建工具 | Vite |
| 路由 | Vue Router |
| 请求库 | Axios |
| 样式 | TailwindCSS |

---

## 开发命令

### 安装依赖

```bash
npm install
```

### 启动开发环境

```bash
npm run dev -- --host 0.0.0.0 --port 3000
```

默认访问地址：

- 前端：`http://localhost:3000`
- 后端 API：`http://localhost:8000`
- Swagger：`http://localhost:8000/docs`

### 构建生产包

```bash
npm run build
```

构建结果会输出到：

```text
dist
```

若前后端分离部署，推荐在 `frontend/.env.local` 中设置：

```text
VITE_API_BASE_URL=http://localhost:8000
```

如果已经按“双服务”方式拆分部署，推荐改成：

```text
VITE_BUSINESS_API_BASE_URL=http://localhost:8000
VITE_AI_API_BASE_URL=http://localhost:8001
VITE_AI_FILE_BASE_URL=http://localhost:8001
```

其中：

- `Auth`、归档记录、目录扫描、批次建档走 `business-api`
- OCR 上传、任务列表、文件预览、批次整合、QA、评测走 `ai-document-service`

---

## 目录结构

```text
frontend/
├── src/
│   ├── api/
│   │   └── ocr.js                # OCR API 封装
│   ├── components/
│   │   ├── BufferZone.vue        # 批量上传区（文件/文件夹/路径导入）
│   │   └── HistoryList.vue       # 历史目录列表（分组查看/删除）
│   ├── features/
│   │   ├── workbench/            # 工作台页面与编排
│   │   ├── result/               # 结果页与字段提取页面
│   │   └── search/               # 检索页面
│   ├── router.js
│   ├── App.vue
│   └── style.css
├── package.json
└── vite.config.js
```

---

## 当前已实现的前端能力

### 1. 批量上传与导入

- 拖拽文件到卡片区域批量上传
- 点击选择多个本地文件上传
- 点击 `选文件夹`，直接从资源管理器选择本地文件夹
- 在“文件夹路径”中输入服务器路径并点击“导入”
- 本地文件夹上传时自动携带相对目录结构，便于后端按批次归档与历史分组

### 2. 归档与输出配置

- 支持填写归档 Excel 路径
- 支持填写识别结果输出目录
- 批量处理时会把这些参数传给后端
- 归档 Excel 会写入档号、文号、责任者、题名、日期、页数、密级等字段
- 档号提取当前优先保留完整文件编号，避免同批 `KJ` / `WS` 文件被截成相同前缀

### 3. 历史与结果查看

- 首页历史按文件夹聚合展示
- 支持按文件夹删除历史记录
- 进入结果页后，左侧展示当前目录全部文件
- 支持在原文预览与识别结果之间联动查看

### 4. 搜索与编辑

- 支持全文搜索历史识别结果
- 支持对识别结果在线编辑并保存

---

## 与后端的协作方式

### 本地文件夹上传

前端通过浏览器文件夹选择器获取本地文件，并将 `relative_path` 一并提交给后端。

后端会：

- 保存上传文件
- 尽量保留原始相对目录层级
- 执行 OCR
- 按需写入 Excel
- 按需输出 `.json` 与 `.txt`
- 首个成功文件可触发 Excel 数据区清空，后续文件逐行追加

### 服务器路径导入

前端先调用：

```text
GET /api/ocr/scan-folder
```

获取服务器目录中的文件列表，再逐个调用：

```text
POST /api/ocr/upload-from-path
```

完成批量识别。

---

## 浏览器限制说明

当前纯 Web 前端下：

- **源文件夹** 可以通过资源管理器直接选择
- **归档Excel路径** 不能直接像桌面程序一样选择真实 Windows 绝对路径
- **识别结果输出目录** 也不能直接把本地绝对路径暴露给后端

因此，目前前端仅对“源文件夹”提供直接点选能力；`归档Excel路径` 与 `识别结果输出目录` 仍需手动输入。

如果未来需要把这两个路径也改成真正的资源管理器点选，建议改为：

- 桌面化方案：Electron / Tauri
- 或改造成基于浏览器本地文件系统授权的保存模式

---

## 开发注意事项

- 本项目开发模式默认通过 Vite 代理访问后端 API
- 若修改了后端接口参数，需同步更新 `src/api/ocr.js`
- 若修改了批量上传逻辑，需同时检查：
  - `BufferZone.vue`
  - `app/api/tasks.py`
  - `app/application/workflows/tasks.py`
  - `app/services/ocr_service.py`
- 生产环境访问异常时，优先确认是否已执行 `npm run build`

---

## 相关文档

- 根目录说明：`../README.md`
- 部署文档：`../DEPLOYMENT.md`
