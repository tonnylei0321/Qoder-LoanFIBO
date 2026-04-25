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
          <p class="subtitle">TTL 本体文件上传、语法检核与版本管理</p>
        </div>
      </div>
      <div class="header-actions">
        <el-select v-model="statusFilter" placeholder="状态筛选" clearable style="width: 130px" @change="loadVersions">
          <el-option label="草稿" value="draft" />
          <el-option label="已发布" value="published" />
          <el-option label="已同步" value="synced" />
        </el-select>
        <el-button type="primary" class="btn-glow" @click="showUploadDialog = true">
          <el-icon><Upload /></el-icon>
          上传 TTL
        </el-button>
        <el-button @click="loadVersions" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
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
          <span class="stat-value">{{ versions.filter(v => v.status === 'published' || v.status === 'synced').length }}</span>
          <span class="stat-label">已发布</span>
        </div>
      </div>
      <div class="stat-card-glass">
        <div class="stat-icon" :class="versions.some(v => v.ttl_valid === false) ? 'danger' : 'success'">
          <el-icon><DocumentChecked /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ versions.filter(v => v.ttl_valid === false).length }}</span>
          <span class="stat-label">语法异常</span>
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
        <el-table-column prop="ttl_file_name" label="TTL 文件" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.ttl_file_name" class="file-name">{{ row.ttl_file_name }}</span>
            <span v-else class="no-file">未上传</span>
          </template>
        </el-table-column>
        <el-table-column label="文件大小" width="100">
          <template #default="{ row }">
            {{ row.ttl_file_size ? formatFileSize(row.ttl_file_size) : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="语法检核" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.ttl_valid === true" type="success" effect="dark" round size="small">通过</el-tag>
            <el-tag v-else-if="row.ttl_valid === false" type="danger" effect="dark" round size="small">失败</el-tag>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="class_count" label="类" width="70">
          <template #default="{ row }">{{ row.class_count ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="property_count" label="属性" width="70">
          <template #default="{ row }">{{ row.property_count ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" effect="dark" round size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="140" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="viewDetail(row)">详情</el-button>
            <el-button
              v-if="row.status === 'draft'"
              type="success"
              size="small"
              @click="handlePublish(row)"
            >发布</el-button>
            <el-button
              v-if="row.status === 'draft' && row.ttl_valid === false"
              type="danger"
              size="small"
              @click="handleDelete(row)"
            >删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Upload Dialog -->
    <el-dialog v-model="showUploadDialog" title="上传 TTL 文件" width="560px" :close-on-click-modal="false">
      <el-form :model="uploadForm" label-width="100px">
        <el-form-item label="版本标签" required>
          <el-input v-model="uploadForm.version_tag" placeholder="如 v1.0.0" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="uploadForm.description" type="textarea" :rows="2" placeholder="版本描述" />
        </el-form-item>
        <el-form-item label="创建者">
          <el-input v-model="uploadForm.created_by" placeholder="如: admin" />
        </el-form-item>
        <el-form-item label="TTL 文件" required>
          <el-upload
            ref="uploadRef"
            action="#"
            :auto-upload="false"
            :on-change="handleFileChange"
            :limit="1"
            accept=".ttl,.rdf"
          >
            <el-button type="primary">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">支持 .ttl 或 .rdf 格式，上传后自动检核语法</div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <!-- Upload Result -->
      <div v-if="uploadResult" class="upload-result" :class="uploadResult.ttl_valid ? 'result-ok' : 'result-err'">
        <div class="result-header">
          <el-icon :size="18"><template v-if="uploadResult.ttl_valid"><CircleCheck /></template><template v-else><CircleClose /></template></el-icon>
          <span>{{ uploadResult.ttl_valid ? '语法检核通过' : '语法检核失败' }}</span>
        </div>
        <div v-if="uploadResult.ttl_valid" class="result-stats">
          <span>类: {{ uploadResult.class_count }}</span>
          <span>属性: {{ uploadResult.property_count }}</span>
          <span>大小: {{ formatFileSize(uploadResult.ttl_file_size!) }}</span>
        </div>
        <div v-if="!uploadResult.ttl_valid && uploadResult.ttl_validation_msg" class="result-error">
          {{ uploadResult.ttl_validation_msg }}
        </div>
      </div>
      <template #footer>
        <el-button @click="closeUploadDialog">取消</el-button>
        <el-button type="primary" @click="handleUpload" :loading="uploading">上传</el-button>
      </template>
    </el-dialog>

    <!-- Detail Drawer -->
    <el-drawer v-model="showDetail" title="版本详情" size="500px">
      <template v-if="detailData">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="版本标签">{{ detailData.version_tag }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusTagType(detailData.status)" effect="dark" round size="small">
              {{ statusLabel(detailData.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="TTL 文件">{{ detailData.ttl_file_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="文件大小">{{ detailData.ttl_file_size ? formatFileSize(detailData.ttl_file_size) : '-' }}</el-descriptions-item>
          <el-descriptions-item label="语法检核">
            <el-tag v-if="detailData.ttl_valid === true" type="success" size="small">通过</el-tag>
            <el-tag v-else-if="detailData.ttl_valid === false" type="danger" size="small">失败</el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item v-if="detailData.ttl_validation_msg" label="检核信息">
            <span class="validation-msg">{{ detailData.ttl_validation_msg }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="类数量">{{ detailData.class_count ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="属性数量">{{ detailData.property_count ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="描述">{{ detailData.description || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建者">{{ detailData.created_by || '-' }}</el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ formatTime(detailData.created_at) }}</el-descriptions-item>
          <el-descriptions-item label="发布时间">{{ formatTime(detailData.published_at) }}</el-descriptions-item>
          <el-descriptions-item label="同步时间">{{ formatTime(detailData.synced_at) }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { graphdbSyncApi, type SyncVersion, type VersionCreateForm } from '@/api/graphdbSync'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { UploadInstance, UploadFile } from 'element-plus'

const loading = ref(false)
const versions = ref<SyncVersion[]>([])
const showUploadDialog = ref(false)
const uploading = ref(false)
const uploadRef = ref<UploadInstance>()
const selectedFile = ref<File | null>(null)
const uploadResult = ref<SyncVersion | null>(null)
const showDetail = ref(false)
const detailData = ref<SyncVersion | null>(null)

const uploadForm = ref<{ version_tag: string; description: string; created_by: string }>({
  version_tag: '',
  description: '',
  created_by: '',
})
const statusFilter = ref<string>('')

function formatTime(iso?: string | null): string {
  if (!iso) return '-'
  try { return new Date(iso).toLocaleString('zh-CN') } catch { return iso }
}

function formatFileSize(size: number): string {
  if (size < 1024) return size + ' B'
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB'
  return (size / (1024 * 1024)).toFixed(1) + ' MB'
}

function statusTagType(s: string): string {
  if (s === 'synced') return 'success'
  if (s === 'published') return ''
  if (s === 'draft') return 'warning'
  if (s === 'failed') return 'danger'
  return 'info'
}

function statusLabel(s: string): string {
  const map: Record<string, string> = { draft: '草稿', published: '已发布', synced: '已同步', failed: '失败' }
  return map[s] || s
}

async function loadVersions() {
  loading.value = true
  try {
    const params: { status_filter?: string; limit?: number; offset?: number } = {}
    if (statusFilter.value) params.status_filter = statusFilter.value
    versions.value = await graphdbSyncApi.listVersions(params)
  } catch {
    ElMessage.error('加载版本列表失败')
  } finally {
    loading.value = false
  }
}

function handleFileChange(uploadFile: UploadFile) {
  selectedFile.value = uploadFile.raw || null
}

function closeUploadDialog() {
  showUploadDialog.value = false
  uploadResult.value = null
  selectedFile.value = null
  uploadRef.value?.clearFiles()
}

async function handleUpload() {
  if (!selectedFile.value) {
    ElMessage.warning('请选择文件')
    return
  }
  if (!uploadForm.value.version_tag.trim()) {
    ElMessage.warning('请输入版本标签')
    return
  }
  uploading.value = true
  const formData = new FormData()
  formData.append('file', selectedFile.value)
  formData.append('version_tag', uploadForm.value.version_tag)
  if (uploadForm.value.description) formData.append('description', uploadForm.value.description)
  if (uploadForm.value.created_by) formData.append('created_by', uploadForm.value.created_by)

  try {
    const result = await graphdbSyncApi.uploadVersionTTL(formData)
    uploadResult.value = result
    if (result.ttl_valid) {
      ElMessage.success('TTL 文件上传成功，语法检核通过')
    } else {
      ElMessage.warning('TTL 文件已上传，但语法检核失败')
    }
    await loadVersions()
  } catch {
    ElMessage.error('上传失败')
  } finally {
    uploading.value = false
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
  } catch { /* cancelled */ }
}

async function handleDelete(version: SyncVersion) {
  try {
    await ElMessageBox.confirm(`确定要删除版本 ${version.version_tag} 吗？`, '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await graphdbSyncApi.deleteVersion(version.id)
    ElMessage.success('版本已删除')
    await loadVersions()
  } catch { /* cancelled */ }
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

.stats-grid {
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
.stat-icon.warning { background: rgba(245, 158, 11, 0.15); color: #f59e0b; }
.stat-icon.success { background: rgba(16, 185, 129, 0.15); color: #10b981; }
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

.file-name {
  font-family: 'Fira Code', monospace;
  font-size: 0.82rem;
}

.no-file {
  color: var(--text-muted);
  font-size: 0.82rem;
}

.text-muted {
  color: var(--text-muted);
}

.validation-msg {
  font-family: 'Fira Code', monospace;
  font-size: 0.75rem;
  color: #ef4444;
  word-break: break-all;
}

.upload-result {
  margin-top: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 0.85rem;
}

.result-ok {
  background: rgba(16, 185, 129, 0.08);
  border: 1px solid rgba(16, 185, 129, 0.25);
  color: #10b981;
}

.result-err {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.25);
  color: #ef4444;
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  margin-bottom: 8px;
}

.result-stats {
  display: flex;
  gap: 16px;
  font-size: 0.82rem;
}

.result-error {
  font-family: 'Fira Code', monospace;
  font-size: 0.75rem;
  max-height: 80px;
  overflow-y: auto;
  word-break: break-all;
}
</style>
