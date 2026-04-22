<template>
  <div class="audit-version">
    <el-tabs v-model="activeTab">
      <!-- 审计日志 -->
      <el-tab-pane label="审计日志" name="audit">
        <div class="filter-bar">
          <el-date-picker
            v-model="dateRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            format="YYYY-MM-DD HH:mm"
            value-format="YYYY-MM-DDTHH:mm:ssZ"
          />
          <el-button type="primary" @click="fetchAuditLogs" :loading="auditLoading">查询</el-button>
        </div>

        <el-alert
          v-if="auditOverflow"
          type="error"
          title="AUDIT_OVERFLOW: 日志超过 1000 条，请缩小查询范围"
          show-icon
          :closable="false"
          style="margin-bottom: 16px"
        />

        <el-timeline>
          <el-timeline-item
            v-for="log in auditLogs"
            :key="log.id"
            :timestamp="formatTime(log.created_at)"
            placement="top"
          >
            <el-card shadow="never">
              <div class="log-content">
                <el-tag size="small" type="info">{{ log.action }}</el-tag>
                <span class="log-operator">操作人: {{ log.operator }}</span>
                <span class="log-ip">IP: {{ log.ip }}</span>
              </div>
              <div class="log-detail" v-if="log.detail && Object.keys(log.detail).length">
                {{ JSON.stringify(log.detail) }}
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>

        <el-empty v-if="!auditLoading && auditLogs.length === 0" description="暂无审计日志" />
      </el-tab-pane>

      <!-- 版本管理 -->
      <el-tab-pane label="版本管理" name="version">
        <div class="filter-bar">
          <el-button type="primary" @click="showVersionDialog = true">上传新版本</el-button>
        </div>

        <el-table :data="versions" v-loading="versionLoading" stripe>
          <el-table-column prop="version" label="版本号" width="120" />
          <el-table-column prop="platform" label="平台" width="100" />
          <el-table-column prop="download_url" label="下载链接" />
          <el-table-column prop="min_version" label="最低版本" width="120" />
          <el-table-column prop="created_at" label="上传时间" width="180">
            <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
          </el-table-column>
        </el-table>

        <!-- 版本上传对话框 -->
        <el-dialog v-model="showVersionDialog" title="上传代理版本" width="500px">
          <el-form :model="versionForm" label-width="100px">
            <el-form-item label="版本号">
              <el-input v-model="versionForm.version" placeholder="如：1.2.0" />
            </el-form-item>
            <el-form-item label="平台">
              <el-select v-model="versionForm.platform">
                <el-option label="Windows" value="windows" />
                <el-option label="Linux" value="linux" />
              </el-select>
            </el-form-item>
            <el-form-item label="下载链接">
              <el-input v-model="versionForm.download_url" placeholder="https://..." />
            </el-form-item>
            <el-form-item label="最低版本">
              <el-input v-model="versionForm.min_version" placeholder="如：1.0.0" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showVersionDialog = false">取消</el-button>
            <el-button type="primary" @click="handleUploadVersion" :loading="uploading">上传</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { agentApi } from '@/api/agent'

const activeTab = ref('audit')

// 审计日志
const auditLoading = ref(false)
const auditLogs = ref<any[]>([])
const auditOverflow = ref(false)
const dateRange = ref<[string, string] | null>(null)

// 版本管理
const versionLoading = ref(false)
const versions = ref<any[]>([])
const showVersionDialog = ref(false)
const uploading = ref(false)
const versionForm = ref({
  version: '',
  platform: 'linux',
  download_url: '',
  min_version: '1.0.0',
})

const fetchAuditLogs = async () => {
  auditLoading.value = true
  try {
    const params: any = { limit: 100 }
    if (dateRange.value) {
      params.start = dateRange.value[0]
      params.end = dateRange.value[1]
    }
    const result = (await agentApi.getAuditLogs(params)) as any
    auditLogs.value = result.data || result || []
    auditOverflow.value = result.overflow || false
  } catch (e) {
    // ignore
  } finally {
    auditLoading.value = false
  }
}

const fetchVersions = async () => {
  versionLoading.value = true
  try {
    const data = (await agentApi.getVersions()) as unknown as any[]
    versions.value = data
  } catch (e) {
    // ignore
  } finally {
    versionLoading.value = false
  }
}

const handleUploadVersion = async () => {
  if (!versionForm.value.version || !versionForm.value.download_url) {
    ElMessage.warning('请填写版本号和下载链接')
    return
  }
  uploading.value = true
  try {
    await agentApi.uploadVersion(versionForm.value)
    ElMessage.success('版本上传成功')
    showVersionDialog.value = false
    versionForm.value = { version: '', platform: 'linux', download_url: '', min_version: '1.0.0' }
    await fetchVersions()
  } catch (e) {
    // error handled by interceptor
  } finally {
    uploading.value = false
  }
}

const formatTime = (iso: string) => {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchAuditLogs()
  fetchVersions()
})
</script>

<style scoped>
.audit-version {
  padding: 20px;
}
.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  align-items: center;
}
.log-content {
  display: flex;
  gap: 12px;
  align-items: center;
}
.log-operator, .log-ip {
  font-size: 13px;
  color: #666;
}
.log-detail {
  margin-top: 8px;
  font-size: 12px;
  color: #999;
  font-family: monospace;
}
</style>
