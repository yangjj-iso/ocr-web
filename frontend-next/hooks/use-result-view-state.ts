'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import dayjs from 'dayjs'
import { useRouter, useSearchParams } from 'next/navigation'

import { getTask, getTaskFileUrl, getTasks, updateTask } from '@/api/ocr'
import { getModeLabel, getStatusClass, getStatusLabel } from '@/lib/ui-copy'
import { useAsyncState } from '@/hooks/use-async-state'
import { useTaskPolling } from '@/hooks/use-task-polling'
import { normalizeTaskForDisplay } from '@/lib/ocr-display'

function inferFolderPath(filePath = '') {
  const normalized = String(filePath || '')
  if (!normalized) return ''
  const slashIndex = Math.max(normalized.lastIndexOf('/'), normalized.lastIndexOf('\\'))
  return slashIndex >= 0 ? normalized.slice(0, slashIndex) : ''
}

function normalizePages(value: any): any[] {
  if (Array.isArray(value)) return value
  if (value && typeof value === 'object' && Array.isArray(value.pages)) return value.pages
  return []
}

function normalizeResultData(data: any) {
  const rawResultData = data?.result_data && typeof data.result_data === 'object' ? data.result_data : {}
  const pages = normalizePages(rawResultData.pages ?? data?.result_json)
  return { ...rawResultData, pages }
}

function normalizeTaskDetail(data: any) {
  const normalizedResultData = normalizeResultData(data)
  return normalizeTaskForDisplay({
    ...(data || {}),
    result_data: normalizedResultData,
    result_json: normalizedResultData.pages,
  })
}

const MODE_CLASS_MAP: Record<string, string> = {
  baidu_vl: 'bg-cyan-100 text-cyan-700',
  vl: 'bg-indigo-100 text-indigo-700',
  layout: 'bg-blue-100 text-blue-700',
  ocr: 'bg-green-100 text-green-700',
}

// PLACEHOLDER_HOOK_BODY

export function useResultViewState(taskId: string | number) {
  const router = useRouter()
  const searchParams = useSearchParams()

  const [task, setTask] = useState<any>(null)
  const [resultData, setResultData] = useState<{ pages: any[] }>({ pages: [] })
  const viewState = useAsyncState<any>(null)
  const [toast, setToast] = useState('')
  const [activeTab, setActiveTab] = useState<'parsed' | 'json' | 'fields' | 'report'>('parsed')
  const [activeKey, setActiveKey] = useState('')
  const [pageNum, setPageNum] = useState(1)
  const [refreshing, setRefreshing] = useState(false)

  const [folderTasks, setFolderTasks] = useState<any[]>([])
  const [folderLoading, setFolderLoading] = useState(false)
  const regionRefs = useRef<Record<string, HTMLElement>>({})

  const [editingKey, setEditingKey] = useState('')
  const [editText, setEditText] = useState('')
  const [editingTableKey, setEditingTableKey] = useState('')
  const [tableDraft, setTableDraft] = useState<string[][]>([['']])

  const latestFetchTokenRef = useRef(0)
  const taskIdRef = useRef(taskId)
  taskIdRef.current = taskId

  const routeFolder = searchParams?.get('folder') || ''
  const routeSubmissionId = searchParams?.get('submission_id') || ''
  const routeBatchId = searchParams?.get('batch_id') || ''

  const fileUrl = useMemo(() => getTaskFileUrl(taskId), [taskId])
  const taskFolderPath = useMemo(() => (task?.folder || inferFolderPath(task?.file_path || '')).trim(), [task])
  const taskBatchIdVal = useMemo(() => (task?.batch_id || '').trim(), [task])

  const materialContextKind = useMemo(() => {
    if (routeFolder || taskFolderPath) return 'folder'
    if (routeSubmissionId) return 'submission'
    if (routeBatchId || taskBatchIdVal) return 'batch'
    return ''
  }, [routeFolder, taskFolderPath, routeSubmissionId, routeBatchId, taskBatchIdVal])

  const materialContextValue = useMemo(() => {
    if (materialContextKind === 'folder') return routeFolder || taskFolderPath
    if (materialContextKind === 'submission') return routeSubmissionId
    if (materialContextKind === 'batch') return routeBatchId || taskBatchIdVal
    return ''
  }, [materialContextKind, routeFolder, taskFolderPath, routeSubmissionId, routeBatchId, taskBatchIdVal])

  const folderPath = useMemo(
    () => (materialContextKind && materialContextValue ? `${materialContextKind}:${materialContextValue}` : ''),
    [materialContextKind, materialContextValue]
  )
  const folderSourcePath = useMemo(
    () => (materialContextKind === 'folder' ? materialContextValue : ''),
    [materialContextKind, materialContextValue]
  )
  const folderLabel = useMemo(() => {
    if (materialContextKind === 'submission') return '同次提交材料'
    if (materialContextKind === 'batch') return '同批次材料'
    const normalized = folderSourcePath.replace(/\\/g, '/')
    return normalized.split('/').filter(Boolean).pop() || folderSourcePath
  }, [materialContextKind, folderSourcePath])

  const pages = useMemo(() => normalizePages(resultData?.pages), [resultData])
  const totalPages = useMemo(() => pages.length || 1, [pages])
  const isPdf = useMemo(() => String(task?.file_type || '').toLowerCase() === '.pdf', [task])
  const jsonText = useMemo(() => JSON.stringify(resultData, null, 2), [resultData])
  const modeLabel = useMemo(() => getModeLabel(task?.mode || ''), [task])
  const modeClass = useMemo(() => MODE_CLASS_MAP[task?.mode] || 'bg-gray-100 text-gray-700', [task])
  const currentPage = useMemo(() => pages[pageNum - 1] || { regions: [], lines: [] }, [pages, pageNum])

  // PLACEHOLDER_ACTIONS

  const showToast = useCallback((message: string) => {
    setToast(message)
    window.setTimeout(() => setToast((prev) => (prev === message ? '' : prev)), 1800)
  }, [])

  const formatTime = useCallback((value?: string) => (value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'), [])
  const statusLabel = useCallback((status?: string) => getStatusLabel(status || ''), [])
  const statusClass = useCallback((status?: string) => getStatusClass(status || ''), [])

  const applyTask = useCallback((data: any) => {
    const normalizedData = normalizeTaskDetail(data)
    setTask(normalizedData)
    const rd = normalizedData.result_data || { pages: [] }
    setResultData(rd)
    viewState.setSuccess(normalizedData)
    return normalizedData
  }, [viewState])

  const { polling, start: startPolling, stop: stopPolling } = useTaskPolling(
    async () => { const { data } = await getTask(taskIdRef.current); return data },
    (data: any) => { applyTask(data) }
  )

  const fetchTask = useCallback(async ({ silent = false } = {}) => {
    const fetchToken = ++latestFetchTokenRef.current
    const requestedTaskId = taskIdRef.current
    if (!silent || !task) viewState.setLoading()
    setRefreshing(true)
    stopPolling()
    try {
      const { data } = await getTask(requestedTaskId)
      if (fetchToken !== latestFetchTokenRef.current || String(requestedTaskId) !== String(taskIdRef.current)) return
      const normalizedData = applyTask(data)
      const p = normalizePages(normalizedData?.result_data?.pages)
      if (p.length) viewState.setSuccess(normalizedData)
      else viewState.setEmpty(normalizedData)
      if (!['done', 'failed', 'human_review'].includes(normalizedData?.status)) startPolling()
    } catch (requestError: any) {
      if (fetchToken !== latestFetchTokenRef.current || String(requestedTaskId) !== String(taskIdRef.current)) return
      const message = requestError?.response?.data?.detail || '结果加载失败。'
      if (task && silent) showToast(message)
      else viewState.setError(message)
    } finally {
      if (fetchToken === latestFetchTokenRef.current) setRefreshing(false)
    }
  }, [task, viewState, stopPolling, startPolling, applyTask, showToast])

  const loadFolderTasks = useCallback(async () => {
    if (!materialContextKind || !materialContextValue) { setFolderTasks([]); return }
    setFolderLoading(true)
    try {
      const { data } = await getTasks(
        1, 500,
        materialContextKind === 'folder' ? materialContextValue : '',
        materialContextKind === 'submission' ? materialContextValue : '',
        materialContextKind === 'batch' ? materialContextValue : ''
      )
      setFolderTasks((data.tasks || []).map((item: any) => normalizeTaskForDisplay(item)))
    } catch (_) { setFolderTasks([]) }
    finally { setFolderLoading(false) }
  }, [materialContextKind, materialContextValue])

  // PLACEHOLDER_EDIT

  const switchTask = useCallback((nextTaskId: string | number) => {
    if (String(nextTaskId) === String(taskId)) return
    const params = new URLSearchParams()
    if (materialContextKind === 'folder' && materialContextValue) params.set('folder', materialContextValue)
    else if (materialContextKind === 'submission' && materialContextValue) params.set('submission_id', materialContextValue)
    else if (materialContextKind === 'batch' && materialContextValue) params.set('batch_id', materialContextValue)
    const qs = params.toString()
    router.push(`/result/${nextTaskId}${qs ? `?${qs}` : ''}`)
  }, [taskId, materialContextKind, materialContextValue, router])

  const copyRegion = useCallback((item: any) => {
    navigator.clipboard.writeText(item?.content || '').then(() => showToast('已复制当前区域。'))
  }, [showToast])

  const copyAll = useCallback(() => {
    navigator.clipboard.writeText(task?.full_text || '').then(() => showToast('已复制全文。'))
  }, [task, showToast])

  const downloadTxt = useCallback(() => {
    const blob = new Blob([task?.full_text || ''], { type: 'text/plain;charset=utf-8' })
    const link = document.createElement('a')
    link.href = URL.createObjectURL(blob)
    link.download = `${task?.filename || 'result'}.txt`
    link.click()
  }, [task])

  const setRegionRef = useCallback((key: string, element: HTMLElement | null) => {
    if (element) regionRefs.current[key] = element
    else delete regionRefs.current[key]
  }, [])

  const startTextEdit = useCallback((item: any) => {
    setEditingTableKey('')
    setEditingKey(item._key)
    setEditText(item.content || '')
  }, [])

  const cancelTextEdit = useCallback(() => { setEditingKey(''); setEditText('') }, [])

  const cloneTableData = useCallback((tableData: any[]) =>
    Array.isArray(tableData) && tableData.length
      ? tableData.map((row: any) => (Array.isArray(row) && row.length ? [...row] : ['']))
      : [['']], [])

  const tableDataToText = useCallback((tableData: any[]) =>
    tableData.map((row: any) => row.map((cell: any) => String(cell || '')).join('\t').trim()).filter(Boolean).join('\n'), [])

  const startTableEdit = useCallback((item: any) => {
    setEditingKey('')
    setEditingTableKey(item._key)
    setTableDraft(cloneTableData(item.table_data))
  }, [cloneTableData])

  const cancelTableEdit = useCallback(() => { setEditingTableKey(''); setTableDraft([['']]) }, [])

  const saveTextEdit = useCallback(async (item: any) => {
    const p = normalizePages(resultData?.pages)
    const page = p[item._pageIdx]
    if (!page) return
    if (item._regionIdx !== undefined && page.regions?.[item._regionIdx]) {
      page.regions[item._regionIdx].content = editText
      delete page.regions[item._regionIdx].region_lines
    } else if (item._lineIdx !== undefined && page.lines?.[item._lineIdx]) {
      page.lines[item._lineIdx].text = editText
    }
    try {
      const { data } = await updateTask(taskId, { result_json: p })
      applyTask(data)
      showToast('文本已保存。')
      cancelTextEdit()
    } catch (_) { showToast('保存未完成，请稍后重试。') }
  }, [resultData, editText, taskId, applyTask, showToast, cancelTextEdit])

  const saveTableEdit = useCallback(async (item: any) => {
    const p = normalizePages(resultData?.pages)
    const page = p[item._pageIdx]
    if (!page?.regions?.[item._regionIdx]) return
    const region = page.regions[item._regionIdx]
    region.table_data = cloneTableData(tableDraft)
    region.content = tableDataToText(tableDraft)
    delete region.html
    try {
      const { data } = await updateTask(taskId, { result_json: p })
      applyTask(data)
      showToast('表格已保存。')
      cancelTableEdit()
    } catch (_) { showToast('保存未完成，请稍后重试。') }
  }, [resultData, tableDraft, taskId, applyTask, showToast, cancelTableEdit, cloneTableData, tableDataToText])

  useEffect(() => { fetchTask(); loadFolderTasks() }, [])
  useEffect(() => {
    setPageNum(1); setActiveKey(''); cancelTextEdit(); cancelTableEdit()
    fetchTask({ silent: true })
  }, [taskId])
  useEffect(() => { loadFolderTasks() }, [folderPath])

  return {
    task, resultData, viewState, loading: viewState.isLoading, error: viewState.error,
    toast, activeTab, setActiveTab, activeKey, setActiveKey, pageNum, setPageNum,
    folderTasks, folderLoading, regionRefs, editingKey, editText, setEditText,
    editingTableKey, tableDraft, setTableDraft, refreshing,
    fileUrl, folderPath, folderSourcePath, materialContextKind, materialContextValue,
    folderLabel, pages, totalPages, isPdf, jsonText, modeLabel, modeClass, currentPage, polling,
    formatTime, showToast, statusLabel, statusClass, switchTask,
    copyRegion, copyAll, downloadTxt, setRegionRef,
    startTextEdit, cancelTextEdit, startTableEdit, cancelTableEdit,
    cloneTableData, tableDataToText, saveTextEdit, saveTableEdit, fetchTask,
  }
}
