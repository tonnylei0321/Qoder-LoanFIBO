<template>
  <div class="sync-task-view">
    <!-- Header -->
    <div class="page-header-modern">
      <div class="header-content">
        <div class="header-icon">
          <el-icon><Refresh /></el-icon>
        </div>
        <div class="header-text">
          <h1>同步任务</h1>
          <p class="subtitle">选择 TTL 版本导入 GraphDB，实时查看同步进度</p>
        </div>
      </div>
      <div class="header-actions">
        <el-button type="primary" class="btn-glow" @click="showCreateTaskDialog = true">
          <el-icon><Plus /></el-icon>
          新建同步
        </el-button>
        <el-button @click="loadTasks" :loading="loadingTasks">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- Stats -->
    <div class="task-stats-grid">
      <div class="stat-card-glass">
        <div class="stat-icon primary"><el-icon><List /></el-icon></div>
        <div class="stat-info">
          <span class="stat-value">{{ tasks.length }}</span>
          <span class="stat-label">任务总数</span>
        </div>
      </div>
      <div class="stat-card-glass">
        <div class="stat-icon success"><el-icon><CircleCheck /></el-icon></div>
        <div class="stat-info">
          <span class="stat-value">{{ tasks.filter(t => t.status === 'completed').length }}</span>
          <span class="stat-label">已完成</span>
        </div>
      </div>
      <div class="stat-card-glass">
        <div class="stat-icon warning"><el-icon><Loading /></el-icon></div>
        <div class="stat-info">
          <span class="stat-value">{{ tasks.filter(t => t.status === 'running').length }}</span>
          <span class="stat-label">运行中</span>
        </div>
      </div>
      <div class="stat-card-glass">
        <div class="stat-icon danger"><el-icon><CircleClose /></el-icon></div>
        <div class="stat-info">
          <span class="stat-value">{{ tasks.filter(t => t.status === 'failed').length }}</span>
          <span class="stat-label">失败</span>
        </div>
      </div>
    </div>

    <!-- Task Table -->
    <div class="table-card">
      <el-table :data="tasks" v-loading="loadingTasks" stripe style="width: 100%">
        <el-table-column label="版本" min-width="140">
          <template #default="{ row }">
            <span class="version-link">{{ getVersionTag(row.version_id) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="目标实例" min-width="140">
          <template #default="{ row }">
            <span>{{ getInstanceName(row.instance_id) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="mode" label="模式" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.mode === 'replace' ? '全量替换' : '增量' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="getTaskStatusType(row.status)" effect="dark" round size="small">
              {{ getTaskStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="200">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round(row.progress * 100)"
              :status="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'exception' : undefined"
              :stroke-width="8"
            />
          </template>
        </el-table-column>
        <el-table-column prop="triples_synced" label="已同步行数" width="110" />
        <el-table-column label="错误信息" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.error_message" class="error-text">{{ row.error_message }}</span>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="refreshTask(row.id)" :loading="refreshing === row.id">刷新</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Create Sync Task Dialog -->
    <el-dialog v-model="showCreateTaskDialog" title="新建同步任务" width="520px" :close-on-click-modal="false">
      <el-form :model="taskForm" label-width="100px">
        <el-form-item label="TTL 版本" required>
          <el-select v-model="taskForm.version_id" placeholder="选择版本" style="width: 100%">
            <el-option
              v-for="v in versionsWithTTL"
              :key="v.id"
              :label="v.version_tag + ' - ' + (v.ttl_file_name || '无文件')"
              :value="v.id"
            >
              <div style="display:flex;justify-content:space-between;align-items:center">
                <span>{{ v.version_tag }}</span>
                <el-tag v-if="v.ttl_valid === false" type="danger" size="small">语法异常</el-tag>
                <el-tag v-else-if="v.ttl_valid === true" type="success" size="small">通过</el-tag>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="目标实例" required>
          <el-select v-model="taskForm.instance_id" placeholder="选择 GraphDB 实例" style="width: 100%">
            <el-option
              v-for="i in activeInstances"
              :key="i.id"
              :label="i.name + ' (' + i.repo_id + ')'"
              :value="i.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="同步模式">
          <el-radio-group v-model="taskForm.mode">
            <el-radio value="upsert">增量更新</el-radio>
            <el-radio value="replace">全量替换</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateTaskDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateTask" :loading="creatingTask">开始同步</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { graphdbSyncApi, type SyncTask, type SyncTaskCreateForm, type SyncVersion, type GraphDBInstance } from '@/api/graphdbSync'
import { ElMessage } from 'element-plus'

const loadingTasks = ref(false)
const refreshing = ref<string | null>(null)
const tasks = ref<SyncTask[]>([])
const allVersions = ref<SyncVersion[]>([])
const allInstances = ref<GraphDBInstance[]>([])
let pollTimer: ReturnType<typeof setInterval> | null = null

const versionsWithTTL = computed(() => allVersions.value.filter(v => v.ttl_file_name))
const activeInstances = computed(() => allInstances.value.filter(i => i.is_active))

const showCreateTaskDialog = ref(false)
const creatingTask = ref(false)
const taskForm = ref<SyncTaskCreateForm>({
  version_id: '',
  instance_id: '',
  mode: 'upsert',
})

async function loadTasks() {
  loadingTasks.value = true
  try {
    tasks.value = await graphdbSyncApi.listSyncTasks()
  } catch {
    ElMessage.error('加载同步任务失败')
  } finally {
    loadingTasks.value = false
  }
}

async function loadFormData() {
  try {
    const [v, i] = await Promise.all([
      graphdbSyncApi.listVersions(),
      graphdbSyncApi.listInstances(),
    ])
    allVersions.value = v
    allInstances.value = i
  } catch { /* silent */ }
}

async function refreshTask(id: string) {
  refreshing.value = id
  try {
    const task = await graphdbSyncApi.getTaskProgress(id)
    const idx = tasks.value.findIndex(t => t.id === id)
    if (idx >= 0) tasks.value[idx] = task
  } catch {
    ElMessage.error('刷新失败')
  } finally {
    refreshing.value = null
  }
}

async function handleCreateTask() {
  if (!taskForm.value.version_id || !taskForm.value.instance_id) {
    ElMessage.warning('请选择版本和实例')
    return
  }
  creatingTask.value = true
  try {
    await graphdbSyncApi.createSyncTask(taskForm.value)
    ElMessage.success('同步任务已创建并开始执行')
    showCreateTaskDialog.value = false
    taskForm.value = { version_id: '', instance_id: '', mode: 'upsert' }
    await loadTasks()
  } catch {
    ElMessage.error('创建失败')
  } finally {
    creatingTask.value = false
  }
}

function getVersionTag(versionId: string): string {
  const v = allVersions.value.find(ver => ver.id === versionId)
  return v ? v.version_tag : versionId
}

function getInstanceName(instanceId: string): string {
  const i = allInstances.value.find(inst => inst.id === instanceId)
  return i ? i.name : instanceId
}

function formatTime(iso?: string | null): string {
  if (!iso) return '-'
  try { return new Date(iso).toLocaleString('zh-CN') } catch { return iso }
}

function getTaskStatusType(s: string): string {
  if (s === 'completed') return 'success'
  if (s === 'running') return ''
  if (s === 'failed') return 'danger'
  return 'info'
}

function getTaskStatusText(s: string): string {
  const map: Record<string, string> = { pending: '待执行', running: '运行中', completed: '已完成', failed: '失败' }
  return map[s] || s
}

// Auto-poll running tasks every 2 seconds
function startPolling() {
  pollTimer = setInterval(async () => {
    const hasRunning = tasks.value.some(t => t.status === 'running' || t.status === 'pending')
    if (hasRunning) {
      try {
        tasks.value = await graphdbSyncApi.listSyncTasks()
      } catch { /* silent */ }
    }
  }, 2000)
}

onMounted(async () => {
  await Promise.all([loadTasks(), loadFormData()])
  startPolling()
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.sync-task-view {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header-modern {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.header-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 20px;
}

.header-text h1 {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.subtitle {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin: 0;
}

.task-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card-glass {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all 0.2s ease;
}

.stat-card-glass:hover {
  border-color: #667eea;
}

.stat-icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}

.stat-icon.primary { background: rgba(102, 126, 234, 0.15); color: #667eea; }
.stat-icon.success { background: rgba(16, 185, 129, 0.15); color: #10b981; }
.stat-icon.warning { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
.stat-icon.danger { background: rgba(239, 68, 68, 0.15); color: #ef4444; }

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  display: block;
}

.stat-label {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.table-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
}

.version-link {
  font-family: 'Fira Code', monospace;
  font-weight: 600;
  color: #667eea;
}

.error-text {
  color: #ef4444;
  font-size: 0.82rem;
}

.text-muted {
  color: var(--text-muted);
}
</style>
