<template>
  <div>
    <div v-if="loading" class="px-4 py-8 text-center text-sm gov-muted">
      <svg class="mx-auto mb-2 h-5 w-5 animate-spin text-[var(--gov-primary)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" />
      </svg>
      正在加载处理记录...
    </div>

    <div v-else-if="groups.length" class="space-y-2">
      <div v-for="group in groups" :key="group.submission_id" class="overflow-hidden rounded-xl border border-[var(--gov-border)] bg-white">
        <div
          class="group flex cursor-pointer items-center px-4 py-3 transition hover:bg-slate-50"
          @click="toggleSubmission(group.submission_id)"
        >
          <svg
            class="mr-2 h-4 w-4 flex-shrink-0 text-slate-400 transition-transform duration-200"
            :class="expandedSubmissions[group.submission_id] ? 'rotate-90' : ''"
            fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
          ><path d="M9 5l7 7-7 7" /></svg>

          <div
            class="mr-3 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg"
            :class="expandedSubmissions[group.submission_id] ? 'bg-[var(--gov-primary)] text-white' : 'bg-[var(--gov-surface-muted)] text-[var(--gov-primary)]'"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path d="M8 6h8m-8 4h8m-8 4h5M7 3h10a2 2 0 012 2v14a2 2 0 01-2 2H7a2 2 0 01-2-2V5a2 2 0 012-2z" />
            </svg>
          </div>

          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="truncate text-sm font-semibold text-[var(--gov-text)]">{{ submissionLabel(group) }}</span>
              <span class="rounded-full bg-[var(--gov-primary-soft)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--gov-primary)]">
                {{ group.count }} 份材料
              </span>
              <span v-if="group.batch_id" class="rounded-full bg-violet-100 px-1.5 py-0.5 text-[11px] font-medium text-violet-700">
                可做批次分析
              </span>
            </div>
            <div class="mt-0.5 truncate text-xs gov-muted">{{ submissionMeta(group) }}</div>
          </div>

          <div class="ml-3 flex flex-shrink-0 items-center gap-2">
            <span class="text-xs gov-muted">{{ formatTime(group.last_time) }}</span>

            <template v-if="group.batch_id">
              <button
                class="flex items-center gap-1 rounded border border-[var(--gov-primary)] px-2 py-0.5 text-[11px] font-medium text-[var(--gov-primary)] opacity-0 transition hover:bg-[var(--gov-primary-soft)] group-hover:opacity-100"
                :class="expandedSubmissions[group.submission_id] ? 'opacity-100' : ''"
                title="查看批次整合结果"
                @click.stop="emitViewBatch(group)"
              >
                <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>
                查看结果
              </button>
              <button
                class="flex items-center gap-1 rounded border border-emerald-500 px-2 py-0.5 text-[11px] font-medium text-emerald-600 opacity-0 transition hover:bg-emerald-50 group-hover:opacity-100"
                :class="[exportingBatchId === group.batch_id ? 'opacity-100 cursor-wait' : expandedSubmissions[group.submission_id] ? 'opacity-100' : '']"
                :disabled="exportingBatchId === group.batch_id"
                :title="exportingBatchId === group.batch_id ? '正在导出...' : '导出归档 Excel'"
                @click.stop="handleExportArchive(group)"
              >
                <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
                {{ exportingBatchId === group.batch_id ? '导出中...' : '导出归档' }}
              </button>
            </template>

            <button
              class="flex h-6 w-6 items-center justify-center rounded opacity-0 transition hover:bg-red-50 group-hover:opacity-100"
              :class="expandedSubmissions[group.submission_id] ? 'opacity-100' : ''"
              title="删除本次提交记录"
              @click.stop="confirmDelete(group)"
            >
              <svg class="h-3.5 w-3.5 text-slate-400 hover:text-red-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M9 7V4h6v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>

        <div v-if="expandedSubmissions[group.submission_id]" class="border-t border-[var(--gov-border)]">
          <div v-if="submissionTasks[group.submission_id]?.loading" class="px-6 py-4 text-center text-xs gov-muted">
            加载材料列表...
          </div>
          <div v-else-if="submissionTasks[group.submission_id]?.tasks?.length" class="max-h-[360px] overflow-y-auto">
            <div
              v-for="task in submissionTasks[group.submission_id].tasks"
              :key="task.id"
              class="flex items-center border-b border-[var(--gov-border)] px-4 py-2.5 transition last:border-b-0"
              :class="canOpenTask(task) ? 'cursor-pointer hover:bg-[var(--gov-primary-soft)]/40' : 'cursor-not-allowed bg-slate-50/70'"
              @click="canOpenTask(task) && emitViewResult(task.id, { folder: inferFolderPath(task.file_path), submissionId: group.submission_id, batchId: group.batch_id || task.batch_id || '' })"
            >
              <div class="ml-6 mr-3 flex h-6 w-6 flex-shrink-0 items-center justify-center">
                <svg class="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
              </div>
              <div class="min-w-0 flex-1">
                <span class="truncate text-sm text-[var(--gov-text)]">{{ task.filename || `任务 #${task.id}` }}</span>
              </div>
              <div class="ml-2 flex flex-shrink-0 items-center gap-2">
                <span
                  class="rounded-full px-1.5 py-0.5 text-[10px] font-medium"
                  :class="task.status === 'done' ? 'bg-emerald-100 text-emerald-700' : task.status === 'failed' ? 'bg-red-100 text-red-700' : task.status === 'human_review' ? 'bg-violet-100 text-violet-700' : 'bg-amber-100 text-amber-700'"
                >{{ task.status === 'done' ? '完成' : task.status === 'failed' ? '失败' : task.status === 'human_review' ? '待复核' : '处理中' }}</span>
                <span class="text-[11px] gov-muted">{{ formatTime(task.created_at) }}</span>
              </div>
            </div>
          </div>
          <div v-else class="px-6 py-4 text-center text-xs gov-muted">本次提交暂无材料记录。</div>
        </div>
      </div>
    </div>

    <div v-else class="px-4 py-10 text-center text-sm gov-muted">
      <svg class="mx-auto mb-3 h-10 w-10 text-slate-300" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path d="M8 6h8m-8 4h8m-8 4h5M7 3h10a2 2 0 012 2v14a2 2 0 01-2 2H7a2 2 0 01-2-2V5a2 2 0 012-2z" />
      </svg>
      {{ emptyMessage }}
    </div>

    <div v-if="deleteTarget" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="deleteTarget = null">
      <div class="w-80 rounded-xl bg-white p-6 shadow-xl">
        <h3 class="mb-1 text-sm font-semibold text-[var(--gov-text)]">删除记录确认</h3>
        <p class="mb-1 text-xs gov-muted">
          将删除提交记录
          <span class="font-medium text-[var(--gov-text)]">"{{ submissionLabel(deleteTarget) }}"</span>
          中的
          <span class="font-medium text-[var(--gov-danger)]">{{ deleteTarget.count }} 份</span>
          材料。
        </p>
        <p class="mb-4 truncate text-xs text-slate-400">{{ submissionMeta(deleteTarget) }}</p>
        <div class="flex justify-end space-x-2">
          <button class="rounded border border-[var(--gov-border)] px-3 py-1.5 text-xs text-[var(--gov-text-muted)] hover:bg-slate-50" @click="deleteTarget = null">
            取消
          </button>
          <button
            class="rounded bg-[var(--gov-danger)] px-3 py-1.5 text-xs text-white hover:brightness-105 disabled:opacity-50"
            :disabled="deleting"
            @click="doDelete"
          >
            {{ deleting ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'

import { deleteTasksBySubmission, exportBatchMergeArchiveRecords, getTaskSubmissions, getTasks } from '../api/ocr.js'

const emit = defineEmits(['view-result', 'batch-context', 'view-batch'])

const groups = ref([])
const loading = ref(true)
const deleteTarget = ref(null)
const deleting = ref(false)
const loadMessage = ref('')
const expandedSubmissions = reactive({})
const submissionTasks = reactive({})
const exportingBatchId = ref('')

function extractErrorText(error) {
  return `${error?.response?.data?.detail || error?.response?.data || ''} ${error?.message || ''}`.replace(/\s+/g, ' ').trim()
}

function isBackendUnavailableError(error) {
  const status = Number(error?.response?.status || 0)
  if (status === 502 || status === 503 || status === 504) {
    return true
  }
  return /ECONNREFUSED|ERR_CONNECTION_REFUSED|connection refused|connect ECONNREFUSED|proxy error/i.test(
    extractErrorText(error)
  )
}

function isTransientNetworkError(error) {
  return /ERR_NETWORK_CHANGED|network\s+error|ERR_NETWORK|Failed to fetch|Network request failed/i.test(
    extractErrorText(error)
  )
}

const emptyMessage = computed(() => loadMessage.value || '暂无处理记录，请先提交材料。')

async function loadSubmissions() {
  loading.value = true
  loadMessage.value = ''

  try {
    const { data } = await getTaskSubmissions()
    groups.value = data || []
  } catch (error) {
    groups.value = []
    if (isBackendUnavailableError(error)) {
      loadMessage.value = '后端服务暂未启动或尚未就绪，处理记录将在服务恢复后显示。'
      return
    }
    if (isTransientNetworkError(error)) {
      loadMessage.value = '网络环境已变化，请稍后重试。'
      return
    }
    loadMessage.value = '处理记录暂时无法加载，请稍后重试。'
    console.error('Load submissions failed', error)
  } finally {
    loading.value = false
  }
}

async function toggleSubmission(submissionId) {
  expandedSubmissions[submissionId] = !expandedSubmissions[submissionId]
  if (expandedSubmissions[submissionId] && !submissionTasks[submissionId]) {
    submissionTasks[submissionId] = { loading: true, tasks: [] }

    const group = groups.value.find((item) => item.submission_id === submissionId)
    if (group?.batch_id) {
      emit('batch-context', { submissionId, batchId: group.batch_id })
    }

    try {
      const { data } = await getTasks(1, 200, '', submissionId)
      submissionTasks[submissionId] = { loading: false, tasks: data?.tasks || [] }
    } catch (error) {
      console.error('Load submission tasks failed', error)
      submissionTasks[submissionId] = { loading: false, tasks: [] }
    }
  }
}

function inferFolderPath(filePath = '') {
  const normalized = String(filePath || '')
  if (!normalized) return ''
  const slashIndex = Math.max(normalized.lastIndexOf('/'), normalized.lastIndexOf('\\'))
  return slashIndex >= 0 ? normalized.slice(0, slashIndex) : ''
}

function emitViewBatch(group) {
  if (!group?.batch_id) return
  emit('view-batch', { batchId: group.batch_id, submissionId: group.submission_id })
}

async function handleExportArchive(group) {
  if (!group?.batch_id || exportingBatchId.value === group.batch_id) return
  exportingBatchId.value = group.batch_id
  try {
    exportBatchMergeArchiveRecords({ batchId: group.batch_id })
  } finally {
    setTimeout(() => {
      if (exportingBatchId.value === group.batch_id) exportingBatchId.value = ''
    }, 2000)
  }
}

function emitViewResult(taskId, options = {}) {
  if (!taskId) return
  emit('view-result', {
    taskId,
    folder: String(options.folder || '').trim(),
    submissionId: String(options.submissionId || '').trim(),
    batchId: String(options.batchId || '').trim(),
  })
}

function refresh() {
  Object.keys(expandedSubmissions).forEach((key) => { expandedSubmissions[key] = false })
  Object.keys(submissionTasks).forEach((key) => delete submissionTasks[key])
  loadSubmissions()
}

function canOpenTask(task) {
  return ['done', 'failed', 'human_review'].includes(String(task?.status || ''))
}

function submissionLabel(group) {
  return group?.submission_name || '未命名提交'
}

function submissionMeta(group) {
  const username = group?.submitter_username || '匿名用户'
  const batchSuffix = group?.batch_id ? ` · 批次 ${group.batch_id}` : ''
  return `提交人：${username}${batchSuffix}`
}

function formatTime(value) {
  return value ? dayjs(value).format('MM-DD HH:mm') : '-'
}

function confirmDelete(group) {
  deleteTarget.value = group
}

async function doDelete() {
  if (!deleteTarget.value?.submission_id) return
  deleting.value = true
  try {
    await deleteTasksBySubmission(deleteTarget.value.submission_id)
    deleteTarget.value = null
    await loadSubmissions()
  } catch (error) {
    console.error('Delete submission failed', error)
  } finally {
    deleting.value = false
  }
}

defineExpose({ refresh, groups })
onMounted(() => loadSubmissions())
</script>
