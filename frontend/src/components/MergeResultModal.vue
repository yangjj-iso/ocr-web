<template>
  <div v-if="visible" class="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" @click.self="$emit('close')">
    <div class="max-h-[85vh] w-full max-w-5xl overflow-hidden rounded-xl bg-white shadow-2xl">
      <div class="flex items-center justify-between border-b border-[var(--gov-border)] px-5 py-3">
        <div>
          <h3 class="text-sm font-semibold text-[var(--gov-text)]">智能整合结果</h3>
          <p class="text-xs gov-muted">已生成可核对的归并文件和字段建议。</p>
        </div>
        <button class="rounded px-2 py-1 text-xs gov-muted hover:bg-slate-100" @click="$emit('close')">关闭</button>
      </div>

      <div v-if="loadingMerge" class="px-5 py-10 text-center text-sm gov-muted">
        <svg class="mx-auto mb-2 h-6 w-6 animate-spin text-[var(--gov-primary)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" /></svg>
        正在加载智能整合数据…
      </div>
      <div v-else-if="mergeError" class="px-5 py-10 text-center text-sm text-[var(--gov-danger)]">{{ mergeError }}</div>

      <div v-else-if="mergeResult" class="max-h-[calc(85vh-64px)] space-y-4 overflow-y-auto px-5 py-4">
        <div class="grid grid-cols-2 gap-2 text-xs text-[var(--gov-text-muted)] md:grid-cols-4">
          <div class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2">原始材料：{{ mergeResult.summary.total_tasks }}</div>
          <div class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2">可分析材料：{{ mergeResult.summary.eligible_tasks }}</div>
          <div class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2">判定分组：{{ mergeResult.summary.groups_count }}</div>
          <div class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2">归并文件：{{ mergeResult.summary.documents_count }}</div>
        </div>

        <div class="rounded-xl border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-4 py-3">
          <div class="mb-2 flex items-center justify-between">
            <p class="text-xs font-semibold text-[var(--gov-text)]">统计概览</p>
            <div class="flex items-center space-x-2">
              <button
                class="rounded border border-[var(--gov-border)] bg-white px-2 py-1 text-[11px] text-[var(--gov-text)] hover:bg-slate-50"
                :disabled="refreshing"
                @click="$emit('recompute')"
              >
                {{ refreshing ? '分析中…' : '重新分析' }}
              </button>
              <button
                class="rounded bg-[var(--gov-primary)] px-2 py-1 text-[11px] text-white hover:brightness-105"
                @click="$emit('open-batch-insights')"
              >
                查看质量概览
              </button>
              <button
                class="rounded bg-white px-2 py-1 text-[11px] text-[var(--gov-primary)] ring-1 ring-[var(--gov-border)] hover:bg-[var(--gov-primary-soft)]"
                @click="$emit('open-boundary-review')"
              >
                人工校核归并
              </button>
            </div>
          </div>
          <p v-if="metricsLoading" class="text-xs gov-muted">质量分析中…</p>
          <p v-else-if="metricsError" class="text-xs text-[var(--gov-danger)]">{{ metricsError }}</p>
          <div v-else-if="operationalMetrics" class="grid grid-cols-2 gap-2 text-xs text-[var(--gov-text)] md:grid-cols-4">
            <div class="rounded bg-white px-2 py-1">字段完整率：{{ pct(operationalMetrics.field_fill_rate?.recommended) }}</div>
            <div class="rounded bg-white px-2 py-1">待核对率：{{ pct(operationalMetrics.conflict_rate) }}</div>
            <div class="rounded bg-white px-2 py-1">整合可信度：{{ pct(operationalMetrics.avg_same_document_confidence) }}</div>
            <div class="rounded bg-white px-2 py-1">双路一致度：{{ pct(operationalMetrics.avg_rule_llm_agreement) }}</div>
          </div>
        </div>

        <div
          v-for="documentItem in mergedDocuments"
          :key="documentItem.key"
          class="rounded-xl border border-[var(--gov-border)] bg-white p-4"
        >
          <div class="mb-2 flex items-center justify-between">
            <div>
              <div class="text-sm font-semibold text-[var(--gov-text)]">归并文件 {{ documentItem.index }}</div>
              <p class="mt-1 text-xs gov-muted">{{ documentItem.sourceSummary }}</p>
            </div>
            <div class="text-xs gov-muted">整合可信度：{{ documentItem.sameDocumentConfidence.toFixed(2) }}</div>
          </div>

          <div class="mb-3 rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p class="mb-1 text-xs font-medium text-[var(--gov-text)]">归并文件名</p>
                <p class="text-sm font-semibold text-[var(--gov-text)]">{{ documentItem.displayName }}</p>
                <p v-if="documentItem.title" class="mt-1 text-xs gov-muted">题名建议：{{ documentItem.title }}</p>
              </div>
              <div class="text-right text-xs gov-muted">
                <p>归并页数：{{ documentItem.mergedPageCount || documentItem.sourceCount }}</p>
                <p>来源图片：{{ documentItem.sourceCount }} 张</p>
              </div>
            </div>

            <div v-if="documentItem.sourceBadges.length" class="mt-3 flex flex-wrap gap-2">
              <span
                v-for="(badge, idx) in documentItem.sourceBadges"
                :key="`${documentItem.key}-badge-${idx}`"
                class="rounded-full border border-[var(--gov-border)] bg-white px-2 py-1 text-[11px] text-[var(--gov-text-muted)]"
              >
                {{ badge }}
              </span>
            </div>

            <div class="mt-3 flex flex-wrap gap-2">
              <button
                v-if="documentItem.primaryTaskId"
                class="rounded border border-[var(--gov-border)] bg-white px-2 py-1 text-[11px] text-[var(--gov-primary)] hover:bg-[var(--gov-primary-soft)]"
                @click="$emit('open-task', documentItem.primaryTaskId)"
              >
                {{ documentItem.sourceCount > 1 ? '查看首页' : '查看文件' }}
              </button>
              <button
                v-for="(taskId, idx) in documentItem.taskIds"
                :key="`${documentItem.key}-task-${taskId}`"
                class="rounded border border-[var(--gov-border)] bg-white px-2 py-1 text-[11px] text-[var(--gov-text-muted)] hover:bg-slate-50"
                @click="$emit('open-task', taskId)"
              >
                查看来源页 {{ idx + 1 }}
              </button>
            </div>
          </div>

          <div class="mb-3 rounded-lg border border-[var(--gov-border)] bg-[var(--gov-primary-soft)] px-3 py-2">
            <p class="mb-1 text-xs font-medium text-[var(--gov-primary)]">判定依据</p>
            <p class="text-xs leading-5 text-[var(--gov-text)]">{{ documentItem.decisionReasons.join('；') || '-' }}</p>
          </div>

          <div v-if="documentItem.document" class="rounded-lg border border-emerald-100 bg-emerald-50/50 px-3 py-3">
            <div class="mb-2 flex items-center justify-between text-xs text-emerald-800">
              <span>合并页数：{{ documentItem.mergedPageCount }}</span>
              <span>协同一致度：{{ documentItem.agreementRatio.toFixed(2) }}</span>
            </div>
            <div class="grid gap-1 text-xs text-[var(--gov-text)] md:grid-cols-2">
              <div
                v-for="[field, value] in fieldEntries(documentItem.recommendedFields)"
                :key="`${documentItem.key}-${field}`"
                class="rounded bg-white px-2 py-1"
              >
                <span class="gov-muted">{{ field }}：</span>
                <span>{{ value || '-' }}</span>
              </div>
            </div>
            <p
              v-if="documentItem.conflictFields.length"
              class="mt-2 text-xs text-amber-700"
            >
              待核对字段：{{ documentItem.conflictFields.join('、') }}
            </p>
          </div>
        </div>

        <div
          v-if="mergeResult.summary.skipped_tasks?.length"
          class="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-700"
        >
          <p class="mb-1 font-medium">已跳过材料</p>
          <div v-for="task in mergeResult.summary.skipped_tasks" :key="`skip-${task.task_id}`">
            #{{ task.task_id }} {{ task.filename }}（{{ task.reason }}）
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { buildMergedDocumentViews } from '../utils/mergeDocumentDisplay.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  mergeResult: { type: Object, default: null },
  metrics: { type: Object, default: null },
  metricsLoading: { type: Boolean, default: false },
  metricsError: { type: String, default: '' },
  loadingMerge: { type: Boolean, default: false },
  mergeError: { type: String, default: '' },
  refreshing: { type: Boolean, default: false },
})

defineEmits(['close', 'recompute', 'open-batch-insights', 'open-boundary-review', 'open-task'])

const mergedDocuments = computed(() => buildMergedDocumentViews(props.mergeResult))
const operationalMetrics = computed(() => props.metrics?.operational_metrics || null)

function fieldEntries(fields) {
  return Object.entries(fields || {})
}

function pct(value) {
  const numeric = Number(value || 0)
  return `${(numeric * 100).toFixed(1)}%`
}
</script>
