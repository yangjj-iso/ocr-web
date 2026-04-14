<template>
  <!-- Modal backdrop -->
  <transition
    enter-active-class="transition duration-150 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-100 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div v-if="modelValue" class="gov-modal-backdrop">
      <div class="gov-modal-panel w-full max-w-lg" @click.stop>
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-[var(--gov-border)] px-5 py-3">
          <h3 class="text-sm font-semibold text-[var(--gov-text)]">提报问题 / 申请返工</h3>
          <button
            class="rounded p-1 text-slate-400 hover:bg-slate-100"
            @click="$emit('update:modelValue', false)"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <!-- Form -->
        <div class="space-y-4 px-5 py-4">
          <div>
            <label class="mb-1 block text-xs font-semibold text-[var(--gov-text-muted)]">问题类型 <span class="text-red-500">*</span></label>
            <select
              v-model="form.issue_type"
              class="w-full rounded-lg border border-[var(--gov-border)] bg-white px-3 py-2 text-sm focus:border-[var(--gov-primary)] focus:outline-none"
            >
              <option value="">请选择问题类型</option>
              <option value="boundary_error">分件边界错误</option>
              <option value="metadata_error">著录字段错误</option>
              <option value="ordering_error">排序错误</option>
              <option value="missing_page">缺页/重复页</option>
              <option value="pdf_quality">PDF质量问题</option>
              <option value="other">其他</option>
            </select>
          </div>

          <div>
            <label class="mb-1 block text-xs font-semibold text-[var(--gov-text-muted)]">影响范围</label>
            <input
              v-model="form.affected_scope"
              type="text"
              placeholder="例如：件2-件5，或第12-15页"
              class="w-full rounded-lg border border-[var(--gov-border)] px-3 py-2 text-sm focus:border-[var(--gov-primary)] focus:outline-none"
            />
          </div>

          <div>
            <label class="mb-1 block text-xs font-semibold text-[var(--gov-text-muted)]">问题描述 <span class="text-red-500">*</span></label>
            <textarea
              v-model="form.description"
              rows="4"
              placeholder="详细描述发现的问题..."
              class="w-full resize-none rounded-lg border border-[var(--gov-border)] px-3 py-2 text-sm leading-relaxed focus:border-[var(--gov-primary)] focus:outline-none"
            />
          </div>

          <div>
            <label class="mb-1 block text-xs font-semibold text-[var(--gov-text-muted)]">紧急程度</label>
            <div class="flex gap-2">
              <label
                v-for="opt in priorities"
                :key="opt.value"
                class="flex flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-lg border py-2 text-xs font-medium transition"
                :class="form.priority === opt.value
                  ? opt.activeClass
                  : 'border-[var(--gov-border)] text-slate-500 hover:border-slate-300'"
              >
                <input type="radio" v-model="form.priority" :value="opt.value" class="sr-only" />
                <span class="h-1.5 w-1.5 rounded-full" :class="opt.dotClass" />
                {{ opt.label }}
              </label>
            </div>
          </div>
        </div>

        <!-- Footer -->
        <div class="flex items-center justify-end gap-3 border-t border-[var(--gov-border)] px-5 py-3">
          <button
            class="rounded-md px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 transition"
            @click="$emit('update:modelValue', false)"
          >取消</button>
          <button
            :disabled="!form.issue_type || !form.description || submitting"
            class="gov-btn text-sm disabled:cursor-not-allowed disabled:opacity-50 flex items-center gap-2"
            @click="submit"
          >
            <svg v-if="submitting" class="h-4 w-4 animate-spin" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" />
            </svg>
            提交返工申请
          </button>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  recordId: { type: String, default: null },
  recordVersion: { type: Number, default: null },
})

const emit = defineEmits(['update:modelValue', 'submitted'])

const submitting = ref(false)

const form = reactive({
  issue_type: '',
  affected_scope: '',
  description: '',
  priority: 'normal',
})

const priorities = [
  { value: 'low',    label: '低',    dotClass: 'bg-slate-400',   activeClass: 'border-slate-400 bg-slate-50 text-slate-700' },
  { value: 'normal', label: '正常',  dotClass: 'bg-blue-500',    activeClass: 'border-blue-400 bg-blue-50 text-blue-700' },
  { value: 'high',   label: '高',    dotClass: 'bg-amber-500',   activeClass: 'border-amber-400 bg-amber-50 text-amber-700' },
  { value: 'urgent', label: '紧急',  dotClass: 'bg-red-500',     activeClass: 'border-red-400 bg-red-50 text-red-700' },
]

watch(() => props.modelValue, (v) => {
  if (v) Object.assign(form, { issue_type: '', affected_scope: '', description: '', priority: 'normal' })
})

async function submit() {
  submitting.value = true
  try {
    emit('submitted', { ...form, record_id: props.recordId, record_version: props.recordVersion })
    emit('update:modelValue', false)
  } finally {
    submitting.value = false
  }
}
</script>
