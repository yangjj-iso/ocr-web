import { computed, ref } from 'vue'

import {
  approveUser,
  getAuthStatus,
  getPendingUsers,
  login as loginApi,
  logout as logoutApi,
  register as registerApi,
  rejectUser,
} from '../api/auth.js'

const authLoading = ref(false)
const authLoaded = ref(false)
const authError = ref('')
const auth = ref({
  enabled: false,
  authenticated: false,
  username: null,
  is_admin: false,
  user_status: null,
  default_username: null,
})

const pendingUsers = ref([])
const pendingLoading = ref(false)
const pendingError = ref('')

let inflightRefresh = null

async function refreshAuthStatus(force = false) {
  if (inflightRefresh && !force) return inflightRefresh
  inflightRefresh = (async () => {
    authLoading.value = true
    authError.value = ''
    try {
      const { data } = await getAuthStatus()
      auth.value = {
        enabled: Boolean(data?.enabled),
        authenticated: Boolean(data?.authenticated),
        username: data?.username || null,
        is_admin: Boolean(data?.is_admin),
        user_status: data?.user_status || null,
        default_username: data?.default_username || null,
      }
      authLoaded.value = true
      return auth.value
    } catch (error) {
      authError.value = error?.response?.data?.detail || '认证状态检查失败。'
      auth.value = {
        enabled: true,
        authenticated: false,
        username: null,
        is_admin: false,
        user_status: null,
        default_username: null,
      }
      authLoaded.value = true
      return auth.value
    } finally {
      authLoading.value = false
      inflightRefresh = null
    }
  })()
  return inflightRefresh
}

async function login(username, password) {
  const { data } = await loginApi(username, password)
  auth.value = {
    ...auth.value,
    enabled: true,
    authenticated: true,
    username: data?.username || username,
    is_admin: Boolean(data?.is_admin),
    user_status: data?.user_status || 'active',
  }
  authLoaded.value = true
  return auth.value
}

async function register(username, password) {
  const { data } = await registerApi(username, password)
  return data
}

async function logout() {
  try {
    await logoutApi()
  } finally {
    auth.value = {
      ...auth.value,
      authenticated: false,
      username: null,
      is_admin: false,
      user_status: null,
    }
  }
}

async function loadPendingUsers() {
  pendingLoading.value = true
  pendingError.value = ''
  try {
    const { data } = await getPendingUsers()
    pendingUsers.value = Array.isArray(data?.items) ? data.items : []
    return pendingUsers.value
  } catch (error) {
    pendingError.value = error?.response?.data?.detail || '待审核列表加载失败。'
    pendingUsers.value = []
    return []
  } finally {
    pendingLoading.value = false
  }
}

async function approvePendingUser(userId) {
  await approveUser(userId)
  await loadPendingUsers()
}

async function rejectPendingUser(userId) {
  await rejectUser(userId)
  await loadPendingUsers()
}

export function useAuthState() {
  return {
    auth,
    authLoading,
    authLoaded,
    authError,
    pendingUsers,
    pendingLoading,
    pendingError,
    isAuthEnabled: computed(() => Boolean(auth.value.enabled)),
    isAuthenticated: computed(() => Boolean(auth.value.authenticated)),
    isAdmin: computed(() => Boolean(auth.value.is_admin)),
    refreshAuthStatus,
    login,
    register,
    logout,
    loadPendingUsers,
    approvePendingUser,
    rejectPendingUser,
  }
}
