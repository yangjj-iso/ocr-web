<template>
  <div class="mx-auto flex min-h-[calc(100vh-96px)] w-full max-w-xl items-center px-6 py-10">
    <section class="gov-panel w-full overflow-hidden">
      <div class="border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-6 py-5">
        <p class="text-xs font-semibold tracking-[0.16em] text-[var(--gov-primary)]">身份认证</p>
        <h2 class="mt-1 text-xl font-semibold text-[var(--gov-text)]">人社档案系统登录</h2>
        <p class="mt-2 text-sm gov-muted">请使用已开通账号登录，未开通账号可先提交注册申请。</p>
      </div>

      <form class="space-y-4 px-6 py-6" @submit.prevent="submitLogin">
        <label class="block text-sm text-[var(--gov-text)]">
          账号
          <input
            v-model="username"
            type="text"
            autocomplete="username"
            class="mt-1 w-full rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2 text-sm focus:border-[var(--gov-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--gov-primary)]/30"
            placeholder="请输入账号"
          />
        </label>

        <label class="block text-sm text-[var(--gov-text)]">
          密码
          <input
            v-model="password"
            type="password"
            autocomplete="current-password"
            class="mt-1 w-full rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2 text-sm focus:border-[var(--gov-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--gov-primary)]/30"
            placeholder="请输入密码"
          />
        </label>

        <p v-if="error" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">{{ error }}</p>

        <button
          type="submit"
          class="w-full rounded-lg bg-[var(--gov-primary)] py-2.5 text-sm font-medium text-white transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="submitting"
        >
          {{ submitting ? '登录中...' : '登录' }}
        </button>

        <div class="flex items-center justify-between text-xs gov-muted">
          <span>没有账号？</span>
          <router-link class="text-[var(--gov-primary)] hover:underline" to="/register">去注册</router-link>
        </div>
      </form>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthState } from '@/composables/useAuthState.js'

const route = useRoute()
const router = useRouter()
const authState = useAuthState()

const username = ref('')
const password = ref('')
const submitting = ref(false)
const error = ref('')

async function submitLogin() {
  if (!username.value.trim() || !password.value) {
    error.value = '请输入账号和密码。'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    await authState.login(username.value.trim(), password.value)
    await authState.refreshAuthStatus(true)
    const redirect = String(route.query.redirect || '/')
    router.replace(redirect || '/')
  } catch (requestError) {
    error.value = requestError?.response?.data?.detail || '登录未完成，请稍后重试。'
  } finally {
    submitting.value = false
  }
}
</script>
