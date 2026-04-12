import axios from 'axios'

import { controlPlaneApiBase, requestDefaults } from './runtime.js'

const devDashboardApi = axios.create({
  baseURL: controlPlaneApiBase('/dev/dashboard'),
  ...requestDefaults,
})

function taskPath(taskId) {
  return `/tasks/${encodeURIComponent(String(taskId))}`
}

export const getDevDashboardSnapshot = (params = {}) => devDashboardApi.get('/snapshot', { params })
export const listDevDashboardTasks = (params = {}) => devDashboardApi.get('/tasks', { params })
export const getDevDashboardTask = (taskId) => devDashboardApi.get(taskPath(taskId))
export const retryDevDashboardTask = (taskId, payload = {}) => devDashboardApi.post(`${taskPath(taskId)}/retry`, payload)
export const getDevDashboardAuthStatus = () => devDashboardApi.get('/auth/status')
export const loginDevDashboard = (payload) => devDashboardApi.post('/auth/login', payload)
export const logoutDevDashboard = () => devDashboardApi.post('/auth/logout')
