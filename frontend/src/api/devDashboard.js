import axios from 'axios'
import { controlPlaneApiBase, requestDefaults } from './runtime.js'

const devDashboardApi = axios.create({
  baseURL: controlPlaneApiBase('/dev/dashboard'),
  ...requestDefaults,
})

export const getDevDashboardSession = () => devDashboardApi.get('/me')

export const loginDevDashboard = (username, password) =>
  devDashboardApi.post('/login', { username, password })

export const logoutDevDashboard = () => devDashboardApi.post('/logout')

export const getDevDashboardMetrics = () => devDashboardApi.get('/metrics')
