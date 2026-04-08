<template>
  <div class="mx-auto flex min-h-[calc(100vh-96px)] w-full max-w-xl items-center px-6 py-10">
    <section class="gov-panel w-full overflow-hidden">
      <div class="border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-6 py-5">
        <p class="text-xs font-semibold tracking-[0.16em] text-[var(--gov-primary)]">账号申请</p>
        <h2 class="mt-1 text-xl font-semibold text-[var(--gov-text)]">提交注册申请</h2>
        <p class="mt-2 text-sm gov-muted">注册后需管理员审核，通过后即可登录系统。</p>
      </div>

      <form class="space-y-4 px-6 py-6" @submit.prevent="submitRegister">
        <label class="block text-sm text-[var(--gov-text)]">
          账号
          <input
            v-model="username"
            type="text"
            autocomplete="username"
            class="mt-1 w-full rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2 text-sm focus:border-[var(--gov-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--gov-primary)]/30"
            placeholder="3-120 位字符"
          />
        </label>

        <label class="block text-sm text-[var(--gov-text)]">
          密码
          <input
            v-model="password"
            type="password"
            autocomplete="new-password"
            class="mt-1 w-full rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2 text-sm focus:border-[var(--gov-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--gov-primary)]/30"
            placeholder="至少 6 位"
          />
        </label>

        <label class="block text-sm text-[var(--gov-text)]">
          确认密码
          <input
            v-model="confirmPassword"
            type="password"
            autocomplete="new-password"
            class="mt-1 w-full rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2 text-sm focus:border-[var(--gov-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--gov-primary)]/30"
            placeholder="请再次输入密码"
          />
        </label>

        <p v-if="success" class="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">{{ success }}</p>
        <p v-if="error" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">{{ error }}</p>

        <button
          type="submit"
          class="w-full rounded-lg bg-[var(--gov-primary)] py-2.5 text-sm font-medium text-white transition hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
          :disabled="submitting"
        >
          {{ submitting ? '提交中...' : '提交注册' }}
        </button>

        <div class="flex items-center justify-between text-xs gov-muted">
          <span>已有账号？</span>
          <router-link class="text-[var(--gov-primary)] hover:underline" to="/login">返回登录</router-link>
        </div>
      </form>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'

import { useAuthState } from '@/composables/useAuthState.js'

const authState = useAuthState()

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const submitting = ref(false)
const error = ref('')
const success = ref('')

async function submitRegister() {
  const name = username.value.trim()
  if (!name || !password.value || !confirmPassword.value) {
    error.value = '请完整填写注册信息。'
    success.value = ''
    return
  }
  if (password.value !== confirmPassword.value) {
    error.value = '两次输入的密码不一致。'
    success.value = ''
    return
  }

  submitting.value = true
  error.value = ''
  success.value = ''
  try {
    const data = await authState.register(name, password.value)
    success.value = data?.message || '注册申请已提交，请等待管理员审核。'
    password.value = ''
    confirmPassword.value = ''
  } catch (requestError) {
    error.value = requestError?.response?.data?.detail || '注册未完成，请稍后重试。'
  } finally {
    submitting.value = false
  }
}
</script>
