<template>
  <div class="overflow-hidden rounded-lg border border-[var(--gov-border)] bg-white">
    <!-- Filter bar slot -->
    <div v-if="$slots.filters" class="border-b border-[var(--gov-border)] px-4 py-2.5">
      <slot name="filters" />
    </div>

    <!-- Table -->
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-[var(--gov-border)] bg-slate-50/60">
            <th
              v-for="col in columns"
              :key="col.key"
              class="px-4 py-2.5 text-left text-[11px] font-semibold text-[var(--gov-text-muted)]"
              :style="col.width ? { width: col.width } : {}"
            >
              {{ col.label }}
            </th>
            <th v-if="$slots.actions" class="px-4 py-2.5 text-right text-[11px] font-semibold text-[var(--gov-text-muted)]">
              操作
            </th>
          </tr>
        </thead>
        <tbody class="divide-y divide-[var(--gov-border)]">
          <tr v-if="loading">
            <td :colspan="columns.length + ($slots.actions ? 1 : 0)" class="py-16 text-center">
              <div class="flex items-center justify-center gap-2 text-[var(--gov-text-muted)]">
                <svg class="h-5 w-5 animate-spin" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                  <path d="M4 12a8 8 0 018-8v4l3-3-3-3v4a8 8 0 100 16 8 8 0 008-8h-4" />
                </svg>
                加载中…
              </div>
            </td>
          </tr>
          <tr v-else-if="!rows.length">
            <td :colspan="columns.length + ($slots.actions ? 1 : 0)" class="py-16 text-center text-sm text-[var(--gov-text-muted)]">
              {{ emptyText }}
            </td>
          </tr>
          <tr
            v-else
            v-for="(row, idx) in rows"
            :key="rowKey ? row[rowKey] : idx"
            class="transition-colors hover:bg-slate-50/70"
            :class="clickable ? 'cursor-pointer' : ''"
            @click="clickable ? $emit('row-click', row) : undefined"
          >
            <td
              v-for="col in columns"
              :key="col.key"
              class="px-4 py-3 text-[var(--gov-text)]"
              :class="col.mono ? 'font-mono text-xs' : ''"
            >
              <slot :name="`cell-${col.key}`" :row="row" :value="getVal(row, col.key)">
                <span :class="col.muted ? 'text-[var(--gov-text-muted)]' : ''">{{ getVal(row, col.key) ?? '—' }}</span>
              </slot>
            </td>
            <td v-if="$slots.actions" class="px-4 py-3 text-right">
              <slot name="actions" :row="row" />
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="total > pageSize" class="flex items-center justify-between border-t border-[var(--gov-border)] px-5 py-3">
      <p class="text-xs text-[var(--gov-text-muted)]">
        共 <span class="font-semibold text-[var(--gov-text)]">{{ total }}</span> 条，第 {{ page }} / {{ totalPages }} 页
      </p>
      <div class="flex items-center gap-1">
        <button
          :disabled="page <= 1"
          class="flex h-7 w-7 items-center justify-center rounded-lg text-sm font-medium transition bg-slate-100 text-[var(--gov-text-muted)] hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed"
          @click="$emit('page-change', page - 1)"
        >‹</button>
        <template v-for="p in pageNums" :key="p">
          <span v-if="p === '…'" class="px-1 text-slate-400">…</span>
          <button
            v-else
            class="flex h-7 w-7 items-center justify-center rounded-lg text-sm font-medium transition"
            :class="p === page ? 'bg-[var(--gov-primary)] text-white' : 'bg-slate-100 text-[var(--gov-text-muted)] hover:bg-slate-200'"
            @click="$emit('page-change', p)"
          >{{ p }}</button>
        </template>
        <button
          :disabled="page >= totalPages"
          class="flex h-7 w-7 items-center justify-center rounded-lg text-sm font-medium transition bg-slate-100 text-[var(--gov-text-muted)] hover:bg-slate-200 disabled:opacity-40 disabled:cursor-not-allowed"
          @click="$emit('page-change', page + 1)"
        >›</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  columns: { type: Array, required: true }, // [{ key, label, width?, mono?, muted? }]
  rows: { type: Array, default: () => [] },
  rowKey: { type: String, default: 'id' },
  loading: { type: Boolean, default: false },
  emptyText: { type: String, default: '暂无数据' },
  total: { type: Number, default: 0 },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 20 },
  clickable: { type: Boolean, default: false },
})

defineEmits(['row-click', 'page-change'])

function getVal(row, key) {
  return key.split('.').reduce((obj, k) => obj?.[k], row)
}

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const pageNums = computed(() => {
  const total = totalPages.value
  const current = props.page
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const pages = []
  if (current <= 4) {
    for (let i = 1; i <= 5; i++) pages.push(i)
    pages.push('…')
    pages.push(total)
  } else if (current >= total - 3) {
    pages.push(1)
    pages.push('…')
    for (let i = total - 4; i <= total; i++) pages.push(i)
  } else {
    pages.push(1)
    pages.push('…')
    for (let i = current - 1; i <= current + 1; i++) pages.push(i)
    pages.push('…')
    pages.push(total)
  }
  return pages
})
</script>
