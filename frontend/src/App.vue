<template>
  <div class="gov-shell">
    <header class="gov-header">
      <div class="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-5 gap-y-2 px-6 py-2.5">
        <router-link to="/" class="min-w-0 pr-1 no-underline">
          <h1 class="gov-header-title truncate text-lg text-[var(--gov-text)]">启智 · AI档案数据资产平台</h1>
        </router-link>

        <div class="hidden h-8 w-px bg-[var(--gov-border)] lg:block"></div>

        <nav
          v-if="showMainNav"
          class="order-3 flex w-full flex-wrap items-center gap-y-1.5 text-sm lg:order-none lg:w-auto"
        >
          <template v-for="(item, index) in navItems" :key="item.to">
            <router-link
              :to="item.to"
              class="gov-header-nav-link px-1 text-xs transition"
              :class="isActiveRoute(item.to) ? 'font-medium text-[var(--gov-primary)]' : 'text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]'"
            >
              {{ item.label }}
            </router-link>
            <span
              v-if="index < navItems.length - 1"
              class="mx-3 h-3.5 w-px bg-[var(--gov-border-strong)]"
              aria-hidden="true"
            ></span>
          </template>
        </nav>

        <div
          v-if="authState.isAuthEnabled.value && authState.isAuthenticated.value"
          class="flex items-center gap-2 lg:ml-auto"
        >
          <span class="rounded-lg border border-[var(--gov-border)] bg-white px-3 py-1 text-xs text-[var(--gov-text-muted)]">
            {{ authState.auth.value?.username }}
          </span>
          <button
            class="rounded-lg border border-[var(--gov-border)] bg-white px-3 py-1 text-xs text-[var(--gov-text)] transition hover:bg-slate-50"
            @click="handleLogout"
          >
            退出
          </button>
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

const navItems = computed(() => {
  const items = [
    { to: '/', label: '工作台' },
    { to: '/search', label: '检索' },
  ]
  if (authState.auth.value?.is_admin) {
    items.push({ to: '/admin/review', label: '账号审核' })
  }
  return items
})

const showMainNav = computed(() => {
  if (!authState.isAuthEnabled.value) return true
  if (!authState.isAuthenticated.value) return false
  return route.name !== 'Login' && route.name !== 'Register'
})

function isActiveRoute(targetPath) {
  return route.path === targetPath
}

async function handleLogout() {
  await authState.logout()
  router.replace('/login')
}

onMounted(() => {
  authState.refreshAuthStatus()
})
</script>
