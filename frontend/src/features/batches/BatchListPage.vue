<template>
  <AppShell>
    <div class="p-5 space-y-4">
      <!-- 页头 -->
      <div class="flex items-center justify-between gap-3">
        <div>
          <h1 class="gov-page-header">批次管理</h1>
        </div>
        <div class="flex items-center gap-2">
          <span v-if="refreshStatusText" class="hidden text-xs text-[var(--gov-text-muted)] md:inline">{{ refreshStatusText }}</span>
          <button
            @click="handleManualRefresh"
            class="px-3 py-2 border border-[var(--gov-border)] text-sm rounded-md text-[var(--gov-text-muted)] hover:bg-slate-50 transition"
          >
            刷新
          </button>
          <button
            v-if="canCreate"
            @click="openCreateModal"
            class="gov-btn text-sm"
          >
            + 新建批次
          </button>
        </div>
      </div>

      <!-- 数据表格 -->
      <DataTable
        :columns="columns"
        :rows="batches"
        :total="total"
        :page="page"
        :page-size="pageSize"
        :loading="loading"
        row-key="batch_id"
        clickable
        @row-click="handleRowClick"
        @page-change="handlePageChange"
      >
        <!-- 过滤器 -->
        <template #filters>
          <div class="flex gap-3 flex-wrap">
            <select
              v-model="filterStatus"
              @change="loadData"
              class="gov-select text-sm"
            >
              <option value="">全部状态</option>
              <option value="draft">草稿</option>
              <option value="processing">处理中</option>
              <option value="review_required">待审核</option>
              <option value="done">已完成</option>
              <option value="failed">失败</option>
            </select>
            <input
              v-model="filterDateFrom"
              type="date"
              @change="loadData"
              class="gov-filter-input text-sm"
              placeholder="开始日期"
            />
            <input
              v-model="filterDateTo"
              type="date"
              @change="loadData"
              class="gov-filter-input text-sm"
              placeholder="结束日期"
            />
            <button @click="resetFilters" class="text-sm text-[var(--gov-text-muted)] hover:text-[var(--gov-text)] px-2">
              重置
            </button>
          </div>
        </template>

        <!-- 状态列 -->
        <template #cell-status="{ value }">
          <StatusBadge :status="value" />
        </template>

        <!-- 文件数量列 -->
        <template #cell-file_count="{ value }">
          <span class="font-mono text-sm">{{ value ?? 0 }}</span>
        </template>

        <!-- 进度列 -->
        <template #cell-progress="{ row }">
          <div class="flex items-center gap-2">
            <div class="flex-1 bg-gray-200 rounded-full h-1.5 min-w-[60px]">
              <div
                class="bg-[var(--gov-primary)] h-1.5 rounded-full transition-all"
                :style="{ width: `${getProgress(row)}%` }"
              ></div>
            </div>
            <span class="text-xs text-[var(--gov-text-muted)] w-8 text-right">{{ getProgress(row) }}%</span>
          </div>
        </template>

        <!-- 创建时间列 -->
        <template #cell-created_at="{ value }">
          <span class="text-sm text-[var(--gov-text-muted)]">{{ formatDate(value) }}</span>
        </template>

        <!-- 操作列 -->
        <template #actions="{ row }">
          <div class="flex gap-2">
            <button
              @click.stop="handleViewDetail(row)"
              class="text-xs text-[var(--gov-primary)] hover:underline"
            >
              详情
            </button>
            <button
              v-if="canStartWorkflow(row)"
              @click.stop="handleStartWorkflow(row)"
              class="text-xs text-green-600 hover:underline"
            >
              启动
            </button>
            <button
              v-if="canAssign(row)"
              @click.stop="handleAssign(row)"
              class="text-xs text-amber-600 hover:underline"
            >
              分配
            </button>
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

    <!-- 批次详情抽屉 -->
    <DetailDrawer v-model="drawerVisible" :title="`批次详情：${selectedBatch?.batch_id}`" width="500px">
      <div v-if="selectedBatch" class="space-y-4">
        <div class="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">批次ID</p>
            <p class="mt-0.5 font-mono text-[var(--gov-text)]">{{ selectedBatch.batch_id || '-' }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">状态</p>
            <div class="mt-0.5"><StatusBadge :status="selectedBatch.status" /></div>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">文件数量</p>
            <p class="mt-0.5 text-[var(--gov-text)]">{{ selectedBatch.file_count ?? 0 }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">策略版本</p>
            <p class="mt-0.5 text-[var(--gov-text)]">{{ selectedBatch.policy_snapshot_version ?? '默认' }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">创建人</p>
            <p class="mt-0.5 text-[var(--gov-text)]">{{ selectedBatch.created_by ?? '-' }}</p>
          </div>
          <div>
            <p class="text-xs text-[var(--gov-text-muted)]">创建时间</p>
            <p class="mt-0.5 text-[var(--gov-text)]">{{ formatDate(selectedBatch.created_at) }}</p>
          </div>
        </div>

        <div class="rounded-md border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] p-3">
          <div class="flex items-center gap-3">
            <div class="flex-1 bg-gray-200 rounded-full h-1.5 min-w-[60px]">
              <div
                class="bg-[var(--gov-primary)] h-1.5 rounded-full transition-all"
                :style="{ width: `${getProgress(selectedBatch)}%` }"
              ></div>
            </div>
            <span class="w-10 text-right font-mono text-sm text-[var(--gov-text-muted)]">{{ getProgress(selectedBatch) }}%</span>
          </div>
          <p v-if="getProgressSummary(selectedBatch)" class="mt-2 text-xs text-[var(--gov-text-muted)]">
            {{ getProgressSummary(selectedBatch) }}
          </p>
        </div>

        <!-- 工作流进度 -->
        <div v-if="selectedBatch.workflow_stages?.length" class="mt-4">
          <p class="text-sm font-medium text-[var(--gov-text)] mb-2">工作流阶段</p>
          <div class="space-y-2">
            <div
              v-for="stage in selectedBatch.workflow_stages"
              :key="stage.name"
              class="flex items-center gap-3 text-sm"
            >
              <span
                class="w-2 h-2 rounded-full flex-shrink-0"
                :class="{
                  'bg-green-500': stage.status === 'done',
                  'bg-blue-500 animate-pulse': stage.status === 'processing',
                  'bg-amber-400': stage.status === 'pending',
                  'bg-red-500': stage.status === 'failed',
                  'bg-gray-300': !stage.status
                }"
              ></span>
              <span class="text-[var(--gov-text)]">{{ stage.label }}</span>
              <span class="ml-auto text-[var(--gov-text-muted)]">{{ stage.count ?? '' }}</span>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex gap-2">
        <button
          @click="router.push(`/batches/${selectedBatch?.batch_id}`)"
          class="gov-btn text-sm"
        >
          进入批次
        </button>
        <button
          v-if="canStartWorkflow(selectedBatch)"
          @click="handleStartWorkflow(selectedBatch)"
          class="px-4 py-2 border border-green-500 text-green-600 text-sm rounded-md hover:bg-green-50 transition"
        >
          启动工作流
        </button>
        <button @click="drawerVisible = false" class="px-4 py-2 border border-[var(--gov-border)] text-sm rounded-md text-[var(--gov-text-muted)] hover:bg-slate-50 transition">
          关闭
        </button>
        </div>
      </template>
    </DetailDrawer>

    <!-- 新建批次模态框 -->
    <div v-if="showCreateModal" class="gov-modal-backdrop">
      <div class="gov-modal-panel w-[480px] p-6">
        <h3 class="text-base font-semibold text-[var(--gov-text)] mb-4">新建批次</h3>
        <div class="space-y-3">
          <div>
            <label class="text-sm text-[var(--gov-text-muted)] block mb-1">批次名称（可选）</label>
            <input
              v-model="createForm.name"
              type="text"
              class="w-full gov-filter-input text-sm"
              placeholder="批次名称，留空则自动生成"
            />
          </div>
          <div>
            <label class="text-sm text-[var(--gov-text-muted)] block mb-1">策略版本</label>
            <select v-model="createForm.policy_snapshot_id" class="w-full gov-select text-sm">
              <option value="">使用最新策略</option>
              <option v-for="p in policySnapshots" :key="p.id" :value="p.id">{{ p.version }} — {{ formatDate(p.created_at) }}</option>
            </select>
          </div>
          <div>
            <label class="text-sm text-[var(--gov-text-muted)] block mb-1">备注</label>
            <textarea
              v-model="createForm.notes"
              class="w-full gov-filter-input text-sm resize-none"
              rows="2"
              placeholder="批次备注信息"
            ></textarea>
          </div>
        </div>
        <div class="flex justify-end gap-2 mt-5">
          <button @click="closeCreateModal" class="px-4 py-2 border border-[var(--gov-border)] text-sm rounded-md text-[var(--gov-text-muted)] hover:bg-slate-50 transition">取消</button>
          <button @click="submitCreate" :disabled="creating" class="gov-btn text-sm disabled:opacity-50">
            {{ creating ? '创建中...' : '创建批次' }}
          </button>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthState } from '@/composables/useAuthState'
import AppShell from '@/layouts/AppShell.vue'
import DataTable from '@/shared/components/DataTable.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import DetailDrawer from '@/shared/components/DetailDrawer.vue'
import {
  formatRefreshTime,
  getBatchProgressPercent,
  getBatchProgressSummary,
  isBatchAutoRefreshable,
} from '@/features/batches/progress'
import {
  listBatches,
  createBatch,
  startBatchWorkflow,
  listPolicySnapshots
} from '@/api/archive'
import dayjs from 'dayjs'

const router = useRouter()
const route = useRoute()
const { authProfile } = useAuthState()

// 权限
const isSysAdmin = computed(() => authProfile.value.isSysAdmin)
const isTenantAdmin = computed(() => authProfile.value.isTenantAdmin)
const canCreate = computed(() => authProfile.value.hasOperator)
const canAssignUser = computed(() => isSysAdmin.value || isTenantAdmin.value)

// 列表状态
const batches = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

// 过滤条件
const filterStatus = ref('')
const filterDateFrom = ref('')
const filterDateTo = ref('')

// 抽屉
const drawerVisible = ref(false)
const selectedBatch = ref(null)

// 创建模态框
const showCreateModal = ref(false)
const creating = ref(false)
const policySnapshots = ref([])
const createForm = ref({ name: '', policy_snapshot_id: '', notes: '' })
const loadError = ref('')
const opMsg = ref(null)
const lastRefreshedAt = ref(null)

const AUTO_REFRESH_MS = 15000
let listAutoRefreshTimer = null
let loadInFlight = false

const columns = [
  { key: 'batch_id', label: '批次ID', width: '200px' },
  { key: 'file_count', label: '文件数' },
  { key: 'status', label: '状态' },
  { key: 'progress', label: '进度' },
  { key: 'created_at', label: '创建时间' },
]

const hasActiveBatches = computed(() => batches.value.some((batch) => isBatchAutoRefreshable(batch)))
const refreshStatusText = computed(() => {
  const stamp = formatRefreshTime(lastRefreshedAt.value)
  if (hasActiveBatches.value) {
    return stamp ? `${stamp} 更新 · 在途批次每15s自动刷新` : '在途批次每15s自动刷新'
  }
  return stamp ? `${stamp} 更新` : ''
})

function syncSelectedBatch(nextRows) {
  if (!selectedBatch.value?.batch_id) return
  const nextSelected = nextRows.find((row) => row.batch_id === selectedBatch.value.batch_id)
  if (nextSelected) {
    selectedBatch.value = nextSelected
  }
}

function startAutoRefresh() {
  stopAutoRefresh()
  if (!hasActiveBatches.value) return
  listAutoRefreshTimer = window.setInterval(() => {
    if (!document.hidden) {
      loadData({ silent: true })
    }
  }, AUTO_REFRESH_MS)
}

function stopAutoRefresh() {
  if (listAutoRefreshTimer) {
    window.clearInterval(listAutoRefreshTimer)
    listAutoRefreshTimer = null
  }
}

async function loadData(options = {}) {
  if (loadInFlight) return
  loadInFlight = true
  if (!options.silent) {
    loading.value = true
  }
  loadError.value = ''
  try {
    const params = {
      page: page.value,
      page_size: pageSize.value,
      status: filterStatus.value || undefined,
      date_from: filterDateFrom.value || undefined,
      date_to: filterDateTo.value || undefined,
    }
    const res = await listBatches(params)
    batches.value = res.data?.items ?? res.data ?? []
    total.value = res.data?.total ?? batches.value.length
    syncSelectedBatch(batches.value)
    lastRefreshedAt.value = new Date()
  } catch (e) {
    console.error('加载批次失败', e)
    loadError.value = e?.response?.status === 401 ? '认证已失效，请重新登录。' : '加载批次列表失败，请稍后重试。'
  } finally {
    if (!options.silent) {
      loading.value = false
    }
    loadInFlight = false
  }
}

function resetFilters() {
  filterStatus.value = ''
  filterDateFrom.value = ''
  filterDateTo.value = ''
  page.value = 1
  loadData()
}

function handlePageChange(p) {
  page.value = p
  loadData()
}

function handleRowClick(row) {
  router.push(`/batches/${row.batch_id}`)
}

function handleViewDetail(row) {
  selectedBatch.value = row
  drawerVisible.value = true
}

function getProgress(row) {
  return getBatchProgressPercent(row)
}

function getProgressSummary(row) {
  return getBatchProgressSummary(row)
}

async function handleManualRefresh() {
  await loadData()
}

function canStartWorkflow(row) {
  if (!row) return false
  return canCreate.value && row.status === 'draft' && Number(row.file_count || 0) > 0
}

function canAssign(row) {
  return canAssignUser.value && ['processing', 'review_required'].includes(row?.status)
}

async function handleStartWorkflow(row) {
  if (!row) return
  opMsg.value = null
  try {
    await startBatchWorkflow(row.batch_id)
    opMsg.value = { ok: true, text: '工作流已启动' }
    await loadData()
    drawerVisible.value = false
  } catch (e) {
    console.error('启动工作流失败', e)
    opMsg.value = { ok: false, text: '启动工作流失败：' + (e?.response?.data?.detail || e.message || '未知错误') }
  }
}

function handleAssign(row) {
  router.push({ path: '/tasks', query: { batchId: row.batch_id } })
}

function openCreateModal() {
  showCreateModal.value = true
  if (route.query.create !== '1') {
    router.replace({ query: { ...route.query, create: '1' } }).catch(() => {})
  }
}

function closeCreateModal() {
  showCreateModal.value = false
  if (route.query.create) {
    const query = { ...route.query }
    delete query.create
    router.replace({ query }).catch(() => {})
  }
}

async function submitCreate() {
  creating.value = true
  try {
    const payload = {
      name: createForm.value.name || undefined,
      policy_snapshot_id: createForm.value.policy_snapshot_id || undefined,
      notes: createForm.value.notes || undefined,
    }
    const res = await createBatch(payload)
    closeCreateModal()
    createForm.value = { name: '', policy_snapshot_id: '', notes: '' }
    opMsg.value = { ok: true, text: '批次已创建' }
    await loadData()
    if (res.data?.batch_id) {
      router.push(`/batches/${res.data.batch_id}`)
    }
  } catch (e) {
    console.error('创建批次失败', e)
    opMsg.value = { ok: false, text: '创建批次失败：' + (e?.response?.data?.detail || e.message || '未知错误') }
  } finally {
    creating.value = false
  }
}

function formatDate(val) {
  if (!val) return '-'
  return dayjs(val).format('YYYY-MM-DD HH:mm')
}

watch(
  () => route.query.create,
  (flag) => {
    showCreateModal.value = flag === '1' && canCreate.value
  },
  { immediate: true }
)

watch(hasActiveBatches, (active) => {
  if (active) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
})

onMounted(async () => {
  await loadData()
  try {
    const res = await listPolicySnapshots()
    policySnapshots.value = res.data?.items ?? res.data ?? []
  } catch {}
})

onBeforeUnmount(() => {
  stopAutoRefresh()
})
</script>
