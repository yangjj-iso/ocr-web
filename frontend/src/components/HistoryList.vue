<template>
  <div>
    <div v-if="loading" class="px-4 py-8 text-center text-sm gov-muted">
      <svg class="mx-auto mb-2 h-5 w-5 animate-spin text-[var(--gov-primary)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
        <path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" />
      </svg>
      正在加载处理记录...
    </div>

    <div v-else-if="groups.length" class="space-y-2">
      <div v-for="group in groups" :key="group.folder" class="rounded-xl border border-[var(--gov-border)] bg-white overflow-hidden">
        <div
          class="flex cursor-pointer items-center px-4 py-3 transition hover:bg-slate-50"
          @click="toggleFolder(group.folder)"
        >
          <svg
            class="mr-2 h-4 w-4 flex-shrink-0 text-slate-400 transition-transform duration-200"
            :class="expandedFolders[group.folder] ? 'rotate-90' : ''"
            fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
          ><path d="M9 5l7 7-7 7" /></svg>

          <div class="mr-3 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg" :class="expandedFolders[group.folder] ? 'bg-[var(--gov-primary)] text-white' : 'bg-[var(--gov-surface-muted)] text-[var(--gov-primary)]'">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
            </svg>
          </div>

          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <span class="truncate text-sm font-semibold text-[var(--gov-text)]">{{ folderLabel(group.folder) }}</span>
              <span class="rounded-full bg-[var(--gov-primary-soft)] px-1.5 py-0.5 text-[11px] font-medium text-[var(--gov-primary)]">
                {{ group.count }} 份材料
              </span>
              <span v-if="group.batch_ids?.length" class="rounded-full bg-violet-100 px-1.5 py-0.5 text-[11px] font-medium text-violet-700">
                已批处理
              </span>
            </div>
            <div class="mt-0.5 truncate text-xs gov-muted">{{ group.folder }}</div>
          </div>

          <div class="ml-3 flex flex-shrink-0 items-center gap-2">
            <span class="text-xs gov-muted">{{ formatTime(group.last_time) }}</span>
            <button
              class="flex h-6 w-6 items-center justify-center rounded opacity-0 transition hover:bg-red-50 group-hover:opacity-100"
              :class="expandedFolders[group.folder] ? 'opacity-100' : ''"
              title="删除该目录下全部记录"
              @click.stop="confirmDelete(group)"
            >
              <svg class="h-3.5 w-3.5 text-slate-400 hover:text-red-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6M9 7V4h6v3M4 7h16" />
              </svg>
            </button>
          </div>
        </div>

        <div v-if="expandedFolders[group.folder]" class="border-t border-[var(--gov-border)]">
          <div class="flex flex-wrap gap-2 border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-4 py-2.5">
            <button
              class="rounded-lg bg-[var(--gov-primary)] px-3 py-1.5 text-xs font-medium text-white transition hover:brightness-105"
              @click="doExportArchive(group)"
            >导出归档</button>
            <button
              class="rounded-lg px-3 py-1.5 text-xs font-medium text-white transition"
              :class="group.batch_ids?.length ? 'bg-violet-600 hover:brightness-105' : 'cursor-not-allowed bg-violet-300'"
              :disabled="!group.batch_ids?.length"
              @click="openBatchInsights(group)"
            >质量概览</button>
            <button
              class="rounded-lg border border-[var(--gov-border)] bg-white px-3 py-1.5 text-xs font-medium text-[var(--gov-text)] transition hover:bg-slate-50"
              @click="openLatestResult(group)"
            >查看最新结果</button>
          </div>

          <div v-if="folderTasks[group.folder]?.loading" class="px-6 py-4 text-center text-xs gov-muted">
            加载文件列表...
          </div>
          <div v-else-if="folderTasks[group.folder]?.tasks?.length" class="max-h-[360px] overflow-y-auto">
            <div
              v-for="task in folderTasks[group.folder].tasks"
              :key="task.id"
              class="flex items-center border-b border-[var(--gov-border)] px-4 py-2.5 transition last:border-b-0"
              :class="canOpenTask(task) ? 'cursor-pointer hover:bg-[var(--gov-primary-soft)]/40' : 'cursor-not-allowed bg-slate-50/70'"
              @click="canOpenTask(task) && emit('view-result', task.id)"
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
                  :class="task.status === 'done' ? 'bg-emerald-100 text-emerald-700' : task.status === 'failed' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'"
                >{{ task.status === 'done' ? '完成' : task.status === 'failed' ? '失败' : '处理中' }}</span>
                <span class="text-[11px] gov-muted">{{ formatTime(task.created_at) }}</span>
              </div>
            </div>
          </div>
          <div v-else class="px-6 py-4 text-center text-xs gov-muted">该目录下暂无文件记录。</div>
        </div>
      </div>
    </div>

    <div v-else class="px-4 py-10 text-center text-sm gov-muted">
      <svg class="mx-auto mb-3 h-10 w-10 text-slate-300" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
      </svg>
      {{ emptyMessage }}
    </div>

    <div v-if="deleteTarget" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40" @click.self="deleteTarget = null">
      <div class="w-80 rounded-xl bg-white p-6 shadow-xl">
        <h3 class="mb-1 text-sm font-semibold text-[var(--gov-text)]">删除记录确认</h3>
        <p class="mb-1 text-xs gov-muted">
          将删除目录
          <span class="font-medium text-[var(--gov-text)]">"{{ folderLabel(deleteTarget.folder) }}"</span>
          下的全部
          <span class="font-medium text-[var(--gov-danger)]">{{ deleteTarget.count }} 条</span>
          记录。
        </p>
        <p class="mb-4 truncate text-xs text-slate-400">{{ deleteTarget.folder }}</p>
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
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'

import { deleteTasksByFolder, exportArchiveRecords, getFolders, getTasks } from '../api/ocr.js'

const emit = defineEmits(['view-result', 'batch-context'])

const router = useRouter()

const groups = ref([])
const loading = ref(true)
const deleteTarget = ref(null)
const deleting = ref(false)
const loadState = ref('idle')
const loadMessage = ref('')
const expandedFolders = reactive({})
const folderTasks = reactive({})

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

const emptyMessage = computed(() => {
  if (loadMessage.value) return loadMessage.value
  return '暂无处理记录，请先导入材料。'
})

async function loadFolders() {
  loading.value = true
  loadState.value = 'loading'
  loadMessage.value = ''

  try {
    const { data } = await getFolders()
    groups.value = data || []
    loadState.value = 'ready'
  } catch (error) {
    groups.value = []
    if (isBackendUnavailableError(error)) {
      loadState.value = 'backend-unavailable'
      loadMessage.value = '后端服务暂未启动或尚未就绪，处理记录将在服务恢复后显示。'
      return
    }
    if (isTransientNetworkError(error)) {
      loadState.value = 'network-changed'
      loadMessage.value = '网络环境已变化，请稍后重试。'
      return
    }
    loadState.value = 'error'
    loadMessage.value = '处理记录暂时无法加载，请稍后重试。'
    console.error('Load folders failed', error)
  } finally {
    loading.value = false
  }
}

async function toggleFolder(folder) {
  expandedFolders[folder] = !expandedFolders[folder]
  if (expandedFolders[folder] && !folderTasks[folder]) {
    folderTasks[folder] = { loading: true, tasks: [] }

    const group = groups.value.find((g) => g.folder === folder)
    const batchId = group?.batch_ids?.[0] || ''

    if (batchId) {
      emit('batch-context', { folder, batchId })
    }

    try {
      const { data } = await getTasks(1, 200, folder)
      folderTasks[folder] = { loading: false, tasks: data?.tasks || [] }
    } catch (error) {
      console.error('Load folder tasks failed', error)
      folderTasks[folder] = { loading: false, tasks: [] }
    }
  }
}

function refresh() {
  Object.keys(expandedFolders).forEach((k) => { expandedFolders[k] = false })
  Object.keys(folderTasks).forEach((k) => delete folderTasks[k])
  loadFolders()
}

function getLatestBatchId(group) {
  return group.batch_ids?.[0] || ''
}

function doExportArchive(group) {
  const batchId = getLatestBatchId(group)
  exportArchiveRecords({
    folder: group.folder,
    batch_id: batchId,
    filename: `${folderLabel(group.folder)}_archive.xlsx`,
  })
}

function openBatchInsights(group) {
  const batchId = getLatestBatchId(group)
  if (batchId) {
    router.push(`/batch-insights/${encodeURIComponent(batchId)}`)
  }
}

function openLatestResult(group) {
  if (group.latest_task_id) {
    emit('view-result', group.latest_task_id)
  }
}

function canOpenTask(task) {
  return ['done', 'failed'].includes(String(task?.status || ''))
}

defineExpose({ refresh, groups })
onMounted(() => loadFolders())

function folderLabel(folder) {
  if (!folder) return '未知目录'
  const normalized = folder.replace(/\\/g, '/')
  const parts = normalized.split('/').filter(Boolean)
  return parts.at(-1) || folder
}

function formatTime(value) {
  return value ? dayjs(value).format('MM-DD HH:mm') : '-'
}

function confirmDelete(group) {
  deleteTarget.value = group
}

async function doDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await deleteTasksByFolder(deleteTarget.value.folder)
    deleteTarget.value = null
    await loadFolders()
  } catch (error) {
    console.error('Delete folder failed', error)
  } finally {
    deleting.value = false
  }
}
</script>
