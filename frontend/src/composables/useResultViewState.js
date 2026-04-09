import { computed, onMounted, ref, watch } from 'vue'
import dayjs from 'dayjs'

import { getTask, getTaskFileUrl, getTasks, updateTask } from '../api/ocr.js'
import { getModeLabel, getStatusClass, getStatusLabel } from '../constants/uiCopy.js'
import { useAsyncState } from './useAsyncState.js'
import { useTaskPolling } from './useTaskPolling.js'
import { normalizeTaskForDisplay } from '../utils/ocrDisplay.js'

/**
 * @typedef {{
 *   task: import('vue').Ref<any>,
 *   resultData: import('vue').Ref<{pages: any[]}>,
 *   viewState: import('./useAsyncState.js').AsyncState<any>,
 *   loading: import('vue').ComputedRef<boolean>,
 *   error: import('vue').ComputedRef<string>,
 *   toast: import('vue').Ref<string>,
 *   activeTab: import('vue').Ref<'parsed'|'json'|'fields'|'report'>,
 *   activeKey: import('vue').Ref<string>,
 *   pageNum: import('vue').Ref<number>,
 *   folderTasks: import('vue').Ref<any[]>,
 *   folderLoading: import('vue').Ref<boolean>,
 *   regionRefs: import('vue').Ref<Record<string, HTMLElement>>,
 *   editingKey: import('vue').Ref<string>,
 *   editText: import('vue').Ref<string>,
 *   editingTableKey: import('vue').Ref<string>,
 *   tableDraft: import('vue').Ref<string[][]>,
 *   previewImg: import('vue').Ref<HTMLImageElement | null>,
 *   imgW: import('vue').Ref<number>,
 *   imgH: import('vue').Ref<number>,
 *   natW: import('vue').Ref<number>,
 *   natH: import('vue').Ref<number>,
 *   fileUrl: import('vue').ComputedRef<string>,
 *   folderPath: import('vue').ComputedRef<string>,
 *   folderSourcePath: import('vue').ComputedRef<string>,
 *   materialContextKind: import('vue').ComputedRef<string>,
 *   materialContextValue: import('vue').ComputedRef<string>,
 *   folderLabel: import('vue').ComputedRef<string>,
 *   pages: import('vue').ComputedRef<any[]>,
 *   totalPages: import('vue').ComputedRef<number>,
 *   isPdf: import('vue').ComputedRef<boolean>,
 *   jsonText: import('vue').ComputedRef<string>,
 *   modeLabel: import('vue').ComputedRef<string>,
 *   modeClass: import('vue').ComputedRef<string>,
 *   currentPage: import('vue').ComputedRef<any>,
 *   polling: import('vue').Ref<boolean>,
 *   formatTime: (value?: string) => string,
 *   showToast: (message: string) => void,
 *   statusLabel: (status?: string) => string,
 *   statusClass: (status?: string) => string,
 *   switchTask: (taskId: string | number) => void,
 *   copyRegion: (item: any) => void,
 *   copyAll: () => void,
 *   downloadTxt: () => void,
 *   setRegionRef: (key: string, element: HTMLElement | null) => void,
 *   startTextEdit: (item: any) => void,
 *   cancelTextEdit: () => void,
 *   startTableEdit: (item: any) => void,
 *   cancelTableEdit: () => void,
 *   cloneTableData: (tableData: any[]) => string[][],
 *   tableDataToText: (tableData: any[]) => string,
 *   saveTextEdit: (item: any) => Promise<void>,
 *   saveTableEdit: (item: any) => Promise<void>,
 * }} ResultViewState
 */

/**
 * @param {{
 *   taskId: import('vue').Ref<string | number>,
 *   route: import('vue-router').RouteLocationNormalizedLoaded,
 *   router: import('vue-router').Router,
 * }} options
 * @returns {ResultViewState}
 */
export function useResultViewState({ taskId, route, router }) {
  const task = ref(null)
  const resultData = ref({ pages: [] })
  const viewState = useAsyncState(null)
  const loading = computed(() => viewState.isLoading.value)
  const error = computed(() => viewState.error.value)
  const toast = ref('')
  const activeTab = ref('parsed')
  const activeKey = ref('')
  const pageNum = ref(1)
  const refreshing = ref(false)

  const folderTasks = ref([])
  const folderLoading = ref(false)
  const regionRefs = ref({})

  const editingKey = ref('')
  const editText = ref('')
  const editingTableKey = ref('')
  const tableDraft = ref([['']])

  const previewImg = ref(null)
  const imgW = ref(0)
  const imgH = ref(0)
  const natW = ref(0)
  const natH = ref(0)

  const inferFolderPath = (filePath = '') => {
    const normalized = String(filePath || '')
    if (!normalized) return ''
    const slashIndex = Math.max(normalized.lastIndexOf('/'), normalized.lastIndexOf('\\'))
    return slashIndex >= 0 ? normalized.slice(0, slashIndex) : ''
  }

  const normalizePages = (value) => {
    if (Array.isArray(value)) return value
    if (value && typeof value === 'object' && Array.isArray(value.pages)) {
      return value.pages
    }
    return []
  }

  const normalizeResultData = (data) => {
    const rawResultData = data?.result_data && typeof data.result_data === 'object' ? data.result_data : {}
    const pages = normalizePages(rawResultData.pages ?? data?.result_json)
    return {
      ...rawResultData,
      pages,
    }
  }

  const normalizeTaskDetail = (data) => {
    const normalizedResultData = normalizeResultData(data)
    return normalizeTaskForDisplay({
      ...(data || {}),
      result_data: normalizedResultData,
      result_json: normalizedResultData.pages,
    })
  }

  const normalizeString = (value) => String(value || '').trim()
  const fileUrl = computed(() => getTaskFileUrl(taskId.value))
  const routeFolderPath = computed(() => normalizeString(route.query.folder))
  const routeSubmissionId = computed(() => normalizeString(route.query.submission_id))
  const routeBatchId = computed(() => normalizeString(route.query.batch_id))
  const taskFolderPath = computed(() => normalizeString(task.value?.folder || inferFolderPath(task.value?.file_path || '')))
  const taskBatchId = computed(() => normalizeString(task.value?.batch_id))

  const materialContextKind = computed(() => {
    if (routeFolderPath.value || taskFolderPath.value) return 'folder'
    if (routeSubmissionId.value) return 'submission'
    if (routeBatchId.value || taskBatchId.value) return 'batch'
    return ''
  })

  const materialContextValue = computed(() => {
    if (materialContextKind.value === 'folder') {
      return routeFolderPath.value || taskFolderPath.value
    }
    if (materialContextKind.value === 'submission') {
      return routeSubmissionId.value
    }
    if (materialContextKind.value === 'batch') {
      return routeBatchId.value || taskBatchId.value
    }
    return ''
  })

  const folderPath = computed(() => (
    materialContextKind.value && materialContextValue.value
      ? `${materialContextKind.value}:${materialContextValue.value}`
      : ''
  ))
  const folderSourcePath = computed(() => (materialContextKind.value === 'folder' ? materialContextValue.value : ''))
  const folderLabel = computed(() => {
    if (materialContextKind.value === 'submission') {
      return '同次提交材料'
    }
    if (materialContextKind.value === 'batch') {
      return '同批次材料'
    }
    const normalized = folderSourcePath.value.replace(/\\/g, '/')
    return normalized.split('/').filter(Boolean).pop() || folderSourcePath.value
  })
  const pages = computed(() => normalizePages(resultData.value?.pages))
  const totalPages = computed(() => pages.value.length || 1)
  const isPdf = computed(() => String(task.value?.file_type || '').toLowerCase() === '.pdf')
  const jsonText = computed(() => JSON.stringify(resultData.value, null, 2))
  const modeLabel = computed(() => getModeLabel(task.value?.mode))
  const modeClass = computed(() => ({
    baidu_vl: 'bg-cyan-100 text-cyan-700',
    vl: 'bg-indigo-100 text-indigo-700',
    layout: 'bg-blue-100 text-blue-700',
    ocr: 'bg-green-100 text-green-700',
  }[task.value?.mode] || 'bg-gray-100 text-gray-700'))
  const currentPage = computed(() => pages.value[pageNum.value - 1] || { regions: [], lines: [] })
  let latestFetchToken = 0

  const applyTask = (data) => {
    const normalizedData = normalizeTaskDetail(data)
    task.value = normalizedData
    resultData.value = normalizedData.result_data || { pages: [] }
    if (pageNum.value > totalPages.value) {
      pageNum.value = 1
    }
    if (totalPages.value === 0) {
      pageNum.value = 1
    }
    viewState.data.value = normalizedData
    return normalizedData
  }

  const { polling, start: startPolling, stop: stopPolling } = useTaskPolling(
    async () => {
      const { data } = await getTask(taskId.value)
      return data
    },
    (data) => {
      applyTask(data)
    }
  )

  const fetchTask = async ({ silent = false } = {}) => {
    const fetchToken = ++latestFetchToken
    const requestedTaskId = taskId.value
    if (!silent || !task.value) {
      viewState.setLoading()
    }
    refreshing.value = true
    stopPolling()
    try {
      const { data } = await getTask(requestedTaskId)
      if (fetchToken !== latestFetchToken || String(requestedTaskId) !== String(taskId.value)) {
        return
      }
      const normalizedData = applyTask(data)
      if (pages.value.length) {
        viewState.setSuccess(normalizedData)
      } else {
        viewState.setEmpty(normalizedData)
      }
      if (!['done', 'failed', 'human_review'].includes(normalizedData?.status)) {
        startPolling()
      }
    } catch (requestError) {
      if (fetchToken !== latestFetchToken || String(requestedTaskId) !== String(taskId.value)) {
        return
      }
      const message = requestError.response?.data?.detail || '结果加载失败。'
      if (task.value && silent) {
        showToast(message)
      } else {
        viewState.setError(message)
      }
    } finally {
      if (fetchToken === latestFetchToken) {
        refreshing.value = false
      }
    }
  }

  const loadFolderTasks = async () => {
    if (!materialContextKind.value || !materialContextValue.value) {
      folderTasks.value = []
      return
    }
    folderLoading.value = true
    try {
      const { data } = await getTasks(
        1,
        500,
        materialContextKind.value === 'folder' ? materialContextValue.value : '',
        materialContextKind.value === 'submission' ? materialContextValue.value : '',
        materialContextKind.value === 'batch' ? materialContextValue.value : ''
      )
      folderTasks.value = (data.tasks || []).map((item) => normalizeTaskForDisplay(item))
    } catch (_) {
      folderTasks.value = []
    } finally {
      folderLoading.value = false
    }
  }

  const showToast = (message) => {
    toast.value = message
    window.setTimeout(() => {
      if (toast.value === message) {
        toast.value = ''
      }
    }, 1800)
  }

  const statusLabel = (status) => getStatusLabel(status)

  const statusClass = (status) => getStatusClass(status)

  const formatTime = (value) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-')

  const switchTask = (nextTaskId) => {
    if (String(nextTaskId) === String(taskId.value)) return
    const query = {}
    if (materialContextKind.value === 'folder' && materialContextValue.value) {
      query.folder = materialContextValue.value
    } else if (materialContextKind.value === 'submission' && materialContextValue.value) {
      query.submission_id = materialContextValue.value
    } else if (materialContextKind.value === 'batch' && materialContextValue.value) {
      query.batch_id = materialContextValue.value
    }
    router.push({ path: `/result/${nextTaskId}`, query })
  }

  const copyRegion = (item) => {
    navigator.clipboard.writeText(item?.content || '').then(() => showToast('已复制当前区域。'))
  }

  const copyAll = () => {
    navigator.clipboard.writeText(task.value?.full_text || '').then(() => showToast('已复制全文。'))
  }

  const downloadTxt = () => {
    const blob = new Blob([task.value?.full_text || ''], { type: 'text/plain;charset=utf-8' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${task.value?.filename || 'result'}.txt`
    link.click()
  }

  const setRegionRef = (key, element) => {
    if (element) {
      regionRefs.value[key] = element
    } else {
      delete regionRefs.value[key]
    }
  }

  const startTextEdit = (item) => {
    editingTableKey.value = ''
    editingKey.value = item._key
    editText.value = item.content || ''
  }

  const cancelTextEdit = () => {
    editingKey.value = ''
    editText.value = ''
  }

  const cloneTableData = (tableData) =>
    Array.isArray(tableData) && tableData.length
      ? tableData.map((row) => (Array.isArray(row) && row.length ? [...row] : ['']))
      : [['']]

  const tableDataToText = (tableData) =>
    tableData
      .map((row) => row.map((cell) => String(cell || '')).join('\t').trim())
      .filter(Boolean)
      .join('\n')

  const startTableEdit = (item) => {
    editingKey.value = ''
    editingTableKey.value = item._key
    tableDraft.value = cloneTableData(item.table_data)
  }

  const cancelTableEdit = () => {
    editingTableKey.value = ''
    tableDraft.value = [['']]
  }

  const persistPages = async (successMessage) => {
    const { data } = await updateTask(taskId.value, { result_json: pages.value })
    applyTask(data)
    showToast(successMessage)
  }

  const saveTextEdit = async (item) => {
    const page = pages.value[item._pageIdx]
    if (!page) return

    if (item._regionIdx !== undefined && page.regions?.[item._regionIdx]) {
      page.regions[item._regionIdx].content = editText.value
      // Ensure manual edits take display priority over stale OCR line fragments.
      delete page.regions[item._regionIdx].region_lines
    } else if (item._lineIdx !== undefined && page.lines?.[item._lineIdx]) {
      page.lines[item._lineIdx].text = editText.value
    }

    try {
      await persistPages('文本已保存。')
      cancelTextEdit()
    } catch (_) {
      showToast('保存未完成，请稍后重试。')
    }
  }

  const saveTableEdit = async (item) => {
    const page = pages.value[item._pageIdx]
    if (!page?.regions?.[item._regionIdx]) return
    const region = page.regions[item._regionIdx]
    region.table_data = cloneTableData(tableDraft.value)
    region.content = tableDataToText(tableDraft.value)
    delete region.html

    try {
      await persistPages('表格已保存。')
      cancelTableEdit()
    } catch (_) {
      showToast('保存未完成，请稍后重试。')
    }
  }

  onMounted(async () => {
    await fetchTask()
    await loadFolderTasks()
  })

  watch(
    () => taskId.value,
    async () => {
      pageNum.value = 1
      activeKey.value = ''
      cancelTextEdit()
      cancelTableEdit()
      await fetchTask({ silent: true })
    }
  )

  watch(folderPath, loadFolderTasks)

  return {
    task,
    resultData,
    viewState,
    loading,
    error,
    toast,
    activeTab,
    activeKey,
    pageNum,
    folderTasks,
    folderLoading,
    regionRefs,
    editingKey,
    editText,
    editingTableKey,
    tableDraft,
    previewImg,
    imgW,
    imgH,
    natW,
    natH,
    fileUrl,
    folderPath,
    folderSourcePath,
    materialContextKind,
    materialContextValue,
    folderLabel,
    pages,
    totalPages,
    isPdf,
    jsonText,
    modeLabel,
    modeClass,
    currentPage,
    polling,
    refreshing,
    formatTime,
    showToast,
    statusLabel,
    statusClass,
    switchTask,
    copyRegion,
    copyAll,
    downloadTxt,
    setRegionRef,
    startTextEdit,
    cancelTextEdit,
    startTableEdit,
    cancelTableEdit,
    cloneTableData,
    tableDataToText,
    saveTextEdit,
    saveTableEdit,
  }
}
