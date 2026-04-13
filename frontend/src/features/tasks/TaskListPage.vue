<template>
  <AppShell>
    <div class="p-5 space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="gov-page-header">任务列表</h1>
        </div>
      </div>

      <DataTable
        :columns="columns"
        :rows="tasks"
        :total="total"
        :page="page"
        :page-size="pageSize"
        :loading="loading"
        row-key="id"
        clickable
        @row-click="handleRowClick"
        @page-change="handlePageChange"
      >
        <template #filters>
          <div class="flex gap-3 flex-wrap items-center">
            <select v-model="filters.type" @change="reloadFromFirstPage" class="gov-select text-sm">
              <option value="">全部类型</option>
              <option value="boundary_review">边界校正</option>
              <option value="metadata_review">元数据检录</option>
              <option value="order_review">排序复核</option>
              <option value="final_release">发布确认</option>
              <option value="rework">返工处理</option>
            </select>
            <select v-model="filters.status" @change="reloadFromFirstPage" class="gov-select text-sm">
              <option value="">全部状态</option>
              <option value="pending">待处理</option>
              <option value="processing">处理中</option>
              <option value="human_review">待人工审核</option>
              <option value="done">已完成</option>
              <option value="failed">失败</option>
            </select>
            <input
              v-model.trim="filters.keyword"
              @keyup.enter="reloadFromFirstPage"
              class="gov-filter-input text-sm w-[220px]"
              placeholder="批次ID / 任务ID"
            />
            <button @click="reloadFromFirstPage" class="gov-btn text-sm">查询</button>
            <button @click="resetFilters" class="px-2 text-sm text-[var(--gov-text-muted)] hover:text-[var(--gov-text)]">重置</button>
          </div>
        </template>

        <template #cell-type="{ value }">
          <span class="inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium text-[var(--gov-text-muted)] bg-slate-100">
            {{ formatTaskType(value) }}
          </span>
        </template>

        <template #cell-status="{ value }">
          <StatusBadge :status="value" />
        </template>

        <template #cell-assignee="{ row }">
          <span class="text-sm">{{ row.assignee || row.assignee_name || '-' }}</span>
        </template>

        <template #cell-created_at="{ value }">
          <span class="text-sm text-[var(--gov-text-muted)]">{{ formatDate(value) }}</span>
        </template>

        <template #actions="{ row }">
          <div class="flex gap-2 justify-end">
            <button @click.stop="goToTask(row)" class="text-xs text-[var(--gov-primary)] hover:underline">处理</button>
            <button v-if="canAssignTask" @click.stop="openAssign(row)" class="text-xs text-amber-600 hover:underline">分配</button>
          </div>
        </template>
      </DataTable>

      <div v-if="loadError" class="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        {{ loadError }}
      </div>
    </div>

    <div v-if="showAssign" class="gov-modal-backdrop">
      <div class="gov-modal-panel w-[420px] p-5">
        <h3 class="text-base font-semibold text-[var(--gov-text)]">任务分配</h3>
        <p class="text-sm text-[var(--gov-text-muted)] mt-1">任务 {{ selectedTask?.id }} / {{ formatTaskType(selectedTask?.type) }}</p>

        <div class="mt-4 space-y-3">
          <div>
            <label class="text-sm text-[var(--gov-text-muted)] block mb-1">选择执行人</label>
            <select v-model="assignForm.userId" class="w-full gov-select text-sm">
              <option value="">请选择</option>
              <option v-for="u in assignableUsers" :key="u.id || u.user_id || u.username" :value="u.id || u.user_id || u.username">
                {{ u.display_name || u.username }}
              </option>
            </select>
          </div>
          <div>
            <label class="text-sm text-[var(--gov-text-muted)] block mb-1">备注</label>
            <textarea v-model="assignForm.notes" rows="2" class="w-full gov-filter-input text-sm resize-none" placeholder="可选"></textarea>
          </div>
        </div>

        <div class="mt-5 flex justify-end gap-2">
          <button @click="closeAssign" class="px-4 py-2 border border-[var(--gov-border)] text-sm rounded-md text-[var(--gov-text-muted)] hover:bg-slate-50 transition">取消</button>
          <button @click="submitAssign" :disabled="assigning || !assignForm.userId" class="gov-btn text-sm disabled:opacity-50">
            {{ assigning ? '提交中...' : '确认分配' }}
          </button>
        </div>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'

import AppShell from '@/layouts/AppShell.vue'
import DataTable from '@/shared/components/DataTable.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import { useAuthState } from '@/composables/useAuthState'
import { listReviewTasks, getMyAssignedTasks, assignTask } from '@/api/archive'
import { listUsers } from '@/api/admin'
import { buildAuthProfile } from '@/utils/authz.js'

const router = useRouter()
const { authProfile } = useAuthState()

const canAssignTask = computed(() => authProfile.value.isSysAdmin || authProfile.value.isTenantAdmin)
const canViewAll = computed(() => canAssignTask.value)

const tasks = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

const loadError = ref('')
const filters = ref({ type: '', status: '', keyword: '' })

const columns = [
  { key: 'id', label: '任务ID', width: '140px', mono: true },
  { key: 'type', label: '任务类型', width: '130px' },
  { key: 'batch_id', label: '批次ID', width: '180px' },
  { key: 'assignee', label: '执行人', width: '120px' },
  { key: 'status', label: '状态', width: '120px' },
  { key: 'created_at', label: '创建时间', width: '160px' },
]

const showAssign = ref(false)
const assigning = ref(false)
const selectedTask = ref(null)
const assignableUsers = ref([])
const assignForm = ref({ userId: '', notes: '' })

function buildParams() {
  return {
    page: page.value,
    page_size: pageSize.value,
    type: filters.value.type || undefined,
    status: filters.value.status || undefined,
    q: filters.value.keyword || undefined,
  }
}

async function loadTasks() {
  loading.value = true
  loadError.value = ''
  try {
    const params = buildParams()
    const res = canViewAll.value
      ? await listReviewTasks(params)
      : await getMyAssignedTasks(params)
    const data = res.data || {}
    tasks.value = data.items || data.tasks || []
    total.value = data.total || tasks.value.length
  } catch (error) {
    console.error('加载任务失败', error)
    loadError.value = '加载任务失败，请检查网络或稍后重试。'
    tasks.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function loadAssignableUsers() {
  if (!canAssignTask.value) return
  try {
    const res = await listUsers({ page: 1, page_size: 200 })
    const items = res.data?.items || res.data || []
    assignableUsers.value = items.filter((u) => {
      const profile = buildAuthProfile(u)
      return profile.hasOperator || profile.hasSearcher
    })
  } catch (error) {
    console.error('加载用户失败', error)
  }
}

function reloadFromFirstPage() {
  page.value = 1
  loadTasks()
}

function resetFilters() {
  filters.value = { type: '', status: '', keyword: '' }
  reloadFromFirstPage()
}

function handlePageChange(p) {
  page.value = p
  loadTasks()
}

function formatTaskType(type) {
  const map = {
    boundary: '边界校正',
    boundary_review: '边界校正',
    metadata: '元数据检录',
    metadata_review: '元数据检录',
    ordering: '排序复核',
    order_review: '排序复核',
    final_release: '发布确认',
    rework: '返工处理',
  }
  return map[type] || type || '-'
}

function formatDate(value) {
  if (!value) return '-'
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

function goToTask(task) {
  if (!task) return
  if (task.type === 'final_release') {
    router.push('/release')
    return
  }
  router.push(`/review/${task.id}`)
}

function handleRowClick(task) {
  goToTask(task)
}

function openAssign(task) {
  selectedTask.value = task
  assignForm.value = { userId: '', notes: '' }
  showAssign.value = true
}

function closeAssign() {
  showAssign.value = false
  selectedTask.value = null
}

async function submitAssign() {
  if (!selectedTask.value || !assignForm.value.userId) return
  assigning.value = true
  try {
    await assignTask({
      task_id: selectedTask.value.id,
      assignee_id: assignForm.value.userId,
      notes: assignForm.value.notes || undefined,
    })
    closeAssign()
    await loadTasks()
  } catch (error) {
    console.error('任务分配失败', error)
  } finally {
    assigning.value = false
  }
}

onMounted(async () => {
  if (route.query.type) filters.value.type = String(route.query.type)
  await Promise.all([loadTasks(), loadAssignableUsers()])
})

watch(() => route.query.type, (val) => {
  filters.value.type = val ? String(val) : ''
  reloadFromFirstPage()
})
</script>
