import { Page, Locator } from '@playwright/test'

export class DashboardPage {
  readonly page: Page
  readonly newJobButton: Locator
  readonly refreshButton: Locator
  readonly totalTablesCard: Locator
  readonly pageTitle: Locator

  constructor(page: Page) {
    this.page = page
    this.newJobButton = page.locator('[data-testid="btn-new-job"]')
    this.refreshButton = page.locator('[data-testid="btn-refresh"]')
    this.totalTablesCard = page.locator('[data-testid="stat-total-tables"]')
    this.pageTitle = page.locator('.dashboard-header h1')
  }

  async goto() {
    await this.page.goto('/dashboard')
    await this.page.waitForLoadState('networkidle')
  }

  async getPageTitle(): Promise<string> {
    return (await this.pageTitle.textContent()) || ''
  }

  async clickNewJob() {
    await this.newJobButton.click()
  }

  async clickRefresh() {
    await this.refreshButton.click()
  }

  async getStatValue(testid: string): Promise<string> {
    const card = this.page.locator(`[data-testid="${testid}"] .stat-value`)
    return (await card.textContent()) || '0'
  }
}
