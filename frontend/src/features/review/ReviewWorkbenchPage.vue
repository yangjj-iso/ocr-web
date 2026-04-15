<template>
  <AppShell>
    <template #review-toolbar>
      <div class="flex items-center gap-3">
        <span class="font-mono text-xs text-[var(--gov-text-muted)]">#{{ taskId }}</span>
        <StatusBadge :status="task?.status" />
        <div class="ml-auto flex items-center gap-2">
          <span v-if="refreshStatusText" class="hidden text-[11px] text-[var(--gov-text-muted)] lg:inline">{{ refreshStatusText }}</span>
          <button @click="handleManualRefresh" :disabled="refreshing" class="h-8 rounded-md border border-[var(--gov-border)] px-3 text-[11px] text-[var(--gov-text-muted)] hover:bg-slate-50 disabled:opacity-50">
            {{ refreshing ? '刷新中...' : '刷新' }}
          </button>
        </div>
        <span class="hidden sm:inline-flex items-center gap-1.5 text-[11px] text-[var(--gov-text-muted)]">
          <span class="gov-kbd">&#8593;</span><span class="gov-kbd">&#8595;</span> 切换文档
          <span class="ml-1 gov-kbd">S</span> 保存
          <span class="ml-1 gov-kbd">Enter</span> 提交
        </span>
      </div>
    </template>

    <div class="h-full flex bg-[var(--gov-bg)]">
      <!-- Load error -->
      <div v-if="loadError" class="w-full flex items-center justify-center p-8">
        <div class="max-w-sm rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-center">
          <p class="text-sm text-red-700">{{ loadError }}</p>
          <button class="mt-3 text-xs font-medium text-red-600 hover:underline" @click="$router.back()">返回</button>
        </div>
      </div>

      <!-- 左侧：文档导航 -->
      <aside v-if="!loadError" class="w-[220px] border-r border-[var(--gov-border)] bg-white flex flex-col flex-shrink-0">
        <div class="h-10 px-3 border-b border-[var(--gov-border)] flex items-center">
          <span class="text-[11px] font-medium text-[var(--gov-text-muted)]">文档 ({{ docs.length }})</span>
        </div>
        <div class="flex-1 overflow-y-auto py-1">
          <button
            v-for="(doc, idx) in docs"
            :key="doc.id || doc.doc_id || idx"
            @click="selectDoc(doc, idx)"
            class="group w-full flex items-center gap-2 px-3 py-2 text-left transition-colors"
            :class="selectedDocIndex === idx
              ? 'bg-[var(--gov-primary-soft)] border-l-2 border-l-[var(--gov-primary)]'
              : 'border-l-2 border-l-transparent hover:bg-slate-50'"
          >
            <span class="flex-shrink-0 w-5 h-5 rounded bg-slate-100 flex items-center justify-center text-[10px] font-medium text-[var(--gov-text-muted)]">{{ idx + 1 }}</span>
            <div class="min-w-0 flex-1">
              <p class="text-xs font-medium text-[var(--gov-text)] truncate leading-tight">{{ doc.title || doc.name || `文档 ${idx + 1}` }}</p>
              <p class="text-[10px] text-[var(--gov-text-muted)] mt-0.5">{{ doc.page_count || doc.pages || 0 }} 页
                <span v-if="doc.risk_level" class="text-amber-600 ml-1">{{ doc.risk_level }}</span>
              </p>
            </div>
            <StatusBadge :status="doc.status || 'pending'" />
          </button>
        </div>
      </aside>

      <!-- 中间：主预览 -->
      <section v-if="!loadError" class="flex-1 min-w-0 flex flex-col bg-white">
        <div class="h-10 px-3 border-b border-[var(--gov-border)] flex items-center justify-between flex-shrink-0">
          <div class="flex items-center gap-2 min-w-0">
            <p class="text-sm font-medium text-[var(--gov-text)] truncate">{{ selectedDocTitle }}</p>
            <span class="flex-shrink-0 text-[11px] text-[var(--gov-text-muted)] tabular-nums">{{ currentPage }}/{{ pageThumbs.length || 1 }}</span>
          </div>
          <button
            @click="showOcrText = !showOcrText"
            class="flex-shrink-0 px-2 py-1 text-[11px] rounded transition-colors"
            :class="showOcrText ? 'bg-[var(--gov-primary-soft)] text-[var(--gov-primary)]' : 'text-[var(--gov-text-muted)] hover:bg-slate-50'"
          >OCR</button>
        </div>

        <div class="flex-1 min-h-0 flex">
          <div class="flex-1 min-w-0 min-h-0">
            <PdfViewer
              v-if="previewPdfUrl"
              :src="previewPdfUrl"
              :page="currentPage"
              class="h-full"
              @page-change="(p) => (currentPage = p)"
            />
            <div v-else class="h-full flex items-center justify-center text-sm text-[var(--gov-text-muted)]">暂无预览</div>
          </div>
          <div v-if="showOcrText" class="w-[280px] border-l border-[var(--gov-border)] overflow-y-auto bg-[var(--gov-surface-muted)] flex-shrink-0">
            <div class="px-3 py-2 border-b border-[var(--gov-border)] sticky top-0 bg-[var(--gov-surface-muted)]">
              <span class="text-[11px] font-medium text-[var(--gov-text-muted)]">OCR 文本</span>
            </div>
            <pre class="px-3 py-2 text-xs whitespace-pre-wrap break-words leading-relaxed text-[var(--gov-text)]">{{ currentPageOcrText || '（无文本）' }}</pre>
          </div>
        </div>

        <div class="h-10 border-t border-[var(--gov-border)] px-2 flex items-center gap-1 overflow-x-auto flex-shrink-0">
          <button
            v-for="p in pageThumbs"
            :key="p"
            @click="currentPage = p"
            class="h-7 min-w-7 rounded text-[11px] font-medium transition-colors"
            :class="currentPage === p ? 'bg-[var(--gov-primary)] text-white' : 'text-[var(--gov-text-muted)] hover:bg-slate-100'"
          >{{ p }}</button>
        </div>
      </section>

      <!-- 右侧：字段表单与动作 -->
      <aside v-if="!loadError" class="w-[300px] border-l border-[var(--gov-border)] bg-white flex flex-col flex-shrink-0">
        <!-- 置信度指示条 -->
        <div v-if="fieldConfidences.length" class="h-10 px-3 border-b border-[var(--gov-border)] flex items-center gap-1 overflow-hidden">
          <span v-for="fc in fieldConfidences" :key="fc.key" class="text-[10px] rounded px-1.5 py-0.5" :class="confBadge(fc.confidence)">
            {{ fc.label }} {{ (fc.confidence * 100).toFixed(0) }}%
          </span>
        </div>

        <!-- 候选值：紧凑卡片 -->
        <div v-if="candidates.length" class="px-3 py-2 border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)]">
          <div class="space-y-1.5">
            <div v-for="c in candidates" :key="c.field" class="flex items-start gap-2">
              <span class="flex-shrink-0 text-[11px] font-medium text-[var(--gov-text-muted)] w-12 text-right pt-0.5">{{ fieldLabel(c.field) }}</span>
              <div class="flex items-center gap-1 flex-wrap flex-1">
                <button
                  v-for="(val, vi) in c.values"
                  :key="vi"
                  @click="adoptCandidate(c.field, val)"
                  class="text-[11px] rounded px-1.5 py-0.5 text-[var(--gov-primary)] bg-[var(--gov-primary-soft)] hover:bg-blue-100 transition-colors cursor-pointer"
                >{{ val }}</button>
                <span v-if="c.confidence != null" class="text-[10px] text-[var(--gov-text-muted)]">{{ (c.confidence * 100).toFixed(0) }}%</span>
              </div>
            </div>
          </div>
        </div>

        <div class="flex-1 overflow-y-auto px-3 py-2">
          <FieldForm v-model="formModel" :field-defs="fieldDefs" />
        </div>

        <!-- 操作区 -->
        <div class="border-t border-[var(--gov-border)] p-3 space-y-2 flex-shrink-0">
          <div v-if="opMsg" class="rounded border p-2 text-[11px]" :class="opMsg.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'">
            {{ opMsg.text }}
          </div>
          <div class="flex gap-2">
            <button @click="saveMetadata" :disabled="saving" class="flex-1 h-9 text-[13px] rounded-md border border-[var(--gov-border)] text-[var(--gov-text)] hover:bg-slate-50 disabled:opacity-40 transition-colors">
              {{ saving ? '保存中…' : '保存' }}
            </button>
            <button @click="submitApprove" :disabled="submitting" class="flex-1 h-9 text-[13px] font-medium rounded-md bg-[var(--gov-primary)] text-white hover:bg-[var(--gov-primary-hover)] disabled:opacity-40 transition-colors">
              通过
            </button>
            <button @click="openReject" class="h-9 px-3 text-[13px] rounded-md border border-red-200 text-red-600 hover:bg-red-50 transition-colors">
              驳回
            </button>
          </div>
        </div>
      </aside>
    </div>

    <ReworkModal
      v-model="showReworkModal"
      :record-id="selectedDoc?.id || selectedDoc?.doc_id || String(taskId)"
      @submitted="submitReject"
    />
  </AppShell>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import AppShell from '@/layouts/AppShell.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import PdfViewer from '@/shared/components/PdfViewer.vue'
import FieldForm from '@/shared/components/FieldForm.vue'
import ReworkModal from '@/shared/components/ReworkModal.vue'
import { formatRefreshTime } from '@/features/batches/progress'
import {
  getReviewTask,
  listDocUnits,
  getDocUnit,
  updateDocMetadata,
  submitReview,
} from '@/api/archive'

const route = useRoute()
const router = useRouter()
const taskId = route.params.taskId

const task = ref(null)
const docs = ref([])
const selectedDoc = ref(null)
const selectedDocIndex = ref(0)
const currentPage = ref(1)
const showOcrText = ref(false)
const loadError = ref('')
const refreshing = ref(false)
const lastRefreshedAt = ref(null)
const hasPendingEdits = ref(false)

const showReworkModal = ref(false)
const saving = ref(false)
const submitting = ref(false)
const opMsg = ref(null)

const formModel = ref({})

const fieldDefs = [
  { key: 'title', label: '题名', source: 'llm' },
  { key: 'responsible', label: '责任者', source: 'llm' },
  { key: 'doc_no', label: '文号', source: 'rule' },
  { key: 'date', label: '形成日期', type: 'date', source: 'rule' },
  { key: 'preservation_period', label: '保管期限', type: 'select', source: 'rule', options: [
    { value: '', label: '请选择' },
    { value: '永久', label: '永久' },
    { value: '30年', label: '30年' },
    { value: '10年', label: '10年' },
  ] },
  { key: 'tags', label: '主题标签', type: 'tags', source: 'manual' },
  { key: 'notes', label: '备注', type: 'textarea' },
]

const candidates = ref([])
const fieldConfidences = ref([])
const persistedFormSnapshot = ref('')

const AUTO_REFRESH_MS = 10000
const ACTIVE_REVIEW_TASK_STATUSES = new Set(['pending', 'processing', 'human_review', 'claimed', 'running'])
let reviewWorkbenchRefreshTimer = null

function buildFormModel(value = {}) {
  return {
    title: value?.title || '',
    responsible: value?.responsible || '',
    doc_no: value?.doc_no || '',
    date: value?.date || '',
    preservation_period: value?.preservation_period || '',
    tags: Array.isArray(value?.tags) ? [...value.tags] : [],
    notes: value?.notes || '',
  }
}

function snapshotFormModel(value) {
  return JSON.stringify(buildFormModel(value))
}

function getDocKey(doc) {
  const key = doc?.id ?? doc?.doc_id
  return key == null ? '' : String(key)
}

function getDocPageCount(doc) {
  const directCount = Number(doc?.page_count || doc?.pages_count)
  if (Number.isFinite(directCount) && directCount > 0) return directCount
  if (Array.isArray(doc?.ocr_pages)) return Math.max(doc.ocr_pages.length, 1)
  if (Array.isArray(doc?.pages)) return Math.max(doc.pages.length, 1)
  const fallback = Number(doc?.pages || 1)
  return Number.isFinite(fallback) && fallback > 0 ? fallback : 1
}

function fieldLabel(key) {
  const def = fieldDefs.find(d => d.key === key)
  return def?.label || key
}

function confBadge(c) {
  if (c >= 0.8) return 'border-green-300 text-green-700 bg-green-50'
  if (c >= 0.5) return 'border-amber-300 text-amber-700 bg-amber-50'
  return 'border-red-300 text-red-600 bg-red-50'
}

function adoptCandidate(field, value) {
  formModel.value = { ...formModel.value, [field]: value }
}

function extractCandidates(doc) {
  const result = []
  const cands = doc?.candidates || doc?.field_candidates || {}
  for (const [field, info] of Object.entries(cands)) {
    const values = Array.isArray(info) ? info : (info?.values || (info?.value ? [info.value] : []))
    if (values.length) {
      result.push({
        field,
        values: values.slice(0, 5),
        confidence: info?.confidence ?? null,
        reason: info?.reason || info?.source || null,
      })
    }
  }
  return result
}

function extractFieldConfidences(doc) {
  const result = []
  const conf = doc?.confidence || doc?.confidence_json || doc?.field_confidences || {}
  for (const def of fieldDefs) {
    const c = conf[def.key]
    if (c != null) {
      result.push({ key: def.key, label: def.label, confidence: c })
    }
  }
  return result
}

const selectedDocTitle = computed(() => selectedDoc.value?.title || selectedDoc.value?.name || '未选择文档')
const previewPdfUrl = computed(() => {
  return selectedDoc.value?.pdf_url || selectedDoc.value?.preview_url || selectedDoc.value?.file_url || null
})
const autoRefreshEnabled = computed(() => {
  const status = String(task.value?.status || '').trim().toLowerCase()
  return ACTIVE_REVIEW_TASK_STATUSES.has(status) && !hasPendingEdits.value
})
const refreshStatusText = computed(() => {
  const stamp = formatRefreshTime(lastRefreshedAt.value)
  if (hasPendingEdits.value) {
    return stamp ? `${stamp} 更新 · 存在未保存修改，已暂停自动刷新` : '存在未保存修改，已暂停自动刷新'
  }
  if (autoRefreshEnabled.value) {
    return stamp ? `${stamp} 更新 · 审核页每10s自动刷新` : '审核页每10s自动刷新'
  }
  return stamp ? `${stamp} 更新` : ''
})

const currentPageOcrText = computed(() => {
  const pages = selectedDoc.value?.ocr_pages || selectedDoc.value?.pages || []
  const pageObj = Array.isArray(pages)
    ? pages.find((p) => Number(p.page_no || p.page || p.index) === Number(currentPage.value))
    : null
  return pageObj?.text || selectedDoc.value?.ocr_text || ''
})

const pageThumbs = computed(() => {
  const count = getDocPageCount(selectedDoc.value)
  const max = Math.min(Math.max(count, 1), 12)
  return Array.from({ length: max }, (_, i) => i + 1)
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
  const previousDocKey = options.preserveSelection === false ? '' : getDocKey(selectedDoc.value)
  const previousPage = currentPage.value
  try {
    const res = await getReviewTask(taskId)
    task.value = res.data || null

    const taskDocs = task.value?.docs || task.value?.doc_units || []
    if (Array.isArray(taskDocs) && taskDocs.length) {
      docs.value = taskDocs
    } else if (task.value?.batch_id) {
      const r = await listDocUnits(task.value.batch_id)
      docs.value = extractArray(r.data)
    } else {
      docs.value = []
    }

    if (docs.value.length) {
      const nextIndex = previousDocKey
        ? docs.value.findIndex((doc) => getDocKey(doc) === previousDocKey)
        : 0
      const targetIndex = nextIndex >= 0 ? nextIndex : 0
      const preservePage = Boolean(previousDocKey) && targetIndex >= 0 && getDocKey(docs.value[targetIndex]) === previousDocKey
      await selectDoc(docs.value[targetIndex], targetIndex, { preservePage, page: previousPage })
    } else {
      selectedDoc.value = null
      selectedDocIndex.value = 0
      currentPage.value = 1
      formModel.value = buildFormModel()
      candidates.value = []
      fieldConfidences.value = []
      persistedFormSnapshot.value = snapshotFormModel(formModel.value)
      hasPendingEdits.value = false
    }
    lastRefreshedAt.value = new Date()
  } catch (error) {
    loadError.value = error?.response?.data?.detail || '加载审核任务失败，请返回重试。'
    console.error('加载审核任务失败', error)
  }
}

async function selectDoc(doc, idx, options = {}) {
  selectedDocIndex.value = idx
  selectedDoc.value = doc

  const metadata = doc?.metadata || doc?.fields || {}
  formModel.value = buildFormModel(metadata)

  candidates.value = extractCandidates(doc)
  fieldConfidences.value = extractFieldConfidences(doc)

  if (task.value?.batch_id && (doc?.id || doc?.doc_id)) {
    try {
      const detail = await getDocUnit(task.value.batch_id, doc.id || doc.doc_id)
      const d = detail.data || {}
      selectedDoc.value = { ...doc, ...d }
      const fields = d.metadata || d.fields
      if (fields) {
        formModel.value = buildFormModel({
          ...formModel.value,
          ...fields,
        })
      }
      candidates.value = extractCandidates(selectedDoc.value)
      fieldConfidences.value = extractFieldConfidences(selectedDoc.value)
    } catch {
      // 兼容后端未实现详情接口的情况
    }
  }

  const nextPage = Number(options.page || 1)
  const maxPage = getDocPageCount(selectedDoc.value)
  currentPage.value = options.preservePage ? Math.min(Math.max(nextPage, 1), maxPage) : 1
  persistedFormSnapshot.value = snapshotFormModel(formModel.value)
  hasPendingEdits.value = false
}

async function saveMetadata() {
  if (!task.value?.batch_id || !(selectedDoc.value?.id || selectedDoc.value?.doc_id)) return
  saving.value = true
  opMsg.value = null
  try {
    await updateDocMetadata(task.value.batch_id, selectedDoc.value.id || selectedDoc.value.doc_id, formModel.value)
    const nextMetadata = buildFormModel(formModel.value)
    selectedDoc.value = {
      ...selectedDoc.value,
      metadata: nextMetadata,
      fields: nextMetadata,
    }
    docs.value[selectedDocIndex.value] = selectedDoc.value
    persistedFormSnapshot.value = snapshotFormModel(formModel.value)
    hasPendingEdits.value = false
    opMsg.value = { ok: true, text: '字段已保存' }
  } catch (error) {
    console.error('保存元数据失败', error)
    opMsg.value = { ok: false, text: '保存失败：' + (error?.response?.data?.detail || error.message || '未知错误') }
  } finally {
    saving.value = false
  }
}

async function submitApprove() {
  submitting.value = true
  opMsg.value = null
  try {
    await submitReview(taskId, {
      decision: 'approve',
      doc_id: selectedDoc.value?.id || selectedDoc.value?.doc_id,
      metadata: formModel.value,
    })
    router.push('/tasks')
  } catch (error) {
    console.error('提交审核失败', error)
    opMsg.value = { ok: false, text: '提交失败：' + (error?.response?.data?.detail || error.message || '未知错误') }
  } finally {
    submitting.value = false
  }
}

function openReject() {
  showReworkModal.value = true
}

function startAutoRefresh() {
  stopAutoRefresh()
  if (!autoRefreshEnabled.value) return
  reviewWorkbenchRefreshTimer = window.setInterval(() => {
    if (!document.hidden && !showReworkModal.value && !saving.value && !submitting.value && !hasPendingEdits.value) {
      loadTask()
    }
  }, AUTO_REFRESH_MS)
}

function stopAutoRefresh() {
  if (reviewWorkbenchRefreshTimer) {
    window.clearInterval(reviewWorkbenchRefreshTimer)
    reviewWorkbenchRefreshTimer = null
  }
}

async function handleManualRefresh() {
  if (refreshing.value) return
  if (hasPendingEdits.value) {
    opMsg.value = { ok: false, text: '存在未保存修改，请先保存后再刷新' }
    return
  }
  refreshing.value = true
  try {
    await loadTask()
  } finally {
    refreshing.value = false
  }
}

async function submitReject(payload) {
  submitting.value = true
  opMsg.value = null
  try {
    await submitReview(taskId, {
      decision: 'reject',
      reason: payload.description,
      rework: payload,
      doc_id: selectedDoc.value?.id || selectedDoc.value?.doc_id,
    })
    showReworkModal.value = false
    router.push('/tasks')
  } catch (error) {
    console.error('驳回提交失败', error)
    opMsg.value = { ok: false, text: '驳回失败：' + (error?.response?.data?.detail || error.message || '未知错误') }
  } finally {
    submitting.value = false
  }
}

watch(formModel, (value) => {
  hasPendingEdits.value = snapshotFormModel(value) !== persistedFormSnapshot.value
}, { deep: true })

watch(autoRefreshEnabled, (active) => {
  if (active) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

onMounted(() => {
  loadTask()
  document.addEventListener('keydown', handleKeyboard)
})

onUnmounted(() => {
  stopAutoRefresh()
  document.removeEventListener('keydown', handleKeyboard)
})

function handleKeyboard(e) {
  // Ignore if user is typing in an input/textarea/select
  const tag = e.target?.tagName?.toLowerCase()
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return

  if (e.key === 'ArrowUp' && !e.ctrlKey) {
    e.preventDefault()
    if (selectedDocIndex.value > 0) selectDoc(docs.value[selectedDocIndex.value - 1], selectedDocIndex.value - 1)
  } else if (e.key === 'ArrowDown' && !e.ctrlKey) {
    e.preventDefault()
    if (selectedDocIndex.value < docs.value.length - 1) selectDoc(docs.value[selectedDocIndex.value + 1], selectedDocIndex.value + 1)
  } else if (e.key === 's' && !e.ctrlKey && !e.metaKey) {
    e.preventDefault()
    saveMetadata()
  } else if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submitApprove()
  }
}
</script>
