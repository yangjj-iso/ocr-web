<template>
  <AppShell>
    <div class="p-5 space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="gov-page-header">批次详情</h1>
          <p class="text-sm text-[var(--gov-text-muted)] mt-0.5">批次 {{ batchId }}</p>
        </div>
        <div class="flex items-center gap-2">
          <button v-if="canStartWorkflow" @click="handleStartWorkflow" :disabled="starting" class="px-4 py-2 text-sm rounded-md bg-green-600 text-white hover:bg-green-700 transition disabled:opacity-50">
            {{ starting ? '启动中...' : '启动工作流' }}
          </button>
          <button v-if="canReview" @click="goTask" class="gov-btn text-sm">进入任务列表</button>
        </div>
      </div>

      <div v-if="opMsg" class="rounded-lg border p-3 text-sm" :class="opMsg.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'">
        {{ opMsg.text }}
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <!-- 批次概览 -->
        <section class="rounded-lg border border-[var(--gov-border)] bg-white p-4 lg:col-span-2">
          <h2 class="text-sm font-semibold text-[var(--gov-text)]">批次概览</h2>
          <div class="mt-3 grid grid-cols-2 gap-3 text-sm">
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">批次ID</p>
              <p class="mt-0.5 font-mono text-[var(--gov-text)]">{{ batch.batch_id || batch.id || '-' }}</p>
            </div>
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">状态</p>
              <div class="mt-1"><StatusBadge :status="batch.status" /></div>
            </div>
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">文件数量</p>
              <p class="mt-0.5 text-[var(--gov-text)]">{{ batch.file_count ?? files.length ?? '-' }}</p>
            </div>
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">创建人</p>
              <p class="mt-0.5 text-[var(--gov-text)]">{{ batch.created_by || '-' }}</p>
            </div>
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">策略版本</p>
              <p class="mt-0.5 text-[var(--gov-text)]">{{ batch.policy_snapshot_version || '-' }}</p>
            </div>
            <div>
              <p class="text-xs text-[var(--gov-text-muted)]">创建时间</p>
              <p class="mt-0.5 text-[var(--gov-text)]">{{ fmt(batch.created_at) }}</p>
            </div>
          </div>
        </section>

        <!-- 处理进度 -->
        <section class="rounded-lg border border-[var(--gov-border)] bg-white p-4">
          <h2 class="text-sm font-semibold text-[var(--gov-text)]">处理进度</h2>
          <div class="mt-3 space-y-2">
            <div v-for="s in stages" :key="s.name || s.id" class="flex items-center gap-2 text-sm">
              <span class="w-2 h-2 rounded-full" :class="dotClass(s.status)"></span>
              <span class="text-[var(--gov-text)]">{{ s.label || s.name }}</span>
              <span class="ml-auto text-[var(--gov-text-muted)]">{{ s.count ?? '' }}</span>
            </div>
            <p v-if="!stages.length" class="text-sm text-[var(--gov-text-muted)]">暂无进度信息</p>
          </div>
        </section>
      </div>

      <!-- 文件上传 -->
      <section v-if="canUpload" class="rounded-lg border border-[var(--gov-border)] bg-white p-4">
        <h2 class="text-sm font-semibold text-[var(--gov-text)] mb-3">上传文件</h2>
        <div
          class="border-2 border-dashed border-[var(--gov-border)] rounded-lg p-6 text-center transition hover:border-[var(--gov-primary)] hover:bg-blue-50/30"
          @dragover.prevent
          @drop.prevent="handleDrop"
        >
          <svg class="mx-auto h-8 w-8 text-[var(--gov-text-muted)]" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>
          <p class="mt-2 text-sm text-[var(--gov-text-muted)]">拖放文件到此处，或</p>
          <label class="mt-2 inline-block cursor-pointer text-sm text-[var(--gov-primary)] hover:underline">
            选择文件
            <input type="file" multiple accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif" class="hidden" @change="handleFileSelect" />
          </label>
          <p class="mt-1 text-xs text-[var(--gov-text-muted)]">支持 PDF、JPG、PNG、TIFF</p>
        </div>
        <div v-if="uploading" class="mt-3 flex items-center gap-2 text-sm text-[var(--gov-text-muted)]">
          <svg class="h-4 w-4 animate-spin" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4"/></svg>
          上传中...
        </div>
      </section>

      <!-- 文件列表 -->
      <section class="rounded-lg border border-[var(--gov-border)] bg-white p-4">
        <h2 class="text-sm font-semibold text-[var(--gov-text)] mb-3">文件列表</h2>
        <div v-if="filesLoading" class="text-sm text-[var(--gov-text-muted)]">加载中...</div>
        <div v-else-if="!files.length" class="text-sm text-[var(--gov-text-muted)]">暂无文件</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)]">
                <th class="px-3 py-2 text-left text-xs font-semibold text-[var(--gov-text-muted)]">文件名</th>
                <th class="px-3 py-2 text-left text-xs font-semibold text-[var(--gov-text-muted)]">大小</th>
                <th class="px-3 py-2 text-left text-xs font-semibold text-[var(--gov-text-muted)]">类型</th>
                <th class="px-3 py-2 text-left text-xs font-semibold text-[var(--gov-text-muted)]">上传时间</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[var(--gov-border)]">
              <tr v-for="f in files" :key="f.id || f.file_id || f.name" class="hover:bg-slate-50/70">
                <td class="px-3 py-2 text-[var(--gov-text)]">{{ f.name || f.file_name || f.original_name || '-' }}</td>
                <td class="px-3 py-2 text-[var(--gov-text-muted)]">{{ formatSize(f.size || f.file_size) }}</td>
                <td class="px-3 py-2 text-[var(--gov-text-muted)]">{{ f.content_type || f.mime_type || '-' }}</td>
                <td class="px-3 py-2 text-[var(--gov-text-muted)]">{{ fmt(f.created_at || f.uploaded_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 文档单元列表 -->
      <section class="rounded-lg border border-[var(--gov-border)] bg-white p-4">
        <h2 class="text-sm font-semibold text-[var(--gov-text)] mb-3">文档单元（分件结果）</h2>
        <div v-if="docsLoading" class="text-sm text-[var(--gov-text-muted)]">加载中...</div>
        <div v-else-if="!docUnits.length" class="text-sm text-[var(--gov-text-muted)]">暂无文档单元，工作流执行后自动生成</div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)]">
                <th class="px-3 py-2 text-left text-xs font-semibold text-[var(--gov-text-muted)]">文档ID</th>
                <th class="px-3 py-2 text-left text-xs font-semibold text-[var(--gov-text-muted)]">题名</th>
                <th class="px-3 py-2 text-left text-xs font-semibold text-[var(--gov-text-muted)]">页范围</th>
                <th class="px-3 py-2 text-left text-xs font-semibold text-[var(--gov-text-muted)]">置信度</th>
                <th class="px-3 py-2 text-left text-xs font-semibold text-[var(--gov-text-muted)]">状态</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-[var(--gov-border)]">
              <tr v-for="d in docUnits" :key="d.doc_id || d.id" class="hover:bg-slate-50/70">
                <td class="px-3 py-2 font-mono text-xs text-[var(--gov-text)]">{{ d.doc_id || d.id || '-' }}</td>
                <td class="px-3 py-2 text-[var(--gov-text)]">{{ d.title || d.metadata?.title || '-' }}</td>
                <td class="px-3 py-2 text-[var(--gov-text-muted)]">{{ d.start_page ?? '-' }} – {{ d.end_page ?? '-' }}</td>
                <td class="px-3 py-2">
                  <span v-if="d.confidence != null" class="text-xs rounded px-2 py-0.5 border" :class="confidenceClass(d.confidence)">{{ (d.confidence * 100).toFixed(0) }}%</span>
                  <span v-else class="text-[var(--gov-text-muted)]">-</span>
                </td>
                <td class="px-3 py-2"><StatusBadge :status="d.status" /></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import dayjs from 'dayjs'

import AppShell from '@/layouts/AppShell.vue'
import StatusBadge from '@/shared/components/StatusBadge.vue'
import { useAuthState } from '@/composables/useAuthState'
import { getBatch, startBatchWorkflow, listBatchFiles, uploadBatchFiles, listDocUnits } from '@/api/archive'

const route = useRoute()
const router = useRouter()
const { authProfile } = useAuthState()

const batchId = route.params.id
const batch = ref({})
const stages = ref([])
const files = ref([])
const docUnits = ref([])
const filesLoading = ref(false)
const docsLoading = ref(false)
const uploading = ref(false)
const starting = ref(false)
const opMsg = ref(null)

const canReview = computed(() => authProfile.value.hasOperator)
const canUpload = computed(() => {
  const s = batch.value.status
  return !s || s === 'created' || s === 'pending' || s === 'draft'
})
const canStartWorkflow = computed(() => {
  const s = batch.value.status
  return canReview.value && (s === 'created' || s === 'pending' || s === 'draft') && files.value.length > 0
})

function fmt(v) {
  return v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'
}

function formatSize(bytes) {
  if (!bytes) return '-'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function dotClass(status) {
  if (status === 'done') return 'bg-green-500'
  if (status === 'processing') return 'bg-blue-500 animate-pulse'
  if (status === 'failed') return 'bg-red-500'
  return 'bg-slate-300'
}

function confidenceClass(c) {
  if (c >= 0.8) return 'border-green-300 text-green-700 bg-green-50'
  if (c >= 0.5) return 'border-amber-300 text-amber-700 bg-amber-50'
  return 'border-red-300 text-red-600 bg-red-50'
}

function goTask() {
  router.push('/tasks')
}

async function load() {
  try {
    const res = await getBatch(batchId)
    batch.value = res.data || {}
    stages.value = batch.value.workflow_stages || []
  } catch (e) {
    console.error('加载批次详情失败', e)
  }
}

async function loadFiles() {
  filesLoading.value = true
  try {
    const res = await listBatchFiles(batchId)
    files.value = res.data?.items || res.data || []
  } catch {
    files.value = []
  } finally {
    filesLoading.value = false
  }
}

async function loadDocUnits() {
  docsLoading.value = true
  try {
    const res = await listDocUnits(batchId)
    docUnits.value = res.data?.items || res.data || []
  } catch {
    docUnits.value = []
  } finally {
    docsLoading.value = false
  }
}

async function handleFileSelect(e) {
  const selected = e.target.files
  if (!selected?.length) return
  await doUpload(selected)
  e.target.value = ''
}

function handleDrop(e) {
  const dropped = e.dataTransfer?.files
  if (dropped?.length) doUpload(dropped)
}

async function doUpload(fileList) {
  uploading.value = true
  opMsg.value = null
  try {
    const fd = new FormData()
    for (const f of fileList) fd.append('files', f)
    await uploadBatchFiles(batchId, fd)
    opMsg.value = { ok: true, text: `成功上传 ${fileList.length} 个文件` }
    await loadFiles()
  } catch (e) {
    opMsg.value = { ok: false, text: '上传失败：' + (e?.response?.data?.detail || e.message || '未知错误') }
  } finally {
    uploading.value = false
  }
}

async function handleStartWorkflow() {
  starting.value = true
  opMsg.value = null
  try {
    await startBatchWorkflow(batchId, batch.value.policy_snapshot_id)
    opMsg.value = { ok: true, text: '工作流已启动' }
    await load()
  } catch (e) {
    opMsg.value = { ok: false, text: '启动失败：' + (e?.response?.data?.detail || e.message || '未知错误') }
  } finally {
    starting.value = false
  }
}

onMounted(() => {
  load()
  loadFiles()
  loadDocUnits()
})
</script>
