<template>
  <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold leading-none" :class="cls">
    <span class="h-1.5 w-1.5 rounded-full flex-shrink-0" :class="dotCls" />
    {{ label }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: '' },
  type: { type: String, default: 'task' }, // task | doc | batch | review
})

const MAP = {
  // Task statuses
  pending:         { label: '待处理',   bg: 'bg-slate-100  text-slate-600',  dot: 'bg-slate-400' },
  queued:          { label: '排队中',   bg: 'bg-slate-100  text-slate-600',  dot: 'bg-slate-400' },
  processing:      { label: '处理中',   bg: 'bg-blue-50    text-blue-700',   dot: 'bg-blue-500' },
  running:         { label: '运行中',   bg: 'bg-blue-50    text-blue-700',   dot: 'bg-blue-500 animate-pulse' },
  human_review:    { label: '人工审核', bg: 'bg-amber-50   text-amber-700',  dot: 'bg-amber-500 animate-pulse' },
  done:            { label: '已完成',   bg: 'bg-emerald-50 text-emerald-700',dot: 'bg-emerald-500' },
  completed:       { label: '已完成',   bg: 'bg-emerald-50 text-emerald-700',dot: 'bg-emerald-500' },
  failed:          { label: '失败',     bg: 'bg-red-50     text-red-700',    dot: 'bg-red-500' },
  cancelled:       { label: '已取消',   bg: 'bg-slate-100  text-slate-500',  dot: 'bg-slate-300' },
  // Doc/batch statuses
  draft:           { label: '草稿',     bg: 'bg-slate-100  text-slate-600',  dot: 'bg-slate-400' },
  review_required: { label: '待审核',   bg: 'bg-amber-50   text-amber-700',  dot: 'bg-amber-500 animate-pulse' },
  boundary_confirmed:{ label: '边界已确认', bg: 'bg-sky-50 text-sky-700',   dot: 'bg-sky-500' },
  metadata_confirmed:{ label: '著录已确认', bg: 'bg-indigo-50 text-indigo-700', dot: 'bg-indigo-500' },
  archived:        { label: '已入库',   bg: 'bg-emerald-50 text-emerald-700',dot: 'bg-emerald-500' },
  rework:          { label: '返工中',   bg: 'bg-orange-50  text-orange-700', dot: 'bg-orange-500 animate-pulse' },
  // Review task types
  boundary:        { label: '边界审核', bg: 'bg-sky-50     text-sky-700',    dot: 'bg-sky-500' },
  boundary_review: { label: '边界审核', bg: 'bg-sky-50     text-sky-700',    dot: 'bg-sky-500' },
  metadata:        { label: '著录审核', bg: 'bg-indigo-50  text-indigo-700', dot: 'bg-indigo-500' },
  metadata_review: { label: '著录审核', bg: 'bg-indigo-50  text-indigo-700', dot: 'bg-indigo-500' },
  ordering:        { label: '排序审核', bg: 'bg-violet-50  text-violet-700', dot: 'bg-violet-500' },
  order_review:    { label: '排序审核', bg: 'bg-violet-50  text-violet-700', dot: 'bg-violet-500' },
  final_release:   { label: '放行审核', bg: 'bg-emerald-50 text-emerald-700',dot: 'bg-emerald-500' },
}

const entry = computed(() => MAP[props.status?.toLowerCase?.()] || {
  label: props.status || '未知',
  bg: 'bg-slate-100 text-slate-500',
  dot: 'bg-slate-300',
})

const cls = computed(() => entry.value.bg)
const dotCls = computed(() => entry.value.dot)
const label = computed(() => entry.value.label)
</script>
