<template>
  <div class="dashboard">
    <!-- Header -->
    <div class="dashboard-header">
      <h1>语义对齐看板</h1>
      <div class="header-actions">
        <el-button type="primary" @click="showNewJobDialog = true">
          <el-icon><Plus /></el-icon>
          新建对齐任务
        </el-button>
        <el-button @click="refreshStats">
          <el-icon><Refresh /></el-icon>
          刷新统计
        </el-button>
      </div>
    </div>

    <!-- Job Info Card -->
    <el-card v-if="currentJob" class="job-info-card">
      <template #header>
        <div class="job-header">
          <span class="job-title">{{ currentJob.name }}</span>
          <el-tag :type="getStatusType(currentJob.status)">
            {{ getStatusText(currentJob.status) }}
          </el-tag>
        </div>
      </template>
      <div class="job-source-target">
        <div class="source">
          <el-icon><Document /></el-icon>
          <span>源系统：{{ currentJob.ddlFileTag }}</span>
        </div>
        <el-icon class="arrow"><ArrowRight /></el-icon>
        <div class="target">
          <el-icon><Collection /></el-icon>
          <span>目标本体：{{ currentJob.ttlFileTag }}</span>
        </div>
      </div>
    </el-card>

    <!-- Stats Cards -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">总表数</div>
          <div class="stat-value">{{ formatNumber(stats.totalTables) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">已映射表</div>
          <div class="stat-value success">{{ formatNumber(stats.mappedTables) }}</div>
          <div class="stat-percent" v-if="stats.totalTables">
            {{ ((stats.mappedTables / stats.totalTables) * 100).toFixed(1) }}%
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">总字段数</div>
          <div class="stat-value">{{ formatNumber(stats.totalFields) }}</div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-label">已映射字段</div>
          <div class="stat-value success">{{ formatNumber(stats.mappedFields) }}</div>
          <div class="stat-percent" v-if="stats.totalFields">
            {{ ((stats.mappedFields / stats.totalFields) * 100).toFixed(1) }}%
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- Progress Section -->
    <el-card v-if="currentJob?.status === 'running'" class="progress-card">
      <template #header>
        <div class="progress-header">
          <span>正在执行全量智能对齐（规则引擎 + LLM）...</span>
          <span class="progress-numbers">
            {{ formatNumber(progress.processedFields) }} / {{ formatNumber(progress.totalFields) }} 字段
            ({{ progress.percentage }}%)
          </span>
        </div>
      </template>
      <el-progress
        :percentage="progress.percentage"
        :stroke-width="20"
        :status="progress.status"
      />
      <div class="progress-detail">
        <span>当前已成功新增映射字段: {{ formatNumber(stats.mappedFields) }}</span>
        <span class="hint">大表已自动切片，请耐心等待...</span>
      </div>
    </el-card>

    <!-- Pipeline Stages -->
    <el-card class="pipeline-card">
      <template #header>
        <span>对齐流水线 (4 Stages Pipeline)</span>
      </template>
      <el-row :gutter="16">
        <el-col :span="6">
          <div class="stage-box tier-0">
            <div class="stage-title">规则与启发式 (RULE MATCH)</div>
            <div class="stage-count">{{ stats.stages?.ruleMatch || 0 }}</div>
            <el-tag size="small" type="info">Tier 0</el-tag>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stage-box tier-1">
            <div class="stage-title">向量引擎检索 (VECTOR/FAISS)</div>
            <div class="stage-count">{{ stats.stages?.vectorSearch || 0 }}</div>
            <el-tag size="small" type="warning">Tier 1 & 2</el-tag>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stage-box tier-3">
            <div class="stage-title">大模型深度推理 (LLM / AI)</div>
            <div class="stage-count">{{ stats.stages?.llmMapping || 0 }}</div>
            <el-tag size="small" type="danger">Tier 3</el-tag>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stage-box bypass">
            <div class="stage-title">静默拦截/黑名单 (IGNORED)</div>
            <div class="stage-count">{{ stats.stages?.ignored || 0 }}</div>
            <el-tag size="small">Bypass</el-tag>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- Mapping Results Table -->
    <el-card class="results-card">
      <template #header>
        <div class="results-header">
          <span>映射结果明细</span>
          <div class="filters">
            <el-select v-model="filterStatus" placeholder="状态筛选" clearable style="width: 120px">
              <el-option label="全部" value="" />
              <el-option label="已映射" value="mapped" />
              <el-option label="未映射" value="unmapped" />
              <el-option label="待审核" value="review_required" />
            </el-select>
            <el-input
              v-model="searchKeyword"
              placeholder="搜索表名/字段名"
              style="width: 200px"
              clearable
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
          </div>
        </div>
      </template>
      <el-table :data="mappingResults" v-loading="loading" stripe>
        <el-table-column prop="databaseName" label="数据库" width="150" />
        <el-table-column prop="tableName" label="表名" width="180" />
        <el-table-column prop="fieldName" label="字段名" width="180" />
        <el-table-column prop="fieldType" label="字段类型" width="120" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getMappingStatusType(row.status)">
              {{ getMappingStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="fiboClassUri" label="FIBO 类" min-width="200" show-overflow-tooltip />
        <el-table-column prop="fiboPropertyUri" label="FIBO 属性" min-width="200" show-overflow-tooltip />
        <el-table-column prop="confidenceLevel" label="置信度" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.confidenceLevel" :type="getConfidenceType(row.confidenceLevel)">
              {{ row.confidenceLevel }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleEdit(row)">
              人工指定
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.pageSize"
          :total="pagination.total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- New Job Dialog -->
    <NewJobDialog v-model="showNewJobDialog" @success="onJobCreated" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useJobWebSocket } from '@/composables/useWebSocket'
import type { Job, PipelineStats, MappingResult } from '@/types'
import NewJobDialog from './components/NewJobDialog.vue'

const route = useRoute()
const { lastProgress, connect, disconnect } = useJobWebSocket()

// State
const currentJob = ref<Job | null>(null)
const stats = reactive<PipelineStats>({
  totalTables: 13548,
  mappedTables: 0,
  totalFields: 1001483,
  mappedFields: 25011,
  stages: {
    ruleMatch: 0,
    vectorSearch: 0,
    llmMapping: 0,
    ignored: 0,
  },
})
const mappingResults = ref<MappingResult[]>([])
const loading = ref(false)
const showNewJobDialog = ref(false)
const filterStatus = ref('')
const searchKeyword = ref('')
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

// Computed
const progress = computed(() => {
  const processed = lastProgress.value?.processedFields || stats.mappedFields
  const total = lastProgress.value?.totalFields || stats.totalFields
  const percentage = total > 0 ? Math.round((processed / total) * 100) : 0
  return {
    processedFields: processed,
    totalFields: total,
    percentage,
    status: percentage >= 100 ? 'success' : undefined,
  }
})

// Methods
const formatNumber = (num: number) => {
  return num?.toLocaleString() || '0'
}

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

const getMappingStatusType = (status: string) => {
  const map: Record<string, string> = {
    mapped: 'success',
    unmapped: 'info',
    pending: 'warning',
    review_required: 'danger',
  }
  return map[status] || 'info'
}

const getMappingStatusText = (status: string) => {
  const map: Record<string, string> = {
    mapped: '已映射',
    unmapped: '未映射',
    pending: '处理中',
    review_required: '待审核',
  }
  return map[status] || status
}

const getConfidenceType = (level: string) => {
  const map: Record<string, string> = {
    high: 'success',
    medium: 'warning',
    low: 'danger',
  }
  return map[level] || 'info'
}

const refreshStats = async () => {
  // TODO: Call API
  console.log('Refreshing stats...')
}

const handleSizeChange = (size: number) => {
  pagination.pageSize = size
  loadMappingResults()
}

const handlePageChange = (page: number) => {
  pagination.page = page
  loadMappingResults()
}

const loadMappingResults = async () => {
  loading.value = true
  // TODO: Call API
  // Mock data
  mappingResults.value = [
    {
      id: 1,
      databaseName: 'ctmfa',
      tableName: 'aa_billcondition',
      fieldName: 'cconditionvalue',
      fieldType: 'varchar(255)',
      status: 'unmapped',
      reviewStatus: 'pending',
    },
    {
      id: 2,
      databaseName: 'ctmfa',
      tableName: 'aa_billcondition',
      fieldName: 'operator',
      fieldType: 'varchar(50)',
      status: 'unmapped',
      reviewStatus: 'pending',
    },
  ]
  pagination.total = 2
  loading.value = false
}

const handleEdit = (row: MappingResult) => {
  console.log('Edit mapping:', row)
}

const onJobCreated = (job: Job) => {
  currentJob.value = job
  showNewJobDialog.value = false
  // Connect WebSocket
  connect(job.id)
}

// Lifecycle
onMounted(() => {
  loadMappingResults()
  // Check if viewing specific job
  const jobId = route.params.id as string
  if (jobId) {
    // TODO: Load job details
    connect(parseInt(jobId))
  }
})
</script>

<style scoped>
.dashboard {
  padding-bottom: 40px;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.dashboard-header h1 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.job-info-card {
  margin-bottom: 20px;
}

.job-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.job-title {
  font-size: 16px;
  font-weight: 500;
}

.job-source-target {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 10px 0;
}

.source, .target {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  background-color: #f5f7fa;
  border-radius: 4px;
}

.arrow {
  font-size: 20px;
  color: #909399;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
  padding: 20px;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.stat-value {
  font-size: 32px;
  font-weight: 600;
  color: #303133;
}

.stat-value.success {
  color: #67c23a;
}

.stat-percent {
  font-size: 14px;
  color: #67c23a;
  margin-top: 4px;
}

.progress-card {
  margin-bottom: 20px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-numbers {
  color: #409EFF;
  font-weight: 500;
}

.progress-detail {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
  color: #606266;
  font-size: 14px;
}

.hint {
  color: #909399;
}

.pipeline-card {
  margin-bottom: 20px;
}

.stage-box {
  padding: 20px;
  border-radius: 8px;
  text-align: center;
  background-color: #f5f7fa;
}

.stage-box.tier-0 {
  background-color: #ecf5ff;
}

.stage-box.tier-1 {
  background-color: #fdf6ec;
}

.stage-box.tier-3 {
  background-color: #fef0f0;
}

.stage-box.bypass {
  background-color: #f4f4f5;
}

.stage-title {
  font-size: 12px;
  color: #606266;
  margin-bottom: 12px;
}

.stage-count {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.results-card {
  margin-bottom: 20px;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filters {
  display: flex;
  gap: 12px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 20px;
}
</style>
