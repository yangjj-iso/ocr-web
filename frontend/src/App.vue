<template>
  <div :class="isStandalonePage ? 'min-h-screen' : 'gov-shell'">
    <header v-if="showAppHeader" class="gov-header">
      <div class="mx-auto flex max-w-[1600px] items-center justify-between px-6 py-3">
        <div class="flex items-center space-x-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--gov-primary)] to-indigo-600 shadow-sm">
            <svg class="h-4.5 w-4.5 text-white" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
              <path d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
            </svg>
          </div>
          <div>
            <h1 class="text-lg font-bold text-[var(--gov-text)]">启智 · AI档案数据资产平台</h1>
            <p class="text-xs gov-muted">智能识别 · 全文检索 · 自动归档 · 数据资产管理</p>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <nav v-if="showMainNav" class="flex items-center space-x-2 rounded-lg border border-[var(--gov-border)] bg-white/90 p-1">
            <router-link
              v-if="isAdmin"
              to="/dashboard"
              class="rounded-md px-3 py-1.5 text-sm transition"
              :class="$route.path === '/dashboard' ? 'bg-[var(--gov-primary-soft)] font-medium text-[var(--gov-primary)]' : 'text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]'"
            >
              仪表盘
            </router-link>
            <router-link
              v-if="isAdmin || userRole === 'operator'"
              to="/"
              class="rounded-md px-3 py-1.5 text-sm transition"
              :class="$route.path === '/' ? 'bg-[var(--gov-primary-soft)] font-medium text-[var(--gov-primary)]' : 'text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]'"
            >
              签录工作台
            </router-link>
            <router-link
              v-if="userRole === 'searcher'"
              to="/searcher-home"
              class="rounded-md px-3 py-1.5 text-sm transition"
              :class="$route.path === '/searcher-home' ? 'bg-[var(--gov-primary-soft)] font-medium text-[var(--gov-primary)]' : 'text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]'"
            >
              检索首页
            </router-link>
            <router-link
              v-if="isAdmin || userRole === 'operator'"
              to="/storage"
              class="rounded-md px-3 py-1.5 text-sm transition"
              :class="$route.path === '/storage' ? 'bg-[var(--gov-primary-soft)] font-medium text-[var(--gov-primary)]' : 'text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]'"
            >
              存放区
            </router-link>
            <router-link
              v-if="isAdmin"
              to="/batch-import"
              class="rounded-md px-3 py-1.5 text-sm transition"
              :class="$route.path === '/batch-import' ? 'bg-[var(--gov-primary-soft)] font-medium text-[var(--gov-primary)]' : 'text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]'"
            >
              批量导入
            </router-link>
            <router-link
              to="/search"
              class="rounded-md px-3 py-1.5 text-sm transition"
              :class="$route.path === '/search' ? 'bg-[var(--gov-primary-soft)] font-medium text-[var(--gov-primary)]' : 'text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]'"
            >
              {{ userRole === 'searcher' ? '高级检索' : '检索' }}
            </router-link>
            <router-link
              v-if="isAdmin"
              to="/admin"
              class="relative rounded-md px-3 py-1.5 text-sm transition"
              :class="$route.path.startsWith('/admin') ? 'bg-[var(--gov-primary-soft)] font-medium text-[var(--gov-primary)]' : 'text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]'"
            >
              管理中心
              <span v-if="pendingCount > 0" class="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold leading-none text-white">{{ pendingCount }}</span>
            </router-link>
          </nav>

          <div v-if="authState.isAuthenticated.value || !authState.isAuthEnabled.value" class="flex items-center gap-2">
            <router-link
              to="/profile"
              class="flex items-center gap-1.5 rounded-lg border border-[var(--gov-border)] bg-white px-3 py-1 text-xs text-[var(--gov-text-muted)] transition hover:bg-slate-50"
              :class="$route.path === '/profile' ? 'ring-1 ring-[var(--gov-primary)] text-[var(--gov-primary)]' : ''"
            >
              {{ displayName }}
              <span :class="roleBadgeClass" class="rounded px-1.5 py-0.5 text-[10px] font-medium">{{ roleLabel }}</span>
            </router-link>
            <button
              class="rounded-lg border border-[var(--gov-border)] bg-white px-3 py-1 text-xs text-[var(--gov-text)] hover:bg-slate-50"
              @click="handleLogout"
            >
              退出登录
            </button>
          </div>
        </div>
      </div>
    </header>

    <router-view />
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getPendingUsers } from './api/auth.js'
import { useAuthState } from './composables/useAuthState.js'

const route = useRoute()
const router = useRouter()
const authState = useAuthState()

const isAuthPage = computed(() => route.name === 'Login' || route.name === 'Register')
const isStandalonePage = computed(() => route.meta?.standalone === true)
const showAppHeader = computed(() => !isStandalonePage.value && !isAuthPage.value)

const showMainNav = computed(() => {
  if (!authState.isAuthEnabled.value) return true
  if (!authState.isAuthenticated.value) return false
  return !isAuthPage.value
})

const ROLE_LABELS = { admin: '管理员', operator: '签录员', searcher: '检索员' }
const ROLE_BADGE_CLASS = {
  admin: 'bg-indigo-100 text-indigo-700',
  operator: 'bg-blue-50 text-blue-600',
  searcher: 'bg-slate-100 text-slate-500',
}

const isAdmin = computed(() => Boolean(authState.auth.value?.is_admin))
const userRole = computed(() => authState.auth.value?.role || 'operator')
const roleLabel = computed(() => ROLE_LABELS[userRole.value] || userRole.value || '未知角色')
const roleBadgeClass = computed(() => ROLE_BADGE_CLASS[userRole.value] || 'bg-slate-100 text-slate-500')
const displayName = computed(() => authState.auth.value?.display_name || authState.auth.value?.username || '当前用户')

const pendingCount = ref(0)

async function refreshPendingCount() {
  if (!authState.auth.value?.is_admin) {
    pendingCount.value = 0
    return
  }
  try {
    const { data } = await getPendingUsers()
    pendingCount.value = (data?.items || []).length
  } catch {
    pendingCount.value = 0
  }
}

watch(() => authState.auth.value?.is_admin, (admin) => {
  if (admin) refreshPendingCount()
  else pendingCount.value = 0
})

async function handleLogout() {
  try {
    await authState.logout()
  } catch {
    // ignore API errors (e.g. 401 when session already expired)
  }
  router.replace('/login')
}

onMounted(() => {
  if (!isStandalonePage.value) {
    authState.refreshAuthStatus()
  }
})
</script>
