<template>
  <AppShell>
    <div class="p-5 space-y-4">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="gov-page-header">规则配置</h1>
          <p class="text-sm text-[var(--gov-text-muted)] mt-0.5">管理策略快照与规则，用于批次处理时版本化引用</p>
        </div>
        <div class="flex items-center gap-2">
          <button @click="openCreateForm" class="px-3 py-1.5 text-sm bg-green-600 text-white rounded-md hover:bg-green-700 transition">新建快照</button>
          <button @click="loadSnapshots" class="gov-btn text-sm">刷新</button>
        </div>
      </div>

      <div v-if="opMsg" class="rounded-lg border p-3 text-sm" :class="opMsg.ok ? 'border-green-200 bg-green-50 text-green-700' : 'border-red-200 bg-red-50 text-red-700'">
        {{ opMsg.text }}
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-4">
        <section class="rounded-lg border border-[var(--gov-border)] bg-white p-3 max-h-[calc(100vh-180px)] overflow-y-auto">
          <p class="text-xs font-semibold text-[var(--gov-text-muted)] mb-2">策略快照</p>
          <div class="space-y-2">
            <button
              v-for="s in snapshots"
              :key="s.id"
              @click="selectSnapshot(s)"
              class="w-full text-left rounded border p-2"
              :class="selected?.id === s.id ? 'border-[var(--gov-primary)] bg-blue-50' : 'border-[var(--gov-border)] bg-white hover:bg-slate-50'"
            >
              <p class="text-sm font-medium text-[var(--gov-text)]">{{ s.version || s.id }}</p>
              <p class="text-xs text-[var(--gov-text-muted)] mt-1">{{ fmt(s.created_at) }}</p>
            </button>
            <p v-if="!snapshots.length && !loading" class="text-sm text-[var(--gov-text-muted)]">暂无快照</p>
          </div>
        </section>

        <section class="rounded-lg border border-[var(--gov-border)] bg-white p-4 overflow-auto max-h-[calc(100vh-180px)]">
          <!-- 编辑模式 -->
          <div v-if="editing" class="space-y-4">
            <div class="flex items-center justify-between">
              <p class="text-sm font-semibold text-[var(--gov-text)]">{{ editingNew ? '新建策略快照' : '编辑规则' }}</p>
              <div class="flex gap-2">
                <button @click="cancelEdit" class="px-3 py-1.5 text-sm border border-[var(--gov-border)] rounded hover:bg-slate-50">取消</button>
                <button @click="saveEdit" :disabled="saving" class="gov-btn text-sm disabled:opacity-50">
                  {{ saving ? '保存中...' : '保存' }}
                </button>
              </div>
            </div>

            <div v-if="editingNew" class="space-y-3">
              <div>
                <label class="text-xs font-medium text-[var(--gov-text-muted)]">版本号</label>
                <input v-model="editForm.version" class="mt-1 w-full border border-[var(--gov-border)] rounded px-3 py-1.5 text-sm" placeholder="如 v1.0" />
              </div>
            </div>

            <div class="space-y-3">
              <div>
                <label class="text-xs font-medium text-[var(--gov-text-muted)]">分件规则</label>
                <textarea v-model="editForm.split_rules" rows="3" class="mt-1 w-full border border-[var(--gov-border)] rounded px-3 py-2 text-sm font-mono resize-none" placeholder='JSON 数组，如 [{"type":"boundary","pattern":"..."}]'></textarea>
              </div>
              <div>
                <label class="text-xs font-medium text-[var(--gov-text-muted)]">排序规则</label>
                <textarea v-model="editForm.sort_rules" rows="2" class="mt-1 w-full border border-[var(--gov-border)] rounded px-3 py-2 text-sm font-mono resize-none" placeholder='如 {"primary":"date","secondary":"doc_no"}'></textarea>
              </div>
              <div>
                <label class="text-xs font-medium text-[var(--gov-text-muted)]">编号规则</label>
                <textarea v-model="editForm.numbering_rules" rows="2" class="mt-1 w-full border border-[var(--gov-border)] rounded px-3 py-2 text-sm font-mono resize-none" placeholder='如 {"prefix":"A-","start":1}'></textarea>
              </div>
              <div>
                <label class="text-xs font-medium text-[var(--gov-text-muted)]">保管期限规则</label>
                <textarea v-model="editForm.retention_rules" rows="2" class="mt-1 w-full border border-[var(--gov-border)] rounded px-3 py-2 text-sm font-mono resize-none" placeholder='如 [{"match":"密级","period":"永久"}]'></textarea>
              </div>
              <div>
                <label class="text-xs font-medium text-[var(--gov-text-muted)]">字段提取规则</label>
                <textarea v-model="editForm.field_rules" rows="2" class="mt-1 w-full border border-[var(--gov-border)] rounded px-3 py-2 text-sm font-mono resize-none" placeholder='如 {"title":"llm","doc_no":"regex"}'></textarea>
              </div>
              <div>
                <label class="text-xs font-medium text-[var(--gov-text-muted)]">标签规则</label>
                <textarea v-model="editForm.tag_rules" rows="2" class="mt-1 w-full border border-[var(--gov-border)] rounded px-3 py-2 text-sm font-mono resize-none" placeholder='如 [{"category":"文种","values":["通知","报告"]}]'></textarea>
              </div>
              <div>
                <label class="text-xs font-medium text-[var(--gov-text-muted)]">审核阈值</label>
                <textarea v-model="editForm.review_thresholds" rows="2" class="mt-1 w-full border border-[var(--gov-border)] rounded px-3 py-2 text-sm font-mono resize-none" placeholder='如 {"boundary_confidence":0.7,"metadata_confidence":0.6}'></textarea>
              </div>
            </div>
          </div>

          <!-- 查看模式 -->
          <div v-else>
            <div class="flex items-center justify-between">
              <div>
                <p class="text-sm font-semibold text-[var(--gov-text)]">规则详情</p>
                <p class="text-xs text-[var(--gov-text-muted)] mt-1">{{ selected?.version || selected?.id || '未选择快照' }}</p>
              </div>
              <button v-if="selected" @click="openEditForm" class="px-3 py-1.5 text-sm border border-[var(--gov-border)] rounded hover:bg-slate-50">编辑</button>
            </div>
            <pre class="mt-3 rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] p-3 text-xs leading-5 whitespace-pre-wrap break-words">{{ prettyRules }}</pre>
          </div>
        </section>
      </div>
    </div>
  </AppShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import dayjs from 'dayjs'

import AppShell from '@/layouts/AppShell.vue'
import { listPolicySnapshots, getPolicySnapshot, createPolicySnapshot, updatePolicySnapshot } from '@/api/archive'

const loading = ref(false)
const saving = ref(false)
const snapshots = ref([])
const selected = ref(null)
const selectedDetail = ref(null)
const editing = ref(false)
const editingNew = ref(false)
const opMsg = ref(null)

const editForm = ref({
  version: '',
  split_rules: '',
  sort_rules: '',
  numbering_rules: '',
  retention_rules: '',
  field_rules: '',
  tag_rules: '',
  review_thresholds: '',
})

function fmt(v) {
  return v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-'
}

const prettyRules = computed(() => {
  if (!selectedDetail.value) return '暂无规则详情'
  return JSON.stringify(selectedDetail.value, null, 2)
})

async function loadSnapshots() {
  loading.value = true
  try {
    const res = await listPolicySnapshots()
    snapshots.value = res.data?.items || res.data || []
    if (snapshots.value.length && !selected.value) {
      await selectSnapshot(snapshots.value[0])
    }
  } catch (e) {
    console.error('加载策略快照失败', e)
    snapshots.value = []
  } finally {
    loading.value = false
  }
}

async function selectSnapshot(snapshot) {
  selected.value = snapshot
  selectedDetail.value = null
  editing.value = false
  try {
    if (snapshot?.id) {
      const res = await getPolicySnapshot(snapshot.id)
      selectedDetail.value = res.data || snapshot
    } else {
      selectedDetail.value = snapshot
    }
  } catch (e) {
    console.error('加载策略详情失败', e)
    selectedDetail.value = snapshot
  }
}

function openCreateForm() {
  editing.value = true
  editingNew.value = true
  editForm.value = {
    version: '',
    split_rules: '',
    sort_rules: '',
    numbering_rules: '',
    retention_rules: '',
    field_rules: '',
    tag_rules: '',
    review_thresholds: '',
  }
}

function openEditForm() {
  editing.value = true
  editingNew.value = false
  const d = selectedDetail.value || {}
  editForm.value = {
    version: d.version || '',
    split_rules: safeStr(d.split_rules),
    sort_rules: safeStr(d.sort_rules),
    numbering_rules: safeStr(d.numbering_rules),
    retention_rules: safeStr(d.retention_rules),
    field_rules: safeStr(d.field_rules),
    tag_rules: safeStr(d.tag_rules),
    review_thresholds: safeStr(d.review_thresholds),
  }
}

function cancelEdit() {
  editing.value = false
  editingNew.value = false
}

function safeStr(v) {
  if (v == null) return ''
  if (typeof v === 'string') return v
  return JSON.stringify(v, null, 2)
}

function safeParse(v) {
  if (!v || !v.trim()) return null
  try { return JSON.parse(v) } catch { return v }
}

async function saveEdit() {
  saving.value = true
  opMsg.value = null
  try {
    const payload = {
      version: editForm.value.version || undefined,
      split_rules: safeParse(editForm.value.split_rules),
      sort_rules: safeParse(editForm.value.sort_rules),
      numbering_rules: safeParse(editForm.value.numbering_rules),
      retention_rules: safeParse(editForm.value.retention_rules),
      field_rules: safeParse(editForm.value.field_rules),
      tag_rules: safeParse(editForm.value.tag_rules),
      review_thresholds: safeParse(editForm.value.review_thresholds),
    }

    if (editingNew.value) {
      await createPolicySnapshot(payload)
      opMsg.value = { ok: true, text: '策略快照已创建' }
    } else {
      await updatePolicySnapshot(selected.value.id, payload)
      opMsg.value = { ok: true, text: '规则已更新' }
    }
    editing.value = false
    editingNew.value = false
    await loadSnapshots()
  } catch (e) {
    opMsg.value = { ok: false, text: '保存失败：' + (e?.response?.data?.detail || e.message || '未知错误') }
  } finally {
    saving.value = false
  }
}

onMounted(loadSnapshots)
</script>
