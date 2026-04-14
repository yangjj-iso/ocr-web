<template>
  <transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="translate-x-4 opacity-0"
    enter-to-class="translate-x-0 opacity-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="translate-x-0 opacity-100"
    leave-to-class="translate-x-4 opacity-0"
  >
    <div
      v-if="modelValue"
      class="fixed inset-y-0 right-0 z-40 flex w-full max-w-lg flex-col border-l border-[var(--gov-border)] bg-white shadow-lg"
    >
      <!-- Header -->
      <div class="flex items-center justify-between border-b border-[var(--gov-border)] px-5 py-3">
        <h3 class="text-sm font-semibold text-[var(--gov-text)]">{{ title }}</h3>
        <button
          class="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition"
          @click="$emit('update:modelValue', false)"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <!-- Content -->
      <div class="flex-1 overflow-y-auto p-4">
        <slot />
      </div>

      <!-- Footer actions -->
      <div v-if="$slots.footer" class="border-t border-[var(--gov-border)] px-5 py-3">
        <slot name="footer" />
      </div>
    </div>
  </transition>

  <!-- Backdrop -->
  <transition
    enter-active-class="transition duration-200 ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition duration-150 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="modelValue"
      class="fixed inset-0 z-30 bg-black/20 backdrop-blur-[2px]"
      @click="$emit('update:modelValue', false)"
    />
  </transition>
</template>

<script setup>
defineProps({
  modelValue: { type: Boolean, required: true },
  title: { type: String, default: '详情' },
})
defineEmits(['update:modelValue'])
</script>
