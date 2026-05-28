function trimTrailingSlash(value: string = '') {
  return String(value || '').replace(/\/+$/, '')
}

const env =
  typeof process !== 'undefined' && process.env
    ? process.env
    : ({} as Record<string, string | undefined>)

const browserOrigin =
  typeof window !== 'undefined' && window.location ? window.location.origin : ''

const fallbackControlPlaneOrigin = trimTrailingSlash(
  env.NEXT_PUBLIC_CONTROL_PLANE_API_BASE_URL ||
    env.NEXT_PUBLIC_API_BASE_URL ||
    browserOrigin ||
    ''
)

const businessOrigin = trimTrailingSlash(
  env.NEXT_PUBLIC_BUSINESS_API_BASE_URL || fallbackControlPlaneOrigin
)
const controlPlaneOrigin = trimTrailingSlash(
  env.NEXT_PUBLIC_CONTROL_PLANE_API_BASE_URL || businessOrigin || fallbackControlPlaneOrigin
)
const aiOrigin = trimTrailingSlash(env.NEXT_PUBLIC_AI_API_BASE_URL || controlPlaneOrigin)
const businessFileOrigin = trimTrailingSlash(
  env.NEXT_PUBLIC_BUSINESS_FILE_BASE_URL || businessOrigin
)
const controlPlaneFileOrigin = trimTrailingSlash(
  env.NEXT_PUBLIC_CONTROL_PLANE_FILE_BASE_URL || controlPlaneOrigin || businessFileOrigin
)
const aiFileOrigin = trimTrailingSlash(
  env.NEXT_PUBLIC_FILE_BASE_URL || env.NEXT_PUBLIC_AI_FILE_BASE_URL || aiOrigin
)

export const requestDefaults = {
  withCredentials: true,
  timeout: 10000,
}

function joinOrigin(origin: string, path: string) {
  if (!origin) return path
  if (!path.startsWith('/')) return `${origin}/${path}`
  return `${origin}${path}`
}

export function apiUrl(path: string) {
  return joinOrigin(aiOrigin || businessOrigin, path)
}

export function backendUrl(path: string) {
  return joinOrigin(aiFileOrigin, path)
}

export function apiBase(path: string) {
  return apiUrl(`/api${path}`)
}

export function businessApiUrl(path: string) {
  return joinOrigin(businessOrigin, path)
}

export function controlPlaneApiUrl(path: string) {
  return joinOrigin(controlPlaneOrigin || businessOrigin, path)
}

export function aiApiUrl(path: string) {
  return joinOrigin(aiOrigin, path)
}

export function businessBackendUrl(path: string) {
  return joinOrigin(businessFileOrigin, path)
}

export function controlPlaneBackendUrl(path: string) {
  return joinOrigin(controlPlaneFileOrigin, path)
}

export function aiBackendUrl(path: string) {
  return joinOrigin(aiFileOrigin, path)
}

export function businessApiBase(path: string) {
  return businessApiUrl(`/api${path}`)
}

export function controlPlaneApiBase(path: string) {
  return controlPlaneApiUrl(`/api${path}`)
}

export function aiApiBase(path: string) {
  return aiApiUrl(`/api${path}`)
}
