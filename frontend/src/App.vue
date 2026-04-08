<template>
  <div class="gov-shell">
    <header class="gov-header">
      <div class="mx-auto flex max-w-[1600px] items-center justify-between px-6 py-3">
        <div class="flex items-center space-x-3">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--gov-primary)] shadow-sm">
            <svg class="h-4 w-4 text-white" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
              <circle cx="12" cy="12" r="3" />
            </svg>
          </div>
          <div>
            <h1 class="text-lg font-bold text-[var(--gov-text)]">人社档案整理系统</h1>
            <p class="text-xs gov-muted">支持智能辅助识别、检索与归档整理</p>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <nav v-if="showMainNav" class="flex items-center space-x-2 rounded-lg border border-[var(--gov-border)] bg-white/90 p-1">
            <router-link
              to="/"
              class="rounded-md px-3 py-1.5 text-sm transition"
              :class="$route.path === '/' ? 'bg-[var(--gov-primary-soft)] font-medium text-[var(--gov-primary)]' : 'text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]'"
            >
              工作台
            </router-link>
            <router-link
              to="/search"
              class="rounded-md px-3 py-1.5 text-sm transition"
              :class="$route.path === '/search' ? 'bg-[var(--gov-primary-soft)] font-medium text-[var(--gov-primary)]' : 'text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]'"
            >
              检索
            </router-link>
            <router-link
              v-if="authState.auth.value?.is_admin"
              to="/admin/review"
              class="rounded-md px-3 py-1.5 text-sm transition"
              :class="$route.path === '/admin/review' ? 'bg-[var(--gov-primary-soft)] font-medium text-[var(--gov-primary)]' : 'text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]'"
            >
              账号审核
            </router-link>
          </nav>

          <div v-if="authState.isAuthEnabled.value && authState.isAuthenticated.value" class="flex items-center gap-2">
            <span class="rounded-lg border border-[var(--gov-border)] bg-white px-3 py-1 text-xs text-[var(--gov-text-muted)]">
              {{ authState.auth.value?.username }}
            </span>
            <button
              class="rounded-lg border border-[var(--gov-border)] bg-white px-3 py-1 text-xs text-[var(--gov-text)] hover:bg-slate-50"
              @click="handleLogout"
            >
              退出
            </button>
          </div>
        </div>
      </div>
    </header>

    <router-view />
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthState } from './composables/useAuthState.js'

const route = useRoute()
const router = useRouter()
const authState = useAuthState()

const showMainNav = computed(() => {
  if (!authState.isAuthEnabled.value) return true
  if (!authState.isAuthenticated.value) return false
  return route.name !== 'Login' && route.name !== 'Register'
})

async function handleLogout() {
  await authState.logout()
  router.replace('/login')
}

onMounted(() => {
  authState.refreshAuthStatus()
})
</script>
