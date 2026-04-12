<template>
  <div class="min-h-[calc(100vh-56px)] bg-gradient-to-br from-slate-50 via-white to-indigo-50/30">
    <div class="mx-auto max-w-[1440px] px-6 py-5">
      <div class="mb-5 flex items-end justify-between">
        <div>
          <h1 class="text-xl font-bold text-[var(--gov-text)]">系统运行总览</h1>
          <p class="mt-0.5 text-xs text-[var(--gov-text-muted)]">实时监控平台运行数据 · {{ todayStr }}</p>
        </div>
        <div class="flex gap-2">
          <router-link to="/admin" class="gov-btn-secondary px-3 py-1.5 text-xs">用户管理</router-link>
          <router-link to="/" class="gov-btn px-3 py-1.5 text-xs">签录工作台</router-link>
        </div>
      </div>

      <div class="mb-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div v-for="card in kpiCards" :key="card.label" class="relative overflow-hidden rounded-xl border border-[var(--gov-border)] bg-white px-5 py-4 shadow-sm">
          <div class="absolute -right-3 -top-3 h-16 w-16 rounded-full opacity-10" :class="card.bgClass" />
          <p class="text-[11px] font-medium text-[var(--gov-text-muted)]">{{ card.label }}</p>
          <p class="mt-1.5 text-3xl font-extrabold tracking-tight" :class="card.valueClass">{{ card.value }}</p>
          <div class="mt-2 flex items-center gap-1.5">
            <span class="inline-flex items-center rounded-full px-1.5 py-0.5 text-[10px] font-semibold" :class="card.trendClass">
              <svg v-if="card.trendUp" class="mr-0.5 h-2.5 w-2.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path d="M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25" />
              </svg>
              <svg v-else class="mr-0.5 h-2.5 w-2.5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                <path d="M4.5 4.5l15 15m0 0V8.25m0 11.25H8.25" />
              </svg>
              {{ card.trend }}
            </span>
            <span class="text-[10px] text-[var(--gov-text-muted)]">{{ card.sub }}</span>
          </div>
        </div>
      </div>

      <div class="mb-5 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div class="col-span-2 rounded-xl border border-[var(--gov-border)] bg-white px-5 py-4 shadow-sm">
          <div class="mb-3 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-[var(--gov-text)]">OCR 任务趋势</h3>
            <div class="flex gap-1">
              <button
                v-for="period in ['7天', '30天']"
                :key="period"
                class="rounded-md px-2 py-0.5 text-[10px] font-medium transition"
                :class="trendPeriod === period ? 'bg-[var(--gov-primary)] text-white' : 'bg-slate-100 text-slate-500 hover:bg-slate-200'"
                @click="trendPeriod = period"
              >
                {{ period }}
              </button>
            </div>
          </div>
          <div class="h-[220px]">
            <Line v-if="trendChartReady" :data="trendChartData" :options="trendChartOptions" />
          </div>
        </div>

        <div class="rounded-xl border border-[var(--gov-border)] bg-white px-5 py-4 shadow-sm">
          <h3 class="mb-3 text-sm font-semibold text-[var(--gov-text)]">用户角色分布</h3>
          <div class="flex h-[180px] items-center justify-center">
            <Doughnut v-if="roleChartReady" :data="roleChartData" :options="roleChartOptions" />
          </div>
          <div class="mt-3 flex justify-center gap-4 text-[10px]">
            <span class="flex items-center gap-1"><span class="h-2 w-2 rounded-full bg-indigo-500" />管理员 {{ stats.admins }}</span>
            <span class="flex items-center gap-1"><span class="h-2 w-2 rounded-full bg-blue-500" />签录员 {{ stats.operators }}</span>
            <span class="flex items-center gap-1"><span class="h-2 w-2 rounded-full bg-slate-400" />检索员 {{ stats.searchers }}</span>
          </div>
        </div>
      </div>

      <div class="mb-5 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div class="rounded-xl border border-[var(--gov-border)] bg-white px-5 py-4 shadow-sm">
          <h3 class="mb-3 text-sm font-semibold text-[var(--gov-text)]">任务状态分布</h3>
          <div class="h-[180px]">
            <Bar v-if="statusChartReady" :data="statusChartData" :options="statusChartOptions" />
          </div>
        </div>

        <div class="rounded-xl border border-[var(--gov-border)] bg-white px-5 py-4 shadow-sm">
          <h3 class="mb-3 text-sm font-semibold text-[var(--gov-text)]">最近动态</h3>
          <div v-if="recentLogs.length === 0" class="flex flex-col items-center justify-center py-8 text-[var(--gov-text-muted)]">
            <svg class="mb-2 h-8 w-8 opacity-30" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
              <path d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span class="text-xs">暂无操作记录</span>
          </div>
          <div v-else class="max-h-[200px] space-y-2.5 overflow-y-auto pr-1">
            <div v-for="log in recentLogs" :key="log.id" class="flex items-start gap-2.5">
              <div class="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white" :class="logBgClass(log.action_type)">
                {{ (log.username || '?')[0] }}
              </div>
              <div class="min-w-0 flex-1">
                <p class="text-xs text-[var(--gov-text)]">
                  <strong>{{ log.username }}</strong>
                  <span class="text-[var(--gov-text-muted)]"> {{ actionLabel(log.action_type) }}</span>
                </p>
                <p class="text-[10px] text-[var(--gov-text-muted)]">{{ fmtDate(log.created_at) }}</p>
              </div>
            </div>
          </div>
        </div>

        <div class="space-y-4">
          <div class="rounded-xl border border-[var(--gov-border)] bg-white px-5 py-4 shadow-sm">
            <div class="mb-3 flex items-center justify-between">
              <h3 class="text-sm font-semibold text-[var(--gov-text)]">系统状态</h3>
              <button class="text-[10px] font-medium text-[var(--gov-primary)] hover:underline" @click="refreshSystemHealth">
                刷新
              </button>
            </div>
            <div class="space-y-3">
              <div v-for="item in serviceHealthCards" :key="item.key" class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2">
                <div class="flex items-center justify-between">
                  <span class="text-xs text-[var(--gov-text-muted)]">{{ item.label }}</span>
                  <span class="flex items-center gap-1 text-[10px] font-medium" :class="item.up ? 'text-emerald-600' : 'text-red-500'">
                    <span class="h-1.5 w-1.5 rounded-full" :class="item.up ? 'bg-emerald-500 animate-pulse' : 'bg-red-400'" />
                    {{ item.up ? '运行中' : '异常' }}
                  </span>
                </div>
                <p class="mt-1 text-[10px] text-[var(--gov-text-muted)]">{{ item.detail }}</p>
              </div>
            </div>
          </div>

          <div class="rounded-xl border border-[var(--gov-border)] bg-gradient-to-br from-[var(--gov-primary)] to-indigo-600 px-5 py-4 shadow-sm">
            <h3 class="mb-2 text-sm font-semibold text-white/90">待处理事项</h3>
            <div class="space-y-1.5">
              <router-link v-if="stats.pendingUsers > 0" to="/admin" class="flex items-center justify-between rounded-lg bg-white/15 px-3 py-2 text-xs text-white transition hover:bg-white/25">
                <span>{{ stats.pendingUsers }} 个账号待审核</span>
                <span class="text-white/60">→</span>
              </router-link>
              <router-link v-if="stats.activeAssignments > 0" to="/admin" class="flex items-center justify-between rounded-lg bg-white/15 px-3 py-2 text-xs text-white transition hover:bg-white/25">
                <span>{{ stats.activeAssignments }} 个分配仍在处理中</span>
                <span class="text-white/60">→</span>
              </router-link>
              <div v-if="stats.pendingUsers === 0 && stats.activeAssignments === 0" class="rounded-lg bg-white/10 px-3 py-2 text-center text-xs text-white/70">
                当前没有待处理事项
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import axios from 'axios'
import { computed, onMounted, ref, watch } from 'vue'
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js'
import { Bar, Doughnut, Line } from 'vue-chartjs'

import { getPendingUsers } from '@/api/auth.js'
import { listAssignments, listOperationLogs, listUsers } from '@/api/admin.js'
import { getDashboardStats } from '@/api/ocr.js'
import { controlPlaneApiUrl } from '@/api/runtime.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, BarElement, ArcElement, Filler, Tooltip, Legend)

const todayStr = new Date().toLocaleDateString('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
  weekday: 'long',
})

const stats = ref({
  totalUsers: 0,
  admins: 0,
  operators: 0,
  searchers: 0,
  pendingUsers: 0,
  totalTasks: 0,
  doneTasks: 0,
  processingTasks: 0,
  pendingTasks: 0,
  failedTasks: 0,
  totalAssignments: 0,
  activeAssignments: 0,
  completedAssignments: 0,
})

const recentLogs = ref([])
const trendPeriod = ref('7天')
const cachedDailyCounts = ref([])

const healthState = ref({
  controlPlane: { key: 'controlPlane', label: 'Java 控制面', up: false, detail: '未探测' },
  database: { key: 'database', label: '数据库', up: false, detail: '未探测' },
  rabbitmq: { key: 'rabbitmq', label: 'RabbitMQ', up: false, detail: '未探测' },
  aiService: { key: 'aiService', label: 'Python AI API', up: false, detail: '未探测' },
})

const trendChartReady = ref(false)
const roleChartReady = ref(false)
const statusChartReady = ref(false)

const serviceHealthCards = computed(() => Object.values(healthState.value))
const healthyServiceCount = computed(() => serviceHealthCards.value.filter((item) => item.up).length)
const systemHealthPercent = computed(() => {
  if (!serviceHealthCards.value.length) return 0
  return Math.round((healthyServiceCount.value / serviceHealthCards.value.length) * 100)
})

const kpiCards = computed(() => [
  {
    label: '用户总数',
    value: stats.value.totalUsers,
    bgClass: 'bg-blue-500',
    valueClass: 'text-blue-600',
    trendUp: stats.value.pendingUsers === 0,
    trend: `${stats.value.pendingUsers} 待审核`,
    trendClass: stats.value.pendingUsers === 0 ? 'bg-emerald-50 text-emerald-600' : 'bg-blue-50 text-blue-600',
    sub: '注册审批',
  },
  {
    label: 'OCR 任务',
    value: stats.value.totalTasks,
    bgClass: 'bg-indigo-500',
    valueClass: 'text-indigo-600',
    trendUp: stats.value.doneTasks >= stats.value.failedTasks,
    trend: `${stats.value.doneTasks} 已完成`,
    trendClass: 'bg-emerald-50 text-emerald-600',
    sub: '任务处理',
  },
  {
    label: '批次分配',
    value: stats.value.totalAssignments,
    bgClass: 'bg-emerald-500',
    valueClass: 'text-emerald-600',
    trendUp: stats.value.completedAssignments >= stats.value.activeAssignments,
    trend: `${stats.value.completedAssignments} 已交付`,
    trendClass: stats.value.completedAssignments >= stats.value.activeAssignments ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600',
    sub: `${stats.value.activeAssignments} 进行中`,
  },
  {
    label: '系统健康',
    value: `${systemHealthPercent.value}%`,
    bgClass: systemHealthPercent.value === 100 ? 'bg-emerald-500' : 'bg-amber-500',
    valueClass: systemHealthPercent.value === 100 ? 'text-emerald-600' : 'text-amber-600',
    trendUp: systemHealthPercent.value === 100,
    trend: `${healthyServiceCount.value}/${serviceHealthCards.value.length} 正常`,
    trendClass: systemHealthPercent.value === 100 ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600',
    sub: '依赖状态',
  },
])

const trendChartData = ref({ labels: [], datasets: [] })
const trendChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: true, position: 'top', labels: { boxWidth: 8, font: { size: 10 } } },
    tooltip: { mode: 'index', intersect: false },
  },
  scales: {
    x: { grid: { display: false }, ticks: { font: { size: 9 } } },
    y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: { size: 9 }, stepSize: 1 } },
  },
  elements: { line: { tension: 0.4 }, point: { radius: 3, hoverRadius: 5 } },
  interaction: { mode: 'nearest', axis: 'x', intersect: false },
}

const roleChartData = ref({ labels: [], datasets: [] })
const roleChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  cutout: '65%',
  plugins: { legend: { display: false }, tooltip: { bodyFont: { size: 11 } } },
}

const statusChartData = ref({ labels: [], datasets: [] })
const statusChartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: { legend: { display: false }, tooltip: { bodyFont: { size: 11 } } },
  scales: {
    x: { grid: { display: false }, ticks: { font: { size: 10 } } },
    y: { beginAtZero: true, grid: { color: '#f1f5f9' }, ticks: { font: { size: 9 }, stepSize: 1 } },
  },
}

function buildTrendChart(dailyCounts) {
  return {
    labels: dailyCounts.map((item) => item.date),
    datasets: [
      {
        label: '新建任务',
        data: dailyCounts.map((item) => item.created),
        borderColor: '#6366f1',
        backgroundColor: 'rgba(99,102,241,0.08)',
        fill: true,
        borderWidth: 2,
      },
      {
        label: '完成任务',
        data: dailyCounts.map((item) => item.completed),
        borderColor: '#10b981',
        backgroundColor: 'rgba(16,185,129,0.08)',
        fill: true,
        borderWidth: 2,
      },
    ],
  }
}

const ACTION_LABELS = {
  import_files: '导入文件',
  assign_batch: '分配批次',
  set_role: '修改角色',
  update_quota: '修改配额',
  reset_quota: '重置配额',
  approve_user: '审核通过',
  reject_user: '驳回用户',
  delete_user: '删除用户',
}

function actionLabel(actionType) {
  return ACTION_LABELS[actionType] || actionType
}

function logBgClass(actionType) {
  return {
    import_files: 'bg-blue-500',
    assign_batch: 'bg-indigo-500',
    set_role: 'bg-violet-500',
    approve_user: 'bg-emerald-500',
    reject_user: 'bg-red-500',
  }[actionType] || 'bg-slate-400'
}

function fmtDate(isoValue) {
  if (!isoValue) return '未知时间'
  const date = new Date(isoValue)
  return `${date.toLocaleDateString('zh-CN')} ${date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
}

function componentIsUp(component) {
  return String(component?.status || '').toUpperCase() === 'UP'
}

function formatComponentDetail(component) {
  if (!component) return '未探测'
  const detail = component.detail || component.status || '未知'
  const latency = component.latency_ms
  return latency == null ? detail : `${detail} · ${latency} ms`
}

function applyHealthPayload(payload) {
  const components = payload?.components || {}
  const controlPlaneUp = String(payload?.status || '').toUpperCase() === 'UP'
  healthState.value = {
    controlPlane: {
      key: 'controlPlane',
      label: 'Java 控制面',
      up: controlPlaneUp,
      detail: payload ? `控制面 ${String(payload.status || 'UNKNOWN').toUpperCase()}` : '未探测',
    },
    database: {
      key: 'database',
      label: '数据库',
      up: componentIsUp(components.database),
      detail: formatComponentDetail(components.database),
    },
    rabbitmq: {
      key: 'rabbitmq',
      label: 'RabbitMQ',
      up: componentIsUp(components.rabbitmq),
      detail: formatComponentDetail(components.rabbitmq),
    },
    aiService: {
      key: 'aiService',
      label: 'Python AI API',
      up: componentIsUp(components.ai_service),
      detail: formatComponentDetail(components.ai_service),
    },
  }
}

async function refreshSystemHealth() {
  try {
    const { data } = await axios.get(controlPlaneApiUrl('/api/health'), { withCredentials: true })
    applyHealthPayload(data)
  } catch (error) {
    if (error?.response?.data) {
      applyHealthPayload(error.response.data)
      return
    }
    applyHealthPayload(null)
  }
}

onMounted(async () => {
  const [usersRes, pendingRes, assignRes, logsRes, taskStatsRes] = await Promise.all([
    listUsers().catch(() => ({ data: { items: [] } })),
    getPendingUsers().catch(() => ({ data: { items: [] } })),
    listAssignments().catch(() => ({ data: { items: [] } })),
    listOperationLogs({ limit: 8 }).catch(() => ({ data: { items: [] } })),
    getDashboardStats(7).catch(() => ({ data: null })),
    refreshSystemHealth(),
  ])

  const users = usersRes.data?.items || []
  stats.value.totalUsers = users.length + 1
  stats.value.admins = users.filter((user) => user.role === 'admin').length + 1
  stats.value.operators = users.filter((user) => user.role === 'operator').length
  stats.value.searchers = users.filter((user) => user.role === 'searcher').length
  stats.value.pendingUsers = (pendingRes.data?.items || []).length

  const assignments = assignRes.data?.items || []
  stats.value.totalAssignments = assignments.length
  stats.value.activeAssignments = assignments.filter((assignment) => ['pending', 'processing'].includes(assignment.status)).length
  stats.value.completedAssignments = assignments.filter((assignment) => assignment.status === 'done').length

  recentLogs.value = (logsRes.data?.items || []).slice(0, 8)

  const taskStats = taskStatsRes.data
  if (taskStats) {
    stats.value.totalTasks = taskStats.total_tasks || 0
    stats.value.doneTasks = taskStats.done_tasks || 0
    stats.value.processingTasks = taskStats.processing_tasks || 0
    stats.value.pendingTasks = taskStats.pending_tasks || 0
    stats.value.failedTasks = taskStats.failed_tasks || 0
    cachedDailyCounts.value = taskStats.daily_counts || []
  }

  roleChartData.value = {
    labels: ['管理员', '签录员', '检索员'],
    datasets: [{
      data: [stats.value.admins || 0, stats.value.operators || 0, stats.value.searchers || 0],
      backgroundColor: ['#6366f1', '#3b82f6', '#94a3b8'],
      borderWidth: 0,
      hoverOffset: 6,
    }],
  }
  roleChartReady.value = true

  statusChartData.value = {
    labels: ['已完成', '处理中', '等待中', '失败'],
    datasets: [{
      data: [stats.value.doneTasks, stats.value.processingTasks, stats.value.pendingTasks, stats.value.failedTasks],
      backgroundColor: ['#10b981', '#3b82f6', '#f59e0b', '#ef4444'],
      borderRadius: 6,
      borderWidth: 0,
    }],
  }
  statusChartReady.value = true

  trendChartData.value = buildTrendChart(cachedDailyCounts.value)
  trendChartReady.value = true
})

watch(trendPeriod, async (period) => {
  const days = period === '30天' ? 30 : 7
  try {
    const { data } = await getDashboardStats(days)
    if (data?.daily_counts) {
      cachedDailyCounts.value = data.daily_counts
      trendChartData.value = buildTrendChart(data.daily_counts)
    }
  } catch {
    // Keep the previous chart if refresh fails.
  }
})
</script>
