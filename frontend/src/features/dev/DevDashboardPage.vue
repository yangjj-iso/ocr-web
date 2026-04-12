<template>
  <div class="min-h-screen bg-[var(--gov-bg)] px-4 py-5 sm:px-6">
    <div v-if="!authenticated" class="mx-auto flex min-h-[calc(100vh-120px)] max-w-md items-center">
      <form class="w-full rounded-lg border border-[var(--gov-border)] bg-white p-6 shadow-sm" @submit.prevent="submitLogin">
        <p class="text-xs font-semibold text-[var(--gov-primary)]">DEV DASHBOARD</p>
        <h1 class="mt-2 text-xl font-bold text-[var(--gov-text)]">开发后台登录</h1>
        <p class="mt-1 text-sm text-[var(--gov-text-muted)]">使用 .env 中声明的后台账号进入。</p>

        <div v-if="sessionChecked && !configured" class="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          DEV_DASHBOARD_USERNAME 和 DEV_DASHBOARD_PASSWORD 尚未配置。
        </div>

        <label class="mt-5 block text-sm font-medium text-[var(--gov-text)]">
          账号
          <input v-model="loginForm.username" class="gov-input mt-1 w-full" autocomplete="username" />
        </label>
        <label class="mt-4 block text-sm font-medium text-[var(--gov-text)]">
          密码
          <input v-model="loginForm.password" class="gov-input mt-1 w-full" type="password" autocomplete="current-password" />
        </label>
        <p v-if="loginError" class="mt-3 text-sm text-red-600">{{ loginError }}</p>
        <button class="gov-btn mt-5 w-full" :disabled="loginLoading || !configured">
          {{ loginLoading ? '登录中...' : '进入后台' }}
        </button>
      </form>
    </div>

    <div v-else class="mx-auto max-w-[1480px]">
      <div class="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p class="text-xs font-semibold text-[var(--gov-primary)]">DEV DASHBOARD</p>
          <h1 class="mt-1 text-2xl font-bold text-[var(--gov-text)]">工作流与队列监控</h1>
          <p class="mt-1 text-sm text-[var(--gov-text-muted)]">Java 控制面汇总任务状态、RabbitMQ 队列和 Python 计算侧指标。</p>
        </div>
        <div class="flex gap-2">
          <button class="gov-btn-secondary" :disabled="metricsLoading" @click="loadMetrics">
            {{ metricsLoading ? '刷新中...' : '刷新' }}
          </button>
          <button class="gov-btn-secondary" @click="handleLogout">退出</button>
        </div>
      </div>

      <div v-if="metricsError" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {{ metricsError }}
      </div>

      <div class="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div v-for="item in kpis" :key="item.label" class="rounded-lg border border-[var(--gov-border)] bg-white px-4 py-3 shadow-sm">
          <p class="text-xs text-[var(--gov-text-muted)]">{{ item.label }}</p>
          <p class="mt-2 text-2xl font-bold text-[var(--gov-text)]">{{ item.value }}</p>
          <p class="mt-1 text-xs text-[var(--gov-text-muted)]">{{ item.sub }}</p>
        </div>
      </div>

      <div class="grid gap-4 lg:grid-cols-[1fr_360px]">
        <section class="rounded-lg border border-[var(--gov-border)] bg-white shadow-sm">
          <div class="border-b border-[var(--gov-border)] px-4 py-3">
            <h2 class="text-sm font-semibold text-[var(--gov-text)]">工作队列</h2>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-[var(--gov-surface-muted)] text-left text-xs text-[var(--gov-text-muted)]">
                <tr>
                  <th class="px-4 py-2 font-medium">队列</th>
                  <th class="px-4 py-2 font-medium">任务数</th>
                  <th class="px-4 py-2 font-medium">消费者</th>
                  <th class="px-4 py-2 font-medium">状态</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[var(--gov-border)]">
                <tr v-for="queue in metrics?.queues || []" :key="queue.name">
                  <td class="px-4 py-3 font-mono text-xs">{{ queue.name }}</td>
                  <td class="px-4 py-3 text-lg font-semibold">{{ queue.message_count }}</td>
                  <td class="px-4 py-3">{{ queue.consumer_count }}</td>
                  <td class="px-4 py-3">
                    <span :class="queue.available ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'" class="rounded-md px-2 py-1 text-xs">
                      {{ queue.available ? '可用' : queue.detail || '不可用' }}
                    </span>
                  </td>
                </tr>
                <tr v-if="!(metrics?.queues || []).length">
                  <td class="px-4 py-6 text-center text-[var(--gov-text-muted)]" colspan="4">暂无队列数据</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="rounded-lg border border-[var(--gov-border)] bg-white p-4 shadow-sm">
          <h2 class="text-sm font-semibold text-[var(--gov-text)]">Python 计算侧</h2>
          <div class="mt-3 space-y-3 text-sm">
            <div class="flex items-center justify-between">
              <span class="text-[var(--gov-text-muted)]">指标源</span>
              <span :class="pythonMetrics.available ? 'text-emerald-700' : 'text-red-600'" class="font-medium">
                {{ pythonMetrics.available ? '已连接' : '不可用' }}
              </span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-[var(--gov-text-muted)]">Celery Worker</span>
              <span class="font-medium">{{ pythonCelery.worker_count || 0 }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-[var(--gov-text-muted)]">Active / Reserved</span>
              <span class="font-medium">{{ pythonCelery.active_count || 0 }} / {{ pythonCelery.reserved_count || 0 }}</span>
            </div>
            <p class="rounded-lg bg-[var(--gov-surface-muted)] px-3 py-2 text-xs text-[var(--gov-text-muted)]">
              {{ pythonMetrics.detail || '等待刷新' }}
            </p>
          </div>
        </section>
      </div>

      <div class="mt-4 grid gap-4 lg:grid-cols-2">
        <TaskListPanel title="正在排队的任务" :tasks="metrics?.queued_tasks || []" empty-text="当前没有排队任务" />
        <TaskListPanel title="正在处理的任务" :tasks="metrics?.processing_tasks || []" empty-text="当前没有处理中的任务" />
      </div>

      <div class="mt-4 grid gap-4 lg:grid-cols-2">
        <section class="rounded-lg border border-[var(--gov-border)] bg-white shadow-sm">
          <div class="border-b border-[var(--gov-border)] px-4 py-3">
            <h2 class="text-sm font-semibold text-[var(--gov-text)]">任务状态分布</h2>
          </div>
          <div class="grid grid-cols-2 gap-2 p-4 sm:grid-cols-3">
            <div v-for="item in metrics?.tasks?.by_status || []" :key="item.status" class="rounded-lg border border-[var(--gov-border)] px-3 py-2">
              <p class="text-xs text-[var(--gov-text-muted)]">{{ statusLabel(item.status) }}</p>
              <p class="mt-1 text-lg font-semibold">{{ item.count }}</p>
            </div>
          </div>
        </section>

        <section class="rounded-lg border border-[var(--gov-border)] bg-white shadow-sm">
          <div class="border-b border-[var(--gov-border)] px-4 py-3">
            <h2 class="text-sm font-semibold text-[var(--gov-text)]">按模式统计平均耗时</h2>
          </div>
          <div class="divide-y divide-[var(--gov-border)]">
            <div v-for="item in metrics?.workflow?.by_mode || []" :key="item.mode" class="flex items-center justify-between px-4 py-3 text-sm">
              <span class="font-mono text-xs">{{ item.mode }}</span>
              <span class="font-medium">{{ formatDuration(item.average_completed_duration_ms) }}</span>
              <span class="text-xs text-[var(--gov-text-muted)]">{{ item.sample_count }} 样本</span>
            </div>
            <div v-if="!(metrics?.workflow?.by_mode || []).length" class="px-4 py-6 text-center text-sm text-[var(--gov-text-muted)]">暂无完成样本</div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import {
  getDevDashboardMetrics,
  getDevDashboardSession,
  loginDevDashboard,
  logoutDevDashboard,
} from '@/api/devDashboard.js'

const configured = ref(false)
const authenticated = ref(false)
const sessionChecked = ref(false)
const loginLoading = ref(false)
const loginError = ref('')
const metricsLoading = ref(false)
const metricsError = ref('')
const metrics = ref(null)

const loginForm = reactive({ username: '', password: '' })

const queueBacklog = computed(() => (metrics.value?.queues || []).reduce((sum, queue) => sum + Number(queue.message_count || 0), 0))
const pythonMetrics = computed(() => metrics.value?.python_metrics || { available: false, detail: '' })
const pythonCelery = computed(() => pythonMetrics.value?.payload?.celery || {})

const kpis = computed(() => [
  {
    label: '平均工作流时长',
    value: formatDuration(metrics.value?.workflow?.average_completed_duration_ms || metrics.value?.workflow?.average_event_duration_ms || 0),
    sub: `${metrics.value?.workflow?.completed_sample_count || metrics.value?.workflow?.event_sample_count || 0} 个样本`,
  },
  { label: '队列积压', value: queueBacklog.value, sub: 'RabbitMQ message count' },
  { label: '排队任务', value: metrics.value?.tasks?.pending || 0, sub: 'pending / queued' },
  { label: '处理中', value: metrics.value?.tasks?.processing || 0, sub: 'running / worker accepted' },
  { label: '失败任务', value: metrics.value?.tasks?.failed || 0, sub: `${metrics.value?.tasks?.done || 0} 已完成` },
])

async function refreshSession() {
  try {
    const { data } = await getDevDashboardSession()
    configured.value = !!data.configured
    authenticated.value = !!data.authenticated
    if (authenticated.value) await loadMetrics()
  } finally {
    sessionChecked.value = true
  }
}

async function submitLogin() {
  loginLoading.value = true
  loginError.value = ''
  try {
    await loginDevDashboard(loginForm.username, loginForm.password)
    authenticated.value = true
    loginForm.password = ''
    await loadMetrics()
  } catch (error) {
    loginError.value = error?.response?.data?.detail || '登录失败'
  } finally {
    loginLoading.value = false
  }
}

async function handleLogout() {
  await logoutDevDashboard().catch(() => null)
  authenticated.value = false
  metrics.value = null
}

async function loadMetrics() {
  metricsLoading.value = true
  metricsError.value = ''
  try {
    const { data } = await getDevDashboardMetrics()
    metrics.value = data
  } catch (error) {
    metricsError.value = error?.response?.data?.detail || '指标加载失败'
    if (error?.response?.status === 401) authenticated.value = false
  } finally {
    metricsLoading.value = false
  }
}

function formatDuration(ms) {
  const value = Number(ms || 0)
  if (value <= 0) return '0 ms'
  if (value < 1000) return `${Math.round(value)} ms`
  if (value < 60000) return `${(value / 1000).toFixed(1)} s`
  if (value < 3600000) return `${(value / 60000).toFixed(1)} min`
  return `${(value / 3600000).toFixed(1)} h`
}

function formatAge(seconds) {
  const value = Number(seconds || 0)
  if (value < 60) return `${value}s`
  if (value < 3600) return `${Math.floor(value / 60)}m ${value % 60}s`
  return `${Math.floor(value / 3600)}h ${Math.floor((value % 3600) / 60)}m`
}

function formatTime(value) {
  if (!value) return '-'
  const date = new Date(value)
  return `${date.toLocaleDateString('zh-CN')} ${date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}`
}

function statusLabel(status) {
  return {
    pending: '排队中',
    processing: '处理中',
    done: '已完成',
    failed: '失败',
    human_review: '人工复核',
  }[status] || status
}

const TaskListPanel = defineComponent({
  props: {
    title: { type: String, required: true },
    tasks: { type: Array, default: () => [] },
    emptyText: { type: String, required: true },
  },
  setup(props) {
    return () => h('section', { class: 'rounded-lg border border-[var(--gov-border)] bg-white shadow-sm' }, [
      h('div', { class: 'border-b border-[var(--gov-border)] px-4 py-3' }, [
        h('h2', { class: 'text-sm font-semibold text-[var(--gov-text)]' }, props.title),
      ]),
      props.tasks.length
        ? h('div', { class: 'max-h-[380px] divide-y divide-[var(--gov-border)] overflow-y-auto' }, props.tasks.map((task) =>
          h('div', { class: 'px-4 py-3', key: task.id }, [
            h('div', { class: 'flex items-start justify-between gap-3' }, [
              h('div', { class: 'min-w-0' }, [
                h('p', { class: 'truncate text-sm font-medium text-[var(--gov-text)]', title: task.filename }, task.filename || `Task #${task.id}`),
                h('p', { class: 'mt-1 font-mono text-xs text-[var(--gov-text-muted)]' }, `#${task.id} · ${task.mode || '-'} · ${task.batch_id || '-'}`),
              ]),
              h('span', { class: 'rounded-md bg-[var(--gov-surface-muted)] px-2 py-1 text-xs text-[var(--gov-text-muted)]' }, formatAge(task.age_seconds)),
            ]),
            h('div', { class: 'mt-2 flex flex-wrap gap-3 text-xs text-[var(--gov-text-muted)]' }, [
              h('span', null, `状态 ${statusLabel(task.status)}`),
              h('span', null, `进度 ${Math.round(Number(task.progress_percent || 0))}%`),
              h('span', null, formatTime(task.created_at)),
            ]),
          ])
        ))
        : h('div', { class: 'px-4 py-8 text-center text-sm text-[var(--gov-text-muted)]' }, props.emptyText),
    ])
  },
})

onMounted(refreshSession)
</script>
