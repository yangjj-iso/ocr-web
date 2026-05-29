import axios from 'axios'
import { controlPlaneApiBase, requestDefaults } from './runtime'
import { attachErrorToast, attachCsrfToken } from './index'

const authApi = attachErrorToast(
  attachCsrfToken(
    axios.create({
      baseURL: controlPlaneApiBase('/auth'),
      ...requestDefaults,
    })
  )
)

export const getAuthStatus = () => authApi.get('/me')

export const login = (username: string, password: string) =>
  authApi.post('/login', { username, password })

export const register = (username: string, password: string) =>
  authApi.post('/register', { username, password })

export const logout = () => authApi.post('/logout')

export const getPendingUsers = () => authApi.get('/pending-users')

export const approveUser = (userId: string | number) =>
  authApi.post(`/users/${userId}/approve`)

export const rejectUser = (userId: string | number) =>
  authApi.post(`/users/${userId}/reject`)

export const getAllUsers = () => authApi.get('/users')

export const setUserAdmin = (userId: string | number, admin: boolean) =>
  authApi.post(`/users/${userId}/set-admin`, { admin })
