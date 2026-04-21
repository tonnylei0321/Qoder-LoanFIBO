<template>
  <div class="dashboard">
    <!-- Header -->
    <div class="dashboard-header">
      <div class="header-title">
        <h1>语义对齐看板</h1>
        <p class="subtitle">FIBO 本体映射智能分析平台</p>
      </div>
      <div class="header-actions">
        <el-button type="primary" class="btn-glow" @click="showNewJobDialog = true">
          <el-icon><Plus /></el-icon>
          新建对齐任务
        </el-button>
        <el-button class="btn-ghost" @click="refreshStats">
          <el-icon><Refresh /></el-icon>
          刷新统计
        </el-button>
      </div>
    </div>

    <!-- Job Info Card -->
    <div v-if="currentJob" class="job-info-glass">
      <div class="job-header">
        <div class="job-title-wrapper">
          <div class="pulse-dot" :class="currentJob.status"></div>
          <span class="job-title">{{ currentJob.name }}</span>
        </div>
        <el-tag :type="getStatusType(currentJob.status)" effect="dark" round>
          {{ getStatusText(currentJob.status) }}
        </el-tag>
      </div>
      <div class="job-source-target">
        <div class="source">
          <div class="icon-box">
            <el-icon><Document /></el-icon>
          </div>
          <div class="source-info">
            <span class="label">源系统</span>
            <span class="value">BIPV5 财务域</span>
          </div>
        </div>
        <div class="flow-arrow">
          <div class="arrow-line"></div>
          <el-icon><ArrowRight /></el-icon>
        </div>
        <div class="target">
          <div class="icon-box target">
            <el-icon><Collection /></el-icon>
          </div>
          <div class="source-info">
            <span class="label">目标本体</span>
            <span class="value">{{ currentJob.ontologyTag || 'FIBO-2025Q4' }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Stats Cards -->
    <div class="stats-grid">
      <div class="stat-card-glass">
        <div class="stat-icon">
          <el-icon><Grid /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-label">总表数</div>
          <div class="stat-value">{{ formatNumber(stats.totalTables) }}</div>
        </div>
        <div class="stat-glow"></div>
      </div>
      <div class="stat-card-glass success">
        <div class="stat-icon">
          <el-icon><CircleCheck /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-label">已映射表</div>
          <div class="stat-value">{{ formatNumber(stats.mappedTables) }}</div>
          <div class="stat-percent" v-if="stats.totalTables">
            <el-progress :percentage="Math.round((stats.mappedTables / stats.totalTables) * 100)" :stroke-width="4" :show-text="false" />
            <span>{{ ((stats.mappedTables / stats.totalTables) * 100).toFixed(1) }}%</span>
          </div>
        </div>
        <div class="stat-glow"></div>
      </div>
      <div class="stat-card-glass">
        <div class="stat-icon">
          <el-icon><List /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-label">总字段数</div>
          <div class="stat-value">{{ formatNumber(stats.totalFields) }}</div>
        </div>
        <div class="stat-glow"></div>
      </div>
      <div class="stat-card-glass success">
        <div class="stat-icon">
          <el-icon><MagicStick /></el-icon>
        </div>
        <div class="stat-content">
          <div class="stat-label">已映射字段</div>
          <div class="stat-value">{{ formatNumber(stats.mappedFields) }}</div>
          <div class="stat-percent" v-if="stats.totalFields">
            <el-progress :percentage="Math.round((stats.mappedFields / stats.totalFields) * 100)" :stroke-width="4" :show-text="false" />
            <span>{{ ((stats.mappedFields / stats.totalFields) * 100).toFixed(1) }}%</span>
          </div>
        </div>
        <div class="stat-glow"></div>
      </div>
    </div>

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

    <!-- Pipeline Nodes (9 Steps) -->
    <el-card class="pipeline-nodes-card">
      <template #header>
        <span>Pipeline 执行节点 (9 Nodes)</span>
      </template>
      <div class="pipeline-flow">
        <div 
          v-for="(node, index) in pipelineNodes" 
          :key="node.key"
          class="pipeline-node"
          :class="[node.status, { active: node.executed }]"
        >
          <div class="node-number">{{ index + 1 }}</div>
          <div class="node-content">
            <div class="node-name">{{ node.name }}</div>
            <div class="node-desc">{{ node.desc }}</div>
            <div class="node-stats" v-if="node.processed > 0">
              已处理: {{ formatNumber(node.processed) }}
            </div>
          </div>
          <el-tag 
            :type="getNodeStatusType(node.status)" 
            size="small"
            class="node-status"
          >
            {{ getNodeStatusText(node.status) }}
          </el-tag>
          <div v-if="index < pipelineNodes.length - 1" class="node-arrow">→</div>
        </div>
      </div>
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
              <el-option label="无法映射" value="unmappable" />
              <el-option label="处理中" value="pending" />
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
        <el-table-column prop="databaseName" label="数据库" width="140" />
        <el-table-column prop="tableName" label="表名" width="180" show-overflow-tooltip />
        <el-table-column prop="tableComment" label="中文名称" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.tableComment" class="table-comment">{{ row.tableComment }}</span>
            <el-tag v-else type="info" size="small">-</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="totalFields" label="字段总数" width="90" align="center" />
        <el-table-column prop="mappedFields" label="已映射" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.mappedFields > 0" type="success" size="small">{{ row.mappedFields }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="unmappedFields" label="未映射" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.unmappedFields > 0" type="danger" size="small">{{ row.unmappedFields }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="映射状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getMappingStatusType(row.status)">
              {{ getMappingStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="fiboClassUri" label="FIBO 类" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.fiboClassUri && row.fiboClassUri !== '-'" class="fibo-uri" :title="row.fiboClassUri">
              {{ row.fiboClassUri.split('/').pop() || row.fiboClassUri }}
            </span>
            <el-tag v-else type="info" size="small">未映射</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="confidenceLevel" label="置信度" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.confidenceLevel" :type="getConfidenceType(row.confidenceLevel)" size="small">
              {{ row.confidenceLevel }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="reviewStatus" label="审核状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getReviewStatusType(row.reviewStatus)" size="small">
              {{ getReviewStatusText(row.reviewStatus) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="handleViewDetail(row)">
              查看详情
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

    <!-- Mapping Detail Drawer -->
    <el-drawer
      v-model="showDetailDialog"
      title="映射详情"
      direction="rtl"
      size="60%"
    >
      <div v-if="selectedMapping" class="mapping-detail">
        <!-- 基本信息 -->
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="数据库">{{ selectedMapping.databaseName }}</el-descriptions-item>
          <el-descriptions-item label="表名">
            <el-text truncated style="max-width:200px">{{ selectedMapping.tableName }}</el-text>
          </el-descriptions-item>
          <el-descriptions-item label="中文名称" :span="2">
            <span v-if="selectedMapping.tableComment" style="font-weight:500">{{ selectedMapping.tableComment }}</span>
            <el-tag v-else type="info" size="small">-</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="映射状态">
            <el-tag :type="getMappingStatusType(selectedMapping.status)">
              {{ getMappingStatusText(selectedMapping.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="审核状态">
            <el-tag :type="getReviewStatusType(selectedMapping.reviewStatus)" size="small">
              {{ getReviewStatusText(selectedMapping.reviewStatus) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="FIBO 类" :span="2">
            <div v-if="selectedMapping.fiboClassUri && selectedMapping.fiboClassUri !== '-'">
              <el-tag type="primary" size="small" style="margin-bottom:4px">
                {{ selectedMapping.fiboClassUri.split('/').pop() }}
              </el-tag>
              <div class="fibo-uri-full">{{ selectedMapping.fiboClassUri }}</div>
            </div>
            <el-tag v-else type="info" size="small">未映射</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="置信度">
            <el-tag v-if="selectedMapping.confidenceLevel" :type="getConfidenceType(selectedMapping.confidenceLevel)" size="small">
              {{ selectedMapping.confidenceLevel }}
            </el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item label="字段统计">
            <el-space>
              <span>{{ selectedMapping.totalFields || 0 }} 个</span>
              <el-tag type="success" size="small">已映射 {{ selectedMapping.mappedFields || 0 }}</el-tag>
              <el-tag type="warning" size="small" v-if="selectedMapping.unmappedFields > 0">未映射 {{ selectedMapping.unmappedFields }}</el-tag>
            </el-space>
          </el-descriptions-item>
          <el-descriptions-item label="修订次数">{{ selectedMapping.revisionCount || 0 }}</el-descriptions-item>
        </el-descriptions>

        <!-- 映射说明 -->
        <div class="detail-section">
          <div class="section-title">映射说明</div>
          <div class="reason-box">{{ selectedMapping.mappingReasonZh || selectedMapping.mappingReason || '暂无映射说明' }}</div>
        </div>

        <!-- 字段列表 -->
        <div class="detail-section" v-if="selectedMapping.parsedFields && selectedMapping.parsedFields.length">
          <div class="section-title">字段列表 ({{ selectedMapping.parsedFields.length }} 个)</div>
          <el-table :data="selectedMapping.parsedFields" size="small" max-height="500" border stripe>
            <el-table-column prop="name" label="字段名" width="140" fixed />
            <el-table-column prop="comment" label="中文名" width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.comment" class="table-comment">{{ row.comment }}</span>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column prop="type" label="类型" width="110" />
            <el-table-column label="FIBO 实体" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">
                <template v-if="row.fibo_entity">
                  <el-tag type="primary" size="small" :title="row.fibo_entity">
                    {{ row.fibo_entity.split('/').pop()?.split('#').pop() || row.fibo_entity }}
                  </el-tag>
                </template>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column label="实体名称" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.fibo_entity_label" class="entity-label">{{ row.fibo_entity_label }}</span>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column label="FIBO 属性" min-width="160" show-overflow-tooltip>
              <template #default="{ row }">
                <template v-if="row.fibo_property">
                  <el-tag
                    :type="getConfidenceType(row.fibo_property_confidence)"
                    size="small"
                    :title="row.fibo_property"
                  >
                    {{ row.fibo_property.split('#').pop()?.split('/').pop() || row.fibo_property }}
                  </el-tag>
                </template>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
            <el-table-column label="属性名称" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.fibo_property_label" class="property-label">{{ row.fibo_property_label }}</span>
                <span v-else class="text-muted">-</span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useJobWebSocket } from '@/composables/useWebSocket'
import { request } from '@/api'
import type { Job, PipelineStats, MappingResult } from '@/types'
import NewJobDialog from './components/NewJobDialog.vue'

const route = useRoute()
const { lastProgress, connect, disconnect } = useJobWebSocket()

// State
const currentJob = ref<(Job & { ontologyTag?: string }) | null>(null)
const stats = reactive<PipelineStats & { pipelineNodes?: Record<string, any> }>({
  totalTables: 0,
  mappedTables: 0,
  totalFields: 0,
  mappedFields: 0,
  stages: {
    ruleMatch: 0,
    vectorSearch: 0,
    llmMapping: 0,
    ignored: 0,
  },
  pipelineNodes: {},
})
const mappingResults = ref<MappingResult[]>([])
const loading = ref(false)
const showNewJobDialog = ref(false)
const showDetailDialog = ref(false)
const selectedMapping = ref<any>(null)
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
    unmappable: 'info',
    pending: 'warning',
    review_required: 'danger',
  }
  return map[status] || 'info'
}

const getMappingStatusText = (status: string) => {
  const map: Record<string, string> = {
    mapped: '已映射',
    unmapped: '未映射',
    unmappable: '无法映射',
    pending: '处理中',
    review_required: '待审核',
  }
  return map[status] || status
}

const getConfidenceType = (level: string) => {
  const map: Record<string, string> = {
    high: 'success',
    HIGH: 'success',
    medium: 'warning',
    MEDIUM: 'warning',
    low: 'danger',
    LOW: 'danger',
    UNRESOLVED: 'info',
  }
  return map[level] || 'info'
}

const getReviewStatusType = (status: string) => {
  const map: Record<string, string> = {
    pending: 'info',
    approved: 'success',
    needs_revision: 'warning',
    rejected: 'danger',
  }
  return map[status] || 'info'
}

const getReviewStatusText = (status: string) => {
  const map: Record<string, string> = {
    pending: '待审核',
    approved: '已通过',
    needs_revision: '需修订',
    rejected: '已拒绝',
  }
  return map[status] || status
}

// Pipeline node definitions
const pipelineNodeDefinitions = [
  { key: 'parse_ddl', name: 'DDL 解析', desc: '解析 DDL 文件，提取表结构' },
  { key: 'index_ttl', name: 'TTL 索引', desc: '构建本体类向量索引' },
  { key: 'fetch_batch', name: '批次获取', desc: '获取待映射表批次' },
  { key: 'retrieve_candidates', name: '候选检索', desc: '向量检索候选本体类' },
  { key: 'mapping_llm', name: 'LLM 映射', desc: '大模型语义映射推理' },
  { key: 'critic', name: '审核评估', desc: '映射质量批量审核' },
  { key: 'check_revision', name: '修订检查', desc: '检查是否需要修订' },
  { key: 'revision', name: '映射修订', desc: '根据反馈修订映射' },
  { key: 'report', name: '报告生成', desc: '生成执行报告' },
]

const pipelineNodes = computed(() => {
  const nodes = stats.pipelineNodes || {}
  return pipelineNodeDefinitions.map(def => {
    const nodeData = nodes[def.key] || { executed: false, processed: 0, status: 'pending' }
    return {
      ...def,
      executed: nodeData.executed,
      processed: nodeData.processed || 0,
      status: nodeData.status || 'pending',
    }
  })
})

const getNodeStatusType = (status: string) => {
  const map: Record<string, string> = {
    completed: 'success',
    running: 'primary',
    pending: 'info',
    failed: 'danger',
  }
  return map[status] || 'info'
}

const getNodeStatusText = (status: string) => {
  const map: Record<string, string> = {
    completed: '已完成',
    running: '运行中',
    pending: '待执行',
    failed: '失败',
  }
  return map[status] || status
}

const refreshStats = async () => {
  try {
    const response = await request.get('/pipeline/stats')
    const data = response as any
    stats.totalTables = data.total_tables || 0
    stats.mappedTables = data.mapped_tables || 0
    stats.totalFields = data.total_fields || 0
    stats.mappedFields = data.mapped_fields || 0
    if (data.stages) {
      stats.stages.ruleMatch = data.stages.rule_match || 0
      stats.stages.vectorSearch = data.stages.vector_search || 0
      stats.stages.llmMapping = data.stages.llm_mapping || 0
      stats.stages.ignored = data.stages.ignored || 0
    }
    if (data.pipeline_nodes) {
      stats.pipelineNodes = data.pipeline_nodes
    }
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
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
  try {
    // Load mappings from table_mapping API
    const response = await request.get('/pipeline/mappings', {
      params: {
        page: pagination.page,
        page_size: pagination.pageSize,
        mapping_status: filterStatus.value || undefined,
      }
    })
    const data = response as any
    
    // Convert mappings to display format
    mappingResults.value = data.items.map((m: any) => ({
      id: m.id,
      databaseName: m.database_name,
      tableName: m.table_name,
      tableComment: m.table_comment || '',
      totalFields: m.total_fields || 0,
      mappedFields: m.mapped_fields || 0,
      unmappedFields: m.unmapped_fields || 0,
      fieldName: '-',
      fieldType: '-',
      status: m.mapping_status,
      fiboClassUri: m.fibo_class_uri || '-',
      fiboPropertyUri: '-',
      confidenceLevel: m.confidence_level,
      mappingReason: m.mapping_reason || '',
      reviewStatus: m.review_status,
      parsedFields: m.parsed_fields || [],
      revisionCount: m.revision_count,
    }))
    pagination.total = data.total || 0
  } catch (error) {
    console.error('Failed to load mappings:', error)
  } finally {
    loading.value = false
  }
}

const handleViewDetail = (row: MappingResult) => {
  selectedMapping.value = row
  showDetailDialog.value = true
}

const onJobCreated = (job: Job) => {
  currentJob.value = job
  showNewJobDialog.value = false
  // Connect WebSocket
  connect(job.id)
}

// Lifecycle
onMounted(() => {
  refreshStats()
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

/* Modern Dashboard Header */
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header-title h1 {
  margin: 0 0 4px 0;
  font-size: 28px;
  font-weight: 700;
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.subtitle {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.btn-glow {
  background: var(--gradient-primary) !important;
  border: none !important;
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
  transition: all 0.3s ease;
}

.btn-glow:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
}

.btn-ghost {
  background: var(--bg-tertiary) !important;
  border: 1px solid var(--border-color) !important;
  color: var(--text-secondary) !important;
}

.btn-ghost:hover {
  background: var(--bg-elevated) !important;
  color: var(--text-primary) !important;
}

/* Glass Job Info Card */
.job-info-glass {
  background: var(--card-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  padding: 20px 24px;
  margin-bottom: 24px;
  box-shadow: var(--glass-shadow);
}

.job-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.job-title-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pulse-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 0 0 rgba(0, 200, 83, 0.7);
  animation: pulse-dot 2s infinite;
}

.pulse-dot.running {
  background: var(--warning);
  box-shadow: 0 0 0 0 rgba(255, 171, 0, 0.7);
}

.pulse-dot.pending {
  background: var(--info);
  box-shadow: 0 0 0 0 rgba(0, 176, 255, 0.7);
}

@keyframes pulse-dot {
  0% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(0, 200, 83, 0.7);
  }
  70% {
    transform: scale(1);
    box-shadow: 0 0 0 10px rgba(0, 200, 83, 0);
  }
  100% {
    transform: scale(0.95);
    box-shadow: 0 0 0 0 rgba(0, 200, 83, 0);
  }
}

.job-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.job-source-target {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 16px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
}

.source, .target {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.icon-box {
  width: 48px;
  height: 48px;
  background: var(--gradient-primary);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 24px;
}

.icon-box.target {
  background: var(--gradient-accent);
}

.source-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.source-info .label {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.source-info .value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.flow-arrow {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  color: var(--text-muted);
}

.arrow-line {
  width: 2px;
  height: 20px;
  background: linear-gradient(to bottom, var(--primary-500), var(--accent-cyan));
  border-radius: 1px;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-bottom: 24px;
}

.stat-card-glass {
  position: relative;
  background: var(--card-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  overflow: hidden;
  transition: all 0.3s ease;
}

.stat-card-glass:hover {
  transform: translateY(-4px);
  border-color: rgba(102, 126, 234, 0.3);
}

.stat-card-glass.success {
  border-color: rgba(0, 200, 83, 0.2);
}

.stat-card-glass.success .stat-icon {
  background: rgba(0, 200, 83, 0.15);
  color: var(--success);
}

.stat-glow {
  position: absolute;
  top: -50%;
  right: -50%;
  width: 100%;
  height: 100%;
  background: radial-gradient(circle, rgba(102, 126, 234, 0.1) 0%, transparent 70%);
  pointer-events: none;
}

.stat-icon {
  width: 56px;
  height: 56px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: var(--primary-400);
  flex-shrink: 0;
}

.stat-content {
  flex: 1;
}

.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.stat-percent {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.stat-percent .el-progress {
  flex: 1;
}

.stat-percent span {
  font-size: 13px;
  font-weight: 600;
  color: var(--success);
  white-space: nowrap;
}

@media (max-width: 1200px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .job-source-target {
    flex-direction: column;
    gap: 16px;
  }
  
  .flow-arrow {
    transform: rotate(90deg);
  }
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
  color: var(--primary-400, #40a9ff);
  font-weight: 500;
}

.progress-detail {
  display: flex;
  justify-content: space-between;
  margin-top: 12px;
  color: var(--text-secondary, #9ca3af);
  font-size: 14px;
}

.hint {
  color: var(--text-muted, #4b5563);
  font-style: italic;
}

/* Pipeline Nodes Styles - Dark Theme Compatible */
.pipeline-nodes-card {
  margin-bottom: 20px;
}

.pipeline-flow {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 10px 0;
}

.pipeline-node {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--radius-md, 8px);
  background: var(--bg-tertiary, #1f2937);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  transition: all 0.3s;
  flex: 1;
  min-width: 200px;
  max-width: 300px;
  position: relative;
}

.pipeline-node.active {
  border-color: var(--primary-400, #40a9ff);
  background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%);
}

.pipeline-node.completed {
  border-color: var(--success, #00c853);
  background: rgba(0, 200, 83, 0.05);
}

.pipeline-node.running {
  border-color: var(--warning, #ffab00);
  background: rgba(255, 171, 0, 0.05);
  animation: node-pulse 2s infinite;
}

.pipeline-node.failed {
  border-color: var(--danger, #ff1744);
  background: rgba(255, 23, 68, 0.05);
}

@keyframes node-pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(255, 171, 0, 0.2);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(255, 171, 0, 0);
  }
}

.node-number {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--bg-elevated, #243447);
  color: var(--text-secondary, #9ca3af);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
  transition: all 0.3s ease;
}

.pipeline-node.active .node-number {
  background: var(--gradient-primary, linear-gradient(135deg, #667eea 0%, #764ba2 100%));
  color: white;
}

.pipeline-node.completed .node-number {
  background: var(--success, #00c853);
  color: white;
}

.pipeline-node.running .node-number {
  background: var(--warning, #ffab00);
  color: white;
}

.pipeline-node.failed .node-number {
  background: var(--danger, #ff1744);
  color: white;
}

.node-content {
  flex: 1;
  min-width: 0;
}

.node-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #ffffff);
  margin-bottom: 4px;
}

.node-desc {
  font-size: 12px;
  color: var(--text-secondary, #9ca3af);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-stats {
  font-size: 12px;
  color: var(--primary-400, #40a9ff);
  margin-top: 4px;
  font-weight: 500;
}

.node-status {
  flex-shrink: 0;
}

.node-arrow {
  position: absolute;
  right: -18px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted, #4b5563);
  font-size: 16px;
  font-weight: bold;
  z-index: 1;
}

.fibo-uri {
  font-size: 12px;
  color: var(--primary-400, #40a9ff);
  word-break: break-all;
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
}

@media (max-width: 1200px) {
  .node-arrow {
    display: none;
  }
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

/* 详情抽屉样式 */
.mapping-detail {
  padding: 4px 0;
}

.detail-section {
  margin-top: 20px;
}

.section-title {
  margin: 0 0 10px 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #ffffff);
  padding-bottom: 8px;
  border-bottom: 1px solid var(--divider-color, rgba(255, 255, 255, 0.06));
}

.reason-box {
  background: var(--bg-tertiary, #1f2937);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  border-radius: var(--radius-md, 12px);
  padding: 10px 12px;
  font-size: 13px;
  color: var(--text-secondary, #9ca3af);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

.fibo-uri-full {
  font-size: 11px;
  color: var(--text-muted, #4b5563);
  word-break: break-all;
  margin-top: 2px;
}

.ddl-preview {
  background-color: var(--bg-tertiary, #1f2937);
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.1));
  border-radius: 4px;
  padding: 12px;
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-primary, #ffffff);
  max-height: 200px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.table-comment {
  color: var(--text-secondary, #9ca3af);
  font-size: 13px;
}

.text-muted {
  color: var(--text-muted, #4b5563);
  font-size: 12px;
}
</style>
