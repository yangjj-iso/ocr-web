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
        <div class="grid grid-cols-2 gap-3">
          <div class="rounded-lg bg-white/10 px-4 py-3.5 backdrop-blur-sm">
            <div class="flex items-center gap-2">
              <svg class="h-4 w-4 text-emerald-300" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
              <span class="text-xs font-semibold text-white">智能 OCR 识别</span>
            </div>
            <p class="mt-1.5 text-[11px] leading-relaxed text-white/60">自动提取文号、题名、日期等关键字段，告别手工录入</p>
          </div>
          <div class="rounded-lg bg-white/10 px-4 py-3.5 backdrop-blur-sm">
            <div class="flex items-center gap-2">
              <svg class="h-4 w-4 text-sky-300" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/></svg>
              <span class="text-xs font-semibold text-white">全文检索</span>
            </div>
            <p class="mt-1.5 text-[11px] leading-relaxed text-white/60">基于 AI 语义理解的全文索引，关键词精准定位档案原文</p>
          </div>
          <div class="rounded-lg bg-white/10 px-4 py-3.5 backdrop-blur-sm">
            <div class="flex items-center gap-2">
              <svg class="h-4 w-4 text-amber-300" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"/></svg>
              <span class="text-xs font-semibold text-white">自动归档分件</span>
            </div>
            <p class="mt-1.5 text-[11px] leading-relaxed text-white/60">归档章检测 + 档号规则自动建立文件夹，批量分件入库</p>
          </div>
          <div class="rounded-lg bg-white/10 px-4 py-3.5 backdrop-blur-sm">
            <div class="flex items-center gap-2">
              <svg class="h-4 w-4 text-violet-300" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"/></svg>
              <span class="text-xs font-semibold text-white">数据资产化</span>
            </div>
            <p class="mt-1.5 text-[11px] leading-relaxed text-white/60">签录模板 + 双层 PDF 导出，档案数据可追溯、可复用</p>
          </div>
        </div>
        <p class="auth-hero-sub text-center text-[11px] tracking-wider text-white/25">启智 · AI档案数据资产平台 v1.0</p>
      </div>
    </div>

    <!-- Right: Login Form -->
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

        <div class="mb-7">
          <h2 class="auth-form-title text-2xl text-[var(--gov-text)]">欢迎登录</h2>
          <p class="mt-1.5 text-sm text-[var(--gov-text-muted)]">请使用工号和密码登录，未开通账号可先提交注册申请。</p>
        </div>

        <form class="space-y-4" @submit.prevent="submitLogin">
          <div>
            <label class="mb-1.5 block text-xs font-medium text-[var(--gov-text-muted)]">工号</label>
            <input
              v-model="username"
              type="text"
              autocomplete="username"
              class="w-full rounded-lg border border-[var(--gov-border)] bg-white px-3.5 py-2.5 text-sm shadow-sm focus:border-[var(--gov-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--gov-primary)]/20"
              placeholder="请输入工号"
            />
          </div>

          <div>
            <label class="mb-1.5 block text-xs font-medium text-[var(--gov-text-muted)]">密码</label>
            <input
              v-model="password"
              type="password"
              autocomplete="current-password"
              class="w-full rounded-lg border border-[var(--gov-border)] bg-white px-3.5 py-2.5 text-sm shadow-sm focus:border-[var(--gov-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--gov-primary)]/20"
              placeholder="请输入密码"
            />
          </div>

          <p v-if="error" class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">{{ error }}</p>

          <button
            type="submit"
            class="w-full rounded-lg bg-gradient-to-r from-[var(--gov-primary)] to-indigo-600 py-2.5 text-sm font-medium text-white shadow-sm transition hover:shadow-md hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-60"
            :disabled="submitting"
          >
            {{ submitting ? '登录中...' : '登 录' }}
          </button>

          <div class="flex items-center justify-between text-xs text-[var(--gov-text-muted)]">
            <span>没有账号？</span>
            <router-link class="font-medium text-[var(--gov-primary)] hover:underline" to="/register">申请注册</router-link>
          </div>
        </form>

        <div class="mt-8 border-t border-[var(--gov-border)] pt-5">
          <p class="text-center text-[10px] text-[var(--gov-text-muted)]/50">
            AI 赋能档案管理 · 让数据成为资产
          </p>
        </div>
      </div>
    </div>
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
    error.value = '请输入工号和密码。'
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
    const d = requestError?.response?.data
    error.value = d?.detail || d?.message || (requestError?.response?.status === 401 ? '工号或密码错误，请重试。' : '登录未完成，请稍后重试。')
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
