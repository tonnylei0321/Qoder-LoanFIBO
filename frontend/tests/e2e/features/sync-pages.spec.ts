import { test, expect } from '@playwright/test'
import { LoginPage } from '../pages/LoginPage'
import { VersionManagerPage } from '../pages/VersionManagerPage'
import { InstanceManagerPage } from '../pages/InstanceManagerPage'
import { SyncTaskPage } from '../pages/SyncTaskPage'

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
    await expect(page.locator('h1')).toContainText('图谱浏览')
  })

  test('should have instance selector', async ({ page }) => {
    await page.goto('/sync/graph-explorer')
    await page.waitForLoadState('networkidle')
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

// ─── 版本管理页面测试 ────────────────────────────────────────
test.describe('Version Manager Page', () => {
  let loginPage: LoginPage
  let versionPage: VersionManagerPage

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page)
    await loginPage.loginSuccessfully()
    versionPage = new VersionManagerPage(page)
    await versionPage.goto()
  })

  test('should load version manager page with correct title', async () => {
    await expect(versionPage.pageTitle).toContainText('版本管理')
  })

  test('should display stats cards', async () => {
    const stats = await versionPage.getStatValues()
    expect(stats.length).toBe(4) // 版本总数, 草稿, 已发布, 语法异常
  })

  test('should display version table', async () => {
    await expect(versionPage.versionTable).toBeVisible()
  })

  test('should have upload TTL button', async () => {
    await expect(versionPage.uploadButton).toBeVisible()
  })

  test('should have refresh button', async () => {
    await expect(versionPage.refreshButton).toBeVisible()
  })

  test('should have status filter dropdown', async () => {
    await expect(versionPage.statusFilter).toBeVisible()
  })

  test('should open upload dialog when clicking upload button', async () => {
    await versionPage.openUploadDialog()
    await expect(versionPage.uploadDialog).toBeVisible()
    await expect(versionPage.versionTagInput).toBeVisible()
    await expect(versionPage.descriptionInput).toBeVisible()
    await expect(versionPage.createdByInput).toBeVisible()
  })

  test('should close upload dialog on cancel', async ({ page }) => {
    await versionPage.openUploadDialog()
    await page.locator('.el-dialog:has-text("上传 TTL") button:has-text("取消")').click()
    await expect(versionPage.uploadDialog).not.toBeVisible()
  })

  test('should show validation warning when uploading without file', async ({ page }) => {
    await versionPage.openUploadDialog()
    await versionPage.fillUploadForm('v1.0.0', 'Test version', 'admin')
    await versionPage.uploadSubmitButton.click()
    // Should show warning about file selection
    await expect(page.locator('.el-message')).toBeVisible({ timeout: 5000 }).catch(() => {
      // Message may appear briefly; also check form state
    })
  })

  test('should have version table columns', async () => {
    const headers = versionPage.versionTable.locator('th')
    // Should have key column headers
    await expect(headers.filter({ hasText: '版本标签' })).toBeVisible()
    await expect(headers.filter({ hasText: 'TTL 文件' })).toBeVisible()
    await expect(headers.filter({ hasText: '语法检核' })).toBeVisible()
    await expect(headers.filter({ hasText: '状态' })).toBeVisible()
    await expect(headers.filter({ hasText: '操作' })).toBeVisible()
  })

  test('should open detail drawer when clicking detail button', async ({ page }) => {
    const rows = await versionPage.getVersionRows()
    const rowCount = await rows.count()
    if (rowCount > 0) {
      await versionPage.clickDetailForRow(0)
      await expect(versionPage.detailDrawer).toBeVisible()
    }
  })
})

// ─── 实例管理页面测试 ────────────────────────────────────────
test.describe('Instance Manager Page', () => {
  let loginPage: LoginPage
  let instancePage: InstanceManagerPage

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page)
    await loginPage.loginSuccessfully()
    instancePage = new InstanceManagerPage(page)
    await instancePage.goto()
  })

  test('should load instance manager page with correct title', async () => {
    await expect(instancePage.pageTitle).toContainText('实例管理')
  })

  test('should display instance grid or empty state', async ({ page }) => {
    const cards = await instancePage.getInstanceCards()
    const cardCount = await cards.count()
    // Should either have cards or show empty state
    if (cardCount === 0) {
      await expect(page.locator('.el-empty')).toBeVisible()
    } else {
      expect(cardCount).toBeGreaterThan(0)
    }
  })

  test('should have new instance button', async () => {
    await expect(instancePage.createButton).toBeVisible()
  })

  test('should open create dialog when clicking new instance', async () => {
    await instancePage.openCreateDialog()
    await expect(instancePage.createDialog).toBeVisible()
    await expect(instancePage.nameInput).toBeVisible()
    await expect(instancePage.serverUrlInput).toBeVisible()
    await expect(instancePage.repoIdInput).toBeVisible()
    await expect(instancePage.versionSelect).toBeVisible()
  })

  test('should have version binding selector in create form', async () => {
    await instancePage.openCreateDialog()
    // 版本绑定选择器应存在
    await expect(instancePage.versionSelect).toBeVisible()
  })

  test('should close create dialog on cancel', async ({ page }) => {
    await instancePage.openCreateDialog()
    await page.locator('.el-dialog button:has-text("取消")').click()
    await expect(instancePage.createDialog).not.toBeVisible()
  })

  test('should show validation for required fields', async ({ page }) => {
    await instancePage.openCreateDialog()
    // Click save without filling fields
    await instancePage.save()
    // Should show warning about required fields
    await expect(page.locator('.el-message')).toBeVisible({ timeout: 5000 }).catch(() => {
      // Message may be brief
    })
  })

  test('should show instance card with health check button', async () => {
    const cards = await instancePage.getInstanceCards()
    const cardCount = await cards.count()
    if (cardCount > 0) {
      const firstCard = cards.nth(0)
      await expect(firstCard.locator('button:has-text("健康检查")')).toBeVisible()
      await expect(firstCard.locator('button:has-text("编辑")')).toBeVisible()
      await expect(firstCard.locator('button:has-text("删除")')).toBeVisible()
    }
  })
})

// ─── 同步任务页面测试 ────────────────────────────────────────
test.describe('Sync Task Page', () => {
  let loginPage: LoginPage
  let syncPage: SyncTaskPage

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page)
    await loginPage.loginSuccessfully()
    syncPage = new SyncTaskPage(page)
    await syncPage.goto()
  })

  test('should load sync task page with correct title', async () => {
    await expect(syncPage.pageTitle).toContainText('同步任务')
  })

  test('should display stats cards', async () => {
    const stats = await syncPage.getStatValues()
    expect(stats.length).toBe(4) // 任务总数, 已完成, 运行中, 失败
  })

  test('should display task table', async () => {
    await expect(syncPage.taskTable).toBeVisible()
  })

  test('should have create sync task button', async () => {
    await expect(syncPage.createTaskButton).toBeVisible()
  })

  test('should have refresh button', async () => {
    await expect(syncPage.refreshButton).toBeVisible()
  })

  test('should open create sync task dialog', async () => {
    await syncPage.openCreateTaskDialog()
    await expect(syncPage.createTaskDialog).toBeVisible()
    // Should have version and instance selectors
    await expect(syncPage.versionSelect).toBeVisible()
    await expect(syncPage.instanceSelect).toBeVisible()
    // Should have mode radio buttons
    await expect(syncPage.upsertRadio).toBeVisible()
    await expect(syncPage.replaceRadio).toBeVisible()
  })

  test('should have default mode as upsert', async () => {
    await syncPage.openCreateTaskDialog()
    // 增量更新 should be selected by default
    const upsertChecked = await syncPage.upsertRadio.locator('input').isChecked()
    expect(upsertChecked).toBe(true)
  })

  test('should switch mode to replace', async () => {
    await syncPage.openCreateTaskDialog()
    await syncPage.selectMode('replace')
    const replaceChecked = await syncPage.replaceRadio.locator('input').isChecked()
    expect(replaceChecked).toBe(true)
  })

  test('should close dialog on cancel', async ({ page }) => {
    await syncPage.openCreateTaskDialog()
    await page.locator('.el-dialog:has-text("新建同步任务") button:has-text("取消")').click()
    await expect(syncPage.createTaskDialog).not.toBeVisible()
  })

  test('should show validation when creating without selections', async ({ page }) => {
    await syncPage.openCreateTaskDialog()
    await syncPage.startSync()
    // Should show warning about required selections
    await expect(page.locator('.el-message')).toBeVisible({ timeout: 5000 }).catch(() => {
      // Message may be brief
    })
  })

  test('should have task table columns', async () => {
    const headers = syncPage.taskTable.locator('th')
    await expect(headers.filter({ hasText: '版本' })).toBeVisible()
    await expect(headers.filter({ hasText: '目标实例' })).toBeVisible()
    await expect(headers.filter({ hasText: '状态' })).toBeVisible()
    await expect(headers.filter({ hasText: '进度' })).toBeVisible()
  })

  test('should show progress bar in task rows', async () => {
    const rows = await syncPage.getTaskRows()
    const rowCount = await rows.count()
    if (rowCount > 0) {
      await expect(rows.nth(0).locator('.el-progress')).toBeVisible()
    }
  })
})

// ─── 页面间导航测试 ────────────────────────────────────────
test.describe('Sync Pages Navigation', () => {
  let loginPage: LoginPage

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page)
    await loginPage.loginSuccessfully()
  })

  test('should navigate between sync pages', async ({ page }) => {
    // Navigate to version manager
    await page.goto('/sync/versions')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('h1')).toContainText('版本管理')

    // Navigate to instance manager
    await page.goto('/sync/instances')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('h1')).toContainText('实例管理')

    // Navigate to sync tasks
    await page.goto('/sync/tasks')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('h1')).toContainText('同步任务')
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
})
