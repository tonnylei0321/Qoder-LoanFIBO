import { Page, Locator } from '@playwright/test'

export class LoginPage {
  readonly page: Page
  readonly usernameInput: Locator
  readonly passwordInput: Locator
  readonly submitButton: Locator
  readonly brandName: Locator

  constructor(page: Page) {
    this.page = page
    this.usernameInput = page.locator('[data-testid="login-username"]')
    this.passwordInput = page.locator('[data-testid="login-password"]')
    this.submitButton = page.locator('[data-testid="login-submit"]')
    this.brandName = page.locator('.brand-name')
  }

  async goto() {
    await this.page.goto('/login')
    await this.page.waitForLoadState('networkidle')
  }

  async login(username: string, password: string) {
    await this.usernameInput.fill(username)
    await this.passwordInput.fill(password)
    await this.submitButton.click()
  }

  async loginSuccessfully(username = 'admin', password = 'admin') {
    await this.goto()
    await this.login(username, password)
    // Wait for redirect to dashboard
    await this.page.waitForURL('**/dashboard', { timeout: 10000 })
  }

  async getBrandName(): Promise<string> {
    return (await this.brandName.textContent()) || ''
  }

  isSubmitLoading(): Promise<boolean> {
    return this.submitButton.locator('.is-loading').isVisible().catch(() => false)
  }
}
