import { Page, Locator } from '@playwright/test'

export class SyncTaskPage {
  readonly page: Page
  readonly pageTitle: Locator
  readonly createTaskButton: Locator
  readonly refreshButton: Locator
  readonly taskTable: Locator
  readonly createTaskDialog: Locator
  readonly versionSelect: Locator
  readonly instanceSelect: Locator
  readonly upsertRadio: Locator
  readonly replaceRadio: Locator
  readonly startSyncButton: Locator

  constructor(page: Page) {
    this.page = page
    this.pageTitle = page.locator('.sync-task-view h1')
    this.createTaskButton = page.locator('.sync-task-view .header-actions button:has-text("新建同步")')
    this.refreshButton = page.locator('.sync-task-view .header-actions button:has-text("刷新")')
    this.taskTable = page.locator('.sync-task-view .el-table')
    this.createTaskDialog = page.locator('.el-dialog:has-text("新建同步任务")')
    this.versionSelect = page.locator('.el-dialog:has-text("新建同步任务") .el-select').first()
    this.instanceSelect = page.locator('.el-dialog:has-text("新建同步任务") .el-select').nth(1)
    this.upsertRadio = page.locator('.el-dialog:has-text("新建同步任务") .el-radio:has-text("增量更新")')
    this.replaceRadio = page.locator('.el-dialog:has-text("新建同步任务") .el-radio:has-text("全量替换")')
    this.startSyncButton = page.locator('.el-dialog:has-text("新建同步任务") button:has-text("开始同步")')
  }

  async goto() {
    await this.page.goto('/sync/tasks')
    await this.page.waitForLoadState('networkidle')
  }

  async getTaskRows() {
    return this.taskTable.locator('tbody tr')
  }

  async getStatValues() {
    const cards = this.page.locator('.sync-task-view .stat-card-glass')
    const count = await cards.count()
    const values: string[] = []
    for (let i = 0; i < count; i++) {
      const val = await cards.nth(i).locator('.stat-value').textContent()
      values.push(val || '0')
    }
    return values
  }

  async openCreateTaskDialog() {
    await this.createTaskButton.click()
    await this.createTaskDialog.waitFor({ state: 'visible' })
  }

  async selectVersion(versionTag: string) {
    await this.versionSelect.click()
    await this.page.locator('.el-select-dropdown__item').filter({ hasText: versionTag }).first().click()
  }

  async selectInstance(instanceName: string) {
    await this.instanceSelect.click()
    await this.page.locator('.el-select-dropdown__item').filter({ hasText: instanceName }).first().click()
  }

  async selectMode(mode: 'upsert' | 'replace') {
    if (mode === 'replace') {
      await this.replaceRadio.click()
    } else {
      await this.upsertRadio.click()
    }
  }

  async startSync() {
    await this.startSyncButton.click()
  }

  async clickRefreshForRow(index: number) {
    const row = this.taskTable.locator('tbody tr').nth(index)
    await row.locator('button:has-text("刷新")').click()
  }
}
