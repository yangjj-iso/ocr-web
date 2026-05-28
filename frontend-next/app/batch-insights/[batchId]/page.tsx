'use client'

import * as React from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { Loader2 } from 'lucide-react'

import {
  aiMergeExtractBatch,
  askBatchQuestion,
  getBatchBoundaryAnalysis,
  getBatchBoundaryTruth,
  getBatchEvaluationMetrics,
  getBatchEvaluationReport,
  getBatchEvaluationTruth,
  getBatchQaHistory,
  getBatchQaMetrics,
  getTask,
  putBatchBoundaryTruth,
  putBatchEvaluationTruth,
  submitBatchQaFeedback,
} from '@/api/ocr'
import {
  getAiAnswerSource,
  getAiAnswerSourceLabel,
  normalizeAiErrorMessage,
  rememberAiRuntimeState,
  rememberLatestBatchId,
} from '@/hooks/use-ai-capability-state'
import { buildMergedDocumentViews, buildSourcePageSummary } from '@/lib/merge-document-display'

const ARCHIVE_FIELDS = ['档号', '文号', '责任者', '题名', '日期', '页数', '密级', '备注']
const ALLOWED_TABS = new Set(['overview', 'truth', 'metrics', 'qa'])

function pct(value?: number | null) {
  return `${(Number(value || 0) * 100).toFixed(1)}%`
}

function formatTime(value?: string | null) {
  if (!value) return '-'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString()
}

function emptyFields() {
  return Object.fromEntries(ARCHIVE_FIELDS.map((f) => [f, '']))
}

function resolveTab(value: any) {
  const v = String(Array.isArray(value) ? value[0] : value || '').trim()
  return ALLOWED_TABS.has(v) ? v : 'overview'
}

function formatBoundarySystemLabel(d: any) {
  if (d?.should_merge) return '系统建议：合并'
  if (d?.is_ambiguous) return '系统建议：人工确认'
  return '系统建议：切分'
}

function formatFeedbackBiasText(value: number) {
  if (!value) return '无历史偏移'
  const prefix = value > 0 ? '+' : ''
  return `反馈偏移 ${prefix}${value.toFixed(2)}`
}

function buildFeedbackSummary(details: any) {
  const payload = details && typeof details === 'object' ? details : {}
  const parts: string[] = []
  if (payload.family_page_gap) {
    const i = payload.family_page_gap
    parts.push(`${i.family} / gap=${i.page_gap} / same=${i.same_count}/${i.same_count + i.different_count}`)
  }
  if (payload.family_transition_gap) {
    const i = payload.family_transition_gap
    parts.push(`${i.left_family}->${i.right_family} / gap=${i.page_gap} / same=${i.same_count}/${i.same_count + i.different_count}`)
  }
  if (payload.page_gap) {
    const i = payload.page_gap
    parts.push(`gap=${i.page_gap} / same=${i.same_count}/${i.same_count + i.different_count}`)
  }
  return parts.join('；') || '暂无历史样本影响'
}

function qaSupportText(level?: string) {
  if (level === 'supported') return '证据充分'
  if (level === 'partial') return '部分支持'
  return '证据不足'
}

export default function BatchInsightsPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const batchId = String(params?.batchId || '')

  const [activeTab, setActiveTabState] = React.useState(() => resolveTab(searchParams?.get('tab')))
  const [loading, setLoading] = React.useState(true)
  const [refreshing, setRefreshing] = React.useState(false)
  const [error, setError] = React.useState('')
  const [boundarySaveMessage, setBoundarySaveMessage] = React.useState('')
  const [truthSaveMessage, setTruthSaveMessage] = React.useState('')
  const [boundaryWarning, setBoundaryWarning] = React.useState('')
  const [truthWarning, setTruthWarning] = React.useState('')
  const [metricsWarning, setMetricsWarning] = React.useState('')
  const [savingBoundaryTruth, setSavingBoundaryTruth] = React.useState(false)
  const [savingTruth, setSavingTruth] = React.useState(false)
  const [verifyingTaskId, setVerifyingTaskId] = React.useState<number | null>(null)

  const [mergeResult, setMergeResult] = React.useState<any>(null)
  const [boundaryAnalysis, setBoundaryAnalysis] = React.useState<any>({ sequences: [], decisions: [], groups: [], task_to_group: {}, summary: { sequence_count: 0, decision_count: 0, group_count: 0 }, truth_updated_at: null })
  const [boundaryTruth, setBoundaryTruth] = React.useState<any>({ tasks: [], feedback: [], truth_updated_at: null })
  const [metrics, setMetrics] = React.useState<any>(null)
  const [aiReport, setAiReport] = React.useState<any>(null)
  const [loadingAiReport, setLoadingAiReport] = React.useState(false)
  const [aiReportError, setAiReportError] = React.useState('')

  const [qaInput, setQaInput] = React.useState('')
  const [qaSubmitting, setQaSubmitting] = React.useState(false)
  const [qaError, setQaError] = React.useState('')
  const [qaHistoryLoading, setQaHistoryLoading] = React.useState(false)
  const [qaHistory, setQaHistory] = React.useState<any[]>([])
  const [qaMetrics, setQaMetrics] = React.useState<any>(null)
  const [qaFeedbackSubmittingId, setQaFeedbackSubmittingId] = React.useState<any>(null)
  const [qaFeedbackTargetId, setQaFeedbackTargetId] = React.useState<any>(null)
  const [qaFeedbackReason, setQaFeedbackReason] = React.useState('')
  const [qaFeedbackComment, setQaFeedbackComment] = React.useState('')
  const [qaCorrectedAnswer, setQaCorrectedAnswer] = React.useState('')

  const [taskTruthDraft, setTaskTruthDraft] = React.useState<any[]>([])
  const [documentTruthDraft, setDocumentTruthDraft] = React.useState<any[]>([])

  const autoRefreshedRef = React.useRef(false)

  const mergedDocuments = React.useMemo(() => buildMergedDocumentViews(mergeResult), [mergeResult])
  const boundarySummary = React.useMemo(() => boundaryAnalysis?.summary || { sequence_count: 0, decision_count: 0, group_count: 0 }, [boundaryAnalysis])
  const boundaryTruthUpdatedAt = React.useMemo(() => boundaryTruth?.truth_updated_at || boundaryAnalysis?.truth_updated_at || null, [boundaryTruth, boundaryAnalysis])
  const operationalMetrics = React.useMemo(() => metrics?.operational_metrics || null, [metrics])
  const truthMetrics = React.useMemo(() => metrics?.truth_metrics || null, [metrics])

  const boundaryGroupDrafts = React.useMemo(() => {
    const groups = new Map<string, { docKey: string; filenames: string[]; taskIds: number[] }>()
    for (const item of taskTruthDraft) {
      const docKey = String(item.doc_key || item.predicted_group || '').trim()
      if (!docKey) continue
      if (!groups.has(docKey)) groups.set(docKey, { docKey, filenames: [], taskIds: [] })
      const t = groups.get(docKey)!
      t.filenames.push(item.filename)
      t.taskIds.push(Number(item.task_id))
    }
    return Array.from(groups.values())
      .sort((a, b) => (a.taskIds[0] || 0) - (b.taskIds[0] || 0))
      .map((g) => ({ ...g, sourceSummary: buildSourcePageSummary(g.filenames) }))
  }, [taskTruthDraft])

  const boundaryDecisionRows = React.useMemo(() => {
    const draftByTaskId = new Map(taskTruthDraft.map((item, idx) => [Number(item.task_id), { ...item, index: idx }]))
    return (boundaryAnalysis?.decisions || []).map((decision: any) => {
      const leftTaskId = Number(decision.left_task_id)
      const rightTaskId = Number(decision.right_task_id)
      const leftDraft = draftByTaskId.get(leftTaskId)
      const rightDraft = draftByTaskId.get(rightTaskId)
      if (!leftDraft || !rightDraft) return null
      const draftSame = String(leftDraft.doc_key || '') === String(rightDraft.doc_key || '')
      const feedbackBias = Number(decision?.signals?.feedback_bias || 0)
      return {
        key: `${leftTaskId}-${rightTaskId}`, leftTaskId, rightTaskId,
        leftFilename: leftDraft.filename, rightFilename: rightDraft.filename,
        leftLabel: `#${leftTaskId}`, rightLabel: `#${rightTaskId}`,
        leftDocKey: String(leftDraft.doc_key || '-'), rightDocKey: String(rightDraft.doc_key || '-'),
        reason: String(decision.reason || '无判定依据'),
        scoreText: Number(decision.same_document_score || 0).toFixed(2),
        systemLabel: formatBoundarySystemLabel(decision),
        systemClass: decision.should_merge ? 'text-emerald-700' : decision.is_ambiguous ? 'text-amber-700' : 'text-rose-700',
        draftLabel: draftSame ? '当前草稿：同组' : '当前草稿：已断开',
        draftClass: draftSame ? 'text-emerald-700' : 'text-amber-700',
        draftSame, feedbackBias,
        feedbackBiasText: formatFeedbackBiasText(feedbackBias),
        feedbackBiasClass: feedbackBias > 0 ? 'text-emerald-700' : feedbackBias < 0 ? 'text-rose-700' : 'text-muted-foreground',
        feedbackSummary: buildFeedbackSummary(decision?.signals?.feedback_details),
      }
    }).filter(Boolean)
  }, [taskTruthDraft, boundaryAnalysis])

  function setActiveTab(tab: string) {
    const next = resolveTab(tab)
    setActiveTabState(next)
    const url = new URL(window.location.href)
    if (next === 'overview') url.searchParams.delete('tab')
    else url.searchParams.set('tab', next)
    window.history.replaceState(null, '', url.toString())
  }

  function syncAiRuntime({ available, provider, error: err }: { available?: boolean; provider?: string; error?: any }) {
    if (!batchId) return
    rememberLatestBatchId(batchId)
    rememberAiRuntimeState({
      latestBatchId: batchId,
      ...(typeof available === 'boolean' ? { aiServiceAvailable: available } : {}),
      answerSource: provider ? getAiAnswerSource(provider) : undefined,
      lastError: err ? normalizeAiErrorMessage(err) : '',
    })
  }

  function buildPredictedTaskRows(taskDocKeyMap = new Map<number, string>()) {
    const rows: any[] = []
    const groups = (Array.isArray(boundaryAnalysis?.groups) && boundaryAnalysis.groups.length ? boundaryAnalysis.groups : mergeResult?.groups) || []
    for (const group of groups) {
      const taskIds = group.task_ids || []
      const names = group.filenames || []
      taskIds.forEach((taskId: any, index: number) => {
        rows.push({ task_id: taskId, filename: names[index] || `task-${taskId}`, predicted_group: group.group_id, doc_key: String(taskDocKeyMap.get(Number(taskId)) || group.group_id || '') })
      })
    }
    return rows.sort((a, b) => Number(a.task_id) - Number(b.task_id))
  }

  function syncDocumentDraftByTaskMap(draft: any[] = taskTruthDraft) {
    const requiredKeys = new Set(draft.map((i) => String(i.doc_key || '').trim()).filter(Boolean))
    const existingDocs = new Map(documentTruthDraft.map((d) => [String(d.doc_key || '').trim(), d]))
    const nextDocs = Array.from(requiredKeys).map((k) => existingDocs.get(k) || { doc_key: k, fields: emptyFields() })
    const preserved = documentTruthDraft.filter((d) => { const k = String(d.doc_key || '').trim(); if (!k || requiredKeys.has(k)) return false; return Object.values(d.fields || {}).some((v: any) => String(v || '').trim()) })
    setDocumentTruthDraft([...nextDocs, ...preserved])
  }

  function buildTruthTaskPayload() {
    return taskTruthDraft.map((i) => ({ task_id: Number(i.task_id), doc_key: String(i.doc_key || '').trim() })).filter((i) => i.doc_key)
  }

  function nextSplitDocKey(rightRow: any) {
    const occupied = new Set(taskTruthDraft.map((i) => String(i.doc_key || '').trim()).filter(Boolean))
    const preferred = String(rightRow?.predicted_group || '').trim()
    if (preferred && !occupied.has(preferred)) return preferred
    let candidate = `doc-${rightRow?.task_id || 'split'}`
    let idx = 1
    while (occupied.has(candidate)) { candidate = `doc-${rightRow?.task_id || 'split'}-${idx}`; idx++ }
    return candidate
  }

  function mergeBoundaryPair(leftTaskId: number, rightTaskId: number) {
    const rows = [...taskTruthDraft]
    const li = rows.findIndex((i) => Number(i.task_id) === leftTaskId)
    const ri = rows.findIndex((i) => Number(i.task_id) === rightTaskId)
    if (li < 0 || ri < 0 || ri <= li) return
    const leftKey = String(rows[li].doc_key || rows[li].predicted_group || '').trim()
    const rightKey = String(rows[ri].doc_key || rows[ri].predicted_group || '').trim()
    if (!leftKey || !rightKey || leftKey === rightKey) return
    for (let i = ri; i < rows.length; i++) { if (String(rows[i].doc_key || rows[i].predicted_group || '').trim() !== rightKey) break; rows[i] = { ...rows[i], doc_key: leftKey } }
    setTaskTruthDraft(rows)
    syncDocumentDraftByTaskMap(rows)
  }

  function splitBoundaryPair(leftTaskId: number, rightTaskId: number) {
    const rows = [...taskTruthDraft]
    const li = rows.findIndex((i) => Number(i.task_id) === leftTaskId)
    const ri = rows.findIndex((i) => Number(i.task_id) === rightTaskId)
    if (li < 0 || ri < 0 || ri <= li) return
    const leftKey = String(rows[li].doc_key || rows[li].predicted_group || '').trim()
    const rightKey = String(rows[ri].doc_key || rows[ri].predicted_group || '').trim()
    if (!leftKey || leftKey !== rightKey) return
    const newKey = nextSplitDocKey(rows[ri])
    for (let i = ri; i < rows.length; i++) { if (String(rows[i].doc_key || rows[i].predicted_group || '').trim() !== rightKey) break; rows[i] = { ...rows[i], doc_key: newKey } }
    setTaskTruthDraft(rows)
    syncDocumentDraftByTaskMap(rows)
  }

  async function loadQaHistoryFn() {
    if (!batchId) return
    setQaHistoryLoading(true)
    try {
      const { data } = await getBatchQaHistory(batchId, { page: 1, pageSize: 20 })
      if (typeof data === 'string' && /<!doctype html|<html/i.test(data)) throw { response: { data } }
      if (!Array.isArray(data?.items)) throw new Error('Invalid QA history payload.')
      setQaHistory(data.items || [])
      if (data.items?.length) syncAiRuntime({ available: true, provider: data.items[0].provider })
    } catch (e: any) { setQaError(normalizeAiErrorMessage(e, '问答历史暂时不可用，请稍后重试。')) }
    finally { setQaHistoryLoading(false) }
  }

  async function loadQaMetricsFn() {
    if (!batchId) return
    try {
      const { data } = await getBatchQaMetrics(batchId)
      if (typeof data === 'string' && /<!doctype html|<html/i.test(data)) throw { response: { data } }
      if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Invalid QA metrics payload.')
      setQaMetrics(data)
    } catch (e: any) { setQaError(normalizeAiErrorMessage(e, '问答统计暂时不可用，请稍后重试。')) }
  }

  async function loadAll(forceRefresh = false) {
    if (!batchId) { setError('缺少 batch_id。'); setLoading(false); return }
    if (forceRefresh) setRefreshing(true); else setLoading(true)
    setError(''); setBoundarySaveMessage(''); setTruthSaveMessage(''); setBoundaryWarning(''); setTruthWarning(''); setMetricsWarning(''); setAiReportError(''); setQaError('')
    if (!forceRefresh) { setQaHistory([]); setQaMetrics(null) }
    if (forceRefresh) setAiReport(null)

    try {
      const mergeRes = await aiMergeExtractBatch(batchId, { include_evidence: false, persist: false, force_refresh: forceRefresh })
      if (typeof mergeRes.data === 'string' && /<!doctype html|<html/i.test(mergeRes.data)) throw { response: { data: mergeRes.data } }
      if (!mergeRes.data?.batch_id) throw new Error('Invalid batch insights payload.')
      setMergeResult(mergeRes.data)
      syncAiRuntime({ available: true })
    } catch (e: any) {
      setError(normalizeAiErrorMessage(e, '批次智能辅助暂时不可用，请稍后重试。'))
      syncAiRuntime({ available: false, error: e })
      setLoading(false); setRefreshing(false); return
    }

    const [metricsRes, baRes, btRes, truthRes] = await Promise.allSettled([
      getBatchEvaluationMetrics(batchId, { forceRefresh }),
      getBatchBoundaryAnalysis(batchId, { forceRefresh }),
      getBatchBoundaryTruth(batchId),
      getBatchEvaluationTruth(batchId),
    ])

    let newMetrics: any = null
    if (metricsRes.status === 'fulfilled') {
      try { if (!metricsRes.value.data?.batch_id) throw new Error(); newMetrics = metricsRes.value.data }
      catch { setMetricsWarning('质量结果暂时不可用，可稍后重试。') }
    } else { setMetricsWarning(normalizeAiErrorMessage((metricsRes as any).reason, '质量结果暂时不可用，可稍后重试。')) }
    setMetrics(newMetrics)

    let baPayload: any = { sequences: [], decisions: [], groups: [], task_to_group: {}, summary: { sequence_count: 0, decision_count: 0, group_count: 0 }, truth_updated_at: null }
    let btPayload: any = { tasks: [], feedback: [], truth_updated_at: null }
    const bWarnings: string[] = []
    if (baRes.status === 'fulfilled') { try { if (!baRes.value.data?.batch_id) throw new Error(); baPayload = baRes.value.data } catch (e: any) { bWarnings.push(normalizeAiErrorMessage(e, '边界分析结果暂时不可用。')) } }
    else { bWarnings.push(normalizeAiErrorMessage((baRes as any).reason, '边界分析结果暂时不可用。')) }
    if (btRes.status === 'fulfilled') { try { if (!btRes.value.data?.batch_id) throw new Error(); btPayload = btRes.value.data } catch (e: any) { bWarnings.push(normalizeAiErrorMessage(e, '人工分组真值暂时不可用。')) } }
    else { bWarnings.push(normalizeAiErrorMessage((btRes as any).reason, '人工分组真值暂时不可用。')) }

    setBoundaryAnalysis(baPayload)
    setBoundaryTruth(btPayload)
    setBoundaryWarning(bWarnings.filter(Boolean).join(' '))

    // Build task truth draft from boundary data
    const truthTaskMap = new Map((btPayload.tasks || []).map((i: any) => [Number(i.task_id), i.doc_key]))
    const groups = (Array.isArray(baPayload?.groups) && baPayload.groups.length ? baPayload.groups : mergeResult?.groups) || []
    const rows: any[] = []
    for (const group of groups) { (group.task_ids || []).forEach((tid: any, idx: number) => { rows.push({ task_id: tid, filename: (group.filenames || [])[idx] || `task-${tid}`, predicted_group: group.group_id, doc_key: String(truthTaskMap.get(Number(tid)) || group.group_id || '') }) }) }
    rows.sort((a, b) => Number(a.task_id) - Number(b.task_id))
    setTaskTruthDraft(rows)

    // Apply truth data for document drafts
    if (truthRes.status === 'fulfilled') {
      try {
        const td = truthRes.value.data
        if (!td || typeof td !== 'object' || Array.isArray(td)) throw new Error()
        const docMap = new Map((td.documents || []).map((i: any) => [String(i.doc_key), { doc_key: String(i.doc_key), fields: { ...emptyFields(), ...(i.fields || {}) } }]))
        for (const row of rows) { const k = String(row.doc_key || '').trim(); if (k && !docMap.has(k)) docMap.set(k, { doc_key: k, fields: emptyFields() }) }
        setDocumentTruthDraft(Array.from(docMap.values()))
      } catch (e: any) { setDocumentTruthDraft([]); setTruthWarning(normalizeAiErrorMessage(e, '人工核对数据暂时不可用。')) }
    } else { setDocumentTruthDraft([]); setTruthWarning(normalizeAiErrorMessage((truthRes as any).reason, '人工核对数据暂时不可用。')) }

    try { await Promise.all([loadQaHistoryFn(), loadQaMetricsFn()]) } finally { setLoading(false); setRefreshing(false) }
  }

  async function openTask(taskId: any) {
    const id = Number(taskId)
    if (!Number.isFinite(id)) return
    setVerifyingTaskId(id)
    try {
      await getTask(id)
      router.push(`/result/${id}`)
    } catch (e: any) {
      if (Number(e?.response?.status) === 404) {
        setTruthSaveMessage('该材料记录已清理，正在刷新当前批次结果。')
        if (!refreshing && !autoRefreshedRef.current) { autoRefreshedRef.current = true; await loadAll(true) }
        return
      }
      setError(normalizeAiErrorMessage(e, '当前材料暂时无法打开，请稍后重试。'))
    } finally { setVerifyingTaskId(null) }
  }

  async function loadAiReportFn(forceRefresh = false) {
    if (!batchId) return
    setLoadingAiReport(true); setAiReportError('')
    try { const { data } = await getBatchEvaluationReport(batchId, { forceRefresh }); setAiReport(data); syncAiRuntime({ available: true }) }
    catch (e: any) { setAiReportError(normalizeAiErrorMessage(e, '智能诊断报告暂时不可用，请稍后重试。')); syncAiRuntime({ available: false, error: e }) }
    finally { setLoadingAiReport(false) }
  }

  async function saveBoundaryTruthFn() {
    if (!batchId) return
    const payload = buildTruthTaskPayload()
    if (!payload.length) { setError('请先为材料填写人工确认分组后再保存。'); return }
    setSavingBoundaryTruth(true); setBoundarySaveMessage(''); setError('')
    try { await putBatchBoundaryTruth(batchId, { tasks: payload }); await loadAll(true); syncAiRuntime({ available: true }); setBoundarySaveMessage('人工分组已生效，归并展示和边界分析已刷新。') }
    catch (e: any) { setError(normalizeAiErrorMessage(e, '人工分组保存未完成，请稍后重试。')) }
    finally { setSavingBoundaryTruth(false) }
  }

  async function saveTruthFn() {
    if (!batchId) return
    setSavingTruth(true); setTruthSaveMessage(''); setError('')
    try {
      const tasksPayload = buildTruthTaskPayload()
      const docsPayload = documentTruthDraft.map((i) => ({ doc_key: String(i.doc_key || '').trim(), fields: Object.fromEntries(ARCHIVE_FIELDS.map((f) => [f, String(i.fields?.[f] || '').trim()])) })).filter((i) => i.doc_key)
      if (!tasksPayload.length) throw new Error('请先确认分组归属，再保存人工校核基线。')
      await putBatchBoundaryTruth(batchId, { tasks: tasksPayload })
      await putBatchEvaluationTruth(batchId, { tasks: tasksPayload, documents: docsPayload })
      await loadAll(true); syncAiRuntime({ available: true }); setTruthSaveMessage('人工校核基线已保存，分组展示和质量评估已刷新。')
    } catch (e: any) { setError(normalizeAiErrorMessage(e, '人工核对保存未完成，请稍后重试。')) }
    finally { setSavingTruth(false) }
  }

  async function submitQaFn() {
    if (!batchId) return
    const question = qaInput.trim()
    if (!question) { setQaError('请输入问题后再发送。'); return }
    setQaSubmitting(true); setQaError('')
    try {
      const { data } = await askBatchQuestion(batchId, { question, top_k: 8, persist: true })
      setQaHistory((prev) => [data, ...prev.filter((i) => Number(i.qa_id) !== Number(data.qa_id))])
      syncAiRuntime({ available: data?.provider !== 'retrieval' ? true : undefined, provider: data?.provider })
      setQaInput('')
      await loadQaMetricsFn()
    } catch (e: any) { setQaError(normalizeAiErrorMessage(e, '问答请求失败，请稍后重试。')); syncAiRuntime({ available: false, error: e }) }
    finally { setQaSubmitting(false) }
  }

  async function submitHelpfulFeedback(item: any) {
    if (!batchId || !item?.qa_id) return
    setQaFeedbackSubmittingId(item.qa_id); setQaError('')
    try {
      const { data } = await submitBatchQaFeedback(batchId, item.qa_id, { rating: 'helpful' })
      setQaHistory((prev) => prev.map((r) => Number(r.qa_id) === Number(item.qa_id) ? { ...r, feedback: data.feedback } : r))
      await loadQaMetricsFn()
    } catch (e: any) { setQaError(normalizeAiErrorMessage(e, '反馈提交未完成，请稍后重试。')) }
    finally { setQaFeedbackSubmittingId(null) }
  }

  async function submitNotHelpfulFeedback(item: any) {
    if (!batchId || !item?.qa_id) return
    const reason = qaFeedbackReason.trim()
    if (!reason) { setQaError('无帮助反馈需要填写原因。'); return }
    setQaFeedbackSubmittingId(item.qa_id); setQaError('')
    try {
      const { data } = await submitBatchQaFeedback(batchId, item.qa_id, { rating: 'not_helpful', reason, comment: qaFeedbackComment.trim(), corrected_answer: qaCorrectedAnswer.trim(), corrected_evidence: [] })
      setQaHistory((prev) => prev.map((r) => Number(r.qa_id) === Number(item.qa_id) ? { ...r, feedback: data.feedback } : r))
      await loadQaMetricsFn()
      setQaFeedbackTargetId(null); setQaFeedbackReason(''); setQaFeedbackComment(''); setQaCorrectedAnswer('')
    } catch (e: any) { setQaError(normalizeAiErrorMessage(e, '反馈提交未完成，请稍后重试。')) }
    finally { setQaFeedbackSubmittingId(null) }
  }

  async function reloadWithRecompute() {
    autoRefreshedRef.current = false
    const hadReport = Boolean(aiReport)
    await loadAll(true)
    if (hadReport) await loadAiReportFn(true)
  }

  function resetTaskTruthToSuggested() {
    const next = taskTruthDraft.map((i) => ({ ...i, doc_key: String(i.predicted_group || '') }))
    setTaskTruthDraft(next)
    syncDocumentDraftByTaskMap(next)
  }

  React.useEffect(() => { loadAll(false) }, [])

  if (loading) return <div className="flex h-64 items-center justify-center text-sm text-muted-foreground"><Loader2 className="mr-2 h-5 w-5 animate-spin text-primary" />正在汇聚批次归并、质量评估与证据问答数据...</div>
  if (error && !mergeResult) return <div className="mx-auto max-w-7xl px-6 py-8"><div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-6 text-sm text-destructive">{error}</div></div>

  const tabBtn = (key: string, label: string) => (
    <button className={`rounded-lg px-3.5 py-2 text-xs font-medium transition ${activeTab === key ? 'bg-primary text-white shadow-glow-sm' : 'bg-muted text-muted-foreground hover:text-foreground'}`} onClick={() => setActiveTab(key)}>{label}</button>
  )

  return (
    <div className="mx-auto max-w-7xl px-6 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground">批次智能分析中心</h1>
          <p className="mt-1 text-xs text-muted-foreground">批次标识：<span className="font-mono">{batchId}</span> · 面向批量档案识别结果的智能归并、质量评估与证据追溯</p>
        </div>
        <div className="flex items-center gap-2">
          <button className="rounded-lg border border-border bg-white px-3 py-1.5 text-xs font-medium text-foreground transition hover:bg-muted" onClick={() => router.push('/')}>返回工作台</button>
          <button className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-white transition hover:bg-primary/90 disabled:opacity-50" disabled={refreshing || loading} onClick={reloadWithRecompute}>{refreshing ? '智能计算中...' : '刷新智能分析'}</button>
        </div>
      </div>

      <div className="mb-5 flex items-center gap-2">
        {tabBtn('overview', '批次总览')}
        {tabBtn('truth', '人工校核')}
        {tabBtn('metrics', '质量评估')}
        {tabBtn('qa', '证据问答')}
      </div>

      {(truthWarning || metricsWarning) && (
        <div className="mb-4 space-y-2">
          {truthWarning && <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-700">{truthWarning}</p>}
          {metricsWarning && <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-700">{metricsWarning}</p>}
        </div>
      )}
      {error && <p className="mb-4 rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-2 text-xs text-destructive">{error}</p>}

      {activeTab === 'overview' && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-border bg-white px-3 py-3 text-xs text-foreground">归并后文件数：{mergeResult?.summary?.documents_count || 0}</div>
            <div className="rounded-xl border border-border bg-white px-3 py-3 text-xs text-foreground">原始材料数：{mergeResult?.summary?.total_tasks || 0}</div>
            <div className="rounded-xl border border-border bg-white px-3 py-3 text-xs text-foreground">推荐字段覆盖率：{pct(operationalMetrics?.field_fill_rate?.recommended)}</div>
            <div className="rounded-xl border border-border bg-white px-3 py-3 text-xs text-foreground">字段冲突率：{pct(operationalMetrics?.conflict_rate)}</div>
          </div>

          <div className="rounded-xl border border-border bg-white px-4 py-3">
            <h2 className="mb-2 text-sm font-semibold text-foreground">批次质量摘要</h2>
            <p className="mb-2 text-xs text-muted-foreground">平均同文档归并置信度：{pct(operationalMetrics?.avg_same_document_confidence)}，规则与智能协同一致率：{pct(operationalMetrics?.avg_rule_llm_agreement)}</p>
            {truthMetrics?.grouping ? (
              <p className="text-xs text-emerald-700">人工校核综合得分：{pct(truthMetrics.grouping.pairwise_f1)}，任务分配准确率：{pct(truthMetrics.grouping.task_assignment_accuracy)}</p>
            ) : (
              <p className="text-xs text-amber-600">当前尚未建立人工校核基线，请先在"人工校核"页签补充后再查看准确性评估。</p>
            )}
          </div>

          <div className="rounded-xl border border-border bg-white px-4 py-3">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-foreground">智能诊断与决策建议</h2>
              <div className="flex items-center space-x-2">
                <button className="rounded bg-muted px-2 py-1 text-[11px] text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:text-muted-foreground/70" disabled={loadingAiReport} onClick={() => loadAiReportFn(false)}>{loadingAiReport ? '生成中...' : '生成诊断'}</button>
                <button className="rounded bg-primary/10 px-2 py-1 text-[11px] text-primary hover:bg-primary/20 disabled:cursor-not-allowed disabled:text-primary/50" disabled={loadingAiReport} onClick={() => loadAiReportFn(true)}>重新生成</button>
              </div>
            </div>
            {aiReportError ? <p className="text-xs text-destructive">{aiReportError}</p> : aiReport ? (
              <div className="space-y-2 text-xs text-foreground">
                <p className="rounded bg-muted/50 px-3 py-2 leading-6">{aiReport.summary}</p>
                <p className="text-[11px] text-muted-foreground">生成时间：{formatTime(aiReport.generated_at)}</p>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-3">
                  <div className="rounded bg-emerald-50 px-3 py-2"><p className="mb-1 text-[11px] font-medium text-emerald-700">优势</p><ul className="space-y-1">{(aiReport.strengths || []).map((s: string, i: number) => <li key={i}>- {s}</li>)}</ul></div>
                  <div className="rounded bg-amber-50 px-3 py-2"><p className="mb-1 text-[11px] font-medium text-amber-700">风险</p><ul className="space-y-1">{(aiReport.risks || []).map((s: string, i: number) => <li key={i}>- {s}</li>)}</ul></div>
                  <div className="rounded bg-primary/10 px-3 py-2"><p className="mb-1 text-[11px] font-medium text-primary">建议</p><ul className="space-y-1">{(aiReport.recommendations || []).map((s: string, i: number) => <li key={i}>- {s}</li>)}</ul></div>
                </div>
              </div>
            ) : <p className="text-xs text-muted-foreground">点击"生成诊断"后，系统将结合归并质量、字段冲突与人工校核情况输出可解释建议。</p>}
          </div>

          <div className="rounded-xl border border-border bg-white px-4 py-3">
            <h2 className="mb-2 text-sm font-semibold text-foreground">归并文件明细</h2>
            <div className="space-y-2 text-xs">
              {mergedDocuments.map((doc: any) => (
                <div key={doc.key} className="rounded-lg bg-muted/50 px-3 py-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="font-medium text-foreground">{doc.displayName}（置信度 {pct(doc.sameDocumentConfidence)}）</p>
                      {doc.title && <p className="mt-1 truncate text-muted-foreground">题名建议：{doc.title}</p>}
                      <p className="mt-1 text-muted-foreground">{doc.sourceSummary} · 归并页数 {doc.mergedPageCount || doc.sourceCount}</p>
                    </div>
                    {doc.primaryTaskId && <button className="rounded bg-white px-2 py-1 text-[11px] text-primary hover:bg-primary/10" onClick={() => openTask(doc.primaryTaskId)}>{doc.sourceCount > 1 ? '查看首页' : '查看文件'}</button>}
                  </div>
                  <p className="mt-2 text-[11px] text-muted-foreground">{(doc.decisionReasons || []).join('；') || '-'}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {activeTab === 'truth' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-white px-4 py-3">
            <div className="mb-3 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <h2 className="mb-2 text-sm font-semibold text-foreground">文档归并校核</h2>
                <p className="text-xs text-muted-foreground">同一份原始文件请填写相同文档组编号。这里保存后会立即覆盖当前批次的归并展示、边界分析与后续字段抽取基线。</p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <button className="rounded bg-muted px-2 py-1 text-[11px] text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:text-muted-foreground/70" disabled={savingBoundaryTruth || !taskTruthDraft.length} onClick={resetTaskTruthToSuggested}>按系统建议回填</button>
                <button className="rounded bg-primary px-2 py-1 text-[11px] text-white hover:bg-primary/90 disabled:cursor-not-allowed disabled:bg-primary/50" disabled={savingBoundaryTruth || !taskTruthDraft.length} onClick={saveBoundaryTruthFn}>{savingBoundaryTruth ? '保存中...' : '保存分组并刷新展示'}</button>
              </div>
            </div>
            <div className="mb-3 grid grid-cols-2 gap-2 text-xs text-foreground md:grid-cols-4">
              <div className="rounded bg-muted/50 px-3 py-2">系统分组数：{boundarySummary.group_count || 0}</div>
              <div className="rounded bg-muted/50 px-3 py-2">人工分组数：{boundaryGroupDrafts.length}</div>
              <div className="rounded bg-muted/50 px-3 py-2">边界判定数：{boundarySummary.decision_count || 0}</div>
              <div className="rounded bg-muted/50 px-3 py-2">最近应用：{formatTime(boundaryTruthUpdatedAt)}</div>
            </div>
            {boundaryGroupDrafts.length > 0 && (
              <div className="mb-3 flex flex-wrap gap-2">
                {boundaryGroupDrafts.map((g) => <span key={g.docKey} className="rounded-full border border-border bg-muted/50 px-2 py-1 text-[11px] text-muted-foreground">{g.docKey} · {g.sourceSummary}</span>)}
              </div>
            )}
            {boundaryWarning && <p className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">{boundaryWarning}</p>}
            {boundarySaveMessage && <p className="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">{boundarySaveMessage}</p>}
            <div className="max-h-72 overflow-auto">
              <table className="w-full text-left text-xs">
                <thead className="sticky top-0 bg-muted/50 text-muted-foreground"><tr><th className="px-2 py-2">任务编号</th><th className="px-2 py-2">文件名称</th><th className="px-2 py-2">系统建议分组</th><th className="px-2 py-2">人工确认分组</th><th className="px-2 py-2">材料核验</th></tr></thead>
                <tbody>
                  {taskTruthDraft.map((item) => (
                    <tr key={item.task_id} className="border-t border-border/50">
                      <td className="px-2 py-2 text-muted-foreground">#{item.task_id}</td>
                      <td className="px-2 py-2 text-foreground">{item.filename}</td>
                      <td className="px-2 py-2 text-muted-foreground">{item.predicted_group}</td>
                      <td className="px-2 py-2">
                        <input type="text" value={item.doc_key} onChange={(e) => { const v = e.target.value; setTaskTruthDraft((prev) => prev.map((r) => Number(r.task_id) === Number(item.task_id) ? { ...r, doc_key: v } : r)) }} onBlur={() => syncDocumentDraftByTaskMap()} className="w-full rounded border border-border px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-primary/30" />
                        <p className={`mt-1 text-[11px] ${item.doc_key === item.predicted_group ? 'text-muted-foreground/70' : 'text-primary'}`}>{item.doc_key === item.predicted_group ? '沿用系统建议' : `已人工归入 ${item.doc_key}`}</p>
                      </td>
                      <td className="px-2 py-2"><button className="rounded bg-muted px-2 py-1 text-[11px] text-muted-foreground hover:bg-muted disabled:cursor-not-allowed disabled:text-muted-foreground/70" disabled={verifyingTaskId === Number(item.task_id)} onClick={() => openTask(item.task_id)}>{verifyingTaskId === Number(item.task_id) ? '打开中...' : '打开材料'}</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-white px-4 py-3">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div><h2 className="text-sm font-semibold text-foreground">相邻页边界判定</h2><p className="mt-1 text-xs text-muted-foreground">这里展示系统对每一对相邻页的合并/切分判断，以及历史人工样本对本次评分的影响。可以直接一键修正草稿分组。</p></div>
              <div className="rounded bg-muted/50 px-3 py-2 text-[11px] text-muted-foreground">共 {boundaryDecisionRows.length} 个边界</div>
            </div>
            {boundaryDecisionRows.length ? (
              <div className="max-h-[420px] overflow-auto">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-muted/50 text-muted-foreground"><tr><th className="px-2 py-2">边界</th><th className="px-2 py-2">系统判定</th><th className="px-2 py-2">当前草稿</th><th className="px-2 py-2">历史反馈偏移</th><th className="px-2 py-2">快捷修正</th></tr></thead>
                  <tbody>
                    {boundaryDecisionRows.map((d: any) => (
                      <tr key={d.key} className="border-t border-border/50 align-top">
                        <td className="px-2 py-2"><p className="font-medium text-foreground">{d.leftLabel} → {d.rightLabel}</p><p className="mt-1 text-[11px] text-muted-foreground">{d.leftFilename} / {d.rightFilename}</p><p className="mt-1 text-[11px] text-muted-foreground">{d.reason}</p></td>
                        <td className="px-2 py-2"><p className={`font-medium ${d.systemClass}`}>{d.systemLabel}</p><p className="mt-1 text-[11px] text-muted-foreground">same_doc_score：{d.scoreText}</p></td>
                        <td className="px-2 py-2"><p className={`font-medium ${d.draftClass}`}>{d.draftLabel}</p><p className="mt-1 text-[11px] text-muted-foreground">{d.leftDocKey} / {d.rightDocKey}</p></td>
                        <td className="px-2 py-2"><p className={`font-medium ${d.feedbackBiasClass}`}>{d.feedbackBiasText}</p><p className="mt-1 text-[11px] text-muted-foreground">{d.feedbackSummary}</p></td>
                        <td className="px-2 py-2"><div className="flex flex-wrap gap-2"><button className="rounded bg-emerald-100 px-2 py-1 text-[11px] text-emerald-700 hover:bg-emerald-200 disabled:cursor-not-allowed disabled:text-emerald-300" disabled={d.draftSame} onClick={() => mergeBoundaryPair(d.leftTaskId, d.rightTaskId)}>并入上一组</button><button className="rounded bg-amber-100 px-2 py-1 text-[11px] text-amber-700 hover:bg-amber-200 disabled:cursor-not-allowed disabled:text-amber-300" disabled={!d.draftSame} onClick={() => splitBoundaryPair(d.leftTaskId, d.rightTaskId)}>从这里断开</button></div></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <p className="text-xs text-muted-foreground">当前批次暂无可展示的相邻页边界判定。</p>}
          </div>

          <div className="rounded-xl border border-border bg-white px-4 py-3">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-foreground">档案要素校核</h2>
              <button className="rounded bg-muted px-2 py-1 text-[11px] text-foreground hover:bg-muted" onClick={() => setDocumentTruthDraft((prev) => [...prev, { doc_key: `doc-${prev.length + 1}`, fields: emptyFields() }])}>新增校核条目</button>
            </div>
            <p className="mb-3 text-xs text-muted-foreground">在上方先确认分页/归并，再按文档组维护权威档案字段。保存时会同步写入分组真值和字段真值，用于刷新质量评估、支撑模型优化和形成可追溯复核依据。</p>
            <div className="max-h-[420px] space-y-3 overflow-auto">
              {documentTruthDraft.map((doc) => (
                <div key={doc.doc_key} className="rounded-lg border border-border p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <input type="text" value={doc.doc_key} onChange={(e) => setDocumentTruthDraft((prev) => prev.map((d) => d.doc_key === doc.doc_key ? { ...d, doc_key: e.target.value } : d))} className="rounded border border-border px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-primary/30" placeholder="文档组编号" />
                    <button className="rounded bg-destructive/5 px-2 py-1 text-[11px] text-destructive hover:bg-destructive/10" onClick={() => setDocumentTruthDraft((prev) => prev.filter((d) => d.doc_key !== doc.doc_key))}>删除</button>
                  </div>
                  <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                    {ARCHIVE_FIELDS.map((field) => (
                      <label key={`${doc.doc_key}-${field}`} className="text-xs text-muted-foreground">
                        <span className="mb-1 block">{field}</span>
                        <input type="text" value={doc.fields?.[field] || ''} onChange={(e) => setDocumentTruthDraft((prev) => prev.map((d) => d.doc_key === doc.doc_key ? { ...d, fields: { ...d.fields, [field]: e.target.value } } : d))} className="w-full rounded border border-border px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-primary/30" />
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 flex items-center justify-end">
              <button className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-white hover:bg-primary/90 disabled:cursor-not-allowed disabled:bg-primary/50" disabled={savingTruth} onClick={saveTruthFn}>{savingTruth ? '保存中...' : '保存校核基线并刷新评估'}</button>
            </div>
            {truthSaveMessage && <p className="mt-2 text-xs text-emerald-600">{truthSaveMessage}</p>}
          </div>
        </div>
      )}

      {activeTab === 'metrics' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-white px-4 py-3">
            <h2 className="mb-2 text-sm font-semibold text-foreground">自动评估指标（无需人工校核）</h2>
            <div className="grid grid-cols-2 gap-2 text-xs text-foreground md:grid-cols-4">
              <div className="rounded bg-muted/50 px-2 py-2">规则填充率：{pct(operationalMetrics?.field_fill_rate?.rule)}</div>
              <div className="rounded bg-muted/50 px-2 py-2">智能填充率：{pct(operationalMetrics?.field_fill_rate?.llm)}</div>
              <div className="rounded bg-muted/50 px-2 py-2">推荐填充率：{pct(operationalMetrics?.field_fill_rate?.recommended)}</div>
              <div className="rounded bg-muted/50 px-2 py-2">冲突率：{pct(operationalMetrics?.conflict_rate)}</div>
            </div>
          </div>
          <div className="rounded-xl border border-border bg-white px-4 py-3">
            <h2 className="mb-2 text-sm font-semibold text-foreground">基于人工校核的准确性评估</h2>
            {!truthMetrics ? <p className="text-xs text-amber-600">暂无人工校核结果，请先在"人工校核"页签完成归并与字段校核。</p> : (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2 text-xs text-foreground md:grid-cols-4">
                  <div className="rounded bg-muted/50 px-2 py-2">分组准确率：{pct(truthMetrics.grouping?.pairwise_precision)}</div>
                  <div className="rounded bg-muted/50 px-2 py-2">分组召回率：{pct(truthMetrics.grouping?.pairwise_recall)}</div>
                  <div className="rounded bg-muted/50 px-2 py-2">分组综合分：{pct(truthMetrics.grouping?.pairwise_f1)}</div>
                  <div className="rounded bg-muted/50 px-2 py-2">任务分配准确率：{pct(truthMetrics.grouping?.task_assignment_accuracy)}</div>
                </div>
                {(metrics?.compare_targets || []).map((target: string) => (
                  <div key={target} className="rounded-lg border border-border p-3">
                    <p className="mb-2 text-xs font-semibold text-foreground">{target.toUpperCase()} 准确率</p>
                    <p className="mb-2 text-xs text-muted-foreground">总体准确率：{pct(truthMetrics.field_accuracy?.[target]?.overall_accuracy)}，样本数：{truthMetrics.field_accuracy?.[target]?.total || 0}</p>
                    <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground md:grid-cols-4">
                      {ARCHIVE_FIELDS.map((field) => <div key={`${target}-${field}`} className="rounded bg-muted/50 px-2 py-1.5">{field}：{pct(truthMetrics.field_accuracy?.[target]?.per_field_accuracy?.[field])}</div>)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'qa' && (
        <div className="space-y-4">
          <div className="rounded-xl border border-border bg-white px-4 py-3">
            <h2 className="mb-2 text-sm font-semibold text-foreground">批次知识问答与证据追溯</h2>
            <p className="mb-3 text-xs text-muted-foreground">准确优先：系统先检索批次证据，再生成回答并进行一致性校验，确保结论可追溯、可复核。</p>
            <div className="mb-3 grid grid-cols-2 gap-2 text-xs text-foreground md:grid-cols-4">
              <div className="rounded bg-muted/50 px-2 py-2">帮助率：{pct(qaMetrics?.helpful_rate)}</div>
              <div className="rounded bg-muted/50 px-2 py-2">低证据拒答率：{pct(qaMetrics?.insufficient_rate)}</div>
              <div className="rounded bg-muted/50 px-2 py-2">反馈总量：{qaMetrics?.feedback_count || 0}</div>
              <div className="rounded bg-muted/50 px-2 py-2">历史条数：{qaHistory.length}</div>
            </div>
            <div className="flex flex-col gap-2 md:flex-row md:items-center">
              <input type="text" value={qaInput} onChange={(e) => setQaInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitQaFn() } }} placeholder="例如：该批次中 2024 年相关文件主要涉及哪些事项？" className="flex-1 rounded border border-border px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-primary/30" />
              <button className="rounded-lg bg-primary px-3 py-2 text-xs font-medium text-white hover:bg-primary/90 disabled:cursor-not-allowed disabled:bg-primary/50" disabled={qaSubmitting} onClick={submitQaFn}>{qaSubmitting ? '回答中...' : '发起问答'}</button>
            </div>
            {qaError && <p className="mt-2 text-xs text-destructive">{qaError}</p>}
          </div>

          {qaHistoryLoading ? (
            <div className="rounded-xl border border-border bg-white px-4 py-5 text-sm text-muted-foreground">正在加载问答历史...</div>
          ) : !qaHistory.length ? (
            <div className="rounded-xl border border-border bg-white px-4 py-6 text-sm text-muted-foreground">暂无问答记录，发起问题后将展示答案、证据链路与反馈状态。</div>
          ) : null}

          {qaHistory.map((item) => {
            const isRetrieval = getAiAnswerSource(item?.provider) === 'retrieval'
            const isEditingNH = Number(qaFeedbackTargetId) === Number(item.qa_id)
            return (
              <div key={item.qa_id || `${item.generated_at}-${item.question}`} className="rounded-xl border border-border bg-white px-4 py-3">
                <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs font-medium text-foreground">Q：{item.question}</p>
                  <p className="text-[11px] text-muted-foreground">来源：{getAiAnswerSourceLabel(item.provider)} · {formatTime(item.generated_at)}</p>
                </div>
                <div className="mb-2 flex flex-wrap items-center gap-2 text-[11px]">
                  <span className={`rounded px-2 py-1 ${isRetrieval ? 'bg-amber-50 text-amber-700' : 'bg-emerald-50 text-emerald-700'}`}>{getAiAnswerSourceLabel(item.provider)}</span>
                  <span className="rounded bg-primary/10 px-2 py-1 text-primary">支持度：{qaSupportText(item.support_level)}</span>
                  <span className="rounded bg-muted px-2 py-1 text-muted-foreground">置信度：{Number(item.confidence || 0).toFixed(3)}</span>
                  {item.citations?.length > 0 && <span className="rounded bg-emerald-50 px-2 py-1 text-emerald-700">引证：{item.citations.map((c: any) => `#${c.evidence_index}`).join(', ')}</span>}
                </div>
                <p className="rounded bg-muted/50 px-3 py-2 text-sm leading-6 text-foreground">{item.answer}</p>
                <p className={`mt-2 text-xs ${isRetrieval ? 'text-amber-700' : 'text-emerald-700'}`}>{isRetrieval ? '当前回答依据证据检索结果给出，证据不足时会保持保守表述。' : '当前回答已结合智能服务生成，并经过证据一致性校验。'}</p>

                <div className="mt-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs font-medium text-foreground">质量反馈</p>
                    <div className="flex items-center gap-2">
                      <button className="rounded bg-emerald-100 px-2 py-1 text-[11px] text-emerald-700 hover:bg-emerald-200 disabled:cursor-not-allowed disabled:text-emerald-300" disabled={qaFeedbackSubmittingId === item.qa_id} onClick={() => submitHelpfulFeedback(item)}>有帮助</button>
                      <button className="rounded bg-amber-100 px-2 py-1 text-[11px] text-amber-700 hover:bg-amber-200 disabled:cursor-not-allowed disabled:text-amber-300" disabled={qaFeedbackSubmittingId === item.qa_id} onClick={() => { setQaFeedbackTargetId(item.qa_id); setQaFeedbackReason(item.feedback?.reason || ''); setQaFeedbackComment(item.feedback?.comment || ''); setQaCorrectedAnswer(item.feedback?.corrected_answer || '') }}>无帮助</button>
                    </div>
                  </div>
                  {item.feedback && <p className="mb-2 text-[11px] text-muted-foreground">已反馈：{item.feedback.rating === 'helpful' ? '有帮助' : '无帮助'} · {formatTime(item.feedback.updated_at || item.feedback.created_at)}</p>}
                  {isEditingNH && (
                    <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-3">
                      <label className="mb-2 block text-xs text-amber-900">原因（必填）<input type="text" value={qaFeedbackReason} onChange={(e) => setQaFeedbackReason(e.target.value)} className="mt-1 w-full rounded border border-amber-200 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-amber-400" placeholder="例如：证据不足、结论偏差、关键信息遗漏" /></label>
                      <label className="mb-2 block text-xs text-amber-900">备注（可选）<textarea value={qaFeedbackComment} onChange={(e) => setQaFeedbackComment(e.target.value)} rows={2} className="mt-1 w-full rounded border border-amber-200 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-amber-400" placeholder="补充你看到的问题" /></label>
                      <label className="mb-2 block text-xs text-amber-900">纠正答案（可选）<textarea value={qaCorrectedAnswer} onChange={(e) => setQaCorrectedAnswer(e.target.value)} rows={3} className="mt-1 w-full rounded border border-amber-200 bg-white px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-amber-400" placeholder="如果你有更准确结论，可以直接填写" /></label>
                      <div className="flex items-center justify-end gap-2">
                        <button className="rounded bg-white px-2 py-1 text-[11px] text-muted-foreground hover:bg-muted" onClick={() => { setQaFeedbackTargetId(null); setQaFeedbackReason(''); setQaFeedbackComment(''); setQaCorrectedAnswer('') }}>取消</button>
                        <button className="rounded bg-amber-600 px-2 py-1 text-[11px] text-white hover:bg-amber-700 disabled:cursor-not-allowed disabled:bg-amber-300" disabled={qaFeedbackSubmittingId === item.qa_id || !qaFeedbackReason.trim()} onClick={() => submitNotHelpfulFeedback(item)}>{qaFeedbackSubmittingId === item.qa_id ? '提交中...' : '提交无帮助反馈'}</button>
                      </div>
                    </div>
                  )}
                </div>

                <div className="mt-3">
                  <p className="mb-2 text-xs font-medium text-foreground">证据片段</p>
                  <div className="space-y-2">
                    {(item.evidence || []).map((ev: any, ei: number) => (
                      <div key={`${item.qa_id}-${ev.task_id}-${ei}`} className="rounded-lg border border-border px-3 py-2">
                        <div className="mb-1 flex items-center justify-between">
                          <p className="text-xs text-muted-foreground">#{ev.task_id} · {ev.filename}</p>
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] text-muted-foreground">score={Number(ev.score || 0).toFixed(3)}</span>
                            <button className="rounded bg-muted px-2 py-1 text-[11px] text-muted-foreground hover:bg-muted" onClick={() => openTask(ev.task_id)}>查看材料</button>
                          </div>
                        </div>
                        <p className="text-xs leading-5 text-foreground">{ev.snippet}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
