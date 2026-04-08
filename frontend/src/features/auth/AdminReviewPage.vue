<template>
  <div class="mx-auto max-w-5xl px-6 py-6">
    <section class="gov-panel overflow-hidden">
      <div class="flex items-center justify-between border-b border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-5 py-4">
        <div>
          <p class="text-xs font-semibold tracking-[0.16em] text-[var(--gov-primary)]">管理员</p>
          <h2 class="mt-1 text-lg font-semibold text-[var(--gov-text)]">账号审核</h2>
          <p class="mt-1 text-xs gov-muted">审核注册申请，通过后即可登录系统。</p>
        </div>
        <button
          class="rounded-lg border border-[var(--gov-border)] bg-white px-3 py-1.5 text-xs text-[var(--gov-text)] hover:bg-slate-50"
          @click="reload"
        >
          刷新列表
        </button>
      </div>

      <div class="px-5 py-4">
        <p v-if="message" class="mb-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">{{ message }}</p>
        <p v-if="errorText" class="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">{{ errorText }}</p>

        <div v-if="loading" class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-5 text-center text-sm gov-muted">
          正在加载待审核账号...
        </div>
        <div v-else-if="!users.length" class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-5 text-center text-sm gov-muted">
          当前没有待审核账号。
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-left text-sm">
            <thead class="bg-[var(--gov-surface-muted)] text-[var(--gov-text-muted)]">
              <tr>
                <th class="px-3 py-2">账号</th>
                <th class="px-3 py-2">申请时间</th>
                <th class="px-3 py-2">状态</th>
                <th class="px-3 py-2 text-right">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in users" :key="item.id" class="border-t border-[var(--gov-border)]">
                <td class="px-3 py-2 text-[var(--gov-text)]">{{ item.username }}</td>
                <td class="px-3 py-2 gov-muted">{{ item.created_at ? formatTime(item.created_at) : '-' }}</td>
                <td class="px-3 py-2">
                  <span class="rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-700">待审核</span>
                </td>
                <td class="px-3 py-2 text-right">
                  <div class="inline-flex items-center gap-2">
                    <button
                      class="rounded bg-emerald-600 px-2.5 py-1 text-xs text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-emerald-300"
                      :disabled="submittingId === item.id"
                      @click="approve(item.id)"
                    >
                      通过
                    </button>
                    <button
                      class="rounded bg-red-600 px-2.5 py-1 text-xs text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-300"
                      :disabled="submittingId === item.id"
                      @click="reject(item.id)"
                    >
                      驳回
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import dayjs from 'dayjs'
import { computed, onMounted, ref } from 'vue'

import { useAuthState } from '@/composables/useAuthState.js'

const authState = useAuthState()
const submittingId = ref(null)
const message = ref('')

const users = computed(() => authState.pendingUsers.value || [])
const loading = computed(() => authState.pendingLoading.value)
const errorText = computed(() => authState.pendingError.value)

const formatTime = (value) => dayjs(value).format('YYYY-MM-DD HH:mm')

async function reload() {
  message.value = ''
  await authState.loadPendingUsers()
}

async function approve(userId) {
  submittingId.value = userId
  message.value = ''
  try {
    await authState.approvePendingUser(userId)
    message.value = '账号已通过审核。'
  } finally {
    submittingId.value = null
  }
}

async function reject(userId) {
  submittingId.value = userId
  message.value = ''
  try {
    await authState.rejectPendingUser(userId)
    message.value = '账号已驳回。'
  } finally {
    submittingId.value = null
  }
}

onMounted(reload)
</script>
