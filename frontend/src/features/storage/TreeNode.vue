<template>
  <div>
    <div
      class="flex cursor-pointer items-center gap-1 rounded-md px-2 py-1.5 text-xs transition"
      :style="{ paddingLeft: depth * 16 + 8 + 'px' }"
      :class="isSelected ? 'bg-[var(--gov-primary-soft)] text-[var(--gov-primary)] font-medium' : 'text-[var(--gov-text)] hover:bg-slate-100'"
      @click="toggle"
    >
      <!-- Expand/Collapse icon for folders -->
      <svg
        v-if="node.type === 'folder'"
        class="h-3.5 w-3.5 shrink-0 transition-transform"
        :class="expanded ? 'rotate-90' : ''"
        fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"
      >
        <path d="M9 5l7 7-7 7" />
      </svg>
      <span v-else class="inline-block w-3.5" />

      <!-- Folder / File icon -->
      <svg v-if="node.type === 'folder'" class="h-4 w-4 shrink-0 text-amber-500" fill="currentColor" viewBox="0 0 24 24">
        <path d="M2 6a2 2 0 012-2h5l2 2h9a2 2 0 012 2v10a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
      </svg>
      <svg v-else class="h-4 w-4 shrink-0 text-blue-400" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24">
        <path d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>

      <span class="truncate">{{ node.name }}</span>
      <span class="ml-auto shrink-0 rounded-full bg-slate-100 px-1.5 py-0.5 text-[10px] text-[var(--gov-text-muted)]">{{ node.record_count }}</span>
    </div>

    <!-- Children (expanded) -->
    <div v-if="expanded && node.children && node.children.length">
      <TreeNode
        v-for="child in node.children"
        :key="child.path"
        :node="child"
        :selected-path="selectedPath"
        :depth="depth + 1"
        @select="(n) => $emit('select', n)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  node: { type: Object, required: true },
  selectedPath: { type: String, default: '' },
  depth: { type: Number, default: 0 },
})

const emit = defineEmits(['select'])

const expanded = ref(props.depth < 2)

const isSelected = computed(() => props.selectedPath === props.node.path)

function toggle() {
  if (props.node.type === 'folder' && props.node.children?.length) {
    expanded.value = !expanded.value
  }
  emit('select', props.node)
}
</script>
