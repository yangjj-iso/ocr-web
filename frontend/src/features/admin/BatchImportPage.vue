<template>
  <div class="mx-auto max-w-[1600px] px-4 py-3">
    <div class="mb-3 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-[var(--gov-text)]">批量导入</h1>
        <p class="mt-0.5 text-xs text-[var(--gov-text-muted)]">
          管理员上传文件（不立即处理），按目录树存放，可分配给检录员进行批量识别
        </p>
      </div>
      <div class="flex gap-2">
        <button class="gov-btn-secondary text-sm" @click="loadUploadedTasks">
          <svg class="mr-1 inline h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
          刷新
        </button>
      </div>
    </div>

    <!-- Upload area -->
    <div class="gov-card mb-3 p-4">
      <div class="flex items-center gap-4">
        <label
          class="flex cursor-pointer items-center gap-2 rounded-lg border-2 border-dashed border-[var(--gov-primary)]/40 bg-[var(--gov-primary)]/5 px-6 py-3 transition hover:border-[var(--gov-primary)] hover:bg-[var(--gov-primary)]/10"
          @dragover.prevent
          @drop.prevent="handleDrop"
        >
          <svg class="h-5 w-5 text-[var(--gov-primary)]" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
          <span class="text-sm font-medium text-[var(--gov-primary)]">选择文件夹上传</span>
          <input
            ref="folderInput"
            type="file"
            webkitdirectory
            multiple
            class="hidden"
            @change="handleFolderSelect"
          />
        </label>
        <div v-if="uploading" class="flex items-center gap-2 text-sm text-[var(--gov-text-muted)]">
          <svg class="h-4 w-4 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/></svg>
          上传中 {{ uploadProgress.done }}/{{ uploadProgress.total }}
        </div>
        <div v-if="uploadProgress.done > 0 && !uploading" class="text-sm text-emerald-600">
          ✓ 已上传 {{ uploadProgress.done }} 个文件
        </div>
      </div>
    </div>

    <div class="flex gap-3">
      <!-- Left: File tree -->
      <div class="w-[280px] shrink-0">
        <div class="gov-card overflow-hidden">
          <div class="border-b border-[var(--gov-border)] bg-slate-50 px-3 py-2">
            <span class="text-xs font-semibold text-[var(--gov-text)]">已上传文件</span>
            <span class="ml-1 text-xs text-[var(--gov-text-muted)]">{{ uploadedFiles.length }} 个</span>
          </div>
          <div v-if="loadingTasks" class="px-3 py-6 text-center text-xs text-[var(--gov-text-muted)]">加载中…</div>
          <div v-else-if="!fileTree.length" class="px-3 py-6 text-center text-xs text-[var(--gov-text-muted)]">暂无已上传文件</div>
          <div v-else class="max-h-[600px] overflow-auto p-2">
            <TreeNode
              v-for="node in fileTree"
              :key="node.path"
              :node="node"
              :selected-path="selectedFolder"
              @select="handleSelectFolder"
            />
          </div>
        </div>
      </div>

      <!-- Right: Files + assignment -->
      <div class="min-w-0 flex-1 space-y-3">
        <div v-if="!selectedFolder" class="gov-card flex items-center justify-center py-10 text-sm text-[var(--gov-text-muted)]">
          <p>← 点击左侧目录节点查看文件</p>
        </div>

        <template v-else>
          <!-- Files in selected folder -->
          <div class="gov-card overflow-hidden">
            <div class="flex items-center justify-between border-b border-[var(--gov-border)] bg-slate-50 px-3 py-2">
              <div>
                <span class="text-sm font-semibold text-[var(--gov-text)]">{{ selectedFolder }}</span>
                <span class="ml-2 text-xs text-[var(--gov-text-muted)]">{{ folderFiles.length }} 个文件</span>
              </div>
              <div class="flex gap-2">
                <button
                  v-if="isAdmin && folderFiles.length && selectedTaskIds.length"
                  class="gov-btn-primary text-xs"
                  @click="showAssignModal = true"
                >分配给检录员 ({{ selectedTaskIds.length }})</button>
                <button
                  v-if="(isAdmin || isCataloger) && folderFiles.length && selectedTaskIds.length"
                  class="gov-btn-primary text-xs"
                  :disabled="submittingBatch"
                  @click="submitForRecognition"
                >{{ submittingBatch ? '提交中…' : `提交批量识别 (${selectedTaskIds.length})` }}</button>
                <button
                  v-if="folderFiles.length"
                  class="text-xs text-[var(--gov-primary)] hover:underline"
                  @click="toggleSelectAll"
                >{{ allSelected ? '取消全选' : '全选' }}</button>
              </div>
            </div>
            <div v-if="!folderFiles.length" class="px-4 py-6 text-center text-xs text-[var(--gov-text-muted)]">该目录下暂无文件</div>
            <div v-else class="grid grid-cols-5 gap-2 p-3 xl:grid-cols-6 2xl:grid-cols-8">
              <div
                v-for="f in folderFiles"
                :key="f.id"
                class="group relative cursor-pointer rounded-lg border bg-white p-1 transition"
                :class="selectedTaskIds.includes(f.id)
                  ? 'border-[var(--gov-primary)] ring-2 ring-[var(--gov-primary)]/30'
                  : 'border-[var(--gov-border)] hover:border-[var(--gov-primary)] hover:shadow-md'"
                @click="toggleSelect(f.id)"
              >
                <div class="relative aspect-[3/4] overflow-hidden rounded bg-slate-100">
                  <img
                    :src="fileUrl(f.id)"
                    :alt="f.filename"
                    class="h-full w-full object-cover"
                    loading="lazy"
                    @click.stop="previewFile = f"
                  />
                  <span
                    class="absolute bottom-0.5 right-0.5 rounded px-1 py-0.5 text-[9px] font-medium"
                    :class="f.status === 'uploaded' ? 'bg-blue-100 text-blue-700' : f.status === 'done' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'"
                  >{{ statusLabel(f.status) }}</span>
                  <div
                    class="absolute left-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded border-2 shadow-sm"
                    :class="selectedTaskIds.includes(f.id) ? 'border-[var(--gov-primary)] bg-[var(--gov-primary)]' : 'border-gray-400 bg-white/90'"
                  >
                    <svg v-if="selectedTaskIds.includes(f.id)" class="h-3.5 w-3.5 text-white" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                  </div>
                </div>
                <p class="mt-1 truncate text-center text-[10px] text-[var(--gov-text-muted)]" :title="f.filename">{{ baseFilename(f.filename) }}</p>
                <p v-if="f.assignee_username" class="truncate text-center text-[9px] text-blue-600">→ {{ f.assignee_username }}</p>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- Assign modal -->
    <div v-if="showAssignModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50" @click.self="showAssignModal = false">
      <div class="w-[360px] rounded-xl bg-white p-5 shadow-2xl">
        <h3 class="mb-3 text-sm font-bold text-[var(--gov-text)]">分配任务给检录员</h3>
        <p class="mb-3 text-xs text-[var(--gov-text-muted)]">已选择 {{ selectedTaskIds.length }} 个文件</p>
        <select v-model="assignTarget" class="mb-4 w-full rounded-lg border border-[var(--gov-border)] px-3 py-2 text-sm">
          <option value="">选择检录员…</option>
          <option v-for="u in operators" :key="u.id" :value="u.username">{{ u.display_name || u.username }}</option>
        </select>
        <div class="flex justify-end gap-2">
          <button class="gov-btn-secondary text-sm" @click="showAssignModal = false">取消</button>
          <button class="gov-btn-primary text-sm" :disabled="!assignTarget || assigning" @click="doAssign">
            {{ assigning ? '分配中…' : '确认分配' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Image preview modal -->
    <div v-if="previewFile" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="previewFile = null">
      <div class="relative max-h-[90vh] max-w-[90vw] overflow-auto rounded-xl bg-white p-2 shadow-2xl">
        <button class="absolute right-3 top-3 z-10 rounded-full bg-black/50 p-1.5 text-white transition hover:bg-black/70" @click="previewFile = null">
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M6 18L18 6M6 6l12 12"/></svg>
        </button>
        <img :src="fileUrl(previewFile.id)" :alt="previewFile.filename" class="max-h-[85vh] rounded" />
        <p class="mt-1 text-center text-xs text-[var(--gov-text-muted)]">{{ previewFile.filename }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue'
import { uploadOnly, assignTasks, getTaskFileUrl, listTasks, listMyAssignedTasks, submitBatch } from '@/api/ocr.js'
import { listUsers } from '@/api/admin.js'
import { useAuthState } from '@/composables/useAuthState.js'
import TreeNode from '@/features/storage/TreeNode.vue'

const uploading = ref(false)
const uploadProgress = ref({ done: 0, total: 0 })
const uploadedFiles = ref([])
const loadingTasks = ref(true)
const selectedFolder = ref('')
const selectedTaskIds = ref([])
const showAssignModal = ref(false)
const assignTarget = ref('')
const assigning = ref(false)
const previewFile = ref(null)
const operators = ref([])
const folderInput = ref(null)
const submittingBatch = ref(false)

const authState = useAuthState()
const isAdmin = computed(() => Boolean(authState.auth.value?.is_admin))
const isCataloger = computed(() => authState.auth.value?.role === 'operator' || Boolean(authState.auth.value?.is_admin))

function taskPath(task) {
  return String(task?.filename || task?.file_path || task?.filePath || '').trim()
}

function fileUrl(taskId) {
  return getTaskFileUrl(taskId)
}

function baseFilename(filename) {
  if (!filename) return ''
  const idx = Math.max(filename.lastIndexOf('/'), filename.lastIndexOf('\\'))
  return idx >= 0 ? filename.substring(idx + 1) : filename
}

function statusLabel(status) {
  const map = { uploaded: '待分配', queued: '排队中', processing: '处理中', done: '已完成', failed: '失败' }
  return map[status] || status || '未知'
}

const fileTree = computed(() => {
  const paths = new Map()
  for (const f of uploadedFiles.value) {
    const parts = (f.filename || '').split(/[/\\]/)
    let current = ''
    for (let i = 0; i < parts.length - 1; i++) {
      const parent = current
      current = current ? current + '/' + parts[i] : parts[i]
      if (!paths.has(current)) {
        paths.set(current, { name: parts[i], path: current, type: 'folder', children: [], record_count: 0 })
      }
      if (parent && paths.has(parent)) {
        const parentNode = paths.get(parent)
        if (!parentNode.children.find((c) => c.path === current)) {
          parentNode.children.push(paths.get(current))
        }
      }
    }
    // Count files per folder
    if (current && paths.has(current)) {
      paths.get(current).record_count++
    }
  }
  // Return root-level nodes
  const roots = []
  for (const [path, node] of paths) {
    if (!path.includes('/')) roots.push(node)
  }
  // If no folders, create a virtual root
  if (!roots.length && uploadedFiles.value.length) {
    return [{ name: '（根目录）', path: '', type: 'folder', children: [], record_count: uploadedFiles.value.length }]
  }
  return roots
})

const folderFiles = computed(() => {
  if (!selectedFolder.value && selectedFolder.value !== '') return []
  return uploadedFiles.value.filter((f) => {
    const fn = f.filename || ''
    if (selectedFolder.value === '') return !fn.includes('/') && !fn.includes('\\')
    // Match files directly in this folder OR in subfolders of this folder
    return fn.startsWith(selectedFolder.value + '/')
  })
})

const allSelected = computed(() => {
  return folderFiles.value.length > 0 && folderFiles.value.every((f) => selectedTaskIds.value.includes(f.id))
})

function toggleSelect(id) {
  const idx = selectedTaskIds.value.indexOf(id)
  if (idx >= 0) selectedTaskIds.value.splice(idx, 1)
  else selectedTaskIds.value.push(id)
}

function toggleSelectAll() {
  if (allSelected.value) {
    const ids = new Set(folderFiles.value.map((f) => f.id))
    selectedTaskIds.value = selectedTaskIds.value.filter((id) => !ids.has(id))
  } else {
    const existing = new Set(selectedTaskIds.value)
    for (const f of folderFiles.value) {
      if (!existing.has(f.id)) selectedTaskIds.value.push(f.id)
    }
  }
}

function handleSelectFolder(node) {
  selectedFolder.value = node.path
  selectedTaskIds.value = []
}

async function handleFolderSelect(e) {
  const files = Array.from(e.target.files || [])
  if (!files.length) return
  await uploadFiles(files)
  e.target.value = ''
}

async function handleDrop(e) {
  const files = Array.from(e.dataTransfer.files || [])
  if (!files.length) return
  await uploadFiles(files)
}

async function uploadFiles(files) {
  uploading.value = true
  uploadProgress.value = { done: 0, total: files.length }
  const batchId = 'import_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8)
  for (const file of files) {
    try {
      const relativePath = file.webkitRelativePath || file.name
      await uploadOnly(file, relativePath, batchId)
    } catch (err) {
      console.error('Upload failed:', file.name, err)
    }
    uploadProgress.value.done++
  }
  uploading.value = false
  await loadUploadedTasks()
}

async function loadUploadedTasks() {
  loadingTasks.value = true
  try {
    let data
    if (isCataloger.value && !isAdmin.value) {
      // Catalogers see their assigned tasks
      const resp = await listMyAssignedTasks({ status: 'uploaded', page_size: 2000 })
      data = resp.data
    } else {
      // Admins see all uploaded tasks
      const resp = await listTasks({ status: 'uploaded', page_size: 2000 })
      data = resp.data
    }
    const taskItems = Array.isArray(data?.tasks) ? data.tasks : Array.isArray(data?.items) ? data.items : []
    uploadedFiles.value = taskItems.map((t) => ({
      id: t.id,
      filename: taskPath(t),
      status: t.status || '',
      assignee_username: t.assignee_username || t.assigneeUsername || '',
    }))
  } catch (error) {
    console.error('Load uploaded tasks failed:', error)
    uploadedFiles.value = []
  } finally {
    loadingTasks.value = false
  }
}

async function submitForRecognition() {
  if (!selectedTaskIds.value.length) return
  submittingBatch.value = true
  try {
    await submitBatch(selectedTaskIds.value)
    selectedTaskIds.value = []
    await loadUploadedTasks()
  } catch (err) {
    console.error('Submit batch failed:', err)
  } finally {
    submittingBatch.value = false
  }
}

async function loadOperators() {
  try {
    const { data } = await listUsers()
    const list = data.items || data.users || (Array.isArray(data) ? data : [])
    operators.value = list.filter((u) => u.role === 'operator' || u.role === 'admin')
  } catch {
    operators.value = []
  }
}

async function doAssign() {
  if (!assignTarget.value || !selectedTaskIds.value.length) return
  assigning.value = true
  try {
    await assignTasks(selectedTaskIds.value, assignTarget.value)
    showAssignModal.value = false
    selectedTaskIds.value = []
    await loadUploadedTasks()
  } catch (err) {
    console.error('Assign failed:', err)
  } finally {
    assigning.value = false
  }
}

onMounted(() => {
  loadUploadedTasks()
  loadOperators()
})
</script>
