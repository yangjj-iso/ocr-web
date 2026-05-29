import axios, { type AxiosError, type AxiosInstance } from 'axios'
import { toast } from 'sonner'

const CSRF_COOKIE_NAME = 'XSRF-TOKEN'
const CSRF_HEADER_NAME = 'X-XSRF-TOKEN'

/**
 * 从 document.cookie 中读取指定 cookie 值
 */
function getCookie(name: string): string | undefined {
  if (typeof document === 'undefined') return undefined
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : undefined
}

/**
 * 为 axios 实例注册 CSRF token 请求拦截器。
 * 自动从 cookie 读取 XSRF-TOKEN 并附加到请求头。
 */
export function attachCsrfToken(instance: AxiosInstance): AxiosInstance {
  instance.interceptors.request.use((config) => {
    if (typeof window === 'undefined') return config
    const token = getCookie(CSRF_COOKIE_NAME)
    if (token) {
      config.headers[CSRF_HEADER_NAME] = token
    }
    return config
  })
  return instance
}

/**
 * 为 axios 实例注册全局错误 toast 拦截器。
 * 仅在浏览器环境下弹出 toast，SSR 环境静默跳过。
 */
export function attachErrorToast(instance: AxiosInstance): AxiosInstance {
  instance.interceptors.response.use(undefined, (error: AxiosError) => {
    if (typeof window === 'undefined') return Promise.reject(error)

    const status = error.response?.status
    const data = error.response?.data as Record<string, unknown> | undefined

    // 提取后端返回的错误消息
    const serverMessage =
      (data?.message as string) || (data?.detail as string) || (data?.error as string) || ''

    if (status === 401) {
      toast.error('登录已过期，请重新登录')
    } else if (status === 403) {
      toast.error(serverMessage || '没有权限执行此操作')
    } else if (status === 404) {
      // 404 通常不需要全局 toast，由页面自行处理
    } else if (status === 422) {
      toast.error(serverMessage || '请求参数有误')
    } else if (status && status >= 500) {
      toast.error(serverMessage || '服务器内部错误，请稍后重试')
    } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
      toast.error('请求超时，请检查网络后重试')
    } else if (!error.response) {
      toast.error('网络连接失败，请检查网络')
    }

    return Promise.reject(error)
  })
  return instance
}

/**
 * 创建带有 CSRF + 错误 toast 的 axios 实例
 */
export function createApiClient(baseURL: string, options: Record<string, unknown> = {}) {
  const instance = axios.create({ baseURL, ...options })
  attachCsrfToken(instance)
  attachErrorToast(instance)
  return instance
}
