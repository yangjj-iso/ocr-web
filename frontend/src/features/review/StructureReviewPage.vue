<template>
  <AppShell>
    <template #review-toolbar>
      <div class="flex items-center gap-3">
        <span class="font-mono text-xs text-[var(--gov-text-muted)]">#{{ taskId }}</span>
        <StatusBadge :status="task?.status" />
        <span class="text-[11px] font-semibold text-[var(--gov-primary)]">结构审核</span>
        <!-- Progress -->
        <div class="hidden sm:flex items-center gap-2 ml-2">
          <div class="w-24 h-1.5 rounded-full bg-slate-200 overflow-hidden">
            <div class="h-full rounded-full bg-[var(--gov-primary)] transition-all duration-300" :style="{ width: progressPercent + '%' }"></div>
          </div>
          <span class="text-[11px] tabular-nums text-[var(--gov-text-muted)]">{{ confirmedCount }}/{{ docs.length }}</span>
        </div>
        <div class="hidden md:inline-flex items-center gap-1.5 ml-auto text-[11px] text-[var(--gov-text-muted)]">
          <span class="gov-kbd">&uarr;</span><span class="gov-kbd">&darr;</span> 切换件
          <span class="gov-kbd ml-1">Space</span> 确认
          <span class="gov-kbd ml-1">Enter</span> 提交
        </div>
      </div>
    </template>

    <div class="h-full flex bg-[var(--gov-bg)]">
      <!-- Loading / error -->
      <div v-if="loadError" class="w-full flex items-center justify-center p-8">
        <div class="max-w-sm rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-center">
          <p class="text-sm text-red-700">{{ loadError }}</p>
          <button class="mt-3 text-xs font-medium text-red-600 hover:underline" @click="$router.back()">返回</button>
        </div>
      </div>

      <!-- Left: doc list -->
      <aside v-if="!loadError" class="w-[260px] border-r border-[var(--gov-border)] bg-white flex flex-col flex-shrink-0">
        <div class="h-10 px-3 border-b border-[var(--gov-border)] flex items-center justify-between">
          <span class="text-[11px] font-semibold text-[var(--gov-text-muted)]">文档单元 ({{ docs.length }})</span>
          <div class="flex items-center gap-2">
            <span v-if="needAttentionCount > 0" class="text-[10px] font-semibold text-amber-600 bg-amber-50 rounded px-1.5 py-0.5">
              {{ needAttentionCount }} 需关注
            </span>
            <span v-else-if="docs.length > 0" class="text-[10px] font-semibold text-green-600 bg-green-50 rounded px-1.5 py-0.5">
              全部正常
            </span>
          </div>
        </div>

        <!-- Batch confirm -->
        <div v-if="hasUnconfirmedSafe" class="px-3 py-2 border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)]">
          <button @click="confirmAllSafe"
            class="w-full h-7 text-[11px] font-medium rounded-md border border-green-300 text-green-700 bg-green-50 hover:bg-green-100 transition-colors flex items-center justify-center gap-1.5">
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            确认所有低风险件
          </button>
        </div>

        <!-- Draggable doc list -->
        <div class="flex-1 overflow-y-auto py-1" ref="docListRef">
          <div
            v-for="(doc, idx) in docs"
            :key="doc.id || doc.doc_id || idx"
            class="group w-full flex items-center gap-2 px-3 py-2.5 text-left transition-all cursor-pointer select-none border-l-2"
            :class="[
              selectedIdx === idx
                ? 'bg-[var(--gov-primary-soft)] border-l-[var(--gov-primary)]'
                : doc._confirmed
                  ? 'border-l-green-400 bg-green-50/30 hover:bg-green-50/60'
                  : 'border-l-transparent hover:bg-slate-50',
              dragOverIdx === idx ? 'ring-2 ring-[var(--gov-primary)]/30 ring-inset' : ''
            ]"
            :draggable="true"
            @dragstart="onDragStart(idx, $event)"
            @dragover.prevent="dragOverIdx = idx"
            @dragleave="dragOverIdx = -1"
            @drop="onDrop(idx)"
            @click="selectDoc(idx)"
          >
            <!-- Confirmed check or sequence -->
            <span v-if="doc._confirmed" class="flex-shrink-0 w-5 h-5 rounded-full bg-green-500 flex items-center justify-center">
              <svg class="h-3 w-3 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg>
            </span>
            <span v-else class="flex-shrink-0 w-5 h-5 rounded flex items-center justify-center text-[10px] font-bold" :class="docSeqClass(doc)">
              {{ idx + 1 }}
            </span>

            <div class="min-w-0 flex-1">
              <p class="text-xs font-medium text-[var(--gov-text)] truncate leading-tight">{{ doc.title || doc.name || `件 ${idx + 1}` }}</p>
              <div class="flex items-center gap-2 mt-0.5">
                <span class="text-[10px] text-[var(--gov-text-muted)] tabular-nums">第{{ doc.start_page ?? '?' }}–{{ doc.end_page ?? '?' }}页</span>
                <span v-if="docConfidence(doc) != null" class="text-[10px] font-semibold tabular-nums" :class="confColor(docConfidence(doc))">
                  {{ (docConfidence(doc) * 100).toFixed(0) }}%
                </span>
              </div>
            </div>

            <span class="flex-shrink-0 text-slate-300 group-hover:text-slate-400 cursor-grab opacity-0 group-hover:opacity-100 transition-opacity">
              <svg class="h-3.5 w-3.5" fill="currentColor" viewBox="0 0 16 16"><circle cx="5" cy="3" r="1.2"/><circle cx="11" cy="3" r="1.2"/><circle cx="5" cy="8" r="1.2"/><circle cx="11" cy="8" r="1.2"/><circle cx="5" cy="13" r="1.2"/><circle cx="11" cy="13" r="1.2"/></svg>
            </span>

            <span v-if="doc.risk_level && doc.risk_level !== 'none'" class="flex-shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold"
              :class="riskTagClass(doc.risk_level)">
              {{ doc.risk_level === 'high' ? '高' : '中' }}
            </span>
          </div>
        </div>

        <!-- Structure operations -->
        <div class="border-t border-[var(--gov-border)] flex-shrink-0">
          <div class="px-2 py-2 grid grid-cols-2 gap-1.5">
            <button @click="mergeWithPrev" :disabled="selectedIdx <= 0"
              class="flex items-center justify-center gap-1 h-8 text-[11px] font-medium rounded-md border border-[var(--gov-border)] text-[var(--gov-text)] bg-white hover:bg-slate-50 disabled:opacity-30 transition-colors">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12h15m0 0l-6.75-6.75M19.5 12l-6.75 6.75"/></svg>
              合并前件
            </button>
            <button @click="splitAsNew" :disabled="selectedIdx < 0"
              class="flex items-center justify-center gap-1 h-8 text-[11px] font-medium rounded-md border border-[var(--gov-border)] text-[var(--gov-text)] bg-white hover:bg-slate-50 disabled:opacity-30 transition-colors">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5"/></svg>
              拆分新件
            </button>
            <button @click="setAsNextFirst" :disabled="selectedIdx < 0 || selectedIdx >= docs.length - 1"
              class="flex items-center justify-center gap-1 h-8 text-[11px] font-medium rounded-md border border-[var(--gov-border)] text-[var(--gov-text)] bg-white hover:bg-slate-50 disabled:opacity-30 transition-colors">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"/></svg>
              设为后件首页
            </button>
            <button @click="markEscalate" :disabled="selectedIdx < 0"
              class="flex items-center justify-center gap-1 h-8 text-[11px] font-medium rounded-md border border-amber-200 text-amber-700 bg-amber-50 hover:bg-amber-100 disabled:opacity-30 transition-colors">
              <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/></svg>
              标记升级
            </button>
          </div>
        </div>
      </aside>

      <!-- Center: page viewer -->
      <section v-if="!loadError" class="flex-1 min-w-0 flex flex-col bg-white">
        <div class="h-10 px-3 border-b border-[var(--gov-border)] flex items-center justify-between flex-shrink-0">
          <p class="text-sm font-medium text-[var(--gov-text)] truncate">{{ selectedDocTitle }}</p>
          <span class="text-[11px] text-[var(--gov-text-muted)] tabular-nums">{{ currentPage }}/{{ totalPages }}</span>
        </div>

        <div class="flex-1 min-h-0 flex">
          <div class="flex-1 min-w-0 min-h-0">
            <PdfViewer v-if="previewUrl" :src="previewUrl" :page="currentPage" class="h-full" @page-change="(p) => (currentPage = p)" />
            <div v-else class="h-full flex items-center justify-center text-sm text-[var(--gov-text-muted)]">暂无预览</div>
          </div>
        </div>

        <!-- Page thumbnails strip -->
        <div class="h-[52px] border-t border-[var(--gov-border)] px-2 flex items-center gap-1 overflow-x-auto flex-shrink-0 bg-[var(--gov-surface-muted)]">
          <template v-for="p in pageRange" :key="p">
            <div v-if="isBoundaryPage(p) && p !== pageRange[0]" class="w-px h-8 bg-amber-400 mx-0.5 flex-shrink-0 rounded-full"></div>
            <button @click="currentPage = p"
              class="h-10 min-w-10 rounded-md border transition-all flex flex-col items-center justify-center gap-0.5 flex-shrink-0"
              :class="currentPage === p
                ? 'border-[var(--gov-primary)] bg-[var(--gov-primary-soft)] ring-1 ring-[var(--gov-primary)]/30'
                : isBoundaryPage(p)
                  ? 'border-amber-300 bg-amber-50 hover:border-amber-400'
                  : 'border-[var(--gov-border)] bg-white hover:border-slate-300'">
              <span class="text-[11px] font-medium" :class="currentPage === p ? 'text-[var(--gov-primary)]' : 'text-[var(--gov-text-muted)]'">{{ p }}</span>
              <span v-if="isBoundaryPage(p)" class="w-1.5 h-1.5 rounded-full bg-amber-400"></span>
            </button>
          </template>
        </div>
      </section>

      <!-- Right: evidence & actions -->
      <aside v-if="!loadError" class="w-[300px] border-l border-[var(--gov-border)] bg-white flex flex-col flex-shrink-0">
        <!-- Tab bar -->
        <div class="h-10 px-3 border-b border-[var(--gov-border)] flex items-center gap-0.5 flex-shrink-0">
          <button v-for="tab in evidenceTabs" :key="tab.key" @click="activeTab = tab.key"
            class="h-7 px-2.5 text-[11px] font-medium rounded-md transition-colors"
            :class="activeTab === tab.key
              ? 'bg-[var(--gov-primary-soft)] text-[var(--gov-primary)]'
              : 'text-[var(--gov-text-muted)] hover:text-[var(--gov-text)] hover:bg-slate-50'">{{ tab.label }}</button>
        </div>

        <div class="flex-1 overflow-y-auto">
          <!-- Tab: boundary evidence -->
          <div v-show="activeTab === 'boundary'">
            <div class="px-3 py-3 border-b border-[var(--gov-border)]">
              <div class="flex items-center justify-between mb-2">
                <span class="text-[10px] font-semibold text-slate-500 tracking-wider">置信度</span>
                <span class="text-sm font-bold tabular-nums" :class="confColor(currentEvidence.confidence)">{{ confPercent }}%</span>
              </div>
              <div class="h-2 rounded-full bg-slate-100 overflow-hidden">
                <div class="h-full rounded-full transition-all duration-300" :style="{ width: confPercent + '%' }"
                  :class="confPercent >= 80 ? 'bg-green-500' : confPercent >= 50 ? 'bg-amber-500' : 'bg-red-500'"></div>
              </div>
            </div>

            <div class="px-3 py-3 border-b border-[var(--gov-border)]">
              <p class="text-[10px] font-semibold text-slate-500 tracking-wider mb-2">边界判定原因</p>
              <div v-if="currentEvidence.boundary_reason" class="rounded-md border border-slate-200 bg-[var(--gov-surface-muted)] p-2.5">
                <p class="text-xs text-[var(--gov-text)] leading-relaxed">{{ currentEvidence.boundary_reason }}</p>
              </div>
              <p v-else class="text-xs text-[var(--gov-text-muted)] italic">暂无判定信息</p>
            </div>

            <div class="px-3 py-3 border-b border-[var(--gov-border)]">
              <p class="text-[10px] font-semibold text-slate-500 tracking-wider mb-2">标题候选</p>
              <div v-if="currentEvidence.title_candidates?.length" class="space-y-1.5">
                <div v-for="(tc, i) in currentEvidence.title_candidates" :key="i"
                  class="rounded-md border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-2.5 py-1.5 text-xs text-[var(--gov-text)]">{{ tc }}</div>
              </div>
              <p v-else class="text-xs text-[var(--gov-text-muted)] italic">暂无</p>
            </div>

            <div class="px-3 py-3">
              <p class="text-[10px] font-semibold text-slate-500 tracking-wider mb-2">日期候选</p>
              <div v-if="currentEvidence.date_candidates?.length" class="flex flex-wrap gap-1.5">
                <span v-for="(dc, i) in currentEvidence.date_candidates" :key="i"
                  class="inline-block rounded-md bg-purple-50 border border-purple-200 px-2.5 py-1 text-xs text-purple-700 font-medium">{{ dc }}</span>
              </div>
              <p v-else class="text-xs text-[var(--gov-text-muted)] italic">暂无</p>
            </div>
          </div>

          <!-- Tab: OCR text -->
          <div v-show="activeTab === 'ocr'" class="p-3">
            <pre class="text-xs whitespace-pre-wrap break-words leading-relaxed text-[var(--gov-text)] max-h-[calc(100vh-280px)] overflow-y-auto bg-[var(--gov-surface-muted)] rounded-md border border-[var(--gov-border)] p-3">{{ currentPageOcr || '（当前页无OCR文本）' }}</pre>
          </div>
        </div>

        <!-- Action buttons -->
        <div class="border-t border-[var(--gov-border)] p-3 space-y-2 flex-shrink-0">
          <div v-if="opMsg" class="rounded-md border p-2 text-[11px]" :class="opMsg.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'">
            {{ opMsg.text }}
          </div>

          <button v-if="selectedDoc && !selectedDoc._confirmed" @click="confirmDoc(selectedIdx)"
            class="w-full h-9 text-[13px] font-medium rounded-md border border-green-300 text-green-700 bg-green-50 hover:bg-green-100 transition-colors flex items-center justify-center gap-1.5">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg>
            确认本件边界
          </button>
          <div v-else-if="selectedDoc?._confirmed" class="w-full h-9 rounded-md bg-green-50 border border-green-200 flex items-center justify-center gap-1.5 text-[13px] text-green-600 font-medium">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
            已确认
            <button @click="unconfirmDoc(selectedIdx)" class="text-[10px] text-green-500 hover:text-green-700 ml-1 underline">撤销</button>
          </div>

          <div class="flex gap-2">
            <button @click="submitStructure('approve')" :disabled="submitting || confirmedCount < docs.length"
              class="flex-1 h-9 text-[13px] font-semibold rounded-md bg-[var(--gov-primary)] text-white hover:bg-[var(--gov-primary-hover)] disabled:opacity-40 transition-colors">
              {{ submitting ? '提交中…' : '审核通过' }}
            </button>
            <button @click="openReject" class="h-9 px-3 text-[13px] rounded-md border border-red-200 text-red-600 hover:bg-red-50 transition-colors">
              驳回
            </button>
          </div>
          <p v-if="confirmedCount < docs.length" class="text-[10px] text-[var(--gov-text-muted)] text-center">
            请先确认所有件的边界后提交
          </p>
        </div>
      </aside>
    </div>

    <ReworkModal v-model="showReworkModal" :record-id="String(taskId)" @submitted="submitStructure('reject', $event)" />
  </AppShell>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '@/layouts/AppShell.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import PdfViewer from '@/shared/components/PdfViewer.vue'
import ReworkModal from '@/shared/components/ReworkModal.vue'
import { getReviewTask, listDocUnits, submitReview } from '@/api/archive'

const route = useRoute()
const router = useRouter()
const taskId = route.params.taskId

const task = ref(null)
const docs = ref([])
const selectedIdx = ref(0)
const currentPage = ref(1)
const loadError = ref('')
const submitting = ref(false)
const opMsg = ref(null)
const showReworkModal = ref(false)
const activeTab = ref('boundary')
const dragFrom = ref(-1)
const dragOverIdx = ref(-1)

const evidenceTabs = [
  { key: 'boundary', label: '边界证据' },
  { key: 'ocr', label: 'OCR 文本' },
]

const selectedDoc = computed(() => docs.value[selectedIdx.value] || null)
const selectedDocTitle = computed(() => selectedDoc.value?.title || selectedDoc.value?.name || '未选择文档')
const previewUrl = computed(() => selectedDoc.value?.pdf_url || selectedDoc.value?.preview_url || null)
const totalPages = computed(() => Number(selectedDoc.value?.page_count || selectedDoc.value?.pages?.length || 1))
const confirmedCount = computed(() => docs.value.filter(d => d._confirmed).length)
const progressPercent = computed(() => docs.value.length ? Math.round((confirmedCount.value / docs.value.length) * 100) : 0)
const needAttentionCount = computed(() => docs.value.filter(d => (d.risk_level && d.risk_level !== 'none') || (docConfidence(d) != null && docConfidence(d) < 0.6)).length)
const hasUnconfirmedSafe = computed(() => docs.value.some(d => !d._confirmed && (!d.risk_level || d.risk_level === 'none') && (docConfidence(d) == null || docConfidence(d) >= 0.6)))

const pageRange = computed(() => {
  const start = Number(selectedDoc.value?.start_page || 1)
  return Array.from({ length: totalPages.value }, (_, i) => start + i)
})

const currentEvidence = computed(() => {
  const ev = task.value?.evidence || selectedDoc.value?.evidence || {}
  const cands = selectedDoc.value?.candidates || selectedDoc.value?.field_candidates || {}
  return {
    boundary_reason: ev.boundary_reason || ev.reason || selectedDoc.value?.boundary_reason || null,
    confidence: ev.confidence ?? selectedDoc.value?.confidence ?? task.value?.confidence ?? null,
    title_candidates: cands.title?.values || (Array.isArray(cands.title) ? cands.title : []),
    date_candidates: cands.date?.values || (Array.isArray(cands.date) ? cands.date : []),
  }
})

const confPercent = computed(() => {
  const c = currentEvidence.value.confidence
  return c != null ? Math.round(c * 100) : 0
})

const currentPageOcr = computed(() => {
  const pages = selectedDoc.value?.ocr_pages || selectedDoc.value?.pages || []
  if (!Array.isArray(pages)) return ''
  const p = pages.find(pg => Number(pg.page_no || pg.page || pg.index) === Number(currentPage.value))
  return p?.text || ''
})

function docConfidence(doc) { return doc?.confidence ?? doc?.evidence?.confidence ?? null }
function confColor(c) { return c == null ? 'text-slate-400' : c >= 0.8 ? 'text-green-600' : c >= 0.5 ? 'text-amber-600' : 'text-red-600' }
function docSeqClass(doc) { return doc.risk_level === 'high' ? 'bg-red-100 text-red-700' : doc.risk_level === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-600' }
function riskTagClass(level) { return level === 'high' ? 'bg-red-100 text-red-700' : level === 'medium' ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500' }
function isBoundaryPage(p) { return docs.value.some(d => Number(d.start_page) === p) }

function confirmDoc(idx) {
  if (idx < 0 || idx >= docs.value.length) return
  docs.value[idx]._confirmed = true
  opMsg.value = { ok: true, text: `件 ${idx + 1} 已确认` }
  const next = docs.value.findIndex((d, i) => i > idx && !d._confirmed)
  if (next >= 0) setTimeout(() => selectDoc(next), 200)
}
function unconfirmDoc(idx) { if (idx >= 0 && idx < docs.value.length) docs.value[idx]._confirmed = false }
function confirmAllSafe() {
  let count = 0
  docs.value.forEach(d => {
    if (!d._confirmed && (!d.risk_level || d.risk_level === 'none')) {
      const c = docConfidence(d); if (c == null || c >= 0.6) { d._confirmed = true; count++ }
    }
  })
  opMsg.value = { ok: true, text: `已批量确认 ${count} 件` }
}

async function loadTask() {
  loadError.value = ''
  try {
    const res = await getReviewTask(taskId)
    task.value = res.data || null
    const taskDocs = task.value?.docs || task.value?.doc_units || []
    if (Array.isArray(taskDocs) && taskDocs.length) {
      docs.value = taskDocs.map(d => ({ ...d, _confirmed: false }))
    } else if (task.value?.batch_id) {
      const r = await listDocUnits(task.value.batch_id)
      docs.value = (r.data?.items || r.data || []).map(d => ({ ...d, _confirmed: false }))
    } else { docs.value = [] }
    if (docs.value.length) selectDoc(0)
  } catch (error) { loadError.value = error?.response?.data?.detail || '加载审核任务失败，请返回重试。' }
}
function selectDoc(idx) { selectedIdx.value = idx; currentPage.value = Number(docs.value[idx]?.start_page || 1) }

function onDragStart(idx, e) { dragFrom.value = idx; e.dataTransfer.effectAllowed = 'move' }
function onDrop(idx) {
  dragOverIdx.value = -1
  if (dragFrom.value < 0 || dragFrom.value === idx) return
  const list = [...docs.value]; const [moved] = list.splice(dragFrom.value, 1); list.splice(idx, 0, moved)
  docs.value = list; selectedIdx.value = idx; dragFrom.value = -1
  opMsg.value = { ok: true, text: '已调整顺序（本地）' }
}

function mergeWithPrev() {
  if (selectedIdx.value <= 0) return
  const prev = docs.value[selectedIdx.value - 1], cur = docs.value[selectedIdx.value]
  prev.end_page = cur.end_page || prev.end_page
  prev.page_count = (Number(prev.page_count) || 0) + (Number(cur.page_count) || 0)
  prev._confirmed = false; docs.value.splice(selectedIdx.value, 1)
  selectedIdx.value = Math.max(0, selectedIdx.value - 1)
  opMsg.value = { ok: true, text: '已合并到前件（本地）' }
}
function splitAsNew() {
  if (selectedIdx.value < 0) return
  const cur = docs.value[selectedIdx.value]
  const newDoc = { id: `new_${Date.now()}`, title: `拆分件（从第${currentPage.value}页）`, start_page: currentPage.value, end_page: cur.end_page, page_count: (Number(cur.end_page) || currentPage.value) - currentPage.value + 1, status: 'pending', risk_level: 'medium', _confirmed: false }
  cur.end_page = currentPage.value - 1; cur.page_count = (Number(cur.end_page) || 0) - (Number(cur.start_page) || 0) + 1; cur._confirmed = false
  docs.value.splice(selectedIdx.value + 1, 0, newDoc); selectedIdx.value += 1
  opMsg.value = { ok: true, text: '已拆分为新件（本地）' }
}
function setAsNextFirst() {
  if (selectedIdx.value < 0 || selectedIdx.value >= docs.value.length - 1) return
  const cur = docs.value[selectedIdx.value], next = docs.value[selectedIdx.value + 1]
  next.start_page = currentPage.value; cur.end_page = currentPage.value - 1
  cur.page_count = Math.max(0, (Number(cur.end_page) || 0) - (Number(cur.start_page) || 0) + 1)
  cur._confirmed = false; next._confirmed = false
  opMsg.value = { ok: true, text: '已设为后一件首页（本地）' }
}
function markEscalate() {
  if (selectedIdx.value < 0) return
  docs.value[selectedIdx.value].risk_level = 'high'; docs.value[selectedIdx.value].escalated = true; docs.value[selectedIdx.value]._confirmed = false
  opMsg.value = { ok: true, text: '已标记升级处理' }
}

async function submitStructure(decision, rejectPayload) {
  submitting.value = true; opMsg.value = null
  try {
    const payload = { decision, structure: docs.value.map((d, i) => ({ doc_id: d.id || d.doc_id, sequence: i, start_page: d.start_page, end_page: d.end_page, escalated: d.escalated || false })) }
    if (decision === 'reject' && rejectPayload) { payload.reason = rejectPayload.description; payload.rework = rejectPayload }
    await submitReview(taskId, payload); showReworkModal.value = false; router.push('/tasks')
  } catch (error) { opMsg.value = { ok: false, text: '提交失败：' + (error?.response?.data?.detail || error.message || '未知错误') } }
  finally { submitting.value = false }
}
function openReject() { showReworkModal.value = true }

function handleKeyboard(e) {
  const tag = e.target?.tagName?.toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return
  if (e.key === 'ArrowUp' && !e.ctrlKey) { e.preventDefault(); if (selectedIdx.value > 0) selectDoc(selectedIdx.value - 1) }
  else if (e.key === 'ArrowDown' && !e.ctrlKey) { e.preventDefault(); if (selectedIdx.value < docs.value.length - 1) selectDoc(selectedIdx.value + 1) }
  else if (e.key === ' ' && !e.shiftKey) { e.preventDefault(); if (selectedDoc.value && !selectedDoc.value._confirmed) confirmDoc(selectedIdx.value) }
  else if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (confirmedCount.value >= docs.value.length) submitStructure('approve') }
}
onMounted(() => { loadTask(); document.addEventListener('keydown', handleKeyboard) })
onUnmounted(() => { document.removeEventListener('keydown', handleKeyboard) })
</script>
