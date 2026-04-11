import axios from 'axios'
import { aiApiBase, requestDefaults } from './runtime.js'

const adminApi = axios.create({ baseURL: aiApiBase('/admin'), ...requestDefaults })
const operatorApi = axios.create({ baseURL: aiApiBase('/operator'), ...requestDefaults })

// ── Users ──────────────────────────────────────────────────────────────────
export const listUsers = (params = {}) => adminApi.get('/users', { params })
export const setUserRole = (userId, role) => adminApi.put(`/users/${userId}/role`, { role })
export const setDisplayName = (userId, display_name) => adminApi.put(`/users/${userId}/display-name`, { display_name })

// ── Quotas ─────────────────────────────────────────────────────────────────
export const getUserQuota = (userId) => adminApi.get(`/users/${userId}/quota`)
export const updateUserQuota = (userId, data) => adminApi.put(`/users/${userId}/quota`, data)
export const resetUserQuota = (userId) => adminApi.post(`/users/${userId}/quota/reset`)

// ── Assignments ────────────────────────────────────────────────────────────
export const listAssignments = (params = {}) => adminApi.get('/assignments', { params })
export const createAssignment = (data) => adminApi.post('/assignments', data)
export const updateAssignmentStatus = (id, status) => adminApi.put(`/assignments/${id}/status`, { status })

// ── Operation logs ─────────────────────────────────────────────────────────
export const listOperationLogs = (params = {}) => adminApi.get('/operation-logs', { params })

// ── Operator self-service ──────────────────────────────────────────────────
export const getMyQuota = () => operatorApi.get('/my-quota')
export const getMyAssignments = (params = {}) => operatorApi.get('/my-assignments', { params })
export const consumeQuota = (data) => operatorApi.post('/my-quota/consume', data)
