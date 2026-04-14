import axios from 'axios'
import { controlPlaneApiBase, requestDefaults } from './runtime.js'

const authApi = axios.create({
  baseURL: controlPlaneApiBase('/auth'),
  ...requestDefaults,
})

export const getAuthStatus = () => authApi.get('/me')

export const login = (username, password) => authApi.post('/login', { username, password })

export const register = (username, password, realName, requestedCapabilities, tenantId) =>
  authApi.post('/register', { username, password, real_name: realName, requested_capabilities: requestedCapabilities, tenant_id: tenantId || 'default' })

export const logout = () => authApi.post('/logout')

export const getPendingUsers = () => authApi.get('/pending-users')

export const approveUser = (userId) => authApi.post(`/users/${userId}/approve`)

export const rejectUser = (userId) => authApi.post(`/users/${userId}/reject`)

export const resetUserPassword = (userId, newPassword) =>
  authApi.post(`/users/${userId}/reset-password`, { new_password: newPassword })

export const deleteUser = (userId) => authApi.delete(`/users/${userId}`)

export const changePassword = (currentPassword, newPassword) =>
  authApi.post('/change-password', { current_password: currentPassword, new_password: newPassword })

export const updateDisplayName = (displayName) =>
  authApi.put('/me/display-name', { display_name: displayName })
