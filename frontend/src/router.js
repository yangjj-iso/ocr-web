import { createRouter, createWebHistory } from 'vue-router'
import { useAuthState } from './composables/useAuthState.js'

import LoginPage from './features/auth/LoginPage.vue'
import RegisterPage from './features/auth/RegisterPage.vue'
import ProfilePage from './features/profile/ProfilePage.vue'

import DashboardPage from './features/dashboard/DashboardPage.vue'
import BatchListPage from './features/batches/BatchListPage.vue'
import BatchDetailPage from './features/batches/BatchDetailPage.vue'
import TaskListPage from './features/tasks/TaskListPage.vue'
import ReviewWorkbenchPage from './features/review/ReviewWorkbenchPage.vue'
import StructureReviewPage from './features/review/StructureReviewPage.vue'
import CatalogReviewPage from './features/review/CatalogReviewPage.vue'
import ArchiveListPage from './features/archives/ArchiveListPage.vue'
import ArchiveDetailPage from './features/archives/ArchiveDetailPage.vue'
import ReleasePage from './features/release/ReleasePage.vue'
import ReleaseConsolePage from './features/release/ReleaseConsolePage.vue'
import ReworkListPage from './features/rework/ReworkListPage.vue'
import TenantManagePage from './features/config/TenantManagePage.vue'
import UserManagePage from './features/config/UserManagePage.vue'
import RulesConfigPage from './features/config/RulesConfigPage.vue'
import AuditPage from './features/audit/AuditPage.vue'
import DevDashboardPage from './features/dev/DevDashboardPage.vue'
import { hasAuthRole, roleBasedHome } from './utils/authz.js'

const routes = [
  { path: '/', redirect: '/dashboard' },

  { path: '/login', name: 'Login', component: LoginPage, meta: { public: true, authLayout: true } },
  { path: '/register', name: 'Register', component: RegisterPage, meta: { public: true, authLayout: true } },

  { path: '/dashboard', name: 'Dashboard', component: DashboardPage },
  { path: '/admin', redirect: '/config/users' },
  { path: '/batch-import', redirect: '/batches?create=1' },
  { path: '/storage', redirect: '/archives' },
  { path: '/search', redirect: '/archives' },

  { path: '/batches', name: 'BatchList', component: BatchListPage, meta: { roles: ['sys_admin', 'tenant_admin', 'operator'] } },
  { path: '/batches/new', name: 'BatchCreate', redirect: '/batches?create=1', meta: { roles: ['sys_admin', 'tenant_admin', 'operator'] } },
  { path: '/batches/:id', name: 'BatchDetail', component: BatchDetailPage, props: true, meta: { roles: ['sys_admin', 'tenant_admin', 'operator'] } },
  { path: '/batch-insights/:batchId', redirect: (to) => `/batches/${encodeURIComponent(String(to.params.batchId || ''))}` },

  { path: '/tasks', name: 'TaskList', component: TaskListPage, meta: { roles: ['sys_admin', 'tenant_admin', 'operator', 'searcher'] } },
  { path: '/review/:taskId', name: 'ReviewWorkbench', component: ReviewWorkbenchPage, props: true, meta: { reviewLayout: true, roles: ['sys_admin', 'tenant_admin', 'operator'] } },
  { path: '/review/structure/:taskId', name: 'StructureReview', component: StructureReviewPage, props: true, meta: { reviewLayout: true, roles: ['sys_admin', 'tenant_admin', 'operator'] } },
  { path: '/review/catalog/:taskId', name: 'CatalogReview', component: CatalogReviewPage, props: true, meta: { reviewLayout: true, roles: ['sys_admin', 'tenant_admin', 'operator'] } },
  { path: '/result/:taskId', redirect: (to) => ({ path: '/tasks', query: { task: String(to.params.taskId || '') } }) },

  { path: '/release', name: 'Release', component: ReleasePage, meta: { roles: ['sys_admin', 'tenant_admin', 'operator'] } },
  { path: '/release/console/:taskId', name: 'ReleaseConsole', component: ReleaseConsolePage, props: true, meta: { reviewLayout: true, roles: ['sys_admin', 'tenant_admin', 'operator'] } },
  { path: '/release/:taskId', name: 'ReleaseDetail', component: ReleasePage, props: true, meta: { roles: ['sys_admin', 'tenant_admin', 'operator'] } },

  { path: '/rework', name: 'ReworkList', component: ReworkListPage, meta: { roles: ['sys_admin', 'tenant_admin', 'operator', 'searcher'] } },
  { path: '/rework/my', name: 'ReworkMine', component: ReworkListPage, meta: { roles: ['sys_admin', 'tenant_admin', 'operator', 'searcher'] } },

  { path: '/archives', name: 'ArchiveList', component: ArchiveListPage, meta: { roles: ['sys_admin', 'tenant_admin', 'operator', 'searcher'] } },
  { path: '/archives/:id', name: 'ArchiveDetail', component: ArchiveDetailPage, props: true, meta: { roles: ['sys_admin', 'tenant_admin', 'operator', 'searcher'] } },

  { path: '/audit', name: 'Audit', component: AuditPage, meta: { roles: ['sys_admin', 'tenant_admin', 'operator', 'searcher'] } },

  { path: '/config/tenants', name: 'ConfigTenants', component: TenantManagePage, meta: { roles: ['sys_admin'] } },
  { path: '/config/users', name: 'ConfigUsers', component: UserManagePage, meta: { roles: ['sys_admin', 'tenant_admin'] } },
  { path: '/config/rules', name: 'ConfigRules', component: RulesConfigPage, meta: { roles: ['sys_admin', 'tenant_admin'] } },
  { path: '/config/quotas', redirect: '/config/tenants' },
  { path: '/config/audit', name: 'ConfigAudit', component: AuditPage, meta: { roles: ['sys_admin'] } },

  { path: '/profile', name: 'Profile', component: ProfilePage, meta: { roles: ['sys_admin', 'tenant_admin', 'operator', 'searcher'] } },

  { path: '/dev/dashboard', name: 'DevDashboard', component: DevDashboardPage, meta: { public: true, standalone: true } },

  { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const authState = useAuthState()

router.beforeEach(async (to) => {
  if (to.meta?.public && to.meta?.standalone) return true

  const status = await authState.refreshAuthStatus()

  if (!status.enabled) {
    if (to.name === 'Login' || to.name === 'Register') return '/dashboard'
    return true
  }

  if (!status.authenticated) {
    if (to.meta?.public) return true
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  if (to.name === 'Login' || to.name === 'Register') {
    return String(to.query?.redirect || roleBasedHome(status))
  }

  const expectedRoles = Array.isArray(to.meta?.roles) ? to.meta.roles : []
  if (expectedRoles.length > 0) {
    const passed = expectedRoles.some((r) => hasAuthRole(status, r))
    if (!passed) return roleBasedHome(status)
  }

  return true
})

export default router
