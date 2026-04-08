import { createRouter, createWebHistory } from 'vue-router'
import { useAuthState } from './composables/useAuthState.js'
import { LoginView, RegisterView, AdminReviewView } from './features/auth/index.js'
import { BatchInsightsView } from './features/batch-insights/index.js'
import { FieldExtractionView, ResultView } from './features/result/index.js'
import { SearchView } from './features/search/index.js'
import { HomeView } from './features/workbench/index.js'

const routes = [
  { path: '/', name: 'Home', component: HomeView },
  { path: '/search', name: 'Search', component: SearchView },
  { path: '/result/:id', name: 'Result', component: ResultView, props: true },
  { path: '/batch-insights/:batchId', name: 'BatchInsights', component: BatchInsightsView, props: true },
  { path: '/field-extraction', name: 'FieldExtraction', component: FieldExtractionView },
  { path: '/login', name: 'Login', component: LoginView, meta: { public: true } },
  { path: '/register', name: 'Register', component: RegisterView, meta: { public: true } },
  { path: '/admin/review', name: 'AdminReview', component: AdminReviewView, meta: { requiresAdmin: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

const authState = useAuthState()

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
    const redirectTarget = String(to.query?.redirect || '/')
    return redirectTarget || '/'
  }

  if (to.meta?.requiresAdmin && !status.is_admin) {
    return { name: 'Home' }
  }

  return true
})

export default router
