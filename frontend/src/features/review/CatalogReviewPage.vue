<template>
  <AppShell>
    <template #review-toolbar>
      <div class="flex items-center gap-3">
        <span class="font-mono text-xs text-[var(--gov-text-muted)]">#{{ taskId }}</span>
        <StatusBadge :status="task?.status" />
        <span class="text-[11px] font-semibold text-emerald-600">著录审核</span>
        <!-- Field completion progress -->
        <div class="hidden sm:flex items-center gap-2 ml-2">
          <div class="w-24 h-1.5 rounded-full bg-slate-200 overflow-hidden">
            <div class="h-full rounded-full bg-emerald-500 transition-all duration-300" :style="{ width: overallProgress + '%' }"></div>
          </div>
          <span class="text-[11px] tabular-nums text-[var(--gov-text-muted)]">{{ completedDocCount }}/{{ docs.length }} 件</span>
        </div>
        <div class="hidden md:inline-flex items-center gap-1.5 ml-auto text-[11px] text-[var(--gov-text-muted)]">
          <span class="gov-kbd">&uarr;</span><span class="gov-kbd">&darr;</span> 切换
          <span class="gov-kbd ml-1">S</span> 保存
          <span class="gov-kbd ml-1">Enter</span> 提交
        </div>
      </div>
    </template>

    <div class="h-full flex bg-[var(--gov-bg)]">
      <div v-if="loadError" class="w-full flex items-center justify-center p-8">
        <div class="max-w-sm rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-center">
          <p class="text-sm text-red-700">{{ loadError }}</p>
          <button class="mt-3 text-xs font-medium text-red-600 hover:underline" @click="$router.back()">返回</button>
        </div>
      </div>

      <!-- Left: field form panel -->
      <aside v-if="!loadError" class="w-[340px] border-r border-[var(--gov-border)] bg-white flex flex-col flex-shrink-0">
        <!-- Doc selector bar -->
        <div class="h-10 px-3 border-b border-[var(--gov-border)] flex items-center gap-2">
          <button @click="prevDoc" :disabled="selectedDocIdx <= 0"
            class="h-6 w-6 flex items-center justify-center rounded text-slate-400 hover:text-[var(--gov-text)] hover:bg-slate-100 disabled:opacity-30 transition-colors">
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5"/></svg>
          </button>
          <div class="flex-1 min-w-0 text-center">
            <p class="text-xs font-medium text-[var(--gov-text)] truncate">{{ selectedDocTitle }}</p>
            <p class="text-[10px] text-[var(--gov-text-muted)]">{{ selectedDocIdx + 1 }} / {{ docs.length }}</p>
          </div>
          <button @click="nextDoc" :disabled="selectedDocIdx >= docs.length - 1"
            class="h-6 w-6 flex items-center justify-center rounded text-slate-400 hover:text-[var(--gov-text)] hover:bg-slate-100 disabled:opacity-30 transition-colors">
            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5"/></svg>
          </button>
        </div>

        <!-- Confidence overview badges -->
        <div v-if="fieldConfidences.length" class="px-3 py-2 border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)]">
          <div class="flex items-center justify-between mb-1.5">
            <span class="text-[10px] font-semibold text-slate-500">字段置信度</span>
            <button v-if="hasHighConfFields" @click="confirmAllHighConf"
              class="text-[10px] font-medium text-emerald-600 hover:text-emerald-700 hover:underline transition-colors">
              确认所有高置信
            </button>
          </div>
          <div class="flex items-center gap-1 flex-wrap">
            <span v-for="fc in fieldConfidences" :key="fc.key"
              class="inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium border cursor-pointer transition"
              :class="confBadgeClass(fc.confidence)"
              @click="scrollToField(fc.key)">
              {{ fc.label }}
              <span>{{ (fc.confidence * 100).toFixed(0) }}%</span>
            </span>
          </div>
        </div>

        <!-- Field form -->
        <div class="flex-1 overflow-y-auto px-3 py-3">
          <div class="space-y-3" ref="fieldFormRef">
            <div v-for="def in fieldDefs" :key="def.key" :id="'field-' + def.key"
              class="rounded-lg border p-2.5 transition-all"
              :class="isLowConfidence(def.key) ? 'border-amber-300 bg-amber-50/50 shadow-sm shadow-amber-100' : 'border-[var(--gov-border)] bg-white'">

              <label class="flex items-center gap-1.5 mb-1.5">
                <span class="text-[11px] font-semibold text-[var(--gov-text)]">{{ def.label }}</span>
                <span v-if="isLowConfidence(def.key)" class="text-[9px] rounded px-1 py-0.5 bg-amber-100 text-amber-700 font-semibold">低置信</span>
                <span v-if="fieldIsConfirmed(def.key)" class="text-[9px] rounded px-1 py-0.5 bg-green-100 text-green-700 font-semibold flex items-center gap-0.5">
                  <svg class="h-2.5 w-2.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5"/></svg>
                  已确认
                </span>
                <span v-if="def.source" class="ml-auto text-[9px] rounded px-1 py-0.5 bg-slate-100 text-slate-500">{{ def.source }}</span>
              </label>

              <!-- Tags input -->
              <div v-if="def.type === 'tags'" class="flex flex-wrap gap-1">
                <span v-for="(tag, ti) in (formModel[def.key] || [])" :key="ti"
                  class="inline-flex items-center gap-1 rounded-md bg-blue-50 border border-blue-200 px-2 py-0.5 text-[11px] text-blue-700">
                  {{ tag }}
                  <button @click="removeTag(def.key, ti)" class="hover:text-red-500 transition-colors">&times;</button>
                </span>
                <input class="flex-1 min-w-[80px] text-xs border-0 bg-transparent p-0 focus:ring-0 text-[var(--gov-text)]"
                  placeholder="输入标签按回车" @keydown.enter.prevent="addTag(def.key, $event)" />
              </div>

              <!-- Textarea -->
              <textarea v-else-if="def.type === 'textarea'" v-model="formModel[def.key]" @input="markFieldDirty(def.key)"
                class="w-full text-xs border border-[var(--gov-border)] rounded-md p-2 resize-none focus:ring-1 focus:ring-[var(--gov-primary)] focus:border-[var(--gov-primary)] bg-white transition-shadow" rows="2" />

              <!-- Select -->
              <select v-else-if="def.type === 'select'" v-model="formModel[def.key]" @change="markFieldDirty(def.key)"
                class="w-full text-xs border border-[var(--gov-border)] rounded-md p-2 focus:ring-1 focus:ring-[var(--gov-primary)] focus:border-[var(--gov-primary)] bg-white">
                <option v-for="opt in def.options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>

              <!-- Date -->
              <input v-else-if="def.type === 'date'" type="date" v-model="formModel[def.key]" @input="markFieldDirty(def.key)"
                class="w-full text-xs border border-[var(--gov-border)] rounded-md p-2 focus:ring-1 focus:ring-[var(--gov-primary)] focus:border-[var(--gov-primary)] bg-white" />

              <!-- Default text -->
              <input v-else type="text" v-model="formModel[def.key]" @input="markFieldDirty(def.key)"
                class="w-full text-xs border border-[var(--gov-border)] rounded-md p-2 focus:ring-1 focus:ring-[var(--gov-primary)] focus:border-[var(--gov-primary)] bg-white transition-shadow" />
            </div>
          </div>

          <!-- Preservation period rule -->
          <div v-if="preservationRule" class="mt-3 rounded-md border border-blue-200 bg-blue-50 p-2.5">
            <p class="text-[10px] font-semibold text-blue-600 mb-0.5">保管期限规则命中</p>
            <p class="text-xs text-blue-700 leading-relaxed">{{ preservationRule }}</p>
          </div>
        </div>

        <!-- Save / submit -->
        <div class="border-t border-[var(--gov-border)] p-3 space-y-2 flex-shrink-0">
          <div v-if="opMsg" class="rounded-md border p-2 text-[11px]" :class="opMsg.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'">
            {{ opMsg.text }}
          </div>
          <div class="flex gap-2">
            <button @click="saveMetadata" :disabled="saving"
              class="flex-1 h-9 text-[13px] rounded-md border border-[var(--gov-border)] text-[var(--gov-text)] hover:bg-slate-50 disabled:opacity-40 transition-colors flex items-center justify-center gap-1.5">
              <svg v-if="!saving" class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z"/></svg>
              {{ saving ? '保存中…' : '保存' }}
            </button>
            <button @click="submitApprove" :disabled="submitting"
              class="flex-1 h-9 text-[13px] font-semibold rounded-md bg-[var(--gov-primary)] text-white hover:bg-[var(--gov-primary-hover)] disabled:opacity-40 transition-colors">
              {{ submitting ? '提交中…' : '通过' }}
            </button>
            <button @click="openReject" class="h-9 px-3 text-[13px] rounded-md border border-red-200 text-red-600 hover:bg-red-50 transition-colors">
              驳回
            </button>
          </div>
        </div>
      </aside>

      <!-- Center: PDF preview -->
      <section v-if="!loadError" class="flex-1 min-w-0 flex flex-col bg-white">
        <div class="h-10 px-3 border-b border-[var(--gov-border)] flex items-center justify-between flex-shrink-0">
          <p class="text-sm font-medium text-[var(--gov-text)] truncate">{{ selectedDocTitle }}</p>
          <div class="flex items-center gap-2">
            <span class="text-[11px] text-[var(--gov-text-muted)] tabular-nums">{{ currentPage }}/{{ totalPages }}</span>
            <div class="flex items-center border border-[var(--gov-border)] rounded-md overflow-hidden">
              <button @click="zoomOut" class="h-6 w-6 flex items-center justify-center text-slate-500 hover:bg-slate-100 transition-colors">
                <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 12h-15"/></svg>
              </button>
              <span class="text-[10px] tabular-nums text-[var(--gov-text-muted)] w-10 text-center border-x border-[var(--gov-border)]">{{ Math.round(zoom * 100) }}%</span>
              <button @click="zoomIn" class="h-6 w-6 flex items-center justify-center text-slate-500 hover:bg-slate-100 transition-colors">
                <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M12 4.5v15m7.5-7.5h-15"/></svg>
              </button>
            </div>
          </div>
        </div>

        <div class="flex-1 min-h-0 overflow-auto">
          <div :style="{ transform: `scale(${zoom})`, transformOrigin: 'top center', minHeight: '100%' }">
            <PdfViewer v-if="previewUrl" :src="previewUrl" :page="currentPage" class="h-full" @page-change="(p) => (currentPage = p)" />
            <div v-else class="h-full flex items-center justify-center text-sm text-[var(--gov-text-muted)]">暂无预览</div>
          </div>
        </div>

        <!-- Page strip -->
        <div class="h-10 border-t border-[var(--gov-border)] px-2 flex items-center gap-1 overflow-x-auto flex-shrink-0 bg-[var(--gov-surface-muted)]">
          <button v-for="p in totalPages" :key="p" @click="currentPage = p"
            class="h-7 min-w-7 rounded-md text-[11px] font-medium transition-colors"
            :class="currentPage === p ? 'bg-[var(--gov-primary)] text-white' : 'text-[var(--gov-text-muted)] hover:bg-slate-100'">{{ p }}</button>
        </div>
      </section>

      <!-- Right: OCR candidates -->
      <aside v-if="!loadError" class="w-[280px] border-l border-[var(--gov-border)] bg-white flex flex-col flex-shrink-0">
        <div class="h-10 px-3 border-b border-[var(--gov-border)] flex items-center">
          <span class="text-[11px] font-semibold text-[var(--gov-text-muted)]">AI 候选 & OCR</span>
        </div>

        <!-- Candidates -->
        <div v-if="candidates.length" class="border-b border-[var(--gov-border)] px-3 py-3 bg-[var(--gov-surface-muted)]">
          <p class="text-[10px] font-semibold text-slate-500 tracking-wider mb-2">AI 候选值</p>
          <div class="space-y-2.5">
            <div v-for="c in candidates" :key="c.field" class="space-y-1">
              <div class="flex items-center gap-1.5">
                <span class="text-[11px] font-medium text-[var(--gov-text)]">{{ c.label }}</span>
                <span v-if="c.confidence != null" class="text-[10px] font-semibold tabular-nums" :class="confColor(c.confidence)">
                  {{ (c.confidence * 100).toFixed(0) }}%
                </span>
              </div>
              <div class="flex items-center gap-1 flex-wrap">
                <button v-for="(val, vi) in c.values" :key="vi" @click="adoptCandidate(c.field, val)"
                  class="text-[11px] rounded-md px-2 py-1 text-[var(--gov-primary)] bg-[var(--gov-primary-soft)] hover:bg-blue-100 transition-colors cursor-pointer border border-transparent hover:border-[var(--gov-primary)]/30"
                  :title="`采用: ${val}`">{{ val }}</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Tag suggestions -->
        <div v-if="tagSuggestions.length" class="border-b border-[var(--gov-border)] px-3 py-2.5">
          <p class="text-[10px] font-semibold text-slate-500 tracking-wider mb-1.5">推荐标签</p>
          <div class="flex flex-wrap gap-1">
            <button v-for="t in tagSuggestions" :key="t" @click="adoptTag(t)"
              class="text-[11px] rounded-full px-2.5 py-0.5 border border-purple-200 text-purple-600 bg-purple-50 hover:bg-purple-100 transition-colors">+ {{ t }}</button>
          </div>
        </div>

        <!-- OCR text -->
        <div class="flex-1 overflow-y-auto px-3 py-2.5">
          <p class="text-[10px] font-semibold text-slate-500 tracking-wider mb-1.5">当前页 OCR 文本</p>
          <pre class="text-xs whitespace-pre-wrap break-words leading-relaxed text-[var(--gov-text)] bg-[var(--gov-surface-muted)] rounded-md border border-[var(--gov-border)] p-2.5">{{ currentPageOcr || '（无文本）' }}</pre>
        </div>
      </aside>
    </div>

    <ReworkModal v-model="showReworkModal" :record-id="selectedDoc?.id || selectedDoc?.doc_id || String(taskId)" @submitted="handleReject" />
  </AppShell>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppShell from '@/layouts/AppShell.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import PdfViewer from '@/shared/components/PdfViewer.vue'
import ReworkModal from '@/shared/components/ReworkModal.vue'
import { getReviewTask, listDocUnits, getDocUnit, updateDocMetadata, submitReview } from '@/api/archive'

const route = useRoute()
const router = useRouter()
const taskId = route.params.taskId

const task = ref(null)
const docs = ref([])
const selectedDocIdx = ref(0)
const currentPage = ref(1)
const zoom = ref(1)
const loadError = ref('')
const saving = ref(false)
const submitting = ref(false)
const opMsg = ref(null)
const showReworkModal = ref(false)
const formModel = ref({})
const confirmedFields = ref(new Set())

const fieldDefs = [
  { key: 'title', label: '题名', source: 'llm' },
  { key: 'responsible', label: '责任者', source: 'llm' },
  { key: 'doc_no', label: '文号', source: 'rule' },
  { key: 'date', label: '形成日期', type: 'date', source: 'rule' },
  { key: 'preservation_period', label: '保管期限', type: 'select', source: 'rule', options: [
    { value: '', label: '请选择' }, { value: '永久', label: '永久' }, { value: '30年', label: '30年' }, { value: '10年', label: '10年' },
  ] },
  { key: 'tags', label: '主题标签', type: 'tags', source: 'manual' },
  { key: 'notes', label: '备注', type: 'textarea' },
]

const fieldConfidences = ref([])
const candidates = ref([])
const tagSuggestions = ref([])

const selectedDoc = computed(() => docs.value[selectedDocIdx.value] || null)
const selectedDocTitle = computed(() => selectedDoc.value?.title || selectedDoc.value?.name || '未选择文档')
const previewUrl = computed(() => selectedDoc.value?.pdf_url || selectedDoc.value?.preview_url || null)
const totalPages = computed(() => Math.max(Number(selectedDoc.value?.page_count || selectedDoc.value?.pages_count || 1), 1))
const completedDocCount = computed(() => docs.value.filter(d => d._fieldsSaved).length)
const overallProgress = computed(() => docs.value.length ? Math.round((completedDocCount.value / docs.value.length) * 100) : 0)
const hasHighConfFields = computed(() => fieldConfidences.value.some(fc => fc.confidence >= 0.8 && !confirmedFields.value.has(fc.key)))

const preservationRule = computed(() => {
  const ev = selectedDoc.value?.evidence || task.value?.evidence || {}
  return ev.preservation_rule || ev.period_rule_hit || null
})

const currentPageOcr = computed(() => {
  const pages = selectedDoc.value?.ocr_pages || selectedDoc.value?.pages || []
  if (!Array.isArray(pages)) return ''
  const p = pages.find(pg => Number(pg.page_no || pg.page || pg.index) === Number(currentPage.value))
  return p?.text || selectedDoc.value?.ocr_text || ''
})

function confColor(c) { return c == null ? 'text-slate-400' : c >= 0.8 ? 'text-green-600' : c >= 0.5 ? 'text-amber-600' : 'text-red-600' }
function confBadgeClass(c) { return c >= 0.8 ? 'border-green-300 text-green-700 bg-green-50' : c >= 0.5 ? 'border-amber-300 text-amber-700 bg-amber-50' : 'border-red-300 text-red-600 bg-red-50' }
function isLowConfidence(key) { const fc = fieldConfidences.value.find(f => f.key === key); return fc && fc.confidence < 0.6 }
function fieldIsConfirmed(key) { return confirmedFields.value.has(key) }
function fieldLabel(key) { return fieldDefs.find(d => d.key === key)?.label || key }
function scrollToField(key) { document.getElementById('field-' + key)?.scrollIntoView({ behavior: 'smooth', block: 'center' }) }
function zoomIn() { zoom.value = Math.min(zoom.value + 0.15, 3) }
function zoomOut() { zoom.value = Math.max(zoom.value - 0.15, 0.4) }

function markFieldDirty(key) { confirmedFields.value.add(key) }
function confirmAllHighConf() {
  fieldConfidences.value.forEach(fc => { if (fc.confidence >= 0.8) confirmedFields.value.add(fc.key) })
  opMsg.value = { ok: true, text: '已确认所有高置信字段' }
}

function adoptCandidate(field, value) {
  formModel.value = { ...formModel.value, [field]: value }
  confirmedFields.value.add(field)
  opMsg.value = { ok: true, text: `已采用 ${fieldLabel(field)}: ${value}` }
}
function adoptTag(tag) {
  const tags = formModel.value.tags || []
  if (!tags.includes(tag)) { formModel.value = { ...formModel.value, tags: [...tags, tag] } }
}
function removeTag(key, idx) {
  const tags = [...(formModel.value[key] || [])]; tags.splice(idx, 1)
  formModel.value = { ...formModel.value, [key]: tags }
}
function addTag(key, e) {
  const val = e.target.value.trim(); if (!val) return
  const tags = formModel.value[key] || []
  if (!tags.includes(val)) { formModel.value = { ...formModel.value, [key]: [...tags, val] } }
  e.target.value = ''
}

function extractCandidates(doc) {
  const result = []; const cands = doc?.candidates || doc?.field_candidates || {}
  for (const [field, info] of Object.entries(cands)) {
    const values = Array.isArray(info) ? info : (info?.values || (info?.value ? [info.value] : []))
    if (values.length) result.push({ field, label: fieldLabel(field), values: values.slice(0, 5), confidence: info?.confidence ?? null })
  }
  return result
}
function extractFieldConfidences(doc) {
  const result = []; const conf = doc?.confidence || doc?.confidence_json || doc?.field_confidences || {}
  for (const def of fieldDefs) { const c = conf[def.key]; if (c != null) result.push({ key: def.key, label: def.label, confidence: c }) }
  return result
}
function extractTagSuggestions(doc) {
  const vocab = doc?.tag_vocab || doc?.suggested_tags || doc?.evidence?.suggested_tags || []
  const current = formModel.value.tags || []
  return (Array.isArray(vocab) ? vocab : []).filter(t => !current.includes(t)).slice(0, 8)
}

function prevDoc() { if (selectedDocIdx.value > 0) { selectedDocIdx.value--; onDocChange() } }
function nextDoc() { if (selectedDocIdx.value < docs.value.length - 1) { selectedDocIdx.value++; onDocChange() } }

async function loadTask() {
  loadError.value = ''
  try {
    const res = await getReviewTask(taskId); task.value = res.data || null
    const taskDocs = task.value?.docs || task.value?.doc_units || []
    if (Array.isArray(taskDocs) && taskDocs.length) { docs.value = taskDocs.map(d => ({ ...d, _fieldsSaved: false })) }
    else if (task.value?.batch_id) { const r = await listDocUnits(task.value.batch_id); docs.value = (r.data?.items || r.data || []).map(d => ({ ...d, _fieldsSaved: false })) }
    else { docs.value = [] }
    if (docs.value.length) await onDocChange()
  } catch (error) { loadError.value = error?.response?.data?.detail || '加载审核任务失败，请返回重试。' }
}

async function onDocChange() {
  const doc = docs.value[selectedDocIdx.value]; if (!doc) return
  currentPage.value = 1; zoom.value = 1; confirmedFields.value = new Set()
  const metadata = doc?.metadata || doc?.fields || {}
  formModel.value = { title: metadata.title || '', responsible: metadata.responsible || '', doc_no: metadata.doc_no || '', date: metadata.date || '', preservation_period: metadata.preservation_period || '', tags: metadata.tags || [], notes: metadata.notes || '' }
  candidates.value = extractCandidates(doc); fieldConfidences.value = extractFieldConfidences(doc); tagSuggestions.value = extractTagSuggestions(doc)
  if (task.value?.batch_id && (doc?.id || doc?.doc_id)) {
    try {
      const detail = await getDocUnit(task.value.batch_id, doc.id || doc.doc_id); const d = detail.data || {}
      docs.value[selectedDocIdx.value] = { ...doc, ...d }; const fields = d.metadata || d.fields
      if (fields) formModel.value = { ...formModel.value, ...fields }
      candidates.value = extractCandidates(docs.value[selectedDocIdx.value])
      fieldConfidences.value = extractFieldConfidences(docs.value[selectedDocIdx.value])
      tagSuggestions.value = extractTagSuggestions(docs.value[selectedDocIdx.value])
    } catch { /* compat */ }
  }
  await nextTick()
  const lowField = fieldConfidences.value.find(fc => fc.confidence < 0.6)
  if (lowField) scrollToField(lowField.key)
}

async function saveMetadata() {
  if (!task.value?.batch_id || !(selectedDoc.value?.id || selectedDoc.value?.doc_id)) return
  saving.value = true; opMsg.value = null
  try {
    await updateDocMetadata(task.value.batch_id, selectedDoc.value.id || selectedDoc.value.doc_id, formModel.value)
    docs.value[selectedDocIdx.value]._fieldsSaved = true
    opMsg.value = { ok: true, text: '字段已保存' }
  } catch (error) { opMsg.value = { ok: false, text: '保存失败：' + (error?.response?.data?.detail || error.message || '未知错误') } }
  finally { saving.value = false }
}

async function submitApprove() {
  submitting.value = true; opMsg.value = null
  try {
    await submitReview(taskId, { decision: 'approve', doc_id: selectedDoc.value?.id || selectedDoc.value?.doc_id, metadata: formModel.value })
    router.push('/tasks')
  } catch (error) { opMsg.value = { ok: false, text: '提交失败：' + (error?.response?.data?.detail || error.message || '未知错误') } }
  finally { submitting.value = false }
}
function openReject() { showReworkModal.value = true }
async function handleReject(payload) {
  submitting.value = true; opMsg.value = null
  try {
    await submitReview(taskId, { decision: 'reject', reason: payload.description, rework: payload, doc_id: selectedDoc.value?.id || selectedDoc.value?.doc_id })
    showReworkModal.value = false; router.push('/tasks')
  } catch (error) { opMsg.value = { ok: false, text: '驳回失败：' + (error?.response?.data?.detail || error.message || '未知错误') } }
  finally { submitting.value = false }
}

function handleKeyboard(e) {
  const tag = e.target?.tagName?.toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return
  if (e.key === 'ArrowUp' && !e.ctrlKey) { e.preventDefault(); prevDoc() }
  else if (e.key === 'ArrowDown' && !e.ctrlKey) { e.preventDefault(); nextDoc() }
  else if (e.key === 's' && !e.ctrlKey && !e.metaKey) { e.preventDefault(); saveMetadata() }
  else if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submitApprove() }
}
onMounted(() => { loadTask(); document.addEventListener('keydown', handleKeyboard) })
onUnmounted(() => { document.removeEventListener('keydown', handleKeyboard) })
</script>
