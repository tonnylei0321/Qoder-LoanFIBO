import { test, expect } from '@playwright/test'
import { LoginPage } from '../pages/LoginPage'

test.describe('Navigation', () => {
  let loginPage: LoginPage

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page)
    await loginPage.loginSuccessfully()
  })

  const routes = [
    { path: '/dashboard', title: '语义对齐' },
    { path: '/files/ddl', title: /DDL|文件/ },
    { path: '/jobs', title: /任务|Jobs/ },
    { path: '/loan-analysis/pre-loan', title: /贷前|Pre/ },
    { path: '/loan-analysis/post-loan', title: /贷后|Post/ },
    { path: '/loan-analysis/supply-chain', title: /供应链|Supply/ },
    { path: '/rules/nlq-query', title: /NLQ|查询/ },
    { path: '/rules/manager', title: /规则/ },
    { path: '/rules/compile-status', title: /编译|状态/ },
    { path: '/sync/graph-explorer', title: /图谱|浏览/ },
    { path: '/sync/instances', title: /实例/ },
    { path: '/sync/versions', title: /版本/ },
    { path: '/sync/tasks', title: /同步/ },
  ]

  for (const route of routes) {
    test(`should load ${route.path} page`, async ({ page }) => {
      await page.goto(route.path)
      await page.waitForLoadState('networkidle')
      expect(page.url()).toContain(route.path)
    })
  }

  test('should redirect to login on logout', async ({ page }) => {
    // Clear auth state
    await page.evaluate(() => {
      localStorage.removeItem('token')
    })
    // Navigate to protected page
    await page.goto('/dashboard')
    // Should redirect to login
    await page.waitForURL('**/login', { timeout: 10000 })
  })
})
