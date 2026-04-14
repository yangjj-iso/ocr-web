<template>
  <AppShell>
    <div class="p-5 space-y-4">
      <div class="flex items-center justify-between gap-3">
        <div>
          <h1 class="gov-page-header">任务列表</h1>
        </div>
        <div class="flex items-center gap-2">
          <span v-if="refreshStatusText" class="hidden text-xs text-[var(--gov-text-muted)] md:inline">{{ refreshStatusText }}</span>
          <button @click="handleManualRefresh" class="px-3 py-2 border border-[var(--gov-border)] text-sm rounded-md text-[var(--gov-text-muted)] hover:bg-slate-50 transition">
            刷新
          </button>
        </div>
      </div>

      <DataTable
        :columns="columns"
        :rows="tasks"
        :total="total"
        :page="page"
        :page-size="pageSize"
        :loading="loading"
        row-key="id"
        clickable
        @row-click="handleRowClick"
        @page-change="handlePageChange"
      >
        <template #filters>
          <div class="flex gap-3 flex-wrap items-center">
            <select v-model="filters.type" @change="reloadFromFirstPage" class="gov-select text-sm">
              <option value="">全部类型</option>
              <option value="boundary_review">边界校正</option>
              <option value="metadata_review">元数据检录</option>
              <option value="order_review">排序复核</option>
              <option value="final_release">发布确认</option>
              <option value="rework">返工处理</option>
            </select>
            <select v-model="filters.status" @change="reloadFromFirstPage" class="gov-select text-sm">
              <option value="">全部状态</option>
              <option value="pending">待处理</option>
              <option value="processing">处理中</option>
              <option value="human_review">待人工审核</option>
              <option value="done">已完成</option>
              <option value="failed">失败</option>
            </select>
            <input
              v-model.trim="filters.keyword"
              @keyup.enter="reloadFromFirstPage"
              class="gov-filter-input text-sm w-[220px]"
              placeholder="批次ID / 任务ID"
            />
            <button @click="reloadFromFirstPage" class="gov-btn text-sm">查询</button>
            <button @click="resetFilters" class="px-2 text-sm text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]">重置</button>
          </div>
        </template>

        <template #cell-type="{ value }">
          <span class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium text-[var(--gov-text-muted)] bg-slate-100">
            {{ formatTaskType(value) }}
          </span>
        </template>

        <template #cell-status="{ value }">
          <StatusBadge :status="value" />
        </template>

        <template #cell-assignee="{ row }">
          <span class="text-sm">{{ row.assignee || row.assignee_name || '-' }}</span>
        </template>

        <template #cell-created_at="{ value }">
          <span class="text-sm text-[var(--gov-text-muted)]">{{ formatDate(value) }}</span>
        </template>

        <template #actions="{ row }">
          <div class="flex gap-2 justify-end">
            <button @click.stop="goToTask(row)" class="text-xs text-[var(--gov-primary)] hover:underline">处理</button>
            <button v-if="canAssignTask" @click.stop="openAssign(row)" class="text-xs text-amber-600 hover:underline">分配</button>
          </div>
        </template>
      </DataTable>

      <div v-if="loadError" class="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {{ loadError }}
      </div>

      <div v-if="opMsg" class="rounded-md border p-3 text-sm" :class="opMsg.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'">
        {{ opMsg.text }}
      </div>
    </div>

    <div v-if="showAssign" class="gov-modal-backdrop">
      <div class="gov-modal-panel w-[420px] p-5">
        <h3 class="text-base font-semibold text-[var(--gov-text)]">任务分配</h3>
        <p class="text-sm text-[var(--gov-text-muted)] mt-1">任务 {{ selectedTask?.id }} / {{ formatTaskType(selectedTask?.type) }}</p>

        <div class="mt-4 space-y-3">
          <div>
            <label class="text-sm text-[var(--gov-text-muted)] block mb-1">选择执行人</label>
            <select v-model="assignForm.userId" class="w-full gov-select text-sm">
              <option value="">请选择</option>
              <option v-for="u in assignableUsers" :key="u.id || u.user_id || u.username" :value="u.id || u.user_id || u.username">
                {{ u.display_name || u.username }}
              </option>
            </select>
          </div>
          <div>
            <label class="text-sm text-[var(--gov-text-muted)] block mb-1">备注</label>
            <textarea v-model="assignForm.notes" rows="2" class="w-full gov-filter-input text-sm resize-none" placeholder="可选"></textarea>
          </div>
        </div>

        <div class="mt-5 flex justify-end gap-2">
          <button @click="closeAssign" class="px-4 py-2 border border-[var(--gov-border)] text-sm rounded-md text-[var(--gov-text-muted)] hover:bg-slate-50 transition">取消</button>
          <button @click="submitAssign" :disabled="assigning || !assignForm.userId" class="gov-btn text-sm disabled:opacity-50">
            {{ assigning ? '提交中...' : '确认分配' }}
          </button>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'

import AppShell from '@/layouts/AppShell.vue'
import DataTable from '@/shared/components/DataTable.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import { useAuthState } from '@/composables/useAuthState'
import { listReviewTasks, getMyAssignedTasks, assignTask } from '@/api/archive'
import { listUsers } from '@/api/admin'
import { buildAuthProfile } from '@/utils/authz.js'
import { formatRefreshTime } from '@/features/batches/progress'

const route = useRoute()
const router = useRouter()
const { authProfile } = useAuthState()

const canAssignTask = computed(() => authProfile.value.isSysAdmin || authProfile.value.isTenantAdmin)
const canViewAll = computed(() => canAssignTask.value)

const tasks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const loadError = ref('')
const opMsg = ref(null)
const filters = ref({ type: '', status: '', keyword: '' })

const columns = [
  { key: 'id', label: '任务ID', width: '140px', mono: true },
  { key: 'type', label: '任务类型', width: '130px' },
  { key: 'batch_id', label: '批次ID', width: '180px' },
  { key: 'assignee', label: '执行人', width: '120px' },
  { key: 'status', label: '状态', width: '120px' },
  { key: 'created_at', label: '创建时间', width: '160px' },
]

const showAssign = ref(false)
const assigning = ref(false)
const selectedTask = ref(null)
const assignableUsers = ref([])
const assignForm = ref({ userId: '', notes: '' })
const lastRefreshedAt = ref(null)

const AUTO_REFRESH_MS = 15000
const ACTIVE_TASK_STATUSES = new Set(['pending', 'processing', 'human_review', 'claimed', 'running'])
let taskAutoRefreshTimer = null
let taskLoadInFlight = false

const shouldPollForTasks = computed(() => {
  const selectedStatus = String(filters.value.status || '').trim().toLowerCase()
  if (!selectedStatus || ACTIVE_TASK_STATUSES.has(selectedStatus)) {
    return true
  }
  return tasks.value.some((task) => ACTIVE_TASK_STATUSES.has(String(task?.status || '').trim().toLowerCase()))
})

const refreshStatusText = computed(() => {
  const stamp = formatRefreshTime(lastRefreshedAt.value)
  if (shouldPollForTasks.value) {
    return stamp ? `${stamp} 更新 · 任务列表每15s自动刷新` : '任务列表每15s自动刷新'
  }
  return stamp ? `${stamp} 更新` : ''
})

function normalizeTaskType(type) {
  return {
    boundary: 'boundary_review',
    boundary_review: 'boundary_review',
    metadata: 'metadata_review',
    metadata_review: 'metadata_review',
    ordering: 'order_review',
    order_review: 'order_review',
    final_release: 'final_release',
    rework: 'rework',
  }[String(type || '').trim()] || String(type || '').trim()
}

function buildParams() {
  return {
    page: page.value,
    page_size: pageSize.value,
    type: filters.value.type || undefined,
    status: filters.value.status || undefined,
    q: filters.value.keyword || undefined,
  }
}

function matchesTaskKeyword(task, keyword) {
  const q = String(keyword || '').trim().toLowerCase()
  if (!q) return true
  const haystack = [
    task?.id,
    task?.review_task_id,
    task?.batch_id,
    task?.title,
    task?.reason,
    task?.assignee,
    task?.assignee_name,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase()
  return haystack.includes(q)
}

function filterAssignedTasks(items, params) {
  const normalizedType = normalizeTaskType(params.type)
  return items.filter((task) => {
    const taskType = normalizeTaskType(task?.type || task?.task_type)
    if (normalizedType && taskType !== normalizedType) return false
    return matchesTaskKeyword(task, params.q)
  })
}

function extractArray(data, keys = ['items', 'tasks']) {
  for (const key of keys) {
    if (Array.isArray(data?.[key])) return data[key]
  }
  if (Array.isArray(data)) return data
  return []
}

function syncSelectedTask(nextTasks) {
  if (!selectedTask.value?.id) return
  const nextSelected = nextTasks.find((task) => String(task.id) === String(selectedTask.value.id))
  if (nextSelected) {
    selectedTask.value = nextSelected
  }
}

async function loadTasks(options = {}) {
  if (taskLoadInFlight) return
  taskLoadInFlight = true
  if (!options.silent) {
    loading.value = true
  }
  loadError.value = ''
  try {
    const params = buildParams()
    const res = canViewAll.value
      ? await listReviewTasks(params)
      : await getMyAssignedTasks({
          page: 1,
          page_size: 500,
          status: params.status,
        })
    const data = res.data || {}
    const items = data.items || data.tasks || []

    if (canViewAll.value) {
      tasks.value = items
      total.value = data.total || tasks.value.length
    } else {
      const filteredItems = filterAssignedTasks(items, params)
      total.value = filteredItems.length
      const start = (page.value - 1) * pageSize.value
      tasks.value = filteredItems.slice(start, start + pageSize.value)
    }
    syncSelectedTask(tasks.value)
    lastRefreshedAt.value = new Date()
  } catch (error) {
    console.error('加载任务失败', error)
    loadError.value = '加载任务失败，请检查网络或稍后重试。'
    tasks.value = []
    total.value = 0
  } finally {
    if (!options.silent) {
      loading.value = false
    }
    taskLoadInFlight = false
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  if (!shouldPollForTasks.value) return
  taskAutoRefreshTimer = window.setInterval(() => {
    if (!document.hidden && !showAssign.value && !assigning.value) {
      loadTasks({ silent: true })
    }
  }, AUTO_REFRESH_MS)
}

function stopAutoRefresh() {
  if (taskAutoRefreshTimer) {
    window.clearInterval(taskAutoRefreshTimer)
    taskAutoRefreshTimer = null
  }
}

async function loadAssignableUsers() {
  if (!canAssignTask.value) return
  try {
    const res = await listUsers({ page: 1, page_size: 200 })
    const items = extractArray(res.data, ['items'])
    assignableUsers.value = items.filter((u) => {
      const profile = buildAuthProfile(u)
      return !profile.isSysAdmin && !profile.isTenantAdmin && (profile.hasOperator || profile.hasSearcher)
    })
  } catch (error) {
    console.error('加载用户失败', error)
  }
}

function reloadFromFirstPage() {
  page.value = 1
  loadTasks()
}

function resetFilters() {
  filters.value = { type: '', status: '', keyword: '' }
  reloadFromFirstPage()
}

async function handleManualRefresh() {
  await loadTasks()
}

function handlePageChange(p) {
  page.value = p
  loadTasks()
}

function formatTaskType(type) {
  const map = {
    boundary: '边界校正',
    boundary_review: '边界校正',
    metadata: '元数据检录',
    metadata_review: '元数据检录',
    ordering: '排序复核',
    order_review: '排序复核',
    final_release: '发布确认',
    rework: '返工处理',
  }
  return map[type] || type || '-'
}

function formatDate(value) {
  if (!value) return '-'
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

function resolveTaskRoute(task) {
  const taskType = normalizeTaskType(task?.type || task?.task_type)
  if (taskType === 'boundary_review') return `/review/structure/${task.id}`
  if (taskType === 'metadata_review') return `/review/catalog/${task.id}`
  if (taskType === 'final_release') return `/release/console/${task.id}`
  if (taskType === 'rework') return '/rework'
  return `/review/${task.id}`
}

function goToTask(task) {
  if (!task) return
  router.push(resolveTaskRoute(task))
}

function handleRowClick(task) {
  goToTask(task)
}

function openAssign(task) {
  selectedTask.value = task
  assignForm.value = { userId: '', notes: '' }
  showAssign.value = true
}

function closeAssign() {
  showAssign.value = false
  selectedTask.value = null
}

async function submitAssign() {
  if (!selectedTask.value || !assignForm.value.userId) return
  assigning.value = true
  opMsg.value = null
  try {
    const assignee = assignableUsers.value.find((user) => String(user.id || user.user_id || user.username) === String(assignForm.value.userId))
    await assignTask({
      task_id: selectedTask.value.id,
      assignee_id: assignee?.id || assignee?.user_id || Number(assignForm.value.userId) || undefined,
      assignee_username: assignee?.username || undefined,
      notes: assignForm.value.notes || undefined,
    })
    opMsg.value = { ok: true, text: `任务 ${selectedTask.value.id} 已分配` }
    closeAssign()
    await loadTasks()
  } catch (error) {
    console.error('任务分配失败', error)
    opMsg.value = { ok: false, text: '任务分配失败：' + (error?.response?.data?.detail || error.message || '未知错误') }
  } finally {
    assigning.value = false
  }
}

function applyRouteFilters() {
  filters.value = {
    ...filters.value,
    type: route.query.type ? String(route.query.type) : '',
    keyword: route.query.batchId
      ? String(route.query.batchId)
      : route.query.keyword
        ? String(route.query.keyword)
        : filters.value.keyword,
  }
}

onMounted(async () => {
  applyRouteFilters()
  await Promise.all([loadTasks(), loadAssignableUsers()])
})

watch(shouldPollForTasks, (active) => {
  if (active) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

watch(() => [route.query.type, route.query.batchId, route.query.keyword], () => {
  applyRouteFilters()
  reloadFromFirstPage()
})

onBeforeUnmount(() => {
  stopAutoRefresh()
})
</script>
