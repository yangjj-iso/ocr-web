<template>
  <div class="min-h-[calc(100vh-56px)] bg-gradient-to-br from-slate-50 via-white to-blue-50/30">
    <!-- Hero Banner -->
    <div class="border-b border-[var(--gov-border)] bg-white">
      <div class="mx-auto max-w-[1320px] px-6 py-6">
        <div class="flex items-center justify-between">
          <div>
            <div class="flex items-center gap-2 mb-1">
              <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">检索者</span>
              <span class="text-xs text-[var(--gov-text-muted)]">{{ todayStr }}</span>
            </div>
            <h1 class="text-xl font-bold text-[var(--gov-text)]">
              {{ greeting }}，{{ displayName }}
            </h1>
            <p class="mt-0.5 text-sm text-[var(--gov-text-muted)]">档案全文检索 · 快速定位所需文件</p>
          </div>
          <div class="hidden md:flex gap-3">
            <div class="rounded-xl border border-[var(--gov-border)] bg-gradient-to-br from-blue-50 to-white px-5 py-3 text-center">
              <p class="text-2xl font-extrabold text-blue-600">{{ myStats.searchCount }}</p>
              <p class="text-[10px] text-[var(--gov-text-muted)]">今日检索</p>
            </div>
            <div class="rounded-xl border border-[var(--gov-border)] bg-gradient-to-br from-emerald-50 to-white px-5 py-3 text-center">
              <p class="text-2xl font-extrabold text-emerald-600">{{ myStats.viewCount }}</p>
              <p class="text-[10px] text-[var(--gov-text-muted)]">查看文件</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="mx-auto max-w-[1320px] px-6 py-5">
      <!-- Search Box (prominent) -->
      <div class="mb-5 rounded-2xl border border-[var(--gov-border)] bg-white px-6 py-6 shadow-sm">
        <h2 class="mb-3 text-sm font-semibold text-[var(--gov-text)]">全文检索</h2>
        <div class="relative">
          <svg class="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-[var(--gov-text-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
          <input
            ref="searchInput"
            v-model="query"
            type="text"
            placeholder="输入文件名、正文关键词或档号进行检索…"
            class="w-full rounded-xl border border-[var(--gov-border)] bg-slate-50 py-3.5 pl-12 pr-28 text-sm shadow-inner focus:border-transparent focus:bg-white focus:outline-none focus:ring-2 focus:ring-[var(--gov-primary)]/30"
            @keydown.enter="doSearch"
          />
          <button
            class="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg bg-gradient-to-r from-[var(--gov-primary)] to-indigo-600 px-5 py-2 text-sm font-medium text-white shadow-sm transition hover:shadow-md hover:brightness-105 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="!query.trim() || loading"
            @click="doSearch"
          >
            {{ loading ? '搜索中…' : '搜索' }}
          </button>
        </div>
        <div class="mt-3 flex flex-wrap gap-2">
          <span class="text-[10px] text-[var(--gov-text-muted)]">快捷搜索：</span>
          <button v-for="tag in quickTags" :key="tag" class="rounded-full border border-[var(--gov-border)] px-2.5 py-0.5 text-[10px] text-[var(--gov-text-muted)] hover:bg-slate-50 hover:text-[var(--gov-text)] transition" @click="query = tag; doSearch()">
            {{ tag }}
          </button>
        </div>
      </div>

      <!-- Results -->
      <div v-if="loading" class="flex justify-center py-16">
        <div class="flex flex-col items-center gap-2">
          <svg class="h-8 w-8 animate-spin text-[var(--gov-primary)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" /></svg>
          <span class="text-xs text-[var(--gov-text-muted)]">正在检索…</span>
        </div>
      </div>

      <div v-else-if="searched && !results.length" class="rounded-xl border border-[var(--gov-border)] bg-white py-16 text-center shadow-sm">
        <svg class="mx-auto h-10 w-10 text-slate-300 mb-3" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/></svg>
        <p class="text-sm text-[var(--gov-text-muted)]">没有找到包含"{{ lastQuery }}"的记录</p>
        <p class="mt-1 text-xs text-[var(--gov-text-muted)]">请尝试其他关键词或调整搜索条件</p>
      </div>

      <div v-else-if="searched" class="space-y-3">
        <div class="flex items-center justify-between mb-2">
          <p class="text-xs text-[var(--gov-text-muted)]">找到 <strong class="text-[var(--gov-text)]">{{ total }}</strong> 条结果</p>
        </div>
        <router-link
          v-for="item in results" :key="item.id"
          :to="`/result/${item.id}`"
          class="block rounded-xl border border-[var(--gov-border)] bg-white p-4 shadow-sm hover:shadow-md hover:border-[var(--gov-primary)]/30 transition"
        >
          <div class="flex items-start justify-between">
            <div class="flex-1 min-w-0">
              <h3 class="text-sm font-semibold text-[var(--gov-text)] truncate">{{ item.filename }}</h3>
              <p v-if="item.snippet" class="mt-1 text-xs text-[var(--gov-text-muted)] line-clamp-2">{{ item.snippet }}</p>
              <div class="mt-2 flex flex-wrap gap-2">
                <span class="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-500">{{ item.file_type || 'file' }}</span>
                <span class="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] text-blue-500">{{ item.mode || 'ocr' }}</span>
                <span v-if="item.page_count" class="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] text-emerald-500">{{ item.page_count }} 页</span>
              </div>
            </div>
            <svg class="ml-3 h-4 w-4 flex-shrink-0 text-[var(--gov-text-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M8.25 4.5l7.5 7.5-7.5 7.5"/></svg>
          </div>
        </router-link>
      </div>

      <!-- Empty State: Feature Cards -->
      <div v-if="!searched && !loading" class="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div class="rounded-xl border border-[var(--gov-border)] bg-white p-5 shadow-sm">
          <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 mb-3">
            <svg class="h-5 w-5 text-blue-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/></svg>
          </div>
          <h3 class="text-sm font-semibold text-[var(--gov-text)]">全文检索</h3>
          <p class="mt-1 text-xs text-[var(--gov-text-muted)]">对所有已识别档案的全文内容进行智能检索，支持模糊匹配和精确查找。</p>
        </div>
        <div class="rounded-xl border border-[var(--gov-border)] bg-white p-5 shadow-sm">
          <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-indigo-50 mb-3">
            <svg class="h-5 w-5 text-indigo-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"/><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
          </div>
          <h3 class="text-sm font-semibold text-[var(--gov-text)]">在线预览</h3>
          <p class="mt-1 text-xs text-[var(--gov-text-muted)]">点击搜索结果直接查看档案原图和OCR识别内容，无需下载。</p>
        </div>
        <div class="rounded-xl border border-[var(--gov-border)] bg-white p-5 shadow-sm">
          <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 mb-3">
            <svg class="h-5 w-5 text-emerald-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>
          </div>
          <h3 class="text-sm font-semibold text-[var(--gov-text)]">结果导出</h3>
          <p class="mt-1 text-xs text-[var(--gov-text-muted)]">支持将检索结果导出为Excel报表，方便归档和汇报使用。</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAuthState } from '@/composables/useAuthState.js'
import { searchTasks } from '@/api/ocr.js'

const authState = useAuthState()
const displayName = computed(() => authState.auth.value?.display_name || authState.auth.value?.username || '用户')

const hour = new Date().getHours()
const greeting = hour < 12 ? '上午好' : hour < 18 ? '下午好' : '晚上好'
const todayStr = new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' })

const quickTags = ['人事档案', '2024年度', '转正申请', '劳动合同', '考核表']

const myStats = ref({ searchCount: 0, viewCount: 0 })

const searchInput = ref(null)
const query = ref('')
const lastQuery = ref('')
const results = ref([])
const total = ref(0)
const loading = ref(false)
const searched = ref(false)

async function doSearch() {
  const q = query.value.trim()
  if (!q) return
  loading.value = true
  searched.value = true
  lastQuery.value = q
  try {
    const { data } = await searchTasks(q, 1, 30)
    results.value = data?.items || data?.tasks || []
    total.value = data?.total ?? results.value.length
    myStats.value.searchCount++
  } catch {
    results.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  searchInput.value?.focus()
})
</script>
