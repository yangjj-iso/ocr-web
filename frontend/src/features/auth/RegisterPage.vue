<template>
  <div class="flex min-h-screen bg-gradient-to-br from-slate-50 via-white to-indigo-50/40">
    <!-- Left: Branding Panel -->
    <div class="hidden w-[52%] flex-col justify-between overflow-hidden bg-gradient-to-br from-[#1a237e] via-indigo-700 to-[#0d47a1] px-12 py-10 lg:flex relative">
      <div class="absolute inset-0 opacity-[0.04]" style="background-image:url('data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%2260%22 height=%2260%22><rect width=%2260%22 height=%2260%22 fill=%22none%22/><path d=%22M30 0v60M0 30h60%22 stroke=%22white%22 stroke-width=%220.5%22/></svg>')"></div>
      <div class="relative z-10">
        <div class="flex items-center gap-3.5">
          <div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-white/10 shadow-lg shadow-black/10 backdrop-blur-sm ring-1 ring-white/20">
            <svg class="h-6 w-6 text-white" fill="none" stroke="currentColor" stroke-width="1.6" viewBox="0 0 24 24">
              <path d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
            </svg>
          </div>
          <div>
            <h1 class="auth-hero-title text-[26px] leading-tight text-white">启智 · AI档案数据资产平台</h1>
            <p class="auth-hero-sub mt-0.5 text-[13px] tracking-[0.08em] text-white/50">Intelligent Archive Data Asset Platform</p>
          </div>
        </div>
        <div class="mt-10 max-w-lg">
          <p class="auth-hero-desc text-base leading-[1.9] text-white/85">
            以人工智能驱动档案数据全生命周期管理
          </p>
          <p class="mt-1 text-sm leading-relaxed text-white/55">
            从纸质扫描到数字资产化，让每一份档案可识别、可检索、可追溯、可复用。
          </p>
        </div>
      </div>

      <div class="space-y-4">
        <div class="rounded-lg bg-white/10 px-5 py-4 backdrop-blur-sm">
          <h3 class="text-xs font-semibold text-white/90">注册流程</h3>
          <div class="mt-3 flex items-start gap-3">
            <div class="flex flex-col items-center">
              <div class="flex h-6 w-6 items-center justify-center rounded-full bg-white/20 text-[10px] font-bold text-white">1</div>
              <div class="mt-1 h-8 w-px bg-white/20"></div>
            </div>
            <div>
              <p class="text-xs font-medium text-white">填写基本信息</p>
              <p class="mt-0.5 text-[11px] text-white/50">填写真实姓名、工号并设置密码</p>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <div class="flex flex-col items-center">
              <div class="flex h-6 w-6 items-center justify-center rounded-full bg-white/20 text-[10px] font-bold text-white">2</div>
              <div class="mt-1 h-8 w-px bg-white/20"></div>
            </div>
            <div>
              <p class="text-xs font-medium text-white">等待审核</p>
              <p class="mt-0.5 text-[11px] text-white/50">管理员审核您的注册申请</p>
            </div>
          </div>
          <div class="flex items-start gap-3">
            <div class="flex flex-col items-center">
              <div class="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-400/30 text-[10px] font-bold text-emerald-300">3</div>
            </div>
            <div>
              <p class="text-xs font-medium text-white">审核通过</p>
              <p class="mt-0.5 text-[11px] text-white/50">使用工号与密码登录系统开始工作</p>
            </div>
          </div>
        </div>
        <p class="auth-hero-sub text-center text-[11px] tracking-wider text-white/25">启智 · AI档案数据资产平台 v1.0</p>
      </div>
    </div>

    <!-- Right: Register Form -->
    <div class="flex flex-1 items-center justify-center px-6 py-10">
      <div class="w-full max-w-sm">
        <!-- Mobile logo (hidden on lg) -->
        <div class="mb-8 flex items-center gap-2.5 lg:hidden">
          <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-[var(--gov-primary)] to-indigo-600 shadow-sm">
            <svg class="h-4 w-4 text-white" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="0 0 24 24">
              <path d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
            </svg>
          </div>
          <span class="text-base font-bold text-[var(--gov-text)]">启智 · AI档案数据资产平台</span>
        </div>

        <div class="mb-5">
          <h2 class="auth-form-title text-2xl text-[var(--gov-text)]">申请注册</h2>
          <p class="mt-1.5 text-sm text-[var(--gov-text-muted)]">注册后需管理员审核，通过后即可登录系统。</p>
        </div>

        <!-- Admin restriction notice -->
        <div class="mb-4 flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2">
          <svg class="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clip-rule="evenodd"/>
          </svg>
          <p class="text-[11px] leading-relaxed text-amber-700">
            <strong>管理员账号不可自行注册。</strong>普通人员注册后需等待管理员审核通过后方可登录。
          </p>
        </div>

        <form class="space-y-3.5" @submit.prevent="submitRegister">
          <div>
            <label class="mb-1.5 block text-xs font-medium text-[var(--gov-text-muted)]">真实姓名 <span class="text-red-400">*</span></label>
            <input
              v-model="realName"
              type="text"
              autocomplete="name"
              class="w-full rounded-lg border border-[var(--gov-border)] bg-white px-3.5 py-2.5 text-sm shadow-sm focus:border-[var(--gov-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--gov-primary)]/20"
              placeholder="请输入真实姓名（将作为系统显示名）"
              maxlength="60"
            />
          </div>

          <div>
            <label class="mb-1.5 block text-xs font-medium text-[var(--gov-text-muted)]">工号 <span class="text-red-400">*</span></label>
            <input
              v-model="username"
              type="text"
              autocomplete="username"
              class="w-full rounded-lg border border-[var(--gov-border)] bg-white px-3.5 py-2.5 text-sm shadow-sm focus:border-[var(--gov-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--gov-primary)]/20"
              placeholder="请输入工号（用于登录）"
              maxlength="60"
            />
            <p class="mt-1 text-[11px] text-[var(--gov-text-muted)]">工号即系统登录账号，注册后不可更改。</p>
          </div>

          <div>
            <label class="mb-1.5 block text-xs font-medium text-[var(--gov-text-muted)]">工作岗位 <span class="text-red-400">*</span></label>
            <p class="mb-2 text-[11px] text-[var(--gov-text-muted)]">选择您的岗位类型（可多选）：</p>
            <div class="flex gap-3">
              <label
                class="flex flex-1 cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-sm transition"
                :class="wantOperator ? 'border-[var(--gov-primary)] bg-[var(--gov-primary-soft)] text-[var(--gov-primary)] font-medium' : 'border-[var(--gov-border)] bg-white text-[var(--gov-text-muted)] hover:border-slate-300'"
              >
                <input v-model="wantOperator" type="checkbox" class="h-3.5 w-3.5 accent-[var(--gov-primary)]" />
                <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z M19.5 7.125l-2.652-2.652"/></svg>
                <div>
                  <span class="text-xs font-medium">著录者</span>
                  <p class="text-[10px] leading-tight opacity-60">档案录入、OCR识别、归档操作</p>
                </div>
              </label>
              <label
                class="flex flex-1 cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-sm transition"
                :class="wantSearcher ? 'border-[var(--gov-primary)] bg-[var(--gov-primary-soft)] text-[var(--gov-primary)] font-medium' : 'border-[var(--gov-border)] bg-white text-[var(--gov-text-muted)] hover:border-slate-300'"
              >
                <input v-model="wantSearcher" type="checkbox" class="h-3.5 w-3.5 accent-[var(--gov-primary)]" />
                <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/></svg>
                <div>
                  <span class="text-xs font-medium">检索者</span>
                  <p class="text-[10px] leading-tight opacity-60">档案查询、全文检索、预览</p>
                </div>
              </label>
            </div>
            <p v-if="!wantOperator && !wantSearcher" class="mt-1 text-[11px] text-red-500">请至少选择一个岗位。</p>
          </div>

          <div v-if="availableTenants.length > 1">
            <label class="mb-1.5 block text-xs font-medium text-[var(--gov-text-muted)]">所属机构 <span class="text-red-400">*</span></label>
            <select
              v-model="selectedTenantId"
              class="w-full rounded-lg border border-[var(--gov-border)] bg-white px-3.5 py-2.5 text-sm shadow-sm focus:border-[var(--gov-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--gov-primary)]/20"
            >
              <option v-for="t in availableTenants" :key="t.id" :value="t.id">{{ t.name }}</option>
            </select>
          </div>

          <div>
            <label class="mb-1.5 block text-xs font-medium text-[var(--gov-text-muted)]">密码 <span class="text-red-400">*</span></label>
            <input
              v-model="password"
              type="password"
              autocomplete="new-password"
              class="w-full rounded-lg border border-[var(--gov-border)] bg-white px-3.5 py-2.5 text-sm shadow-sm focus:border-[var(--gov-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--gov-primary)]/20"
              placeholder="至少 6 位"
            />
          </div>

          <div>
            <label class="mb-1.5 block text-xs font-medium text-[var(--gov-text-muted)]">确认密码 <span class="text-red-400">*</span></label>
            <input
              v-model="confirmPassword"
              type="password"
              autocomplete="new-password"
              class="w-full rounded-lg border border-[var(--gov-border)] bg-white px-3.5 py-2.5 text-sm shadow-sm focus:border-[var(--gov-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--gov-primary)]/20"
              placeholder="请再次输入密码"
            />
          </div>

          <p v-if="success" class="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">{{ success }}</p>
          <p v-if="error" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">{{ error }}</p>

          <button
            type="submit"
            class="w-full rounded-lg bg-gradient-to-r from-[var(--gov-primary)] to-indigo-600 py-2.5 text-sm font-medium text-white shadow-sm transition hover:shadow-md hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
            :disabled="submitting"
          >
            {{ submitting ? '提交中…' : '提交注册申请' }}
          </button>

          <div class="flex items-center justify-between text-xs text-[var(--gov-text-muted)]">
            <span>已有账号？</span>
            <router-link class="font-medium text-[var(--gov-primary)] hover:underline" to="/login">返回登录</router-link>
          </div>
        </form>

        <div class="mt-6 border-t border-[var(--gov-border)] pt-4">
          <p class="text-center text-[10px] text-[var(--gov-text-muted)]/50">
            AI 赋能档案管理 · 让数据成为资产
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

import { useAuthState } from '@/composables/useAuthState.js'
import { aiApiBase, requestDefaults } from '@/api/runtime.js'

const authState = useAuthState()

const realName = ref('')
const username = ref('')
const wantOperator = ref(true)
const wantSearcher = ref(false)
const password = ref('')
const confirmPassword = ref('')
const submitting = ref(false)
const error = ref('')
const success = ref('')

// Tenant selection
const selectedTenantId = ref('default')
const availableTenants = ref([{ id: 'default', name: '默认机构' }])

onMounted(async () => {
  try {
    const api = axios.create({ baseURL: aiApiBase('/tenants'), ...requestDefaults })
    const { data } = await api.get('')
    if (data?.items?.length) {
      availableTenants.value = data.items
      selectedTenantId.value = data.items[0].id
    }
  } catch {
    // silently fall back to default
  }
})

const requestedCapabilities = computed(() => {
  const parts = []
  if (wantOperator.value) parts.push('operator')
  if (wantSearcher.value) parts.push('searcher')
  return parts.join(',')
})

async function submitRegister() {
  const trimName = realName.value.trim()
  const trimUser = username.value.trim()
  error.value = ''
  success.value = ''

  if (!trimName) { error.value = '请填写真实姓名。'; return }
  if (!trimUser) { error.value = '请填写工号。'; return }
  if (!wantOperator.value && !wantSearcher.value) { error.value = '请至少选择一个岗位。'; return }
  if (!password.value) { error.value = '请填写密码。'; return }
  if (password.value.length < 6) { error.value = '密码至少 6 位。'; return }
  if (password.value !== confirmPassword.value) { error.value = '两次输入的密码不一致。'; return }

  submitting.value = true
  try {
    const data = await authState.register(trimUser, password.value, trimName, requestedCapabilities.value, selectedTenantId.value)
    success.value = data?.message || '注册申请已提交，请等待管理员审核通过后登录。'
    realName.value = ''
    username.value = ''
    wantOperator.value = true
    wantSearcher.value = false
    password.value = ''
    confirmPassword.value = ''
  } catch (requestError) {
    error.value = requestError?.response?.data?.message || requestError?.response?.data?.detail || '注册失败，请稍后重试。'
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.auth-hero-title {
  font-family: 'Noto Serif SC', '宋体', serif;
  font-weight: 700;
  letter-spacing: 0.04em;
}
.auth-hero-sub {
  font-family: 'Playfair Display', 'Noto Serif SC', serif;
  font-weight: 600;
}
.auth-hero-desc {
  font-family: 'Noto Serif SC', '宋体', serif;
  font-weight: 600;
}
.auth-form-title {
  font-family: 'Noto Serif SC', '宋体', serif;
  font-weight: 700;
  letter-spacing: 0.02em;
}
</style>
