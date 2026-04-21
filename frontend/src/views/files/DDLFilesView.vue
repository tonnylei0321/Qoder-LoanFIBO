<template>
  <div class="ddl-files">
    <!-- Modern Header -->
    <div class="page-header-modern">
      <div class="header-content">
        <div class="header-icon">
          <el-icon><Document /></el-icon>
        </div>
        <div class="header-text">
          <h1>DDL 版本管理</h1>
          <p class="subtitle">管理数据库结构定义文件版本</p>
        </div>
      </div>
      <el-button type="primary" class="btn-glow" @click="showUploadDialog = true">
        <el-icon><Upload /></el-icon>
        上传 DDL 文件
      </el-button>
    </div>

    <!-- Stats Overview -->
    <div class="file-stats-grid">
      <div class="stat-card-glass">
        <div class="stat-icon blue">
          <el-icon><DocumentChecked /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ files.length }}</span>
          <span class="stat-label">文件总数</span>
        </div>
      </div>
      <div class="stat-card-glass">
        <div class="stat-icon green">
          <el-icon><CircleCheck /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ files.filter(f => f.parseStatus === 'completed').length }}</span>
          <span class="stat-label">已解析</span>
        </div>
      </div>
      <div class="stat-card-glass">
        <div class="stat-icon orange">
          <el-icon><Timer /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ files.filter(f => f.parseStatus === 'pending').length }}</span>
          <span class="stat-label">待解析</span>
        </div>
      </div>
      <div class="stat-card-glass">
        <div class="stat-icon purple">
          <el-icon><Grid /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ files.reduce((sum, f) => sum + (f.tableCount || 0), 0) }}</span>
          <span class="stat-label">总表数</span>
        </div>
      </div>
    </div>

    <!-- File List Card -->
    <div class="file-list-card">
      <div class="card-header">
        <span class="card-title">文件列表</span>
        <el-input
          v-model="searchQuery"
          placeholder="搜索版本标签或ERP来源..."
          class="search-input"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
      
      <el-table :data="filteredFiles" v-loading="loading" class="modern-table">
        <el-table-column prop="sourceTag" label="版本标签" min-width="200">
          <template #default="{ row }">
            <div class="file-tag">
              <el-icon><Document /></el-icon>
              <span>{{ row.sourceTag }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="erpSource" label="ERP来源" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.erpSource }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="version" label="版本号" width="100">
          <template #default="{ row }">
            <span class="version-text">{{ row.version }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="fileSize" label="文件大小" width="120">
          <template #default="{ row }">
            <span class="file-size">{{ formatFileSize(row.fileSize) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="tableCount" label="表数量" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.tableCount" type="info" effect="plain" size="small">
              {{ row.tableCount }} 表
            </el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="parseStatus" label="解析状态" width="120" align="center">
          <template #default="{ row }">
            <div class="status-badge" :class="row.parseStatus">
              <span class="status-dot"></span>
              <span>{{ getStatusText(row.parseStatus) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="uploadTime" label="上传时间" width="180">
          <template #default="{ row }">
            <span class="time-text">{{ row.uploadTime }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button
                v-if="row.parseStatus === 'pending'"
                type="primary"
                size="small"
                class="btn-action"
                @click="handleParse(row)"
              >
                <el-icon><VideoPlay /></el-icon>
                解析
              </el-button>
              <el-button type="primary" size="small" plain class="btn-action" @click="handleView(row)">
                <el-icon><View /></el-icon>
                查看
              </el-button>
              <el-button type="danger" size="small" plain class="btn-action" @click="handleDelete(row)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-modern">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="loadFiles"
          @current-change="loadFiles"
        />
      </div>
    </div>

    <!-- Upload Dialog -->
    <el-dialog v-model="showUploadDialog" title="上传 DDL 文件" width="500px">
      <el-form :model="uploadForm" label-width="100px">
        <el-form-item label="版本标签" required>
          <el-input
            v-model="uploadForm.sourceTag"
            placeholder="例如：BIPV5-财务域-v1.2"
          />
        </el-form-item>
        <el-form-item label="ERP来源" required>
          <el-input
            v-model="uploadForm.erpSource"
            placeholder="例如：BIPV5、SAP"
          />
        </el-form-item>
        <el-form-item label="版本号" required>
          <el-input v-model="uploadForm.version" placeholder="例如：v1.2" />
        </el-form-item>
        <el-form-item label="文件" required>
          <el-upload
            ref="uploadRef"
            action="#"
            :auto-upload="false"
            :on-change="handleFileChange"
            :limit="1"
            accept=".sql,.ddl"
          >
            <el-button type="primary">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">
                支持 .sql 或 .ddl 格式文件
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="handleUpload">
          上传
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadInstance, UploadFile } from 'element-plus'
import { filesApi } from '@/api'
import type { DDLFile } from '@/types'

const loading = ref(false)
const showUploadDialog = ref(false)
const uploading = ref(false)
const uploadRef = ref<UploadInstance>()
const files = ref<DDLFile[]>([])
const selectedFile = ref<File | null>(null)
const searchQuery = ref('')

// Computed
const filteredFiles = computed(() => {
  if (!searchQuery.value) return files.value
  const query = searchQuery.value.toLowerCase()
  return files.value.filter(f => 
    f.sourceTag.toLowerCase().includes(query) ||
    f.erpSource.toLowerCase().includes(query)
  )
})

const uploadForm = reactive({
  sourceTag: '',
  erpSource: '',
  version: '',
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})

const formatFileSize = (size: number) => {
  if (size < 1024) return size + ' B'
  if (size < 1024 * 1024) return (size / 1024).toFixed(2) + ' KB'
  return (size / (1024 * 1024)).toFixed(2) + ' MB'
}

const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    parsing: 'warning',
    completed: 'success',
    failed: 'danger',
  }
  return map[status] || 'info'
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待解析',
    parsing: '解析中',
    completed: '已完成',
    failed: '失败',
  }
  return map[status] || status
}

const loadFiles = async () => {
  loading.value = true
  try {
    const res = await filesApi.getDDLFiles({
      page: pagination.page,
      pageSize: pagination.pageSize,
    })
    files.value = res.items
    pagination.total = res.total
  } catch (error) {
    ElMessage.error('加载文件列表失败')
  } finally {
    loading.value = false
  }
}

const handleFileChange = (uploadFile: UploadFile) => {
  selectedFile.value = uploadFile.raw || null
}

const handleUpload = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  if (!uploadForm.sourceTag || !uploadForm.erpSource || !uploadForm.version) {
    ElMessage.warning('请填写完整信息')
    return
  }

  uploading.value = true
  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('sourceTag', uploadForm.sourceTag)
  formData.append('erpSource', uploadForm.erpSource)
  formData.append('version', uploadForm.version)

  try {
    await filesApi.uploadDDLFile(formData)
    ElMessage.success('上传成功')
    showUploadDialog.value = false
    loadFiles()
  } catch (error) {
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
    selectedFile.value = null
    uploadRef.value?.clearFiles()
  }
}

const handleParse = async (row: DDLFile) => {
  try {
    await filesApi.parseDDLFile(row.id)
    ElMessage.success('解析任务已启动')
    loadFiles()
  } catch (error) {
    ElMessage.error('启动解析失败')
  }
}

const handleView = (row: DDLFile) => {
  console.log('View file:', row)
}

const handleDelete = async (row: DDLFile) => {
  try {
    await ElMessageBox.confirm('确定要删除该文件吗？', '提示', {
      type: 'warning',
    })
    await filesApi.deleteDDLFile(row.id)
    ElMessage.success('删除成功')
    loadFiles()
  } catch {
    // Cancelled
  }
}

onMounted(() => {
  loadFiles()
})
</script>

<style scoped>
.ddl-files {
  padding-bottom: 40px;
}

/* Modern Header */
.page-header-modern {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-icon {
  width: 56px;
  height: 56px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 28px;
}

.header-text h1 {
  margin: 0 0 4px 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
}

.subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
}

.btn-glow {
  background: var(--gradient-primary) !important;
  border: none !important;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
}

/* Stats Grid */
.file-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card-glass {
  background: var(--card-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all 0.3s ease;
}

.stat-card-glass:hover {
  transform: translateY(-2px);
  border-color: rgba(102, 126, 234, 0.3);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  flex-shrink: 0;
}

.stat-icon.blue {
  background: rgba(24, 144, 255, 0.15);
  color: #1890ff;
}

.stat-icon.green {
  background: rgba(0, 200, 83, 0.15);
  color: #00c853;
}

.stat-icon.orange {
  background: rgba(255, 171, 0, 0.15);
  color: #ffab00;
}

.stat-icon.purple {
  background: rgba(102, 126, 234, 0.15);
  color: #667eea;
}

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 2px;
}

/* File List Card */
.file-list-card {
  background: var(--card-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  padding: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.search-input {
  width: 300px;
}

.search-input :deep(.el-input__wrapper) {
  background: var(--bg-tertiary);
  box-shadow: 0 0 0 1px var(--border-color) inset;
}

/* Modern Table */
.modern-table {
  --el-table-border-color: var(--divider-color);
  --el-table-header-bg-color: var(--bg-tertiary);
}

.modern-table :deep(.el-table__header th) {
  font-weight: 600;
  color: var(--text-secondary);
  background: var(--bg-tertiary);
}

.modern-table :deep(.el-table__row) {
  transition: all 0.2s ease;
}

.modern-table :deep(.el-table__row:hover) {
  background: var(--bg-tertiary);
}

/* File Tag */
.file-tag {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  font-weight: 500;
}

.file-tag .el-icon {
  color: var(--primary-400);
  font-size: 18px;
}

/* Version Text */
.version-text {
  font-family: var(--font-mono);
  color: var(--text-secondary);
  font-size: 13px;
}

/* File Size */
.file-size {
  color: var(--text-secondary);
  font-size: 13px;
}

/* Time Text */
.time-text {
  color: var(--text-muted);
  font-size: 13px;
}

/* Status Badge */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

.status-badge .status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-badge.pending {
  background: rgba(0, 176, 255, 0.1);
  color: var(--info);
}

.status-badge.pending .status-dot {
  background: var(--info);
  box-shadow: 0 0 6px var(--info);
}

.status-badge.parsing {
  background: rgba(255, 171, 0, 0.1);
  color: var(--warning);
}

.status-badge.parsing .status-dot {
  background: var(--warning);
  box-shadow: 0 0 6px var(--warning);
  animation: pulse 1.5s infinite;
}

.status-badge.completed {
  background: rgba(0, 200, 83, 0.1);
  color: var(--success);
}

.status-badge.completed .status-dot {
  background: var(--success);
  box-shadow: 0 0 6px var(--success);
}

.status-badge.failed {
  background: rgba(255, 23, 68, 0.1);
  color: var(--danger);
}

.status-badge.failed .status-dot {
  background: var(--danger);
  box-shadow: 0 0 6px var(--danger);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Action Buttons */
.action-buttons {
  display: flex;
  gap: 8px;
  justify-content: center;
}

.btn-action {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

/* Pagination */
.pagination-modern {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--divider-color);
}

/* Text Muted */
.text-muted {
  color: var(--text-muted);
}

/* Responsive */
@media (max-width: 1200px) {
  .file-stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .file-stats-grid {
    grid-template-columns: 1fr;
  }
  
  .page-header-modern {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }
  
  .search-input {
    width: 100%;
  }
  
  .card-header {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
}
</style>
