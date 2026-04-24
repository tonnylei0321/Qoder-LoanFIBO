import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Layout
import MainLayout from '@/components/layout/MainLayout.vue'

// Views
import LoginView from '@/views/LoginView.vue'
import DashboardView from '@/views/dashboard/DashboardView.vue'
import DDLFilesView from '@/views/files/DDLFilesView.vue'
import TTLFilesView from '@/views/files/TTLFilesView.vue'
import JobsView from '@/views/jobs/JobsView.vue'
import NewJobView from '@/views/jobs/NewJobView.vue'
import ReviewsView from '@/views/reviews/ReviewsView.vue'
import UsersView from '@/views/users/UsersView.vue'
import RolesView from '@/views/roles/RolesView.vue'
import PermissionsView from '@/views/permissions/PermissionsView.vue'
import SettingsView from '@/views/settings/SettingsView.vue'
import PreLoanView from '@/views/loan-analysis/PreLoanView.vue'
import PostLoanView from '@/views/loan-analysis/PostLoanView.vue'
import SupplyChainView from '@/views/loan-analysis/SupplyChainView.vue'
import NLQQueryView from '@/views/rules/NLQQueryView.vue'
import RulesManagerView from '@/views/rules/RulesManagerView.vue'
import CompileStatusView from '@/views/rules/CompileStatusView.vue'
import GraphExplorerView from '@/views/sync/GraphExplorerView.vue'
import InstanceManagerView from '@/views/sync/InstanceManagerView.vue'
import VersionManagerView from '@/views/sync/VersionManagerView.vue'
import SyncTaskView from '@/views/sync/SyncTaskView.vue'
import OrgManagerView from '@/views/org/OrgManagerView.vue'
import AuthScopeView from '@/views/org/AuthScopeView.vue'
import OrgManageView from '@/views/agent/OrgManage.vue'
import AgentStatusView from '@/views/agent/AgentStatus.vue'
import AuditVersionView from '@/views/agent/AuditVersion.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { public: true },
    },
    {
      path: '/',
      component: MainLayout,
      redirect: '/dashboard',
      children: [
        {
          path: 'dashboard',
          name: 'dashboard',
          component: DashboardView,
        },
        {
          path: 'dashboard/job/:id',
          name: 'job-dashboard',
          component: DashboardView,
        },
        {
          path: 'files/ddl',
          name: 'ddl-files',
          component: DDLFilesView,
        },
        {
          path: 'files/ttl',
          name: 'ttl-files',
          component: TTLFilesView,
        },
        {
          path: 'jobs',
          name: 'jobs',
          component: JobsView,
        },
        {
          path: 'jobs/new',
          name: 'new-job',
          component: NewJobView,
        },
        {
          path: 'reviews',
          name: 'reviews',
          component: ReviewsView,
        },
        {
          path: 'users',
          name: 'users',
          component: UsersView,
          meta: { requiresAdmin: true },
        },
        {
          path: 'roles',
          name: 'roles',
          component: RolesView,
          meta: { requiresAdmin: true },
        },
        {
          path: 'permissions',
          name: 'permissions',
          component: PermissionsView,
          meta: { requiresAdmin: true },
        },
        {
          path: 'settings',
          name: 'settings',
          component: SettingsView,
        },
        {
          path: 'loan-analysis/pre-loan',
          name: 'pre-loan',
          component: PreLoanView,
        },
        {
          path: 'loan-analysis/post-loan',
          name: 'post-loan',
          component: PostLoanView,
        },
        {
          path: 'loan-analysis/supply-chain',
          name: 'supply-chain',
          component: SupplyChainView,
        },
        {
          path: 'rules/nlq-query',
          name: 'nlq-query',
          component: NLQQueryView,
        },
        {
          path: 'rules/manager',
          name: 'rules-manager',
          component: RulesManagerView,
        },
        {
          path: 'rules/compile-status',
          name: 'compile-status',
          component: CompileStatusView,
        },
        {
          path: 'sync/graph-explorer',
          name: 'graph-explorer',
          component: GraphExplorerView,
        },
        {
          path: 'sync/instances',
          name: 'instances',
          component: InstanceManagerView,
        },
        {
          path: 'sync/versions',
          name: 'versions',
          component: VersionManagerView,
        },
        {
          path: 'sync/tasks',
          name: 'sync-tasks',
          component: SyncTaskView,
        },
        {
          path: 'org/orgs',
          name: 'org-manager',
          component: OrgManagerView,
        },
        {
          path: 'org/auth-scopes',
          name: 'auth-scopes',
          component: AuthScopeView,
        },
        // Agent 管理路由
        {
          path: 'agent/orgs',
          name: 'agent-orgs',
          component: OrgManageView,
          meta: { requiresAdmin: true },
        },
        {
          path: 'agent/status',
          name: 'agent-status',
          component: AgentStatusView,
        },
        {
          path: 'agent/audit',
          name: 'agent-audit',
          component: AuditVersionView,
          meta: { requiresAdmin: true },
        },
      ],
    },
  ],
})

// Navigation guard
router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  // Check if route is public
  if (to.meta.public) {
    next()
    return
  }

  // Check if user is logged in
  if (!authStore.isLoggedIn) {
    next('/login')
    return
  }

  // Fetch user info if not loaded
  if (!authStore.user) {
    await authStore.fetchUserInfo()
  }

  // Check admin permission
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next('/dashboard')
    return
  }

  // Menu-based access control (skip for admin — menuCodes === null)
  const routeName = to.name as string | undefined
  if (routeName && routeName !== 'dashboard' && authStore.menuCodes !== null) {
    if (!authStore.canAccessMenu(routeName)) {
      next('/dashboard')
      return
    }
  }

  next()
})

export default router
