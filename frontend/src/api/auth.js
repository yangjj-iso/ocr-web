import axios from 'axios'
import { businessApiBase, requestDefaults } from './runtime.js'

const authApi = axios.create({
  baseURL: businessApiBase('/auth'),
  ...requestDefaults,
})

export const getAuthStatus = () => authApi.get('/me')

export const login = (username, password) => authApi.post('/login', { username, password })

export const register = (username, password) => authApi.post('/register', { username, password })

export const logout = () => authApi.post('/logout')

export const getPendingUsers = () => authApi.get('/pending-users')

export const approveUser = (userId) => authApi.post(`/users/${userId}/approve`)

export const rejectUser = (userId) => authApi.post(`/users/${userId}/reject`)
