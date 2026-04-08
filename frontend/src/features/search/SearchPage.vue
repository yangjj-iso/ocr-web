<template>
  <div class="mx-auto max-w-[1320px] px-6 py-6">
    <section class="gov-panel mb-4 p-5">
      <div class="mb-4 flex items-end justify-between">
        <div>
          <h1 class="gov-section-title text-xl font-bold">档案全文检索</h1>
          <p class="mt-1 text-xs gov-muted">支持按文件名、正文片段与结构化内容检索处理记录。</p>
        </div>
        <p v-if="searched" class="text-xs gov-muted">
          共 <span class="font-semibold text-[var(--gov-text)]">{{ total }}</span> 条
        </p>
      </div>

      <div class="relative">
        <svg class="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-[var(--gov-text-muted)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <circle cx="11" cy="11" r="8" />
          <path d="M21 21l-4.35-4.35" />
        </svg>
        <input
          ref="searchInput"
          v-model="query"
          type="text"
          placeholder="输入文件名、正文关键词或结构化内容"
          class="w-full rounded-xl border border-[var(--gov-border)] bg-white py-3 pl-12 pr-24 text-sm shadow-sm focus:border-transparent focus:outline-none focus:ring-2 focus:ring-[var(--gov-primary)]/30"
          @input="onInput"
          @keydown.enter="doSearch"
        />
        <button
          class="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg bg-[var(--gov-primary)] px-4 py-1.5 text-sm font-medium text-white transition hover:brightness-105 disabled:cursor-not-allowed disabled:bg-slate-300"
          :disabled="!query.trim()"
          @click="doSearch"
        >
          搜索
        </button>
      </div>
    </section>

    <section class="gov-panel min-h-[320px] p-4">
      <div v-if="loading" class="flex justify-center py-16">
        <svg class="h-8 w-8 animate-spin text-[var(--gov-primary)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
          <path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" />
        </svg>
      </div>

      <div v-else-if="searched && !results.length" class="py-16 text-center">
        <p class="text-sm gov-muted">没有找到包含“{{ lastQuery }}”的记录。</p>
      </div>

      <div v-else-if="!searched" class="py-16 text-center text-sm gov-muted">
        请输入检索词开始查询处理记录。
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="item in results"
          :key="item.id"
          class="group flex overflow-hidden rounded-xl border border-[var(--gov-border)] bg-white transition-all"
          :class="canOpenResult(item) ? 'cursor-pointer hover:border-[var(--gov-border-strong)] hover:shadow-sm' : 'cursor-not-allowed opacity-90'"
          @click="openResult(item)"
        >
          <div class="relative h-28 w-32 flex-shrink-0 overflow-hidden bg-slate-100">
            <img :src="getTaskThumbnailUrl(item.id)" class="h-full w-full object-cover transition-transform duration-300 group-hover:scale-102" />
          </div>

          <div class="min-w-0 flex-1 px-4 py-3">
            <div class="mb-1 flex items-center space-x-2">
              <h3 class="truncate text-sm font-semibold text-[var(--gov-text)]">{{ item.filename }}</h3>
              <span class="flex-shrink-0 rounded px-1.5 py-0.5 text-xs font-medium" :class="modeClass(item.mode)">
                {{ modeLabel(item.mode) }}
              </span>
            </div>

            <p v-if="item.snippet" class="mb-2 line-clamp-2 text-xs leading-relaxed gov-muted" v-html="highlightSnippet(item.snippet)"></p>

            <div class="flex items-center space-x-3 text-xs gov-muted">
              <span>{{ item.page_count || 0 }} 页</span>
              <span>{{ formatTime(item.created_at) }}</span>
              <span class="flex items-center space-x-1">
                <span class="h-1.5 w-1.5 rounded-full" :class="statusDot(item.status)"></span>
                <span>{{ statusLabel(item.status) }}</span>
              </span>
            </div>
          </div>

          <div class="flex items-center px-3 text-slate-300 transition group-hover:text-[var(--gov-primary)]">
            <svg v-if="canOpenResult(item)" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 5l7 7-7 7" /></svg>
            <svg v-else class="h-5 w-5 text-slate-300" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 8v4l2 2" /><circle cx="12" cy="12" r="9" /></svg>
          </div>
        </div>

        <div v-if="total > pageSize" class="flex justify-center space-x-2 pt-4">
          <button
            v-for="pageNumber in totalPageCount"
            :key="pageNumber"
            class="h-8 w-8 rounded-lg text-xs font-medium transition"
            :class="page === pageNumber ? 'bg-[var(--gov-primary)] text-white' : 'bg-slate-100 text-[var(--gov-text-muted)] hover:bg-slate-200'"
            @click="goPage(pageNumber)"
          >
            {{ pageNumber }}
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'

import { getTaskThumbnailUrl, searchTasks } from '@/api/ocr.js'
import { getModeLabel, getStatusLabel } from '@/constants/uiCopy.js'

const query = ref('')
const lastQuery = ref('')
const results = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(false)
const searched = ref(false)
const searchInput = ref(null)
const router = useRouter()

let debounceTimer = null

const totalPageCount = computed(() => Math.ceil(total.value / pageSize))

onMounted(() => {
  searchInput.value?.focus()
})

function onInput() {
  clearTimeout(debounceTimer)
  if (query.value.trim().length >= 2) {
    debounceTimer = window.setTimeout(() => doSearch(), 350)
  }
}

async function doSearch(resetPage = true) {
  const keyword = query.value.trim()
  if (!keyword) return
  if (resetPage) page.value = 1

  loading.value = true
  searched.value = true
  lastQuery.value = keyword

  try {
    const { data } = await searchTasks(keyword, page.value, pageSize)
    results.value = data.tasks || []
    total.value = data.total || 0
  } catch (_) {
    results.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function goPage(nextPage) {
  page.value = nextPage
  doSearch(false)
}

function highlightSnippet(text) {
  const escapedText = text
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
  if (!lastQuery.value) return escapedText
  const escaped = lastQuery.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return escapedText.replace(new RegExp(`(${escaped})`, 'gi'), '<mark class="gov-mark">$1</mark>')
}

function modeLabel(mode) {
  return getModeLabel(mode)
}

function modeClass(mode) {
  return {
    vl: 'bg-indigo-100 text-indigo-700',
    layout: 'bg-blue-100 text-blue-700',
    ocr: 'bg-emerald-100 text-emerald-700',
  }[mode] || 'bg-slate-100 text-slate-700'
}

function statusDot(status) {
  return {
    done: 'bg-emerald-500',
    failed: 'bg-rose-500',
    processing: 'bg-amber-400',
    pending: 'bg-slate-300',
  }[status] || 'bg-slate-300'
}

function statusLabel(status) {
  return getStatusLabel(status)
}

function formatTime(value) {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'
}

function canOpenResult(item) {
  return ['done', 'failed'].includes(String(item?.status || ''))
}

function openResult(item) {
  if (!canOpenResult(item)) return
  router.push(`/result/${item.id}`)
}
</script>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
}
</style>
