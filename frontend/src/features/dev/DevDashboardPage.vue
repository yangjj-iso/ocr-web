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

    <div v-else class="mx-auto max-w-[1540px]">
      <section class="mb-4 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
        <div class="bg-[linear-gradient(135deg,#f8fafc_0%,#eef6f2_48%,#fff7ed_100%)] px-5 py-5 sm:px-6">
          <div class="flex flex-wrap items-start justify-between gap-4">
            <div class="max-w-3xl">
              <p class="text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700">Dev Console</p>
              <h1 class="mt-2 text-3xl font-bold text-slate-900">运行环境与任务控制台</h1>
              <p class="mt-2 text-sm leading-6 text-slate-600">在同一个面板里查看队列、任务、工作流时长，并实时调整当前运行环境。</p>
            </div>
            <div class="flex flex-wrap items-center gap-2">
              <div class="rounded-lg border border-slate-200 bg-white/90 px-3 py-2 text-xs text-slate-500">
                <div>指标刷新 {{ formatTime(metrics?.generated_at) }}</div>
                <div class="mt-1">环境文件 {{ environment?.env_file_path || '.env' }}</div>
              </div>
              <button class="gov-btn-secondary" :disabled="dashboardRefreshing" @click="refreshDashboard">
                {{ dashboardRefreshing ? '刷新中...' : '全部刷新' }}
              </button>
              <button class="gov-btn-secondary" @click="handleLogout">退出</button>
            </div>
          </div>
        </div>
      </section>

      <div v-if="dashboardError" class="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {{ dashboardError }}
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

      <div class="mt-4 grid gap-4 xl:grid-cols-[minmax(320px,0.82fr)_minmax(0,1.18fr)]">
        <section class="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <div class="border-b border-slate-200 px-4 py-3">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 class="text-sm font-semibold text-slate-900">最近更新任务</h2>
                <p class="mt-1 text-xs text-slate-500">可直接查看任务详情与工作流事件。</p>
              </div>
              <div class="flex gap-2">
                <input
                  v-model="taskLookupId"
                  type="number"
                  min="1"
                  class="gov-input w-32"
                  placeholder="任务 ID"
                  @keydown.enter.prevent="openTaskFromLookup"
                />
                <button class="gov-btn-secondary" :disabled="taskLoading || !taskLookupId" @click="openTaskFromLookup">
                  查看
                </button>
              </div>
            </div>
          </div>

          <div v-if="metrics?.recent_tasks?.length" class="max-h-[620px] divide-y divide-slate-200 overflow-y-auto">
            <button
              v-for="task in metrics.recent_tasks"
              :key="task.id"
              type="button"
              class="block w-full px-4 py-3 text-left transition hover:bg-slate-50"
              :class="selectedTask?.task?.id === task.id ? 'bg-emerald-50/60' : ''"
              @click="openTask(task.id, task)"
            >
              <div class="flex items-start justify-between gap-3">
                <div class="min-w-0">
                  <p class="truncate text-sm font-semibold text-slate-900">{{ task.filename || `Task #${task.id}` }}</p>
                  <p class="mt-1 font-mono text-[11px] text-slate-500">#{{ task.id }} · {{ task.mode || '-' }} · {{ task.batch_id || '-' }}</p>
                </div>
                <span :class="statusBadgeClass(task.status)" class="rounded-md px-2 py-1 text-[11px] font-semibold">
                  {{ statusLabel(task.status) }}
                </span>
              </div>
              <div class="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                <span>{{ formatTime(task.updated_at || task.created_at) }}</span>
                <span>{{ formatAge(task.age_seconds) }}</span>
                <span v-if="task.error_message" class="text-rose-600">存在错误信息</span>
              </div>
            </button>
          </div>
          <div v-else class="px-4 py-10 text-center text-sm text-slate-500">暂无最近更新任务</div>
        </section>

        <section class="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <div class="border-b border-slate-200 px-4 py-3">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 class="text-sm font-semibold text-slate-900">任务详情</h2>
                <p class="mt-1 text-xs text-slate-500">任务元数据、结果预览与工作流事件时间线。</p>
              </div>
              <span v-if="selectedTask?.task" :class="statusBadgeClass(selectedTask.task.status)" class="rounded-md px-2 py-1 text-xs font-semibold">
                {{ statusLabel(selectedTask.task.status) }}
              </span>
            </div>
          </div>

          <div v-if="taskError" class="m-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {{ taskError }}
          </div>

          <div v-if="taskLoading" class="px-4 py-16 text-center text-sm text-slate-500">任务详情加载中...</div>

          <div v-else-if="selectedTask?.task" class="max-h-[720px] overflow-y-auto px-4 py-4">
            <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <div v-for="item in taskMetaItems" :key="item.label" class="rounded-lg border border-slate-200 bg-slate-50 px-3 py-3">
                <p class="text-xs uppercase tracking-[0.14em] text-slate-500">{{ item.label }}</p>
                <p class="mt-2 break-all text-sm font-medium text-slate-900">{{ item.value }}</p>
              </div>
            </div>

            <div v-if="selectedTask.task.error_message" class="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {{ selectedTask.task.error_message }}
            </div>

            <section class="mt-4 rounded-lg border border-slate-200">
              <div class="border-b border-slate-200 px-4 py-3">
                <h3 class="text-sm font-semibold text-slate-900">全文预览</h3>
              </div>
              <div class="max-h-[220px] overflow-y-auto px-4 py-3 text-sm leading-6 text-slate-700">
                <pre class="whitespace-pre-wrap break-words font-sans">{{ selectedTask.task.full_text || '暂无全文结果' }}</pre>
              </div>
            </section>

            <section class="mt-4 rounded-lg border border-slate-200">
              <div class="border-b border-slate-200 px-4 py-3">
                <h3 class="text-sm font-semibold text-slate-900">工作流事件</h3>
              </div>
              <div v-if="selectedTask.workflow_events?.events?.length" class="divide-y divide-slate-200">
                <div v-for="event in selectedTask.workflow_events.events" :key="`${event.event_id}-${event.created_at}`" class="px-4 py-3">
                  <div class="flex flex-wrap items-center justify-between gap-2">
                    <p class="text-sm font-semibold text-slate-900">{{ event.event_type }}</p>
                    <span class="font-mono text-[11px] text-slate-500">{{ formatTime(event.created_at || event.occurred_at) }}</span>
                  </div>
                  <p class="mt-1 break-all font-mono text-[11px] text-slate-500">{{ event.event_id }}</p>
                  <pre class="mt-3 overflow-x-auto rounded-lg bg-slate-950/95 p-3 text-[11px] leading-5 text-slate-100">{{ stringifyJson(event.payload) }}</pre>
                </div>
              </div>
              <div v-else class="px-4 py-8 text-center text-sm text-slate-500">暂无工作流事件</div>
            </section>

            <details class="mt-4 rounded-lg border border-slate-200" open>
              <summary class="cursor-pointer list-none border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-900">结果 JSON</summary>
              <pre class="max-h-[260px] overflow-auto px-4 py-3 text-[11px] leading-5 text-slate-700">{{ stringifyJson(selectedTask.task.result_json) }}</pre>
            </details>
          </div>

          <div v-else class="px-4 py-16 text-center text-sm text-slate-500">从左侧选择任务，或输入任务 ID 查看详情。</div>
        </section>
      </div>

      <section class="mt-4 rounded-lg border border-slate-200 bg-white shadow-sm">
        <div class="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div>
            <h2 class="text-sm font-semibold text-slate-900">运行环境</h2>
            <p class="mt-1 text-xs text-slate-500">修改后写回 .env，并对新请求立即生效。</p>
          </div>
          <div class="flex gap-2">
            <button class="gov-btn-secondary" :disabled="environmentLoading" @click="loadEnvironment">
              {{ environmentLoading ? '读取中...' : '重读环境' }}
            </button>
            <button class="gov-btn" :disabled="environmentSaving || !environmentDirty" @click="saveEnvironment">
              {{ environmentSaving ? '保存中...' : '保存并应用' }}
            </button>
          </div>
        </div>

        <div v-if="environmentError" class="mx-4 mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {{ environmentError }}
        </div>
        <div v-if="environmentSuccess" class="mx-4 mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {{ environmentSuccess }}
        </div>

        <div class="grid gap-4 p-4 xl:grid-cols-2">
          <section v-for="group in environment?.groups || []" :key="group.key" class="rounded-lg border border-slate-200 bg-slate-50">
            <div class="border-b border-slate-200 px-4 py-3">
              <h3 class="text-sm font-semibold text-slate-900">{{ group.label }}</h3>
              <p class="mt-1 text-xs text-slate-500">{{ group.description }}</p>
            </div>
            <div class="grid gap-3 p-4">
              <article v-for="field in group.fields" :key="field.key" class="rounded-lg border border-slate-200 bg-white px-3 py-3">
                <div class="flex items-start justify-between gap-3">
                  <div>
                    <p class="text-sm font-semibold text-slate-900">{{ field.label }}</p>
                    <p class="mt-1 text-xs leading-5 text-slate-500">{{ field.description }}</p>
                  </div>
                  <span v-if="field.runtime_applied" class="rounded-md bg-emerald-50 px-2 py-1 text-[11px] font-semibold text-emerald-700">即时生效</span>
                </div>

                <div class="mt-3">
                  <label v-if="field.type === 'boolean'" class="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2">
                    <span class="text-sm text-slate-700">{{ environmentDraft[field.key] ? '已开启' : '已关闭' }}</span>
                    <input v-model="environmentDraft[field.key]" type="checkbox" class="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" />
                  </label>
                  <input
                    v-else
                    v-model="environmentDraft[field.key]"
                    :type="fieldInputType(field)"
                    class="gov-input w-full bg-white"
                    :placeholder="field.placeholder || field.description"
                  />
                </div>

                <p class="mt-2 text-[11px] text-slate-500">
                  {{ field.sensitive ? (field.configured ? '当前已有值，留空不会覆盖。' : '当前未配置。') : `当前值：${displayEnvironmentFieldValue(field)}` }}
                </p>
              </article>
            </div>
          </section>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref } from 'vue'
import {
  getDevDashboardEnvironment,
  getDevDashboardMetrics,
  getDevDashboardSession,
  getDevDashboardTask,
  loginDevDashboard,
  logoutDevDashboard,
  updateDevDashboardEnvironment,
} from '@/api/devDashboard.js'

const configured = ref(false)
const authenticated = ref(false)
const sessionChecked = ref(false)
const loginLoading = ref(false)
const loginError = ref('')
const dashboardRefreshing = ref(false)
const metricsLoading = ref(false)
const dashboardError = ref('')
const environmentLoading = ref(false)
const environmentSaving = ref(false)
const environmentError = ref('')
const environmentSuccess = ref('')
const taskLoading = ref(false)
const taskError = ref('')
const metrics = ref(null)
const environment = ref(null)
const selectedTask = ref(null)
const taskLookupId = ref('')

const loginForm = reactive({ username: '', password: '' })
const environmentDraft = reactive({})

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

const environmentDirty = computed(() => {
  const groups = environment.value?.groups || []
  return groups.some((group) => group.fields.some((field) => hasFieldChanged(field)))
})

const taskMetaItems = computed(() => {
  const task = selectedTask.value?.task
  if (!task) return []
  return [
    { label: '任务 ID', value: task.id ?? '-' },
    { label: '文件名', value: task.filename || '-' },
    { label: '文件路径', value: task.file_path || '-' },
    { label: '批次号', value: task.batch_id || '-' },
    { label: '模式', value: task.mode || '-' },
    { label: 'Trace ID', value: task.trace_id || '-' },
    { label: '页数', value: task.page_count ?? 0 },
    { label: '进度', value: `${Math.round(Number(task.progress_percent || 0))}%` },
    { label: '工作流线程', value: task.workflow_thread_id || '-' },
    { label: '复核状态', value: task.review_status || '-' },
    { label: '创建时间', value: formatTime(task.created_at) },
    { label: '更新时间', value: formatTime(task.updated_at) },
  ]
})

async function refreshSession() {
  try {
    const { data } = await getDevDashboardSession()
    configured.value = !!data.configured
    authenticated.value = !!data.authenticated
    if (authenticated.value) await refreshDashboard()
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
    await refreshDashboard()
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
  environment.value = null
  selectedTask.value = null
  taskLookupId.value = ''
}

async function refreshDashboard() {
  dashboardRefreshing.value = true
  dashboardError.value = ''
  environmentError.value = ''
  environmentSuccess.value = ''
  try {
    await Promise.all([loadMetrics(), loadEnvironment()])
  } catch (error) {
    dashboardError.value = error?.response?.data?.detail || '控制台数据加载失败'
  } finally {
    dashboardRefreshing.value = false
  }
}

async function loadMetrics() {
  metricsLoading.value = true
  try {
    const { data } = await getDevDashboardMetrics()
    metrics.value = data
  } catch (error) {
    if (error?.response?.status === 401) authenticated.value = false
    throw error
  } finally {
    metricsLoading.value = false
  }
}

async function loadEnvironment() {
  environmentLoading.value = true
  try {
    const { data } = await getDevDashboardEnvironment()
    environment.value = data
    hydrateEnvironmentDraft(data)
  } catch (error) {
    environmentError.value = error?.response?.data?.detail || '运行环境读取失败'
    if (error?.response?.status === 401) authenticated.value = false
    throw error
  } finally {
    environmentLoading.value = false
  }
}

function hydrateEnvironmentDraft(snapshot) {
  for (const key of Object.keys(environmentDraft)) delete environmentDraft[key]
  for (const group of snapshot?.groups || []) {
    for (const field of group.fields || []) {
      environmentDraft[field.key] = field.type === 'boolean' ? field.value === 'true' : (field.value ?? '')
    }
  }
}

async function saveEnvironment() {
  environmentSaving.value = true
  environmentError.value = ''
  environmentSuccess.value = ''
  try {
    const values = collectEnvironmentChanges()
    if (!values.length) {
      environmentSuccess.value = '当前没有需要保存的变更。'
      return
    }
    const { data } = await updateDevDashboardEnvironment({ values })
    environment.value = data
    hydrateEnvironmentDraft(data)
    environmentSuccess.value = '运行环境已保存，新请求已开始使用最新配置。'
    await loadMetrics()
  } catch (error) {
    environmentError.value = error?.response?.data?.detail || '运行环境保存失败'
    if (error?.response?.status === 401) authenticated.value = false
  } finally {
    environmentSaving.value = false
  }
}

function collectEnvironmentChanges() {
  const values = []
  for (const group of environment.value?.groups || []) {
    for (const field of group.fields || []) {
      if (!hasFieldChanged(field)) continue
      values.push({
        key: field.key,
        value: serializeFieldValue(field),
      })
    }
  }
  return values
}

function hasFieldChanged(field) {
  const draftValue = environmentDraft[field.key]
  if (field.type === 'boolean') {
    return String(Boolean(draftValue)) !== String(field.value === 'true')
  }
  if (field.sensitive) {
    return String(draftValue || '').trim().length > 0
  }
  return String(draftValue ?? '') !== String(field.value ?? '')
}

function serializeFieldValue(field) {
  if (field.type === 'boolean') {
    return environmentDraft[field.key] ? 'true' : 'false'
  }
  return String(environmentDraft[field.key] ?? '').trim()
}

async function openTask(taskId) {
  if (!taskId) return
  taskLoading.value = true
  taskError.value = ''
  taskLookupId.value = String(taskId)
  try {
    const { data } = await getDevDashboardTask(taskId)
    selectedTask.value = data
  } catch (error) {
    taskError.value = error?.response?.data?.detail || '任务详情加载失败'
    if (error?.response?.status === 401) authenticated.value = false
  } finally {
    taskLoading.value = false
  }
}

async function openTaskFromLookup() {
  const taskId = Number(taskLookupId.value)
  if (!taskId) return
  await openTask(taskId)
}

function fieldInputType(field) {
  if (field.sensitive) return 'password'
  if (field.type === 'number') return 'number'
  return 'text'
}

function displayEnvironmentFieldValue(field) {
  if (field.type === 'boolean') {
    return field.value === 'true' ? 'true' : 'false'
  }
  return field.value || '未配置'
}

function statusBadgeClass(status) {
  return {
    pending: 'bg-amber-50 text-amber-700',
    processing: 'bg-sky-50 text-sky-700',
    done: 'bg-emerald-50 text-emerald-700',
    failed: 'bg-rose-50 text-rose-700',
    human_review: 'bg-violet-50 text-violet-700',
  }[status] || 'bg-slate-100 text-slate-700'
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

function stringifyJson(value) {
  if (!value || (typeof value === 'object' && Object.keys(value).length === 0)) {
    return '暂无数据'
  }
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
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
