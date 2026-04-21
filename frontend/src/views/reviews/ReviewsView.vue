<template>
  <div class="reviews-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-title">
        <h1>稽核管理</h1>
        <p class="subtitle">人工审核语义对齐结果，处理 Critic 和 Revision 阶段产生的待确认项</p>
      </div>
      <div class="header-stats">
        <div class="stat-card">
          <span class="stat-num">{{ stats.pending }}</span>
          <span class="stat-label">待审核</span>
        </div>
        <div class="stat-card">
          <span class="stat-num">{{ stats.approved }}</span>
          <span class="stat-label">已通过</span>
        </div>
        <div class="stat-card">
          <span class="stat-num">{{ stats.rejected }}</span>
          <span class="stat-label">已驳回</span>
        </div>
      </div>
    </div>

    <!-- Filter Bar -->
    <div class="filter-bar">
      <el-select v-model="filterDatabase" placeholder="选择数据库" clearable @change="handleFilterChange">
        <el-option label="全部数据库" value="" />
        <el-option v-for="db in databases" :key="db" :label="db" :value="db" />
      </el-select>
      <el-input v-model="searchTable" placeholder="搜索表名..." clearable @input="handleSearch" style="width: 240px">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <!-- Review Tabs -->
    <el-card class="review-card">
      <el-tabs v-model="activeTab" @tab-change="handleTabChange">
        <el-tab-pane label="待审核" name="pending">
          <el-table :data="filteredReviews" v-loading="loading" stripe>
            <el-table-column prop="database_name" label="数据库" width="120" />
            <el-table-column prop="table_name" label="表名" width="180" />
            <el-table-column label="FIBO 映射" min-width="280">
              <template #default="{ row }">
                <div class="mapping-info">
                  <div class="fibo-class">
                    <el-tag size="small" type="info" v-if="row.fibo_class_uri">
                      {{ extractFiboLabel(row.fibo_class_uri) }}
                    </el-tag>
                    <el-tag size="small" type="warning" v-else>未映射</el-tag>
                  </div>
                  <div class="confidence">
                    <el-tag size="small" :type="getConfidenceType(row.confidence_level)">
                      {{ row.confidence_level || 'low' }}
                    </el-tag>
                    <span class="model-tag" v-if="row.model_used">{{ row.model_used }}</span>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="审核意见" min-width="200">
              <template #default="{ row }">
                <div class="review-comments">
                  <div v-for="rev in row.reviews.slice(0, 2)" :key="rev.id" class="comment-item">
                    <el-tag size="small" :type="getSeverityType(rev.severity)">{{ rev.issue_type }}</el-tag>
                    <span class="comment-text" :title="rev.issue_description">
                      {{ truncate(rev.issue_description, 30) }}
                    </span>
                  </div>
                  <el-tag v-if="row.reviews.length > 2" size="small" type="info">+{{ row.reviews.length - 2 }}</el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="openDetail(row)">
                  <el-icon><View /></el-icon> 查看详情
                </el-button>
                <el-button type="success" link size="small" @click="handleApprove(row)">
                  <el-icon><Check /></el-icon> 通过
                </el-button>
                <el-button type="danger" link size="small" @click="handleReject(row)">
                  <el-icon><Close /></el-icon> 驳回
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="已审核" name="completed">
          <el-table :data="filteredReviews" v-loading="loading" stripe>
            <el-table-column prop="database_name" label="数据库" width="120" />
            <el-table-column prop="table_name" label="表名" width="180" />
            <el-table-column label="FIBO 映射" min-width="280">
              <template #default="{ row }">
                <div class="mapping-info">
                  <el-tag size="small" :type="row.review_status === 'approved' ? 'success' : 'danger'">
                    {{ row.review_status === 'approved' ? '已通过' : '已驳回' }}
                  </el-tag>
                  <div class="fibo-class" v-if="row.fibo_class_uri">
                    {{ extractFiboLabel(row.fibo_class_uri) }}
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="updated_at" label="审核时间" width="160">
              <template #default="{ row }">
                {{ formatDate(row.updated_at) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button type="primary" link size="small" @click="openDetail(row)">查看</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>

      <!-- Pagination -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <!-- Detail Drawer -->
    <el-drawer v-model="drawerVisible" :title="`审核详情: ${currentItem?.table_name}`" size="600px">
      <div v-if="currentItem" class="detail-content">
        <!-- Table Info -->
        <div class="detail-section">
          <h3>表信息</h3>
          <el-descriptions :column="2" border>
            <el-descriptions-item label="数据库">{{ currentItem.database_name }}</el-descriptions-item>
            <el-descriptions-item label="表名">{{ currentItem.table_name }}</el-descriptions-item>
            <el-descriptions-item label="映射状态">
              <el-tag :type="getMappingStatusType(currentItem.mapping_status)">{{ currentItem.mapping_status }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="置信度">
              <el-tag :type="getConfidenceType(currentItem.confidence_level)">{{ currentItem.confidence_level }}</el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- Current Mapping -->
        <div class="detail-section">
          <h3>当前 FIBO 映射</h3>
          <div class="mapping-edit">
            <el-input v-model="editableFiboUri" placeholder="FIBO Class URI">
              <template #prepend>fibo:</template>
            </el-input>
            <div class="mapping-reason" v-if="currentItem.mapping_reason">
              <label>映射理由:</label>
              <p>{{ currentItem.mapping_reason }}</p>
            </div>
          </div>
        </div>

        <!-- Review Comments -->
        <div class="detail-section" v-if="currentItem.reviews.length > 0">
          <h3>审核意见 ({{ currentItem.reviews.length }})</h3>
          <div class="review-list">
            <div v-for="rev in currentItem.reviews" :key="rev.id" class="review-item" :class="rev.severity">
              <div class="review-header">
                <el-tag size="small" :type="getSeverityType(rev.severity)">{{ rev.severity }}</el-tag>
                <span class="issue-type">{{ rev.issue_type }}</span>
                <el-tag v-if="rev.is_must_fix" size="small" type="danger" effect="dark">必须修复</el-tag>
              </div>
              <p class="review-desc">{{ rev.issue_description }}</p>
              <p v-if="rev.suggested_fix" class="review-suggest">
                <strong>建议:</strong> {{ rev.suggested_fix }}
              </p>
            </div>
          </div>
        </div>

        <!-- Field Mappings -->
        <div class="detail-section" v-if="currentItem.field_mappings.length > 0">
          <h3>字段映射 ({{ currentItem.field_mappings.length }})</h3>
          <el-table :data="currentItem.field_mappings" size="small">
            <el-table-column prop="field_name" label="字段名" width="120" />
            <el-table-column prop="field_type" label="类型" width="100" />
            <el-table-column prop="fibo_property_uri" label="FIBO 属性" min-width="200">
              <template #default="{ row }">
                <span v-if="row.fibo_property_uri" class="fibo-prop">{{ extractFiboLabel(row.fibo_property_uri) }}</span>
                <el-tag v-else size="small" type="info">未映射</el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- Review Comment Input -->
        <div class="detail-section" v-if="activeTab === 'pending'">
          <h3>审核备注</h3>
          <el-input
            v-model="reviewComment"
            type="textarea"
            :rows="3"
            placeholder="输入审核意见（可选）..."
          />
        </div>

        <!-- Actions -->
        <div class="detail-actions" v-if="activeTab === 'pending'">
          <el-button type="success" size="large" @click="submitApprove">
            <el-icon><Check /></el-icon> 审核通过
          </el-button>
          <el-button type="danger" size="large" @click="submitReject">
            <el-icon><Close /></el-icon> 驳回修改
          </el-button>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { reviewsApi, type ReviewItem } from '@/api/reviews'
import { Search, View, Check, Close } from '@element-plus/icons-vue'

const loading = ref(false)
const activeTab = ref<'pending' | 'completed'>('pending')
const reviews = ref<ReviewItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const filterDatabase = ref('')
const searchTable = ref('')
const databases = ref<string[]>([])

// Stats
const stats = computed(() => ({
  pending: reviews.value.filter(r => r.review_status === 'pending').length,
  approved: reviews.value.filter(r => r.review_status === 'approved').length,
  rejected: reviews.value.filter(r => r.review_status === 'rejected').length,
}))

// Filtered reviews (client-side search)
const filteredReviews = computed(() => {
  let result = reviews.value
  if (searchTable.value) {
    const kw = searchTable.value.toLowerCase()
    result = result.filter(r => r.table_name.toLowerCase().includes(kw))
  }
  return result
})

// Detail drawer
const drawerVisible = ref(false)
const currentItem = ref<ReviewItem | null>(null)
const editableFiboUri = ref('')
const reviewComment = ref('')

const loadReviews = async () => {
  loading.value = true
  try {
    const res = await reviewsApi.getReviews({
      review_status: activeTab.value,
      database: filterDatabase.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    reviews.value = res.items
    total.value = res.total
    // Collect unique databases for filter
    const dbs = new Set<string>()
    res.items.forEach(item => dbs.add(item.database_name))
    databases.value = Array.from(dbs).sort()
  } catch (err) {
    ElMessage.error('加载审核列表失败')
  } finally {
    loading.value = false
  }
}

const handleTabChange = () => {
  page.value = 1
  loadReviews()
}

const handleFilterChange = () => {
  page.value = 1
  loadReviews()
}

const handleSearch = () => {
  // Client-side filter, no need to reload
}

const handleSizeChange = (val: number) => {
  pageSize.value = val
  loadReviews()
}

const handlePageChange = (val: number) => {
  page.value = val
  loadReviews()
}

const openDetail = (row: ReviewItem) => {
  currentItem.value = row
  editableFiboUri.value = row.fibo_class_uri || ''
  reviewComment.value = ''
  drawerVisible.value = true
}

const handleApprove = async (row: ReviewItem) => {
  try {
    await ElMessageBox.confirm(`确认通过 "${row.table_name}" 的映射？`, '审核确认', {
      confirmButtonText: '通过',
      cancelButtonText: '取消',
      type: 'success',
    })
    await reviewsApi.submitReview(row.id, { action: 'approve' })
    ElMessage.success('审核通过')
    loadReviews()
  } catch {
    // Cancelled
  }
}

const handleReject = async (row: ReviewItem) => {
  try {
    await ElMessageBox.confirm(`确认驳回 "${row.table_name}" 的映射？`, '审核确认', {
      confirmButtonText: '驳回',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await reviewsApi.submitReview(row.id, { action: 'reject' })
    ElMessage.info('已驳回')
    loadReviews()
  } catch {
    // Cancelled
  }
}

const submitApprove = async () => {
  if (!currentItem.value) return
  try {
    await reviewsApi.submitReview(currentItem.value.id, {
      action: 'approve',
      comment: reviewComment.value,
      new_fibo_class_uri: editableFiboUri.value || undefined,
    })
    ElMessage.success('审核通过')
    drawerVisible.value = false
    loadReviews()
  } catch {
    ElMessage.error('提交失败')
  }
}

const submitReject = async () => {
  if (!currentItem.value) return
  try {
    await reviewsApi.submitReview(currentItem.value.id, {
      action: 'reject',
      comment: reviewComment.value,
      new_fibo_class_uri: editableFiboUri.value || undefined,
    })
    ElMessage.info('已驳回')
    drawerVisible.value = false
    loadReviews()
  } catch {
    ElMessage.error('提交失败')
  }
}

// Helpers
const extractFiboLabel = (uri: string) => {
  if (!uri) return '-'
  const parts = uri.split('#')
  return parts[parts.length - 1] || uri
}

const getConfidenceType = (level?: string | null) => {
  const map: Record<string, string> = { high: 'success', medium: 'warning', low: 'danger' }
  return map[level || 'low'] || 'info'
}

const getSeverityType = (severity: string) => {
  const map: Record<string, string> = { high: 'danger', medium: 'warning', low: 'info' }
  return map[severity] || 'info'
}

const getMappingStatusType = (status: string) => {
  const map: Record<string, string> = { mapped: 'success', unmappable: 'danger', pending: 'info' }
  return map[status] || 'info'
}

const truncate = (text: string, len: number) => {
  if (!text) return ''
  return text.length > len ? text.slice(0, len) + '...' : text
}

const formatDate = (iso?: string | null) => {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(loadReviews)
</script>

<style scoped>
.reviews-page {
  padding: 24px;
  max-width: 1400px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.header-title h1 {
  margin: 0 0 8px;
  font-size: 1.5rem;
  color: var(--page-title-color);
}

.subtitle {
  margin: 0;
  color: var(--page-desc-color);
  font-size: 0.9rem;
}

.header-stats {
  display: flex;
  gap: 16px;
}

.stat-card {
  background: var(--card-bg-subtle);
  border: 1px solid var(--card-border);
  border-radius: 12px;
  padding: 16px 24px;
  text-align: center;
  min-width: 100px;
}

.stat-num {
  display: block;
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--score-number-color);
}

.stat-label {
  font-size: 0.8rem;
  color: var(--stat-label-color);
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.review-card {
  background: var(--card-bg-subtle);
}

.mapping-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.fibo-class {
  font-weight: 500;
}

.confidence {
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-tag {
  font-size: 0.75rem;
  color: var(--text-muted);
  background: var(--bg-tertiary);
  padding: 2px 8px;
  border-radius: 4px;
}

.review-comments {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.comment-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.comment-text {
  font-size: 0.85rem;
  color: var(--suggestion-text-color);
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--card-border);
}

/* Detail Drawer */
.detail-content {
  padding: 8px;
}

.detail-section {
  margin-bottom: 24px;
}

.detail-section h3 {
  margin: 0 0 12px;
  font-size: 1rem;
  color: var(--page-title-color);
  border-left: 4px solid #667eea;
  padding-left: 12px;
}

.mapping-edit {
  background: var(--bg-tertiary);
  padding: 16px;
  border-radius: 8px;
}

.mapping-reason {
  margin-top: 12px;
}

.mapping-reason label {
  font-size: 0.8rem;
  color: var(--card-title-color);
}

.mapping-reason p {
  margin: 4px 0 0;
  font-size: 0.9rem;
  color: var(--suggestion-text-color);
  line-height: 1.6;
}

.review-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.review-item {
  background: var(--bg-tertiary);
  border-radius: 8px;
  padding: 12px;
  border-left: 4px solid var(--border-color);
}

.review-item.high { border-left-color: #ef4444; }
.review-item.medium { border-left-color: #f59e0b; }
.review-item.low { border-left-color: #3b82f6; }

.review-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.issue-type {
  font-weight: 500;
  color: var(--text-primary);
}

.review-desc {
  margin: 0 0 8px;
  font-size: 0.9rem;
  color: var(--suggestion-text-color);
  line-height: 1.5;
}

.review-suggest {
  margin: 0;
  font-size: 0.85rem;
  color: var(--text-secondary);
  background: var(--bg-primary);
  padding: 8px;
  border-radius: 4px;
}

.fibo-prop {
  color: #667eea;
  font-family: 'Fira Code', monospace;
  font-size: 0.85rem;
}

.detail-actions {
  display: flex;
  gap: 12px;
  padding-top: 16px;
  border-top: 1px solid var(--card-border);
}

.detail-actions .el-button {
  flex: 1;
}
</style>
