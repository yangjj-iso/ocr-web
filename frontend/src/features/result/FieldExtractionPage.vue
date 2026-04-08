<template>
  <div class="flex h-screen flex-col overflow-hidden bg-gray-50">
    <div class="flex flex-shrink-0 items-center justify-between border-b border-gray-200 bg-white px-4 py-2">
      <div class="flex items-center space-x-3">
        <button class="rounded p-1 transition hover:bg-gray-100" title="返回" @click="goBack">
          <svg class="h-5 w-5 text-gray-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M15 19l-7-7 7-7" /></svg>
        </button>
        <h2 class="text-sm font-semibold text-gray-800">字段提取</h2>
        <span class="rounded-full bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-600">档案要素识别</span>
      </div>
      <div v-if="selectedTask" class="flex items-center space-x-2 text-xs text-gray-500">
        <span class="truncate max-w-[260px]">{{ selectedTask.filename }}</span>
        <span>{{ selectedTask.page_count || 0 }} 页</span>
      </div>
    </div>

    <div class="flex min-h-0 flex-1">
      <!-- Left: task list -->
      <aside class="flex w-64 flex-shrink-0 flex-col border-r border-gray-200 bg-white">
        <div class="flex items-center justify-between border-b border-gray-100 px-4 py-2.5">
          <span class="text-xs font-semibold text-gray-600">已完成任务</span>
          <span class="text-[10px] text-gray-400">{{ doneTasks.length }} 项</span>
        </div>
        <div v-if="tasksLoading" class="flex flex-1 items-center justify-center">
          <svg class="h-5 w-5 animate-spin text-blue-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" /></svg>
        </div>
        <div v-else-if="!doneTasks.length" class="flex flex-1 items-center justify-center px-4 text-center text-xs text-gray-400">
          暂无已完成任务，请先去工作台处理文件
        </div>
        <ul v-else class="flex-1 overflow-y-auto">
          <li
            v-for="t in doneTasks"
            :key="t.id"
            class="cursor-pointer border-b border-gray-50 px-4 py-3 transition"
            :class="selectedTaskId === t.id ? 'bg-blue-50 border-l-2 border-l-blue-500' : 'hover:bg-gray-50'"
            @click="selectTask(t)"
          >
            <p class="truncate text-xs font-medium" :class="selectedTaskId === t.id ? 'text-blue-700' : 'text-gray-700'">{{ t.filename }}</p>
            <p class="mt-0.5 text-[10px] text-gray-400">{{ t.page_count || 0 }} 页 · {{ formatTime(t.updated_at) }}</p>
          </li>
        </ul>
      </aside>

      <!-- Middle: field extraction cards -->
      <section class="flex min-w-0 flex-1 flex-col bg-white">
        <div v-if="!selectedTaskId" class="flex flex-1 items-center justify-center text-sm text-gray-400">
          请从左侧选择一个已完成的任务
        </div>
        <template v-else>
          <div class="flex flex-shrink-0 items-center justify-between border-b border-gray-100 px-5 py-3">
            <div>
              <h3 class="text-sm font-semibold text-gray-800">档案字段提取</h3>
              <p class="mt-0.5 text-xs text-gray-400">基于识别结果自动提取关键归档字段，可手动修正</p>
            </div>
            <button
              class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition"
              :class="aiLoading ? 'bg-indigo-50 text-indigo-400' : 'bg-indigo-600 text-white hover:bg-indigo-700'"
              :disabled="aiLoading"
              @click="runAiExtraction"
            >
              <svg v-if="aiLoading" class="h-3.5 w-3.5 animate-spin" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" /></svg>
              <svg v-else class="h-3.5 w-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
              {{ aiLoading ? '提取中…' : 'AI 智能提取' }}
            </button>
          </div>

          <div class="flex-1 overflow-y-auto px-5 py-4">
            <div v-if="fieldsLoading" class="flex items-center justify-center py-16 text-sm text-gray-400">
              <svg class="mr-2 h-5 w-5 animate-spin" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" /></svg>
              正在提取字段…
            </div>

            <div v-else-if="fieldsError" class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-700">
              {{ fieldsError }}
            </div>

            <div v-else class="space-y-3">
              <div v-if="aiFields" class="mb-3 flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2">
                <svg class="h-4 w-4 flex-shrink-0 text-green-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                <span class="text-xs text-green-700">已完成 AI 智能提取，字段已自动择优合并</span>
              </div>

              <div
                v-for="field in FIELD_LABELS"
                :key="field.key"
                class="rounded-xl border transition"
                :class="fieldHasConflict(field.key) ? 'border-amber-200 bg-amber-50/50' : 'border-gray-100 bg-white hover:border-gray-200 hover:shadow-sm'"
              >
                <div class="flex items-start gap-3 px-4 py-3">
                  <div
                    class="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg text-xs font-bold"
                    :class="fieldHasConflict(field.key) ? 'bg-amber-100 text-amber-700' : fieldIconClass(field.key)"
                  >{{ field.icon }}</div>
                  <div class="min-w-0 flex-1">
                    <div class="flex items-center justify-between">
                      <span class="text-xs font-medium text-gray-500">{{ field.key }}</span>
                      <div class="flex items-center gap-1">
                        <span v-if="fieldHasConflict(field.key)" class="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-600">有差异</span>
                        <span v-else-if="aiFields && fieldDisplayValue(field.key)" class="rounded bg-green-100 px-1.5 py-0.5 text-[10px] font-medium text-green-600">已确认</span>
                        <button
                          v-if="editingFieldKey !== field.key"
                          class="rounded px-1.5 py-0.5 text-[10px] text-gray-400 hover:bg-gray-100 hover:text-blue-600"
                          @click.stop="startFieldEdit(field.key)"
                        >编辑</button>
                      </div>
                    </div>

                    <template v-if="editingFieldKey === field.key">
                      <textarea
                        v-model="editingFieldValue"
                        rows="2"
                        class="mt-1.5 w-full rounded-lg border border-blue-200 bg-white px-3 py-2 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-blue-100"
                      />
                      <div class="mt-1.5 flex items-center justify-end gap-2">
                        <button class="rounded bg-gray-100 px-3 py-1 text-xs text-gray-600 hover:bg-gray-200" @click="cancelFieldEdit">取消</button>
                        <button class="rounded bg-blue-600 px-3 py-1 text-xs text-white hover:bg-blue-700" @click="saveFieldEdit(field.key)">保存</button>
                      </div>
                    </template>

                    <template v-else>
                      <p class="mt-1 text-sm leading-6 text-gray-800" :class="{ 'italic text-gray-300': !fieldDisplayValue(field.key) }">
                        {{ fieldDisplayValue(field.key) || '未提取到' }}
                      </p>
                    </template>

                    <div v-if="fieldHasConflict(field.key)" class="mt-2 space-y-1 border-t border-amber-100 pt-2">
                      <p class="text-[11px] text-gray-500"><span class="font-medium text-gray-600">规则：</span>{{ fieldConflicts[field.key]?.rule || '—' }}</p>
                      <p class="text-[11px] text-gray-500"><span class="font-medium text-indigo-600">AI：</span>{{ fieldConflicts[field.key]?.llm || '—' }}</p>
                      <p v-if="fieldConflicts[field.key]?.evidence" class="text-[11px] italic text-gray-400">依据：{{ fieldConflicts[field.key].evidence }}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>
      </section>

      <!-- Right: source file preview -->
      <section v-if="selectedTaskId" class="flex w-[42%] flex-shrink-0 flex-col border-l border-gray-200 bg-gray-50">
        <div class="flex flex-shrink-0 items-center justify-between border-b border-gray-100 bg-white px-4 py-2.5">
          <span class="text-xs font-semibold text-gray-600">源文件预览</span>
          <div v-if="totalPages > 1" class="flex items-center space-x-1">
            <button class="rounded px-1.5 py-0.5 text-xs text-gray-500 hover:bg-gray-100" :disabled="previewPage <= 1" @click="previewPage = Math.max(1, previewPage - 1)">上一页</button>
            <span class="text-xs text-gray-500">{{ previewPage }} / {{ totalPages }}</span>
            <button class="rounded px-1.5 py-0.5 text-xs text-gray-500 hover:bg-gray-100" :disabled="previewPage >= totalPages" @click="previewPage = Math.min(totalPages, previewPage + 1)">下一页</button>
          </div>
        </div>
        <div class="flex flex-1 items-start justify-center overflow-auto p-3">
          <iframe v-if="isPdf && pdfImgFailed" :src="fileUrl" class="h-full w-full rounded border-0" />
          <img v-else :src="previewImageUrl" class="max-w-full rounded shadow" @error="onImgError" />
        </div>
      </section>
    </div>

    <transition name="fade">
      <div v-if="toast" class="fixed bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-slate-900 px-4 py-2 text-sm text-white shadow-lg">
        {{ toast }}
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'

import { aiExtractFields, getTaskFields, getTaskFileUrl, getTaskPageImageUrl, getTasks } from '@/api/ocr.js'

const router = useRouter()

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/')
}

const FIELD_LABELS = [
  { key: '档号', icon: '#' },
  { key: '文号', icon: '§' },
  { key: '题名', icon: 'T' },
  { key: '责任者', icon: '人' },
  { key: '日期', icon: '日' },
  { key: '页数', icon: '页' },
  { key: '密级', icon: '密' },
  { key: '备注', icon: '注' },
]

function fieldIconClass(key) {
  const map = {
    '档号': 'bg-blue-100 text-blue-600',
    '文号': 'bg-purple-100 text-purple-600',
    '题名': 'bg-indigo-100 text-indigo-600',
    '责任者': 'bg-teal-100 text-teal-600',
    '日期': 'bg-orange-100 text-orange-600',
    '页数': 'bg-slate-100 text-slate-500',
    '密级': 'bg-red-100 text-red-600',
    '备注': 'bg-gray-100 text-gray-500',
  }
  return map[key] || 'bg-slate-100 text-slate-500'
}

// --- toast ---
const toast = ref('')
let toastTimer = null
function showToast(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 2200)
}

// --- task list ---
const tasksLoading = ref(true)
const allTasks = ref([])
const doneTasks = computed(() => allTasks.value.filter(t => t.status === 'done'))
const selectedTaskId = ref(null)
const selectedTask = computed(() => allTasks.value.find(t => t.id === selectedTaskId.value) || null)

async function loadTasks() {
  tasksLoading.value = true
  try {
    const { data } = await getTasks(1, 500)
    allTasks.value = data.tasks || []
  } catch (_) {
    allTasks.value = []
  } finally {
    tasksLoading.value = false
  }
}
loadTasks()

function selectTask(t) {
  if (selectedTaskId.value === t.id) return
  selectedTaskId.value = t.id
  ruleFields.value = {}
  aiFields.value = null
  recommendedFields.value = null
  fieldConflicts.value = {}
  fieldsError.value = ''
  previewPage.value = 1
  pdfImgFailed.value = false
  loadRuleFields()
}

// --- preview ---
const previewPage = ref(1)
const pdfImgFailed = ref(false)
const isPdf = computed(() => {
  const name = (selectedTask.value?.filename || '').toLowerCase()
  return name.endsWith('.pdf')
})
const totalPages = computed(() => selectedTask.value?.page_count || 1)
const fileUrl = computed(() => selectedTaskId.value ? getTaskFileUrl(selectedTaskId.value) : '')
const previewImageUrl = computed(() => {
  if (!selectedTaskId.value) return ''
  return isPdf.value ? getTaskPageImageUrl(selectedTaskId.value, previewPage.value) : fileUrl.value
})

function onImgError() {
  if (isPdf.value) pdfImgFailed.value = true
}

watch(previewImageUrl, () => { pdfImgFailed.value = false })

// --- fields ---
const ruleFields = ref({})
const aiFields = ref(null)
const recommendedFields = ref(null)
const fieldConflicts = ref({})
const fieldsLoading = ref(false)
const aiLoading = ref(false)
const fieldsError = ref('')
const editingFieldKey = ref('')
const editingFieldValue = ref('')

async function loadRuleFields() {
  if (!selectedTaskId.value) return
  fieldsLoading.value = true
  fieldsError.value = ''
  try {
    const { data } = await getTaskFields(selectedTaskId.value)
    ruleFields.value = data.fields || {}
  } catch (err) {
    fieldsError.value = err.response?.data?.detail || '字段提取失败'
  } finally {
    fieldsLoading.value = false
  }
}

async function runAiExtraction() {
  if (!selectedTaskId.value) return
  aiLoading.value = true
  fieldsError.value = ''
  try {
    const { data } = await aiExtractFields(selectedTaskId.value)
    ruleFields.value = data.rule_fields || {}
    aiFields.value = data.llm_fields || {}
    recommendedFields.value = data.recommended_fields || {}
    fieldConflicts.value = data.conflicts || {}
    showToast('AI 智能提取完成')
  } catch (err) {
    const detail = err.response?.data?.detail || ''
    fieldsError.value = detail.includes('disabled') || detail.includes('not configured')
      ? '智能提取服务暂未启用，请联系管理员检查本地配置后重试。'
      : detail || 'AI 提取失败'
  } finally {
    aiLoading.value = false
  }
}

function fieldDisplayValue(key) {
  if (recommendedFields.value) return recommendedFields.value[key] || ''
  return ruleFields.value[key] || ''
}

function fieldHasConflict(key) {
  return !!fieldConflicts.value[key]
}

function startFieldEdit(key) {
  editingFieldKey.value = key
  editingFieldValue.value = fieldDisplayValue(key)
}

function cancelFieldEdit() {
  editingFieldKey.value = ''
  editingFieldValue.value = ''
}

function saveFieldEdit(key) {
  if (recommendedFields.value) {
    recommendedFields.value[key] = editingFieldValue.value
  } else {
    ruleFields.value[key] = editingFieldValue.value
  }
  if (fieldConflicts.value[key]) delete fieldConflicts.value[key]
  editingFieldKey.value = ''
  editingFieldValue.value = ''
  showToast('已保存')
}

function formatTime(v) {
  if (!v) return ''
  return dayjs(v).format('MM-DD HH:mm')
}
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.25s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
