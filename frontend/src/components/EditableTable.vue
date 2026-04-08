<template>
  <div class="space-y-3">
    <div v-if="editing" class="flex flex-wrap items-center gap-2 text-xs">
      <button class="rounded-md border border-gray-200 bg-white px-2 py-1 text-gray-600 hover:border-blue-200 hover:text-blue-600" @click="addRow">
        + 行
      </button>
      <button class="rounded-md border border-gray-200 bg-white px-2 py-1 text-gray-600 hover:border-blue-200 hover:text-blue-600" @click="addColumn">
        + 列
      </button>
      <button
        class="rounded-md border border-gray-200 bg-white px-2 py-1 text-gray-600 hover:border-red-200 hover:text-red-600"
        :disabled="rows.length <= 1"
        @click="removeRow(rows.length - 1)"
      >
        - 行
      </button>
      <button
        class="rounded-md border border-gray-200 bg-white px-2 py-1 text-gray-600 hover:border-red-200 hover:text-red-600"
        :disabled="columnCount <= 1"
        @click="removeColumn(columnCount - 1)"
      >
        - 列
      </button>
    </div>

    <div class="overflow-x-auto rounded-lg border border-gray-200">
      <table class="min-w-full border-collapse text-sm">
        <tbody>
          <tr v-for="(row, rowIndex) in rows" :key="`row-${rowIndex}`">
            <td
              v-for="(cell, columnIndex) in row"
              :key="`cell-${rowIndex}-${columnIndex}`"
              class="border border-gray-200 bg-white align-top"
            >
              <textarea
                v-if="editing"
                :value="cell"
                rows="2"
                class="min-h-[56px] w-full resize-y border-0 bg-transparent px-2 py-1.5 text-sm text-gray-700 focus:outline-none"
                @input="setCell(rowIndex, columnIndex, $event.target.value)"
              />
              <div v-else class="px-2 py-1.5 text-gray-700 whitespace-pre-wrap">
                {{ cell || '—' }}
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Array,
    default: () => [['']],
  },
  editing: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:modelValue'])

function normalizeRows(value) {
  const rows = Array.isArray(value) && value.length ? value : [['']]
  const normalized = rows.map((row) => (Array.isArray(row) && row.length ? row.map((cell) => String(cell ?? '')) : ['']))
  const width = Math.max(...normalized.map((row) => row.length), 1)
  return normalized.map((row) => [...row, ...Array(Math.max(width - row.length, 0)).fill('')])
}

const rows = ref(normalizeRows(props.modelValue))

watch(
  () => props.modelValue,
  (value) => {
    rows.value = normalizeRows(value)
  },
  { deep: true }
)

const columnCount = computed(() => Math.max(...rows.value.map((row) => row.length), 1))

function sync() {
  emit('update:modelValue', rows.value.map((row) => [...row]))
}

function setCell(rowIndex, columnIndex, value) {
  rows.value[rowIndex][columnIndex] = value
  sync()
}

function addRow() {
  rows.value.push(Array(columnCount.value).fill(''))
  sync()
}

function addColumn() {
  rows.value = rows.value.map((row) => [...row, ''])
  sync()
}

function removeRow(rowIndex) {
  if (rows.value.length <= 1) return
  rows.value.splice(rowIndex, 1)
  sync()
}

function removeColumn(columnIndex) {
  if (columnCount.value <= 1) return
  rows.value = rows.value.map((row) => row.filter((_, index) => index !== columnIndex))
  sync()
}
</script>
