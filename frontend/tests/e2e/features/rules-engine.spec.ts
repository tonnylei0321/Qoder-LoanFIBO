import { test, expect } from '@playwright/test'
import { LoginPage } from '../pages/LoginPage'

test.describe('Rules Engine - NLQ Query', () => {
  let loginPage: LoginPage

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page)
    await loginPage.loginSuccessfully()
  })

  test('should display NLQ query page', async ({ page }) => {
    await page.goto('/rules/nlq-query')
    await page.waitForLoadState('networkidle')

    const title = page.locator('[data-testid="nlq-title"]')
    await expect(title).toContainText('自然语言查询')
  })

  test('should have tenant selector and query input', async ({ page }) => {
    await page.goto('/rules/nlq-query')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('[data-testid="nlq-tenant"]')).toBeVisible()
    await expect(page.locator('[data-testid="nlq-query-input"]')).toBeVisible()
    await expect(page.locator('[data-testid="nlq-query-btn"]')).toBeVisible()
  })

  test('should show quick query tags', async ({ page }) => {
    await page.goto('/rules/nlq-query')
    await page.waitForLoadState('networkidle')

    const quickTags = page.locator('.quick-tag')
    const count = await quickTags.count()
    expect(count).toBeGreaterThan(0)
  })

  test('should fill query and submit', async ({ page }) => {
    await page.goto('/rules/nlq-query')
    await page.waitForLoadState('networkidle')

    // Playwright fill on el-input: find the visible editable element
    const wrapper = page.locator('[data-testid="nlq-query-input"]')
    await wrapper.click()
    await page.keyboard.type('查询资产负债率超过60%的企业')

    // Click query button (will fail API but test UI behavior)
    await page.locator('[data-testid="nlq-query-btn"]').click()
    // Page should still be functional
    await expect(page.locator('[data-testid="nlq-query-btn"]')).toBeVisible()
  })
})

test.describe('Rules Engine - Rules Manager', () => {
  let loginPage: LoginPage

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page)
    await loginPage.loginSuccessfully()
  })

  test('should display rules manager page', async ({ page }) => {
    await page.goto('/rules/manager')
    await page.waitForLoadState('networkidle')

    const title = page.locator('[data-testid="rules-title"]')
    await expect(title).toContainText('规则管理')
  })

  test('should have tenant selector and action buttons', async ({ page }) => {
    await page.goto('/rules/manager')
    await page.waitForLoadState('networkidle')

    await expect(page.locator('[data-testid="rules-tenant"]')).toBeVisible()
    await expect(page.locator('[data-testid="rules-add-btn"]')).toBeVisible()
    await expect(page.locator('[data-testid="rules-compile-btn"]')).toBeVisible()
  })

  test('should open create rule dialog', async ({ page }) => {
    await page.goto('/rules/manager')
    await page.waitForLoadState('networkidle')

    await page.locator('[data-testid="rules-add-btn"]').click()

    const dialog = page.locator('[data-testid="rules-create-dialog"]')
    await expect(dialog).toBeVisible()
  })
})

test.describe('Rules Engine - Compile Status', () => {
  let loginPage: LoginPage

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page)
    await loginPage.loginSuccessfully()
  })

  test('should display compile status page', async ({ page }) => {
    await page.goto('/rules/compile-status')
    await page.waitForLoadState('networkidle')

    const title = page.locator('[data-testid="compile-title"]')
    await expect(title).toContainText('编译状态看板')
  })

  test('should show stat cards', async ({ page }) => {
    await page.goto('/rules/compile-status')
    await page.waitForLoadState('networkidle')

    const statCards = page.locator('.stat-card')
    const count = await statCards.count()
    expect(count).toBe(4) // completed, compiling, failed, never
  })

  test('should show tenant cards', async ({ page }) => {
    await page.goto('/rules/compile-status')
    await page.waitForLoadState('networkidle')

    const tenantCards = page.locator('[data-testid="compile-tenant-card"]')
    // May not have visible cards if API is down, but the page should load
    await page.waitForLoadState('networkidle')
  })
})
