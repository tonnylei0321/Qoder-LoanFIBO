<template>
  <div class="ddl-files">
    <div class="page-header">
      <h1>DDL 版本管理</h1>
      <el-button type="primary" @click="showUploadDialog = true">
        <el-icon><Upload /></el-icon>
        上传 DDL 文件
      </el-button>
    </div>

    <el-card>
      <el-table :data="files" v-loading="loading" stripe>
        <el-table-column prop="sourceTag" label="版本标签" min-width="180" />
        <el-table-column prop="erpSource" label="ERP来源" width="120" />
        <el-table-column prop="version" label="版本号" width="100" />
        <el-table-column prop="fileSize" label="文件大小" width="120">
          <template #default="{ row }">
            {{ formatFileSize(row.fileSize) }}
          </template>
        </el-table-column>
        <el-table-column prop="tableCount" label="表数量" width="100">
          <template #default="{ row }">
            {{ row.tableCount || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="parseStatus" label="解析状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.parseStatus)" size="small">
              {{ getStatusText(row.parseStatus) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="uploadTime" label="上传时间" width="180" />
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.parseStatus === 'pending'"
              type="primary"
              link
              size="small"
              @click="handleParse(row)"
            >
              解析
            </el-button>
            <el-button type="primary" link size="small" @click="handleView(row)">
              查看
            </el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
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
    </el-card>

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
import { ref, reactive, onMounted } from 'vue'
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

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
