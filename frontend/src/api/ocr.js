import axios from 'axios'
import {
  controlPlaneApiBase,
  controlPlaneBackendUrl,
  requestDefaults,
} from './runtime.js'

const controlPlaneApi = axios.create({
  baseURL: controlPlaneApiBase('/ocr'),
  ...requestDefaults,
})

export const uploadFile = (file, mode, options = {}) => {
  const form = new FormData()
  form.append('file', file)
  if (options.relativePath) form.append('relative_path', options.relativePath)
  return controlPlaneApi.post('/upload', form, {
    params: {
      mode,
      ...(options.excelPath ? { excel_path: options.excelPath } : {}),
      ...(options.excelInit ? { excel_init: 1 } : {}),
      ...(options.outputDir ? { output_dir: options.outputDir } : {}),
      ...(options.batchId ? { batch_id: options.batchId } : {}),
    },
  })
}

export const scanFolder = (path) => controlPlaneApi.get('/scan-folder', { params: { path } })

export const uploadFromPath = (filePath, mode, options = {}) =>
  controlPlaneApi.post(
    '/upload-from-path',
    { file_path: filePath },
    {
      params: {
        mode,
        ...(options.excelPath ? { excel_path: options.excelPath } : {}),
        ...(options.excelInit ? { excel_init: 1 } : {}),
        ...(options.outputDir ? { output_dir: options.outputDir } : {}),
        ...(options.batchId ? { batch_id: options.batchId } : {}),
      }
    }
  )

export const getTasks = (page = 1, pageSize = 20, folder = '') =>
  controlPlaneApi.get('/tasks', { params: { page, page_size: pageSize, ...(folder ? { folder } : {}) } })

export const getFolders = () => controlPlaneApi.get('/tasks/folders')

export const searchTasks = (q, page = 1, pageSize = 20) =>
  controlPlaneApi.get('/tasks/search', { params: { q, page, page_size: pageSize } })

export const getTask = (id) => controlPlaneApi.get(`/tasks/${id}`)

export const getTasksProgress = (taskIds = []) => controlPlaneApi.post('/tasks/progress', { task_ids: taskIds })

export const updateTask = (id, payload) => controlPlaneApi.put(`/tasks/${id}`, payload)

export const resumeHumanReviewTask = (id, resumePayload = {}) =>
  controlPlaneApi.post(`/tasks/${id}/human-review/resume`, { resume_payload: resumePayload })

export const aiMergeExtractBatch = (batchId, payload = {}) =>
  controlPlaneApi.post(`/batches/${encodeURIComponent(batchId)}/ai-merge-extract`, payload)

export const getBatchEvaluationTruth = (batchId) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/evaluation-truth`)

export const putBatchEvaluationTruth = (batchId, payload = {}) =>
  controlPlaneApi.put(`/batches/${encodeURIComponent(batchId)}/evaluation-truth`, payload)

export const getBatchEvaluationMetrics = (batchId, { forceRefresh = false } = {}) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/evaluation-metrics`, {
    params: { force_refresh: forceRefresh },
  })

export const getBatchEvaluationReport = (batchId, { forceRefresh = false } = {}) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/evaluation-report`, {
    params: { force_refresh: forceRefresh },
  })

export const getBatchBoundaryAnalysis = (batchId, { forceRefresh = false } = {}) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/boundary-analysis`, {
    params: { force_refresh: forceRefresh },
  })

export const getBatchBoundaryTruth = (batchId) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/boundary-truth`)

export const putBatchBoundaryTruth = (batchId, payload = {}) =>
  controlPlaneApi.put(`/batches/${encodeURIComponent(batchId)}/boundary-truth`, payload)

export const askBatchQuestion = (batchId, payload = {}) =>
  controlPlaneApi.post(`/batches/${encodeURIComponent(batchId)}/qa`, payload)

export const getBatchQaHistory = (batchId, { page = 1, pageSize = 20 } = {}) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/qa/history`, {
    params: { page, page_size: pageSize },
  })

export const submitBatchQaFeedback = (batchId, qaId, payload = {}) =>
  controlPlaneApi.post(`/batches/${encodeURIComponent(batchId)}/qa/${qaId}/feedback`, payload)

export const getBatchQaMetrics = (batchId) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/qa/metrics`)

export const deleteTask = (id) => controlPlaneApi.delete(`/tasks/${id}`)

export const deleteTasksByFolder = (folder) =>
  controlPlaneApi.delete('/tasks/by-folder', { params: { folder } })

export const exportArchiveRecords = (params = {}) => {
  const qs = new URLSearchParams()
  if (params.folder) qs.set('folder', params.folder)
  if (params.batch_id) qs.set('batch_id', params.batch_id)
  const link = document.createElement('a')
  link.href = controlPlaneBackendUrl(`/api/ocr/archive-records/export?${qs.toString()}`)
  link.download = params.filename || 'archive_records.xlsx'
  document.body.appendChild(link)
  link.click()
  setTimeout(() => document.body.removeChild(link), 200)
}

export const getArchiveRecords = (params = {}) => controlPlaneApi.get('/archive-records', { params })

export const importArchiveFromExcel = (filePath, batchId = '') =>
  controlPlaneApi.post('/archive-records/import-excel', { file_path: filePath, batch_id: batchId })

export const deleteArchiveRecords = (params = {}) => controlPlaneApi.delete('/archive-records', { params })

export const ensureFolderBatch = (folder) => controlPlaneApi.post('/folders/ensure-batch', { folder })

export const getTaskFileUrl = (id) => controlPlaneBackendUrl(`/api/ocr/tasks/${id}/file`)

export const getTaskThumbnailUrl = (id) => controlPlaneBackendUrl(`/api/ocr/tasks/${id}/thumbnail`)

export const getTaskPageImageUrl = (id, pageNum) => controlPlaneBackendUrl(`/api/ocr/tasks/${id}/pages/${pageNum}/image`)

export const getTaskFields = (id) => controlPlaneApi.get(`/tasks/${id}/extract-fields`)

export const aiExtractFields = (id, options = {}) =>
  controlPlaneApi.post(`/tasks/${id}/ai-extract-fields`, {
    include_evidence: options.includeEvidence !== false,
    persist: !!options.persist,
  })
