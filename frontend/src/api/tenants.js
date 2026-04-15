import axios from 'axios'
import { controlPlaneApiBase, requestDefaults } from './runtime.js'

const tenantsApi = axios.create({ baseURL: controlPlaneApiBase('/admin/tenants'), ...requestDefaults })
const publicTenantsApi = axios.create({ baseURL: controlPlaneApiBase('/tenants'), ...requestDefaults })

export const listPublicTenants = () => publicTenantsApi.get('')

export const listTenants = () => tenantsApi.get('')

export const createTenant = (data) => tenantsApi.post('', data)

export const getTenant = (tenantId) => tenantsApi.get(`/${tenantId}`)

export const updateTenant = (tenantId, data) => tenantsApi.patch(`/${tenantId}`, data)

export const assignUserToTenant = (tenantId, userId) =>
  tenantsApi.post(`/${tenantId}/assign-user`, { user_id: userId })
