<template>
  <div :class="isStandalonePage ? 'min-h-screen' : 'gov-shell'">
    <header v-if="showAppHeader" class="gov-header">
      <div class="mx-auto flex max-w-[1600px] items-center justify-between px-6 py-3">
        <div class="flex items-center gap-3">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 shadow-sm shadow-blue-600/20">
            <svg class="h-4 w-4 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
            </svg>
          </div>
          <h1 class="text-[17px] font-semibold text-slate-800 tracking-wide">启智 <span class="mx-1.5 text-slate-300 font-normal">|</span> AI档案数据资产平台</h1>
        </div>

        <div class="flex items-center gap-6">
          <nav v-if="showMainNav" class="flex items-center space-x-1 lg:space-x-2">
            <router-link
              v-if="isAdmin"
              to="/dashboard"
              class="relative rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200"
              :class="$route.path === '/dashboard' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'"
            >
              仪表盘
            </router-link>
            <router-link
              v-if="isAdmin || userRole === 'operator'"
              to="/"
              class="relative rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200"
              :class="$route.path === '/' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'"
            >
              签录工作台
            </router-link>
            <router-link
              v-if="userRole === 'searcher'"
              to="/searcher-home"
              class="relative rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200"
              :class="$route.path === '/searcher-home' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'"
            >
              检索首页
            </router-link>
            <router-link
              v-if="isAdmin || userRole === 'operator'"
              to="/storage"
              class="relative rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200"
              :class="$route.path === '/storage' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'"
            >
              存放区
            </router-link>
            <router-link
              v-if="isAdmin"
              to="/batch-import"
              class="relative rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200"
              :class="$route.path === '/batch-import' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'"
            >
              批量导入
            </router-link>
            <router-link
              to="/search"
              class="relative rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200"
              :class="$route.path === '/search' ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'"
            >
              {{ userRole === 'searcher' ? '高级检索' : '检索' }}
            </router-link>
            <router-link
              v-if="isAdmin"
              to="/admin"
              class="relative rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200"
              :class="$route.path.startsWith('/admin') ? 'bg-blue-50 text-blue-600' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900'"
            >
              管理中心
              <span v-if="pendingCount > 0" class="absolute top-1 right-0 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold leading-none text-white ring-2 ring-white">{{ pendingCount }}</span>
            </router-link>
          </nav>

          <div v-if="authState.isAuthenticated.value || !authState.isAuthEnabled.value" class="flex items-center gap-4 border-l border-slate-200 pl-6">
            <router-link
              to="/profile"
              class="group flex items-center gap-2 transition-all"
            >
              <div class="flex h-8 w-8 items-center justify-center rounded-full bg-blue-100 text-sm font-bold text-blue-600 group-hover:bg-blue-200">
                {{ displayName.charAt(0).toUpperCase() }}
              </div>
              <div class="flex flex-col">
                <span class="text-sm font-medium text-slate-700 group-hover:text-blue-600">{{ displayName }}</span>
                <span class="text-[10px] text-slate-400">{{ roleLabel }}</span>
              </div>
            </router-link>
            
            <button
              class="flex h-8 w-8 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-red-50 hover:text-red-500"
              title="退出登录"
              @click="handleLogout"
            >
              <svg class="h-4.5 w-4.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
              </svg>
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
const isStandalonePage = computed(() => Boolean(route.meta?.standalone))
const showAppHeader = computed(() => !isAuthPage.value && !isStandalonePage.value)

const showMainNav = computed(() => {
  if (isStandalonePage.value) return false
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
