import axios from 'axios'
import { aiApiBase, controlPlaneApiBase, requestDefaults } from './runtime.js'

const adminUsersApi = axios.create({ baseURL: controlPlaneApiBase('/admin'), ...requestDefaults })
const operatorSelfApi = axios.create({ baseURL: controlPlaneApiBase('/operator'), ...requestDefaults })
const adminApi = axios.create({ baseURL: aiApiBase('/admin'), ...requestDefaults })
const operatorApi = axios.create({ baseURL: aiApiBase('/operator'), ...requestDefaults })
const taskApi = axios.create({ baseURL: controlPlaneApiBase('/ocr'), ...requestDefaults })

function normalizeAssignedStatus(status = '') {
  const value = String(status || '').trim().toLowerCase()
  if (!value || value === 'uploaded' || value === 'pending') return 'pending'
  if (['queued', 'processing', 'worker_accepted', 'running', 'human_review'].includes(value)) return 'processing'
  if (['done', 'completed'].includes(value)) return 'done'
  if (value === 'failed') return 'failed'
  if (value === 'cancelled') return 'cancelled'
  return value
}

function aggregateAssignedStatus(statuses = []) {
  if (statuses.includes('pending')) return 'pending'
  if (statuses.includes('processing')) return 'processing'
  if (statuses.includes('failed')) return 'failed'
  if (statuses.length && statuses.every((status) => status === 'done')) return 'done'
  if (statuses.includes('cancelled')) return 'cancelled'
  return statuses[0] || 'pending'
}

function summarizeAssignedTasks(tasks = []) {
  const groups = new Map()

  for (const task of Array.isArray(tasks) ? tasks : []) {
    const batchId = String(task?.batch_id || task?.batchId || '').trim()
    const fallbackId = task?.id != null ? `task-${task.id}` : `task-${groups.size + 1}`
    const key = batchId || fallbackId
    const timestamp = task?.updated_at || task?.updatedAt || task?.created_at || task?.createdAt || ''

    if (!groups.has(key)) {
      groups.set(key, {
        id: key,
        batch_id: batchId || fallbackId,
        file_count: 0,
        note: '',
        created_at: timestamp,
        _statuses: [],
      })
    }

    const group = groups.get(key)
    group.file_count += 1
    group._statuses.push(normalizeAssignedStatus(task?.status))
    if (timestamp && (!group.created_at || new Date(timestamp).getTime() > new Date(group.created_at).getTime())) {
      group.created_at = timestamp
    }
  }

  return Array.from(groups.values())
    .map((group) => ({
      id: group.id,
      batch_id: group.batch_id,
      file_count: group.file_count,
      note: group.note,
      status: aggregateAssignedStatus(group._statuses),
      created_at: group.created_at,
    }))
    .sort((left, right) => new Date(right.created_at || 0).getTime() - new Date(left.created_at || 0).getTime())
}

// ── Users ──────────────────────────────────────────────────────────────────
export const listUsers = (params = {}) => adminUsersApi.get('/users', { params })
export const setUserRole = (userId, role, capabilities) => adminUsersApi.put(`/users/${userId}/role`, { role, capabilities: capabilities ?? null })
export const setDisplayName = (userId, display_name) => adminUsersApi.put(`/users/${userId}/display-name`, { display_name })

// ── Quotas ─────────────────────────────────────────────────────────────────
export const getUserQuota = (userId) => adminUsersApi.get(`/users/${userId}/quota`)
export const updateUserQuota = (userId, data) => adminUsersApi.put(`/users/${userId}/quota`, data)
export const resetUserQuota = (userId) => adminUsersApi.post(`/users/${userId}/quota/reset`)

// ── Assignments ────────────────────────────────────────────────────────────
export const listAssignments = (params = {}) => adminApi.get('/assignments', { params })
export const createAssignment = (data) => adminApi.post('/assignments', data)
export const updateAssignmentStatus = (id, status) => adminApi.put(`/assignments/${id}/status`, { status })

// ── Operation logs ─────────────────────────────────────────────────────────
export const listOperationLogs = (params = {}) => adminApi.get('/operation-logs', { params })

// ── Operator self-service ──────────────────────────────────────────────────
export const getMyQuota = () => operatorSelfApi.get('/my-quota')
export const getMyAssignments = async (params = {}) => {
  const { data } = await taskApi.get('/tasks/my-assigned', {
    params: {
      page: params.page || 1,
      page_size: params.page_size || 2000,
    },
  })
  const items = summarizeAssignedTasks(data?.tasks || [])
  const filteredItems = params.status
    ? items.filter((item) => String(item.status || '').toLowerCase() === String(params.status || '').toLowerCase())
    : items
  return { data: { items: filteredItems, total: filteredItems.length } }
}
export const consumeQuota = (data) => operatorSelfApi.post('/my-quota/consume', data)
