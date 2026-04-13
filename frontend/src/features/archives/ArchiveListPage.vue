<template>
  <AppShell>
    <div class="p-5 space-y-4">
      <div>
        <h1 class="gov-page-header">卷宗检索</h1>
      </div>

      <DataTable
        :columns="columns"
        :rows="rows"
        :total="total"
        :page="page"
        :page-size="pageSize"
        :loading="loading"
        row-key="record_id"
        clickable
        @row-click="openDetail"
        @page-change="onPageChange"
      >
        <template #filters>
          <div class="flex flex-wrap gap-3 items-center">
            <input
              v-model.trim="filters.q"
              @keyup.enter="reload"
              placeholder="题名 / 文号 / 责任者 / 关键词"
              class="gov-filter-input text-sm w-[300px]"
            />
            <input v-model="filters.dateFrom" type="date" class="gov-filter-input text-sm" />
            <input v-model="filters.dateTo" type="date" class="gov-filter-input text-sm" />
            <button @click="reload" class="gov-btn text-sm">检索</button>
            <button @click="reset" class="text-sm text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]">重置</button>
          </div>
        </template>

        <template #cell-status="{ value }">
          <StatusBadge :status="value || 'archived'" />
        </template>

        <template #cell-created_at="{ value }">
          <span class="text-sm text-[var(--gov-text-muted)]">{{ fmt(value) }}</span>
        </template>

        <template #actions="{ row }">
          <button @click.stop="openDetail(row)" class="text-xs text-[var(--gov-primary)] hover:underline">查看详情</button>
        </template>
      </DataTable>

      <div v-if="loadError" class="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {{ loadError }}
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'

import AppShell from '@/layouts/AppShell.vue'
import DataTable from '@/shared/components/DataTable.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import { listArchiveRecords } from '@/api/archive'

const router = useRouter()

const columns = [
  { key: 'record_id', label: '卷宗ID', width: '160px', mono: true },
  { key: 'title', label: '题名', width: '280px' },
  { key: 'doc_no', label: '文号', width: '170px' },
  { key: 'responsible', label: '责任者', width: '140px' },
  { key: 'status', label: '状态', width: '110px' },
  { key: 'created_at', label: '归档时间', width: '160px' },
]

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const loadError = ref('')

const filters = ref({ q: '', dateFrom: '', dateTo: '' })

function fmt(val) {
  return val ? dayjs(val).format('YYYY-MM-DD HH:mm') : '-'
}

function buildParams() {
  return {
    page: page.value,
    page_size: pageSize.value,
    q: filters.value.q || undefined,
    date_from: filters.value.dateFrom || undefined,
    date_to: filters.value.dateTo || undefined,
  }
}

function extractRows(data) {
  if (Array.isArray(data?.items)) return data.items
  if (Array.isArray(data?.records)) return data.records
  if (Array.isArray(data)) return data
  return []
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const res = await listArchiveRecords(buildParams())
    const data = res.data || {}
    rows.value = extractRows(data)
    total.value = data.total || rows.value.length
  } catch (e) {
    console.error('加载归档列表失败', e)
    loadError.value = '加载归档列表失败，请稍后重试。'
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function reload() {
  page.value = 1
  load()
}

function reset() {
  filters.value = { q: '', dateFrom: '', dateTo: '' }
  reload()
}

function onPageChange(p) {
  page.value = p
  load()
}

function openDetail(row) {
  const id = row.record_id || row.id
  if (!id) return
  router.push(`/archives/${id}`)
}

onMounted(load)
</script>
