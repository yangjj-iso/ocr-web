<template>
  <div class="relative" ref="menuRef">
    <button
      class="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-slate-600 hover:bg-slate-100 transition"
      @click="open = !open"
    >
      <div class="flex h-8 w-8 items-center justify-center rounded-full text-xs font-bold text-white" :class="roleBadgeColor">
        {{ initial }}
      </div>
      <span class="hidden text-xs font-medium sm:block">{{ displayName }}</span>
      <svg class="h-3.5 w-3.5 text-slate-400" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 8.25l-7.5 7.5-7.5-7.5" />
      </svg>
    </button>

    <transition
      enter-active-class="transition duration-100 ease-out"
      enter-from-class="transform scale-95 opacity-0"
      enter-to-class="transform scale-100 opacity-100"
      leave-active-class="transition duration-75 ease-in"
      leave-from-class="transform scale-100 opacity-100"
      leave-to-class="transform scale-95 opacity-0"
    >
      <div
        v-if="open"
        class="absolute right-0 top-full mt-1 w-52 rounded-lg border border-[var(--gov-border)] bg-white py-1 shadow-lg z-50"
      >
        <div class="border-b border-slate-100 px-4 py-3">
          <p class="text-sm font-semibold text-slate-800">{{ displayName }}</p>
          <p class="text-[11px] text-slate-500">{{ roleLabel }}</p>
        </div>
        <button
          class="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
          @click="goProfile"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"/>
          </svg>
          个人设置
        </button>
        <button
          class="flex w-full items-center gap-2.5 px-4 py-2 text-sm text-red-600 hover:bg-red-50"
          @click="handleLogout"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9"/>
          </svg>
          退出登录
        </button>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthState } from '@/composables/useAuthState.js'

const router = useRouter()
const authState = useAuthState()
const auth = authState.auth
const authProfile = authState.authProfile
const open = ref(false)
const menuRef = ref(null)

const displayName = computed(() => auth.value?.display_name || auth.value?.username || '用户')
const isSysAdmin = computed(() => authProfile.value.isSysAdmin)
const isTenantAdmin = computed(() => authProfile.value.isTenantAdmin)
const isOperator = computed(() => !isSysAdmin.value && !isTenantAdmin.value && authProfile.value.hasOperator)
const isSearcher = computed(() => !isSysAdmin.value && !isTenantAdmin.value && !authProfile.value.hasOperator && authProfile.value.hasSearcher)

const roleLabel = computed(() => authProfile.value.roleLabel)

const initial = computed(() => displayName.value?.[0]?.toUpperCase() || 'U')

const roleBadgeColor = computed(() => {
  if (isSysAdmin.value) return 'bg-purple-600'
  if (isTenantAdmin.value) return 'bg-blue-600'
  if (isOperator.value) return 'bg-emerald-600'
  if (isSearcher.value) return 'bg-amber-600'
  return 'bg-slate-500'
})

function goProfile() {
  open.value = false
  router.push('/profile')
}

async function handleLogout() {
  open.value = false
  await authState.logout()
  router.push('/login')
}

function onClickOutside(e) {
  if (menuRef.value && !menuRef.value.contains(e.target)) {
    open.value = false
  }
}

onMounted(() => document.addEventListener('click', onClickOutside, true))
onUnmounted(() => document.removeEventListener('click', onClickOutside, true))
</script>
