/**
 * Archive workflow compatibility API.
 * Archive records and release/rework routes are Java-first; workflow authoring surfaces keep Python compatibility.
 */
import axios from 'axios'
import { aiApiBase, controlPlaneApiBase, requestDefaults } from './runtime.js'

const aiApi = axios.create({ baseURL: aiApiBase('/archive'), ...requestDefaults })
const legacyOcrApi = axios.create({ baseURL: controlPlaneApiBase('/ocr'), ...requestDefaults })
const legacyAdminApi = axios.create({ baseURL: controlPlaneApiBase('/admin'), ...requestDefaults })
const archiveApi = axios.create({
  baseURL: import.meta.env.VITE_CONTROL_PLANE_API_BASE_URL ? controlPlaneApiBase('/archive') : '/api/archive-control',
  ...requestDefaults,
})

function isNotFound(error) {
  return Number(error?.response?.status || 0) === 404
}

function normalizeLegacyTaskItem(task = {}) {
  const status = String(task.status || '').toLowerCase()
  const type = status === 'human_review' ? 'metadata_review' : (task.type || task.task_type || 'metadata_review')
  return {
    ...task,
    id: task.id,
    batch_id: task.batch_id || '',
    type,
    created_at: task.created_at || task.updated_at || null,
  }
}

function normalizeLegacyTaskListPayload(data = {}) {
  const rawItems = Array.isArray(data?.items)
    ? data.items
    : Array.isArray(data?.tasks)
      ? data.tasks
      : Array.isArray(data)
        ? data
        : []
  const items = rawItems.map((task) => normalizeLegacyTaskItem(task))
  const total = typeof data?.total === 'number' ? data.total : items.length
  return { items, total }
}

function mapReviewStatusToLegacy(status) {
  const normalized = String(status || '').trim().toLowerCase()
  if (!normalized) return ''
  if (normalized === 'human_review') return 'processing'
  if (normalized === 'done') return 'done'
  if (normalized === 'failed') return 'failed'
  return normalized
}

function normalizeAuditLogItem(item = {}) {
  return {
    id: item.id,
    review_task_id: item.review_task_id || item.resource_id || '',
    batch_id: item.batch_id || item.detail?.batch_id || '',
    action: item.action || item.action_type || '',
    operator_name: item.operator_name || item.username || '',
    note: item.note || item.detail?.message || '',
    occurred_at: item.occurred_at || item.created_at || null,
    before_snapshot: item.before_snapshot || item.detail?.before || null,
    after_snapshot: item.after_snapshot || item.detail?.after || null,
    detail: item.detail,
  }
}

function unsupportedFeatureError(feature) {
  return new Error(`当前后端未启用 ${feature} 接口，请切换到包含 /api/archive 的服务实例。`)
}

async function listLegacyTasks(params = {}) {
  if (params.q) {
    const { data } = await legacyOcrApi.get('/tasks/search', {
      params: {
        q: params.q,
        page: params.page || 1,
        page_size: params.page_size || 20,
      },
    })
    return normalizeLegacyTaskListPayload(data)
  }

  const { data } = await legacyOcrApi.get('/tasks', {
    params: {
      page: params.page || 1,
      page_size: params.page_size || 20,
      status: mapReviewStatusToLegacy(params.status),
      batch_id: params.batch_id || undefined,
      folder: params.folder || undefined,
      submission_id: params.submission_id || undefined,
    },
  })
  return normalizeLegacyTaskListPayload(data)
}

function normalizeLegacyBatchListPayload(taskPayload = {}) {
  const groups = new Map()
  const items = Array.isArray(taskPayload?.items) ? taskPayload.items : []

  for (const task of items) {
    const batchId = String(task?.batch_id || '').trim()
    if (!batchId) continue
    const current = groups.get(batchId) || {
      id: batchId,
      batch_id: batchId,
      status: 'pending',
      task_count: 0,
      doc_count: 0,
      created_at: task?.created_at || task?.updated_at || null,
      updated_at: task?.updated_at || task?.created_at || null,
      workflow_stages: [],
    }
    current.task_count += 1
    current.doc_count += Number(task?.page_count || 0) > 0 ? 1 : 0
    const status = String(task?.status || '').toLowerCase()
    if (['failed'].includes(status)) current.status = 'failed'
    else if (['processing', 'running', 'human_review'].includes(status) && current.status !== 'failed') current.status = 'processing'
    else if (['done', 'completed'].includes(status) && !['failed', 'processing'].includes(current.status)) current.status = 'done'
    groups.set(batchId, current)
  }

  const batchItems = Array.from(groups.values()).sort(
    (a, b) => new Date(b.updated_at || 0).getTime() - new Date(a.updated_at || 0).getTime()
  )
  return { items: batchItems, total: batchItems.length }
}

function normalizeLegacyArchiveRecord(task = {}) {
  return {
    id: task.id,
    record_id: task.id,
    archive_no: String(task.id || ''),
    batch_id: task.batch_id || '',
    filename: task.filename || '',
    title: task.filename || task.title || '',
    responsible: task.responsible || '',
    doc_no: task.doc_no || '',
    date: task.date || '',
    preservation_period: task.preservation_period || '',
    page_count: task.page_count || 0,
    status: task.status || '',
    created_at: task.created_at || task.updated_at || null,
    updated_at: task.updated_at || task.created_at || null,
    pdf_url: '',
    doc_units: [],
    versions: [],
  }
}

function normalizeArchiveDocUnit(doc = {}) {
  const id = doc.doc_id || doc.docId || doc.id || ''
  const pageCount = Number(doc.page_count ?? doc.pageCount ?? doc.pages ?? 0) || 0
  const startPage = Number(doc.start_page ?? doc.startPage ?? 1) || 1
  const endPage = Number(doc.end_page ?? doc.endPage ?? (pageCount || startPage)) || (pageCount || startPage)
  return {
    ...doc,
    id,
    doc_id: id,
    title: doc.title || doc.metadata?.title || '',
    sort_index: doc.sort_index ?? doc.sortIndex ?? 1,
    start_page: startPage,
    end_page: endPage,
    page_count: pageCount || Math.max(0, endPage - startPage + 1),
    status: doc.status || 'archived',
    preview_url: doc.preview_url || doc.previewUrl || doc.pdf_url || doc.pdfUrl || '',
    pdf_url: doc.pdf_url || doc.pdfUrl || doc.preview_url || doc.previewUrl || '',
  }
}

function normalizeArchiveVersion(version = {}, index = 0) {
  return {
    ...version,
    id: version.id ?? version.version_no ?? version.versionNo ?? index + 1,
    version_no: version.version_no ?? version.versionNo ?? index + 1,
    version_type: version.version_type || version.versionType || 'archive',
    created_at: version.created_at || version.createdAt || null,
  }
}

function normalizeArchiveRecord(record = {}) {
  const id = record.record_id ?? record.recordId ?? record.id ?? null
  const rawDocUnits = Array.isArray(record.doc_units)
    ? record.doc_units
    : Array.isArray(record.docUnits)
      ? record.docUnits
      : Array.isArray(record.docs)
        ? record.docs
        : []
  const rawVersions = Array.isArray(record.versions)
    ? record.versions
    : Array.isArray(record.doc_versions)
      ? record.doc_versions
      : Array.isArray(record.docVersions)
        ? record.docVersions
        : []
  return {
    ...record,
    id,
    record_id: id,
    task_id: record.task_id ?? record.taskId ?? null,
    batch_id: record.batch_id ?? record.batchId ?? '',
    batch_folder: record.batch_folder ?? record.batchFolder ?? '',
    archive_no: record.archive_no ?? record.archiveNo ?? '',
    doc_no: record.doc_no ?? record.docNo ?? '',
    responsible: record.responsible || '',
    title: record.title || '',
    date: record.date || '',
    preservation_period: record.preservation_period ?? record.preservationPeriod ?? '',
    classification: record.classification || '',
    remarks: record.remarks || '',
    storage_path: record.storage_path ?? record.storagePath ?? '',
    page_count: Number(record.page_count ?? record.pageCount ?? record.pages ?? 0) || 0,
    status: record.status || 'archived',
    created_at: record.created_at || record.createdAt || null,
    updated_at: record.updated_at || record.updatedAt || null,
    pdf_url: record.pdf_url || record.pdfUrl || '',
    file_url: record.file_url || record.fileUrl || '',
    last_rework_status: record.last_rework_status || record.lastReworkStatus || '',
    doc_units: rawDocUnits.map((item) => normalizeArchiveDocUnit(item)),
    docs: rawDocUnits.map((item) => normalizeArchiveDocUnit(item)),
    versions: rawVersions.map((item, index) => normalizeArchiveVersion(item, index)),
  }
}

function normalizeArchiveRecordListPayload(data = {}) {
  const rawItems = Array.isArray(data?.items)
    ? data.items
    : Array.isArray(data?.records)
      ? data.records
      : Array.isArray(data)
        ? data
        : []
  const items = rawItems.map((record) => normalizeArchiveRecord(record))
  const total = typeof data?.total === 'number' ? data.total : items.length
  return { items, total }
}

// ── Batches ────────────────────────────────────────────────────────────────
export const listBatches = (params = {}) =>
  aiApi.get('/batches', { params }).catch(async (error) => {
    if (!isNotFound(error)) throw error
    const payload = await listLegacyTasks({
      page: params.page || 1,
      page_size: params.page_size || 500,
      q: params.q,
      status: params.status,
    })
    return { data: normalizeLegacyBatchListPayload(payload) }
  })

export const createBatch = (data) =>
  aiApi.post('/batches', data).catch((error) => {
    if (!isNotFound(error)) throw error
    throw unsupportedFeatureError('批次创建')
  })

export const getBatch = (batchId) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}`).catch(async (error) => {
    if (!isNotFound(error)) throw error
    const payload = await listLegacyTasks({ page: 1, page_size: 1000, batch_id: batchId })
    const data = normalizeLegacyBatchListPayload(payload)
    const batch = data.items.find((item) => String(item.batch_id) === String(batchId))
    if (!batch) throw unsupportedFeatureError('批次详情')
    return { data: batch }
  })

export const startBatchWorkflow = (batchId, policySnapshotId) =>
  aiApi.post(`/batches/${encodeURIComponent(batchId)}/start`, { policy_snapshot_id: policySnapshotId }).catch((error) => {
    if (!isNotFound(error)) throw error
    throw unsupportedFeatureError('批次工作流启动')
  })

export const getBatchStatus = (batchId) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/status`).catch(async (error) => {
    if (!isNotFound(error)) throw error
    const res = await getBatch(batchId)
    return { data: { batch_id: batchId, status: res.data?.status || 'pending' } }
  })

// ── Review tasks ───────────────────────────────────────────────────────────
export const listReviewTasks = (params = {}) =>
  aiApi.get('/tasks', { params }).catch(async (error) => {
    if (!isNotFound(error)) throw error
    const payload = await listLegacyTasks(params)
    return { data: payload }
  })

export const getReviewTask = (taskId) =>
  aiApi.get(`/tasks/${taskId}`).catch(async (error) => {
    if (!isNotFound(error)) throw error
    const { data } = await legacyOcrApi.get(`/tasks/${taskId}`)
    const task = normalizeLegacyTaskItem(data || {})
    return { data: { ...task, docs: [], doc_units: [], evidence: {} } }
  })

export const getWorkflowEvents = (taskId) =>
  aiApi.get(`/tasks/${taskId}/workflow-events`).catch((error) => {
    if (!isNotFound(error)) throw error
    return { data: { items: [], total: 0 } }
  })

export const submitReview = (taskId, payload) =>
  aiApi.post(`/tasks/${taskId}/submit`, payload).catch((error) => {
    if (!isNotFound(error)) throw error
    throw unsupportedFeatureError('审核提交流程')
  })

export const assignTask = (data) =>
  legacyOcrApi.post('/tasks/assign', {
    task_ids: Array.isArray(data?.task_ids)
      ? data.task_ids
      : data?.task_id != null
        ? [Number(data.task_id)]
        : [],
    assignee_username: String(data?.assignee_username || '').trim(),
  }).catch(async (error) => {
    if (!isNotFound(error)) throw error
    const taskIds = Array.isArray(data?.task_ids)
      ? data.task_ids
      : data?.task_id != null
        ? [Number(data.task_id)]
        : []
    const assigneeUsername = String(data?.assignee_username || '').trim()
    if (!taskIds.length || !assigneeUsername) throw unsupportedFeatureError('审核任务分配')
    const { data: response } = await aiApi.post('/tasks/assign', {
      task_ids: taskIds,
      assignee_username: assigneeUsername,
    })
    return { data: response }
  })

// ── Archive records (final) ────────────────────────────────────────────────
export const listArchiveRecords = (params = {}) =>
  archiveApi.get('/archive-records', { params }).then(({ data }) => ({ data: normalizeArchiveRecordListPayload(data) })).catch(async (error) => {
    if (!isNotFound(error)) throw error
    const payload = await listLegacyTasks({
      page: params.page || 1,
      page_size: params.page_size || 200,
      q: params.q,
      status: 'done',
      batch_id: params.batch_id || params.batchId,
      folder: params.folder,
    })
    const items = payload.items.map((task) => normalizeLegacyArchiveRecord(task))
    return { data: { items, total: items.length } }
  })

export const getArchiveRecord = (recordId) =>
  archiveApi.get(`/archive-records/${recordId}`).then(({ data }) => ({ data: normalizeArchiveRecord(data) })).catch(async (error) => {
    if (!isNotFound(error)) throw error
    const { data } = await legacyOcrApi.get(`/tasks/${recordId}`)
    return { data: normalizeLegacyArchiveRecord(data || {}) }
  })

export const searchArchiveRecords = (q, page = 1, pageSize = 20) =>
  listArchiveRecords({ q, page, page_size: pageSize })

// ── Doc units (draft docs inside workflow) ─────────────────────────────────
export const listDocUnits = (batchId) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/docs`).catch((error) => {
    if (!isNotFound(error)) throw error
    return { data: { items: [], total: 0 } }
  })

export const getDocUnit = (batchId, docId) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/docs/${docId}`).catch((error) => {
    if (!isNotFound(error)) throw error
    return { data: {} }
  })

export const updateDocMetadata = (batchId, docId, fields) =>
  aiApi.patch(`/batches/${encodeURIComponent(batchId)}/docs/${docId}/metadata`, fields).catch((error) => {
    if (!isNotFound(error)) throw error
    throw unsupportedFeatureError('文档元数据更新')
  })

// ── Release / final confirmation ──────────────────────────────────────────
export const listPendingRelease = (params = {}) =>
  aiApi.get('/tasks', { params: { status: 'human_review', type: 'final_release', ...params } }).catch(async (error) => {
    if (!isNotFound(error)) throw error
    const payload = await listLegacyTasks({
      ...params,
      status: 'human_review',
    })
    return { data: payload }
  })

export const releaseBatch = (taskId, payload = {}) =>
  legacyOcrApi.post(`/tasks/${taskId}/release-decision`, { decision: 'approve', ...payload }).catch((error) => {
    if (!isNotFound(error)) throw error
    return aiApi.post(`/tasks/${taskId}/submit`, { decision: 'approve', ...payload })
  })

export const rejectRelease = (taskId, reason, rework = null) =>
  legacyOcrApi.post(`/tasks/${taskId}/release-decision`, { decision: 'reject', reason, rework }).catch((error) => {
    if (!isNotFound(error)) throw error
    return aiApi.post(`/tasks/${taskId}/submit`, { decision: 'reject', reason, rework })
  })

// ── Rework ─────────────────────────────────────────────────────────────────
export const listReworkTasks = (params = {}) =>
  legacyOcrApi.get('/rework-tasks', { params }).catch((error) => {
    if (!isNotFound(error)) throw error
    return aiApi.get('/rework-tasks', { params })
  })

export const createReworkTask = (data) =>
  legacyOcrApi.post('/rework-tasks', data).catch((error) => {
    if (!isNotFound(error)) throw error
    return aiApi.post('/rework-tasks', data)
  })

export const getReworkTask = (taskId) =>
  legacyOcrApi.get(`/rework-tasks/${taskId}`).catch((error) => {
    if (!isNotFound(error)) throw error
    return aiApi.get(`/rework-tasks/${taskId}`)
  })

export const acceptReworkTask = (taskId) =>
  legacyOcrApi.post(`/rework-tasks/${taskId}/accept`).catch((error) => {
    if (!isNotFound(error)) throw error
    return aiApi.post(`/rework-tasks/${taskId}/accept`)
  })

export const rejectReworkTask = (taskId, reason) =>
  legacyOcrApi.post(`/rework-tasks/${taskId}/reject`, { reason }).catch((error) => {
    if (!isNotFound(error)) throw error
    return aiApi.post(`/rework-tasks/${taskId}/reject`, { reason })
  })

// ── Policy rules ───────────────────────────────────────────────────────────
export const listPolicySnapshots = () =>
  aiApi.get('/policy-snapshots').catch((error) => {
    if (!isNotFound(error)) throw error
    return { data: { items: [], total: 0 } }
  })

export const getPolicySnapshot = (id) =>
  aiApi.get(`/policy-snapshots/${id}`).catch((error) => {
    if (!isNotFound(error)) throw error
    return { data: null }
  })

export const createPolicySnapshot = (data) =>
  aiApi.post('/policy-snapshots', data).catch((error) => {
    if (!isNotFound(error)) throw error
    throw unsupportedFeatureError('策略快照创建')
  })

export const updatePolicySnapshot = (id, data) =>
  aiApi.put(`/policy-snapshots/${id}`, data).catch((error) => {
    if (!isNotFound(error)) throw error
    throw unsupportedFeatureError('策略快照更新')
  })

// ── Dashboard stats ────────────────────────────────────────────────────────
export const getArchiveDashboardStats = () =>
  aiApi.get('/dashboard/stats').catch(async (error) => {
    if (!isNotFound(error)) throw error
    const payload = await listLegacyTasks({ page: 1, page_size: 1000 })
    const items = payload.items
    const countByStatus = (statuses) => items.filter((task) => statuses.includes(String(task.status || '').toLowerCase())).length
    return {
      data: {
        processingTasks: countByStatus(['processing', 'running', 'human_review']),
        myPendingTasks: countByStatus(['pending', 'uploaded']),
        rejectedTasks: countByStatus(['failed']),
        pendingRelease: countByStatus(['human_review']),
        totalArchived: countByStatus(['done', 'completed']),
        recentArchived: (() => {
          const cutoff = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)
          return items.filter((task) => {
            if (!['done', 'completed'].includes(String(task.status || '').toLowerCase())) return false
            const ts = task.updated_at || task.created_at
            return ts ? new Date(ts) >= cutoff : false
          }).length
        })(),
      },
    }
  })

export const getMyAssignedTasks = (params = {}) =>
  legacyOcrApi.get('/tasks/my-assigned', {
    params: {
      page: params.page || 1,
      page_size: params.page_size || 20,
      status: mapReviewStatusToLegacy(params.status),
    },
  }).then(({ data }) => ({ data: normalizeLegacyTaskListPayload(data) })).catch(async (error) => {
    if (!isNotFound(error)) throw error
    return aiApi.get('/tasks/my-assigned', { params })
  })

// ── Audit logs ─────────────────────────────────────────────────────────────
export const listAuditLogs = (params = {}) =>
  legacyAdminApi.get('/operation-logs', {
    params: {
      action_type: params.action || undefined,
      limit: params.page_size || 20,
      offset: Math.max(0, ((params.page || 1) - 1) * (params.page_size || 20)),
    },
  }).then(({ data }) => {
    const rawItems = Array.isArray(data?.items) ? data.items : []
    const items = rawItems
      .filter((item) => {
        const keyword = String(params.q || '').trim().toLowerCase()
        if (!keyword) return true
        const haystack = [
          item?.resource_id,
          item?.username,
          item?.action_type,
          item?.detail?.batch_id,
          item?.detail?.message,
        ]
          .filter(Boolean)
          .join(' ')
          .toLowerCase()
        return haystack.includes(keyword)
      })
      .map((item) => normalizeAuditLogItem(item))
    return {
      data: {
        items,
        total: typeof data?.total === 'number' ? data.total : items.length,
      },
    }
  }).catch(async (error) => {
    if (!isNotFound(error)) throw error
    return aiApi.get('/audit-logs', { params })
  })

// ── Batch files ────────────────────────────────────────────────────────────
export const listBatchFiles = (batchId) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/files`).catch(async (error) => {
    if (!isNotFound(error)) throw error
    const payload = await listLegacyTasks({ page: 1, page_size: 1000, batch_id: batchId })
    const items = payload.items.map((task) => ({
      id: task.id,
      name: task.filename || `task_${task.id}`,
      size: task.file_size || 0,
      created_at: task.created_at || task.updated_at || null,
      task_id: task.id,
    }))
    return { data: { items, total: items.length } }
  })

export const uploadBatchFiles = (batchId, formData) =>
  aiApi.post(`/batches/${encodeURIComponent(batchId)}/files`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }).catch((error) => {
    if (!isNotFound(error)) throw error
    throw unsupportedFeatureError('批次文件上传')
  })

// ── Archive downloads ──────────────────────────────────────────────────────
export const downloadArchivePdf = (recordId) =>
  archiveApi.get(`/archive-records/${recordId}/pdf`, { responseType: 'blob' }).catch(async (error) => {
    if (!isNotFound(error)) throw error
    return legacyOcrApi.get(`/tasks/${recordId}/file`, { responseType: 'blob' })
  })

export const exportBatchFinalPdf = (batchId) =>
  aiApi.post(`/batches/${encodeURIComponent(batchId)}/export/final-pdf`).catch((error) => {
    if (!isNotFound(error)) throw error
    throw unsupportedFeatureError('终审 PDF 导出')
  })
