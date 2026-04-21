<template>
  <div class="jobs">
    <!-- Modern Header -->
    <div class="page-header-modern">
      <div class="header-content">
        <div class="header-icon">
          <el-icon><List /></el-icon>
        </div>
        <div class="header-text">
          <h1>任务管理</h1>
          <p class="subtitle">管理 FIBO 本体映射任务</p>
        </div>
      </div>
      <el-button type="primary" class="btn-glow" @click="$router.push('/jobs/new')">
        <el-icon><Plus /></el-icon>
        新建任务
      </el-button>
    </div>

    <!-- Job Stats -->
    <div class="job-stats-grid">
      <div class="stat-card-glass">
        <div class="stat-icon primary">
          <el-icon><List /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ jobs.length }}</span>
          <span class="stat-label">任务总数</span>
        </div>
      </div>
      <div class="stat-card-glass">
        <div class="stat-icon success">
          <el-icon><VideoPlay /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ jobs.filter(j => j.status === 'running').length }}</span>
          <span class="stat-label">运行中</span>
        </div>
      </div>
      <div class="stat-card-glass">
        <div class="stat-icon warning">
          <el-icon><Timer /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ jobs.filter(j => j.status === 'pending').length }}</span>
          <span class="stat-label">待启动</span>
        </div>
      </div>
      <div class="stat-card-glass">
        <div class="stat-icon info">
          <el-icon><CircleCheck /></el-icon>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ jobs.filter(j => j.status === 'completed').length }}</span>
          <span class="stat-label">已完成</span>
        </div>
      </div>
    </div>

    <!-- Job List Card -->
    <div class="job-list-card">
      <div class="card-header">
        <span class="card-title">任务列表</span>
        <el-radio-group v-model="statusFilter" size="small">
          <el-radio-button label="">全部</el-radio-button>
          <el-radio-button label="running">运行中</el-radio-button>
          <el-radio-button label="completed">已完成</el-radio-button>
          <el-radio-button label="failed">失败</el-radio-button>
        </el-radio-group>
      </div>
      
      <el-table :data="filteredJobs" v-loading="loading" class="modern-table">
        <el-table-column prop="id" label="任务ID" width="80" align="center">
          <template #default="{ row }">
            <span class="job-id">#{{ row.id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="name" label="任务名称" min-width="200">
          <template #default="{ row }">
            <div class="job-name">
              <el-icon><Document /></el-icon>
              <span>{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="ddlFileTag" label="DDL源" width="150">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" type="info">{{ row.ddlFileTag }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="ttlFileTag" label="目标本体" width="150">
          <template #default="{ row }">
            <el-tag size="small" effect="plain" type="primary">{{ row.ttlFileTag }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120" align="center">
          <template #default="{ row }">
            <div class="job-status" :class="row.status">
              <span class="status-pulse"></span>
              <span>{{ getStatusText(row.status) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="180">
          <template #default="{ row }">
            <div class="progress-wrapper">
              <el-progress 
                :percentage="row.progress" 
                :status="getProgressStatus(row)"
                :stroke-width="8"
                class="job-progress"
              />
              <span class="progress-text">{{ row.progress }}%</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="180">
          <template #default="{ row }">
            <span class="time-text">{{ row.createdAt }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right" align="center">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button type="primary" size="small" plain class="btn-action" @click="viewJob(row)">
                <el-icon><View /></el-icon>
                查看
              </el-button>
              <el-button
                v-if="row.status === 'running'"
                type="warning"
                size="small"
                class="btn-action"
                @click="pauseJob(row)"
              >
                <el-icon><VideoPause /></el-icon>
                暂停
              </el-button>
              <el-button
                v-if="row.status === 'paused'"
                type="success"
                size="small"
                class="btn-action"
                @click="resumeJob(row)"
              >
                <el-icon><VideoPlay /></el-icon>
                恢复
              </el-button>
              <el-button
                v-if="['running', 'paused'].includes(row.status)"
                type="danger"
                size="small"
                plain
                class="btn-action"
                @click="stopJob(row)"
              >
                <el-icon><CircleClose /></el-icon>
                停止
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
          @size-change="loadJobs"
          @current-change="loadJobs"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { jobsApi } from '@/api'
import type { Job } from '@/types'

const router = useRouter()
const loading = ref(false)
const jobs = ref<Job[]>([])
const statusFilter = ref('')

// Computed
const filteredJobs = computed(() => {
  if (!statusFilter.value) return jobs.value
  return jobs.value.filter(j => j.status === statusFilter.value)
})

const pagination = reactive({
  page: 1,
  pageSize: 10,
  total: 0,
})

const getStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    running: 'primary',
    paused: 'warning',
    completed: 'success',
    failed: 'danger',
    stopped: 'info',
  }
  return map[status] || 'info'
}

const getStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待启动',
    running: '运行中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败',
    stopped: '已停止',
  }
  return map[status] || status
}

const getProgressStatus = (row: Job) => {
  if (row.status === 'completed') return 'success'
  if (row.status === 'failed') return 'exception'
  return undefined
}

const loadJobs = async () => {
  loading.value = true
  try {
    const res = await jobsApi.getJobs({
      page: pagination.page,
      pageSize: pagination.pageSize,
    })
    jobs.value = res.items
    pagination.total = res.total
  } catch (error) {
    ElMessage.error('加载任务列表失败')
  } finally {
    loading.value = false
  }
}

const viewJob = (row: Job) => {
  router.push(`/dashboard/job/${row.id}`)
}

const pauseJob = async (row: Job) => {
  try {
    await jobsApi.pauseJob(row.id)
    ElMessage.success('任务已暂停')
    loadJobs()
  } catch (error) {
    ElMessage.error('暂停失败')
  }
}

const resumeJob = async (row: Job) => {
  try {
    await jobsApi.resumeJob(row.id)
    ElMessage.success('任务已恢复')
    loadJobs()
  } catch (error) {
    ElMessage.error('恢复失败')
  }
}

const stopJob = async (row: Job) => {
  try {
    await jobsApi.stopJob(row.id)
    ElMessage.success('任务已停止')
    loadJobs()
  } catch (error) {
    ElMessage.error('停止失败')
  }
}

onMounted(() => {
  loadJobs()
})
</script>

<style scoped>
.jobs {
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
  background: linear-gradient(135deg, #00d4ff 0%, #00b8d4 100%);
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

/* Job Stats Grid */
.job-stats-grid {
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

.stat-icon.primary {
  background: rgba(102, 126, 234, 0.15);
  color: #667eea;
}

.stat-icon.success {
  background: rgba(0, 200, 83, 0.15);
  color: #00c853;
}

.stat-icon.warning {
  background: rgba(255, 171, 0, 0.15);
  color: #ffab00;
}

.stat-icon.info {
  background: rgba(0, 176, 255, 0.15);
  color: #00b0ff;
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

/* Job List Card */
.job-list-card {
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

/* Job ID */
.job-id {
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 600;
}

/* Job Name */
.job-name {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  font-weight: 500;
}

.job-name .el-icon {
  color: var(--primary-400);
  font-size: 18px;
}

/* Job Status */
.job-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

.status-pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.job-status.pending {
  background: rgba(0, 176, 255, 0.1);
  color: var(--info);
}

.job-status.pending .status-pulse {
  background: var(--info);
  box-shadow: 0 0 6px var(--info);
}

.job-status.running {
  background: rgba(0, 200, 83, 0.1);
  color: var(--success);
}

.job-status.running .status-pulse {
  background: var(--success);
  box-shadow: 0 0 6px var(--success);
  animation: pulse 1.5s infinite;
}

.job-status.paused {
  background: rgba(255, 171, 0, 0.1);
  color: var(--warning);
}

.job-status.paused .status-pulse {
  background: var(--warning);
  box-shadow: 0 0 6px var(--warning);
}

.job-status.completed {
  background: rgba(0, 200, 83, 0.1);
  color: var(--success);
}

.job-status.completed .status-pulse {
  background: var(--success);
  box-shadow: 0 0 6px var(--success);
}

.job-status.failed {
  background: rgba(255, 23, 68, 0.1);
  color: var(--danger);
}

.job-status.failed .status-pulse {
  background: var(--danger);
  box-shadow: 0 0 6px var(--danger);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Progress Wrapper */
.progress-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.job-progress {
  flex: 1;
}

.progress-text {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  min-width: 36px;
}

/* Time Text */
.time-text {
  color: var(--text-muted);
  font-size: 13px;
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

/* Radio Group Override */
:deep(.el-radio-button__inner) {
  background: var(--bg-tertiary);
  border-color: var(--border-color);
  color: var(--text-secondary);
}

:deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) {
  background: var(--primary-500);
  border-color: var(--primary-500);
  color: white;
  box-shadow: -1px 0 0 0 var(--primary-500);
}

/* Responsive */
@media (max-width: 1200px) {
  .job-stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .job-stats-grid {
    grid-template-columns: 1fr;
  }
  
  .page-header-modern {
    flex-direction: column;
    gap: 16px;
    align-items: flex-start;
  }
  
  .card-header {
    flex-direction: column;
    gap: 12px;
    align-items: flex-start;
  }
  
  .progress-wrapper {
    flex-direction: column;
    gap: 4px;
  }
}
</style>
