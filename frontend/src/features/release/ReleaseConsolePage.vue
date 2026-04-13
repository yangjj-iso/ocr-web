<template>
  <AppShell>
    <template #review-toolbar>
      <div class="flex items-center gap-3">
        <span class="font-mono text-xs text-[var(--gov-text-muted)]">#{{ taskId }}</span>
        <StatusBadge :status="task?.status" />
        <span class="text-[11px] font-semibold text-purple-600">放行控制</span>
        <span v-if="refreshStatusText" class="hidden text-[11px] text-[var(--gov-text-muted)] lg:inline">{{ refreshStatusText }}</span>
        <button @click="handleManualRefresh" :disabled="refreshing" class="h-8 rounded-md border border-[var(--gov-border)] px-3 text-[11px] text-[var(--gov-text-muted)] hover:bg-slate-50 disabled:opacity-50">
          {{ refreshing ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </template>

    <div class="h-full flex flex-col bg-[var(--gov-bg)] overflow-y-auto">
      <div v-if="loadError" class="flex items-center justify-center p-8 flex-1">
        <div class="max-w-sm rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-center">
          <p class="text-sm text-red-700">{{ loadError }}</p>
          <button class="mt-3 text-xs font-medium text-red-600 hover:underline" @click="$router.back()">返回</button>
        </div>
      </div>

      <div v-else class="mx-auto max-w-[1200px] w-full px-5 py-4 space-y-4">

        <!-- Go / No-Go indicator -->
        <div class="rounded-lg border-2 p-4 flex items-center gap-4 transition-colors"
          :class="hasBlockingRisks ? 'border-red-300 bg-red-50' : 'border-green-300 bg-green-50'">
          <div class="flex-shrink-0 h-12 w-12 rounded-full flex items-center justify-center"
            :class="hasBlockingRisks ? 'bg-red-100' : 'bg-green-100'">
            <svg v-if="!hasBlockingRisks" class="h-7 w-7 text-green-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            <svg v-else class="h-7 w-7 text-red-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
            </svg>
          </div>
          <div class="min-w-0 flex-1">
            <p class="text-sm font-bold" :class="hasBlockingRisks ? 'text-red-800' : 'text-green-800'">
              {{ hasBlockingRisks ? '暂不可放行' : '可以放行' }}
            </p>
            <p class="text-xs mt-0.5" :class="hasBlockingRisks ? 'text-red-600' : 'text-green-600'">
              {{ hasBlockingRisks ? `存在 ${blockingCount} 个阻断项需先处理` : risks.length ? `${risks.length} 个提示项（非阻断）` : '所有检查项均通过' }}
            </p>
          </div>
          <button v-if="!hasBlockingRisks" @click="showReleaseConfirm = true" :disabled="submitting"
            class="flex-shrink-0 h-10 px-5 text-sm font-semibold rounded-lg bg-[var(--gov-primary)] text-white hover:bg-[var(--gov-primary-hover)] disabled:opacity-40 transition-colors flex items-center gap-2">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            Final 放行
          </button>
        </div>

        <!-- Stats row using StatCard -->
        <section>
          <h2 class="text-xs font-semibold text-slate-500 tracking-wider mb-2">整卷总览</h2>
          <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
            <StatCard label="总页数" :value="overview.total_pages ?? '—'" color="blue" />
            <StatCard label="文档件数" :value="overview.doc_count ?? '—'" color="purple" />
            <StatCard label="待审段数" :value="overview.pending_reviews ?? 0"
              :color="(overview.pending_reviews ?? 0) > 0 ? 'amber' : 'green'" />
            <StatCard label="返工状态" :value="(overview.open_rework ?? 0) + ' 未关闭'"
              :color="(overview.open_rework ?? 0) > 0 ? 'red' : 'green'" />
            <StatCard label="批次" :value="task?.batch_id ? task.batch_id.slice(-8) : '—'" color="slate" />
          </div>
        </section>

        <!-- Preflight checklist -->
        <section>
          <h2 class="text-xs font-semibold text-slate-500 tracking-wider mb-2">放行检查清单</h2>
          <div class="rounded-lg border border-[var(--gov-border)] bg-white overflow-hidden divide-y divide-[var(--gov-border)]">
            <!-- Passed checks -->
            <div v-for="check in checklistPassed" :key="check.label"
              class="flex items-center gap-3 px-4 py-2.5">
              <div class="flex-shrink-0 h-5 w-5 rounded-full bg-green-100 flex items-center justify-center">
                <svg class="h-3 w-3 text-green-600" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg>
              </div>
              <span class="text-xs text-[var(--gov-text)]">{{ check.label }}</span>
            </div>
            <!-- Risk items -->
            <div v-for="(risk, idx) in risks" :key="'risk-' + idx"
              class="flex items-center gap-3 px-4 py-2.5" :class="risk.level === 'high' ? 'bg-red-50/50' : 'bg-amber-50/50'">
              <div class="flex-shrink-0 h-5 w-5 rounded-full flex items-center justify-center"
                :class="risk.level === 'high' ? 'bg-red-100' : 'bg-amber-100'">
                <svg class="h-3 w-3" :class="risk.level === 'high' ? 'text-red-600' : 'text-amber-600'" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
                </svg>
              </div>
              <div class="flex-1 min-w-0">
                <span class="text-xs font-medium" :class="risk.level === 'high' ? 'text-red-700' : 'text-amber-700'">{{ risk.title }}</span>
                <span class="text-[11px] text-slate-500 ml-2">{{ risk.detail }}</span>
              </div>
              <span class="flex-shrink-0 text-[10px] font-semibold rounded px-2 py-0.5"
                :class="risk.level === 'high' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'">
                {{ risk.level === 'high' ? '阻断' : '提示' }}
              </span>
            </div>
            <div v-if="!risks.length && !checklistPassed.length" class="px-4 py-3 text-xs text-[var(--gov-text-muted)]">加载中…</div>
          </div>
        </section>

        <!-- Document units table -->
        <section v-if="docUnits.length">
          <h2 class="text-xs font-semibold text-slate-500 tracking-wider mb-2">文档单元 ({{ docUnits.length }})</h2>
          <div class="rounded-lg border border-[var(--gov-border)] bg-white overflow-hidden">
            <table class="w-full text-sm">
              <thead>
                <tr class="bg-slate-50 text-[11px] text-[var(--gov-text-muted)]">
                  <th class="px-3 py-2 text-left font-medium">#</th>
                  <th class="px-3 py-2 text-left font-medium">题名</th>
                  <th class="px-3 py-2 text-center font-medium">页数</th>
                  <th class="px-3 py-2 text-center font-medium">状态</th>
                  <th class="px-3 py-2 text-center font-medium">风险</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[var(--gov-border)]">
                <tr v-for="(du, idx) in docUnits" :key="du.id || idx" class="hover:bg-slate-50 transition-colors">
                  <td class="px-3 py-2 text-xs text-[var(--gov-text-muted)] tabular-nums">{{ idx + 1 }}</td>
                  <td class="px-3 py-2 text-xs text-[var(--gov-text)] truncate max-w-[200px]">{{ du.title || du.name || '—' }}</td>
                  <td class="px-3 py-2 text-xs text-center tabular-nums">{{ du.page_count || '—' }}</td>
                  <td class="px-3 py-2 text-center"><StatusBadge :status="du.status || 'pending'" /></td>
                  <td class="px-3 py-2 text-center">
                    <span v-if="du.risk_level && du.risk_level !== 'none'" class="text-[10px] font-semibold rounded px-1.5 py-0.5"
                      :class="du.risk_level === 'high' ? 'bg-red-100 text-red-700' : 'bg-amber-100 text-amber-700'">
                      {{ du.risk_level === 'high' ? '高' : '中' }}
                    </span>
                    <span v-else class="text-[10px] text-slate-300">—</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- Operation panel -->
        <section class="rounded-lg border border-[var(--gov-border)] bg-white p-4">
          <h2 class="text-xs font-semibold text-slate-500 tracking-wider mb-3">操作区</h2>
          <div v-if="opMsg" class="rounded-md border p-2 mb-3 text-sm" :class="opMsg.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'">
            {{ opMsg.text }}
          </div>
          <div class="flex flex-wrap gap-3">
            <button @click="openRework"
              class="inline-flex items-center gap-2 h-10 px-5 text-sm font-medium rounded-lg border border-amber-300 text-amber-700 bg-amber-50 hover:bg-amber-100 transition-colors">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"/></svg>
              返工
            </button>
            <button @click="doArchive" :disabled="submitting"
              class="inline-flex items-center gap-2 h-10 px-5 text-sm font-medium rounded-lg border border-[var(--gov-border)] text-[var(--gov-text)] bg-white hover:bg-slate-50 transition-colors disabled:opacity-40">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"/></svg>
              入库确认
            </button>
            <button @click="doExport" :disabled="exporting"
              class="inline-flex items-center gap-2 h-10 px-5 text-sm font-medium rounded-lg border border-[var(--gov-border)] text-[var(--gov-text)] bg-white hover:bg-slate-50 transition-colors disabled:opacity-40">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3"/></svg>
              {{ exporting ? '导出中…' : '导出终审 PDF' }}
            </button>
          </div>
        </section>
      </div>

      <!-- Release confirmation modal -->
      <Teleport to="body">
        <div v-if="showReleaseConfirm" class="gov-modal-backdrop" @click.self="showReleaseConfirm = false">
          <div class="gov-modal-panel max-w-md w-full">
            <div class="p-5 text-center">
              <div class="mx-auto h-14 w-14 rounded-full bg-[var(--gov-primary-soft)] flex items-center justify-center mb-3">
                <svg class="h-7 w-7 text-[var(--gov-primary)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                </svg>
              </div>
              <h3 class="text-base font-bold text-[var(--gov-text)]">确认放行</h3>
              <p class="text-sm text-[var(--gov-text-muted)] mt-2 leading-relaxed">
                放行后批次将进入归档流程，此操作不可撤销。共 <strong>{{ overview.doc_count ?? 0 }}</strong> 个文档单元、
                <strong>{{ overview.total_pages ?? 0 }}</strong> 页。
              </p>
              <div class="flex gap-3 mt-5 justify-center">
                <button @click="showReleaseConfirm = false"
                  class="h-9 px-5 text-sm rounded-md border border-[var(--gov-border)] text-[var(--gov-text)] hover:bg-slate-50 transition-colors">
                  取消
                </button>
                <button @click="doRelease" :disabled="submitting"
                  class="h-9 px-5 text-sm font-semibold rounded-md bg-[var(--gov-primary)] text-white hover:bg-[var(--gov-primary-hover)] disabled:opacity-40 transition-colors">
                  {{ submitting ? '处理中…' : '确认放行' }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </Teleport>

      <ReworkModal v-model="showReworkModal" :record-id="String(taskId)" @submitted="handleRework" />
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '@/layouts/AppShell.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import StatCard from '@/shared/components/StatCard.vue'
import ReworkModal from '@/shared/components/ReworkModal.vue'
import { getReviewTask, listDocUnits, releaseBatch, rejectRelease, exportBatchFinalPdf } from '@/api/archive'
import { formatRefreshTime } from '@/features/batches/progress'

const route = useRoute()
const router = useRouter()
const taskId = route.params.taskId

const task = ref(null)
const docUnits = ref([])
const loadError = ref('')
const submitting = ref(false)
const exporting = ref(false)
const opMsg = ref(null)
const showReworkModal = ref(false)
const showReleaseConfirm = ref(false)
const refreshing = ref(false)
const lastRefreshedAt = ref(null)

const AUTO_REFRESH_MS = 10000
const ACTIVE_RELEASE_TASK_STATUSES = new Set(['pending', 'processing', 'human_review', 'claimed', 'running'])
let releaseConsoleRefreshTimer = null

const overview = computed(() => {
  const t = task.value || {}; const ev = t.evidence || {}; const docsArr = docUnits.value
  return {
    total_pages: ev.total_pages ?? (docsArr.reduce((s, d) => s + (Number(d.page_count) || 0), 0) || t.total_pages),
    doc_count: ev.doc_count ?? (docsArr.length || t.doc_count),
    pending_reviews: ev.pending_reviews ?? t.pending_reviews ?? 0,
    open_rework: ev.open_rework ?? t.open_rework ?? 0,
    low_confidence_fields: ev.low_confidence_fields ?? 0,
    unconfirmed_tags: ev.unconfirmed_tags ?? 0,
  }
})

const risks = computed(() => {
  const out = []; const ov = overview.value
  if ((ov.open_rework ?? 0) > 0) out.push({ level: 'high', title: '未关闭返工任务', detail: `${ov.open_rework} 条返工任务尚未完成` })
  if ((ov.pending_reviews ?? 0) > 0) out.push({ level: 'medium', title: '待审段仍有遗留', detail: `${ov.pending_reviews} 段审核待处理` })
  if ((ov.low_confidence_fields ?? 0) > 0) out.push({ level: 'medium', title: '低置信度字段', detail: `${ov.low_confidence_fields} 个字段置信度偏低` })
  if ((ov.unconfirmed_tags ?? 0) > 0) out.push({ level: 'medium', title: '未确认标签', detail: `${ov.unconfirmed_tags} 个标签待确认` })
  const highRiskDocs = docUnits.value.filter(d => d.risk_level === 'high')
  if (highRiskDocs.length) out.push({ level: 'high', title: '高风险文档单元', detail: `${highRiskDocs.length} 个文档标记为高风险` })
  return out
})

const hasBlockingRisks = computed(() => risks.value.some(r => r.level === 'high'))
const blockingCount = computed(() => risks.value.filter(r => r.level === 'high').length)
const autoRefreshEnabled = computed(() => ACTIVE_RELEASE_TASK_STATUSES.has(String(task.value?.status || '').trim().toLowerCase()))
const refreshStatusText = computed(() => {
  const stamp = formatRefreshTime(lastRefreshedAt.value)
  if (autoRefreshEnabled.value) {
    return stamp ? `${stamp} 更新 · 当前放行页每10s自动刷新` : '当前放行页每10s自动刷新'
  }
  return stamp ? `${stamp} 更新` : ''
})

const checklistPassed = computed(() => {
  const out = []; const ov = overview.value
  if ((ov.open_rework ?? 0) === 0) out.push({ label: '无未关闭返工任务' })
  if ((ov.pending_reviews ?? 0) === 0) out.push({ label: '所有审核段已完成' })
  if ((ov.low_confidence_fields ?? 0) === 0) out.push({ label: '无低置信度字段' })
  if ((ov.unconfirmed_tags ?? 0) === 0) out.push({ label: '所有标签已确认' })
  if (!docUnits.value.some(d => d.risk_level === 'high')) out.push({ label: '无高风险文档单元' })
  return out
})

function extractArray(data, keys = ['items']) {
  for (const key of keys) {
    if (Array.isArray(data?.[key])) return data[key]
  }
  if (Array.isArray(data)) return data
  return []
}

async function loadTask(options = {}) {
  loadError.value = ''
  try {
    const res = await getReviewTask(taskId); task.value = res.data || null
    const taskDocs = task.value?.docs || task.value?.doc_units || []
    if (Array.isArray(taskDocs) && taskDocs.length) { docUnits.value = taskDocs }
    else if (task.value?.batch_id) { const r = await listDocUnits(task.value.batch_id); docUnits.value = extractArray(r.data) }
    lastRefreshedAt.value = new Date()
  } catch (error) { loadError.value = error?.response?.data?.detail || '加载放行任务失败，请返回重试。' }
}

function startAutoRefresh() {
  stopAutoRefresh()
  if (!autoRefreshEnabled.value) return
  releaseConsoleRefreshTimer = window.setInterval(() => {
    if (!document.hidden && !showReworkModal.value && !showReleaseConfirm.value && !submitting.value && !exporting.value) {
      loadTask({ silent: true })
    }
  }, AUTO_REFRESH_MS)
}

function stopAutoRefresh() {
  if (releaseConsoleRefreshTimer) {
    window.clearInterval(releaseConsoleRefreshTimer)
    releaseConsoleRefreshTimer = null
  }
}

async function handleManualRefresh() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    await loadTask()
  } finally {
    refreshing.value = false
  }
}

async function doRelease() {
  submitting.value = true; opMsg.value = null
  try {
    await releaseBatch(taskId); showReleaseConfirm.value = false
    opMsg.value = { ok: true, text: '放行成功，即将跳转…' }
    setTimeout(() => router.push('/tasks'), 1200)
  } catch (error) { opMsg.value = { ok: false, text: '放行失败：' + (error?.response?.data?.detail || error.message || '未知错误') } }
  finally { submitting.value = false }
}

async function doArchive() {
  submitting.value = true; opMsg.value = null
  try { await releaseBatch(taskId, { action: 'archive' }); opMsg.value = { ok: true, text: '入库确认已完成' } }
  catch (error) { opMsg.value = { ok: false, text: '入库失败：' + (error?.response?.data?.detail || error.message || '未知错误') } }
  finally { submitting.value = false }
}

async function doExport() {
  if (!task.value?.batch_id) { opMsg.value = { ok: false, text: '无法获取批次信息' }; return }
  exporting.value = true; opMsg.value = null
  try { await exportBatchFinalPdf(task.value.batch_id); opMsg.value = { ok: true, text: '终审 PDF 导出请求已提交' } }
  catch (error) { opMsg.value = { ok: false, text: '导出失败：' + (error?.response?.data?.detail || error.message || '未知错误') } }
  finally { exporting.value = false }
}

function openRework() { showReworkModal.value = true }
async function handleRework(payload) {
  submitting.value = true; opMsg.value = null
  try {
    await rejectRelease(taskId, payload.description, payload)
    showReworkModal.value = false
    opMsg.value = { ok: true, text: '已发起返工，即将跳转…' }; setTimeout(() => router.push('/tasks'), 1200)
  } catch (error) { opMsg.value = { ok: false, text: '返工失败：' + (error?.response?.data?.detail || error.message || '未知错误') } }
  finally { submitting.value = false }
}

watch(autoRefreshEnabled, (active) => {
  if (active) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

onMounted(loadTask)

onBeforeUnmount(() => {
  stopAutoRefresh()
})
</script>
