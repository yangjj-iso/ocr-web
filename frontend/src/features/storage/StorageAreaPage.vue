<template>
  <div class="mx-auto max-w-[1600px] px-4 py-3">
    <div class="mb-3 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-[var(--gov-text)]">存放区</h1>
        <p class="mt-0.5 text-xs text-[var(--gov-text-muted)]">
          以目录树形式浏览已归档记录的存放路径结构
          <template v-if="treeMeta.totalPaths > 0">
            · {{ treeMeta.totalPaths }} 个路径 · {{ treeMeta.totalRecords }} 条记录
          </template>
        </p>
      </div>
      <div class="flex gap-2">
        <button class="gov-btn-secondary text-sm" @click="loadTree">
          <svg class="mr-1 inline h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
          刷新
        </button>
        <button class="gov-btn text-sm" @click="$router.push('/')">返回工作台</button>
      </div>
    </div>

    <div class="flex gap-3">
      <!-- Left: Tree -->
      <div class="w-64 shrink-0">
        <div class="gov-card overflow-hidden">
          <div class="border-b border-[var(--gov-border)] bg-slate-50 px-4 py-2.5">
            <span class="text-xs font-semibold text-[var(--gov-text)]">目录结构</span>
          </div>
          <div v-if="loading" class="px-4 py-8 text-center text-xs text-[var(--gov-text-muted)]">加载中…</div>
          <div v-else-if="!tree.length" class="px-4 py-8 text-center text-xs text-[var(--gov-text-muted)]">
            暂无存放路径数据。<br/>文件经 OCR 处理后将自动生成存放路径。
          </div>
          <div v-else class="max-h-[calc(100vh-220px)] overflow-y-auto px-2 py-2">
            <TreeNode
              v-for="node in tree"
              :key="node.path"
              :node="node"
              :selected-path="selectedPath"
              :depth="0"
              @select="handleSelectNode"
            />
          </div>
        </div>
      </div>

      <!-- Right: Detail Panel -->
      <div class="min-w-0 flex-1">
        <div v-if="!selectedPath" class="gov-card flex items-center justify-center py-10 text-sm text-[var(--gov-text-muted)]">
          <p>← 点击左侧目录节点查看归档记录</p>
        </div>

        <div v-else class="space-y-3">
          <!-- Archive metadata table -->
          <div class="gov-card overflow-hidden">
            <div class="flex items-center justify-between border-b border-[var(--gov-border)] bg-slate-50 px-3 py-2">
              <div>
                <span class="text-sm font-semibold text-[var(--gov-text)]">{{ selectedPath }}</span>
                <span class="ml-2 text-xs text-[var(--gov-text-muted)]">{{ records.length }} 条归档记录</span>
              </div>
            </div>
            <div v-if="recordsLoading" class="px-4 py-6 text-center text-xs text-[var(--gov-text-muted)]">加载中…</div>
            <div v-else-if="!records.length && !pageFiles.length" class="px-4 py-6 text-center text-xs text-[var(--gov-text-muted)]">该路径下暂无归档记录</div>
            <table v-else-if="records.length" class="w-full text-sm">
              <thead class="bg-slate-50/60">
                <tr>
                  <th class="px-3 py-1.5 text-left text-xs font-medium text-[var(--gov-text-muted)]">档号</th>
                  <th class="px-3 py-1.5 text-left text-xs font-medium text-[var(--gov-text-muted)]">文号</th>
                  <th class="px-3 py-1.5 text-left text-xs font-medium text-[var(--gov-text-muted)]">责任者</th>
                  <th class="px-3 py-1.5 text-left text-xs font-medium text-[var(--gov-text-muted)]">题名</th>
                  <th class="px-3 py-1.5 text-left text-xs font-medium text-[var(--gov-text-muted)]">日期</th>
                  <th class="px-3 py-1.5 text-left text-xs font-medium text-[var(--gov-text-muted)]">页数</th>
                  <th class="px-3 py-1.5 text-left text-xs font-medium text-[var(--gov-text-muted)]">密级</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-[var(--gov-border)]">
                <tr v-for="r in records" :key="r.id" class="hover:bg-slate-50 transition">
                  <td class="px-3 py-1.5 text-xs font-mono text-[var(--gov-primary)]">{{ r.archive_no || '—' }}</td>
                  <td class="px-3 py-1.5 text-xs">{{ r.doc_no || '—' }}</td>
                  <td class="px-3 py-1.5 text-xs">{{ r.responsible || '—' }}</td>
                  <td class="px-3 py-1.5 text-xs max-w-[240px] truncate" :title="r.title">{{ r.title || '—' }}</td>
                  <td class="px-3 py-1.5 text-xs whitespace-nowrap">{{ r.date || '—' }}</td>
                  <td class="px-3 py-1.5 text-xs text-center">{{ r.pages || '—' }}</td>
                  <td class="px-3 py-1.5 text-xs">{{ r.classification || '—' }}</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- Page files with preview -->
          <div v-if="pageFiles.length" class="gov-card overflow-hidden">
            <div class="border-b border-[var(--gov-border)] bg-slate-50 px-3 py-2">
              <span class="text-xs font-semibold text-[var(--gov-text)]">原始页面文件</span>
              <span class="ml-2 text-xs text-[var(--gov-text-muted)]">{{ pageFiles.length }} 页</span>
            </div>
            <div class="grid grid-cols-5 gap-2 p-3 xl:grid-cols-6 2xl:grid-cols-8">
              <div
                v-for="pf in pageFiles"
                :key="pf.task_id"
                class="group cursor-pointer rounded-lg border border-[var(--gov-border)] bg-white p-1 transition hover:border-[var(--gov-primary)] hover:shadow-md"
                @click="openPreview(pf)"
              >
                <div class="relative aspect-[3/4] overflow-hidden rounded bg-slate-100">
                  <img
                    :src="fileUrl(pf.task_id)"
                    :alt="pf.filename"
                    class="h-full w-full object-cover transition group-hover:scale-105"
                    loading="lazy"
                  />
                  <span
                    class="absolute bottom-0.5 right-0.5 rounded px-1 py-0.5 text-[9px] font-medium"
                    :class="pf.status === 'done' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'"
                  >{{ pf.status === 'done' ? '已处理' : '待处理' }}</span>
                </div>
                <p class="mt-1 truncate text-center text-[10px] text-[var(--gov-text-muted)]" :title="pf.filename">{{ pf.filename }}</p>
              </div>
            </div>
          </div>
        </div>

        <!-- Image preview modal -->
        <div v-if="previewFile" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="previewFile = null">
          <div class="relative max-h-[90vh] max-w-[90vw] overflow-auto rounded-xl bg-white p-2 shadow-2xl">
            <button class="absolute right-3 top-3 z-10 rounded-full bg-black/50 p-1.5 text-white transition hover:bg-black/70" @click="previewFile = null">
              <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
            <img :src="fileUrl(previewFile.task_id)" :alt="previewFile.filename" class="max-h-[85vh] rounded" />
            <p class="mt-1 text-center text-xs text-[var(--gov-text-muted)]">{{ previewFile.filename }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, reactive } from 'vue'
import { getStorageTree, getStorageTreeRecords, getTaskFileUrl } from '@/api/ocr.js'
import TreeNode from './TreeNode.vue'

const tree = ref([])
const loading = ref(true)
const treeMeta = reactive({ totalPaths: 0, totalRecords: 0 })

const selectedPath = ref('')
const records = ref([])
const pageFiles = ref([])
const recordsLoading = ref(false)
const previewFile = ref(null)

async function loadTree() {
  loading.value = true
  try {
    const { data } = await getStorageTree()
    tree.value = data.tree || []
    treeMeta.totalPaths = data.total_paths || 0
    treeMeta.totalRecords = data.total_records || 0
  } catch {
    tree.value = []
  } finally {
    loading.value = false
  }
}

function fileUrl(taskId) {
  return getTaskFileUrl(taskId)
}

function openPreview(pf) {
  previewFile.value = pf
}

async function handleSelectNode(node) {
  selectedPath.value = node.path
  recordsLoading.value = true
  try {
    const { data } = await getStorageTreeRecords(node.path)
    records.value = data.records || []
    pageFiles.value = data.page_files || []
  } catch {
    records.value = []
    pageFiles.value = []
  } finally {
    recordsLoading.value = false
  }
}

onMounted(loadTree)
</script>
