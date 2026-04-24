import { test, expect } from '@playwright/test'
import { LoginPage } from '../pages/LoginPage'

test.describe('Graph Explorer Page', () => {
  let loginPage: LoginPage

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page)
    await loginPage.loginSuccessfully()
  })

  test('should load graph explorer page', async ({ page }) => {
    await page.goto('/sync/graph-explorer')
    await page.waitForLoadState('networkidle')
    expect(page.url()).toContain('/sync/graph-explorer')
    // Should show header
    await expect(page.locator('h1')).toContainText('图谱浏览')
  })

  test('should have instance selector', async ({ page }) => {
    await page.goto('/sync/graph-explorer')
    await page.waitForLoadState('networkidle')
    // Should show instance selector dropdown
    const selector = page.locator('.instance-selector .el-select')
    await expect(selector).toBeVisible()
  })

  test('should have search input', async ({ page }) => {
    await page.goto('/sync/graph-explorer')
    await page.waitForLoadState('networkidle')
    const searchInput = page.locator('.search-bar input')
    await expect(searchInput).toBeVisible()
  })

  test('should have graph container', async ({ page }) => {
    await page.goto('/sync/graph-explorer')
    await page.waitForLoadState('networkidle')
    const graphContainer = page.locator('.graph-container')
    await expect(graphContainer).toBeVisible()
  })
})

test.describe('Sync Pages', () => {
  let loginPage: LoginPage

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page)
    await loginPage.loginSuccessfully()
  })

  test('should load instance manager page', async ({ page }) => {
    await page.goto('/sync/instances')
    await page.waitForLoadState('networkidle')
    expect(page.url()).toContain('/sync/instances')
    await expect(page.locator('h1')).toContainText('实例管理')
  })

  test('should load version manager page', async ({ page }) => {
    await page.goto('/sync/versions')
    await page.waitForLoadState('networkidle')
    expect(page.url()).toContain('/sync/versions')
    await expect(page.locator('h1')).toContainText('版本管理')
  })

  test('should load sync task page', async ({ page }) => {
    await page.goto('/sync/tasks')
    await page.waitForLoadState('networkidle')
    expect(page.url()).toContain('/sync/tasks')
    await expect(page.locator('h1')).toContainText('同步任务')
  })

  test('should show tabs on sync task page', async ({ page }) => {
    await page.goto('/sync/tasks')
    await page.waitForLoadState('networkidle')
    // Should have tab for sync tasks and foreign keys
    const tabs = page.locator('.el-tabs__item')
    await expect(tabs).toHaveCount(2)
  })
})
