import axios from 'axios'
import { controlPlaneApiBase, controlPlaneBackendUrl, requestDefaults } from './runtime'

const controlPlaneApi = axios.create({
  baseURL: controlPlaneApiBase('/ocr'),
  ...requestDefaults,
})

export type UploadOptions = {
  relativePath?: string
  excelPath?: string
  excelInit?: boolean
  outputDir?: string
  batchId?: string
}

export const uploadFile = (file: File, mode: string, options: UploadOptions = {}) => {
  const form = new FormData()
  form.append('file', file)
  if (options.relativePath) form.append('relative_path', options.relativePath)
  return controlPlaneApi.post('/upload', form, {
    timeout: 120000,
    params: {
      mode,
      ...(options.excelPath ? { excel_path: options.excelPath } : {}),
      ...(options.excelInit ? { excel_init: 1 } : {}),
      ...(options.outputDir ? { output_dir: options.outputDir } : {}),
      ...(options.batchId ? { batch_id: options.batchId } : {}),
    },
  })
}

export const scanFolder = (path: string) =>
  controlPlaneApi.get('/scan-folder', { params: { path }, timeout: 60000 })

export const uploadFromPath = (filePath: string, mode: string, options: UploadOptions = {}) =>
  controlPlaneApi.post(
    '/upload-from-path',
    { file_path: filePath },
    {
      timeout: 120000,
      params: {
        mode,
        ...(options.excelPath ? { excel_path: options.excelPath } : {}),
        ...(options.excelInit ? { excel_init: 1 } : {}),
        ...(options.outputDir ? { output_dir: options.outputDir } : {}),
        ...(options.batchId ? { batch_id: options.batchId } : {}),
      },
    }
  )

export const getTasks = (
  page = 1,
  pageSize = 20,
  folder = '',
  submissionId = '',
  batchId = ''
) =>
  controlPlaneApi.get('/tasks', {
    params: {
      page,
      page_size: pageSize,
      ...(folder ? { folder } : {}),
      ...(submissionId ? { submission_id: submissionId } : {}),
      ...(batchId ? { batch_id: batchId } : {}),
    },
  })

export const getFolders = () => controlPlaneApi.get('/tasks/folders')

export const getTaskSubmissions = () => controlPlaneApi.get('/tasks/submissions')

export const searchTasks = (q: string, page = 1, pageSize = 20) =>
  controlPlaneApi.get('/tasks/search', { params: { q, page, page_size: pageSize } })

export const getTask = (id: string | number) => controlPlaneApi.get(`/tasks/${id}`)

export const getTasksProgress = (taskIds: Array<string | number> = []) =>
  controlPlaneApi.post('/tasks/progress', { task_ids: taskIds })

export const updateTask = (id: string | number, payload: Record<string, unknown>) =>
  controlPlaneApi.put(`/tasks/${id}`, payload)

export const resumeHumanReviewTask = (
  id: string | number,
  resumePayload: Record<string, unknown> = {}
) =>
  controlPlaneApi.post(`/tasks/${id}/human-review/resume`, {
    resume_payload: resumePayload,
  })

export const aiMergeExtractBatch = (batchId: string, payload: Record<string, unknown> = {}) =>
  controlPlaneApi.post(`/batches/${encodeURIComponent(batchId)}/ai-merge-extract`, payload, {
    timeout: 300000,
  })

export const getBatchEvaluationTruth = (batchId: string) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/evaluation-truth`)

export const putBatchEvaluationTruth = (
  batchId: string,
  payload: Record<string, unknown> = {}
) =>
  controlPlaneApi.put(`/batches/${encodeURIComponent(batchId)}/evaluation-truth`, payload)

export const getBatchEvaluationMetrics = (
  batchId: string,
  { forceRefresh = false }: { forceRefresh?: boolean } = {}
) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/evaluation-metrics`, {
    params: { force_refresh: forceRefresh },
  })

export const getBatchEvaluationReport = (
  batchId: string,
  { forceRefresh = false }: { forceRefresh?: boolean } = {}
) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/evaluation-report`, {
    params: { force_refresh: forceRefresh },
  })

export const getBatchBoundaryAnalysis = (
  batchId: string,
  {
    forceRefresh = false,
    similarityThreshold = undefined,
  }: { forceRefresh?: boolean; similarityThreshold?: number } = {}
) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/boundary-analysis`, {
    params: {
      force_refresh: forceRefresh,
      ...(similarityThreshold === undefined
        ? {}
        : { similarity_threshold: similarityThreshold }),
    },
  })

export const getBatchBoundaryTruth = (batchId: string) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/boundary-truth`)

export const putBatchBoundaryTruth = (
  batchId: string,
  payload: Record<string, unknown> = {}
) =>
  controlPlaneApi.put(`/batches/${encodeURIComponent(batchId)}/boundary-truth`, payload)

export const askBatchQuestion = (batchId: string, payload: Record<string, unknown> = {}) =>
  controlPlaneApi.post(`/batches/${encodeURIComponent(batchId)}/qa`, payload, {
    timeout: 120000,
  })

export const getBatchQaHistory = (
  batchId: string,
  { page = 1, pageSize = 20 }: { page?: number; pageSize?: number } = {}
) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/qa/history`, {
    params: { page, page_size: pageSize },
  })

export const submitBatchQaFeedback = (
  batchId: string,
  qaId: string | number,
  payload: Record<string, unknown> = {}
) =>
  controlPlaneApi.post(
    `/batches/${encodeURIComponent(batchId)}/qa/${qaId}/feedback`,
    payload
  )

export const getBatchQaMetrics = (batchId: string) =>
  controlPlaneApi.get(`/batches/${encodeURIComponent(batchId)}/qa/metrics`)

export const deleteTask = (id: string | number) => controlPlaneApi.delete(`/tasks/${id}`)

export const deleteTasksByFolder = (folder: string) =>
  controlPlaneApi.delete('/tasks/by-folder', { params: { folder } })

export const deleteTasksBySubmission = (submissionId: string) =>
  controlPlaneApi.delete('/tasks/by-submission', { params: { submission_id: submissionId } })

export const exportArchiveRecords = (
  params: { folder?: string; batch_id?: string; filename?: string } = {}
) => {
  const qs = new URLSearchParams()
  if (params.folder) qs.set('folder', params.folder)
  if (params.batch_id) qs.set('batch_id', params.batch_id)
  if (typeof document === 'undefined') return
  const link = document.createElement('a')
  link.href = controlPlaneBackendUrl(`/api/ocr/archive-records/export?${qs.toString()}`)
  link.download = params.filename || 'archive_records.xlsx'
  document.body.appendChild(link)
  link.click()
  setTimeout(() => document.body.removeChild(link), 200)
}

export const getArchiveRecords = (params: Record<string, unknown> = {}) =>
  controlPlaneApi.get('/archive-records', { params })

export const importArchiveFromExcel = (filePath: string, batchId = '') =>
  controlPlaneApi.post('/archive-records/import-excel', {
    file_path: filePath,
    batch_id: batchId,
  })

export const deleteArchiveRecords = (params: Record<string, unknown> = {}) =>
  controlPlaneApi.delete('/archive-records', { params })

export const ensureFolderBatch = (folder: string) =>
  controlPlaneApi.post('/folders/ensure-batch', { folder })

export const getTaskFileUrl = (id: string | number) =>
  controlPlaneBackendUrl(`/api/ocr/tasks/${id}/file`)

export const getTaskThumbnailUrl = (id: string | number) =>
  controlPlaneBackendUrl(`/api/ocr/tasks/${id}/thumbnail`)

export const getTaskPageImageUrl = (id: string | number, pageNum: number) =>
  controlPlaneBackendUrl(`/api/ocr/tasks/${id}/pages/${pageNum}/image`)

export const getTaskRegionImageUrl = (
  id: string | number,
  pageNum: number,
  regionIndex: number
) =>
  controlPlaneBackendUrl(
    `/api/ocr/tasks/${id}/pages/${pageNum}/regions/${regionIndex}/image`
  )

export const getTaskFields = (id: string | number) =>
  controlPlaneApi.get(`/tasks/${id}/extract-fields`)

export const aiExtractFields = (
  id: string | number,
  options: { includeEvidence?: boolean; persist?: boolean } = {}
) =>
  controlPlaneApi.post(`/tasks/${id}/ai-extract-fields`, {
    include_evidence: options.includeEvidence !== false,
    persist: !!options.persist,
  }, { timeout: 120000 })
