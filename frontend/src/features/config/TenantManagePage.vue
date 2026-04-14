<template>
  <AppShell>
    <div class="p-5 space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="gov-page-header">租户管理</h1>
          <p class="mt-0.5 text-sm text-[var(--gov-text-muted)]">维护租户启停状态与基础信息</p>
        </div>
        <button @click="openCreate" class="gov-btn text-sm">
          新建租户
        </button>
      </div>

      <DataTable
        :columns="columns"
        :rows="pagedRows"
        :total="tenants.length"
        :page="page"
        :page-size="pageSize"
        :loading="loading"
        row-key="id"
        @page-change="onPageChange"
      >
        <template #cell-status="{ value }">
          <StatusBadge :status="value === 'disabled' ? 'failed' : 'done'" :type="'batch'" />
        </template>

        <template #cell-created_at="{ value }">
          <span class="text-sm text-[var(--gov-text-muted)]">{{ formatDate(value) }}</span>
        </template>

        <template #actions="{ row }">
          <button @click="openEdit(row)" class="text-xs text-[var(--gov-primary)] hover:underline">编辑</button>
        </template>
      </DataTable>
    </div>

    <div v-if="editing" class="gov-modal-backdrop">
      <div class="gov-modal-panel w-[480px] p-5">
        <h3 class="text-base font-semibold text-[var(--gov-text)]">{{ formMode === 'create' ? '新建租户' : '编辑租户' }}</h3>

        <div class="mt-4 space-y-3">
          <div>
            <label class="mb-1 block text-sm text-[var(--gov-text-muted)]">租户标识</label>
            <input
              v-model.trim="form.id"
              :disabled="formMode !== 'create'"
              placeholder="例如 archive_cn"
              class="w-full gov-filter-input text-sm disabled:bg-slate-50"
            />
            <p class="mt-1 text-xs text-[var(--gov-text-muted)]">仅支持小写字母、数字、下划线和横线</p>
          </div>

          <div>
            <label class="mb-1 block text-sm text-[var(--gov-text-muted)]">租户名称</label>
            <input
              v-model.trim="form.name"
              placeholder="租户显示名称"
              class="w-full gov-filter-input text-sm"
            />
          </div>

          <div v-if="formMode !== 'create'">
            <label class="mb-1 block text-sm text-[var(--gov-text-muted)]">状态</label>
            <select v-model="form.status" class="w-full gov-select text-sm">
              <option value="active">active</option>
              <option value="disabled">disabled</option>
            </select>
          </div>

          <p v-if="opMsg" class="rounded border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {{ opMsg }}
          </p>
        </div>

        <div class="mt-5 flex justify-end gap-2">
          <button @click="closeDialog" class="px-4 py-2 border border-[var(--gov-border)] rounded-md text-sm text-[var(--gov-text-muted)] hover:bg-slate-50 transition">取消</button>
          <button @click="save" :disabled="saving || !form.id || !form.name" class="gov-btn text-sm disabled:opacity-50">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import dayjs from 'dayjs'

import AppShell from '@/layouts/AppShell.vue'
import DataTable from '@/shared/components/DataTable.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import { createTenant, listTenants, updateTenant } from '@/api/tenants.js'

const columns = [
  { key: 'id', label: '租户标识', width: '180px', mono: true },
  { key: 'name', label: '租户名称', width: '220px' },
  { key: 'status', label: '状态', width: '120px' },
  { key: 'user_count', label: '用户数', width: '100px' },
  { key: 'created_at', label: '创建时间', width: '180px' },
]

const tenants = ref([])
const loading = ref(false)
const saving = ref(false)
const page = ref(1)
const pageSize = ref(20)
const opMsg = ref('')

const editing = ref(false)
const formMode = ref('create')
const form = ref({ id: '', name: '', status: 'active' })

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return tenants.value.slice(start, start + pageSize.value)
})

function formatDate(value) {
  return value ? dayjs(value).format('YYYY-MM-DD HH:mm') : '-'
}

function onPageChange(nextPage) {
  page.value = nextPage
}

function openCreate() {
  formMode.value = 'create'
  form.value = { id: '', name: '', status: 'active' }
  opMsg.value = ''
  editing.value = true
}

function openEdit(tenant) {
  formMode.value = 'edit'
  form.value = {
    id: tenant.id || '',
    name: tenant.name || '',
    status: tenant.status || 'active',
  }
  opMsg.value = ''
  editing.value = true
}

function closeDialog() {
  editing.value = false
  opMsg.value = ''
}

function validateCreatePayload() {
  const normalizedId = String(form.value.id || '').trim().toLowerCase()
  const normalizedName = String(form.value.name || '').trim()
  form.value.id = normalizedId
  form.value.name = normalizedName

  if (!/^[a-z0-9_-]{2,64}$/.test(normalizedId)) {
    return '租户标识不合法：仅支持 2-64 位小写字母、数字、下划线和横线。'
  }
  if (!normalizedName) {
    return '租户名称不能为空。'
  }
  if (normalizedName.length > 120) {
    return '租户名称长度不能超过 120。'
  }
  return ''
}

function parseApiError(error) {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const field = Array.isArray(item?.loc) ? item.loc.join('.') : 'body'
        return `${field}: ${item?.msg || '参数不合法'}`
      })
      .join('；')
  }
  if (typeof detail === 'string' && detail) {
    return detail
  }
  return error?.message || '未知错误'
}

async function loadTenants() {
  loading.value = true
  try {
    const res = await listTenants()
    const data = res.data || {}
    tenants.value = data.items || []
  } catch (error) {
    console.error('加载租户失败', error)
    tenants.value = []
  } finally {
    loading.value = false
  }
}

async function save() {
  opMsg.value = ''
  if (formMode.value === 'create') {
    const validationError = validateCreatePayload()
    if (validationError) {
      opMsg.value = validationError
      return
    }
  }

  saving.value = true
  try {
    if (formMode.value === 'create') {
      await createTenant({ id: form.value.id, name: form.value.name })
    } else {
      await updateTenant(form.value.id, { name: form.value.name, status: form.value.status })
    }
    closeDialog()
    await loadTenants()
  } catch (error) {
    opMsg.value = `保存失败：${parseApiError(error)}`
    console.error('保存租户失败', error)
  } finally {
    saving.value = false
  }
}

onMounted(loadTenants)
</script>