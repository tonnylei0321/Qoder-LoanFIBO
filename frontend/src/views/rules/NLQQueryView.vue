<template>
  <div class="nlq-query-view">
    <div class="page-header">
      <h2 data-testid="nlq-title">自然语言查询</h2>
      <p class="subtitle">使用自然语言提问，系统将自动解析意图并生成查询</p>
    </div>

    <!-- 查询输入区 -->
    <div class="query-input-section">
      <div class="input-row">
        <el-select
          v-model="tenantId"
          placeholder="选择租户"
          class="tenant-select"
          data-testid="nlq-tenant"
        >
          <el-option label="默认租户" value="default" />
          <el-option label="银行A" value="bank_a" />
          <el-option label="银行B" value="bank_b" />
        </el-select>
        <el-input
          v-model="queryText"
          placeholder="输入自然语言查询，例如：查询资产负债率超过60%的企业"
          size="large"
          class="query-input"
          data-testid="nlq-query-input"
          @keyup.enter="handleQuery"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button
          type="primary"
          size="large"
          :loading="querying"
          data-testid="nlq-query-btn"
          @click="handleQuery"
        >
          <el-icon v-if="!querying"><Promotion /></el-icon>
          查询
        </el-button>
      </div>
      <div class="quick-queries">
        <span class="label">快捷查询：</span>
        <el-tag
          v-for="q in quickQueries"
          :key="q"
          class="quick-tag"
          effect="plain"
          @click="queryText = q"
        >
          {{ q }}
        </el-tag>
      </div>
    </div>

    <!-- 查询结果区 -->
    <div v-if="result" class="result-section">
      <!-- 状态横幅 -->
      <div class="status-banner" :class="result.status">
        <el-icon v-if="result.status === 'success'"><CircleCheck /></el-icon>
        <el-icon v-else-if="result.status === 'needs_confirmation'"><Warning /></el-icon>
        <el-icon v-else><CircleClose /></el-icon>
        <span>{{ statusMessage }}</span>
      </div>

      <!-- 确认对话框 -->
      <div v-if="result.status === 'needs_confirmation'" class="confirm-panel">
        <p>系统对查询意图的置信度较低，请确认以下解析是否正确：</p>
        <div class="confirm-detail">
          <div class="detail-item">
            <span class="detail-label">意图：</span>
            <span>{{ result.data?.intent_id || '未识别' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">生成的SQL：</span>
            <code>{{ result.sql }}</code>
          </div>
        </div>
        <div class="confirm-actions">
          <el-button type="primary" data-testid="nlq-confirm-yes" @click="confirmQuery(true)">确认查询</el-button>
          <el-button data-testid="nlq-confirm-no" @click="confirmQuery(false)">取消</el-button>
        </div>
      </div>

      <!-- SQL 展示 -->
      <div v-if="result.sql" class="sql-panel">
        <div class="panel-header">
          <span>生成 SQL</span>
          <el-button text size="small" @click="copySql">
            <el-icon><CopyDocument /></el-icon> 复制
          </el-button>
        </div>
        <pre class="sql-code"><code>{{ result.sql }}</code></pre>
      </div>

      <!-- 数据表格 -->
      <div v-if="result.data?.rows?.length" class="data-panel">
        <div class="panel-header">
          <span>查询结果 ({{ result.data.rows.length }} 条)</span>
          <el-button text size="small" @click="exportData">
            <el-icon><Download /></el-icon> 导出
          </el-button>
        </div>
        <el-table
          :data="result.data.rows"
          stripe
          class="result-table"
          data-testid="nlq-result-table"
        >
          <el-table-column
            v-for="col in result.data.columns"
            :key="col"
            :prop="col"
            :label="col"
            min-width="140"
          />
        </el-table>
      </div>

      <!-- 空结果 -->
      <div v-if="result.status === 'success' && (!result.data?.rows?.length)" class="empty-result">
        <el-empty description="查询结果为空" />
      </div>

      <!-- 管理员告警 -->
      <div v-if="result.admin_alert" class="admin-alert">
        <el-alert type="error" :closable="false" show-icon>
          <template #title>系统异常，需要管理员介入</template>
          {{ result.message }}
        </el-alert>
      </div>
    </div>

    <!-- 历史查询 -->
    <div v-if="queryHistory.length" class="history-section">
      <div class="panel-header">
        <span>查询历史</span>
        <el-button text size="small" @click="queryHistory = []">清空</el-button>
      </div>
      <div class="history-list">
        <div
          v-for="(item, idx) in queryHistory"
          :key="idx"
          class="history-item"
          @click="replayQuery(item)"
        >
          <el-icon><Clock /></el-icon>
          <span class="history-text">{{ item.query }}</span>
          <el-tag size="small" :type="item.status === 'success' ? 'success' : 'warning'">
            {{ item.status === 'success' ? '成功' : '待确认' }}
          </el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { rulesEngineApi, type QueryResponse } from '@/api/rulesEngine'

const tenantId = ref('default')
const queryText = ref('')
const querying = ref(false)
const result = ref<QueryResponse | null>(null)
const queryHistory = ref<Array<{ query: string; status: string; timestamp: number }>>([])

const quickQueries = [
  '查询资产负债率超过60%的企业',
  '最近一年营收增长率最高的前10家企业',
  '流动比率低于1.5的企业名单',
  '查询所有A股上市银行的ROE',
]

const statusMessage = computed(() => {
  if (!result.value) return ''
  const map: Record<string, string> = {
    success: '查询成功',
    needs_confirmation: '需要确认查询意图',
    compiling: '规则编译中，请稍后重试',
    error: '查询失败',
  }
  return map[result.value.status] || result.value.message
})

async function handleQuery() {
  if (!queryText.value.trim()) {
    ElMessage.warning('请输入查询内容')
    return
  }
  querying.value = true
  result.value = null
  try {
    result.value = await rulesEngineApi.query({
      tenant_id: tenantId.value,
      query: queryText.value.trim(),
    })
    queryHistory.value.unshift({
      query: queryText.value.trim(),
      status: result.value.status,
      timestamp: Date.now(),
    })
    if (queryHistory.value.length > 20) {
      queryHistory.value = queryHistory.value.slice(0, 20)
    }
  } catch (e: any) {
    result.value = {
      status: 'error',
      message: e?.message || '查询失败',
      admin_alert: false,
    }
  } finally {
    querying.value = false
  }
}

async function confirmQuery(confirmed: boolean) {
  if (!confirmed) {
    result.value = null
    return
  }
  // Re-query with confirmation context
  querying.value = true
  try {
    result.value = await rulesEngineApi.query({
      tenant_id: tenantId.value,
      query: queryText.value.trim(),
      context: { confirmed: true },
    })
  } catch (e: any) {
    result.value = {
      status: 'error',
      message: e?.message || '查询失败',
      admin_alert: false,
    }
  } finally {
    querying.value = false
  }
}

function copySql() {
  if (result.value?.sql) {
    navigator.clipboard.writeText(result.value.sql)
    ElMessage.success('SQL 已复制到剪贴板')
  }
}

function exportData() {
  if (!result.value?.data?.rows) return
  const cols = result.value.data.columns || []
  const header = cols.join(',')
  const rows = result.value.data.rows.map((r: any) => cols.map((c: string) => r[c] ?? '').join(','))
  const csv = [header, ...rows].join('\n')
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `query_result_${Date.now()}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

function replayQuery(item: { query: string }) {
  queryText.value = item.query
  handleQuery()
}
</script>

<style scoped>
.nlq-query-view {
  max-width: 1200px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 0.9rem;
  margin: 0;
}

/* 输入区 */
.query-input-section {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg, 12px);
  padding: 24px;
  margin-bottom: 24px;
}

.input-row {
  display: flex;
  gap: 12px;
  align-items: center;
}

.tenant-select {
  width: 140px;
  flex-shrink: 0;
}

.query-input {
  flex: 1;
}

.quick-queries {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.quick-queries .label {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.quick-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.quick-tag:hover {
  background: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
}

/* 结果区 */
.result-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.status-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 20px;
  border-radius: var(--radius-md, 8px);
  font-weight: 500;
  font-size: 0.95rem;
}

.status-banner.success {
  background: rgba(82, 196, 26, 0.1);
  color: #52c41a;
  border: 1px solid rgba(82, 196, 26, 0.3);
}

.status-banner.needs_confirmation {
  background: rgba(250, 173, 20, 0.1);
  color: #faad14;
  border: 1px solid rgba(250, 173, 20, 0.3);
}

.status-banner.error {
  background: rgba(255, 77, 79, 0.1);
  color: #ff4d4f;
  border: 1px solid rgba(255, 77, 79, 0.3);
}

.status-banner.compiling {
  background: rgba(24, 144, 255, 0.1);
  color: #1890ff;
  border: 1px solid rgba(24, 144, 255, 0.3);
}

/* 确认面板 */
.confirm-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg, 12px);
  padding: 20px;
}

.confirm-panel p {
  margin: 0 0 16px 0;
  color: var(--text-secondary);
}

.confirm-detail {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.detail-item {
  display: flex;
  gap: 8px;
  align-items: flex-start;
}

.detail-label {
  color: var(--text-muted);
  font-size: 0.85rem;
  min-width: 80px;
}

.detail-item code {
  background: var(--bg-tertiary);
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.85rem;
  color: var(--primary-500);
}

.confirm-actions {
  display: flex;
  gap: 12px;
}

/* SQL 面板 */
.sql-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg, 12px);
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid var(--border-color);
  font-weight: 500;
  color: var(--text-secondary);
}

.sql-code {
  margin: 0;
  padding: 16px 20px;
  background: var(--bg-tertiary);
  overflow-x: auto;
}

.sql-code code {
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  font-size: 0.85rem;
  color: var(--text-primary);
  line-height: 1.6;
}

/* 数据面板 */
.data-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg, 12px);
  overflow: hidden;
}

.result-table {
  margin: 0;
}

.empty-result {
  padding: 40px;
  text-align: center;
}

.admin-alert {
  margin-top: 8px;
}

/* 历史查询 */
.history-section {
  margin-top: 24px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg, 12px);
  overflow: hidden;
}

.history-list {
  padding: 8px 12px;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md, 8px);
  cursor: pointer;
  transition: background 0.2s;
}

.history-item:hover {
  background: var(--bg-tertiary);
}

.history-text {
  flex: 1;
  color: var(--text-secondary);
  font-size: 0.9rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
