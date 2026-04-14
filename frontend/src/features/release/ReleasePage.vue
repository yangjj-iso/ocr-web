<template>
  <AppShell>
    <div class="p-5 space-y-4">
      <div class="flex items-center justify-between gap-3">
        <h1 class="gov-page-header">入库发布确认</h1>
        <div class="flex items-center gap-2">
          <span v-if="refreshStatusText" class="hidden text-xs text-[var(--gov-text-muted)] md:inline">{{ refreshStatusText }}</span>
          <button @click="handleManualRefresh" class="px-3 py-1.5 text-sm border border-[var(--gov-border)] text-[var(--gov-text-muted)] rounded-md hover:bg-slate-50 transition">
            刷新
          </button>
          <button @click="handleExport" :disabled="!selectedRow || exporting" class="px-3 py-1.5 text-sm border border-[var(--gov-primary)] text-[var(--gov-primary)] rounded-md hover:bg-blue-50 transition disabled:opacity-40">
            {{ exporting ? '导出中…' : '导出终审 PDF' }}
          </button>
        </div>
      </div>

      <!-- 批次概览 -->
      <div v-if="overview" class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div class="rounded-lg border border-[var(--gov-border)] bg-white p-3 text-center">
          <p class="text-xs text-[var(--gov-text-muted)]">总页数</p>
          <p class="text-lg font-semibold text-[var(--gov-text)]">{{ overview.total_pages ?? '-' }}</p>
        </div>
        <div class="rounded-lg border border-[var(--gov-border)] bg-white p-3 text-center">
          <p class="text-xs text-[var(--gov-text-muted)]">文档单元数</p>
          <p class="text-lg font-semibold text-[var(--gov-text)]">{{ overview.doc_count ?? '-' }}</p>
        </div>
        <div class="rounded-lg border border-[var(--gov-border)] bg-white p-3 text-center">
          <p class="text-xs text-[var(--gov-text-muted)]">待审段数</p>
          <p class="text-lg font-semibold text-amber-600">{{ overview.pending_reviews ?? '-' }}</p>
        </div>
        <div class="rounded-lg border border-[var(--gov-border)] bg-white p-3 text-center">
          <p class="text-xs text-[var(--gov-text-muted)]">未关闭返工</p>
          <p class="text-lg font-semibold" :class="(overview.open_rework ?? 0) > 0 ? 'text-red-600' : 'text-green-600'">{{ overview.open_rework ?? '-' }}</p>
        </div>
      </div>

      <!-- 风险摘要 -->
      <div v-if="risks.length" class="rounded-lg border border-amber-200 bg-amber-50 p-3">
        <p class="text-xs font-semibold text-amber-700 mb-1">风险提示</p>
        <ul class="list-disc list-inside text-sm text-amber-700 space-y-0.5">
          <li v-for="(r, i) in risks" :key="i">{{ r }}</li>
        </ul>
      </div>

      <DataTable
        :columns="columns"
        :rows="rows"
        :total="total"
        :page="page"
        :page-size="pageSize"
        :loading="loading"
        row-key="id"
        @page-change="onPageChange"
      >
        <template #filters>
          <div class="flex gap-3 items-center flex-wrap">
            <select v-model="status" @change="reload" class="gov-select text-sm">
              <option value="">全部状态</option>
              <option value="human_review">待确认</option>
              <option value="processing">处理中</option>
              <option value="done">已发布</option>
            </select>
            <button @click="reload" class="gov-btn text-sm">刷新</button>
          </div>
        </template>

        <template #cell-status="{ value }">
          <StatusBadge :status="value" />
        </template>

        <template #cell-created_at="{ value }">
          <span class="text-sm text-[var(--gov-text-muted)]">{{ fmt(value) }}</span>
        </template>

        <template #actions="{ row }">
          <div class="flex gap-2 justify-end">
            <button @click="selectRow(row)" class="text-xs text-[var(--gov-primary)] hover:underline">详情</button>
            <button @click="approve(row)" :disabled="submittingId === row.id" class="text-xs text-green-600 hover:underline disabled:opacity-50">发布</button>
            <button @click="askReject(row)" :disabled="submittingId === row.id" class="text-xs text-red-600 hover:underline disabled:opacity-50">驳回</button>
          </div>
        </template>
      </DataTable>

      <div v-if="loadError" class="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {{ loadError }}
      </div>

      <div v-if="opMsg" class="rounded-md border p-3 text-sm" :class="opMsg.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'">
        {{ opMsg.text }}
      </div>
    </div>

    <!-- 驳回弹窗 -->
    <div v-if="rejectingRow" class="gov-modal-backdrop">
      <div class="gov-modal-panel w-[460px] p-5">
        <h3 class="text-base font-semibold text-[var(--gov-text)]">驳回发布</h3>
        <p class="text-sm text-[var(--gov-text-muted)] mt-1">#{{ rejectingRow.id }}</p>
        <textarea v-model="rejectReason" rows="3" class="mt-4 w-full gov-filter-input text-sm resize-none" placeholder="请输入驳回原因"></textarea>
        <div class="mt-4 flex justify-end gap-2">
          <button @click="cancelReject" class="px-4 py-2 border border-[var(--gov-border)] rounded-md text-sm text-[var(--gov-text-muted)] hover:bg-slate-50 transition">取消</button>
          <button @click="confirmReject" :disabled="!rejectReason.trim()" class="px-4 py-2 bg-red-600 text-white rounded-md text-sm disabled:opacity-50 hover:bg-red-700 transition">确认驳回</button>
        </div>
      </div>
    </div>

    <!-- 详情抽屉 -->
    <DetailDrawer v-model="showDrawer" title="发布任务详情">
      <div v-if="selectedRow" class="space-y-4">
        <div class="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">任务ID</p>
            <p class="mt-0.5 font-mono text-[var(--gov-text)]">{{ selectedRow.id }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">批次ID</p>
            <p class="mt-0.5 font-mono text-[var(--gov-text)]">{{ selectedRow.batch_id || '-' }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">类型</p>
            <p class="mt-0.5 text-[var(--gov-text)]">{{ selectedRow.type || '-' }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">状态</p>
            <StatusBadge :status="selectedRow.status" />
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">创建时间</p>
            <p class="mt-0.5 text-[var(--gov-text)]">{{ fmt(selectedRow.created_at) }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">文档数</p>
            <p class="mt-0.5 text-[var(--gov-text)]">{{ selectedRow.doc_count ?? '-' }}</p>
          </div>
          <div class="col-span-2">
            <p class="text-xs text-[var(--gov-text-muted)]">备注</p>
            <p class="mt-0.5 text-[var(--gov-text)]">{{ selectedRow.note || selectedRow.remark || '-' }}</p>
          </div>
        </div>
      </div>
    </DetailDrawer>
  </AppShell>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import dayjs from 'dayjs'

import AppShell from '@/layouts/AppShell.vue'
import DataTable from '@/shared/components/DataTable.vue'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import { listPendingRelease, releaseBatch, rejectRelease, exportBatchFinalPdf } from '@/api/archive'
import { formatRefreshTime } from '@/features/batches/progress'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const status = ref('')
const loading = ref(false)
const submittingId = ref(null)
const loadError = ref('')
const exporting = ref(false)

const rejectingRow = ref(null)
const rejectReason = ref('')
const opMsg = ref(null)

const showDrawer = ref(false)
const selectedRow = ref(null)
const overview = ref(null)
const lastRefreshedAt = ref(null)

const AUTO_REFRESH_MS = 15000
const ACTIVE_RELEASE_STATUSES = new Set(['human_review', 'processing', 'pending', 'claimed', 'running'])
let releaseAutoRefreshTimer = null
let releaseLoadInFlight = false

const shouldPollReleases = computed(() => {
  const selectedStatus = String(status.value || '').trim().toLowerCase()
  if (!selectedStatus || ACTIVE_RELEASE_STATUSES.has(selectedStatus)) {
    return true
  }
  return rows.value.some((row) => ACTIVE_RELEASE_STATUSES.has(String(row?.status || '').trim().toLowerCase()))
})

const refreshStatusText = computed(() => {
  const stamp = formatRefreshTime(lastRefreshedAt.value)
  if (shouldPollReleases.value) {
    return stamp ? `${stamp} 更新 · 放行列表每15s自动刷新` : '放行列表每15s自动刷新'
  }
  return stamp ? `${stamp} 更新` : ''
})

const columns = [
  { key: 'id', label: '任务ID', width: '140px', mono: true },
  { key: 'batch_id', label: '批次ID', width: '180px' },
  { key: 'type', label: '类型', width: '120px' },
  { key: 'status', label: '状态', width: '120px' },
  { key: 'created_at', label: '创建时间', width: '170px' },
]

function fmt(v) {
  return v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'
}

// 风险摘要
const risks = computed(() => {
  if (!overview.value) return []
  const out = []
  if ((overview.value.open_rework ?? 0) > 0) out.push(`${overview.value.open_rework} 条未关闭返工任务`)
  if ((overview.value.low_confidence_fields ?? 0) > 0) out.push(`${overview.value.low_confidence_fields} 个字段置信度偏低 (<60%)`)
  if ((overview.value.unconfirmed_tags ?? 0) > 0) out.push(`${overview.value.unconfirmed_tags} 个标签未确认`)
  return out
})

function extractRows(data) {
  if (Array.isArray(data?.items)) return data.items
  if (Array.isArray(data?.tasks)) return data.tasks
  if (Array.isArray(data)) return data
  return []
}

function syncSelectedRow(nextRows) {
  if (!selectedRow.value?.id) return
  const nextSelected = nextRows.find((row) => String(row.id) === String(selectedRow.value.id))
  if (nextSelected) {
    selectedRow.value = nextSelected
  }
}

async function load(options = {}) {
  if (releaseLoadInFlight) return
  releaseLoadInFlight = true
  if (!options.silent) {
    loading.value = true
  }
  loadError.value = ''
  try {
    const res = await listPendingRelease({
      page: page.value,
      page_size: pageSize.value,
      status: status.value || undefined,
    })
    const data = res.data || {}
    rows.value = extractRows(data)
    total.value = data.total || rows.value.length
    syncSelectedRow(rows.value)
    // 如果后端返回 overview 字段则展示
    if (data.overview) overview.value = data.overview
    lastRefreshedAt.value = new Date()
  } catch (e) {
    console.error('加载发布列表失败', e)
    loadError.value = '加载发布列表失败，请稍后重试。'
    rows.value = []
    total.value = 0
  } finally {
    if (!options.silent) {
      loading.value = false
    }
    releaseLoadInFlight = false
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  if (!shouldPollReleases.value) return
  releaseAutoRefreshTimer = window.setInterval(() => {
    if (!document.hidden && !rejectingRow.value && !submittingId.value && !showDrawer.value && !exporting.value) {
      load({ silent: true })
    }
  }, AUTO_REFRESH_MS)
}

function stopAutoRefresh() {
  if (releaseAutoRefreshTimer) {
    window.clearInterval(releaseAutoRefreshTimer)
    releaseAutoRefreshTimer = null
  }
}

function reload() {
  page.value = 1
  load()
}

async function handleManualRefresh() {
  await load()
}

function onPageChange(p) {
  page.value = p
  load()
}

function selectRow(row) {
  selectedRow.value = row
  showDrawer.value = true
}

async function approve(row) {
  submittingId.value = row.id
  opMsg.value = null
  try {
    await releaseBatch(row.id)
    opMsg.value = { ok: true, text: '发布成功' }
    await load()
  } catch (e) {
    console.error('发布失败', e)
    opMsg.value = { ok: false, text: '发布失败：' + (e?.response?.data?.detail || e.message || '未知错误') }
  } finally {
    submittingId.value = null
  }
}

function askReject(row) {
  rejectingRow.value = row
  rejectReason.value = ''
}

function cancelReject() {
  rejectingRow.value = null
  rejectReason.value = ''
}

async function confirmReject() {
  if (!rejectingRow.value || !rejectReason.value.trim()) return
  submittingId.value = rejectingRow.value.id
  opMsg.value = null
  try {
    await rejectRelease(rejectingRow.value.id, rejectReason.value.trim())
    opMsg.value = { ok: true, text: '已驳回' }
    cancelReject()
    await load()
  } catch (e) {
    console.error('驳回失败', e)
    opMsg.value = { ok: false, text: '驳回失败：' + (e?.response?.data?.detail || e.message || '未知错误') }
  } finally {
    submittingId.value = null
  }
}

async function handleExport() {
  if (!selectedRow.value?.batch_id) {
    opMsg.value = { ok: false, text: '请先选择一个发布任务查看详情' }
    return
  }
  exporting.value = true
  opMsg.value = null
  try {
    await exportBatchFinalPdf(selectedRow.value.batch_id)
    opMsg.value = { ok: true, text: '终审 PDF 导出请求已提交' }
  } catch (e) {
    console.error('导出终审 PDF 失败', e)
    opMsg.value = { ok: false, text: '导出失败：' + (e?.response?.data?.detail || e.message || '未知错误') }
  } finally {
    exporting.value = false
  }
}

watch(shouldPollReleases, (active) => {
  if (active) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

onMounted(load)

onBeforeUnmount(() => {
  stopAutoRefresh()
})
</script>
