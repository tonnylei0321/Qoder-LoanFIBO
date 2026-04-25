import { Page, Locator } from '@playwright/test'

export class VersionManagerPage {
  readonly page: Page
  readonly pageTitle: Locator
  readonly uploadButton: Locator
  readonly refreshButton: Locator
  readonly statusFilter: Locator
  readonly versionTable: Locator
  readonly uploadDialog: Locator
  readonly versionTagInput: Locator
  readonly descriptionInput: Locator
  readonly createdByInput: Locator
  readonly fileUpload: Locator
  readonly uploadSubmitButton: Locator
  readonly detailDrawer: Locator

  constructor(page: Page) {
    this.page = page
    this.pageTitle = page.locator('.version-manager h1')
    this.uploadButton = page.locator('.version-manager .header-actions .btn-glow, .version-manager .header-actions button:has-text("上传")').first()
    this.refreshButton = page.locator('.version-manager .header-actions button:has-text("刷新")')
    this.statusFilter = page.locator('.version-manager .header-actions .el-select')
    this.versionTable = page.locator('.version-manager .el-table')
    this.uploadDialog = page.locator('.el-dialog:has-text("上传 TTL")')
    this.versionTagInput = page.locator('.el-dialog:has-text("上传 TTL") input[placeholder="如 v1.0.0"]')
    this.descriptionInput = page.locator('.el-dialog:has-text("上传 TTL") textarea')
    this.createdByInput = page.locator('.el-dialog:has-text("上传 TTL") input[placeholder="如: admin"]')
    this.fileUpload = page.locator('.el-dialog:has-text("上传 TTL") .el-upload button')
    this.uploadSubmitButton = page.locator('.el-dialog:has-text("上传 TTL") button:has-text("上传")').last()
    this.detailDrawer = page.locator('.el-drawer:has-text("版本详情")')
  }

  async goto() {
    await this.page.goto('/sync/versions')
    await this.page.waitForLoadState('networkidle')
  }

  async getStatValues() {
    const cards = this.page.locator('.version-manager .stat-card-glass')
    const count = await cards.count()
    const values: string[] = []
    for (let i = 0; i < count; i++) {
      const val = await cards.nth(i).locator('.stat-value').textContent()
      values.push(val || '0')
    }
    return values
  }

  async getVersionRows() {
    return this.versionTable.locator('tbody tr')
  }

  async openUploadDialog() {
    await this.uploadButton.click()
    await this.uploadDialog.waitFor({ state: 'visible' })
  }

  async fillUploadForm(versionTag: string, description?: string, createdBy?: string) {
    await this.versionTagInput.fill(versionTag)
    if (description) await this.descriptionInput.fill(description)
    if (createdBy) await this.createdByInput.fill(createdBy)
  }

  async clickPublishForRow(index: number) {
    const row = this.versionTable.locator('tbody tr').nth(index)
    await row.locator('button:has-text("发布")').click()
  }

  async confirmPublish() {
    await this.page.locator('.el-message-box__btns button:has-text("确定")').click()
  }

  async clickDetailForRow(index: number) {
    const row = this.versionTable.locator('tbody tr').nth(index)
    await row.locator('button:has-text("详情")').click()
  }

  async selectStatusFilter(status: string) {
    await this.statusFilter.click()
    await this.page.locator('.el-select-dropdown__item:has-text("' + status + '")').click()
  }
}
