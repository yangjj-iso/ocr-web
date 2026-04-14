<template>
  <AppShell>
    <div class="p-5 space-y-4">
      <div>
        <h1 class="gov-page-header">用户与权限</h1>
        <p class="text-sm text-[var(--gov-text-muted)] mt-0.5">用户列表、注册审核、角色能力配置</p>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section class="lg:col-span-2 rounded-lg border border-[var(--gov-border)] bg-white p-4">
          <h2 class="text-sm font-semibold text-[var(--gov-text)]">用户列表</h2>
          <DataTable
            class="mt-3"
            :columns="userColumns"
            :rows="users"
            :total="total"
            :page="page"
            :page-size="pageSize"
            :loading="loading"
            row-key="id"
            @page-change="onPageChange"
          >
            <template #cell-role="{ value }">
              <span class="text-xs rounded px-2 py-0.5 border border-[var(--gov-border)] bg-[var(--gov-surface-muted)]">{{ value || 'member' }}</span>
            </template>
            <template #cell-capabilities="{ value }">
              <span class="text-xs text-[var(--gov-text-muted)]">{{ value || '-' }}</span>
            </template>
            <template #actions="{ row }">
              <button @click="openEdit(row)" class="text-xs text-[var(--gov-primary)] hover:underline">编辑</button>
            </template>
          </DataTable>
        </section>

        <section class="rounded-lg border border-[var(--gov-border)] bg-white p-4">
          <h2 class="text-sm font-semibold text-[var(--gov-text)]">待审核账号</h2>
          <div class="mt-3 space-y-2 max-h-[420px] overflow-y-auto">
            <div v-if="pendingLoading" class="text-sm text-[var(--gov-text-muted)]">加载中...</div>
            <div v-else-if="!pendingUsers.length" class="text-sm text-[var(--gov-text-muted)]">暂无待审核账号</div>
            <div v-else v-for="u in pendingUsers" :key="u.id" class="rounded border border-[var(--gov-border)] p-3">
              <p class="text-sm font-medium text-[var(--gov-text)]">{{ u.display_name || u.username }}</p>
              <p class="text-xs text-[var(--gov-text-muted)] mt-1">{{ u.username }} · {{ u.capabilities || 'member' }}</p>
              <div class="mt-2 flex gap-2">
                <button @click="approve(u.id)" class="px-2 py-1 text-xs rounded bg-green-600 text-white">通过</button>
                <button @click="reject(u.id)" class="px-2 py-1 text-xs rounded bg-red-600 text-white">驳回</button>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>

    <div v-if="editing" class="gov-modal-backdrop">
      <div class="gov-modal-panel w-[520px] p-5">
        <h3 class="text-base font-semibold text-[var(--gov-text)]">编辑用户</h3>
        <p class="text-sm text-[var(--gov-text-muted)] mt-1">{{ editing.username }}</p>

        <div class="mt-4 grid grid-cols-2 gap-3">
          <div>
            <label class="text-xs text-[var(--gov-text-muted)] block mb-1">角色</label>
            <select v-model="editForm.role" class="w-full gov-select text-sm">
              <option value="member">member</option>
              <option value="tenant_admin">tenant_admin</option>
            </select>
          </div>
          <div>
            <label class="text-xs text-[var(--gov-text-muted)] block mb-1">显示名</label>
            <input v-model.trim="editForm.display_name" class="w-full gov-filter-input text-sm" />
          </div>
        </div>

        <div class="mt-3">
          <label class="text-xs text-[var(--gov-text-muted)] block mb-1">所属租户</label>
          <select v-model="editForm.tenant_id" class="w-full gov-select text-sm">
            <option v-for="t in tenantOptions" :key="t.id" :value="t.id">{{ t.name || t.id }} ({{ t.id }})</option>
          </select>
        </div>

        <div class="mt-3">
          <label class="text-xs text-[var(--gov-text-muted)] block mb-1">能力</label>
          <div class="flex gap-3 text-sm">
            <label class="inline-flex items-center gap-1.5">
              <input type="checkbox" v-model="capOperator" /> operator
            </label>
            <label class="inline-flex items-center gap-1.5">
              <input type="checkbox" v-model="capSearcher" /> searcher
            </label>
          </div>
        </div>

        <div class="mt-3">
          <label class="text-xs text-[var(--gov-text-muted)] block mb-1">重置密码（可选）</label>
          <input v-model.trim="editForm.new_password" type="password" class="w-full gov-filter-input text-sm" placeholder="留空不修改" />
        </div>

        <div class="mt-5 flex justify-end gap-2">
          <button @click="editing = null" class="px-4 py-2 border border-[var(--gov-border)] rounded-md text-sm text-[var(--gov-text-muted)] hover:bg-slate-50 transition">取消</button>
          <button @click="saveEdit" :disabled="saving" class="gov-btn text-sm disabled:opacity-50">{{ saving ? '保存中...' : '保存' }}</button>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import AppShell from '@/layouts/AppShell.vue'
import DataTable from '@/shared/components/DataTable.vue'
import { listUsers, setUserRole, setDisplayName } from '@/api/admin'
import { resetUserPassword } from '@/api/auth'
import { assignUserToTenant, listTenants } from '@/api/tenants.js'
import { useAuthState } from '@/composables/useAuthState'

const auth = useAuthState()

const users = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const pendingUsers = computed(() => auth.pendingUsers.value || [])
const pendingLoading = computed(() => auth.pendingLoading.value)

const userColumns = [
  { key: 'username', label: '用户名', width: '130px', mono: true },
  { key: 'display_name', label: '显示名', width: '140px' },
  { key: 'tenant_id', label: '所属租户', width: '140px', mono: true },
  { key: 'role', label: '角色', width: '120px' },
  { key: 'capabilities', label: '能力' },
]

const editing = ref(null)
const saving = ref(false)
const editForm = ref({ role: 'member', display_name: '', new_password: '', tenant_id: 'default' })
const tenantOptions = ref([{ id: 'default', name: '默认机构' }])
const capOperator = ref(false)
const capSearcher = ref(false)

function capsToString() {
  const arr = []
  if (capOperator.value) arr.push('operator')
  if (capSearcher.value) arr.push('searcher')
  return arr.join(',')
}

function extractUsers(data) {
  const rows = Array.isArray(data?.items) ? data.items : (Array.isArray(data) ? data : [])
  return rows.map((row) => ({
    ...row,
    tenant_id: row?.tenant_id || row?.tenantId || 'default',
  }))
}

function extractTenants(data) {
  if (Array.isArray(data?.items)) return data.items
  if (Array.isArray(data)) return data
  return []
}

async function loadTenants() {
  try {
    const res = await listTenants()
    const rows = extractTenants(res.data)
    tenantOptions.value = rows.length ? rows : [{ id: 'default', name: '默认机构' }]
  } catch (e) {
    console.error('加载租户列表失败', e)
    tenantOptions.value = [{ id: 'default', name: '默认机构' }]
  }
}

async function loadUsers() {
  loading.value = true
  try {
    const res = await listUsers({ page: page.value, page_size: pageSize.value })
    const data = res.data || {}
    users.value = extractUsers(data)
    total.value = data.total || users.value.length
  } catch (e) {
    console.error('加载用户失败', e)
    users.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function onPageChange(p) {
  page.value = p
  loadUsers()
}

function openEdit(user) {
  editing.value = user
  const caps = String(user.capabilities || '')
  capOperator.value = caps.includes('operator')
  capSearcher.value = caps.includes('searcher')
  editForm.value = {
    role: user.role || 'member',
    display_name: user.display_name || '',
    new_password: '',
    tenant_id: user.tenant_id || user.tenantId || 'default',
  }
}

async function saveEdit() {
  if (!editing.value) return
  saving.value = true
  try {
    await setUserRole(editing.value.id, editForm.value.role, capsToString())
    await setDisplayName(editing.value.id, editForm.value.display_name || null)
    const currentTenantId = editing.value.tenant_id || editing.value.tenantId || 'default'
    const targetTenantId = editForm.value.tenant_id || 'default'
    if (targetTenantId !== currentTenantId) {
      await assignUserToTenant(targetTenantId, editing.value.id)
    }
    if (editForm.value.new_password) {
      await resetUserPassword(editing.value.id, editForm.value.new_password)
    }
    editing.value = null
    await loadUsers()
  } catch (e) {
    console.error('更新用户失败', e)
  } finally {
    saving.value = false
  }
}

async function approve(userId) {
  await auth.approvePendingUser(userId)
  await Promise.all([auth.loadPendingUsers(), loadUsers()])
}

async function reject(userId) {
  await auth.rejectPendingUser(userId)
  await Promise.all([auth.loadPendingUsers(), loadUsers()])
}

onMounted(async () => {
  await Promise.all([loadUsers(), loadTenants(), auth.loadPendingUsers()])
})
</script>
