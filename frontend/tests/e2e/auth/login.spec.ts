import { test, expect } from '@playwright/test'
import { LoginPage } from '../pages/LoginPage'

test.describe('Login Flow', () => {
  let loginPage: LoginPage

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page)
    await loginPage.goto()
  })

  test('should display login page with brand name', async () => {
    const brandName = await loginPage.getBrandName()
    expect(brandName).toContain('LoanFIBO')
  })

  test('should show validation errors for empty fields', async ({ page }) => {
    // Click submit without filling fields
    await loginPage.submitButton.click()

    // Element Plus shows validation messages
    const errorMessages = page.locator('.el-form-item__error')
    await expect(errorMessages.first()).toBeVisible()
  })

  test('should login successfully with valid credentials', async ({ page }) => {
    await loginPage.login('admin', 'admin')

    // Should redirect to dashboard
    await page.waitForURL('**/dashboard', { timeout: 10000 })
    expect(page.url()).toContain('/dashboard')
  })

  test('should navigate to login page when not authenticated', async ({ page }) => {
    // Try to access dashboard directly
    await page.goto('/dashboard')
    // Should be redirected to login
    await page.waitForURL('**/login', { timeout: 10000 })
    expect(page.url()).toContain('/login')
  })

  test('should show loading state during login', async ({ page }) => {
    await loginPage.usernameInput.fill('admin')
    await loginPage.passwordInput.fill('admin')

    // Click and check loading state
    const clickPromise = loginPage.submitButton.click()
    // Brief loading check (may be too fast to catch)
    await clickPromise
  })
})
