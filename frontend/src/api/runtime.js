function trimTrailingSlash(value = '') {
  return String(value || '').replace(/\/+$/, '')
}

const fallbackControlPlaneOrigin = trimTrailingSlash(
  import.meta.env.VITE_CONTROL_PLANE_API_BASE_URL ||
    import.meta.env.VITE_API_BASE_URL ||
    'http://localhost:8080'
)

const businessOrigin = trimTrailingSlash(
  import.meta.env.VITE_BUSINESS_API_BASE_URL || fallbackControlPlaneOrigin
)
const controlPlaneOrigin = trimTrailingSlash(
  import.meta.env.VITE_CONTROL_PLANE_API_BASE_URL || businessOrigin || fallbackControlPlaneOrigin
)
const aiOrigin = trimTrailingSlash(
  import.meta.env.VITE_AI_API_BASE_URL || controlPlaneOrigin
)
const businessFileOrigin = trimTrailingSlash(
  import.meta.env.VITE_BUSINESS_FILE_BASE_URL || businessOrigin
)
const controlPlaneFileOrigin = trimTrailingSlash(
  import.meta.env.VITE_CONTROL_PLANE_FILE_BASE_URL || controlPlaneOrigin || businessFileOrigin
)
const aiFileOrigin = trimTrailingSlash(import.meta.env.VITE_FILE_BASE_URL || import.meta.env.VITE_AI_FILE_BASE_URL || aiOrigin)

export const requestDefaults = {
  withCredentials: true,
}

function joinOrigin(origin, path) {
  if (!origin) return path
  if (!path.startsWith('/')) return `${origin}/${path}`
  return `${origin}${path}`
}

export function apiUrl(path) {
  return joinOrigin(aiOrigin || businessOrigin, path)
}

export function backendUrl(path) {
  return joinOrigin(aiFileOrigin, path)
}

export function apiBase(path) {
  return apiUrl(`/api${path}`)
}

export function businessApiUrl(path) {
  return joinOrigin(businessOrigin, path)
}

export function controlPlaneApiUrl(path) {
  return joinOrigin(controlPlaneOrigin || businessOrigin, path)
}

export function aiApiUrl(path) {
  return joinOrigin(aiOrigin, path)
}

export function businessBackendUrl(path) {
  return joinOrigin(businessFileOrigin, path)
}

export function controlPlaneBackendUrl(path) {
  return joinOrigin(controlPlaneFileOrigin, path)
}

export function aiBackendUrl(path) {
  return joinOrigin(aiFileOrigin, path)
}

export function businessApiBase(path) {
  return businessApiUrl(`/api${path}`)
}

export function controlPlaneApiBase(path) {
  return controlPlaneApiUrl(`/api${path}`)
}

export function aiApiBase(path) {
  return aiApiUrl(`/api${path}`)
}
