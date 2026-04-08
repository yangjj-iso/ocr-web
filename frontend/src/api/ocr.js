import axios from 'axios'
import {
  aiApiBase,
  aiBackendUrl,
  businessApiBase,
  businessBackendUrl,
  requestDefaults,
} from './runtime.js'

const aiApi = axios.create({
  baseURL: aiApiBase('/ocr'),
  ...requestDefaults,
})

const businessApi = axios.create({
  baseURL: businessApiBase('/ocr'),
  ...requestDefaults,
})

export const uploadFile = (file, mode, options = {}) => {
  const form = new FormData()
  form.append('file', file)
  if (options.relativePath) form.append('relative_path', options.relativePath)
  return aiApi.post('/upload', form, {
    params: {
      mode,
      ...(options.excelPath ? { excel_path: options.excelPath } : {}),
      ...(options.excelInit ? { excel_init: 1 } : {}),
      ...(options.outputDir ? { output_dir: options.outputDir } : {}),
      ...(options.batchId ? { batch_id: options.batchId } : {}),
    },
  })
}

export const scanFolder = (path) => businessApi.get('/scan-folder', { params: { path } })

export const uploadFromPath = (filePath, mode, options = {}) =>
  aiApi.post(
    '/upload-from-path',
    { file_path: filePath },
    {
      params: {
        mode,
        ...(options.excelPath ? { excel_path: options.excelPath } : {}),
        ...(options.excelInit ? { excel_init: 1 } : {}),
        ...(options.outputDir ? { output_dir: options.outputDir } : {}),
        ...(options.batchId ? { batch_id: options.batchId } : {}),
      },
    }
  )

export const getTasks = (page = 1, pageSize = 20, folder = '') =>
  aiApi.get('/tasks', { params: { page, page_size: pageSize, ...(folder ? { folder } : {}) } })

export const getFolders = () => aiApi.get('/tasks/folders')

export const searchTasks = (q, page = 1, pageSize = 20) =>
  aiApi.get('/tasks/search', { params: { q, page, page_size: pageSize } })

export const getTask = (id) => aiApi.get(`/tasks/${id}`)

export const getTasksProgress = (taskIds = []) => aiApi.post('/tasks/progress', { task_ids: taskIds })

export const updateTask = (id, payload) => aiApi.put(`/tasks/${id}`, payload)

export const aiMergeExtractBatch = (batchId, payload = {}) =>
  aiApi.post(`/batches/${encodeURIComponent(batchId)}/ai-merge-extract`, payload)

export const getBatchEvaluationTruth = (batchId) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/evaluation-truth`)

export const putBatchEvaluationTruth = (batchId, payload = {}) =>
  aiApi.put(`/batches/${encodeURIComponent(batchId)}/evaluation-truth`, payload)

export const getBatchEvaluationMetrics = (batchId, { forceRefresh = false } = {}) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/evaluation-metrics`, {
    params: { force_refresh: forceRefresh },
  })

export const getBatchEvaluationReport = (batchId, { forceRefresh = false } = {}) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/evaluation-report`, {
    params: { force_refresh: forceRefresh },
  })

export const getBatchBoundaryAnalysis = (batchId, { forceRefresh = false } = {}) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/boundary-analysis`, {
    params: { force_refresh: forceRefresh },
  })

export const getBatchBoundaryTruth = (batchId) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/boundary-truth`)

export const putBatchBoundaryTruth = (batchId, payload = {}) =>
  aiApi.put(`/batches/${encodeURIComponent(batchId)}/boundary-truth`, payload)

export const askBatchQuestion = (batchId, payload = {}) =>
  aiApi.post(`/batches/${encodeURIComponent(batchId)}/qa`, payload)

export const getBatchQaHistory = (batchId, { page = 1, pageSize = 20 } = {}) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/qa/history`, {
    params: { page, page_size: pageSize },
  })

export const submitBatchQaFeedback = (batchId, qaId, payload = {}) =>
  aiApi.post(`/batches/${encodeURIComponent(batchId)}/qa/${qaId}/feedback`, payload)

export const getBatchQaMetrics = (batchId) =>
  aiApi.get(`/batches/${encodeURIComponent(batchId)}/qa/metrics`)

export const deleteTask = (id) => aiApi.delete(`/tasks/${id}`)

export const deleteTasksByFolder = (folder) =>
  aiApi.delete('/tasks/by-folder', { params: { folder } })

export const exportArchiveRecords = (params = {}) => {
  const qs = new URLSearchParams()
  if (params.folder) qs.set('folder', params.folder)
  if (params.batch_id) qs.set('batch_id', params.batch_id)
  const link = document.createElement('a')
  link.href = businessBackendUrl(`/api/ocr/archive-records/export?${qs.toString()}`)
  link.download = params.filename || 'archive_records.xlsx'
  document.body.appendChild(link)
  link.click()
  setTimeout(() => document.body.removeChild(link), 200)
}

export const getArchiveRecords = (params = {}) => businessApi.get('/archive-records', { params })

export const importArchiveFromExcel = (filePath, batchId = '') =>
  businessApi.post('/archive-records/import-excel', { file_path: filePath, batch_id: batchId })

export const deleteArchiveRecords = (params = {}) => businessApi.delete('/archive-records', { params })

export const ensureFolderBatch = (folder) => businessApi.post('/folders/ensure-batch', { folder })

export const getTaskFileUrl = (id) => aiBackendUrl(`/api/ocr/tasks/${id}/file`)

export const getTaskThumbnailUrl = (id) => aiBackendUrl(`/api/ocr/tasks/${id}/thumbnail`)

export const getTaskPageImageUrl = (id, pageNum) => aiBackendUrl(`/api/ocr/tasks/${id}/pages/${pageNum}/image`)

export const getTaskFields = (id) => aiApi.get(`/tasks/${id}/extract-fields`)

export const aiExtractFields = (id, options = {}) =>
  aiApi.post(`/tasks/${id}/ai-extract-fields`, {
    include_evidence: options.includeEvidence !== false,
    persist: !!options.persist,
  })
