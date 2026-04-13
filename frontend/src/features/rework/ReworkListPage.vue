<template>
  <AppShell>
    <div class="p-5 space-y-4">
      <div class="flex items-center justify-between gap-3">
        <div>
          <h1 class="gov-page-header">返工跟踪</h1>
        </div>
        <div class="flex items-center gap-2">
          <span v-if="refreshStatusText" class="hidden text-xs text-[var(--gov-text-muted)] md:inline">{{ refreshStatusText }}</span>
          <button @click="handleManualRefresh" class="px-3 py-2 border border-[var(--gov-border)] text-sm rounded-md text-[var(--gov-text-muted)] hover:bg-slate-50 transition">
            刷新
          </button>
        </div>
      </div>

      <div v-if="opMsg" class="rounded-md border p-3 text-sm" :class="opMsg.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'">
        {{ opMsg.text }}
      </div>

      <DataTable
        :columns="columns"
        :rows="rows"
        :total="total"
        :page="page"
        :page-size="pageSize"
        :loading="loading"
        row-key="id"
        @page-change="onPageChange"
      >
        <template #filters>
          <div class="flex flex-wrap gap-3 items-center">
            <select v-model="filters.status" @change="reload" class="gov-select text-sm">
              <option value="">全部状态</option>
              <option value="pending">待处理</option>
              <option value="processing">处理中</option>
              <option value="done">已完成</option>
              <option value="rejected">已驳回</option>
            </select>
            <input v-model.trim="filters.keyword" @keyup.enter="reload" placeholder="任务ID / 卷宗ID" class="gov-filter-input text-sm w-[240px]" />
            <button @click="reload" class="gov-btn text-sm">查询</button>
            <button @click="reset" class="text-sm text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]">重置</button>
          </div>
        </template>

        <template #cell-status="{ value }">
          <StatusBadge :status="value" />
        </template>

        <template #cell-priority="{ value }">
          <span class="text-xs rounded px-2 py-0.5 border" :class="priorityClass(value)">{{ value || 'normal' }}</span>
        </template>

        <template #cell-created_at="{ value }">
          <span class="text-sm text-[var(--gov-text-muted)]">{{ fmt(value) }}</span>
        </template>

        <template #actions="{ row }">
          <div class="flex gap-2 justify-end">
            <button @click="viewDetail(row)" class="text-xs text-[var(--gov-primary)] hover:underline">详情</button>
            <button v-if="canManageRework && row.status === 'pending'" @click="handleAccept(row)" :disabled="actionId === row.id" class="text-xs text-green-600 hover:underline disabled:opacity-50">受理</button>
            <button v-if="canManageRework && row.status === 'pending'" @click="openReject(row)" :disabled="actionId === row.id" class="text-xs text-red-600 hover:underline disabled:opacity-50">驳回</button>
          </div>
        </template>
      </DataTable>

      <div v-if="loadError" class="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {{ loadError }}
      </div>
    </div>

    <!-- 详情抽屉 -->
    <DetailDrawer v-model="showDrawer" title="返工任务详情">
      <div v-if="drawerRow" class="space-y-4">
        <div class="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">任务ID</p>
            <p class="mt-0.5 font-mono text-[var(--gov-text)]">{{ drawerRow.id }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">卷宗ID</p>
            <p class="mt-0.5 font-mono text-[var(--gov-text)]">{{ drawerRow.record_id || '-' }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">问题类型</p>
            <p class="mt-0.5 text-[var(--gov-text)]">{{ drawerRow.issue_type || '-' }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">优先级</p>
            <span class="text-xs rounded px-2 py-0.5 border" :class="priorityClass(drawerRow.priority)">{{ drawerRow.priority || 'normal' }}</span>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">状态</p>
            <div class="mt-1"><StatusBadge :status="drawerRow.status" /></div>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">提报人</p>
            <p class="mt-0.5 text-[var(--gov-text)]">{{ drawerRow.reported_by || drawerRow.created_by || '-' }}</p>
          </div>
          <div class="col-span-2">
            <p class="text-xs text-[var(--gov-text-muted)]">影响范围</p>
            <p class="mt-0.5 text-sm text-[var(--gov-text)]">{{ formatAffectedScope(drawerRow.affected_scope, drawerRow.description) }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">创建时间</p>
            <p class="mt-0.5 text-[var(--gov-text)]">{{ fmt(drawerRow.created_at) }}</p>
          </div>
        </div>
      </div>
      <template #footer>
        <div v-if="canManageRework && drawerRow?.status === 'pending'" class="flex gap-2">
          <button @click="handleAccept(drawerRow)" :disabled="actionId === drawerRow?.id" class="px-4 py-2 text-sm rounded-md bg-green-600 text-white hover:bg-green-700 transition disabled:opacity-50">受理</button>
          <button @click="openReject(drawerRow)" :disabled="actionId === drawerRow?.id" class="px-4 py-2 text-sm rounded border border-red-300 text-red-600 hover:bg-red-50 disabled:opacity-50">驳回</button>
        </div>
      </template>
    </DetailDrawer>

    <!-- 驳回弹窗 -->
    <div v-if="rejectingRow" class="gov-modal-backdrop">
      <div class="gov-modal-panel w-[460px] p-5">
        <h3 class="text-base font-semibold text-[var(--gov-text)]">驳回返工</h3>
        <p class="text-sm text-[var(--gov-text-muted)] mt-1">#{{ rejectingRow.id }}</p>
        <textarea v-model="rejectReason" rows="3" class="mt-4 w-full gov-filter-input text-sm resize-none" placeholder="请输入驳回原因"></textarea>
        <div class="mt-4 flex justify-end gap-2">
          <button @click="cancelReject" class="px-4 py-2 border border-[var(--gov-border)] rounded-md text-sm text-[var(--gov-text-muted)] hover:bg-slate-50 transition">取消</button>
          <button @click="confirmReject" :disabled="!rejectReason.trim()" class="px-4 py-2 bg-red-600 text-white rounded-md text-sm disabled:opacity-50 hover:bg-red-700 transition">确认驳回</button>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import dayjs from 'dayjs'

import AppShell from '@/layouts/AppShell.vue'
import DataTable from '@/shared/components/DataTable.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import { useAuthState } from '@/composables/useAuthState'
import { listReworkTasks, acceptReworkTask, rejectReworkTask } from '@/api/archive'
import { formatRefreshTime } from '@/features/batches/progress'

const route = useRoute()
const { auth, authProfile } = useAuthState()

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const loadError = ref('')
const opMsg = ref(null)
const actionId = ref(null)

const filters = ref({ status: '', keyword: '' })

const showDrawer = ref(false)
const drawerRow = ref(null)
const rejectingRow = ref(null)
const rejectReason = ref('')
const lastRefreshedAt = ref(null)

const AUTO_REFRESH_MS = 15000
const ACTIVE_REWORK_STATUSES = new Set(['pending', 'processing', 'accepted', 'in_rework', 'running'])
let reworkAutoRefreshTimer = null
let reworkLoadInFlight = false

const isMineMode = computed(() => route.path === '/rework/my')
const canManageRework = computed(() => authProfile.value.isSysAdmin)
const canViewTenantWide = computed(() => authProfile.value.isSysAdmin || authProfile.value.isTenantAdmin)
const shouldPollReworks = computed(() => {
  const selectedStatus = String(filters.value.status || '').trim().toLowerCase()
  if (!selectedStatus || ACTIVE_REWORK_STATUSES.has(selectedStatus)) {
    return true
  }
  return rows.value.some((row) => ACTIVE_REWORK_STATUSES.has(String(row?.status || '').trim().toLowerCase()))
})
const refreshStatusText = computed(() => {
  const stamp = formatRefreshTime(lastRefreshedAt.value)
  if (shouldPollReworks.value) {
    return stamp ? `${stamp} 更新 · 返工列表每15s自动刷新` : '返工列表每15s自动刷新'
  }
  return stamp ? `${stamp} 更新` : ''
})

const columns = [
  { key: 'id', label: '返工任务ID', width: '140px', mono: true },
  { key: 'record_id', label: '卷宗ID', width: '150px', mono: true },
  { key: 'issue_type', label: '问题类型', width: '140px' },
  { key: 'priority', label: '优先级', width: '100px' },
  { key: 'status', label: '状态', width: '120px' },
  { key: 'created_at', label: '创建时间', width: '170px' },
]

function applyRouteFilters() {
  filters.value = {
    ...filters.value,
    status: route.query.status ? String(route.query.status) : '',
    keyword: route.query.keyword ? String(route.query.keyword) : '',
  }
}

function fmt(v) {
  return v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'
}

function priorityClass(priority) {
  const p = String(priority || '').toLowerCase()
  if (p === 'urgent') return 'border-red-300 text-red-600 bg-red-50'
  if (p === 'high') return 'border-amber-300 text-amber-700 bg-amber-50'
  if (p === 'low') return 'border-slate-300 text-slate-600 bg-slate-50'
  return 'border-blue-300 text-blue-600 bg-blue-50'
}

function formatAffectedScope(scope, fallback = '') {
  if (!scope) return fallback || '-'
  if (typeof scope === 'string') return scope
  const summary = [
    scope.label,
    scope.record_id ? `卷宗 ${scope.record_id}` : '',
    scope.reject_reason ? `驳回原因：${scope.reject_reason}` : '',
  ].filter(Boolean)
  return summary.join(' / ') || fallback || JSON.stringify(scope)
}

function buildParams() {
  return {
    page: page.value,
    page_size: pageSize.value,
    status: filters.value.status || undefined,
    q: filters.value.keyword || undefined,
    mine: isMineMode.value ? true : undefined,
    reporter: !canViewTenantWide.value ? auth.value?.username || undefined : undefined,
  }
}

function extractRows(data) {
  if (Array.isArray(data?.items)) return data.items
  if (Array.isArray(data?.tasks)) return data.tasks
  if (Array.isArray(data)) return data
  return []
}

function syncDrawerRow(nextRows) {
  if (!drawerRow.value?.id) return
  const nextSelected = nextRows.find((row) => String(row.id) === String(drawerRow.value.id))
  if (nextSelected) {
    drawerRow.value = nextSelected
  }
}

async function load(options = {}) {
  if (reworkLoadInFlight) return
  reworkLoadInFlight = true
  if (!options.silent) {
    loading.value = true
  }
  loadError.value = ''
  try {
    const res = await listReworkTasks(buildParams())
    const data = res.data || {}
    rows.value = extractRows(data)
    total.value = data.total || rows.value.length
    syncDrawerRow(rows.value)
    lastRefreshedAt.value = new Date()
  } catch (e) {
    console.error('加载返工列表失败', e)
    loadError.value = '加载返工列表失败，请稍后重试。'
    rows.value = []
    total.value = 0
  } finally {
    if (!options.silent) {
      loading.value = false
    }
    reworkLoadInFlight = false
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  if (!shouldPollReworks.value) return
  reworkAutoRefreshTimer = window.setInterval(() => {
    if (!document.hidden && !rejectingRow.value && !actionId.value && !showDrawer.value) {
      load({ silent: true })
    }
  }, AUTO_REFRESH_MS)
}

function stopAutoRefresh() {
  if (reworkAutoRefreshTimer) {
    window.clearInterval(reworkAutoRefreshTimer)
    reworkAutoRefreshTimer = null
  }
}

function reload() {
  page.value = 1
  load()
}

function reset() {
  filters.value = { status: '', keyword: '' }
  reload()
}

async function handleManualRefresh() {
  await load()
}

function onPageChange(p) {
  page.value = p
  load()
}

function viewDetail(row) {
  drawerRow.value = row
  showDrawer.value = true
}

async function handleAccept(row) {
  actionId.value = row.id
  opMsg.value = null
  try {
    await acceptReworkTask(row.id)
    opMsg.value = { ok: true, text: `返工任务 ${row.id} 已受理` }
    await load()
  } catch (e) {
    opMsg.value = { ok: false, text: '受理失败：' + (e?.response?.data?.detail || e.message || '未知错误') }
  } finally {
    actionId.value = null
  }
}

function openReject(row) {
  rejectingRow.value = row
  rejectReason.value = ''
}

function cancelReject() {
  rejectingRow.value = null
  rejectReason.value = ''
}

async function confirmReject() {
  if (!rejectingRow.value || !rejectReason.value.trim()) return
  actionId.value = rejectingRow.value.id
  opMsg.value = null
  try {
    await rejectReworkTask(rejectingRow.value.id, rejectReason.value.trim())
    opMsg.value = { ok: true, text: '返工任务已驳回' }
    cancelReject()
    await load()
  } catch (e) {
    opMsg.value = { ok: false, text: '驳回失败：' + (e?.response?.data?.detail || e.message || '未知错误') }
  } finally {
    actionId.value = null
  }
}

onMounted(() => {
  applyRouteFilters()
  load()
})

watch(shouldPollReworks, (active) => {
  if (active) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

watch(
  () => [route.path, route.query.status, route.query.keyword],
  () => {
    applyRouteFilters()
    reload()
  }
)

onBeforeUnmount(() => {
  stopAutoRefresh()
})
</script>
