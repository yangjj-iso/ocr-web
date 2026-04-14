<template>
  <!-- Auth/standalone layout: no shell -->
  <slot v-if="isAuthLayout" />

  <!-- Review workbench: slim top bar + full content -->
  <div v-else-if="isReviewLayout" class="flex min-h-screen flex-col bg-[var(--gov-surface-muted)]">
    <header class="gov-header flex h-12 items-center gap-4 px-4">
      <button
        class="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-900"
        @click="$router.back()"
      >
        <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
        </svg>
        返回
      </button>
      <div class="flex h-6 w-6 items-center justify-center rounded bg-blue-600">
        <svg class="h-3.5 w-3.5 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
        </svg>
      </div>
      <span class="text-sm font-semibold text-slate-800">审核台</span>
      <div class="flex-1" />
      <slot name="review-toolbar" />
      <UserMenu />
    </header>
    <div class="flex-1 overflow-hidden">
      <slot />
    </div>
  </div>

  <!-- Normal layout: top navbar + left sidebar + content -->
  <div v-else class="flex min-h-screen flex-col bg-[var(--gov-bg)]">
    <!-- Top navbar -->
    <header class="gov-header sticky top-0 z-30 h-12">
      <div class="flex h-full items-center gap-3 px-4">
        <!-- Logo + System name -->
        <router-link to="/dashboard" class="flex items-center gap-2 flex-shrink-0">
          <div class="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--gov-primary)]">
            <svg class="h-3.5 w-3.5 text-white" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
            </svg>
          </div>
          <span class="text-sm font-semibold text-[var(--gov-text)]">启智档案</span>
        </router-link>

        <!-- Tenant badge (non-sys-admin) -->
        <div
          v-if="tenantName && !auth.is_admin"
          class="hidden items-center gap-1.5 rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs text-blue-700 sm:flex"
        >
          <svg class="h-3 w-3" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21" />
          </svg>
          {{ tenantName }}
        </div>

        <div class="flex-1" />

        <!-- Notifications + todos -->
        <button
          v-if="todoCount > 0"
          class="relative flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-slate-500 hover:bg-slate-100"
          @click="$router.push(todoRoute)"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0" />
          </svg>
          <span class="rounded-full bg-red-500 px-1.5 py-0.5 text-[10px] font-bold text-white leading-none">{{ todoCount }}</span>
          <span>待处理</span>
        </button>

        <UserMenu />
      </div>
    </header>

    <!-- Body: sidebar + content -->
    <div class="flex flex-1 overflow-hidden">
      <!-- Left sidebar -->
      <aside
        class="flex w-52 flex-shrink-0 flex-col border-r border-[var(--gov-border)] bg-white"
        :class="sidebarOpen ? 'translate-x-0' : '-translate-x-full fixed z-20 h-full shadow-xl md:translate-x-0 md:relative md:shadow-none'"
      >
        <!-- Menu items -->
        <nav class="flex-1 overflow-y-auto px-2 py-2 space-y-0.5">
          <template v-for="group in menuGroups" :key="group.label">
            <p v-if="group.label" class="px-3 pt-4 pb-1 text-[10px] font-medium tracking-wider text-slate-400/80 first:pt-2">
              {{ group.label }}
            </p>
            <router-link
              v-for="item in group.items"
              :key="item.to"
              :to="item.to"
              class="flex items-center gap-2.5 rounded-md px-3 py-1.5 text-[13px] font-medium transition-all"
              :class="isActive(item.to)
                ? 'bg-[var(--gov-primary)]/[0.06] text-[var(--gov-primary)] border-l-2 border-[var(--gov-primary)] -ml-px'
                : 'text-slate-600 hover:bg-slate-50 hover:text-slate-800'"
            >
              <component :is="item.icon" class="h-4 w-4 flex-shrink-0" />
              <span class="flex-1 truncate">{{ item.label }}</span>
              <span
                v-if="item.badge"
                class="flex-shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold leading-none"
                :class="isActive(item.to) ? 'bg-[var(--gov-primary)]/20 text-[var(--gov-primary)]' : 'bg-slate-100 text-slate-500'"
              >{{ item.badge }}</span>
            </router-link>
          </template>
        </nav>

      </aside>

      <!-- Main content -->
      <main class="flex-1 min-w-0 overflow-y-auto">
        <slot />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthState } from '@/composables/useAuthState.js'
import { getMyAssignedTasks, listReviewTasks, listReworkTasks } from '@/api/archive.js'

const UserMenu = defineAsyncComponent(() => import('./UserMenu.vue'))

const route = useRoute()
const authState = useAuthState()
const auth = authState.auth
const authProfile = authState.authProfile
const sidebarOpen = ref(false)

const isAuthLayout = computed(() => route.meta?.authLayout)
const isReviewLayout = computed(() => route.meta?.reviewLayout)

const displayName = computed(() => auth.value?.display_name || auth.value?.username || '用户')
const tenantName = computed(() => auth.value?.tenant_name || null)

// Role helpers
const isSysAdmin = computed(() => authProfile.value.isSysAdmin)
const isTenantAdmin = computed(() => authProfile.value.isTenantAdmin)
const isOperator = computed(() => !isSysAdmin.value && !isTenantAdmin.value && authProfile.value.hasOperator)
const isSearcher = computed(() => !isSysAdmin.value && !isTenantAdmin.value && !authProfile.value.hasOperator && authProfile.value.hasSearcher)

const roleLabel = computed(() => authProfile.value.roleLabel)

const roleInitial = computed(() => roleLabel.value[0] || 'U')

const roleBadgeColor = computed(() => {
  if (isSysAdmin.value) return 'bg-purple-600'
  if (isTenantAdmin.value) return 'bg-blue-600'
  if (isOperator.value) return 'bg-emerald-600'
  if (isSearcher.value) return 'bg-amber-600'
  return 'bg-slate-500'
})

const todoCount = ref(0)
const todoRoute = computed(() => {
  if (isSearcher.value) return '/rework/my'
  return '/tasks'
})

const TODO_REFRESH_MS = 30000
let todoRefreshTimer = null

function extractItems(payload) {
  if (Array.isArray(payload)) return payload
  if (Array.isArray(payload?.items)) return payload.items
  if (Array.isArray(payload?.tasks)) return payload.tasks
  return []
}

function extractTotal(payload) {
  if (Array.isArray(payload)) return payload.length
  if (typeof payload?.total === 'number') return payload.total
  return extractItems(payload).length
}

async function refreshTodoCount() {
  if (!auth.value?.authenticated) {
    todoCount.value = 0
    return
  }

  try {
    if (isSysAdmin.value || isTenantAdmin.value) {
      const { data } = await listReviewTasks({
        status: 'human_review',
        page: 1,
        page_size: 1,
      })
      todoCount.value = Math.max(0, extractTotal(data))
      return
    }

    if (isSearcher.value) {
      const [{ data: pendingData }, { data: processingData }] = await Promise.all([
        listReworkTasks({ page: 1, page_size: 1, mine: true, status: 'pending' }),
        listReworkTasks({ page: 1, page_size: 1, mine: true, status: 'processing' }),
      ])
      todoCount.value = Math.max(0, extractTotal(pendingData)) + Math.max(0, extractTotal(processingData))
      return
    }

    const { data } = await getMyAssignedTasks({
      status: 'human_review',
      page: 1,
      page_size: 1,
    })
    todoCount.value = Math.max(0, extractTotal(data))
  } catch {
    todoCount.value = 0
  }
}

function startTodoRefresh() {
  stopTodoRefresh()
  if (!auth.value?.authenticated) return
  todoRefreshTimer = window.setInterval(() => {
    if (!document.hidden) {
      refreshTodoCount()
    }
  }, TODO_REFRESH_MS)
}

function stopTodoRefresh() {
  if (todoRefreshTimer) {
    window.clearInterval(todoRefreshTimer)
    todoRefreshTimer = null
  }
}

onMounted(() => {
  refreshTodoCount()
  startTodoRefresh()
})

watch(
  () => [auth.value?.authenticated, authProfile.value.role, route.fullPath],
  () => {
    refreshTodoCount()
    startTodoRefresh()
  }
)

onBeforeUnmount(() => {
  stopTodoRefresh()
})

// Icon components (inline SVG as object)
function makeIcon(svgPath, viewBox = '0 0 24 24') {
  return {
    template: `<svg class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" viewBox="${viewBox}">${svgPath}</svg>`,
  }
}

const icons = {
  home: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25"/>'),
  layers: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M6.429 9.75L2.25 12l4.179 2.25m0-4.5l5.571 3 5.571-3m-11.142 0L2.25 7.5 12 2.25l9.75 5.25-4.179 2.25m0 0L21.75 12l-4.179 2.25m0 0l4.179 2.25L12 21.75 2.25 16.5l4.179-2.25m11.142 0l-5.571 3-5.571-3"/>'),
  tasks: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M8.25 6.75h12M8.25 12h12m-12 5.25h12M3.75 6.75h.007v.008H3.75V6.75zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zM3.75 12h.007v.008H3.75V12zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm-.375 5.25h.007v.008H3.75v-.008zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z"/>'),
  review: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25zM6.75 12h.008v.008H6.75V12zm0 3h.008v.008H6.75V15zm0 3h.008v.008H6.75V18z"/>'),
  search: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"/>'),
  release: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>'),
  rework: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99"/>'),
  users: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>'),
  settings: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281z"/><path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>'),
  building: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M3.75 21h16.5M4.5 3h15M5.25 3v18m13.5-18v18M9 6.75h1.5m-1.5 3h1.5m-1.5 3h1.5m3-6H15m-1.5 3H15m-1.5 3H15M9 21v-3.375c0-.621.504-1.125 1.125-1.125h3.75c.621 0 1.125.504 1.125 1.125V21"/>'),
  history: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/>'),
  flag: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M3 3v1.5M3 21v-6m0 0l2.77-.693a9 9 0 016.208.682l.108.054a9 9 0 006.086.71l3.114-.732a48.524 48.524 0 01-.005-10.499l-3.11.732a9 9 0 01-6.085-.711l-.108-.054a9 9 0 00-6.208-.682L3 4.5M3 15V4.5"/>'),
  assign: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z"/>'),
  upload: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>'),
  gauge: makeIcon('<path stroke-linecap="round" stroke-linejoin="round" d="M12 3v2.25m6.364.386l-1.591 1.591M21 12h-2.25m-.386 6.364l-1.591-1.591M12 18.75V21m-4.773-4.227l-1.591 1.591M5.25 12H3m4.227-4.773L5.636 5.636M15.75 12a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z"/>'),
}

// Menu definitions per role
const menuGroups = computed(() => {
  if (isSysAdmin.value) {
    return [
      {
        label: '',
        items: [
          { label: '平台概览', to: '/dashboard', icon: icons.home },
          { label: '批次管理', to: '/batches', icon: icons.layers },
          { label: '任务中心', to: '/tasks', icon: icons.tasks },
          { label: '卷宗检索', to: '/archives', icon: icons.search },
        ],
      },
      {
        label: '审核流转',
        items: [
          { label: '入库确认', to: '/release', icon: icons.release },
          { label: '返工跟踪', to: '/rework', icon: icons.rework },
          { label: '审阅记录', to: '/audit', icon: icons.history },
        ],
      },
      {
        label: '系统配置',
        items: [
          { label: '租户管理', to: '/config/tenants', icon: icons.building },
          { label: '用户与权限', to: '/config/users', icon: icons.users },
          { label: '规则配置', to: '/config/rules', icon: icons.settings },
          { label: '系统审计', to: '/config/audit', icon: icons.history },
        ],
      },
    ]
  }

  if (isTenantAdmin.value) {
    return [
      {
        label: '',
        items: [
          { label: '工作台', to: '/dashboard', icon: icons.home },
        ],
      },
      {
        label: '生产链',
        items: [
          { label: '批次管理', to: '/batches', icon: icons.layers },
          { label: '任务分配', to: '/tasks', icon: icons.assign },
          { label: '待最终确认', to: '/release', icon: icons.release },
          { label: '返工管理', to: '/rework', icon: icons.rework },
        ],
      },
      {
        label: '检索链',
        items: [
          { label: '卷宗检索', to: '/archives', icon: icons.search },
          { label: '审阅记录', to: '/audit', icon: icons.history },
        ],
      },
      {
        label: '配置',
        items: [
          { label: '用户与权限', to: '/config/users', icon: icons.users },
          { label: '规则配置', to: '/config/rules', icon: icons.settings },
        ],
      },
    ]
  }

  if (isOperator.value) {
    return [
      {
        label: '',
        items: [
          { label: '工作台', to: '/dashboard', icon: icons.home },
        ],
      },
      {
        label: '任务',
        items: [
          { label: '新建批次', to: '/batches?create=1', icon: icons.upload },
          { label: '我的批次', to: '/batches', icon: icons.layers },
          { label: '我的任务', to: '/tasks', icon: icons.tasks },
        ],
      },
      {
        label: '审核',
        items: [
          { label: '结构审核', to: '/tasks?type=boundary_review', icon: icons.layers },
          { label: '著录审核', to: '/tasks?type=metadata_review', icon: icons.review },
          { label: '放行控制', to: '/release', icon: icons.release },
        ],
      },
      {
        label: '记录',
        items: [
          { label: '审阅记录', to: '/audit', icon: icons.history },
        ],
      },
    ]
  }

  if (isSearcher.value) {
    return [
      {
        label: '',
        items: [
          { label: '工作台', to: '/dashboard', icon: icons.home },
          { label: '卷宗检索', to: '/archives', icon: icons.search },
        ],
      },
      {
        label: '问题跟踪',
        items: [
          { label: '我的问题提报', to: '/rework/my', icon: icons.flag },
          { label: '返工跟踪', to: '/rework', icon: icons.rework },
        ],
      },
      {
        label: '记录',
        items: [
          { label: '审阅记录', to: '/audit', icon: icons.history },
        ],
      },
    ]
  }

  // fallback: authenticated but no specific role → show basic operator menu
  return [
    {
      label: '',
      items: [
        { label: '工作台', to: '/dashboard', icon: icons.home },
      ],
    },
    {
      label: '任务',
      items: [
        { label: '新建批次', to: '/batches?create=1', icon: icons.upload },
        { label: '我的批次', to: '/batches', icon: icons.layers },
        { label: '我的任务', to: '/tasks', icon: icons.tasks },
      ],
    },
    {
      label: '检索',
      items: [
        { label: '卷宗检索', to: '/archives', icon: icons.search },
      ],
    },
  ]
})

function isActive(to) {
  const str = String(to || '')
  const qIdx = str.indexOf('?')
  const pathPart = qIdx >= 0 ? str.slice(0, qIdx) : str
  const queryPart = qIdx >= 0 ? str.slice(qIdx + 1) : ''
  const normalized = pathPart.split('#')[0]

  if (normalized === '/dashboard') return route.path === '/dashboard'

  const pathMatch = route.path === normalized || route.path.startsWith(`${normalized}/`)
  if (!pathMatch) return false

  if (queryPart) {
    // 链接带 query → 当前路由必须包含这些 query 参数
    const toParams = Object.fromEntries(new URLSearchParams(queryPart))
    return Object.entries(toParams).every(([k, v]) => route.query[k] === v)
  } else {
    // 链接不带 query → 仅当当前路由也没有区分性参数时才高亮
    return !route.query.type && !route.query.create
  }
}
</script>
