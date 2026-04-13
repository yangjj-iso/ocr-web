<template>
  <section class="gov-panel overflow-hidden">
    <div class="border-b border-[var(--gov-border)] bg-white px-5 py-4">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p class="text-xs font-semibold tracking-[0.14em] text-[var(--gov-primary)]">任务界面</p>
          <h3 class="mt-2 text-lg font-semibold text-[var(--gov-text)]">提交的任务</h3>
          <p class="mt-1 text-xs gov-muted">按批次查看，自动刷新。</p>
        </div>
        <button
          class="rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2 text-xs font-medium text-[var(--gov-text)] transition hover:bg-slate-50"
          :disabled="loading"
          @click="refresh"
        >
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <div class="bg-white p-5">
      <div class="grid grid-cols-2 gap-2 text-xs xl:grid-cols-5">
        <button
          v-for="item in statusFilters"
          :key="item.key"
          class="rounded-lg border px-3 py-3 text-left transition"
          :class="activeFilter === item.key ? item.activeClass : 'border-[var(--gov-border)] bg-[var(--gov-surface-muted)] hover:bg-slate-50'"
          @click="activeFilter = item.key"
        >
          <p class="font-semibold" :class="activeFilter === item.key ? item.textClass : 'text-[var(--gov-text)]'">
            {{ item.label }}
          </p>
          <p class="mt-1 text-lg font-semibold" :class="item.textClass">{{ item.count }}</p>
        </button>
      </div>

      <div v-if="loading && !groups.length" class="px-4 py-10 text-center text-sm gov-muted">
        <svg class="mx-auto mb-2 h-5 w-5 animate-spin text-[var(--gov-primary)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" />
        </svg>
        正在加载任务...
      </div>

      <div v-else-if="displayGroups.length" class="mt-4 space-y-3">
        <article
          v-for="group in displayGroups"
          :key="groupId(group)"
          class="overflow-hidden rounded-lg border border-[var(--gov-border)] bg-white"
        >
          <button
            class="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-slate-50"
            @click="toggleGroup(group)"
          >
            <svg
              class="h-4 w-4 flex-shrink-0 text-slate-400 transition-transform"
              :class="expandedGroups[groupId(group)] ? 'rotate-90' : ''"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              viewBox="0 0 24 24"
            >
              <path d="M9 5l7 7-7 7" />
            </svg>

            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <span class="truncate text-sm font-semibold text-[var(--gov-text)]">{{ submissionName(group) }}</span>
                <span class="rounded-full bg-[var(--gov-primary-soft)] px-2 py-0.5 text-[11px] font-medium text-[var(--gov-primary)]">
                  {{ group.count || groupTasks(group).length }} 个任务
                </span>
                <span class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="statusMeta(groupStatus(group)).className">
                  {{ statusMeta(groupStatus(group)).label }}
                </span>
              </div>
              <p class="mt-1 truncate text-xs gov-muted">{{ groupSubtitle(group) }}</p>
            </div>

            <div class="hidden flex-shrink-0 items-center gap-2 text-xs gov-muted md:flex">
              <span>{{ formatTime(group.last_time || group.lastTime) }}</span>
              <button
                v-if="groupBatchId(group)"
                class="rounded-lg border border-[var(--gov-primary)] px-2 py-1 text-[11px] font-medium text-[var(--gov-primary)] transition hover:bg-[var(--gov-primary-soft)]"
                @click.stop="emitViewBatch(group)"
              >
                查看批次
              </button>
            </div>
          </button>

          <div v-if="expandedGroups[groupId(group)]" class="border-t border-[var(--gov-border)]">
            <div v-if="tasksState(group).loading" class="px-6 py-4 text-center text-xs gov-muted">任务加载中...</div>
            <div v-else-if="groupTasks(group).length" class="max-h-[420px] overflow-y-auto">
              <button
                v-for="task in groupTasks(group)"
                :key="task.id"
                class="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b border-[var(--gov-border)] px-4 py-3 text-left transition last:border-b-0"
                :class="canOpenTask(task) ? 'hover:bg-[var(--gov-primary-soft)]/40' : 'cursor-default bg-slate-50/70'"
                @click="canOpenTask(task) && emitViewResult(task, group)"
              >
                <div class="min-w-0">
                  <p class="truncate text-sm text-[var(--gov-text)]">{{ task.filename || `任务 #${task.id}` }}</p>
                  <p class="mt-1 truncate text-[11px] gov-muted">{{ task.file_path || task.filePath || '等待后台写入文件路径' }}</p>
                </div>
                <div class="flex flex-shrink-0 items-center gap-2">
                  <span class="rounded-full px-2 py-0.5 text-[11px] font-medium" :class="statusMeta(taskStatus(task)).className">
                    {{ statusMeta(taskStatus(task)).label }}
                  </span>
                  <span class="hidden w-12 text-right text-[11px] gov-muted sm:inline">{{ progressText(task) }}</span>
                </div>
              </button>
            </div>
            <div v-else class="px-6 py-4 text-center text-xs gov-muted">本次提交暂无任务明细。</div>
          </div>
        </article>
      </div>

      <div v-else class="px-4 py-10 text-center text-sm gov-muted">
        <svg class="mx-auto mb-3 h-10 w-10 text-slate-300" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
          <path d="M8 6h8m-8 4h8m-8 4h5M7 3h10a2 2 0 012 2v14a2 2 0 01-2 2H7a2 2 0 01-2-2V5a2 2 0 012-2z" />
        </svg>
        {{ emptyMessage }}
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'

import { getTaskSubmissions, getTasks } from '../api/ocr.js'

const emit = defineEmits(['view-result', 'batch-context', 'view-batch'])

const groups = ref([])
const loading = ref(false)
const loadMessage = ref('')
const activeFilter = ref('all')
const expandedGroups = reactive({})
const taskStates = reactive({})
let pollTimer = null

const STATUS_META = {
  all: {
    label: '全部',
    className: 'bg-slate-100 text-slate-600',
    activeClass: 'border-[var(--gov-primary)] bg-[var(--gov-primary-soft)]',
    textClass: 'text-[var(--gov-primary)]',
  },
  submitting: {
    label: '提交中',
    className: 'bg-blue-100 text-blue-700',
    activeClass: 'border-blue-200 bg-blue-50',
    textClass: 'text-blue-700',
  },
  pending: {
    label: '排队中',
    className: 'bg-slate-100 text-slate-600',
    activeClass: 'border-slate-300 bg-slate-100',
    textClass: 'text-slate-700',
  },
  processing: {
    label: '处理中',
    className: 'bg-amber-100 text-amber-700',
    activeClass: 'border-amber-200 bg-amber-50',
    textClass: 'text-amber-700',
  },
  done: {
    label: '完成',
    className: 'bg-emerald-100 text-emerald-700',
    activeClass: 'border-emerald-200 bg-emerald-50',
    textClass: 'text-emerald-700',
  },
  failed: {
    label: '错误',
    className: 'bg-red-100 text-red-700',
    activeClass: 'border-red-200 bg-red-50',
    textClass: 'text-red-700',
  },
}

const emptyMessage = computed(() => loadMessage.value || '暂无任务')
const allTasks = computed(() => groups.value.flatMap((group) => groupTasks(group)))
const statusCounts = computed(() => {
  const counts = { all: allTasks.value.length, submitting: 0, pending: 0, processing: 0, done: 0, failed: 0 }
  for (const task of allTasks.value) {
    counts[taskStatus(task)] += 1
  }
  return counts
})
const statusFilters = computed(() =>
  ['all', 'submitting', 'pending', 'processing', 'done', 'failed'].map((key) => ({
    key,
    label: STATUS_META[key].label,
    count: statusCounts.value[key] || 0,
    activeClass: STATUS_META[key].activeClass,
    textClass: STATUS_META[key].textClass,
  }))
)
const displayGroups = computed(() => {
  if (activeFilter.value === 'all') return groups.value
  return groups.value.filter((group) => groupTasks(group).some((task) => taskStatus(task) === activeFilter.value))
})
const hasActiveTasks = computed(() =>
  allTasks.value.some((task) => ['submitting', 'pending', 'processing'].includes(taskStatus(task)))
)

function statusMeta(status) {
  return STATUS_META[status] || STATUS_META.processing
}

function normalizeStatus(status) {
  return String(status || '').trim().toLowerCase()
}

function taskStatus(task) {
  const status = normalizeStatus(task?.status)
  if (['submitting', 'uploading', 'uploaded'].includes(status)) return 'submitting'
  if (['pending', 'queued'].includes(status)) return 'pending'
  if (['done', 'completed'].includes(status)) return 'done'
  if (['failed', 'error'].includes(status)) return 'failed'
  return 'processing'
}

function groupStatus(group) {
  const tasks = groupTasks(group)
  if (!tasks.length) return 'submitting'
  const counts = tasks.reduce((acc, task) => {
    const status = taskStatus(task)
    acc[status] = (acc[status] || 0) + 1
    return acc
  }, {})
  if (counts.processing) return 'processing'
  if (counts.pending) return 'pending'
  if (counts.submitting) return 'submitting'
  if (counts.failed) return 'failed'
  return 'done'
}

function groupId(group) {
  return group?.submission_id || group?.submissionId || group?.batch_id || group?.batchId || `single:${group?.latest_task_id || group?.latestTaskId || ''}`
}

function groupBatchId(group) {
  return String(group?.batch_id || group?.batchId || '').trim()
}

function submissionName(group) {
  return group?.submission_name || group?.submissionName || '未命名提交'
}

function submitterName(group) {
  return group?.submitter_username || group?.submitterUsername || '匿名用户'
}

function tasksState(group) {
  return taskStates[groupId(group)] || { loading: false, tasks: [] }
}

function groupTasks(group) {
  return tasksState(group).tasks || []
}

function groupSubtitle(group) {
  const batchId = groupBatchId(group)
  const parts = [`提交人：${submitterName(group)}`]
  if (batchId) parts.push(`批次 ${batchId}`)
  const counts = groupTasks(group).reduce((acc, task) => {
    const status = taskStatus(task)
    acc[status] = (acc[status] || 0) + 1
    return acc
  }, {})
  const statusText = [
    counts.submitting ? `提交中 ${counts.submitting}` : '',
    counts.pending ? `排队 ${counts.pending}` : '',
    counts.processing ? `处理中 ${counts.processing}` : '',
    counts.done ? `完成 ${counts.done}` : '',
    counts.failed ? `错误 ${counts.failed}` : '',
  ].filter(Boolean).join(' / ')
  if (statusText) parts.push(statusText)
  return parts.join(' · ')
}

function formatTime(value) {
  return value ? dayjs(value).format('MM-DD HH:mm') : '-'
}

function progressText(task) {
  const value = Number(task?.progress_percent ?? task?.progressPercent ?? 0)
  if (!Number.isFinite(value) || value <= 0) return '-'
  return `${Math.round(value)}%`
}

function inferFolderPath(filePath = '') {
  const normalized = String(filePath || '')
  if (!normalized) return ''
  const slashIndex = Math.max(normalized.lastIndexOf('/'), normalized.lastIndexOf('\\'))
  return slashIndex >= 0 ? normalized.slice(0, slashIndex) : ''
}

function canOpenTask(task) {
  return ['done', 'failed', 'human_review'].includes(normalizeStatus(task?.status))
}

function emitViewResult(task, group) {
  emit('view-result', {
    taskId: task.id,
    folder: inferFolderPath(task.file_path || task.filePath || ''),
    submissionId: groupId(group),
    batchId: groupBatchId(group) || task.batch_id || task.batchId || '',
  })
}

function emitViewBatch(group) {
  const batchId = groupBatchId(group)
  if (!batchId) return
  emit('view-batch', { batchId, submissionId: groupId(group) })
}

function toggleGroup(group) {
  const id = groupId(group)
  expandedGroups[id] = !expandedGroups[id]
}

async function loadGroupTasks(group) {
  const id = groupId(group)
  if (!id) return
  taskStates[id] = { ...(taskStates[id] || {}), loading: true, tasks: taskStates[id]?.tasks || [] }
  try {
    const { data } = await getTasks(1, 1000, '', id)
    taskStates[id] = { loading: false, tasks: data?.tasks || [] }
  } catch (error) {
    console.error('Load task board group failed', error)
    taskStates[id] = { loading: false, tasks: [] }
  }
}

async function refresh(options = {}) {
  const silent = Boolean(options.silent)
  if (!silent) loading.value = true
  loadMessage.value = ''

  try {
    const { data } = await getTaskSubmissions()
    groups.value = Array.isArray(data) ? data.slice(0, 20) : []
    await Promise.all(groups.value.map(loadGroupTasks))

    if (groups.value.length && !Object.keys(expandedGroups).some((id) => expandedGroups[id])) {
      expandedGroups[groupId(groups.value[0])] = true
    }
  } catch (error) {
    console.error('Load task board failed', error)
    groups.value = []
    loadMessage.value = '任务暂时无法加载，请稍后重试。'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  refresh()
  pollTimer = window.setInterval(() => {
    if (!loading.value && hasActiveTasks.value) {
      refresh({ silent: true })
    }
  }, 5000)
})

onBeforeUnmount(() => {
  if (pollTimer) window.clearInterval(pollTimer)
})

defineExpose({ refresh, groups })
</script>
