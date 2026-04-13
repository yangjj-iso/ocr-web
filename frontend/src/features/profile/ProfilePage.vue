<template>
  <div class="min-h-screen bg-[var(--gov-bg)] p-6">
    <div class="mx-auto max-w-2xl space-y-5">
      <div class="gov-panel px-6 py-5">
        <div class="flex items-center gap-4">
          <div class="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--gov-primary)] text-xl font-bold text-white">
            {{ avatarChar }}
          </div>
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2">
              <p class="text-base font-semibold text-[var(--gov-text)]">{{ authState.auth.value?.username }}</p>
              <span :class="roleBadgeClass" class="rounded px-1.5 py-0.5 text-[10px] font-medium">{{ roleLabel }}</span>
            </div>
            <p class="mt-0.5 text-xs text-[var(--gov-text-muted)]">
              显示名：{{ authState.auth.value?.display_name || '未设置' }}
            </p>
          </div>
        </div>
      </div>

      <div
        v-if="!authState.isAuthEnabled.value"
        class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-700"
      >
        当前运行在开发直通模式，资料页展示的是默认开发账号；界面可以预览角色布局，但无法完成真实退出登录。
      </div>
      <div
        v-else-if="!canViewOperatorSelfService"
        class="rounded-lg border border-slate-200 bg-white px-4 py-3 text-xs text-[var(--gov-text-muted)]"
      >
        当前角色以检索和查看为主，不显示签录配额和处理批次。
      </div>

      <div class="gov-panel px-6 py-5">
        <h3 class="mb-4 text-sm font-semibold text-[var(--gov-text)]">基本信息</h3>
        <div class="space-y-3 text-sm">
          <div class="flex items-center justify-between border-b border-[var(--gov-border)] pb-3">
            <span class="text-[var(--gov-text-muted)]">用户名</span>
            <span class="font-mono text-[var(--gov-text)]">{{ authState.auth.value?.username }}</span>
          </div>
          <div class="flex items-center justify-between border-b border-[var(--gov-border)] pb-3">
            <span class="text-[var(--gov-text-muted)]">角色</span>
            <span :class="roleBadgeClass" class="rounded px-2 py-0.5 text-xs font-medium">{{ roleLabel }}</span>
          </div>
          <div class="flex items-center justify-between border-b border-[var(--gov-border)] pb-3">
            <span class="text-[var(--gov-text-muted)]">账号状态</span>
            <span :class="statusClass" class="rounded px-2 py-0.5 text-xs font-medium">{{ statusLabel }}</span>
          </div>
          <div class="flex items-center justify-between border-b border-[var(--gov-border)] pb-3">
            <span class="text-[var(--gov-text-muted)]">登录模式</span>
            <span :class="authModeClass" class="rounded px-2 py-0.5 text-xs font-medium">{{ authModeLabel }}</span>
          </div>
          <div class="flex items-center justify-between">
            <span class="text-[var(--gov-text-muted)]">显示名</span>
            <div v-if="editingName" class="flex items-center gap-2">
              <input
                v-model="nameValue"
                class="gov-input w-44 text-xs"
                placeholder="输入显示名"
                maxlength="60"
                @keydown.enter="saveName"
                @keydown.esc="editingName = false"
              />
              <button class="gov-btn py-1 text-xs" :disabled="nameSaving" @click="saveName">
                {{ nameSaving ? '保存中...' : '保存' }}
              </button>
              <button class="gov-btn-secondary py-1 text-xs" @click="editingName = false">取消</button>
            </div>
            <div v-else class="flex items-center gap-2">
              <span class="text-[var(--gov-text)]">{{ authState.auth.value?.display_name || '未设置' }}</span>
              <button v-if="!isEnvAdmin" class="text-xs text-[var(--gov-primary)] hover:underline" @click="startEditName">修改</button>
            </div>
          </div>
          <p v-if="nameMsg" class="text-xs" :class="nameError ? 'text-red-500' : 'text-[var(--gov-success)]'">{{ nameMsg }}</p>
        </div>
      </div>

      <div v-if="canViewOperatorSelfService && myQuota" class="gov-panel px-6 py-5">
        <h3 class="mb-4 text-sm font-semibold text-[var(--gov-text)]">配额使用</h3>
        <div class="space-y-3">
          <div class="flex items-center justify-between text-sm">
            <span class="text-[var(--gov-text-muted)]">累计已用 / 总配额</span>
            <span class="font-medium text-[var(--gov-text)]">{{ myQuota.quota_used }} / {{ myQuota.quota_total }} 份</span>
          </div>
          <div class="h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              class="h-full rounded-full transition-all"
              :class="quotaPercent >= 90 ? 'bg-red-400' : quotaPercent >= 70 ? 'bg-amber-400' : 'bg-emerald-500'"
              :style="{ width: `${quotaPercent}%` }"
            />
          </div>
          <div class="grid grid-cols-3 gap-2 text-xs">
            <div class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2 text-center">
              <p class="text-[var(--gov-text-muted)]">已使用</p>
              <p class="mt-0.5 font-semibold text-[var(--gov-text)]">{{ myQuota.quota_used }}</p>
            </div>
            <div class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2 text-center">
              <p class="text-[var(--gov-text-muted)]">剩余</p>
              <p class="mt-0.5 font-semibold text-emerald-600">{{ myQuota.quota_remaining }}</p>
            </div>
            <div class="rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2 text-center">
              <p class="text-[var(--gov-text-muted)]">单次上限</p>
              <p class="mt-0.5 font-semibold text-[var(--gov-text)]">{{ myQuota.quota_per_import }}</p>
            </div>
          </div>
        </div>
      </div>

      <div v-if="canViewOperatorSelfService && assignments.length" class="gov-panel px-6 py-5">
        <div class="mb-3 flex items-center justify-between">
          <h3 class="text-sm font-semibold text-[var(--gov-text)]">近期任务（{{ assignments.length }}）</h3>
          <router-link :to="workbenchRoute" class="text-xs text-[var(--gov-primary)] hover:underline">{{ workbenchLabel }}</router-link>
        </div>
        <div class="space-y-2">
          <div
            v-for="task in assignments.slice(0, 5)"
            :key="task.id"
            class="flex items-center justify-between rounded-lg border border-[var(--gov-border)] bg-[var(--gov-surface-muted)] px-3 py-2 text-xs"
          >
            <span class="font-mono text-[var(--gov-primary)]">{{ task.batch_id }}</span>
            <div class="flex items-center gap-2">
              <span class="text-[var(--gov-text-muted)]">{{ task.file_count }} 份</span>
              <span :class="assignStatusClass(task.status)" class="rounded-full px-2 py-0.5 font-medium">{{ assignStatusLabel(task.status) }}</span>
            </div>
          </div>
        </div>
      </div>

      <div class="gov-panel px-6 py-5">
        <h3 class="mb-4 text-sm font-semibold text-[var(--gov-text)]">修改密码</h3>
        <div v-if="!authState.isAuthEnabled.value" class="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-600">
          当前运行在认证关闭模式，无需密码。
        </div>
        <div v-else-if="isEnvAdmin" class="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-600">
          系统管理员默认账号的密码通过环境变量 `AUTH_PASSWORD` 配置，无法在这里修改。
        </div>
        <form v-else class="space-y-3" @submit.prevent="submitPassword">
          <div>
            <label class="mb-1 block text-xs text-[var(--gov-text-muted)]">当前密码</label>
            <input
              v-model="pwd.current"
              type="password"
              class="gov-input w-full"
              placeholder="请输入当前密码"
              autocomplete="current-password"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs text-[var(--gov-text-muted)]">新密码（至少 6 位）</label>
            <input
              v-model="pwd.next"
              type="password"
              class="gov-input w-full"
              placeholder="请输入新密码"
              autocomplete="new-password"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs text-[var(--gov-text-muted)]">确认新密码</label>
            <input
              v-model="pwd.confirm"
              type="password"
              class="gov-input w-full"
              placeholder="再次输入新密码"
              autocomplete="new-password"
            />
          </div>
          <p v-if="pwdMsg" class="text-xs" :class="pwdError ? 'text-red-500' : 'text-[var(--gov-success)]'">{{ pwdMsg }}</p>
          <button
            type="submit"
            class="gov-btn w-full py-2 text-sm"
            :disabled="pwdSaving || !pwd.current || !pwd.next || !pwd.confirm"
          >
            {{ pwdSaving ? '修改中...' : '确认修改密码' }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

import { changePassword, updateDisplayName } from '@/api/auth.js'
import { getMyAssignments, getMyQuota } from '@/api/admin.js'
import { useAuthState } from '@/composables/useAuthState.js'

const authState = useAuthState()
const authProfile = authState.authProfile

const effectiveRole = computed(() => authProfile.value.role)
const avatarChar = computed(() => {
  const name = authState.auth.value?.display_name || authState.auth.value?.username || '?'
  return name.charAt(0).toUpperCase()
})

const roleLabel = computed(() => authProfile.value.roleLabel)
const roleBadgeClass = computed(() => {
  if (authProfile.value.isSysAdmin) return 'bg-indigo-100 text-indigo-700'
  if (authProfile.value.isTenantAdmin) return 'bg-violet-100 text-violet-700'
  if (authProfile.value.primaryWorkRole === 'operator') return 'bg-emerald-50 text-emerald-700'
  if (authProfile.value.primaryWorkRole === 'searcher') return 'bg-amber-50 text-amber-700'
  return 'bg-slate-100 text-slate-500'
})
const authModeLabel = computed(() => authState.isAuthEnabled.value ? '认证启用' : '开发直通')
const authModeClass = computed(() => (
  authState.isAuthEnabled.value
    ? 'bg-emerald-50 text-emerald-700'
    : 'bg-amber-50 text-amber-700'
))

const isEnvAdmin = computed(() => {
  const auth = authState.auth.value
  return auth?.is_admin && auth?.default_username && auth?.username === auth?.default_username
})

const statusClass = computed(() => ({
  active: 'bg-green-50 text-green-700',
  pending: 'bg-yellow-50 text-yellow-700',
  rejected: 'bg-red-50 text-red-600',
}[authState.auth.value?.user_status] || 'bg-slate-50 text-slate-500'))

const statusLabel = computed(() => ({
  active: '正常',
  pending: '待审核',
  rejected: '已拒绝',
}[authState.auth.value?.user_status] || authState.auth.value?.user_status || '未知'))

const canViewOperatorSelfService = computed(() => authProfile.value.hasOperator)
const workbenchRoute = computed(() => '/')
const workbenchLabel = computed(() => '前往工作台')

const editingName = ref(false)
const nameValue = ref('')
const nameSaving = ref(false)
const nameMsg = ref('')
const nameError = ref(false)

function startEditName() {
  nameValue.value = authState.auth.value?.display_name || ''
  editingName.value = true
  nameMsg.value = ''
}

async function saveName() {
  nameSaving.value = true
  nameMsg.value = ''
  try {
    const trimmed = nameValue.value.trim()
    await updateDisplayName(trimmed)
    authState.auth.value = { ...authState.auth.value, display_name: trimmed || null }
    editingName.value = false
    nameError.value = false
    nameMsg.value = '显示名已更新。'
  } catch (error) {
    nameError.value = true
    nameMsg.value = error?.response?.data?.message || '更新失败'
  } finally {
    nameSaving.value = false
  }
}

const myQuota = ref(null)
const quotaPercent = computed(() => {
  if (!myQuota.value) return 0
  return Math.min(100, Math.round((myQuota.value.quota_used / (myQuota.value.quota_total || 1)) * 100))
})

const assignments = ref([])

function assignStatusClass(status) {
  return {
    pending: 'bg-yellow-50 text-yellow-700',
    processing: 'bg-blue-50 text-blue-700',
    done: 'bg-green-50 text-green-700',
    failed: 'bg-red-50 text-red-600',
    cancelled: 'bg-slate-100 text-slate-500',
  }[status] || 'bg-slate-100 text-slate-500'
}

function assignStatusLabel(status) {
  return {
    pending: '待处理',
    processing: '处理中',
    done: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }[status] || status
}

const pwd = reactive({ current: '', next: '', confirm: '' })
const pwdSaving = ref(false)
const pwdMsg = ref('')
const pwdError = ref(false)

async function submitPassword() {
  pwdMsg.value = ''
  if (pwd.next !== pwd.confirm) {
    pwdError.value = true
    pwdMsg.value = '两次输入的新密码不一致。'
    return
  }
  if (pwd.next.length < 6) {
    pwdError.value = true
    pwdMsg.value = '新密码至少 6 位。'
    return
  }
  pwdSaving.value = true
  try {
    await changePassword(pwd.current, pwd.next)
    pwdError.value = false
    pwdMsg.value = '密码已修改，下次登录请使用新密码。'
    pwd.current = ''
    pwd.next = ''
    pwd.confirm = ''
  } catch (error) {
    pwdError.value = true
    pwdMsg.value = error?.response?.data?.detail || error?.response?.data?.message || '修改失败，请检查当前密码。'
  } finally {
    pwdSaving.value = false
  }
}

onMounted(async () => {
  if (!authState.isAuthenticated.value) return
  if (!canViewOperatorSelfService.value) return

  try {
    const { data } = await getMyQuota()
    if (data?.quota_total < 9999) myQuota.value = data
  } catch {
    myQuota.value = null
  }

  try {
    const { data } = await getMyAssignments()
    assignments.value = data?.items || []
  } catch {
    assignments.value = []
  }
})
</script>
