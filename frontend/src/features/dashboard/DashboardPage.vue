<template>
  <AppShell>
    <div class="mx-auto max-w-[1440px] px-5 py-4 space-y-5">
      <!-- Error banner -->
      <div v-if="loadError" class="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5">
        <svg class="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
          <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
        </svg>
        <span class="text-sm text-amber-700">{{ loadError }}</span>
      </div>

      <!-- Header -->
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-lg font-semibold text-[var(--gov-text)]">
            {{ greeting }}，{{ displayName }}
          </h1>
          <p class="mt-0.5 text-xs text-[var(--gov-text-muted)]">{{ todayStr }}</p>
        </div>
        <!-- Quick action buttons based on role -->
        <div class="flex gap-2">
          <button
            v-if="canImport"
            class="flex items-center gap-1.5 rounded-lg bg-[var(--gov-primary)] px-4 py-2 text-sm font-medium text-white hover:brightness-105"
            @click="$router.push('/batches/new')"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
            新建批次
          </button>
          <button
            v-if="isSearcher"
            class="flex items-center gap-1.5 rounded-lg border border-[var(--gov-border)] bg-white px-4 py-2 text-sm font-medium text-[var(--gov-text)] hover:bg-slate-50"
            @click="$router.push('/archives')"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/>
            </svg>
            检索卷宗
          </button>
        </div>
      </div>

      <!-- KPI stat cards (role-aware) -->
      <div class="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          v-for="card in kpiCards"
          :key="card.label"
          :label="card.label"
          :value="card.value"
          :sub="card.sub"
          :color="card.color"
          :loading="statsLoading"
        />
      </div>

      <!-- Todo / pending tasks panel -->
      <div class="grid gap-3 lg:grid-cols-2">
        <!-- Pending tasks widget -->
        <div class="rounded-lg border border-[var(--gov-border)] bg-white p-4">
          <div class="mb-3 flex items-center justify-between">
            <h3 class="text-[13px] font-semibold text-[var(--gov-text)]">我的待办</h3>
            <button
              class="text-xs text-[var(--gov-primary)] hover:underline"
              @click="$router.push(todoRoute)"
            >查看全部</button>
          </div>
          <div v-if="tasksLoading" class="flex items-center justify-center py-8">
            <svg class="h-5 w-5 animate-spin text-slate-300" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" />
            </svg>
          </div>
          <div v-else-if="!pendingTasks.length" class="py-8 text-center text-sm text-[var(--gov-text-muted)]">
            暂无待办任务
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="task in pendingTasks.slice(0, 5)"
              :key="task.id"
              class="group flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-slate-50"
              @click="goTask(task)"
            >
              <StatusBadge :status="task.type || task.status" />
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-medium text-[var(--gov-text)]">{{ task.title || task.batch_id || task.id }}</p>
                <p class="text-[11px] text-[var(--gov-text-muted)]">{{ formatTime(task.created_at) }}</p>
              </div>
              <svg class="h-4 w-4 text-slate-300 group-hover:text-[var(--gov-primary)]" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
              </svg>
            </div>
          </div>
        </div>

        <!-- Recent batches / activity widget -->
        <div class="rounded-lg border border-[var(--gov-border)] bg-white p-4">
          <div class="mb-3 flex items-center justify-between">
            <h3 class="text-[13px] font-semibold text-[var(--gov-text)]">
              {{ isSearcher ? '最近入库卷宗' : '最近批次' }}
            </h3>
            <button
              class="text-xs text-[var(--gov-primary)] hover:underline"
              @click="$router.push(isSearcher ? '/archives' : '/batches')"
            >查看全部</button>
          </div>
          <div v-if="recentLoading" class="flex items-center justify-center py-8">
            <svg class="h-5 w-5 animate-spin text-slate-300" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" />
            </svg>
          </div>
          <div v-else-if="!recentItems.length" class="py-8 text-center text-sm text-[var(--gov-text-muted)]">
            暂无记录
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="item in recentItems.slice(0, 5)"
              :key="item.id"
              class="group flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-slate-50"
              @click="goItem(item)"
            >
              <span class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-600">
                {{ (item.batch_id || item.id || '?').toString().slice(-3) }}
              </span>
              <div class="min-w-0 flex-1">
                <p class="truncate text-sm font-medium text-[var(--gov-text)]">{{ item.filename || item.batch_id || item.title || item.id }}</p>
                <p class="text-[11px] text-[var(--gov-text-muted)]">{{ item.page_count || item.doc_count || 0 }} 件 · {{ formatTime(item.created_at) }}</p>
              </div>
              <StatusBadge :status="item.status" />
            </div>
          </div>
        </div>
      </div>

      <!-- Alerts / warnings (admin/tenant admin only) -->
      <div
        v-if="(isTenantAdmin || isSysAdmin) && alerts.length"
        class="rounded-lg border border-amber-200 bg-amber-50 p-3"
      >
        <h4 class="mb-1.5 text-[13px] font-semibold text-amber-800">风险告警</h4>
        <ul class="space-y-1">
          <li
            v-for="alert in alerts"
            :key="alert.id"
            class="flex items-start gap-2 text-sm text-amber-700"
          >
            <svg class="mt-0.5 h-4 w-4 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
            </svg>
            {{ alert.message }}
          </li>
        </ul>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '@/layouts/AppShell.vue'
import StatCard from '@/shared/components/StatCard.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import { useAuthState } from '@/composables/useAuthState.js'
import { getArchiveDashboardStats, getMyAssignedTasks, listBatches, listArchiveRecords } from '@/api/archive.js'

const router = useRouter()
const authState = useAuthState()
const auth = authState.auth
const authProfile = authState.authProfile

const statsLoading = ref(true)
const tasksLoading = ref(true)
const recentLoading = ref(true)
const loadError = ref('')

const stats = ref({})
const pendingTasks = ref([])
const recentItems = ref([])
const alerts = ref([])

const displayName = computed(() =>
  auth.value?.display_name || auth.value?.username || '用户'
)

const isSysAdmin = computed(() => authProfile.value.isSysAdmin)
const isTenantAdmin = computed(() => authProfile.value.isTenantAdmin)
const canImport = computed(() => authProfile.value.hasOperator)
const isOperator = computed(() => !isSysAdmin.value && !isTenantAdmin.value && authProfile.value.hasOperator)
const isSearcher = computed(() => !isSysAdmin.value && !isTenantAdmin.value && !authProfile.value.hasOperator && authProfile.value.hasSearcher)

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h < 12) return '早上好'
  if (h < 18) return '下午好'
  return '晚上好'
})

const todayStr = computed(() =>
  new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })
)

const todoRoute = computed(() => '/tasks')

// KPI cards definition based on role
const kpiCards = computed(() => {
  const s = stats.value
  if (isSysAdmin.value) {
    return [
      { label: '租户总数', value: s.tenants ?? '—', color: 'purple' },
      { label: '今日处理量', value: s.todayTasks ?? '—', color: 'blue' },
      { label: '活跃任务', value: s.processingTasks ?? '—', color: 'amber' },
      { label: 'OCR失败率', value: s.failRate ? `${s.failRate}%` : '—', color: 'red', sub: '近24小时' },
    ]
  }
  if (isTenantAdmin.value) {
    return [
      { label: '待导入批次', value: s.pendingBatches ?? '—', color: 'amber' },
      { label: '处理中卷宗', value: s.processingTasks ?? '—', color: 'blue' },
      { label: '待最终确认', value: s.pendingRelease ?? '—', color: 'purple' },
      { label: '返工中', value: s.reworking ?? '—', color: 'red' },
    ]
  }
  if (isSearcher.value) {
    return [
      { label: '最近入库', value: s.recentArchived ?? '—', color: 'green' },
      { label: '我提报的问题', value: s.myReworks ?? '—', color: 'amber' },
      { label: '待跟踪返工', value: s.pendingReworks ?? '—', color: 'red' },
      { label: '可检索卷宗', value: s.totalArchived ?? '—', color: 'blue' },
    ]
  }
  // operator or default
  return [
    { label: '我的待处理任务', value: s.myPendingTasks ?? '—', color: 'amber' },
    { label: '待边界审核', value: s.boundaryTasks ?? '—', color: 'blue' },
    { label: '待字段修正', value: s.metadataTasks ?? '—', color: 'purple' },
    { label: '被退回任务', value: s.rejectedTasks ?? '—', color: 'red' },
  ]
})

function formatTime(ts) {
  if (!ts) return '—'
  const d = new Date(ts)
  const now = new Date()
  const diffMs = now - d
  if (diffMs < 60000) return '刚刚'
  if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)} 分钟前`
  if (diffMs < 86400000) return `${Math.floor(diffMs / 3600000)} 小时前`
  return d.toLocaleDateString('zh-CN', { month: 'numeric', day: 'numeric' })
}

function goTask(task) {
  if (['boundary', 'boundary_review', 'ordering', 'order_review'].includes(task.type)) {
    router.push(`/review/structure/${task.id}`)
  } else if (['metadata', 'metadata_review'].includes(task.type)) {
    router.push(`/review/catalog/${task.id}`)
  } else if (task.type === 'final_release') {
    router.push(`/release/console/${task.id}`)
  } else {
    router.push('/tasks')
  }
}

function goItem(item) {
  if (isSearcher.value) {
    router.push(`/archives/${item.id}`)
  } else {
    router.push(`/batches/${item.batch_id || item.id}`)
  }
}

onMounted(async () => {
  // Load stats
  try {
    const { data } = await getArchiveDashboardStats()
    stats.value = data || {}
  } catch (err) {
    loadError.value = err?.response?.status === 401
      ? '数据服务认证失败，请尝试重新登录。'
      : '工作台数据加载失败，部分统计信息不可用。'
  } finally {
    statsLoading.value = false
  }

  // Load pending tasks
  try {
    const { data } = await getMyAssignedTasks({ status: 'human_review', page_size: 10 })
    const items = Array.isArray(data) ? data : (data?.items || data?.tasks || [])
    pendingTasks.value = items
  } catch { /* non-blocking */ } finally {
    tasksLoading.value = false
  }

  // Load recent items
  try {
    if (isSearcher.value) {
      const { data } = await listArchiveRecords({ page_size: 5, sort: 'newest' })
      recentItems.value = Array.isArray(data) ? data : (data?.items || data?.records || [])
    } else {
      const { data } = await listBatches({ page_size: 5, sort: 'newest' })
      recentItems.value = Array.isArray(data) ? data : (data?.items || data?.batches || [])
    }
  } catch { /* non-blocking */ } finally {
    recentLoading.value = false
  }
})
</script>
