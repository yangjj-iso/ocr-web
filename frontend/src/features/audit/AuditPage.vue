<template>
  <AppShell>
    <div class="p-5 space-y-4">
      <div>
        <h1 class="gov-page-header">审计日志</h1>
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
          <div class="flex flex-wrap gap-3 items-center">
            <select v-model="filters.action" @change="reload" class="gov-select text-sm">
              <option value="">全部动作</option>
              <option value="workflow_start">工作流启动</option>
              <option value="claim">认领</option>
              <option value="submit">提交审核</option>
              <option value="rework_request">返工申请</option>
            </select>
            <input v-model.trim="filters.keyword" @keyup.enter="reload" placeholder="任务ID / 批次ID / 备注" class="gov-filter-input text-sm w-[260px]" />
            <button @click="reload" class="gov-btn text-sm">查询</button>
            <button @click="reset" class="text-sm text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]">重置</button>
          </div>
        </template>

        <template #cell-action="{ value }">
          <span class="text-xs rounded px-2 py-0.5 border" :class="actionClass(value)">{{ actionLabel(value) }}</span>
        </template>

        <template #cell-occurred_at="{ value }">
          <span class="text-sm text-[var(--gov-text-muted)]">{{ fmt(value) }}</span>
        </template>

        <template #actions="{ row }">
          <button @click="viewDetail(row)" class="text-xs text-[var(--gov-primary)] hover:underline">详情</button>
        </template>
      </DataTable>

      <div v-if="error" class="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {{ error }}
      </div>
    </div>

    <!-- 详情抽屉 -->
    <DetailDrawer v-model="showDrawer" title="审计详情">
      <div v-if="drawerRow" class="space-y-4">
        <div class="grid grid-cols-2 gap-3 text-sm">
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">ID</p>
            <p class="mt-0.5 font-mono text-[var(--gov-text)]">{{ drawerRow.id }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">动作</p>
            <span class="text-xs rounded px-2 py-0.5 border" :class="actionClass(drawerRow.action)">{{ actionLabel(drawerRow.action) }}</span>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">审核任务ID</p>
            <p class="mt-0.5 font-mono text-[var(--gov-text)]">{{ drawerRow.review_task_id || '-' }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">批次ID</p>
            <p class="mt-0.5 font-mono text-[var(--gov-text)]">{{ drawerRow.batch_id || '-' }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">操作人</p>
            <p class="mt-0.5 text-[var(--gov-text)]">{{ drawerRow.operator_name || '-' }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">操作时间</p>
            <p class="mt-0.5 text-[var(--gov-text)]">{{ fmt(drawerRow.occurred_at) }}</p>
          </div>
          <div class="col-span-2">
            <p class="text-xs text-[var(--gov-text-muted)]">备注</p>
            <p class="mt-0.5 text-sm text-[var(--gov-text)]">{{ drawerRow.note || '-' }}</p>
          </div>
        </div>

        <!-- 变更前后快照 -->
        <div v-if="drawerRow.before_snapshot || drawerRow.after_snapshot" class="space-y-3">
          <div v-if="drawerRow.before_snapshot">
            <p class="text-xs font-semibold text-[var(--gov-text-muted)] mb-1">变更前</p>
            <pre class="rounded border border-[var(--gov-border)] bg-red-50/50 p-2 text-xs whitespace-pre-wrap break-words leading-5">{{ formatSnapshot(drawerRow.before_snapshot) }}</pre>
          </div>
          <div v-if="drawerRow.after_snapshot">
            <p class="text-xs font-semibold text-[var(--gov-text-muted)] mb-1">变更后</p>
            <pre class="rounded border border-[var(--gov-border)] bg-green-50/50 p-2 text-xs whitespace-pre-wrap break-words leading-5">{{ formatSnapshot(drawerRow.after_snapshot) }}</pre>
          </div>
        </div>
      </div>
    </DetailDrawer>
  </AppShell>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import dayjs from 'dayjs'

import AppShell from '@/layouts/AppShell.vue'
import DataTable from '@/shared/components/DataTable.vue'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import { listAuditLogs } from '@/api/archive'

const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const error = ref('')

const filters = ref({ action: '', keyword: '' })
const showDrawer = ref(false)
const drawerRow = ref(null)

const columns = [
  { key: 'id', label: 'ID', width: '80px', mono: true },
  { key: 'review_task_id', label: '任务ID', width: '140px', mono: true },
  { key: 'batch_id', label: '批次ID', width: '140px', mono: true },
  { key: 'action', label: '动作', width: '110px' },
  { key: 'operator_name', label: '操作人', width: '120px' },
  { key: 'note', label: '备注', muted: true },
  { key: 'occurred_at', label: '操作时间', width: '170px' },
]

function fmt(v) {
  return v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'
}

const actionLabels = {
  workflow_start: '启动工作流',
  claim: '认领',
  submit: '提交审核',
  rework_request: '返工申请',
}
function actionLabel(v) {
  return actionLabels[v] || v || '-'
}

function actionClass(action) {
  const a = String(action || '').toLowerCase()
  if (a === 'submit') return 'border-green-300 text-green-700 bg-green-50'
  if (a === 'rework_request') return 'border-red-300 text-red-600 bg-red-50'
  if (a === 'claim' || a === 'workflow_start') return 'border-blue-300 text-blue-600 bg-blue-50'
  return 'border-slate-300 text-slate-600 bg-slate-50'
}

function formatSnapshot(snapshot) {
  if (!snapshot) return ''
  if (typeof snapshot === 'string') return snapshot
  return JSON.stringify(snapshot, null, 2)
}

function viewDetail(row) {
  drawerRow.value = row
  showDrawer.value = true
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await listAuditLogs({
      page: page.value,
      page_size: pageSize.value,
      action: filters.value.action || undefined,
      q: filters.value.keyword || undefined,
    })
    const data = res.data || {}
    rows.value = data.items || []
    total.value = data.total || rows.value.length
  } catch (e) {
    console.error('加载审计日志失败', e)
    error.value = '加载审计日志失败，请稍后重试。'
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
  filters.value = { action: '', keyword: '' }
  reload()
}

function onPageChange(p) {
  page.value = p
  load()
}

onMounted(load)
</script>
