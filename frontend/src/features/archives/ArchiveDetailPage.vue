<template>
  <AppShell>
    <div class="p-6 h-[calc(100vh-56px)]">
      <div v-if="loadError" class="mb-4 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
        <svg class="mt-0.5 h-4 w-4 flex-shrink-0 text-red-400" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clip-rule="evenodd"/></svg>
        <span class="text-sm text-red-700">{{ loadError }}</span>
      </div>
      <div v-if="opMsg" class="mb-4 rounded-lg border p-3 text-sm" :class="opMsg.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'">
        {{ opMsg.text }}
      </div>
      <div class="h-full grid grid-cols-[280px_1fr_320px] gap-4">
        <!-- 左侧：卷宗信息 -->
        <section class="rounded-lg border border-[var(--gov-border)] bg-white p-4 overflow-y-auto">
          <h2 class="text-sm font-semibold text-[var(--gov-text)]">卷宗信息</h2>
          <div class="mt-3 space-y-3 text-sm">
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">卷宗ID</p>
              <p class="mt-0.5 text-sm font-mono text-[var(--gov-text)]">{{ record.record_id || record.id || '-' }}</p>
            </div>
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">题名</p>
              <p class="mt-0.5 text-sm text-[var(--gov-text)]">{{ record.title || '-' }}</p>
            </div>
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">文号</p>
              <p class="mt-0.5 text-sm text-[var(--gov-text)]">{{ record.doc_no || '-' }}</p>
            </div>
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">责任者</p>
              <p class="mt-0.5 text-sm text-[var(--gov-text)]">{{ record.responsible || '-' }}</p>
            </div>
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">形成日期</p>
              <p class="mt-0.5 text-sm text-[var(--gov-text)]">{{ record.date || '-' }}</p>
            </div>
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">保管期限</p>
              <p class="mt-0.5 text-sm text-[var(--gov-text)]">{{ record.preservation_period || '-' }}</p>
            </div>
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">归档时间</p>
              <p class="mt-0.5 text-sm text-[var(--gov-text)]">{{ fmt(record.created_at) }}</p>
            </div>
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">状态</p>
              <div class="mt-1"><StatusBadge :status="record.status || 'archived'" /></div>
            </div>
          </div>

          <!-- 下载 PDF -->
          <div class="mt-4 pt-3 border-t border-[var(--gov-border)]">
            <button @click="handleDownloadPdf" :disabled="downloading" class="w-full gov-btn text-sm disabled:opacity-50">
              {{ downloading ? '下载中...' : '下载 PDF' }}
            </button>
          </div>

          <!-- 文档单元列表 -->
          <div v-if="docUnits.length" class="mt-4 pt-3 border-t border-[var(--gov-border)]">
            <p class="text-xs font-semibold text-[var(--gov-text-muted)] mb-2">文档单元（{{ docUnits.length }}）</p>
            <div class="space-y-1">
              <div v-for="d in docUnits" :key="d.doc_id || d.id" class="rounded border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] p-2">
                <p class="text-xs font-medium text-[var(--gov-text)] truncate">{{ d.title || d.metadata?.title || `文档 ${d.sort_index || d.doc_id}` }}</p>
                <div class="flex items-center justify-between mt-1">
                  <span class="text-[10px] text-[var(--gov-text-muted)]">页 {{ d.start_page ?? '-' }}–{{ d.end_page ?? '-' }}</span>
                  <StatusBadge :status="d.status" />
                </div>
              </div>
            </div>
          </div>

          <!-- 版本历史 -->
          <div v-if="versions.length" class="mt-4 pt-3 border-t border-[var(--gov-border)]">
            <p class="text-xs font-semibold text-[var(--gov-text-muted)] mb-2">版本历史</p>
            <div class="space-y-1">
              <div v-for="v in versions" :key="v.version_no || v.id" class="flex items-center justify-between rounded border border-[var(--gov-border)] bg-white p-2">
                <div>
                  <p class="text-xs font-medium text-[var(--gov-text)]">v{{ v.version_no || v.id }}</p>
                  <p class="text-[10px] text-[var(--gov-text-muted)]">{{ v.version_type || '-' }}</p>
                </div>
                <span class="text-[10px] text-[var(--gov-text-muted)]">{{ fmt(v.created_at) }}</span>
              </div>
            </div>
          </div>
        </section>

        <!-- 中间：PDF预览 -->
        <section class="rounded-lg border border-[var(--gov-border)] bg-white overflow-hidden">
          <PdfViewer :src="pdfUrl" class="h-full" />
        </section>

        <!-- 右侧：问题提报 -->
        <section class="rounded-lg border border-[var(--gov-border)] bg-white p-4 flex flex-col">
          <h2 class="text-sm font-semibold text-[var(--gov-text)]">问题反馈</h2>

          <div class="mt-4 rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] p-3">
            <p class="text-xs text-[var(--gov-text-muted)]">最近返工状态</p>
            <p class="mt-1 text-sm text-[var(--gov-text)]">{{ reworkHint }}</p>
          </div>

          <div class="mt-auto pt-4">
            <button @click="showModal = true" class="w-full gov-btn text-sm">
              提报返工
            </button>
          </div>
        </section>
      </div>
    </div>

    <ReworkModal
      v-model="showModal"
      :record-id="String(record.record_id || record.id || route.params.id)"
      @submitted="handleSubmitRework"
    />
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import dayjs from 'dayjs'

import AppShell from '@/layouts/AppShell.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import PdfViewer from '@/shared/components/PdfViewer.vue'
import ReworkModal from '@/shared/components/ReworkModal.vue'
import { getArchiveRecord, createReworkTask, downloadArchivePdf, listDocUnits } from '@/api/archive'

const route = useRoute()
const showModal = ref(false)
const record = ref({})
const docUnits = ref([])
const versions = ref([])
const loadError = ref('')
const opMsg = ref(null)
const downloading = ref(false)

const pdfUrl = computed(() => {
  return record.value.pdf_url || record.value.file_url || docUnits.value[0]?.pdf_url || docUnits.value[0]?.preview_url || null
})
const reworkHint = computed(() => record.value.last_rework_status || '暂无')

function fmt(v) {
  return v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'
}

async function load() {
  loadError.value = ''
  try {
    const res = await getArchiveRecord(route.params.id)
    record.value = res.data || {}
    docUnits.value = record.value.doc_units || record.value.docs || []
    versions.value = record.value.versions || record.value.doc_versions || []
    if (!docUnits.value.length && record.value.batch_id) {
      try {
        const docsRes = await listDocUnits(record.value.batch_id)
        const items = Array.isArray(docsRes.data?.items) ? docsRes.data.items : []
        docUnits.value = items
      } catch (detailError) {
        console.warn('加载归档文档单元失败', detailError)
      }
    }
  } catch (e) {
    loadError.value = e?.response?.data?.detail || '加载归档详情失败，请稍后重试。'
    console.error('加载归档详情失败', e)
  }
}

async function handleDownloadPdf() {
  downloading.value = true
  opMsg.value = null
  try {
    const res = await downloadArchivePdf(record.value.record_id || record.value.id || route.params.id)
    const blob = new Blob([res.data], { type: 'application/pdf' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${record.value.title || record.value.record_id || 'archive'}.pdf`
    a.click()
    URL.revokeObjectURL(url)
    opMsg.value = { ok: true, text: 'PDF 下载成功' }
  } catch (e) {
    opMsg.value = { ok: false, text: '下载失败：' + (e?.response?.data?.detail || e.message || '未知错误') }
  } finally {
    downloading.value = false
  }
}

async function handleSubmitRework(payload) {
  try {
    await createReworkTask({
      record_id: record.value.record_id || record.value.id || route.params.id,
      ...payload,
    })
    showModal.value = false
    opMsg.value = { ok: true, text: '返工提报已提交' }
    await load()
  } catch (e) {
    opMsg.value = { ok: false, text: '提报失败：' + (e?.response?.data?.detail || e.message || '未知错误') }
    console.error('提报返工失败', e)
  }
}

onMounted(load)
</script>
