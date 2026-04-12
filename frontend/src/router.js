import { createRouter, createWebHistory } from 'vue-router'
import { useAuthState } from './composables/useAuthState.js'
import { AdminCenterView, DashboardView } from './features/admin/index.js'
import ProfilePage from './features/profile/ProfilePage.vue'
import { LoginView, RegisterView, AdminReviewView } from './features/auth/index.js'
import { BatchInsightsView } from './features/batch-insights/index.js'
import { FieldExtractionView, ResultView } from './features/result/index.js'
import { SearchView, SearcherHomeView } from './features/search/index.js'
import { StorageAreaView } from './features/storage/index.js'
import BatchImportPage from './features/admin/BatchImportPage.vue'
import { HomeView } from './features/workbench/index.js'
import DevDashboardPage from './features/dev/DevDashboardPage.vue'

const routes = [
  { path: '/', name: 'Home', component: HomeView },
  { path: '/search', name: 'Search', component: SearchView },
  { path: '/searcher-home', name: 'SearcherHome', component: SearcherHomeView },
  { path: '/result/:id', name: 'Result', component: ResultView, props: true },
  { path: '/batch-insights/:batchId', name: 'BatchInsights', component: BatchInsightsView, props: true },
  { path: '/field-extraction', name: 'FieldExtraction', component: FieldExtractionView },
  { path: '/login', name: 'Login', component: LoginView, meta: { public: true } },
  { path: '/register', name: 'Register', component: RegisterView, meta: { public: true } },
  { path: '/dashboard', name: 'Dashboard', component: DashboardView, meta: { requiresAdmin: true } },
  { path: '/storage', name: 'StorageArea', component: StorageAreaView },
  { path: '/admin', name: 'AdminCenter', component: AdminCenterView, meta: { requiresAdmin: true } },
  { path: '/profile', name: 'Profile', component: ProfilePage },
  { path: '/admin/review', name: 'AdminReview', component: AdminReviewView, meta: { requiresAdmin: true } },
  { path: '/batch-import', name: 'BatchImport', component: BatchImportPage, meta: { requiresAdmin: true } },
  { path: '/dev/dashboard', name: 'DevDashboard', component: DevDashboardPage, meta: { public: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const authState = useAuthState()

function roleBasedHome(status) {
  if (status.is_admin) return '/dashboard'
  if (status.role === 'searcher') return '/searcher-home'
  return '/'
}

router.beforeEach(async (to) => {
  const status = await authState.refreshAuthStatus()
  if (!status.enabled) {
    if (to.name === 'Login' || to.name === 'Register') {
      return { name: 'Home' }
    }
    return true
  }

  if (!status.authenticated) {
    if (to.meta?.public) return true
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  if (to.name === 'Login' || to.name === 'Register') {
    const redirectTarget = to.query?.redirect
    if (redirectTarget) return String(redirectTarget)
    return roleBasedHome(status)
  }

  if (to.meta?.requiresAdmin && !status.is_admin) {
    return roleBasedHome(status)
  }

  // Searcher cannot access workbench
  if (to.name === 'Home' && status.role === 'searcher') {
    return '/search'
  }

  return true
})

export default router
