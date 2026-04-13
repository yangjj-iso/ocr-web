<template>
  <div class="space-y-3">
    <div
      v-for="field in fieldDefs"
      :key="field.key"
      class="grid gap-1"
    >
      <label class="flex items-center gap-1.5 text-xs font-semibold text-[var(--gov-text-muted)]">
        {{ field.label }}
        <span v-if="field.required" class="text-red-500">*</span>
        <span
          v-if="field.source"
          class="rounded-full px-1.5 py-0.5 text-[9px] font-medium"
          :class="sourceClass(field.source)"
        >{{ sourceLabel(field.source) }}</span>
      </label>

      <!-- Tags (preservation_period / tag list) -->
      <div v-if="field.type === 'tags'" class="flex flex-wrap gap-1">
        <span
          v-for="tag in (form[field.key] || [])"
          :key="tag"
          class="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700"
        >
          {{ tag }}
          <button v-if="!readonly" class="hover:text-blue-900" @click="removeTag(field.key, tag)">×</button>
        </span>
        <input
          v-if="!readonly"
          class="h-6 rounded-full border border-dashed border-blue-200 bg-transparent px-2 text-xs text-blue-600 outline-none placeholder:text-blue-300 focus:border-blue-400"
          placeholder="+ 标签"
          @keydown.enter.prevent="addTag(field.key, $event.target.value); $event.target.value = ''"
        />
      </div>

      <!-- Select -->
      <select
        v-else-if="field.type === 'select'"
        v-model="form[field.key]"
        :disabled="readonly"
        class="w-full rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2 text-sm text-[var(--gov-text)] focus:border-[var(--gov-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--gov-primary)]/30 disabled:bg-slate-50 disabled:text-slate-400"
      >
        <option v-for="opt in field.options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
      </select>

      <!-- Textarea -->
      <textarea
        v-else-if="field.type === 'textarea'"
        v-model="form[field.key]"
        :rows="field.rows || 3"
        :readonly="readonly"
        :placeholder="field.placeholder || ''"
        class="w-full resize-none rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2 text-sm text-[var(--gov-text)] leading-relaxed focus:border-[var(--gov-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--gov-primary)]/30 read-only:bg-slate-50 read-only:text-slate-500"
      />

      <!-- Default: text input -->
      <input
        v-else
        v-model="form[field.key]"
        :type="field.type || 'text'"
        :readonly="readonly"
        :placeholder="field.placeholder || ''"
        class="w-full rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2 text-sm text-[var(--gov-text)] focus:border-[var(--gov-primary)] focus:outline-none focus:ring-1 focus:ring-[var(--gov-primary)]/30 read-only:bg-slate-50 read-only:text-slate-500"
      />

      <!-- Diff hint: original value -->
      <p
        v-if="!readonly && field.original !== undefined && field.original !== form[field.key]"
        class="text-[10px] text-amber-600"
      >
        原值：{{ field.original || '（空）' }}
      </p>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Object, default: () => ({}) },
  fieldDefs: {
    type: Array,
    default: () => [
      { key: 'title', label: '题名', source: 'llm' },
      { key: 'responsible', label: '责任者', source: 'llm' },
      { key: 'doc_no', label: '文号', source: 'rule' },
      { key: 'date', label: '形成日期', type: 'date', source: 'rule' },
      { key: 'page_count', label: '页数', source: 'rule', readonly: true },
      { key: 'preservation_period', label: '保管期限', type: 'select', source: 'rule', options: [
        { value: '永久', label: '永久' },
        { value: '30年', label: '30年' },
        { value: '10年', label: '10年' },
      ]},
      { key: 'tags', label: '主题标签', type: 'tags', source: 'llm' },
      { key: 'notes', label: '备注', type: 'textarea' },
    ],
  },
  readonly: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const form = reactive({ ...props.modelValue })

watch(() => props.modelValue, (v) => Object.assign(form, v), { deep: true })
watch(form, (v) => emit('update:modelValue', { ...v }), { deep: true })

function addTag(key, value) {
  const v = (value || '').trim()
  if (!v) return
  if (!Array.isArray(form[key])) form[key] = []
  if (!form[key].includes(v)) form[key].push(v)
}

function removeTag(key, tag) {
  if (Array.isArray(form[key])) {
    form[key] = form[key].filter((t) => t !== tag)
  }
}

function sourceLabel(src) {
  return { rule: '规则', llm: 'AI', manual: '人工' }[src] || src
}

function sourceClass(src) {
  return {
    rule: 'bg-blue-50 text-blue-600',
    llm: 'bg-purple-50 text-purple-600',
    manual: 'bg-amber-50 text-amber-600',
  }[src] || 'bg-slate-100 text-slate-500'
}
</script>
