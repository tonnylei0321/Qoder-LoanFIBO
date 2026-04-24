<template>
  <div class="version-manager">
    <!-- Header -->
    <div class="page-header-modern">
      <div class="header-content">
        <div class="header-icon">
          <el-icon><Collection /></el-icon>
        </div>
        <div class="header-text">
          <h1>版本管理</h1>
          <p class="subtitle">管理 FIBO 映射版本快照与发布</p>
        </div>
      </div>
      <el-button type="primary" class="btn-glow" @click="showCreateDialog = true">
        <el-icon><Plus /></el-icon>
        创建版本
      </el-button>
    </div>

    <!-- Stats -->
    <div class="stats-grid">
      <div class="stat-card-glass">
        <div class="stat-icon primary"><el-icon><Collection /></el-icon></div>
        <div class="stat-info">
          <span class="stat-value">{{ versions.length }}</span>
          <span class="stat-label">版本总数</span>
        </div>
      </div>
      <div class="stat-card-glass">
        <div class="stat-icon warning"><el-icon><EditPen /></el-icon></div>
        <div class="stat-info">
          <span class="stat-value">{{ versions.filter(v => v.status === 'draft').length }}</span>
          <span class="stat-label">草稿</span>
        </div>
      </div>
      <div class="stat-card-glass">
        <div class="stat-icon success"><el-icon><CircleCheck /></el-icon></div>
        <div class="stat-info">
          <span class="stat-value">{{ versions.filter(v => v.status === 'published').length }}</span>
          <span class="stat-label">已发布</span>
        </div>
      </div>
    </div>

    <!-- Version Table -->
    <div class="version-table-card">
      <el-table :data="versions" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="version_tag" label="版本标签" min-width="120">
          <template #default="{ row }">
            <span class="version-tag">{{ row.version_tag }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="row.status === 'published' ? 'success' : 'warning'" effect="dark" round size="small">
              {{ row.status === 'published' ? '已发布' : '草稿' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
        <el-table-column prop="created_by" label="创建者" width="120" />
        <el-table-column prop="created_at" label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="published_at" label="发布时间" width="170">
          <template #default="{ row }">{{ formatTime(row.published_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row)">详情</el-button>
            <el-button
              v-if="row.status === 'draft'"
              type="success"
              size="small"
              @click="handlePublish(row)"
            >
              发布
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Create Dialog -->
    <el-dialog v-model="showCreateDialog" title="创建版本快照" width="500px" :close-on-click-modal="false">
      <el-form :model="createForm" label-width="90px">
        <el-form-item label="版本标签" required>
          <el-input v-model="createForm.version_tag" placeholder="如 v1.0.0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="版本描述" />
        </el-form-item>
        <el-form-item label="创建者">
          <el-input v-model="createForm.created_by" placeholder="创建者" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate" :loading="creating">创建</el-button>
      </template>
    </el-dialog>

    <!-- Detail Drawer -->
    <el-drawer v-model="showDetail" title="版本详情" size="480px">
      <template v-if="detailData">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="版本标签">{{ detailData.version_tag }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="detailData.status === 'published' ? 'success' : 'warning'" effect="dark" round size="small">
              {{ detailData.status === 'published' ? '已发布' : '草稿' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="描述">{{ detailData.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建者">{{ detailData.created_by || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(detailData.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="发布时间">{{ formatTime(detailData.published_at) }}</el-descriptions-item>
          <el-descriptions-item label="同步时间">{{ formatTime(detailData.synced_at) }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="detailData.snapshot_data" class="snapshot-section">
          <h4>快照数据</h4>
          <el-input type="textarea" :rows="8" :model-value="JSON.stringify(detailData.snapshot_data, null, 2)" readonly />
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { graphdbSyncApi, type SyncVersion, type VersionCreateForm } from '@/api/graphdbSync'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const versions = ref<SyncVersion[]>([])
const showCreateDialog = ref(false)
const creating = ref(false)
const showDetail = ref(false)
const detailData = ref<SyncVersion | null>(null)

const createForm = ref<VersionCreateForm>({
  version_tag: '',
  description: '',
  created_by: '',
})

function formatTime(iso?: string | null): string {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

async function loadVersions() {
  loading.value = true
  try {
    versions.value = await graphdbSyncApi.listVersions()
  } catch {
    ElMessage.error('加载版本列表失败')
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!createForm.value.version_tag.trim()) {
    ElMessage.warning('请输入版本标签')
    return
  }
  creating.value = true
  try {
    await graphdbSyncApi.createVersion(createForm.value)
    ElMessage.success('版本创建成功')
    showCreateDialog.value = false
    createForm.value = { version_tag: '', description: '', created_by: '' }
    await loadVersions()
  } catch {
    ElMessage.error('创建失败')
  } finally {
    creating.value = false
  }
}

async function handlePublish(version: SyncVersion) {
  try {
    await ElMessageBox.confirm(`确定要发布版本 ${version.version_tag} 吗？`, '发布确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await graphdbSyncApi.publishVersion(version.id)
    ElMessage.success('版本已发布')
    await loadVersions()
  } catch {
    // cancelled or error
  }
}

function viewDetail(version: SyncVersion) {
  detailData.value = version
  showDetail.value = true
}

onMounted(loadVersions)
</script>

<style scoped>
.version-manager {
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
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
.stat-icon.warning { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
.stat-icon.success { background: rgba(16, 185, 129, 0.15); color: #10b981; }

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

.version-table-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 16px;
}

.version-tag {
  font-family: 'Fira Code', monospace;
  font-weight: 600;
  color: #667eea;
}

.snapshot-section {
  margin-top: 16px;
}

.snapshot-section h4 {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}
</style>
