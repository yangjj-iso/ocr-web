'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import {
  approveUser,
  getAuthStatus,
  getPendingUsers,
  login as loginApi,
  logout as logoutApi,
  register as registerApi,
  rejectUser,
} from '@/api/auth'

export type AuthState = {
  enabled: boolean
  authenticated: boolean
  username: string | null
  is_admin: boolean
  user_status: string | null
  default_username: string | null
}

const initialAuth: AuthState = {
  enabled: false,
  authenticated: false,
  username: null,
  is_admin: false,
  user_status: null,
  default_username: null,
}

type Listener = () => void

const listeners = new Set<Listener>()
let auth: AuthState = { ...initialAuth }
let authLoaded = false
let authLoading = false
let authError = ''
let pendingUsers: any[] = []
let pendingLoading = false
let pendingError = ''
let inflight: Promise<AuthState> | null = null

function emit() {
  listeners.forEach((l) => l())
}

async function refreshAuthStatus(force = false): Promise<AuthState> {
  if (inflight && !force) return inflight
  inflight = (async () => {
    authLoading = true
    authError = ''
    emit()
    try {
      const { data } = await getAuthStatus()
      auth = {
        enabled: Boolean(data?.enabled),
        authenticated: Boolean(data?.authenticated),
        username: data?.username || null,
        is_admin: Boolean(data?.is_admin),
        user_status: data?.user_status || null,
        default_username: data?.default_username || null,
      }
      authLoaded = true
      return auth
    } catch (error: any) {
      authError = error?.response?.data?.detail || '认证状态检查失败。'
      auth = {
        enabled: true,
        authenticated: false,
        username: null,
        is_admin: false,
        user_status: null,
        default_username: null,
      }
      authLoaded = true
      return auth
    } finally {
      authLoading = false
      inflight = null
      emit()
    }
  })()
  return inflight
}

async function login(username: string, password: string) {
  const { data } = await loginApi(username, password)
  auth = {
    ...auth,
    enabled: true,
    authenticated: true,
    username: data?.username || username,
    is_admin: Boolean(data?.is_admin),
    user_status: data?.user_status || 'active',
  }
  authLoaded = true
  emit()
  return auth
}

async function register(username: string, password: string) {
  const { data } = await registerApi(username, password)
  return data
}

async function logout() {
  try {
    await logoutApi()
  } finally {
    auth = {
      ...auth,
      authenticated: false,
      username: null,
      is_admin: false,
      user_status: null,
    }
    emit()
  }
}

async function loadPendingUsers() {
  pendingLoading = true
  pendingError = ''
  emit()
  try {
    const { data } = await getPendingUsers()
    pendingUsers = Array.isArray(data?.items) ? data.items : []
    return pendingUsers
  } catch (error: any) {
    pendingError = error?.response?.data?.detail || '待审核列表加载失败。'
    pendingUsers = []
    return []
  } finally {
    pendingLoading = false
    emit()
  }
}

async function approvePendingUser(userId: string | number) {
  await approveUser(userId)
  await loadPendingUsers()
}

async function rejectPendingUser(userId: string | number) {
  await rejectUser(userId)
  await loadPendingUsers()
}

export function useAuthState() {
  const [, force] = useState(0)
  useEffect(() => {
    const listener: Listener = () => force((n) => n + 1)
    listeners.add(listener)
    return () => {
      listeners.delete(listener)
    }
  }, [])

  return useMemo(
    () => ({
      auth,
      authLoading,
      authLoaded,
      authError,
      pendingUsers,
      pendingLoading,
      pendingError,
      isAuthEnabled: Boolean(auth.enabled),
      isAuthenticated: Boolean(auth.authenticated),
      isAdmin: Boolean(auth.is_admin),
      refreshAuthStatus,
      login,
      register,
      logout,
      loadPendingUsers,
      approvePendingUser,
      rejectPendingUser,
    }),
    // re-create after each emit so consumers get fresh values
    [auth, authLoading, authLoaded, authError, pendingUsers, pendingLoading, pendingError]
  )
}

export const authStore = {
  refreshAuthStatus,
  login,
  register,
  logout,
  loadPendingUsers,
  approvePendingUser,
  rejectPendingUser,
  get: () => auth,
}
