/**
 * Archive workflow compatibility API.
 * All workflow pages now talk to the Python /api/archive surface.
 */
import axios from 'axios'
import { aiApiBase, requestDefaults } from './runtime.js'

const aiApi = axios.create({ baseURL: aiApiBase('/archive'), ...requestDefaults })

// ── Batches ────────────────────────────────────────────────────────────────
export const listBatches = (params = {}) =>
  aiApi.get('/batches', { params })

export const createBatch = (data) =>
  aiApi.post('/batches', data)

export const getBatch = (batchId) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}`)

export const startBatchWorkflow = (batchId, policySnapshotId) =>
  aiApi.post(`/batches/${encodeURIComponent(batchId)}/start`, { policy_snapshot_id: policySnapshotId })

export const getBatchStatus = (batchId) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/status`)

// ── Review tasks ───────────────────────────────────────────────────────────
export const listReviewTasks = (params = {}) =>
  aiApi.get('/tasks', { params })

export const getReviewTask = (taskId) =>
  aiApi.get(`/tasks/${taskId}`)

export const getWorkflowEvents = (taskId) =>
  aiApi.get(`/tasks/${taskId}/workflow-events`)

export const submitReview = (taskId, payload) =>
  aiApi.post(`/tasks/${taskId}/submit`, payload)

export const assignTask = (data) =>
  aiApi.post('/tasks/assign', data)

// ── Archive records (final) ────────────────────────────────────────────────
export const listArchiveRecords = (params = {}) =>
  aiApi.get('/archive-records', { params })

export const getArchiveRecord = (recordId) =>
  aiApi.get(`/archive-records/${recordId}`)

export const searchArchiveRecords = (q, page = 1, pageSize = 20) =>
  aiApi.get('/archive-records', { params: { q, page, page_size: pageSize } })

// ── Doc units (draft docs inside workflow) ─────────────────────────────────
export const listDocUnits = (batchId) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/docs`)

export const getDocUnit = (batchId, docId) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/docs/${docId}`)

export const updateDocMetadata = (batchId, docId, fields) =>
  aiApi.patch(`/batches/${encodeURIComponent(batchId)}/docs/${docId}/metadata`, fields)

// ── Release / final confirmation ──────────────────────────────────────────
export const listPendingRelease = (params = {}) =>
  aiApi.get('/tasks', { params: { status: 'human_review', type: 'final_release', ...params } })

export const releaseBatch = (taskId, payload = {}) =>
  aiApi.post(`/tasks/${taskId}/submit`, { decision: 'approve', ...payload })

export const rejectRelease = (taskId, reason) =>
  aiApi.post(`/tasks/${taskId}/submit`, { decision: 'reject', reason })

// ── Rework ─────────────────────────────────────────────────────────────────
export const listReworkTasks = (params = {}) =>
  aiApi.get('/rework-tasks', { params })

export const createReworkTask = (data) =>
  aiApi.post('/rework-tasks', data)

export const getReworkTask = (taskId) =>
  aiApi.get(`/rework-tasks/${taskId}`)

export const acceptReworkTask = (taskId) =>
  aiApi.post(`/rework-tasks/${taskId}/accept`)

export const rejectReworkTask = (taskId, reason) =>
  aiApi.post(`/rework-tasks/${taskId}/reject`, { reason })

// ── Policy rules ───────────────────────────────────────────────────────────
export const listPolicySnapshots = () =>
  aiApi.get('/policy-snapshots')

export const getPolicySnapshot = (id) =>
  aiApi.get(`/policy-snapshots/${id}`)

export const createPolicySnapshot = (data) =>
  aiApi.post('/policy-snapshots', data)

export const updatePolicySnapshot = (id, data) =>
  aiApi.put(`/policy-snapshots/${id}`, data)

// ── Dashboard stats ────────────────────────────────────────────────────────
export const getArchiveDashboardStats = () =>
  aiApi.get('/dashboard/stats')

export const getMyAssignedTasks = (params = {}) =>
  aiApi.get('/tasks/my-assigned', { params })

// ── Audit logs ─────────────────────────────────────────────────────────────
export const listAuditLogs = (params = {}) =>
  aiApi.get('/audit-logs', { params })

// ── Batch files ────────────────────────────────────────────────────────────
export const listBatchFiles = (batchId) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/files`)

export const uploadBatchFiles = (batchId, formData) =>
  aiApi.post(`/batches/${encodeURIComponent(batchId)}/files`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })

// ── Archive downloads ──────────────────────────────────────────────────────
export const downloadArchivePdf = (recordId) =>
  aiApi.get(`/archive-records/${recordId}/pdf`, { responseType: 'blob' })

export const exportBatchFinalPdf = (batchId) =>
  aiApi.post(`/batches/${encodeURIComponent(batchId)}/export/final-pdf`)
