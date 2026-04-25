import { Page, Locator } from '@playwright/test'

export class InstanceManagerPage {
  readonly page: Page
  readonly pageTitle: Locator
  readonly createButton: Locator
  readonly instanceGrid: Locator
  readonly createDialog: Locator
  readonly nameInput: Locator
  readonly serverUrlInput: Locator
  readonly repoIdInput: Locator
  readonly namespaceInput: Locator
  readonly domainInput: Locator
  readonly versionSelect: Locator
  readonly saveButton: Locator

  constructor(page: Page) {
    this.page = page
    this.pageTitle = page.locator('.instance-manager h1')
    this.createButton = page.locator('.instance-manager button:has-text("新增实例")')
    this.instanceGrid = page.locator('.instance-manager .instance-grid')
    this.createDialog = page.locator('.el-dialog:has-text("新增实例"), .el-dialog:has-text("编辑实例")')
    this.nameInput = page.locator('.el-dialog input[placeholder="如: Production GraphDB"]')
    this.serverUrlInput = page.locator('.el-dialog input[placeholder="如: http://localhost:7200"]')
    this.repoIdInput = page.locator('.el-dialog input[placeholder="如: loanfibo"]')
    this.namespaceInput = page.locator('.el-dialog input[placeholder="loanfibo"]')
    this.domainInput = page.locator('.el-dialog input[placeholder="如: finance"]')
    this.versionSelect = page.locator('.el-dialog .el-select:has(input[placeholder="选择版本（可选）"])')
    this.saveButton = page.locator('.el-dialog button:has-text("保存")')
  }

  async goto() {
    await this.page.goto('/sync/instances')
    await this.page.waitForLoadState('networkidle')
  }

  async getInstanceCards() {
    return this.instanceGrid.locator('.instance-card')
  }

  async openCreateDialog() {
    await this.createButton.click()
    await this.createDialog.waitFor({ state: 'visible' })
  }

  async openEditDialog(cardIndex: number) {
    const card = this.instanceGrid.locator('.instance-card').nth(cardIndex)
    await card.locator('button:has-text("编辑")').click()
    await this.createDialog.waitFor({ state: 'visible' })
  }

  async fillForm(data: { name: string; server_url: string; repo_id: string; domain?: string }) {
    await this.nameInput.fill(data.name)
    await this.serverUrlInput.fill(data.server_url)
    await this.repoIdInput.fill(data.repo_id)
    if (data.domain) await this.domainInput.fill(data.domain)
  }

  async save() {
    await this.saveButton.click()
  }

  async checkHealth(cardIndex: number) {
    const card = this.instanceGrid.locator('.instance-card').nth(cardIndex)
    await card.locator('button:has-text("健康检查")').click()
  }

  async deleteInstance(cardIndex: number) {
    const card = this.instanceGrid.locator('.instance-card').nth(cardIndex)
    await card.locator('button:has-text("删除")').click()
  }

  async confirmDelete() {
    await this.page.locator('.el-message-box__btns button:has-text("确定")').click()
  }

  async getInstanceCardInfo(cardIndex: number) {
    const card = this.instanceGrid.locator('.instance-card').nth(cardIndex)
    const name = await card.locator('.instance-name').textContent()
    return { name: name || '' }
  }
}
