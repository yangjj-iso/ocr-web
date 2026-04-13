<template>
  <div class="rounded-lg border border-[var(--gov-border)] bg-white px-4 py-3.5">
    <div class="flex items-start justify-between">
      <div class="min-w-0 flex-1">
        <p class="text-[11px] font-medium text-[var(--gov-text-muted)]">{{ label }}</p>
        <p class="mt-1 text-2xl font-bold tracking-tight" :class="valueClass">
          {{ loading ? '—' : value }}
        </p>
        <p v-if="sub" class="mt-0.5 text-[11px] text-[var(--gov-text-muted)]">{{ sub }}</p>
      </div>
      <div
        v-if="icon"
        class="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md"
        :class="iconBgClass"
      >
        <component :is="icon" class="h-4 w-4" />
      </div>
    </div>
    <div v-if="trend !== undefined" class="mt-1.5">
      <span
        class="inline-flex items-center gap-0.5 text-[11px] font-medium"
        :class="trend >= 0 ? 'text-emerald-600' : 'text-red-600'"
      >
        <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" :d="trend >= 0 ? 'M4.5 19.5l15-15m0 0H8.25m11.25 0v11.25' : 'M4.5 4.5l15 15m0 0V8.25m0 11.25H8.25'" />
        </svg>
        {{ Math.abs(trend) }}%
      </span>
      <span class="ml-1 text-[10px] text-[var(--gov-text-muted)]">vs 昨日</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: 0 },
  sub: { type: String, default: '' },
  color: { type: String, default: 'blue' }, // blue | green | amber | purple | red | slate
  trend: { type: Number, default: undefined },
  loading: { type: Boolean, default: false },
  icon: { type: Object, default: null },
})

const colorMap = {
  blue:   { bg: 'bg-blue-500',   value: 'text-blue-700',   iconBg: 'bg-blue-50   text-blue-600' },
  green:  { bg: 'bg-emerald-500',value: 'text-emerald-700',iconBg: 'bg-emerald-50 text-emerald-600' },
  amber:  { bg: 'bg-amber-500',  value: 'text-amber-700',  iconBg: 'bg-amber-50  text-amber-600' },
  purple: { bg: 'bg-purple-500', value: 'text-purple-700', iconBg: 'bg-purple-50 text-purple-600' },
  red:    { bg: 'bg-red-500',    value: 'text-red-700',    iconBg: 'bg-red-50    text-red-600' },
  slate:  { bg: 'bg-slate-500',  value: 'text-slate-700',  iconBg: 'bg-slate-100 text-slate-600' },
}

const c = computed(() => colorMap[props.color] || colorMap.blue)
const bgClass = computed(() => c.value.bg)
const valueClass = computed(() => c.value.value)
const iconBgClass = computed(() => c.value.iconBg)
</script>
