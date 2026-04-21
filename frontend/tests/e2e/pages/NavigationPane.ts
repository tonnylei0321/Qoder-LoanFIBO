import { Page, Locator } from '@playwright/test'

export class NavigationPane {
  readonly page: Page
  readonly sidebar: Locator
  readonly menuItems: Locator

  constructor(page: Page) {
    this.page = page
    this.sidebar = page.locator('.sidebar, .el-menu, nav, [class*="sidebar"], [class*="nav"]')
    this.menuItems = this.sidebar.locator('a, .el-menu-item, [role="menuitem"]')
  }

  async navigateTo(route: string) {
    await this.page.goto(`/${route}`)
    await this.page.waitForLoadState('networkidle')
  }

  async clickMenuItem(label: string) {
    const item = this.sidebar.locator(`text="${label}"`).first()
    await item.click()
    await this.page.waitForLoadState('networkidle')
  }

  async getCurrentPath(): Promise<string> {
    const url = this.page.url()
    return new URL(url).pathname
  }
}
