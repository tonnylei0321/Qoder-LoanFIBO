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
import SettingsView from '@/views/settings/SettingsView.vue'

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
          path: 'settings',
          name: 'settings',
          component: SettingsView,
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

  next()
})

export default router
