import { createRouter, createWebHistory } from 'vue-router'
import { useAuthState } from './composables/useAuthState.js'

import { hasAuthRole, roleBasedHome } from './utils/authz.js'

const LoginPage = () => import('./features/auth/LoginPage.vue')
const RegisterPage = () => import('./features/auth/RegisterPage.vue')
const ProfilePage = () => import('./features/profile/ProfilePage.vue')

const DashboardPage = () => import('./features/dashboard/DashboardPage.vue')
const BatchListPage = () => import('./features/batches/BatchListPage.vue')
const BatchDetailPage = () => import('./features/batches/BatchDetailPage.vue')
const TaskListPage = () => import('./features/tasks/TaskListPage.vue')
const ReviewWorkbenchPage = () => import('./features/review/ReviewWorkbenchPage.vue')
const StructureReviewPage = () => import('./features/review/StructureReviewPage.vue')
const CatalogReviewPage = () => import('./features/review/CatalogReviewPage.vue')
const ArchiveListPage = () => import('./features/archives/ArchiveListPage.vue')
const ArchiveDetailPage = () => import('./features/archives/ArchiveDetailPage.vue')
const ReleasePage = () => import('./features/release/ReleasePage.vue')
const ReleaseConsolePage = () => import('./features/release/ReleaseConsolePage.vue')
const ReworkListPage = () => import('./features/rework/ReworkListPage.vue')
const TenantManagePage = () => import('./features/config/TenantManagePage.vue')
const UserManagePage = () => import('./features/config/UserManagePage.vue')
const RulesConfigPage = () => import('./features/config/RulesConfigPage.vue')
const AuditPage = () => import('./features/audit/AuditPage.vue')
const DevDashboardPage = () => import('./features/dev/DevDashboardPage.vue')

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
