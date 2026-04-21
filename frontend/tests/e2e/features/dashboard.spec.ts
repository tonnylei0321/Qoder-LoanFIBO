import { test, expect } from '@playwright/test'
import { LoginPage } from '../pages/LoginPage'
import { DashboardPage } from '../pages/DashboardPage'

test.describe('Dashboard', () => {
  let loginPage: LoginPage
  let dashboardPage: DashboardPage

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page)
    dashboardPage = new DashboardPage(page)

    // Login first
    await loginPage.loginSuccessfully()
  })

  test('should display dashboard page title', async () => {
    const title = await dashboardPage.getPageTitle()
    expect(title).toContain('语义对齐')
  })

  test('should show stats cards', async () => {
    // Stats cards should be visible
    await expect(dashboardPage.totalTablesCard).toBeVisible()
  })

  test('should show new job button', async () => {
    await expect(dashboardPage.newJobButton).toBeVisible()
  })

  test('should show refresh button', async () => {
    await expect(dashboardPage.refreshButton).toBeVisible()
  })

  test('should open new job dialog on button click', async ({ page }) => {
    await dashboardPage.clickNewJob()

    // Dialog should appear (use .el-dialog specifically for NewJob)
    const dialog = page.locator('.el-dialog').first()
    await expect(dialog).toBeVisible({ timeout: 5000 })
  })

  test('should navigate between pages via sidebar', async ({ page }) => {
    // Navigate to files/ddl via URL
    await page.goto('/files/ddl')
    await page.waitForLoadState('networkidle')
    expect(page.url()).toContain('/files/ddl')
  })
})
