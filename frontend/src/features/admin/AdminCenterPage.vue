<template>
  <div class="mx-auto max-w-[1400px] px-6 py-6">
    <!-- Header -->
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-[var(--gov-text)]">管理中心</h1>
        <p class="text-sm gov-muted mt-0.5">用户管理、配额设置、任务分配与操作日志</p>
      </div>
      <div class="flex gap-2">
        <button
          v-for="tab in tabs" :key="tab.key"
          class="relative rounded-lg px-4 py-2 text-sm font-medium transition border"
          :class="activeTab === tab.key
            ? 'bg-[var(--gov-primary)] text-white border-[var(--gov-primary)]'
            : 'bg-white text-[var(--gov-text-muted)] border-[var(--gov-border)] hover:text-[var(--gov-text)]'"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
          <span v-if="tab.badge > 0" class="absolute -top-1.5 -right-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">{{ tab.badge }}</span>
        </button>
      </div>
    </div>

    <!-- Tab: Users -->
    <div v-if="activeTab === 'users'" class="space-y-4">
      <div class="flex items-center gap-3">
        <select v-model="userFilter" class="gov-input text-sm w-36">
          <option value="">全部角色</option>
          <option value="admin">管理员</option>
          <option value="operator">签录员</option>
          <option value="searcher">检索者</option>
        </select>
        <button class="gov-btn-secondary text-sm" @click="loadUsers">刷新</button>
      </div>

      <div class="gov-card overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 border-b border-[var(--gov-border)]">
            <tr>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">用户名</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">显示名称</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">角色</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">状态</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">配额（已用/总额）</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--gov-border)]">
            <tr v-if="usersLoading">
              <td colspan="6" class="px-4 py-6 text-center text-[var(--gov-text-muted)]">加载中…</td>
            </tr>
            <tr v-else-if="!users.length">
              <td colspan="6" class="px-4 py-6 text-center text-[var(--gov-text-muted)]">暂无用户</td>
            </tr>
            <tr v-for="u in users" :key="u.id" class="hover:bg-slate-50">
              <td class="px-4 py-2.5 font-mono text-xs">{{ u.username }}</td>
              <td class="px-4 py-2.5">
                <input
                  v-if="editingName === u.id"
                  v-model="editNameValue"
                  class="gov-input text-xs w-28"
                  @keydown.enter="saveDisplayName(u)"
                  @keydown.esc="editingName = null"
                />
                <span v-else class="text-[var(--gov-text)]">{{ u.display_name || '—' }}</span>
                <button
                  class="ml-1 text-xs text-[var(--gov-primary)] hover:underline"
                  @click="startEditName(u)"
                >{{ editingName === u.id ? '取消' : '改名' }}</button>
              </td>
              <td class="px-4 py-2.5">
                <select
                  :value="u.role"
                  class="gov-input text-xs w-28"
                  @change="changeRole(u, $event.target.value)"
                >
                  <option value="admin">管理员</option>
                  <option value="operator">签录员</option>
                  <option value="searcher">检索者</option>
                </select>
              </td>
              <td class="px-4 py-2.5">
                <span :class="statusClass(u.status)" class="rounded-full px-2 py-0.5 text-xs font-medium">
                  {{ statusLabel(u.status) }}
                </span>
              </td>
              <td class="px-4 py-2.5">
                <span v-if="u.quota" class="text-xs text-[var(--gov-text-muted)]">
                  {{ u.quota.quota_used }} / {{ u.quota.quota_total }}
                  <span class="ml-1 text-[var(--gov-text-muted)]">（单次上限 {{ u.quota.quota_per_import }}）</span>
                </span>
                <span v-else class="text-xs text-[var(--gov-text-muted)]">未设置</span>
              </td>
              <td class="px-4 py-2.5">
                <div class="flex flex-wrap gap-2">
                  <template v-if="u.status === 'pending'">
                    <button
                      class="rounded px-2 py-0.5 text-xs font-medium bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
                      :disabled="reviewingId === u.id"
                      @click="handleApprove(u)"
                    >通过</button>
                    <button
                      class="rounded px-2 py-0.5 text-xs font-medium bg-red-500 text-white hover:bg-red-600 disabled:opacity-50"
                      :disabled="reviewingId === u.id"
                      @click="handleReject(u)"
                    >驳回</button>
                  </template>
                  <template v-else>
                    <button class="text-xs text-[var(--gov-primary)] hover:underline" @click="openQuotaDialog(u)">设置配额</button>
                    <button class="text-xs text-slate-400 hover:text-orange-500" @click="resetQuota(u)">重置用量</button>
                    <button class="text-xs text-amber-600 hover:underline" @click="handleResetPassword(u)">重置密码</button>
                    <button class="text-xs text-red-500 hover:underline" @click="handleDeleteUser(u)">删除</button>
                  </template>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Tab: Assignments -->
    <div v-if="activeTab === 'assignments'" class="space-y-4">
      <div class="gov-card p-4 space-y-3">
        <h3 class="text-sm font-semibold text-[var(--gov-text)]">新建任务分配</h3>
        <div class="flex flex-wrap gap-3">
          <div class="flex flex-col gap-1">
            <label class="text-xs text-[var(--gov-text-muted)]">批次 ID</label>
            <input v-model="newAssignment.batchId" class="gov-input text-xs w-52" placeholder="batch_xxx…" />
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs text-[var(--gov-text-muted)]">分配给</label>
            <select v-model="newAssignment.operatorId" class="gov-input text-xs w-36">
              <option value="">选择签录员</option>
              <option v-for="op in operators" :key="op.id" :value="op.id">
                {{ op.display_name || op.username }}
              </option>
            </select>
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs text-[var(--gov-text-muted)]">文件数量</label>
            <input v-model.number="newAssignment.fileCount" type="number" min="0" class="gov-input text-xs w-24" />
          </div>
          <div class="flex flex-col gap-1">
            <label class="text-xs text-[var(--gov-text-muted)]">备注</label>
            <input v-model="newAssignment.note" class="gov-input text-xs w-44" placeholder="可选备注…" />
          </div>
          <div class="flex items-end">
            <button class="gov-btn text-sm" :disabled="!newAssignment.batchId || !newAssignment.operatorId" @click="submitAssignment">分配</button>
          </div>
        </div>
        <p v-if="assignmentError" class="text-xs text-red-500">{{ assignmentError }}</p>
      </div>

      <div class="gov-card overflow-hidden">
        <div class="flex items-center justify-between px-4 py-3 border-b border-[var(--gov-border)]">
          <span class="text-sm font-medium text-[var(--gov-text)]">分配记录</span>
          <button class="text-xs text-[var(--gov-primary)] hover:underline" @click="loadAssignments">刷新</button>
        </div>
        <table class="w-full text-sm">
          <thead class="bg-slate-50 border-b border-[var(--gov-border)]">
            <tr>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">批次 ID</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">签录员</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">文件数</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">状态</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">备注</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">创建时间</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--gov-border)]">
            <tr v-if="assignmentsLoading">
              <td colspan="6" class="px-4 py-6 text-center text-[var(--gov-text-muted)]">加载中…</td>
            </tr>
            <tr v-for="a in assignments" :key="a.id" class="hover:bg-slate-50">
              <td class="px-4 py-2.5 font-mono text-xs text-[var(--gov-primary)]">{{ a.batch_id }}</td>
              <td class="px-4 py-2.5">{{ a.operator_name }}</td>
              <td class="px-4 py-2.5">{{ a.file_count }}</td>
              <td class="px-4 py-2.5">
                <select :value="a.status" class="gov-input text-xs w-24" @change="updateStatus(a, $event.target.value)">
                  <option value="pending">待处理</option>
                  <option value="processing">处理中</option>
                  <option value="done">已完成</option>
                  <option value="cancelled">已取消</option>
                </select>
              </td>
              <td class="px-4 py-2.5 text-xs text-[var(--gov-text-muted)]">{{ a.note || '—' }}</td>
              <td class="px-4 py-2.5 text-xs text-[var(--gov-text-muted)]">{{ fmtDate(a.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Tab: Operation Logs -->
    <div v-if="activeTab === 'logs'" class="space-y-4">
      <div class="flex items-center gap-3">
        <select v-model="logFilter.actionType" class="gov-input text-sm w-40">
          <option value="">全部操作</option>
          <option value="import_files">导入文件</option>
          <option value="assign_batch">分配批次</option>
          <option value="set_role">修改角色</option>
          <option value="update_quota">修改配额</option>
          <option value="reset_quota">重置配额</option>
        </select>
        <button class="gov-btn-secondary text-sm" @click="loadLogs">刷新</button>
      </div>

      <div class="gov-card overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 border-b border-[var(--gov-border)]">
            <tr>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">时间</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">操作者</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">操作类型</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">资源</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">详情</th>
              <th class="px-4 py-2.5 text-left text-[var(--gov-text-muted)] font-medium">IP</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-[var(--gov-border)]">
            <tr v-if="logsLoading">
              <td colspan="6" class="px-4 py-6 text-center text-[var(--gov-text-muted)]">加载中…</td>
            </tr>
            <tr v-for="log in logs" :key="log.id" class="hover:bg-slate-50">
              <td class="px-4 py-2.5 text-xs text-[var(--gov-text-muted)] whitespace-nowrap">{{ fmtDate(log.created_at) }}</td>
              <td class="px-4 py-2.5 font-mono text-xs">{{ log.username }}</td>
              <td class="px-4 py-2.5">
                <span class="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium">{{ actionLabel(log.action_type) }}</span>
              </td>
              <td class="px-4 py-2.5 text-xs text-[var(--gov-text-muted)]">{{ log.resource_type }}: {{ log.resource_id }}</td>
              <td class="px-4 py-2.5 text-xs text-[var(--gov-text-muted)] max-w-[240px] truncate" :title="JSON.stringify(log.detail)">
                {{ fmtDetail(log.detail) }}
              </td>
              <td class="px-4 py-2.5 text-xs text-[var(--gov-text-muted)]">{{ log.ip_address || '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Quota Dialog -->
    <div v-if="quotaDialog.open" class="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div class="bg-white rounded-xl shadow-xl p-6 w-80 space-y-4">
        <h3 class="font-semibold text-[var(--gov-text)]">设置配额 — {{ quotaDialog.user?.username }}</h3>
        <div class="space-y-3">
          <div>
            <label class="text-xs text-[var(--gov-text-muted)] block mb-1">单次导入上限（文件数）</label>
            <input v-model.number="quotaDialog.perImport" type="number" min="1" class="gov-input w-full" />
          </div>
          <div>
            <label class="text-xs text-[var(--gov-text-muted)] block mb-1">总配额上限（文件数）</label>
            <input v-model.number="quotaDialog.total" type="number" min="1" class="gov-input w-full" />
          </div>
        </div>
        <div class="flex justify-end gap-2">
          <button class="gov-btn-secondary text-sm" @click="quotaDialog.open = false">取消</button>
          <button class="gov-btn text-sm" @click="saveQuota">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, computed } from 'vue'
import {
  listUsers, setUserRole, setDisplayName,
  updateUserQuota, resetUserQuota,
  listAssignments, createAssignment, updateAssignmentStatus,
  listOperationLogs,
} from '@/api/admin.js'
import { approveUser, rejectUser, resetUserPassword, deleteUser } from '@/api/auth.js'

const pendingCount = computed(() => users.value.filter(u => u.status === 'pending').length)

const tabs = computed(() => [
  { key: 'users', label: '用户管理', badge: pendingCount.value || 0 },
  { key: 'assignments', label: '任务分配', badge: 0 },
  { key: 'logs', label: '操作日志', badge: 0 },
])
const activeTab = ref('users')

// ── Users ──────────────────────────────────────────────────────────────────
const users = ref([])
const usersLoading = ref(false)
const userFilter = ref('')
const editingName = ref(null)
const editNameValue = ref('')

const operators = computed(() => users.value.filter(u => u.role === 'operator'))

async function loadUsers() {
  usersLoading.value = true
  try {
    const { data } = await listUsers(userFilter.value ? { role: userFilter.value } : {})
    users.value = data.items || []
  } finally {
    usersLoading.value = false
  }
}

function startEditName(u) {
  if (editingName.value === u.id) { editingName.value = null; return }
  editingName.value = u.id
  editNameValue.value = u.display_name || ''
}

async function saveDisplayName(u) {
  await setDisplayName(u.id, editNameValue.value)
  u.display_name = editNameValue.value
  editingName.value = null
}

async function changeRole(u, newRole) {
  await setUserRole(u.id, newRole)
  u.role = newRole
  u.is_admin = newRole === 'admin'
}

function statusClass(s) {
  return {
    pending: 'bg-yellow-50 text-yellow-700',
    active: 'bg-green-50 text-green-700',
    rejected: 'bg-red-50 text-red-600',
  }[s] || 'bg-slate-50 text-slate-500'
}
function statusLabel(s) {
  return { pending: '待审核', active: '已激活', rejected: '已拒绝' }[s] || s
}

// ── Approve / Reject ───────────────────────────────────────────────────────
const reviewingId = ref(null)

async function handleApprove(u) {
  if (!confirm(`确认通过 ${u.display_name || u.username} 的注册申请吗？`)) return
  reviewingId.value = u.id
  try {
    await approveUser(u.id)
    await loadUsers()
  } finally {
    reviewingId.value = null
  }
}

async function handleReject(u) {
  if (!confirm(`确认驳回 ${u.display_name || u.username} 的注册申请吗？`)) return
  reviewingId.value = u.id
  try {
    await rejectUser(u.id)
    await loadUsers()
  } finally {
    reviewingId.value = null
  }
}

async function handleResetPassword(u) {
  const newPwd = prompt(`请输入 ${u.display_name || u.username} 的新密码（至少6位）：`)
  if (!newPwd) return
  if (newPwd.length < 6) { alert('密码至少6位。'); return }
  try {
    await resetUserPassword(u.id, newPwd)
    alert(`已重置 ${u.display_name || u.username} 的密码。`)
  } catch (e) {
    alert(e?.response?.data?.detail || e?.response?.data?.message || '重置密码失败')
  }
}

async function handleDeleteUser(u) {
  if (!confirm(`确认永久删除用户 ${u.display_name || u.username}（${u.username}）吗？此操作不可撤销！`)) return
  try {
    await deleteUser(u.id)
    await loadUsers()
  } catch (e) {
    alert(e?.response?.data?.detail || e?.response?.data?.message || '删除用户失败')
  }
}

// ── Quota dialog ───────────────────────────────────────────────────────────
const quotaDialog = reactive({ open: false, user: null, perImport: 200, total: 2000 })

async function openQuotaDialog(u) {
  quotaDialog.user = u
  quotaDialog.perImport = u.quota?.quota_per_import ?? 200
  quotaDialog.total = u.quota?.quota_total ?? 2000
  quotaDialog.open = true
}

async function saveQuota() {
  await updateUserQuota(quotaDialog.user.id, {
    quota_per_import: quotaDialog.perImport,
    quota_total: quotaDialog.total,
  })
  quotaDialog.open = false
  await loadUsers()
}

async function resetQuota(u) {
  if (!confirm(`确认重置 ${u.username} 的已用配额吗？`)) return
  await resetUserQuota(u.id)
  await loadUsers()
}

// ── Assignments ────────────────────────────────────────────────────────────
const assignments = ref([])
const assignmentsLoading = ref(false)
const assignmentError = ref('')
const newAssignment = reactive({ batchId: '', operatorId: '', fileCount: 0, note: '' })

async function loadAssignments() {
  assignmentsLoading.value = true
  try {
    const { data } = await listAssignments()
    assignments.value = data.items || []
  } finally {
    assignmentsLoading.value = false
  }
}

async function submitAssignment() {
  assignmentError.value = ''
  try {
    await createAssignment({
      batch_id: newAssignment.batchId,
      operator_id: Number(newAssignment.operatorId),
      file_count: newAssignment.fileCount,
      note: newAssignment.note || null,
    })
    newAssignment.batchId = ''
    newAssignment.operatorId = ''
    newAssignment.fileCount = 0
    newAssignment.note = ''
    await loadAssignments()
  } catch (e) {
    assignmentError.value = e?.response?.data?.detail || '分配失败'
  }
}

async function updateStatus(a, newStatus) {
  await updateAssignmentStatus(a.id, newStatus)
  a.status = newStatus
}

// ── Logs ───────────────────────────────────────────────────────────────────
const logs = ref([])
const logsLoading = ref(false)
const logFilter = reactive({ actionType: '' })

async function loadLogs() {
  logsLoading.value = true
  try {
    const params = {}
    if (logFilter.actionType) params.action_type = logFilter.actionType
    const { data } = await listOperationLogs(params)
    logs.value = data.items || []
  } finally {
    logsLoading.value = false
  }
}

const ACTION_LABELS = {
  import_files: '导入文件',
  assign_batch: '分配批次',
  set_role: '修改角色',
  update_quota: '修改配额',
  reset_quota: '重置配额',
}
function actionLabel(t) { return ACTION_LABELS[t] || t }

function fmtDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return `${d.toLocaleDateString('zh-CN')} ${d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
}

function fmtDetail(detail) {
  if (!detail || !Object.keys(detail).length) return '—'
  return Object.entries(detail).map(([k, v]) => `${k}: ${v}`).join('，')
}

onMounted(async () => {
  await loadUsers()
  await loadAssignments()
  await loadLogs()
})
</script>
