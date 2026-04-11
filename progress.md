# OCR Web — Phase 2 变更日志

> 记录每次改动内容、审查结果、待测事项。按时间倒序。

---

## 2026-04-11  Phase 2：角色权限、配额、任务分配、目录分组

### 总览
实现系统管理员 / 执行者双角色体系，包含：用户配额管理、批次任务分配、操作可追溯审计日志、上传预览目录分组。

---

### 后端 — Python AI API

#### `app/db/models.py`
- `AppUser` 新增 `role VARCHAR(20) DEFAULT 'operator'`、`display_name VARCHAR(120)` 字段
- 新增 `UserQuota` 表：`quota_per_import`、`quota_total`、`quota_used`、`reset_at`
- 新增 `BatchAssignment` 表：管理员将批次分配给执行者
- 新增 `OperationLog` 表：不可变审计日志，带 JSONB `detail` 字段
- **审查**：JSONB 已在项目中使用，索引已定义 ✅

#### `app/db/database.py`
- `init_db()` 调用 `_run_schema_migrations()`
- `_run_schema_migrations()`：幂等 `ALTER TABLE IF NOT EXISTS` 补列；存量 is_admin=true 行自动回填 role='admin'
- **审查**：每条语句独立 try/except，不影响启动 ✅

#### `app/core/auth.py`
- `create_session_token()` 增加 `role` 参数，写入 payload
- `get_authenticated_user()` 从 payload 提取 `role`
- `set_auth_cookie()` 透传 `role`
- **审查**：AUTH_ENABLED=False 分支也返回 role='admin' ✅

#### `app/domains/auth/auth_service.py`
- `write_auth_cookie_for_user()` 传递 `user.role or 'operator'`
- `write_auth_cookie_for_admin()` 传递 `role='admin'`
- **审查**：注册新用户 AppUser 未显式设置 role，依赖模型 default='operator' ✅

#### `app/api/admin_users.py` — 新文件
路由组：
- `GET /api/admin/users` — 用户列表（支持按 role/status 过滤）
- `PUT /api/admin/users/{id}/role` — 修改角色
- `PUT /api/admin/users/{id}/display-name` — 修改显示名
- `GET|PUT /api/admin/users/{id}/quota` — 查看/修改配额
- `POST /api/admin/users/{id}/quota/reset` — 重置已用配额
- `GET|POST /api/admin/assignments` — 分配列表/新建分配
- `PUT /api/admin/assignments/{id}/status` — 更新分配状态
- `GET /api/admin/operation-logs` — 操作日志
- `GET /api/operator/my-quota` — 执行者查自己配额
- `GET /api/operator/my-assignments` — 执行者查自己的任务
- `POST /api/operator/my-quota/consume` — 消费配额（导入文件后调用）
- `_write_log()` / `write_operation_log()` — 内部审计写入
- **审查**：`request: Request = None` 默认值已修正为正确注入方式（见下方修复记录）

#### `app/api/routes.py`
- 注册 `admin_router`（`/api/admin`）和 `operator_router`（`/api/operator`）

---

### 后端 — Java 控制面

#### `AppUserEntity.java`
- 新增 `role VARCHAR(20) DEFAULT 'operator'`（getter `getRole()` 带空值保护）
- 新增 `display_name VARCHAR(120)`

#### `CurrentUser.java`（record）
- 新增 `String role` 字段
- 新增 `effectiveRole()` 方法：role 为空时按 isAdmin 推断

#### `SessionTokenService.java`
- `createSessionToken()` 增加 `role` 参数写入 payload
- `verifySessionToken()` 从 payload 读取 `role`，默认 'operator'

#### `AuthDtos.java`
- `AuthStatusResponse` 新增 `role` 字段
- `LoginResponse` 新增 `role` 字段
- **注意**：Spring 全局 `SNAKE_CASE` 命名策略，`role` 序列化为 `role` ✅

#### `AuthService.java`
- 所有 `new CurrentUser(...)` 构造点传递 `role`
- `buildAuthCookie()` 透传 `effectiveRole()`
- `getAuthStatus()` 响应包含 `role`
- `login()` 响应及 cookie 包含 `role`
- **审查**：注册时 AppUserEntity.role 默认 'operator'，不需要显式设置 ✅

---

### 前端

#### `frontend/src/style.css`
- 新增 `.gov-btn`、`.gov-btn-secondary`、`.gov-input`、`.gov-card` 全局工具类
- **审查**：已确认 AdminCenterPage.vue 使用的这四个类之前不存在 ✅

#### `frontend/src/api/admin.js` — 新文件
封装所有 `/api/admin/*` 和 `/api/operator/*` 调用

#### `frontend/src/composables/useAuthState.js`
- `auth` ref 增加 `role` 字段（default: 'operator'）
- `refreshAuthStatus()` / `login()` 均从响应中提取 `role`
- 新增导出：`isOperator`、`isReviewer`、`userRole`（均为 computed）

#### `frontend/src/features/admin/AdminCenterPage.vue` — 新文件
三标签页管理中心：
- **用户管理**：列表、改角色（select）、改显示名（inline edit）、配额弹窗、重置配额
- **任务分配**：新建分配表单、分配记录表（支持状态下拉修改）
- **操作日志**：按 action_type 过滤，只读表格
- **审查**：使用 `gov-btn/gov-input/gov-card` — 已在 style.css 补充 ✅

#### `frontend/src/features/admin/index.js` — 新文件
统一导出 `AdminCenterView`

#### `frontend/src/router.js`
- 新增路由 `/admin` → `AdminCenterPage`，`meta: { requiresAdmin: true }`

#### `frontend/src/App.vue`
- 顶部导航加「管理中心」链接（仅管理员可见）
- 用户名旁显示角色徽章（admin/operator/reviewer/searcher 各有颜色）

#### `frontend/src/features/workbench/WorkbenchPage.vue`
- import `useAuthState` 和 `getMyQuota`、`getMyAssignments`
- `myQuota` ref + `quotaPercent` computed
- `loadMyQuota()` / `loadAssignedTasks()` — `onMounted` 调用
- 侧栏新增「我的任务」按钮，带待处理数量红点
- 侧栏底部配额进度条（仅非管理员显示）
- 主内容区新增「我的任务」面板（selectedTab === 'assigned'）
- **审查**：`authState.isAdmin.value` 嵌套访问正确（非顶层 ref 不自动解包）✅

#### `frontend/src/components/BufferZone.vue`
- 上传文件预览改为按目录分组折叠
- `expandedDirs`（ref Set）+ `toggleDirExpand(dir)` 控制展开/收起
- `dirGroupedFiles` computed：按 `webkitRelativePath` 前缀分组
- `dirGroupedPathFiles` computed：按 `rel_path` 前缀分组
- `removeDirFiles(dir)`：降序移除，避免 splice 索引漂移
- 每个目录行右侧有「删除目录」按钮
- **审查**：`removeFile` 使用 `splice(index,1)`，降序移除保证低索引不漂移 ✅
- **审查**：`expandedDirs` 每次赋新 Set 确保 Vue 响应式更新 ✅

---

### 待测清单

| 项目 | 测试方式 |
|------|----------|
| 登录后 `/api/auth/me` 返回包含 `role` | 浏览器 Network / curl |
| 管理员登录后顶栏显示「管理中心」链接 | 手动测试 |
| 执行者登录后顶栏不显示「管理中心」 | 手动测试 |
| 管理中心「用户管理」能列出用户、修改角色 | 手动测试 |
| 配额弹窗保存后列表刷新 | 手动测试 |
| 任务分配创建后出现在分配记录 | 手动测试 |
| 操作日志能按类型过滤 | 手动测试 |
| 执行者工作台侧栏底部显示配额进度条 | 手动测试 |
| 执行者侧栏「我的任务」列出已分配批次 | 手动测试 |
| 选择多目录后预览区按目录分组折叠 | 手动测试 |
| 点击「删除目录」后该目录所有文件移除 | 手动测试 |
| DB 启动时自动添加 role/display_name 列 | 查看启动日志 |
| 存量 is_admin=true 用户 role 被回填为 admin | 查询数据库 |

---

---

## 2026-04-11  注册流程改造（工号 + 真实姓名）

### 需求
- 注册字段：**真实姓名**（→ display_name）+ **工号**（→ username/登录 ID）+ 密码
- 管理员账号不可自行注册，界面明确提示
- 普通人员注册后仍需管理员审核
- 新用户默认角色 `operator`

### 修改文件

| 文件 | 变更 |
|------|------|
| `frontend/src/features/auth/RegisterPage.vue` | 新增"真实姓名"字段；"账号"改为"工号"并加说明；加管理员禁止注册警告横幅 |
| `frontend/src/features/auth/LoginPage.vue` | "账号"→"工号"，提示语同步更新 |
| `frontend/src/features/auth/AdminReviewPage.vue` | 审核列表加"真实姓名"列，列出工号供管理员核验 |
| `frontend/src/api/auth.js` | `register(username, password, realName)` 传 `real_name` 字段 |
| `frontend/src/composables/useAuthState.js` | `register()` 透传 `realName` 参数 |
| `java-control-plane/AuthDtos.java` | `RegisterRequest` 加 `realName`（`@Size(min=2,max=60)`）；`PendingUserItem` 加 `displayName` |
| `java-control-plane/AuthService.java` | `register()` 校验 realName 非空、注册时写入 `display_name` + `role=operator`；错误信息全部改为中文；成功消息改为中文；`listPendingUsers()` 补 `displayName` |
| `java-control-plane/AuthController.java` | `register()` 传 `request.realName()` |

### 代码审查发现并修复

| # | 问题 | 修复 |
|---|------|------|
| 1 | `AuthService.register()` 未设置 `role` 字段 — 新注册用户角色为 null | 补 `user.setRole("operator")` |
| 2 | 服务端成功/错误信息全为英文 — 前端直接展示会影响用户体验 | 所有相关消息改为中文 |
| 3 | 审核列表无真实姓名 — 管理员只能看到工号，无法识别申请人 | `PendingUserItem` 加 `displayName`，审核页面加列 |

---

## 2026-04-11  个人中心 + 甲方需求分析

### 甲方需求对照（图二完整分析）

| 编号 | 功能 | 状态 | 路线 |
|------|------|------|------|
| 01 | 模板入库（Excel 著录模板）| ❌ 待实现 | openpyxl 解析 → recording_templates 表 |
| 02+03 | OCR 自动识别填充 + 页数统计 | ✅ 已有 | batch_merge_extraction 已输出字段 |
| 04 | 批量修改字段 | ❌ 待实现 | PATCH /api/recordings/batch |
| 05 | 人工校对界面（低置信度高亮）| ⚠️ 部分 | ResultPage 扩展 bounding box 高亮 |
| 06 | 著录表导出（Excel/CSV）| ⚠️ 部分 | 已有 Excel，缺 CSV，缺著录表视图 |
| 07 | 灵活配置 | ❌ 待实现 | system_configs 表 + Admin 配置页 |
| 08+09 | 文件夹自动建立 + 图片接续 | ❌ 待实现 | 档案号解析 → os.makedirs → 移动文件 |
| 10 | 归档章识别自动分件 | ✅ 已有 | boundary_engine + starts_archive_stamp |
| 11 | 存放路径回写 | ❌ 待实现 | 处理完成后写 storage_path |
| 12 | OCR 全文识别批量队列 | ✅ 已有 | |
| 13-17 | 全文检索（FTS + 展示 + 定位）| ❌ 待实现 | PostgreSQL GIN + tsvector (zhparser) |
| 19-20 | 用户权限 + 操作日志 | ✅ Phase 2 | |
| 21 | 词库管理 | ❌ 待实现 | custom_dictionary 表 + jieba 自定义词典 |
| 22 | 双层 PDF 导出 | ❌ 待实现 | fpdf2：下层原图 + 上层透明文字层 |

**实施优先级路线：**
- 阶段 2（下一步）：05 人工校对 → 06 著录表导出 → 10 人工处理队列
- 阶段 3：13-17 全文检索 → 22 双层 PDF → 08-09 文件夹建立
- 阶段 4：01 模板/04 批量改/07 配置/21 词库

---

### 个人中心（ProfilePage.vue）

#### 新增/修改文件

| 文件 | 操作 |
|------|------|
| `frontend/src/features/profile/ProfilePage.vue` | 新建：基本信息/显示名编辑/配额/近期任务/改密码 |
| `frontend/src/router.js` | 加 `/profile` → `ProfilePage` 路由 |
| `frontend/src/App.vue` | 用户名改为 router-link → `/profile`，显示 display_name 优先 |
| `frontend/src/api/auth.js` | 新增 `changePassword`、`updateDisplayName` 函数 |
| `frontend/src/composables/useAuthState.js` | `auth` 状态加 `display_name` 字段；login/refresh 路径均已同步 |
| `java-control-plane/.../dto/AuthDtos.java` | `AuthStatusResponse` 加 `displayName`；新增 `ChangePasswordRequest`、`UpdateDisplayNameRequest` |
| `java-control-plane/.../service/AuthService.java` | 新增 `changePassword()`、`updateDisplayName()`；`getAuthStatus()` 补 displayName 查库 |
| `java-control-plane/.../web/AuthController.java` | 新增 `POST /api/auth/change-password`、`PUT /api/auth/me/display-name` |

#### 代码审查发现并修复的问题

| # | 问题 | 修复 |
|---|------|------|
| 1 | ProfilePage.vue 用 `authState.auth.value?.user_id` 做守卫 — auth state 无此字段，导致配额/任务永不加载 | 改为 `if (!authState.isAuthenticated.value) return`，利用 session token 服务端识别用户 |
| 2 | `useAuthState.js` 无 `display_name` 字段 — App.vue `display_name \|\| username` 始终显示 username | 在 auth ref 初始值和 refresh/login 路径补 `display_name` 字段 |
| 3 | `AuthStatusResponse` 无 `displayName` — `/api/auth/me` 不返回显示名 | DTO 加字段；`getAuthStatus()` 按 userId 查库获取 displayName |

---

## 2026-04-11  代码审查修复（同日）

### 审查发现并修复的问题

| # | 文件 | 问题 | 修复方式 |
|---|------|------|----------|
| 1 | `frontend/src/style.css` | `gov-btn`、`gov-btn-secondary`、`gov-input`、`gov-card` 类不存在，AdminCenterPage 引用会失效 | 在 style.css 尾部补充四个工具类定义 |
| 2 | `app/api/admin_users.py` | `request: Request = None` 模式不规范，FastAPI 推荐直接声明 `request: Request` | 所有 5 个端点改为 `request: Request`（无默认值），移至 Depends 之前 |
| 3 | `app/api/admin_users.py` | `_ensure_quota()` 没有处理并发 INSERT 竞态：两个请求同时到达时第二个会抛出 UNIQUE 违规 | 加 `try/except + rollback + re-select` 处理竞态 |
| 4 | `frontend/src/features/admin/AdminCenterPage.vue` | `getUserQuota` 导入但从未在组件内使用（配额通过 `loadUsers` 附带加载）| 删除该无用导入 |
| 5 | `frontend/src/components/BufferZone.vue` | `removeDirFiles` 降序移除逻辑：经审查 `removeFile` 用 `splice(idx,1)` 且降序顺序正确 | 无需修改，记录为已验证 ✅ |
| 6 | `frontend/src/features/workbench/WorkbenchPage.vue` | `authState.isAdmin.value` 嵌套访问：非顶层 ref 不自动解包，需 `.value` | 代码已正确，无需修改 ✅ |
| 7 | `frontend/src/components/BufferZone.vue` | 目录分组头部仅显示文件数，缺少**总大小**（原始设计要求 `[23 份, 18.5MB]`）| `dirGroupedFiles` / `dirGroupedPathFiles` computed 加入 `totalSize` 字段；模板更新为 `N 份 · X.XMB` 格式 |
| 8 | `frontend/src/composables/useAuthState.js` | 四角色设计（admin/operator/reviewer/searcher），只导出了 `isOperator`/`isReviewer`，缺少 `isSearcher` | 补充 `isSearcher: computed(() => auth.value.role === 'searcher')` |

### 已知局限 / 后续优化

- `consume_quota` 仅在手动调用时消费配额，未与上传流程联动（需在 upload batch 完成后调用）
- Java 控制面 `AppUserEntity` 的 `role` 列需要在数据库已有数据时由 Python 迁移脚本补全（`_run_schema_migrations` 已覆盖）
- 管理中心日志过滤需手动点「刷新」，后续可改为 watch 自动触发
