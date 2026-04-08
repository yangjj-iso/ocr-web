<template>
  <div class="flex h-[calc(100vh-64px)] gap-0">
    <aside class="flex w-[280px] flex-shrink-0 flex-col border-r border-[var(--gov-border)] bg-white">
      <nav class="flex flex-1 flex-col overflow-y-auto">
        <div class="border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-5 py-4">
          <p class="text-xs font-semibold tracking-[0.14em] text-[var(--gov-primary)]">功能模块</p>
        </div>

        <div class="flex-1 space-y-1 p-3">
          <button
            v-for="model in models"
            :key="model.mode"
            class="group flex w-full items-center gap-3 rounded-lg px-3 py-4 text-left transition-all"
            :class="selectedTab === model.mode
              ? sidebarActiveClass(model.color)
              : 'hover:bg-slate-50'"
            @click="selectedTab = model.mode"
          >
            <div
              class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg transition-colors"
              :class="selectedTab === model.mode
                ? sidebarIconClass(model.color)
                : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200'"
            >
              <svg v-if="model.icon === 'brain'" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>
              <svg v-else-if="model.icon === 'layout'" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
              <svg v-else class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 7V4h16v3M9 20h6M12 4v16"/></svg>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold text-[var(--gov-text)]">{{ model.name }}</span>
                <span
                  v-if="model.badge"
                  class="rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none"
                  :class="selectedTab === model.mode
                    ? 'bg-white/80 text-[var(--gov-text)]'
                    : badgeClass(model.color)"
                >{{ model.badge }}</span>
              </div>
              <p class="mt-0.5 truncate text-xs gov-muted">{{ model.desc }}</p>
            </div>
          </button>
        </div>

        <div class="mx-3 border-t border-[var(--gov-border)]"></div>

        <div class="space-y-1 p-3">
          <button
            class="group flex w-full items-center gap-3 rounded-lg px-3 py-4 text-left transition-all"
            :class="selectedTab === 'assistant'
              ? 'bg-violet-50 ring-1 ring-violet-200'
              : 'hover:bg-slate-50'"
            @click="onAssistantTabClick"
          >
            <div
              class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg transition-colors"
              :class="selectedTab === 'assistant'
                ? 'bg-violet-600 text-white'
                : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200'"
            >
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2">
                <span class="text-sm font-semibold text-[var(--gov-text)]">智能辅助</span>
                <span
                  class="rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none"
                  :class="capabilityBadgeClass"
                >{{ capabilityBadgeText }}</span>
              </div>
              <p class="mt-0.5 truncate text-xs gov-muted">批次整合与质量概览</p>
            </div>
          </button>

          <button
            class="group flex w-full items-center gap-3 rounded-lg px-3 py-4 text-left transition-all"
            :class="selectedTab === 'history'
              ? 'bg-slate-100 ring-1 ring-slate-200'
              : 'hover:bg-slate-50'"
            @click="selectedTab = 'history'"
          >
            <div
              class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg transition-colors"
              :class="selectedTab === 'history'
                ? 'bg-[var(--gov-primary)] text-white'
                : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200'"
            >
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            </div>
            <div class="min-w-0 flex-1">
              <span class="text-sm font-semibold text-[var(--gov-text)]">处理记录</span>
              <p class="mt-0.5 truncate text-xs gov-muted">按目录快速回看处理记录</p>
            </div>
          </button>
        </div>
      </nav>
    </aside>

    <main id="batch-workbench" class="min-w-0 flex-1 overflow-y-auto bg-[var(--gov-surface-muted)] p-6">
      <BufferZone
        v-for="model in models"
        v-show="selectedTab === model.mode"
        :key="model.mode"
        :model="model"
        @start-batch="handleStartBatch"
        @batch-completed="handleBatchCompleted"
        @view-result="handleViewResult"
      />

      <div v-show="selectedTab === 'assistant'" class="space-y-5">
        <div class="gov-panel overflow-hidden">
          <div class="border-b border-[var(--gov-border)] bg-violet-50 px-5 py-4">
            <div class="flex items-center justify-between">
              <div>
                <h3 class="text-lg font-semibold text-[var(--gov-text)]">智能辅助</h3>
                <p class="mt-1 text-sm gov-muted">{{ capabilityMessage }}</p>
              </div>
              <div class="flex items-center gap-2">
                <span class="rounded-full px-3 py-1 text-xs font-medium" :class="capabilityBadgeClass">
                  {{ capabilityBadgeText }}
                </span>
                <span v-if="latestBatchId" class="rounded-full border border-[var(--gov-border)] bg-white px-3 py-1 text-xs text-[var(--gov-text-muted)]">
                  当前批次：{{ latestBatchId }}
                </span>
              </div>
            </div>
          </div>

          <div class="bg-white p-5">
            <div class="grid gap-4 md:grid-cols-3">
              <article
                v-for="item in assistantItems"
                :key="item.title"
                class="cursor-pointer rounded-xl border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-5 py-5 transition hover:border-violet-200 hover:bg-violet-50/50"
                @click="item.action?.()"
              >
                <div class="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-violet-100 text-violet-600">
                  <svg v-if="item.icon === 'merge'" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                  <svg v-else-if="item.icon === 'chart'" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/></svg>
                  <svg v-else class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"/></svg>
                </div>
                <p class="text-sm font-semibold text-[var(--gov-text)]">{{ item.title }}</p>
                <p class="mt-1 text-xs leading-5 gov-muted">{{ item.description }}</p>
              </article>
            </div>

            <div v-if="answerSourceLabel" class="mt-4 rounded-xl border border-[var(--gov-border)] bg-white px-4 py-3 text-xs text-[var(--gov-text-muted)]">
              最近问答结果来源：<span class="font-medium text-[var(--gov-text)]">{{ answerSourceLabel }}</span>
            </div>

            <div class="mt-5 flex items-center gap-3">
              <button
                class="rounded-lg bg-violet-600 px-5 py-2.5 text-sm font-medium text-white transition hover:brightness-105"
                @click="handleAssistantPrimaryAction"
              >
                {{ hasBatchContext ? '进入质量概览' : '先去批量处理' }}
              </button>
              <button
                v-if="hasBatchContext"
                class="rounded-lg border border-[var(--gov-border)] bg-white px-5 py-2.5 text-sm font-medium text-[var(--gov-text)] transition hover:bg-slate-50"
                @click="selectedTab = 'vl'"
              >
                返回批量处理区
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-show="selectedTab === 'history'">
        <div class="gov-panel overflow-hidden">
          <div class="border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-5 py-4">
            <h3 class="text-lg font-semibold text-[var(--gov-text)]">处理记录与目录入口</h3>
            <p class="mt-1 text-xs gov-muted">按目录快速回看处理记录</p>
          </div>
          <div class="bg-white p-5">
            <HistoryList ref="historyRef" @view-result="handleViewResult" @batch-context="handleHistoryBatchContext" />
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import BufferZone from '@/components/BufferZone.vue'
import HistoryList from '@/components/HistoryList.vue'
import { getModeMeta } from '@/constants/uiCopy.js'
import { getAiAnswerSourceLabel, useAiCapabilityState } from '@/composables/useAiCapabilityState.js'
import { getFolders } from '@/api/ocr.js'

const router = useRouter()
const historyRef = ref(null)
const _storedTab = sessionStorage.getItem('ocr:selectedTab')
const selectedTab = ref(_storedTab || 'vl')
watch(selectedTab, (v) => sessionStorage.setItem('ocr:selectedTab', v))
const aiCapability = useAiCapabilityState()

function sidebarActiveClass(color) {
  const map = {
    indigo: 'bg-indigo-50 ring-1 ring-indigo-200',
    blue: 'bg-blue-50 ring-1 ring-blue-200',
    green: 'bg-emerald-50 ring-1 ring-emerald-200',
  }
  return map[color] || 'bg-slate-100'
}

function sidebarIconClass(color) {
  const map = {
    indigo: 'bg-indigo-600 text-white',
    blue: 'bg-[var(--gov-primary)] text-white',
    green: 'bg-emerald-700 text-white',
  }
  return map[color] || 'bg-slate-500 text-white'
}

function badgeClass(color) {
  const map = {
    indigo: 'bg-indigo-100 text-indigo-700',
    blue: 'bg-blue-100 text-blue-700',
    green: 'bg-emerald-100 text-emerald-700',
  }
  return map[color] || 'bg-slate-100 text-slate-600'
}

const assistantItems = [
  {
    title: '智能整合',
    icon: 'merge',
    description: '对当前批次中的同一文档进行保守整合，返回可核对的分组与字段建议。',
  },
  {
    title: '质量概览',
    icon: 'chart',
    description: '集中查看批次处理质量、冲突项和人工核对结果，便于复核。',
    action: () => {
      if (hasBatchContext.value && latestBatchId.value) {
        router.push(`/batch-insights/${encodeURIComponent(latestBatchId.value)}`)
      }
    },
  },
  {
    title: '批次问答',
    icon: 'chat',
    description: '围绕当前批次做证据可追溯的知识问答，优先给出可解释结论。',
  },
]

const models = [
  {
    mode: 'vl',
    name: getModeMeta('vl').title,
    desc: getModeMeta('vl').description,
    icon: 'brain',
    color: 'indigo',
    badge: getModeMeta('vl').badge,
  },
  {
    mode: 'layout',
    name: getModeMeta('layout').title,
    desc: getModeMeta('layout').description,
    icon: 'layout',
    color: 'blue',
    badge: getModeMeta('layout').badge,
  },
  {
    mode: 'ocr',
    name: getModeMeta('ocr').title,
    desc: getModeMeta('ocr').description,
    icon: 'type',
    color: 'green',
    badge: getModeMeta('ocr').badge,
  },
]

const hasBatchContext = computed(() => aiCapability.hasBatchContext.value)
const latestBatchId = computed(() => aiCapability.latestBatchId.value)
const capabilityMessage = computed(() => aiCapability.capabilityMessage.value)
const answerSourceLabel = computed(() =>
  aiCapability.answerSource.value ? getAiAnswerSourceLabel(aiCapability.answerSource.value) : ''
)
const capabilityBadgeText = computed(() => {
  if (aiCapability.loading.value) return '状态校验中'
  if (aiCapability.capabilityStatus.value === 'ready') return '智能辅助可用'
  if (aiCapability.capabilityStatus.value === 'unavailable') return '智能服务待检查'
  return '尚未形成批次'
})
const capabilityBadgeClass = computed(() => {
  if (aiCapability.capabilityStatus.value === 'ready') {
    return 'bg-emerald-100 text-emerald-700'
  }
  if (aiCapability.capabilityStatus.value === 'unavailable') {
    return 'bg-amber-100 text-amber-700'
  }
  return 'bg-slate-100 text-slate-600'
})

function scrollToWorkbench() {
  document.getElementById('batch-workbench')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function handleAssistantPrimaryAction() {
  if (hasBatchContext.value && latestBatchId.value) {
    router.push(`/batch-insights/${encodeURIComponent(latestBatchId.value)}`)
    return
  }
  selectedTab.value = 'vl'
}

async function tryResolveBatchFromHistory() {
  if (latestBatchId.value) {
    await aiCapability.refreshAiCapability({ passive: false, batchId: latestBatchId.value })
    return
  }

  try {
    const { data } = await getFolders()
    const folders = data || []
    for (const folder of folders) {
      const batchId = folder.batch_ids?.[0] || ''
      if (batchId) {
        await aiCapability.refreshAiCapability({ passive: false, batchId })
        return
      }
    }
  } catch (_) {}
}

async function onAssistantTabClick() {
  selectedTab.value = 'assistant'
  if (!latestBatchId.value) {
    await tryResolveBatchFromHistory()
  } else {
    await aiCapability.refreshAiCapability({ passive: false, batchId: latestBatchId.value })
  }
}

function handleStartBatch() {
  // 批量处理中不做被动评测探测，避免使用上一个批次触发无效请求噪音。
}

async function handleBatchCompleted(payload = {}) {
  historyRef.value?.refresh()
  if (!payload?.hasUsableResults || !payload?.batchId) {
    return
  }
  await aiCapability.refreshAiCapability({ passive: false, batchId: payload.batchId })
}

async function handleHistoryBatchContext(payload = {}) {
  if (!payload?.batchId) {
    return
  }
  await aiCapability.refreshAiCapability({ passive: false, batchId: payload.batchId })
}

function handleViewResult(taskId) {
  router.push(`/result/${taskId}`)
}

onMounted(async () => {
  if (latestBatchId.value) {
    await aiCapability.refreshAiCapability({ passive: false, batchId: latestBatchId.value })
    return
  }
  await tryResolveBatchFromHistory()
})
</script>
