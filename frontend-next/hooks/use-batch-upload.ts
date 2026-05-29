'use client'

import { useCallback, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'

import {
  aiMergeExtractBatch,
  exportArchiveRecords,
  getBatchEvaluationMetrics,
  getTasksProgress,
  scanFolder,
  uploadFile,
  uploadFromPath,
} from '@/api/ocr'
import {
  getStoredLatestBatchId,
  normalizeAiErrorMessage,
  rememberLatestBatchId,
  rememberAiRuntimeState,
  useAiCapabilityState,
} from '@/hooks/use-ai-capability-state'
import { VIEW_MODE } from '@/lib/ui-copy'

const ACCEPTED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.pdf']
const IMPORT_STAGE = {
  IDLE: 'idle',
  SCANNING: 'scanning',
  READY: 'ready',
  UPLOADING: 'uploading',
  PROCESSING: 'processing',
  COMPLETED: 'completed',
} as const

export type ImportStage = (typeof IMPORT_STAGE)[keyof typeof IMPORT_STAGE]

const QUEUE_PREVIEW_LIMIT = 5

const delay = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

function fileExtension(name = '') {
  return `.${name.split('.').pop()?.toLowerCase() || ''}`
}

function extractRelativeFolder(relativePath = '') {
  const normalized = String(relativePath || '').replace(/\\/g, '/')
  const segments = normalized.split('/').filter(Boolean)
  if (segments.length <= 1) return ''
  return segments.slice(0, -1).join('/')
}

export function formatSize(bytes = 0) {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}

type QueueSummary = {
  totalFiles: number
  folderCount: number
  totalSize: number
  totalSizeLabel: string
}

function createQueueSummary(): QueueSummary {
  return { totalFiles: 0, folderCount: 0, totalSize: 0, totalSizeLabel: '0B' }
}

function summarizeQueues(queue: File[], pathQueue: PathQueueItem[]): QueueSummary {
  const folders = new Set<string>()
  let totalSize = 0
  for (const file of queue) {
    totalSize += Number((file as any)?.size || 0)
    const folder = extractRelativeFolder((file as any)?.webkitRelativePath || (file as any)?._relativePath || '')
    if (folder) folders.add(folder)
  }
  for (const item of pathQueue) {
    totalSize += Number(item?.size || 0)
    const folder = extractRelativeFolder(item?.rel_path || '')
    if (folder) folders.add(folder)
  }
  return { totalFiles: queue.length + pathQueue.length, folderCount: folders.size, totalSize, totalSizeLabel: formatSize(totalSize) }
}

export type PathQueueItem = {
  path: string
  rel_path?: string
  size?: number
  name?: string
}

type BatchCallbacks = {
  onSubmitted?: () => void
  onCompleted?: (result: BatchResult) => void
}

export type BatchResult = {
  taskIds: Array<string | number>
  batchId: string
  failures: number
  completed: number
  failed: number
  hasUsableResults: boolean
}

// PLACEHOLDER_HOOK

export function useBatchUpload(mode: string, callbacks: BatchCallbacks = {}) {
  const [queue, setQueue] = useState<File[]>([])
  const [pathQueue, setPathQueue] = useState<PathQueueItem[]>([])
  const [folderPath, setFolderPath] = useState('')
  const [excelPath, setExcelPath] = useState('')
  const [outputDir, setOutputDir] = useState('')
  const [scheduledTime, setScheduledTime] = useState('')
  const [viewMode, setViewMode] = useState<string>(VIEW_MODE.DEFAULT)
  const [processing, setProcessing] = useState(false)
  const [scanning, setScanning] = useState(false)
  const [scanMsg, setScanMsg] = useState('')
  const [scanError, setScanError] = useState(false)
  const [importStage, setImportStage] = useState<ImportStage>(IMPORT_STAGE.IDLE)
  const [importMessage, setImportMessage] = useState('')
  const [importProgressPercent, setImportProgressPercent] = useState(0)
  const [queueExpanded, setQueueExpanded] = useState(false)
  const [batchDone, setBatchDone] = useState(false)
  const [lastBatchId, setLastBatchId] = useState(() => getStoredLatestBatchId())
  const [totalCount, setTotalCount] = useState(0)
  const [doneCount, setDoneCount] = useState(0)
  const [completedCount, setCompletedCount] = useState(0)
  const [failedCount, setFailedCount] = useState(0)
  const [processingCount, setProcessingCount] = useState(0)
  const [pendingCount, setPendingCount] = useState(0)
  const [aiMerging, setAiMerging] = useState(false)
  const [aiMergeError, setAiMergeError] = useState('')
  const [aiMergeResult, setAiMergeResult] = useState<any>(null)
  const [aiMetricsLoading, setAiMetricsLoading] = useState(false)
  const [aiMetricsError, setAiMetricsError] = useState('')
  const [aiMetrics, setAiMetrics] = useState<any>(null)

  const completedSummaryRef = useRef<QueueSummary>(createQueueSummary())
  const callbacksRef = useRef(callbacks)
  callbacksRef.current = callbacks

  const aiRuntimeState = useAiCapabilityState()

  const isAdvancedView = viewMode === VIEW_MODE.ADVANCED

  const queueSummary = useMemo(() => summarizeQueues(queue, pathQueue), [queue, pathQueue])
  const displayQueueSummary = useMemo(
    () => (queueSummary.totalFiles ? queueSummary : completedSummaryRef.current),
    [queueSummary]
  )

  // PLACEHOLDER_METHODS

  const setStatus = useCallback((message: string, isError = false) => {
    setScanMsg(message)
    setScanError(isError)
  }, [])

  const setImportState = useCallback((stage: ImportStage, message = '', progress?: number) => {
    setImportStage(stage)
    setImportMessage(message)
    if (progress !== undefined) setImportProgressPercent(Math.max(0, Math.min(100, Number(progress) || 0)))
  }, [])

  const clearAiMergeResult = useCallback(() => {
    setAiMergeResult(null)
    setAiMergeError('')
    setAiMetrics(null)
    setAiMetricsError('')
  }, [])

  const toggleViewMode = useCallback(() => {
    setViewMode((v) => (v === VIEW_MODE.ADVANCED ? VIEW_MODE.DEFAULT : VIEW_MODE.ADVANCED))
  }, [])

  const toggleQueueExpanded = useCallback(() => {
    setQueueExpanded((v) => !v)
  }, [])

  const clearQueue = useCallback(() => {
    setQueue([])
    setPathQueue([])
    setScheduledTime('')
    completedSummaryRef.current = createQueueSummary()
    setScanMsg('')
    setScanError(false)
    setImportStage(IMPORT_STAGE.IDLE)
    setImportMessage('')
    setImportProgressPercent(0)
    setQueueExpanded(false)
  }, [])

  const removeFile = useCallback((index: number) => {
    setQueue((prev) => prev.filter((_, i) => i !== index))
  }, [])

  const removePathFile = useCallback((index: number) => {
    setPathQueue((prev) => prev.filter((_, i) => i !== index))
  }, [])

  // PLACEHOLDER_DRAGDROP

  const addFiles = useCallback((fileList: File[]) => {
    let addedCount = 0
    const accepted: File[] = []
    for (const file of fileList) {
      if (ACCEPTED_EXTENSIONS.includes(fileExtension(file.name))) {
        accepted.push(file)
        addedCount += 1
      }
    }
    if (accepted.length) setQueue((prev) => [...prev, ...accepted])
    return addedCount
  }, [])

  const readDirEntry = useCallback((entry: any, files: File[], currentPath: string): Promise<void> => {
    return new Promise((resolve) => {
      const reader = entry.createReader()
      const readBatch = () => {
        reader.readEntries(async (entries: any[]) => {
          if (!entries.length) { resolve(); return }
          const nested: Promise<void>[] = []
          for (const item of entries) {
            if (item.isFile) {
              await new Promise<void>((done) =>
                item.file((file: File) => {
                  if (ACCEPTED_EXTENSIONS.includes(fileExtension(file.name))) {
                    try { Object.defineProperty(file, '_relativePath', { value: `${currentPath}/${file.name}` }) } catch (_) {}
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
  }, [])

  const onDrop = useCallback(async (event: React.DragEvent) => {
    event.preventDefault()
    const items = event.dataTransfer?.items
    if (items?.length) {
      const files: File[] = []
      const pending: Promise<void>[] = []
      for (let i = 0; i < items.length; i++) {
        const item = items[i]
        if (item.kind !== 'file') continue
        const entry = (item as any).webkitGetAsEntry?.()
        if (entry?.isDirectory) {
          pending.push(readDirEntry(entry, files, entry.name))
        } else {
          const file = item.getAsFile()
          if (file && ACCEPTED_EXTENSIONS.includes(fileExtension(file.name))) files.push(file)
        }
      }
      await Promise.all(pending)
      const addedCount = files.length
      if (addedCount) setQueue((prev) => [...prev, ...files])
      setStatus(addedCount ? `已加入 ${addedCount} 份本地材料。` : '未找到可识别的文件。', !addedCount)
      return
    }
    const fileList = event.dataTransfer?.files
    if (fileList) {
      const arr = Array.from(fileList).filter((f) => ACCEPTED_EXTENSIONS.includes(fileExtension(f.name)))
      if (arr.length) setQueue((prev) => [...prev, ...arr])
      setStatus(arr.length ? `已加入 ${arr.length} 份本地材料。` : '未找到可识别的文件。', !arr.length)
    }
  }, [readDirEntry, setStatus])

  // PLACEHOLDER_FILESELECT

  const onFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []).filter((f) => ACCEPTED_EXTENSIONS.includes(fileExtension(f.name)))
    if (files.length) setQueue((prev) => [...prev, ...files])
    setStatus(files.length ? `已加入 ${files.length} 份本地材料。` : '未找到可识别的文件。', !files.length)
    event.target.value = ''
  }, [setStatus])

  const onFolderSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []).filter((f) => ACCEPTED_EXTENSIONS.includes(fileExtension(f.name)))
    if (files.length) setQueue((prev) => [...prev, ...files])
    setStatus(files.length ? `已导入 ${files.length} 份本地目录材料。` : '未找到可识别的文件。', !files.length)
    event.target.value = ''
  }, [setStatus])

  const importFromPath = useCallback(async () => {
    const currentFolder = folderPath.trim()
    if (!currentFolder) return
    setScanning(true)
    setStatus('')
    setImportState(IMPORT_STAGE.SCANNING, '正在整理目录材料，请稍候…', 28)
    try {
      const { data } = await scanFolder(currentFolder)
      if (!data.count) {
        setStatus('未找到可识别的文件。', true)
        setImportState(IMPORT_STAGE.IDLE, '', 0)
        return
      }
      setPathQueue((prev) => [...prev, ...data.files])
      setFolderPath('')
      setStatus(`已导入 ${data.count} 份目录材料。`)
    } catch (_) {
      setStatus('目录导入未完成，请检查目录权限或路径设置。', true)
      setImportState(IMPORT_STAGE.IDLE, '', 0)
    } finally {
      setScanning(false)
    }
  }, [folderPath, setStatus, setImportState])

  // PLACEHOLDER_BATCH

  const genBatchId = () => `batch_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`

  const startBatch = useCallback(async () => {
    const selectedFiles = [...queue]
    const selectedPaths = [...pathQueue]
    const requestedCount = selectedFiles.length + selectedPaths.length
    if (!requestedCount || processing) return

    completedSummaryRef.current = summarizeQueues(selectedFiles, selectedPaths)

    if (scheduledTime) {
      const delayMs = new Date(scheduledTime).getTime() - Date.now()
      if (delayMs > 0) {
        setProcessing(true)
        setStatus('等待定时开始处理。')
        setImportState(IMPORT_STAGE.READY, '已排队，等待定时开始处理。', 100)
        await delay(delayMs)
      }
    }

    setProcessing(true)
    setBatchDone(false)
    setDoneCount(0)
    setCompletedCount(0)
    setFailedCount(0)
    setProcessingCount(0)
    setPendingCount(requestedCount)
    setTotalCount(requestedCount)
    setStatus('')
    clearAiMergeResult()
    setImportStage(IMPORT_STAGE.UPLOADING)
    setImportMessage(`材料提交中（0/${requestedCount}）`)
    setImportProgressPercent(12)

    const batchId = genBatchId()
    setLastBatchId(batchId)

    const submittedTaskIds: Array<string | number> = []
    let submissionFailures = 0
    let submittedCount = 0
    let firstSubmissionError = ''
    let needExcelInit = !!excelPath.trim()

    for (const file of selectedFiles) {
      try {
        const { data } = await uploadFile(file, mode, {
          relativePath: (file as any).webkitRelativePath || (file as any)._relativePath || '',
          excelPath: excelPath.trim(),
          excelInit: needExcelInit,
          outputDir: outputDir.trim(),
          batchId,
        })
        if (data?.id) { submittedTaskIds.push(data.id); needExcelInit = false }
      } catch (error: any) {
        submissionFailures += 1
        firstSubmissionError ||= normalizeAiErrorMessage(error, '材料提交失败，请检查控制面与计算面服务。')
      } finally {
        submittedCount += 1
        const ratio = requestedCount ? submittedCount / requestedCount : 0
        setImportMessage(`材料提交中（${submittedCount}/${requestedCount}）`)
        setImportProgressPercent(12 + ratio * 38)
      }
    }

    for (const item of selectedPaths) {
      try {
        const { data } = await uploadFromPath(item.path, mode, {
          excelPath: excelPath.trim(),
          excelInit: needExcelInit,
          outputDir: outputDir.trim(),
          batchId,
        })
        if (data?.id) { submittedTaskIds.push(data.id); needExcelInit = false }
      } catch (error: any) {
        submissionFailures += 1
        firstSubmissionError ||= normalizeAiErrorMessage(error, '目录材料提交失败，请检查控制面与计算面服务。')
      } finally {
        submittedCount += 1
        const ratio = requestedCount ? submittedCount / requestedCount : 0
        setImportMessage(`材料提交中（${submittedCount}/${requestedCount}）`)
        setImportProgressPercent(12 + ratio * 38)
      }
    }

    callbacksRef.current.onSubmitted?.()

    if (submittedTaskIds.length) {
      let localCompleted = 0
      let localFailed = submissionFailures
      while (localCompleted + Math.max(localFailed - submissionFailures, 0) < submittedTaskIds.length) {
        try {
          const { data } = await getTasksProgress(submittedTaskIds)
          localCompleted = Number(data?.done_count || 0)
          localFailed = Number(data?.failed_count || 0) + submissionFailures
          const localProcessing = Number(data?.processing_count || 0)
          const localPending = Number(data?.pending_count || 0)
          setCompletedCount(localCompleted)
          setFailedCount(localFailed)
          setProcessingCount(localProcessing)
          setPendingCount(localPending)
          setDoneCount(localCompleted + localFailed)
          const ratio = requestedCount ? (localCompleted + localFailed) / requestedCount : 0
          const failSuffix = localFailed ? `，异常 ${localFailed}` : ''
          setImportStage(IMPORT_STAGE.PROCESSING)
          setImportMessage(`后台识别中（已完成 ${localCompleted + localFailed}/${requestedCount}${failSuffix}）`)
          setImportProgressPercent(55 + ratio * 45)
        } catch (_) {}
        if (localCompleted + Math.max(localFailed - submissionFailures, 0) < submittedTaskIds.length) {
          await delay(1500)
        }
      }
    } else {
      setDoneCount(submissionFailures)
      setCompletedCount(0)
      setFailedCount(submissionFailures)
      setProcessingCount(0)
      setPendingCount(0)
    }

    setProcessing(false)
    const finalCompleted = submittedTaskIds.length > 0 ? submittedTaskIds.length - submissionFailures : 0
    const hasUsableResults = finalCompleted > 0
    setBatchDone(requestedCount > 1 && submittedTaskIds.length > 0 && hasUsableResults)
    setQueue([])
    setPathQueue([])
    setScheduledTime('')
    setQueueExpanded(false)

    if (batchId) {
      if (hasUsableResults) {
        rememberLatestBatchId(batchId)
        rememberAiRuntimeState({ latestBatchId: batchId, aiServiceAvailable: false, lastError: '' })
      } else {
        rememberAiRuntimeState({ latestBatchId: '', aiServiceAvailable: false, lastError: '' })
      }
    }

    if (submissionFailures) {
      const detail = firstSubmissionError ? ` 原因：${firstSubmissionError}` : ''
      setStatus(`本次处理已完成，但有 ${submissionFailures} 份材料处理异常。${detail}`, true)
      setImportStage(IMPORT_STAGE.COMPLETED)
      setImportMessage(
        submittedTaskIds.length
          ? `处理完成，共核验 ${requestedCount} 份材料，其中 ${submissionFailures} 份需要复核。`
          : `材料未成功提交到后台。${firstSubmissionError || '请检查控制面、RabbitMQ 与 Worker 是否已启动。'}`
      )
      setImportProgressPercent(100)
    } else {
      setStatus(`本次处理已完成，共纳入 ${submittedTaskIds.length} 份材料。`)
      setImportStage(IMPORT_STAGE.COMPLETED)
      setImportMessage(`处理完成，共纳入 ${submittedTaskIds.length} 份材料。`)
      setImportProgressPercent(100)
    }

    callbacksRef.current.onCompleted?.({
      taskIds: [...submittedTaskIds],
      batchId,
      failures: submissionFailures,
      completed: finalCompleted,
      failed: submissionFailures,
      hasUsableResults,
    })
  }, [queue, pathQueue, processing, scheduledTime, excelPath, outputDir, mode, setStatus, setImportState, clearAiMergeResult])

  // PLACEHOLDER_AI

  const doExportExcel = useCallback(() => {
    if (!lastBatchId) {
      toast.error('当前没有可导出的批次记录。')
      return
    }
    exportArchiveRecords({ batch_id: lastBatchId, filename: 'batch_archive.xlsx' })
    toast.success('已开始下载本次归档清单')
  }, [lastBatchId])

  const doExportInitExcel = useCallback(() => {
    exportArchiveRecords({ batch_id: 'init_import', filename: 'archive_catalog.xlsx' })
    toast.success('已开始下载目录清单')
  }, [])

  const fetchAiMetrics = useCallback(async ({ forceRefresh = false, batchId = '' } = {}) => {
    const targetBatchId = String(batchId || lastBatchId || '').trim()
    if (!targetBatchId) return null
    setAiMetricsLoading(true)
    setAiMetricsError('')
    try {
      const { data } = await getBatchEvaluationMetrics(targetBatchId, { forceRefresh })
      setAiMetrics(data)
      aiRuntimeState.markAiRuntimeAvailable(targetBatchId)
      return data
    } catch (error: any) {
      setAiMetricsError(normalizeAiErrorMessage(error, '质量概览暂时无法获取，请稍后重试。'))
      aiRuntimeState.markAiRuntimeUnavailable(targetBatchId, error)
      return null
    } finally {
      setAiMetricsLoading(false)
    }
  }, [lastBatchId, aiRuntimeState])

  const runAiMergeExtract = useCallback(async ({ forceRefresh = false } = {}) => {
    const batchId = String(lastBatchId || '').trim()
    if (!batchId) {
      setAiMergeError('当前没有可分析的处理记录，请先完成一次批量导入。')
      return null
    }
    setAiMerging(true)
    setAiMergeError('')
    try {
      const { data } = await aiMergeExtractBatch(batchId, {
        include_evidence: true,
        persist: false,
        force_refresh: forceRefresh,
      })
      setAiMergeResult(data)
      aiRuntimeState.markAiRuntimeAvailable(batchId)
      await fetchAiMetrics({ forceRefresh, batchId })
      return data
    } catch (error: any) {
      setAiMergeError(normalizeAiErrorMessage(error, '智能整合暂未完成，请稍后重试。'))
      aiRuntimeState.markAiRuntimeUnavailable(batchId, error)
      return null
    } finally {
      setAiMerging(false)
    }
  }, [lastBatchId, aiRuntimeState, fetchAiMetrics])

  return {
    queue, pathQueue, folderPath, excelPath, outputDir, scheduledTime,
    viewMode, isAdvancedView, processing, scanning, scanMsg, scanError,
    importStage, importMessage, importProgressPercent, queueExpanded,
    queueSummary, displayQueueSummary, batchDone, lastBatchId,
    totalCount, doneCount, completedCount, failedCount, processingCount, pendingCount,
    aiMerging, aiMergeError, aiMergeResult, aiMetricsLoading, aiMetricsError, aiMetrics,
    setFolderPath, setExcelPath, setOutputDir, setScheduledTime,
    onDrop, onFileSelect, onFolderSelect, importFromPath,
    removeFile, removePathFile, clearQueue, toggleQueueExpanded, toggleViewMode,
    startBatch, doExportExcel, doExportInitExcel,
    runAiMergeExtract, fetchAiMetrics, clearAiMergeResult,
  }
}
