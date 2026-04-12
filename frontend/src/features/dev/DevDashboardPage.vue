<template>
  <main class="h-screen overflow-hidden bg-white text-neutral-900">
    <section v-if="!authenticated" class="flex h-full items-center justify-center bg-white px-6">
      <form class="w-full max-w-sm rounded-lg border border-neutral-200 bg-white p-6 shadow-sm" @submit.prevent="submitLogin">
        <p class="text-xs font-medium text-neutral-500">开发控制台</p>
        <h1 class="mt-2 text-2xl font-semibold tracking-tight">/dev/dashboard</h1>
        <p class="mt-2 text-sm leading-6 text-neutral-500">输入独立账号、密码和 2FA 验证码进入开发后台。</p>

        <label class="mt-6 block text-sm font-medium text-neutral-700">
          账号
          <input v-model="loginForm.username" class="mt-1 h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-sm outline-none focus:border-blue-500" autocomplete="username">
        </label>
        <label class="mt-4 block text-sm font-medium text-neutral-700">
          密码
          <input v-model="loginForm.password" type="password" class="mt-1 h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 text-sm outline-none focus:border-blue-500" autocomplete="current-password">
        </label>
        <label class="mt-4 block text-sm font-medium text-neutral-700">
          2FA 验证码
          <input v-model="loginForm.twoFactorCode" inputmode="numeric" maxlength="6" class="mt-1 h-10 w-full rounded-lg border border-neutral-300 bg-white px-3 font-mono text-sm outline-none focus:border-blue-500" placeholder="000000">
          <span class="mt-1 block text-xs font-normal text-neutral-500">可由 Google 认证器生成，不接入 Google 账号服务。</span>
        </label>

        <p v-if="authError" class="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{{ authError }}</p>
        <button class="mt-6 h-10 w-full rounded-lg bg-neutral-900 text-sm font-semibold text-white hover:bg-neutral-700 disabled:cursor-wait disabled:opacity-60" :disabled="loginLoading">
          {{ loginLoading ? '验证中...' : '进入控制台' }}
        </button>
      </form>
    </section>

    <section v-else class="flex h-full">
      <aside
        class="flex h-full shrink-0 flex-col border-r border-neutral-200 bg-[#eef3fb] transition-[width] duration-200"
        :class="sidebarCollapsed ? 'w-[76px]' : 'w-[370px]'"
      >
        <div class="flex h-16 shrink-0 items-center px-4" :class="sidebarCollapsed ? 'justify-center' : 'justify-between'">
          <div v-if="!sidebarCollapsed">
            <p class="text-xs text-neutral-500">开发后台</p>
            <h1 class="text-xl font-semibold tracking-tight">开发后台</h1>
          </div>
          <button class="rounded-full p-2 text-neutral-600 hover:bg-white" :title="sidebarCollapsed ? '展开左侧栏' : '收起左侧栏'" @click="sidebarCollapsed = !sidebarCollapsed">
            <PanelLeftOpen v-if="sidebarCollapsed" class="h-5 w-5" />
            <PanelLeftClose v-else class="h-5 w-5" />
          </button>
        </div>

        <nav class="mt-2 min-h-0 flex-1 overflow-y-auto" :class="sidebarCollapsed ? 'px-2' : 'px-4'">
          <p v-if="!sidebarCollapsed" class="px-2 text-xs font-semibold text-neutral-500">模块</p>
          <button
            v-for="module in modules"
            :key="module.key"
            class="mt-2 flex w-full items-center rounded-full py-3 text-left text-sm transition"
            :class="[
              activeModule === module.key ? 'bg-[#d7e7ff] text-blue-700' : 'text-neutral-700 hover:bg-white',
              sidebarCollapsed ? 'justify-center px-0' : 'justify-between px-4',
            ]"
            :title="module.label"
            @click="activeModule = module.key"
          >
            <span class="flex items-center gap-3">
              <component :is="module.icon" class="h-4 w-4" />
              <span v-if="!sidebarCollapsed">{{ module.label }}</span>
            </span>
            <span v-if="!sidebarCollapsed && module.badge" class="rounded-full bg-white/80 px-2 py-0.5 text-xs text-neutral-500">{{ module.badge }}</span>
          </button>
        </nav>

        <div class="shrink-0 border-t border-neutral-200 py-4" :class="sidebarCollapsed ? 'px-2' : 'px-5'">
          <button class="flex w-full items-center rounded-full py-2 text-left text-sm text-neutral-600 hover:bg-white" :class="sidebarCollapsed ? 'justify-center px-0' : 'gap-3 px-3'" @click="logout">
            <LogOut class="h-4 w-4" />
            <span v-if="!sidebarCollapsed">退出登录</span>
          </button>
        </div>
      </aside>

      <section class="min-w-0 flex-1 overflow-y-auto bg-white">
        <header class="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-neutral-200 bg-white/95 px-6 backdrop-blur">
          <div>
            <h2 class="text-xl font-semibold tracking-tight">{{ activeModuleMeta.label }}</h2>
            <p class="mt-0.5 text-sm text-neutral-500">{{ activeModuleMeta.description }}</p>
          </div>
          <div class="flex items-center gap-2">
            <span class="hidden text-sm text-neutral-500 md:inline">每 30 秒采样，保留最近 12 小时</span>
            <button class="inline-flex items-center gap-2 rounded-lg border border-neutral-200 px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-50" @click="refreshAll">
              <RefreshCw class="h-4 w-4" :class="loading ? 'animate-spin' : ''" />
              刷新
            </button>
            <button v-if="selectedTask" class="rounded-lg border border-neutral-200 px-3 py-2 text-sm text-neutral-700 hover:bg-neutral-50" @click="activeModule = 'taskDetail'">查看当前任务</button>
          </div>
        </header>

        <div class="mx-auto max-w-[1280px] px-8 py-8">
          <section v-if="activeModule === 'monitor'" class="space-y-8">
            <div class="grid grid-cols-4 gap-4">
              <article v-for="card in monitorCards" :key="card.label" class="rounded-lg border border-neutral-200 bg-white p-4">
                <div class="flex items-center justify-between text-sm text-neutral-500">
                  <component :is="card.icon" class="h-5 w-5" />
                  <span>{{ card.label }}</span>
                </div>
                <p class="mt-5 text-3xl font-semibold tracking-tight">{{ card.value }}</p>
                <p class="mt-1 truncate text-sm text-neutral-500">{{ card.detail }}</p>
              </article>
            </div>

            <div class="grid grid-cols-2 gap-6">
              <article class="rounded-lg border border-neutral-200 bg-white p-5">
                <div class="flex items-start justify-between">
                  <div>
                    <h3 class="font-semibold">资源使用率</h3>
                    <p class="mt-1 text-sm text-neutral-500">CPU、GPU 和内存趋势</p>
                  </div>
                  <span class="rounded-full bg-neutral-100 px-3 py-1 text-xs text-neutral-500">近 12 小时</span>
                </div>
                <div class="mt-5 h-72">
                  <Line :data="resourceChartData" :options="percentChartOptions" />
                </div>
              </article>

              <article class="rounded-lg border border-neutral-200 bg-white p-5">
                <div class="flex items-start justify-between">
                  <div>
                    <h3 class="font-semibold">QPS 与任务数</h3>
                    <p class="mt-1 text-sm text-neutral-500">请求吞吐和当前处理中任务</p>
                  </div>
                  <span class="rounded-full bg-neutral-100 px-3 py-1 text-xs text-neutral-500">近 12 小时</span>
                </div>
                <div class="mt-5 h-72">
                  <Line :data="trafficChartData" :options="trafficChartOptions" />
                </div>
              </article>
            </div>

            <div class="grid grid-cols-[1.1fr_0.9fr] gap-6">
              <article class="rounded-lg border border-neutral-200 bg-white">
                <div class="border-b border-neutral-200 px-5 py-4">
                  <h3 class="font-semibold">消息队列</h3>
                  <p class="mt-1 text-sm text-neutral-500">共 {{ snapshot.infra.mqBacklog }} 条堆积消息，{{ snapshot.queues.length }} 个队列。</p>
                </div>
                <div class="divide-y divide-neutral-100">
                  <div v-for="queue in snapshot.queues" :key="queue.name" class="px-5 py-4">
                    <div class="flex items-center justify-between gap-4">
                      <span class="font-mono text-sm">{{ queue.name }}</span>
                      <span class="text-sm text-neutral-500">{{ queue.messages }} 条</span>
                    </div>
                    <div class="mt-3 h-2 overflow-hidden rounded-full bg-neutral-100">
                      <div class="h-full rounded-full bg-blue-500" :style="{ width: `${queueWidth(queue.messages)}%` }" />
                    </div>
                    <p class="mt-2 text-sm text-neutral-500">待消费 {{ queue.ready }} · 未确认 {{ queue.unacked }} · 消费者 {{ queue.consumers || 0 }}</p>
                  </div>
                </div>
              </article>

              <article class="rounded-lg border border-neutral-200 bg-white p-5">
                <h3 class="font-semibold">Worker 摘要</h3>
                <p class="mt-2 text-sm leading-6 text-neutral-500">{{ snapshot.infra.cleanupNote }}</p>
                <div class="mt-5 grid grid-cols-3 gap-3">
                  <div v-for="probe in workerProbes" :key="probe.label" class="rounded-lg border border-neutral-200 p-3">
                    <p class="text-sm text-neutral-500">{{ probe.label }}</p>
                    <p class="mt-2 text-2xl font-semibold">{{ probe.value }}</p>
                  </div>
                </div>
              </article>
            </div>
          </section>

          <section v-else-if="activeModule === 'tasks'" class="space-y-5">
            <div class="flex items-center justify-between gap-4">
              <div class="flex items-center gap-2">
                <button v-for="filter in filters" :key="filter.key" class="rounded-full px-4 py-2 text-sm" :class="taskFilter === filter.key ? 'bg-neutral-900 text-white' : 'bg-neutral-100 text-neutral-600 hover:bg-neutral-200'" @click="taskFilter = filter.key">
                  {{ filter.label }} {{ filter.count }}
                </button>
              </div>
              <input v-model="taskQuery" class="h-10 w-72 rounded-full border border-neutral-200 bg-white px-4 text-sm outline-none focus:border-blue-500" placeholder="搜索任务 ID / 模式 / 状态">
            </div>

            <article class="overflow-hidden rounded-lg border border-neutral-200 bg-white">
              <table class="w-full border-collapse text-left text-sm">
                <thead class="bg-neutral-50 text-neutral-500">
                  <tr>
                    <th class="px-5 py-3 font-medium">任务 ID</th>
                    <th class="px-5 py-3 font-medium">状态</th>
                    <th class="px-5 py-3 font-medium">模式</th>
                    <th class="px-5 py-3 font-medium">耗时</th>
                    <th class="px-5 py-3 font-medium">重试</th>
                    <th class="px-5 py-3 font-medium">操作</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-neutral-100">
                  <tr v-for="task in filteredTasks" :key="task.id" class="cursor-pointer hover:bg-neutral-50" :class="selectedTask?.id === task.id ? 'bg-blue-50' : ''" @click="selectedTaskId = task.id">
                    <td class="px-5 py-3 font-mono">{{ task.id }}</td>
                    <td class="px-5 py-3"><span class="rounded-full px-2 py-1 text-xs" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span></td>
                    <td class="px-5 py-3 font-mono text-neutral-600">{{ task.mode }}</td>
                    <td class="px-5 py-3 text-neutral-600">{{ formatDuration(task.durationMs) }}</td>
                    <td class="px-5 py-3 text-neutral-600">{{ task.retries }}</td>
                    <td class="px-5 py-3">
                      <button class="rounded-lg border border-neutral-200 px-3 py-1.5 text-sm hover:bg-neutral-50 disabled:opacity-50" :disabled="retryingId === task.id" @click.stop="retryTask(task)">重试</button>
                    </td>
                  </tr>
                  <tr v-if="filteredTasks.length === 0">
                    <td colspan="6" class="px-5 py-12 text-center text-neutral-500">暂无任务</td>
                  </tr>
                </tbody>
              </table>
            </article>
          </section>

          <section v-else-if="activeModule === 'middleware'" class="grid grid-cols-2 gap-5">
            <article v-for="item in snapshot.middleware" :key="item.id" class="rounded-lg border border-neutral-200 bg-white p-5">
              <div class="flex items-center justify-between gap-4">
                <div>
                  <h3 class="text-lg font-semibold">{{ item.name }}</h3>
                  <p class="mt-1 text-sm text-neutral-500">{{ item.summary }}</p>
                </div>
                <span class="rounded-full px-3 py-1 text-xs" :class="healthClass(item.status)">{{ healthLabel(item.status) }}</span>
              </div>
              <dl class="mt-5 grid grid-cols-2 gap-3">
                <div v-for="metric in item.metrics" :key="metric.label" class="rounded-lg border border-neutral-200 p-3">
                  <dt class="text-sm text-neutral-500">{{ metric.label }}</dt>
                  <dd class="mt-1 truncate font-semibold">{{ metric.value }}</dd>
                </div>
              </dl>
              <pre class="mt-4 max-h-28 overflow-auto rounded-lg bg-neutral-50 p-3 text-xs leading-5 text-neutral-600">{{ item.detail }}</pre>
            </article>
          </section>

          <section v-else-if="activeModule === 'worker'" class="space-y-5">
            <article class="rounded-lg border border-neutral-200 bg-white p-5">
              <h3 class="text-lg font-semibold">Worker 探针</h3>
              <p class="mt-2 text-sm leading-6 text-neutral-500">{{ snapshot.infra.cleanupNote }}</p>
              <div class="mt-6 grid grid-cols-4 gap-4">
                <div v-for="probe in workerProbes" :key="probe.label" class="rounded-lg border border-neutral-200 p-4">
                  <p class="text-sm text-neutral-500">{{ probe.label }}</p>
                  <p class="mt-4 text-3xl font-semibold">{{ probe.value }}</p>
                </div>
              </div>
            </article>

            <article class="rounded-lg border border-neutral-200 bg-white">
              <div class="border-b border-neutral-200 px-5 py-4">
                <h3 class="font-semibold">模型耗时</h3>
              </div>
              <div class="divide-y divide-neutral-100">
                <div v-for="model in snapshot.models" :key="model.name" class="grid grid-cols-[120px_minmax(0,1fr)_120px] items-center gap-4 px-5 py-4">
                  <span class="font-mono">{{ model.name }}</span>
                  <div class="h-2 overflow-hidden rounded-full bg-neutral-100">
                    <div class="h-full rounded-full bg-blue-500" :style="{ width: `${latencyWidth(model.avgMs)}%` }" />
                  </div>
                  <span class="text-right text-sm text-neutral-500">平均 {{ model.avgMs }} ms</span>
                </div>
              </div>
            </article>
          </section>

          <section v-else class="grid grid-cols-[0.95fr_1.05fr] gap-6">
            <article class="rounded-lg border border-neutral-200 bg-white p-5">
              <h3 class="text-lg font-semibold">源文件 / 耗时瀑布</h3>
              <p class="mt-1 text-sm text-neutral-500">{{ selectedTask?.fileName || '未选择任务' }}</p>
              <div class="mt-5 flex h-64 items-center justify-center rounded-lg border border-neutral-200 bg-neutral-50">
                <img v-if="selectedTask?.previewUrl" :src="selectedTask.previewUrl" :alt="selectedTask.fileName" class="h-full w-full object-contain">
                <div v-else class="text-center text-sm text-neutral-500">
                  <Archive class="mx-auto mb-3 h-8 w-8" />
                  后端返回 previewUrl 后显示源文件图
                </div>
              </div>
              <div class="mt-5 space-y-3">
                <div v-for="stage in waterfallSegments" :key="stage.key" class="grid grid-cols-[92px_minmax(0,1fr)_72px] items-center gap-3 text-sm">
                  <span class="truncate text-neutral-500">{{ stage.label }}</span>
                  <div class="relative h-7 rounded-lg bg-neutral-100">
                    <div class="absolute top-1 h-5 rounded-md bg-blue-500" :style="{ left: `${stage.offsetPct}%`, width: `${stage.widthPct}%` }" />
                  </div>
                  <span class="text-right font-mono text-neutral-600">{{ stage.durationMs }}ms</span>
                </div>
              </div>
            </article>

            <article class="rounded-lg border border-neutral-200 bg-white">
              <div class="border-b border-neutral-200 px-5 py-4">
                <h3 class="font-semibold">任务详情</h3>
                <p class="mt-1 font-mono text-sm text-neutral-500">{{ selectedTask?.id || '-' }}</p>
              </div>
              <div class="flex border-b border-neutral-200 px-4 pt-2">
                <button v-for="tab in inspectorTabs" :key="tab.key" class="rounded-t-lg px-4 py-2 text-sm" :class="inspectorTab === tab.key ? 'bg-neutral-100 text-neutral-900' : 'text-neutral-500 hover:text-neutral-900'" @click="inspectorTab = tab.key">
                  {{ tab.label }}
                </button>
              </div>
              <div class="max-h-[620px] overflow-auto p-5">
                <pre v-if="inspectorTab === 'json'" class="rounded-lg bg-neutral-950 p-4 text-xs leading-5 text-neutral-100">{{ inspectorJson }}</pre>
                <pre v-else-if="inspectorTab === 'stack'" class="whitespace-pre-wrap rounded-lg bg-red-50 p-4 text-xs leading-5 text-red-700">{{ selectedTask?.errorMessage || '当前任务没有异常堆栈。' }}</pre>
                <div v-else class="space-y-3">
                  <div v-for="event in selectedTask?.events || []" :key="event.at + event.name" class="rounded-lg border border-neutral-200 p-4">
                    <div class="flex items-center justify-between gap-3 text-sm">
                      <span class="font-semibold">{{ event.name }}</span>
                      <span class="font-mono text-neutral-500">{{ event.at }}</span>
                    </div>
                    <p class="mt-2 text-sm leading-6 text-neutral-500">{{ event.detail }}</p>
                  </div>
                </div>
              </div>
            </article>
          </section>
        </div>
      </section>
    </section>
  </main>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from 'chart.js'
import { Line } from 'vue-chartjs'
import {
  Activity,
  Archive,
  Cpu,
  Database,
  HardDrive,
  Layers,
  ListChecks,
  LogOut,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Server,
  Timer,
  Users,
  Zap,
} from 'lucide-vue-next'

import {
  getDevDashboardAuthStatus,
  getDevDashboardSnapshot,
  loginDevDashboard,
  logoutDevDashboard,
  retryDevDashboardTask,
} from '../../api/devDashboard.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend)

const METRIC_HISTORY_KEY = 'ocr.dev.dashboard.metricHistory.v1'
const METRIC_WINDOW_MS = 12 * 60 * 60 * 1000

const EMPTY_SNAPSHOT = {
  infra: {
    qps: 0,
    recentRequests: 0,
    mqBacklog: 0,
    mqConsumers: 0,
    ackRate: 0,
    activeTasks: 0,
    totalUsers: 0,
    cpuPercent: 0,
    gpuPercent: 0,
    memoryPercent: 0,
    gpuMemoryPercent: 0,
    workerStatus: 'unknown',
    cleanupNote: '等待后端指标。',
  },
  queues: [],
  middleware: [],
  models: [],
  tasks: [],
}

const authenticated = ref(false)
const authError = ref('')
const loginLoading = ref(false)
const loading = ref(false)
const retryingId = ref('')
const activeModule = ref('monitor')
const sidebarCollapsed = ref(false)
const snapshot = ref(cloneSnapshot())
const chartHistory = ref(loadMetricHistory())
const selectedTaskId = ref('')
const taskFilter = ref('all')
const taskQuery = ref('')
const inspectorTab = ref('json')
const loginForm = ref({ username: '', password: '', twoFactorCode: '' })

const inspectorTabs = [
  { key: 'json', label: '原始数据' },
  { key: 'stack', label: '异常堆栈' },
  { key: 'events', label: '事件记录' },
]

const tasks = computed(() => snapshot.value.tasks || [])

const modules = computed(() => [
  { key: 'monitor', label: '系统监控大盘', description: 'QPS、MQ、任务量、用户数、CPU、GPU 和内存。', icon: Activity },
  { key: 'tasks', label: '任务流调试中心', description: '按状态查看任务，并支持失败任务重新投递。', icon: ListChecks, badge: tasks.value.length },
  { key: 'middleware', label: '中间件详情', description: '消息队列、缓存服务和对象存储的探测状态。', icon: Database, badge: snapshot.value.middleware.length },
  { key: 'worker', label: 'Worker 探针', description: 'Worker 资源、模型耗时和清理策略。', icon: Server },
  { key: 'taskDetail', label: '任务详情', description: '源文件、耗时瀑布、原始数据、堆栈和事件。', icon: Layers, badge: selectedTask.value?.id || '' },
])

const activeModuleMeta = computed(() => {
  return modules.value.find((item) => item.key === activeModule.value) || modules.value[0]
})

const monitorCards = computed(() => [
  { label: 'QPS', value: Number(snapshot.value.infra.qps || 0).toFixed(2), detail: `最近 ${snapshot.value.infra.recentRequests || 0} 次请求`, icon: Activity },
  { label: '消息队列', value: snapshot.value.infra.mqBacklog || 0, detail: `${snapshot.value.infra.mqConsumers || 0} 个消费者`, icon: Database },
  { label: '处理中任务', value: snapshot.value.infra.activeTasks || 0, detail: '运行中 / Worker 已接收', icon: ListChecks },
  { label: '用户总数', value: snapshot.value.infra.totalUsers || 0, detail: '业务用户表', icon: Users },
  { label: 'CPU', value: `${snapshot.value.infra.cpuPercent || 0}%`, detail: 'Java 控制面主机', icon: Cpu },
  { label: 'GPU', value: `${snapshot.value.infra.gpuPercent || 0}%`, detail: `显存 ${snapshot.value.infra.gpuMemoryPercent || 0}%`, icon: Zap },
  { label: '内存', value: `${snapshot.value.infra.memoryPercent || 0}%`, detail: 'JVM 内存', icon: HardDrive },
  { label: '平均耗时', value: averageDuration.value, detail: `${tasks.value.length} 个样本`, icon: Timer },
])

const filters = computed(() => [
  { key: 'all', label: '全部', count: tasks.value.length },
  { key: 'queued', label: '排队', count: countStatus('queued') },
  { key: 'running', label: '运行中', count: countStatus('running') },
  { key: 'failed', label: '失败', count: countStatus('failed') },
  { key: 'completed', label: '完成', count: countStatus('completed') },
])

const filteredTasks = computed(() => {
  const query = taskQuery.value.trim().toLowerCase()
  return tasks.value.filter((task) => {
    if (taskFilter.value !== 'all' && task.status !== taskFilter.value) return false
    if (!query) return true
    return [task.id, task.status, task.mode, task.fileName]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query))
  })
})

const selectedTask = computed(() => {
  return tasks.value.find((task) => task.id === selectedTaskId.value) || filteredTasks.value[0] || tasks.value[0] || null
})

const waterfallTotal = computed(() => {
  return (selectedTask.value?.stages || []).reduce((sum, stage) => sum + Number(stage.durationMs || 0), 0)
})

const waterfallSegments = computed(() => {
  const total = Math.max(1, waterfallTotal.value)
  let offset = 0
  return (selectedTask.value?.stages || []).map((stage) => {
    const duration = Number(stage.durationMs || 0)
    const segment = {
      ...stage,
      offsetPct: Math.min(99, (offset / total) * 100),
      widthPct: Math.max(duration > 0 ? 2 : 0, (duration / total) * 100),
    }
    offset += duration
    return segment
  })
})

const workerProbes = computed(() => [
  { label: 'CPU', value: `${snapshot.value.infra.cpuPercent || 0}%` },
  { label: 'GPU', value: `${snapshot.value.infra.gpuPercent || 0}%` },
  { label: '显存', value: `${snapshot.value.infra.gpuMemoryPercent || 0}%` },
  { label: '内存', value: `${snapshot.value.infra.memoryPercent || 0}%` },
])

const averageDuration = computed(() => {
  const values = tasks.value.map((task) => Number(task.durationMs || 0)).filter((value) => value > 0)
  if (!values.length) return '0 ms'
  return formatDuration(values.reduce((sum, value) => sum + value, 0) / values.length)
})

const inspectorJson = computed(() => JSON.stringify({ 任务: selectedTask.value, 基础指标: snapshot.value.infra }, null, 2))

const resourceChartData = computed(() => ({
  labels: chartHistory.value.map((point) => point.label),
  datasets: [
    lineDataset('CPU', chartHistory.value.map((point) => point.cpu), '#2563eb', 'rgba(37, 99, 235, 0.12)'),
    lineDataset('GPU', chartHistory.value.map((point) => point.gpu), '#10b981', 'rgba(16, 185, 129, 0.12)'),
    lineDataset('内存', chartHistory.value.map((point) => point.memory), '#f59e0b', 'rgba(245, 158, 11, 0.12)'),
  ],
}))

const trafficChartData = computed(() => ({
  labels: chartHistory.value.map((point) => point.label),
  datasets: [
    lineDataset('QPS', chartHistory.value.map((point) => point.qps), '#7c3aed', 'rgba(124, 58, 237, 0.12)'),
    lineDataset('任务数', chartHistory.value.map((point) => point.tasks), '#0ea5e9', 'rgba(14, 165, 233, 0.12)'),
  ],
}))

const percentChartOptions = computed(() => chartOptions({ max: 100, suffix: '%' }))
const trafficChartOptions = computed(() => chartOptions({ max: undefined, suffix: '' }))

function lineDataset(label, data, borderColor, backgroundColor) {
  return {
    label,
    data,
    borderColor,
    backgroundColor,
    borderWidth: 2,
    fill: true,
    pointRadius: 2,
    pointHoverRadius: 4,
    tension: 0.35,
  }
}

function chartOptions({ max, suffix }) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: false,
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: {
        position: 'bottom',
        labels: { boxWidth: 10, boxHeight: 10, color: '#525252', usePointStyle: true },
      },
      tooltip: {
        callbacks: {
          label: (context) => `${context.dataset.label}: ${context.parsed.y}${suffix}`,
        },
      },
    },
    scales: {
      x: {
        grid: { color: '#f5f5f5' },
        ticks: { color: '#737373', maxRotation: 0, maxTicksLimit: 12 },
      },
      y: {
        beginAtZero: true,
        max,
        grid: { color: '#eeeeee' },
        ticks: {
          color: '#737373',
          callback: (value) => `${value}${suffix}`,
        },
      },
    },
  }
}

async function checkAuth() {
  try {
    const { data } = await getDevDashboardAuthStatus()
    authenticated.value = Boolean(data?.authenticated)
    if (authenticated.value) {
      await refreshAll()
      startAutoRefresh()
    }
  } catch {
    authenticated.value = false
  }
}

async function submitLogin() {
  loginLoading.value = true
  authError.value = ''
  try {
    await loginDevDashboard({
      username: loginForm.value.username,
      password: loginForm.value.password,
      two_factor_code: loginForm.value.twoFactorCode,
    })
    authenticated.value = true
    loginForm.value.password = ''
    loginForm.value.twoFactorCode = ''
    await refreshAll()
    startAutoRefresh()
  } catch (error) {
    authError.value = error?.response?.data?.detail || '登录失败，请检查账号、密码和 2FA 验证码。'
  } finally {
    loginLoading.value = false
  }
}

async function logout() {
  try {
    await logoutDevDashboard()
  } finally {
    authenticated.value = false
    snapshot.value = cloneSnapshot()
    stopAutoRefresh()
  }
}

async function refreshAll() {
  if (loading.value) return
  loading.value = true
  try {
    const { data } = await getDevDashboardSnapshot({ include_tasks: true })
    const nextSnapshot = normalizeSnapshot(data)
    snapshot.value = nextSnapshot
    recordMetricPoint(nextSnapshot)
    selectedTaskId.value = selectedTask.value?.id || ''
  } catch (error) {
    if (error?.response?.status === 401) authenticated.value = false
  } finally {
    loading.value = false
  }
}

let autoRefreshTimer = null

function startAutoRefresh() {
  stopAutoRefresh()
  autoRefreshTimer = window.setInterval(() => {
    if (authenticated.value) refreshAll()
  }, 30000)
}

function stopAutoRefresh() {
  if (autoRefreshTimer) {
    window.clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
}

function recordMetricPoint(nextSnapshot) {
  const now = new Date()
  const infra = nextSnapshot.infra
  const nextPoint = {
    timestamp: now.getTime(),
    label: now.toLocaleTimeString('zh-CN', { hour12: false, minute: '2-digit', second: '2-digit' }),
    qps: roundMetric(infra.qps),
    tasks: roundMetric(infra.activeTasks),
    cpu: roundMetric(infra.cpuPercent),
    gpu: roundMetric(infra.gpuPercent),
    memory: roundMetric(infra.memoryPercent),
  }
  chartHistory.value = pruneMetricHistory([...chartHistory.value, nextPoint], now.getTime())
  persistMetricHistory(chartHistory.value)
}

function loadMetricHistory() {
  try {
    const raw = window.localStorage.getItem(METRIC_HISTORY_KEY)
    return pruneMetricHistory(JSON.parse(raw || '[]'))
  } catch {
    return []
  }
}

function persistMetricHistory(points) {
  try {
    window.localStorage.setItem(METRIC_HISTORY_KEY, JSON.stringify(points))
  } catch {
    // Storage may be disabled in private or restricted environments.
  }
}

function pruneMetricHistory(points, now = Date.now()) {
  return (Array.isArray(points) ? points : [])
    .map((point) => ({
      timestamp: numberOf(point.timestamp),
      label: point.label || '',
      qps: roundMetric(point.qps),
      tasks: roundMetric(point.tasks),
      cpu: roundMetric(point.cpu),
      gpu: roundMetric(point.gpu),
      memory: roundMetric(point.memory),
    }))
    .filter((point) => point.timestamp >= now - METRIC_WINDOW_MS)
    .sort((left, right) => left.timestamp - right.timestamp)
}

function roundMetric(value) {
  return Math.round(numberOf(value) * 100) / 100
}

async function retryTask(task) {
  if (!task?.id) return
  retryingId.value = task.id
  try {
    await retryDevDashboardTask(task.id, { source: 'dev-dashboard' })
    await refreshAll()
  } finally {
    retryingId.value = ''
  }
}

function normalizeSnapshot(payload = {}) {
  const infra = payload.infra || {}
  const normalizedInfra = {
    qps: numberOf(infra.qps),
    recentRequests: numberOf(infra.recent_requests ?? infra.recentRequests),
    mqBacklog: numberOf(infra.mq_backlog ?? infra.mqBacklog),
    mqConsumers: numberOf(infra.mq_consumers ?? infra.mqConsumers),
    ackRate: numberOf(infra.ack_rate ?? infra.ackRate),
    activeTasks: numberOf(infra.active_tasks ?? infra.activeTasks),
    totalUsers: numberOf(infra.total_users ?? infra.totalUsers),
    cpuPercent: numberOf(infra.cpu_percent ?? infra.cpuPercent),
    gpuPercent: numberOf(infra.gpu_percent ?? infra.gpuPercent),
    memoryPercent: numberOf(infra.memory_percent ?? infra.memoryPercent),
    gpuMemoryPercent: numberOf(infra.gpu_memory_percent ?? infra.gpuMemoryPercent),
    workerStatus: infra.worker_status || infra.workerStatus || 'unknown',
    cleanupNote: infra.cleanup_note || infra.cleanupNote || '等待 Worker 指标。',
  }
  const normalizedQueues = (payload.queues || []).map(normalizeQueue)
  return {
    infra: normalizedInfra,
    queues: normalizedQueues,
    middleware: (payload.middleware || [])
      .map((item) => normalizeMiddleware(item, normalizedQueues, normalizedInfra))
      .filter(isVisibleMiddleware),
    models: (payload.models || []).map(normalizeModel),
    tasks: (payload.tasks || []).map(normalizeTask),
  }
}

function normalizeQueue(queue = {}) {
  return {
    name: queue.name || '',
    messages: numberOf(queue.messages),
    ready: numberOf(queue.ready),
    unacked: numberOf(queue.unacked),
    consumers: numberOf(queue.consumers),
  }
}

function normalizeMiddleware(item = {}, queues = [], infra = EMPTY_SNAPSHOT.infra) {
  const id = String(item.id || item.name || '').toLowerCase()
  if (id === 'rabbitmq' || item.name === 'RabbitMQ') {
    return normalizeRabbitMiddleware(item, queues, infra)
  }
  if (id === 'redis' || item.name === 'Redis') {
    return normalizeRedisMiddleware(item)
  }
  if (id === 'minio' || item.name === 'MinIO') {
    return normalizeMinioMiddleware(item)
  }
  return {
    id,
    name: item.name || item.id || '',
    status: item.status || '未知',
    summary: item.summary || '',
    metrics: item.metrics || [],
    detail: item.detail || '',
  }
}

function normalizeRabbitMiddleware(item = {}, queues = [], infra = EMPTY_SNAPSHOT.infra) {
  const parsedTotal = firstNumberFromText(item.summary)
  const total = parsedTotal ?? queueBacklogFromMetrics(item.metrics)
  const queueCount = queues.length || queueCountFromText(item.summary)
  return {
    id: 'rabbitmq',
    name: '消息队列',
    status: item.status || '正常',
    summary: `当前堆积 ${total} 条消息，覆盖 ${queueCount} 个队列。`,
    metrics: [
      { label: '消息堆积数', value: `${total} 条` },
      { label: '队列数量', value: `${queueCount} 个` },
      { label: '消费者数量', value: `${infra.mqConsumers || 0} 个` },
      ...translateRabbitQueueMetrics(item.metrics),
    ],
    detail: translateRabbitDetail(item.detail),
  }
}

function normalizeRedisMiddleware(item = {}) {
  return {
    id: 'redis',
    name: '缓存服务',
    status: item.status || '待接入',
    summary: 'Java 控制面未配置缓存探针，等待接入缓存命中率和内存指标。',
    metrics: [
      { label: '探针状态', value: '未接入' },
      { label: '缓存命中率', value: '--' },
    ],
    detail: '接入缓存客户端指标后，可展示缓存命中率、键数量和内存占用。',
  }
}

function normalizeMinioMiddleware(item = {}) {
  const fileMetric = (item.metrics || []).find((metric) => ['文件总数', 'total files', 'files'].includes(String(metric.label || '').toLowerCase()))
  return {
    id: 'minio',
    name: '对象存储',
    status: item.status || '正常',
    summary: item.summary && !/[a-z]{3,}/i.test(item.summary)
      ? item.summary
      : `已记录 ${fileMetric?.value || '--'} 个文件。`,
    metrics: (item.metrics || []).map(translateMinioMetric),
    detail: item.detail && !/[a-z]{3,}/i.test(item.detail) ? item.detail : '文件总数按控制面已记录的对象键去重统计。',
  }
}

function isVisibleMiddleware(item = {}) {
  return !['pgsql', 'postgresql'].includes(String(item.id || item.name || '').toLowerCase())
}

function translateRabbitQueueMetrics(metrics = []) {
  return metrics
    .filter((metric) => !['消息堆积数', '队列数量', '消费者数量'].includes(metric.label))
    .map((metric) => ({
      label: metric.label,
      value: `${numberFromText(metric.value)} 条堆积`,
    }))
}

function translateRabbitDetail(detail = '') {
  return String(detail || '')
    .replace('exchange=', '交换机：')
    .replace(', routing_key=', '；路由键：')
}

function translateMinioMetric(metric = {}) {
  const label = String(metric.label || '').toLowerCase()
  const labelMap = {
    endpoint: '访问地址',
    bucket: '存储桶',
    prefix: '对象前缀',
  }
  return {
    label: labelMap[label] || metric.label || '',
    value: metric.value || '',
  }
}

function queueBacklogFromMetrics(metrics = []) {
  const backlog = metrics.find((metric) => metric.label === '消息堆积数')
  if (backlog) return numberFromText(backlog.value)
  return metrics
    .filter((metric) => !['队列数量', '消费者数量'].includes(metric.label))
    .reduce((sum, metric) => sum + numberFromText(metric.value), 0)
}

function queueCountFromText(value = '') {
  const match = String(value).match(/across\s+(\d+)\s+queues/i)
  return match ? Number(match[1]) : 0
}

function numberFromText(value = '') {
  return firstNumberFromText(value) ?? 0
}

function firstNumberFromText(value = '') {
  const match = String(value || '').match(/\d+/)
  return match ? Number(match[0]) : null
}

function normalizeModel(model = {}) {
  return {
    name: model.name || '',
    avgMs: numberOf(model.avg_ms ?? model.avgMs),
    p95Ms: numberOf(model.p95_ms ?? model.p95Ms),
    gpuMemory: model.gpu_memory || model.gpuMemory || '--',
  }
}

function normalizeTask(task = {}) {
  return {
    id: String(task.id || ''),
    status: normalizeStatus(task.status),
    mode: task.mode || 'ocr',
    durationMs: numberOf(task.duration_ms ?? task.durationMs),
    retries: numberOf(task.retries),
    worker: task.worker || '',
    fileName: task.file_name || task.fileName || '',
    previewUrl: task.preview_url || task.previewUrl || '',
    errorMessage: task.error_message || task.errorMessage || '',
    stages: (task.stages || []).map(normalizeStage),
    events: (task.events || []).map(normalizeEvent),
  }
}

function normalizeStage(stage = {}) {
  return {
    key: stage.key || stage.label || 'stage',
    label: stage.label || stage.key || 'stage',
    durationMs: numberOf(stage.duration_ms ?? stage.durationMs),
  }
}

function normalizeEvent(event = {}) {
  return {
    at: event.at || '',
    name: event.name || '',
    detail: event.detail || '',
  }
}

function countStatus(status) {
  return tasks.value.filter((task) => task.status === status).length
}

function normalizeStatus(status = '') {
  const value = String(status || '').toLowerCase()
  if (['pending', 'queued', 'uploaded'].includes(value)) return 'queued'
  if (['processing', 'running', 'worker_accepted'].includes(value)) return 'running'
  if (['done', 'completed', 'success'].includes(value)) return 'completed'
  if (['failed', 'human_review'].includes(value)) return 'failed'
  return value || 'queued'
}

function statusLabel(status) {
  return { queued: '排队', running: '运行中', failed: '失败', completed: '完成' }[status] || status || '未知'
}

function statusClass(status) {
  if (status === 'failed') return 'bg-red-50 text-red-700'
  if (status === 'running') return 'bg-blue-50 text-blue-700'
  if (status === 'completed') return 'bg-emerald-50 text-emerald-700'
  return 'bg-amber-50 text-amber-700'
}

function healthClass(status = '') {
  const value = String(status).toLowerCase()
  if (['healthy', 'connected', 'ok', '正常', '已连接'].includes(value)) return 'bg-emerald-50 text-emerald-700'
  if (['warning', 'degraded', 'unknown', '待接入', '未知'].includes(value)) return 'bg-amber-50 text-amber-700'
  return 'bg-red-50 text-red-700'
}

function healthLabel(status = '') {
  const value = String(status || '').toLowerCase()
  return {
    healthy: '正常',
    connected: '已连接',
    ok: '正常',
    warning: '待接入',
    degraded: '降级',
    unknown: '未知',
    error: '异常',
  }[value] || status || '未知'
}

function formatDuration(value) {
  const ms = Number(value || 0)
  if (ms < 1000) return `${Math.round(ms)} ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)} s`
  return `${(ms / 60000).toFixed(1)} min`
}

function queueWidth(messages) {
  return Math.min(100, Math.max(3, numberOf(messages) * 4))
}

function latencyWidth(ms) {
  return Math.min(100, Math.max(3, numberOf(ms) / 25))
}

function numberOf(value) {
  const number = Number(value || 0)
  return Number.isFinite(number) ? number : 0
}

function cloneSnapshot() {
  return JSON.parse(JSON.stringify(EMPTY_SNAPSHOT))
}

onMounted(() => {
  checkAuth()
})

onBeforeUnmount(() => {
  stopAutoRefresh()
})
</script>
