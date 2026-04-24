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
          <p class="subtitle">GraphDB 同步任务与外键推断管理</p>
        </div>
      </div>
      <el-button type="primary" class="btn-glow" @click="showCreateTaskDialog = true">
        <el-icon><Plus /></el-icon>
        新建同步
      </el-button>
    </div>

    <!-- Tabs -->
    <el-tabs v-model="activeTab" class="modern-tabs">
      <!-- Sync Tasks Tab -->
      <el-tab-pane label="同步任务" name="tasks">
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

        <div class="table-card">
          <el-table :data="tasks" v-loading="loadingTasks" stripe style="width: 100%">
            <el-table-column prop="id" label="任务 ID" width="120" show-overflow-tooltip />
            <el-table-column prop="version_id" label="版本 ID" width="120" show-overflow-tooltip />
            <el-table-column prop="instance_id" label="实例 ID" width="120" show-overflow-tooltip />
            <el-table-column prop="mode" label="模式" width="100">
              <template #default="{ row }">
                <el-tag size="small" effect="plain">{{ row.mode }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="getTaskStatusType(row.status)" effect="dark" round size="small">
                  {{ getTaskStatusText(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="progress" label="进度" width="180">
              <template #default="{ row }">
                <el-progress
                  :percentage="Math.round(row.progress * 100)"
                  :status="row.status === 'completed' ? 'success' : row.status === 'failed' ? 'exception' : undefined"
                  :stroke-width="8"
                />
              </template>
            </el-table-column>
            <el-table-column prop="triples_synced" label="三元组数" width="100" />
            <el-table-column prop="created_at" label="创建时间" width="170">
              <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="refreshTask(row.id)">刷新</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <!-- Foreign Key Tab -->
      <el-tab-pane label="外键推断" name="foreign-keys">
        <div class="fk-actions">
          <el-button type="primary" @click="showInferDialog = true">
            <el-icon><MagicStick /></el-icon>
            推断外键
          </el-button>
          <el-button @click="loadForeignKeys">
            <el-icon><Refresh /></el-icon>
            刷新列表
          </el-button>
        </div>

        <div class="table-card">
          <el-table :data="foreignKeys" v-loading="loadingFK" stripe style="width: 100%">
            <el-table-column prop="source_table" label="源表" min-width="140" show-overflow-tooltip />
            <el-table-column prop="source_column" label="源列" min-width="120" show-overflow-tooltip />
            <el-table-column prop="target_table" label="目标表" min-width="140" show-overflow-tooltip />
            <el-table-column prop="target_column" label="目标列" min-width="120" show-overflow-tooltip />
            <el-table-column prop="confidence" label="置信度" width="100">
              <template #default="{ row }">
                <span :class="row.confidence >= 0.8 ? 'conf-high' : row.confidence >= 0.5 ? 'conf-mid' : 'conf-low'">
                  {{ (row.confidence * 100).toFixed(0) }}%
                </span>
              </template>
            </el-table-column>
            <el-table-column prop="inferred_by" label="来源" width="90" />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="row.status === 'approved' ? 'success' : row.status === 'rejected' ? 'danger' : 'warning'" effect="dark" round size="small">
                  {{ row.status === 'approved' ? '已批准' : row.status === 'rejected' ? '已拒绝' : '待审核' }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="160" fixed="right">
              <template #default="{ row }">
                <template v-if="row.status === 'pending'">
                  <el-button type="success" size="small" @click="approveFK(row.id, 'approve')">批准</el-button>
                  <el-button type="danger" size="small" plain @click="approveFK(row.id, 'reject')">拒绝</el-button>
                </template>
                <span v-else class="done-text">已处理</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- Create Sync Task Dialog -->
    <el-dialog v-model="showCreateTaskDialog" title="新建同步任务" width="520px" :close-on-click-modal="false">
      <el-form :model="taskForm" label-width="100px">
        <el-form-item label="发布版本" required>
          <el-select v-model="taskForm.version_id" placeholder="选择已发布版本" style="width: 100%">
            <el-option
              v-for="v in publishedVersions"
              :key="v.id"
              :label="v.version_tag"
              :value="v.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标实例" required>
          <el-select v-model="taskForm.instance_id" placeholder="选择 GraphDB 实例" style="width: 100%">
            <el-option
              v-for="i in activeInstances"
              :key="i.id"
              :label="i.name"
              :value="i.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="同步模式">
          <el-radio-group v-model="taskForm.mode">
            <el-radio value="upsert">Upsert（增量）</el-radio>
            <el-radio value="replace">Replace（全量替换）</el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateTaskDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreateTask" :loading="creatingTask">创建</el-button>
      </template>
    </el-dialog>

    <!-- Infer Foreign Key Dialog -->
    <el-dialog v-model="showInferDialog" title="外键推断" width="500px" :close-on-click-modal="false">
      <el-form label-width="100px">
        <el-form-item label="表名列表">
          <el-input
            v-model="inferTableNames"
            type="textarea"
            :rows="4"
            placeholder="每行一个表名，如：&#10;FI_COMPANY&#10;FI_INDICATOR&#10;FI_SCORE_RECORD"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showInferDialog = false">取消</el-button>
        <el-button type="primary" @click="handleInfer" :loading="inferring">开始推断</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { graphdbSyncApi, type SyncTask, type SyncTaskCreateForm, type SyncVersion, type GraphDBInstance, type ForeignKey } from '@/api/graphdbSync'
import { ElMessage } from 'element-plus'

const activeTab = ref('tasks')

// ─── Sync Tasks ────────────────────────────────────────────
const loadingTasks = ref(false)
const tasks = ref<SyncTask[]>([])

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

async function refreshTask(id: string) {
  try {
    const task = await graphdbSyncApi.getTaskProgress(id)
    const idx = tasks.value.findIndex(t => t.id === id)
    if (idx >= 0) tasks.value[idx] = task
    ElMessage.success('已刷新')
  } catch {
    ElMessage.error('刷新失败')
  }
}

// ─── Create Task Dialog ─────────────────────────────────────
const showCreateTaskDialog = ref(false)
const creatingTask = ref(false)
const allVersions = ref<SyncVersion[]>([])
const allInstances = ref<GraphDBInstance[]>([])

const publishedVersions = computed(() => allVersions.value.filter(v => v.status === 'published'))
const activeInstances = computed(() => allInstances.value.filter(i => i.is_active))

const taskForm = ref<SyncTaskCreateForm>({
  version_id: '',
  instance_id: '',
  mode: 'upsert',
})

async function loadFormData() {
  try {
    const [v, i] = await Promise.all([
      graphdbSyncApi.listVersions(),
      graphdbSyncApi.listInstances(),
    ])
    allVersions.value = v
    allInstances.value = i
  } catch {
    // Silent
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
    ElMessage.success('同步任务已创建')
    showCreateTaskDialog.value = false
    taskForm.value = { version_id: '', instance_id: '', mode: 'upsert' }
    await loadTasks()
  } catch {
    ElMessage.error('创建失败')
  } finally {
    creatingTask.value = false
  }
}

// ─── Foreign Keys ───────────────────────────────────────────
const loadingFK = ref(false)
const foreignKeys = ref<ForeignKey[]>([])

async function loadForeignKeys() {
  loadingFK.value = true
  try {
    foreignKeys.value = await graphdbSyncApi.listForeignKeys()
  } catch {
    ElMessage.error('加载外键列表失败')
  } finally {
    loadingFK.value = false
  }
}

const showInferDialog = ref(false)
const inferTableNames = ref('')
const inferring = ref(false)

async function handleInfer() {
  const names = inferTableNames.value.split('\n').map(s => s.trim()).filter(Boolean)
  if (names.length === 0) {
    ElMessage.warning('请输入至少一个表名')
    return
  }
  inferring.value = true
  try {
    await graphdbSyncApi.inferForeignKeys({ table_names: names })
    ElMessage.success('外键推断完成')
    showInferDialog.value = false
    inferTableNames.value = ''
    await loadForeignKeys()
  } catch {
    ElMessage.error('推断失败')
  } finally {
    inferring.value = false
  }
}

async function approveFK(id: string, action: 'approve' | 'reject') {
  try {
    await graphdbSyncApi.approveForeignKey(id, action)
    ElMessage.success(action === 'approve' ? '已批准' : '已拒绝')
    await loadForeignKeys()
  } catch {
    ElMessage.error('操作失败')
  }
}

// ─── Helpers ────────────────────────────────────────────────
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

onMounted(async () => {
  await Promise.all([loadTasks(), loadForeignKeys(), loadFormData()])
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

.fk-actions {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.conf-high { color: #10b981; font-weight: 600; }
.conf-mid { color: #f59e0b; font-weight: 600; }
.conf-low { color: #ef4444; font-weight: 600; }

.done-text {
  color: var(--text-muted);
  font-size: 0.8rem;
}
</style>
