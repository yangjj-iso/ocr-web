import { computed, ref } from 'vue'

import {
  aiMergeExtractBatch,
  exportArchiveRecords,
  getBatchEvaluationMetrics,
  getTasksProgress,
  scanFolder,
  uploadFile,
  uploadFromPath,
} from '../api/ocr.js'
import {
  getStoredLatestBatchId,
  normalizeAiErrorMessage,
  rememberLatestBatchId,
  rememberAiRuntimeState,
  useAiCapabilityState,
} from '../composables/useAiCapabilityState.js'
import { VIEW_MODE } from '../constants/uiCopy.js'

const ACCEPTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.pdf']
const IMPORT_STAGE = {
  IDLE: 'idle',
  SCANNING: 'scanning',
  READY: 'ready',
  UPLOADING: 'uploading',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
}
const QUEUE_PREVIEW_LIMIT = 5

const delay = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms))

function fileExtension(name = '') {
  return `.${name.split('.').pop()?.toLowerCase() || ''}`
}

function createQueueSummary() {
  return {
    totalFiles: 0,
    folderCount: 0,
    totalSize: 0,
    totalSizeLabel: '0B',
  }
}

function extractRelativeFolder(relativePath = '') {
  const normalized = String(relativePath || '').replace(/\\/g, '/')
  const segments = normalized.split('/').filter(Boolean)
  if (segments.length <= 1) return ''
  return segments.slice(0, -1).join('/')
}

function formatSize(bytes = 0) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

function summarizeQueues(queue, pathQueue) {
  const folders = new Set()
  let totalSize = 0

  for (const file of queue) {
    totalSize += Number(file?.size || 0)
    const folder = extractRelativeFolder(file?.webkitRelativePath || file?._relativePath || '')
    if (folder) folders.add(folder)
  }

  for (const item of pathQueue) {
    totalSize += Number(item?.size || 0)
    const folder = extractRelativeFolder(item?.rel_path || '')
    if (folder) folders.add(folder)
  }

  return {
    totalFiles: queue.length + pathQueue.length,
    folderCount: folders.size,
    totalSize,
    totalSizeLabel: formatSize(totalSize),
  }
}

/**
 * @typedef {'default' | 'advanced'} ViewMode
 */

/**
 * @typedef {{
 *   queue: import('vue').Ref<File[]>,
 *   pathQueue: import('vue').Ref<any[]>,
 *   folderPath: import('vue').Ref<string>,
 *   excelPath: import('vue').Ref<string>,
 *   outputDir: import('vue').Ref<string>,
 *   scheduledTime: import('vue').Ref<string>,
 *   viewMode: import('vue').Ref<ViewMode>,
 *   isAdvancedView: import('vue').ComputedRef<boolean>,
 *   processing: import('vue').Ref<boolean>,
 *   scanning: import('vue').Ref<boolean>,
 *   scanMsg: import('vue').Ref<string>,
 *   scanError: import('vue').Ref<boolean>,
 *   importStage: import('vue').Ref<string>,
 *   importMessage: import('vue').Ref<string>,
 *   importProgressPercent: import('vue').Ref<number>,
 *   queueExpanded: import('vue').Ref<boolean>,
 *   queueSummary: import('vue').ComputedRef<{totalFiles:number, folderCount:number, totalSize:number, totalSizeLabel:string}>,
 *   displayQueueSummary: import('vue').ComputedRef<{totalFiles:number, folderCount:number, totalSize:number, totalSizeLabel:string}>,
 *   batchDone: import('vue').Ref<boolean>,
 *   lastBatchId: import('vue').Ref<string>,
 *   totalCount: import('vue').Ref<number>,
 *   doneCount: import('vue').Ref<number>,
 *   completedCount: import('vue').Ref<number>,
 *   failedCount: import('vue').Ref<number>,
 *   processingCount: import('vue').Ref<number>,
 *   pendingCount: import('vue').Ref<number>,
 *   aiMerging: import('vue').Ref<boolean>,
 *   aiMergeError: import('vue').Ref<string>,
 *   aiMergeResult: import('vue').Ref<any>,
 *   aiMetricsLoading: import('vue').Ref<boolean>,
 *   aiMetricsError: import('vue').Ref<string>,
 *   aiMetrics: import('vue').Ref<any>,
 *   toggleViewMode: () => void,
 * }} BatchUploadState
 */

/**
 * @param {string} mode
 * @param {Record<string, Function>} [callbacks]
 * @returns {BatchUploadState & Record<string, any>}
 */
export function useBatchUpload(mode, callbacks = {}) {
  const queue = ref([])
  const pathQueue = ref([])
  const folderPath = ref('')
  const excelPath = ref('')
  const outputDir = ref('')
  const scheduledTime = ref('')
  const viewMode = ref(VIEW_MODE.DEFAULT)
  const isAdvancedView = computed(() => viewMode.value === VIEW_MODE.ADVANCED)

  const processing = ref(false)
  const scanning = ref(false)
  const scanMsg = ref('')
  const scanError = ref(false)
  const importStage = ref(IMPORT_STAGE.IDLE)
  const importMessage = ref('')
  const importProgressPercent = ref(0)
  const queueExpanded = ref(false)
  const batchDone = ref(false)
  const lastBatchId = ref(getStoredLatestBatchId())
  const totalCount = ref(0)
  const doneCount = ref(0)
  const completedCount = ref(0)
  const failedCount = ref(0)
  const processingCount = ref(0)
  const pendingCount = ref(0)
  const completedSummary = ref(createQueueSummary())
  const aiMerging = ref(false)
  const aiMergeError = ref('')
  const aiMergeResult = ref(null)
  const aiMetricsLoading = ref(false)
  const aiMetricsError = ref('')
  const aiMetrics = ref(null)
  const aiRuntimeState = useAiCapabilityState()

  const queueSummary = computed(() => summarizeQueues(queue.value, pathQueue.value))
  const displayQueueSummary = computed(() =>
    queueSummary.value.totalFiles ? queueSummary.value : completedSummary.value
  )

  const setStatus = (message, isError = false) => {
    scanMsg.value = message
    scanError.value = isError
  }

  const setImportState = (stage, message = '', progress = importProgressPercent.value) => {
    importStage.value = stage
    importMessage.value = message
    importProgressPercent.value = Math.max(0, Math.min(100, Number(progress) || 0))
  }

  const updateReadyState = (message = '') => {
    const summary = queueSummary.value
    if (!summary.totalFiles) {
      if (!processing.value && !batchDone.value) {
        setImportState(IMPORT_STAGE.IDLE, '', 0)
      }
      queueExpanded.value = false
      return
    }

    const folderSuffix = summary.folderCount ? `，涉及 ${summary.folderCount} 个目录` : ''
    setImportState(IMPORT_STAGE.READY, message || `已整理 ${summary.totalFiles} 份材料${folderSuffix}，可以开始处理。`, 100)
    queueExpanded.value = summary.totalFiles <= QUEUE_PREVIEW_LIMIT
  }

  const updateUploadProgress = (handledCount, requestedCount) => {
    const ratio = requestedCount ? handledCount / requestedCount : 0
    setImportState(IMPORT_STAGE.UPLOADING, `材料提交中（${handledCount}/${requestedCount}）`, 12 + ratio * 38)
  }

  const updateProcessingProgress = (finishedCount, requestedCount, currentFailures = failedCount.value) => {
    const ratio = requestedCount ? finishedCount / requestedCount : 0
    const failureSuffix = currentFailures ? `，异常 ${currentFailures}` : ''
    setImportState(
      IMPORT_STAGE.PROCESSING,
      `后台识别中（已完成 ${finishedCount}/${requestedCount}${failureSuffix}）`,
      55 + ratio * 45
    )
  }

  const addFiles = (fileList) => {
    let addedCount = 0
    for (const file of fileList) {
      if (ACCEPTED_EXTENSIONS.includes(fileExtension(file.name))) {
        queue.value.push(file)
        addedCount += 1
      }
    }
    return addedCount
  }

  const removeFile = (index) => {
    queue.value.splice(index, 1)
    updateReadyState()
  }

  const removePathFile = (index) => {
    pathQueue.value.splice(index, 1)
    updateReadyState()
  }

  const clearQueue = () => {
    queue.value = []
    pathQueue.value = []
    scheduledTime.value = ''
    completedSummary.value = createQueueSummary()
    setStatus('')
    setImportState(IMPORT_STAGE.IDLE, '', 0)
    queueExpanded.value = false
  }

  const toggleQueueExpanded = () => {
    queueExpanded.value = !queueExpanded.value
  }

  const toggleViewMode = () => {
    viewMode.value = isAdvancedView.value ? VIEW_MODE.DEFAULT : VIEW_MODE.ADVANCED
  }

  const clearAiMergeResult = () => {
    aiMergeResult.value = null
    aiMergeError.value = ''
    aiMetrics.value = null
    aiMetricsError.value = ''
  }

  const readDirEntry = (entry, files, currentPath = entry.name) =>
    new Promise((resolve) => {
      const reader = entry.createReader()
      const readBatch = () => {
        reader.readEntries(async (entries) => {
          if (!entries.length) {
            resolve()
            return
          }

          const nested = []
          for (const item of entries) {
            if (item.isFile) {
              await new Promise((done) =>
                item.file((file) => {
                  if (ACCEPTED_EXTENSIONS.includes(fileExtension(file.name))) {
                    try {
                      Object.defineProperty(file, '_relativePath', {
                        value: `${currentPath}/${file.name}`,
                      })
                    } catch (_) {}
                    files.push(file)
                  }
                  done()
                })
              )
            } else if (item.isDirectory) {
              nested.push(readDirEntry(item, files, `${currentPath}/${item.name}`))
            }
          }
          await Promise.all(nested)
          readBatch()
        })
      }
      readBatch()
    })

  const onDrop = async (event) => {
    const items = event.dataTransfer?.items
    if (items?.length) {
      const files = []
      const pending = []
      for (const item of items) {
        if (item.kind !== 'file') continue
        const entry = item.webkitGetAsEntry?.()
        if (entry?.isDirectory) {
          pending.push(readDirEntry(entry, files, entry.name))
        } else {
          const file = item.getAsFile()
          if (file && ACCEPTED_EXTENSIONS.includes(fileExtension(file.name))) {
            files.push(file)
          }
        }
      }
      await Promise.all(pending)
      const addedCount = addFiles(files)
      setStatus(addedCount ? `已加入 ${addedCount} 份本地材料。` : '未找到可识别的文件。', !addedCount)
      if (addedCount) {
        updateReadyState(`已整理 ${queueSummary.value.totalFiles} 份本地材料，待开始处理。`)
      }
      return
    }

    const addedCount = addFiles(event.dataTransfer?.files || [])
    setStatus(addedCount ? `已加入 ${addedCount} 份本地材料。` : '未找到可识别的文件。', !addedCount)
    if (addedCount) {
      updateReadyState(`已整理 ${queueSummary.value.totalFiles} 份本地材料，待开始处理。`)
    }
  }

  const onFileSelect = (event) => {
    const addedCount = addFiles(event.target.files || [])
    setStatus(addedCount ? `已加入 ${addedCount} 份本地材料。` : '未找到可识别的文件。', !addedCount)
    if (addedCount) {
      updateReadyState(`已整理 ${queueSummary.value.totalFiles} 份本地材料，待开始处理。`)
    }
    event.target.value = ''
  }

  const onFolderSelect = (event) => {
    const files = Array.from(event.target.files || []).filter((file) =>
      ACCEPTED_EXTENSIONS.includes(fileExtension(file.name))
    )
    const addedCount = addFiles(files)
    setStatus(addedCount ? `已导入 ${addedCount} 份本地目录材料。` : '未找到可识别的文件。', !addedCount)
    if (addedCount) {
      const summary = queueSummary.value
      updateReadyState(`已整理 ${summary.totalFiles} 份材料${summary.folderCount ? `，涉及 ${summary.folderCount} 个目录` : ''}。`)
    }
    event.target.value = ''
  }

  const importFromPath = async () => {
    const currentFolder = folderPath.value.trim()
    if (!currentFolder) return

    scanning.value = true
    setStatus('')
    setImportState(IMPORT_STAGE.SCANNING, '正在整理目录材料，请稍候…', 28)
    try {
      const { data } = await scanFolder(currentFolder)
      if (!data.count) {
        setStatus('未找到可识别的文件。', true)
        setImportState(queueSummary.value.totalFiles ? IMPORT_STAGE.READY : IMPORT_STAGE.IDLE, importMessage.value, queueSummary.value.totalFiles ? 100 : 0)
        return
      }

      pathQueue.value = [...pathQueue.value, ...data.files]
      folderPath.value = ''
      setStatus(`已导入 ${data.count} 份目录材料。`)
      const summary = queueSummary.value
      updateReadyState(`已整理 ${summary.totalFiles} 份材料${summary.folderCount ? `，涉及 ${summary.folderCount} 个目录` : ''}。`)
    } catch (error) {
      setStatus('目录导入未完成，请检查目录权限或路径设置。', true)
      setImportState(queueSummary.value.totalFiles ? IMPORT_STAGE.READY : IMPORT_STAGE.IDLE, importMessage.value, queueSummary.value.totalFiles ? 100 : 0)
    } finally {
      scanning.value = false
    }
  }

  const genBatchId = () => `batch_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

  const waitUntilFinished = async (taskIds, initialDone = 0, requestedCount = taskIds.length + initialDone) => {
    completedCount.value = 0
    failedCount.value = initialDone
    processingCount.value = taskIds.length
    pendingCount.value = 0
    doneCount.value = initialDone
    updateProcessingProgress(doneCount.value, requestedCount, failedCount.value)

    while (completedCount.value + Math.max(failedCount.value - initialDone, 0) < taskIds.length) {
      try {
        const { data } = await getTasksProgress(taskIds)
        completedCount.value = Number(data?.done_count || 0)
        failedCount.value = Number(data?.failed_count || 0) + initialDone
        processingCount.value = Number(data?.processing_count || 0)
        pendingCount.value = Number(data?.pending_count || 0)
        doneCount.value = completedCount.value + failedCount.value
        updateProcessingProgress(doneCount.value, requestedCount, failedCount.value)
      } catch (_) {}

      if (completedCount.value + Math.max(failedCount.value - initialDone, 0) < taskIds.length) {
        await delay(1500)
      }
    }
  }

  const startBatch = async () => {
    const selectedFiles = [...queue.value]
    const selectedPaths = [...pathQueue.value]
    const requestedCount = selectedFiles.length + selectedPaths.length
    if (!requestedCount || processing.value) return

    completedSummary.value = summarizeQueues(selectedFiles, selectedPaths)

    if (scheduledTime.value) {
      const delayMs = new Date(scheduledTime.value).getTime() - Date.now()
      if (delayMs > 0) {
        processing.value = true
        setStatus('等待定时开始处理。')
        setImportState(IMPORT_STAGE.READY, '已排队，等待定时开始处理。', 100)
        await delay(delayMs)
      }
    }

    processing.value = true
    batchDone.value = false
    doneCount.value = 0
    completedCount.value = 0
    failedCount.value = 0
    processingCount.value = 0
    pendingCount.value = requestedCount
    totalCount.value = requestedCount
    setStatus('')
    clearAiMergeResult()
    updateUploadProgress(0, requestedCount)

    const batchId = requestedCount > 1 ? genBatchId() : ''
    lastBatchId.value = batchId

    const submittedTaskIds = []
    let submissionFailures = 0
    let submittedCount = 0
    let needExcelInit = !!excelPath.value.trim()
    for (const file of selectedFiles) {
      try {
        const { data } = await uploadFile(file, mode, {
          relativePath: file.webkitRelativePath || file._relativePath || '',
          excelPath: excelPath.value.trim(),
          excelInit: needExcelInit,
          outputDir: outputDir.value.trim(),
          batchId,
        })
        if (data?.id) {
          submittedTaskIds.push(data.id)
          needExcelInit = false
        }
      } catch (_) {
        submissionFailures += 1
      } finally {
        submittedCount += 1
        updateUploadProgress(submittedCount, requestedCount)
      }
    }

    for (const item of selectedPaths) {
      try {
        const { data } = await uploadFromPath(item.path, mode, {
          excelPath: excelPath.value.trim(),
          excelInit: needExcelInit,
          outputDir: outputDir.value.trim(),
          batchId,
        })
        if (data?.id) {
          submittedTaskIds.push(data.id)
          needExcelInit = false
        }
      } catch (_) {
        submissionFailures += 1
      } finally {
        submittedCount += 1
        updateUploadProgress(submittedCount, requestedCount)
      }
    }

    callbacks.onSubmitted?.()

    if (submittedTaskIds.length) {
      await waitUntilFinished(submittedTaskIds, submissionFailures, requestedCount)
    } else {
      doneCount.value = submissionFailures
      completedCount.value = 0
      failedCount.value = submissionFailures
      processingCount.value = 0
      pendingCount.value = 0
      updateProcessingProgress(doneCount.value, requestedCount, failedCount.value)
    }

    processing.value = false
    const hasUsableResults = completedCount.value > 0
    batchDone.value = requestedCount > 1 && submittedTaskIds.length > 0 && hasUsableResults
    queue.value = []
    pathQueue.value = []
    scheduledTime.value = ''
    queueExpanded.value = false

    if (batchId) {
      if (hasUsableResults) {
        rememberLatestBatchId(batchId)
        rememberAiRuntimeState({
          latestBatchId: batchId,
          aiServiceAvailable: false,
          lastError: '',
        })
      } else {
        rememberAiRuntimeState({
          latestBatchId: '',
          aiServiceAvailable: false,
          lastError: '',
        })
      }
    }

    if (submissionFailures) {
      setStatus(`本次处理已完成，但有 ${submissionFailures} 份材料处理异常。`, true)
      setImportState(IMPORT_STAGE.COMPLETED, `处理完成，共核验 ${requestedCount} 份材料，其中 ${submissionFailures} 份需要复核。`, 100)
    } else {
      setStatus(`本次处理已完成，共纳入 ${submittedTaskIds.length} 份材料。`)
      setImportState(IMPORT_STAGE.COMPLETED, `处理完成，共纳入 ${submittedTaskIds.length} 份材料。`, 100)
    }

    callbacks.onCompleted?.({
      taskIds: [...submittedTaskIds],
      batchId,
      failures: submissionFailures,
      completed: completedCount.value,
      failed: failedCount.value,
      hasUsableResults,
    })
  }

  const doExportExcel = () => exportArchiveRecords({ batch_id: lastBatchId.value, filename: 'batch_archive.xlsx' })

  const doExportInitExcel = () =>
    exportArchiveRecords({ batch_id: 'init_import', filename: 'archive_catalog.xlsx' })

  const fetchAiMetrics = async ({ forceRefresh = false, batchId = '' } = {}) => {
    const targetBatchId = String(batchId || lastBatchId.value || '').trim()
    if (!targetBatchId) return null

    aiMetricsLoading.value = true
    aiMetricsError.value = ''
    try {
      const { data } = await getBatchEvaluationMetrics(targetBatchId, { forceRefresh })
      aiMetrics.value = data
      aiRuntimeState.markAiRuntimeAvailable(targetBatchId)
      return data
    } catch (error) {
      aiMetricsError.value = normalizeAiErrorMessage(error, '质量概览暂时无法获取，请稍后重试。')
      aiRuntimeState.markAiRuntimeUnavailable(targetBatchId, error)
      return null
    } finally {
      aiMetricsLoading.value = false
    }
  }

  const runAiMergeExtract = async ({ forceRefresh = false } = {}) => {
    const batchId = String(lastBatchId.value || '').trim()
    if (!batchId) {
      aiMergeError.value = '当前没有可分析的处理记录，请先完成一次批量导入。'
      return null
    }

    aiMerging.value = true
    aiMergeError.value = ''
    try {
      const { data } = await aiMergeExtractBatch(batchId, {
        include_evidence: true,
        persist: false,
        force_refresh: forceRefresh,
      })
      aiMergeResult.value = data
      aiRuntimeState.markAiRuntimeAvailable(batchId)
      await fetchAiMetrics({ forceRefresh, batchId })
      return data
    } catch (error) {
      aiMergeError.value = normalizeAiErrorMessage(error, '智能整合暂未完成，请稍后重试。')
      aiRuntimeState.markAiRuntimeUnavailable(batchId, error)
      return null
    } finally {
      aiMerging.value = false
    }
  }

  return {
    queue,
    pathQueue,
    folderPath,
    excelPath,
    outputDir,
    scheduledTime,
    viewMode,
    isAdvancedView,
    processing,
    scanning,
    scanMsg,
    scanError,
    importStage,
    importMessage,
    importProgressPercent,
    queueExpanded,
    queueSummary,
    displayQueueSummary,
    batchDone,
    lastBatchId,
    totalCount,
    doneCount,
    completedCount,
    failedCount,
    processingCount,
    pendingCount,
    aiMerging,
    aiMergeError,
    aiMergeResult,
    aiMetricsLoading,
    aiMetricsError,
    aiMetrics,
    onDrop,
    onFileSelect,
    onFolderSelect,
    importFromPath,
    removeFile,
    removePathFile,
    clearQueue,
    toggleQueueExpanded,
    toggleViewMode,
    formatSize,
    startBatch,
    doExportExcel,
    doExportInitExcel,
    runAiMergeExtract,
    fetchAiMetrics,
    clearAiMergeResult,
  }
}
