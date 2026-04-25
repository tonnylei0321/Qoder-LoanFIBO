<template>
  <div class="agent-status">
    <div class="page-header">
      <h2>代理连接状态</h2>
      <div class="header-actions">
        <el-button type="primary" @click="handleCollect" :loading="collectLoading" size="small">
          手动采集
        </el-button>
        <el-button @click="fetchStatus" :loading="statusLoading" size="small">刷新状态</el-button>
        <el-button @click="fetchTraces" :loading="traceLoading" size="small">刷新记录</el-button>
      </div>
    </div>

    <!-- 磁贴区 -->
    <div class="tile-zone" v-if="agents.length > 0">
      <div class="tile-card" v-for="agent in agents" :key="agent.org_id + agent.datasource">
        <!-- 头部：企业名 + 状态 -->
        <div class="tile-head">
          <span class="tile-org">{{ getOrgName(agent.org_id) }}</span>
          <span class="tile-badge" :class="'badge-' + agent.status.toLowerCase()">
            {{ statusLabel(agent.status) }}
          </span>
        </div>
        <!-- 磁贴网格 -->
        <div class="tile-grid">
          <div class="tile-cell">
            <div class="tile-val">{{ agent.datasource }}</div>
            <div class="tile-key">数据源</div>
          </div>
          <div class="tile-cell">
            <div class="tile-val mono">{{ agent.ip }}</div>
            <div class="tile-key">IP 地址</div>
          </div>
          <div class="tile-cell">
            <div class="tile-val">{{ agent.version || '-' }}</div>
            <div class="tile-key">代理版本</div>
          </div>
          <div class="tile-cell">
            <div class="tile-val">{{ formatTime(agent.connected_at) }}</div>
            <div class="tile-key">建链时间</div>
          </div>
          <div class="tile-cell">
            <div class="tile-val">{{ formatTime(agent.last_seen) }}</div>
            <div class="tile-key">最后心跳</div>
          </div>
          <div class="tile-cell accent">
            <div class="tile-val big">{{ agent.total_tasks }}</div>
            <div class="tile-key">通讯次数</div>
          </div>
          <div class="tile-cell ok">
            <div class="tile-val big">{{ agent.success_tasks }}</div>
            <div class="tile-key">成功</div>
          </div>
          <div class="tile-cell err">
            <div class="tile-val big">{{ agent.fail_tasks }}</div>
            <div class="tile-key">失败</div>
          </div>
          <div class="tile-cell" :class="rateCellClass(agent.success_rate)">
            <div class="tile-val big">{{ agent.success_rate }}%</div>
            <div class="tile-key">成功率</div>
          </div>
        </div>
      </div>
    </div>

    <el-empty v-if="!statusLoading && agents.length === 0" description="暂无在线代理" />

    <!-- 通讯记录表格 -->
    <div class="trace-section">
      <div class="section-header">
        <h3>通讯记录</h3>
        <div class="trace-filters">
          <el-input v-model="traceFilter.org_id" placeholder="企业ID" clearable size="small" style="width: 200px" @change="fetchTraces" />
          <el-select v-model="traceFilter.status" placeholder="状态筛选" clearable size="small" style="width: 140px" @change="fetchTraces">
            <el-option label="已完成" value="COMPLETED" />
            <el-option label="错误" value="ERROR" />
            <el-option label="代理不可达" value="AGENT_UNREACHABLE" />
            <el-option label="等待中" value="PENDING" />
            <el-option label="超时" value="TASK_TIMEOUT" />
          </el-select>
        </div>
      </div>

      <el-table :data="traces" v-loading="traceLoading" stripe style="width: 100%" size="small">
        <el-table-column label="时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="企业" min-width="140">
          <template #default="{ row }">{{ getOrgName(row.org_id) }}</template>
        </el-table-column>
        <el-table-column prop="action" label="动作" width="150" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <span class="trace-status" :class="'ts-' + row.status.toLowerCase()">
              {{ traceStatusLabel(row.status) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="耗时" width="90" align="right">
          <template #default="{ row }">
            <span v-if="row.duration_ms > 0">{{ row.duration_ms }}ms</span>
            <span v-else style="color: var(--el-text-color-placeholder)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="请求概要" min-width="160">
          <template #default="{ row }">
            <span v-if="row.request_summary" class="mono-sm">
              {{ row.request_summary.action }}
              <span v-if="row.request_summary.sql_hint" class="sql-hint">SQL</span>
            </span>
            <span v-else style="color: var(--el-text-color-placeholder)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="响应概要" min-width="140">
          <template #default="{ row }">
            <span v-if="row.response_summary">
              <template v-if="row.response_summary.error">
                <span class="error-text">{{ row.response_summary.error }}</span>
              </template>
              <template v-else>
                <span class="mono-sm">{{ row.response_summary.data_keys?.join(', ') || '-' }}</span>
              </template>
            </span>
            <span v-else style="color: var(--el-text-color-placeholder)">-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="showTraceDetail(row.trace_id)">报文详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="trace-pagination" v-if="traceTotal > traceFilter.limit">
        <el-pagination
          v-model:current-page="tracePage"
          :page-size="traceFilter.limit"
          :total="traceTotal"
          layout="total, prev, pager, next"
          size="small"
          @current-change="onPageChange"
        />
      </div>
    </div>

    <!-- 报文详情弹窗 -->
    <el-dialog v-model="detailVisible" title="通讯报文详情" width="800px" destroy-on-close>
      <div v-if="detailLoading" style="text-align: center; padding: 40px">
        <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      </div>
      <div v-else-if="traceDetail" class="trace-detail">
        <div class="detail-meta">
          <el-descriptions :column="3" size="small" border>
            <el-descriptions-item label="Trace ID">
              <span class="mono-sm">{{ traceDetail.trace_id }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="动作">{{ traceDetail.action }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <span class="trace-status" :class="'ts-' + traceDetail.status.toLowerCase()">
                {{ traceStatusLabel(traceDetail.status) }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item label="数据源">{{ traceDetail.datasource }}</el-descriptions-item>
            <el-descriptions-item label="耗时">
              <span v-if="traceDetail.duration_ms > 0">{{ traceDetail.duration_ms }}ms</span>
              <span v-else>-</span>
            </el-descriptions-item>
            <el-descriptions-item label="创建时间">{{ formatTime(traceDetail.created_at) }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- 全链 Span 时间线 -->
        <h4 class="detail-section-title">全链追踪</h4>
        <div class="span-timeline">
          <div v-for="(span, idx) in traceDetail.spans" :key="idx" class="span-item">
            <div class="span-dot" :class="spanDotClass(span.event)"></div>
            <div class="span-content">
              <div class="span-header">
                <span class="span-node">{{ span.node }}</span>
                <span class="span-event">{{ spanEventLabel(span.event) }}</span>
                <span class="span-ts">{{ formatTime(span.ts) }}</span>
              </div>
              <div class="span-detail" v-if="span.detail && Object.keys(span.detail).length > 0">
                <!-- 请求报文 -->
                <div v-if="span.detail.request" class="msg-block">
                  <div class="msg-label">请求报文</div>
                  <pre class="msg-code">{{ formatJson(span.detail.request) }}</pre>
                </div>
                <!-- 返回报文 -->
                <div v-if="span.detail.response" class="msg-block">
                  <div class="msg-label">返回报文</div>
                  <pre class="msg-code">{{ formatJson(span.detail.response) }}</pre>
                </div>
                <!-- 其他 detail 字段 -->
                <div v-if="!span.detail.request && !span.detail.response" class="msg-block">
                  <pre class="msg-code meta-code">{{ formatJson(span.detail) }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div v-else style="text-align: center; padding: 40px; color: var(--el-text-color-secondary)">未找到记录</div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { agentApi } from '@/api/agent'
import { Loading } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface AgentInfo {
  org_id: string
  datasource: string
  status: string
  version: string
  ip: string
  last_seen: string
  connected_at: string
  total_tasks: number
  success_tasks: number
  fail_tasks: number
  success_rate: number
}

interface TraceInfo {
  trace_id: string
  org_id: string
  datasource: string
  action: string
  status: string
  duration_ms: number
  created_at: string
  request_summary: { action: string; sql_hint: string } | null
  response_summary: { data_keys?: string[]; row_count?: any; error?: string } | null
}

interface TraceDetail {
  trace_id: string
  org_id: string
  datasource: string
  action: string
  status: string
  spans: Array<{ node: string; event: string; ts: string; detail: Record<string, any> }>
  duration_ms: number
  created_at: string
}

interface OrgInfo {
  org_id: string
  name: string
  security_id_masked?: string
}

const statusLoading = ref(false)
const traceLoading = ref(false)
const collectLoading = ref(false)
const agents = ref<AgentInfo[]>([])
const traces = ref<TraceInfo[]>([])
const traceTotal = ref(0)
const tracePage = ref(1)
const orgMap = ref<Map<string, OrgInfo>>(new Map())

const traceFilter = ref<{ org_id: string; status: string; limit: number }>({
  org_id: '',
  status: '',
  limit: 20,
})

// 报文详情
const detailVisible = ref(false)
const detailLoading = ref(false)
const traceDetail = ref<TraceDetail | null>(null)

let pollTimer: ReturnType<typeof setInterval> | null = null

const fetchStatus = async () => {
  statusLoading.value = true
  try {
    const res = (await agentApi.getAgentStatus()) as any
    // 拦截器解包：无分页字段时直接返回数组
    agents.value = Array.isArray(res) ? res : (res?.data || [])
  } catch (e) {
    // ignore
  } finally {
    statusLoading.value = false
  }
}

const fetchOrgs = async () => {
  try {
    const result = (await agentApi.listOrgs()) as any
    const orgs: OrgInfo[] = Array.isArray(result) ? result : (result?.data || [])
    const map = new Map<string, OrgInfo>()
    for (const org of orgs) {
      map.set(org.org_id, org)
    }
    orgMap.value = map
  } catch (e) {
    // ignore
  }
}

const fetchTraces = async () => {
  traceLoading.value = true
  try {
    const params: any = {
      limit: traceFilter.value.limit,
      offset: (tracePage.value - 1) * traceFilter.value.limit,
    }
    if (traceFilter.value.org_id) params.org_id = traceFilter.value.org_id
    if (traceFilter.value.status) params.status = traceFilter.value.status
    const res = await agentApi.getTraces(params) as any
    // 拦截器解包后：有分页时返回 { data: [...], total: N }，否则直接返回数组
    if (res && typeof res === 'object' && !Array.isArray(res) && 'data' in res) {
      traces.value = res.data || []
      traceTotal.value = res.total || 0
    } else if (Array.isArray(res)) {
      traces.value = res
      traceTotal.value = res.length
    } else {
      traces.value = []
    }
  } catch (e) {
    // ignore
  } finally {
    traceLoading.value = false
  }
}

const onPageChange = (page: number) => {
  tracePage.value = page
  fetchTraces()
}

const handleCollect = async () => {
  collectLoading.value = true
  try {
    await agentApi.triggerCollect()
    // 采集完成后刷新通讯记录
    await fetchTraces()
    ElMessage.success('采集任务已触发')
  } catch (e: any) {
    ElMessage.error(e?.message || '采集触发失败')
  } finally {
    collectLoading.value = false
  }
}

const showTraceDetail = async (traceId: string) => {
  detailVisible.value = true
  detailLoading.value = true
  traceDetail.value = null
  try {
    const res = (await agentApi.getTraceDetail(traceId)) as any
    traceDetail.value = (res && typeof res === 'object' && !Array.isArray(res) && 'data' in res) ? res.data : (Array.isArray(res) ? null : res)
  } catch (e) {
    // ignore
  } finally {
    detailLoading.value = false
  }
}

const getOrgName = (orgId: string): string => {
  return orgMap.value.get(orgId)?.name || orgId.slice(0, 8) + '...'
}

const statusLabel = (status: string) => {
  const map: Record<string, string> = {
    ONLINE: '在线', DEGRADED: '降级', OFFLINE: '离线',
  }
  return map[status] || status
}

const traceStatusLabel = (status: string) => {
  const map: Record<string, string> = {
    COMPLETED: '已完成', ERROR: '错误', AGENT_UNREACHABLE: '代理不可达',
    TASK_TIMEOUT: '超时', PENDING: '等待中', DISPATCHED: '已派发',
    EXECUTING: '执行中', DATASOURCE_OFFLINE: '数据源离线', SERVICE_OVERLOAD: '服务过载',
  }
  return map[status] || status
}

const traceStatusType = (status: string) => {
  switch (status) {
    case 'COMPLETED': return 'success'
    case 'ERROR': return 'danger'
    case 'AGENT_UNREACHABLE': return 'warning'
    case 'TASK_TIMEOUT': return 'warning'
    case 'PENDING': return 'info'
    default: return 'info'
  }
}

const rateClass = (rate: number) => {
  if (rate >= 80) return 'rate-good'
  if (rate >= 50) return 'rate-warn'
  return 'rate-bad'
}

const rateCellClass = (rate: number) => {
  if (rate >= 80) return 'ok'
  if (rate >= 50) return 'warn'
  return 'err'
}

const spanDotClass = (event: string) => {
  if (event.includes('error') || event.includes('failed')) return 'dot-error'
  if (event.includes('result') || event === 'ack_received') return 'dot-success'
  return 'dot-normal'
}

const spanEventLabel = (event: string) => {
  const map: Record<string, string> = {
    trace_created: '链路创建',
    task_dispatched: '任务下发',
    ack_received: '代理确认',
    result_received: '结果返回',
    error_received: '错误返回',
    push_failed: '推送失败',
  }
  return map[event] || event
}

const formatTime = (iso: string) => {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

const formatJson = (obj: any) => {
  try {
    return JSON.stringify(obj, null, 2)
  } catch {
    return String(obj)
  }
}

onMounted(() => {
  fetchOrgs()
  fetchStatus()
  fetchTraces()
  // 10 秒轮询刷新状态
  pollTimer = setInterval(fetchStatus, 10000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<style scoped>
.agent-status {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.page-header h2 {
  margin: 0;
  font-size: 18px;
}
.header-actions {
  display: flex;
  gap: 8px;
}

/* 磁贴区 */
.tile-zone {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 12px;
}
.tile-card {
  background: var(--el-bg-color-overlay);
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  padding: 16px 20px 14px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
}
.tile-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.tile-org {
  font-size: 16px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}
.tile-badge {
  display: inline-block;
  padding: 3px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.5px;
}
.badge-online  { background: #e8f5e9; color: #2e7d32; }
.badge-degraded { background: #fff3e0; color: #e65100; }
.badge-offline  { background: #ffebee; color: #c62828; }

.tile-grid {
  display: grid;
  grid-template-columns: repeat(9, 1fr);
  gap: 1px;
  background: var(--el-border-color-extra-light, #f0f0f0);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
}
.tile-cell {
  background: var(--el-bg-color);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: background 0.15s;
}
.tile-cell:hover {
  background: var(--el-fill-color-lighter);
}
.tile-val {
  font-size: 13px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  line-height: 1.3;
}
.tile-val.mono {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
}
.tile-val.big {
  font-size: 22px;
  font-weight: 800;
  line-height: 1.1;
}
.tile-key {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  letter-spacing: 0.3px;
}

/* 磁贴单元格色彩 */
.tile-cell.accent .tile-val.big { color: var(--el-color-primary); }
.tile-cell.ok .tile-val.big    { color: var(--el-color-success); }
.tile-cell.err .tile-val.big   { color: var(--el-color-danger); }
.tile-cell.warn .tile-val.big  { color: var(--el-color-warning); }

/* 通讯记录 */
.trace-section {
  margin-top: 0;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.section-header h3 {
  margin: 0;
  font-size: 15px;
}
.trace-filters {
  display: flex;
  gap: 8px;
}
.trace-pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.mono-sm {
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
}
.sql-hint {
  display: inline-block;
  background: var(--el-color-warning-light-7);
  color: var(--el-color-warning-dark-2);
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 3px;
  margin-left: 4px;
  font-weight: 600;
}
.error-text {
  color: var(--el-color-danger);
  font-size: 12px;
}

/* 通讯状态标签 */
.trace-status {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
}
.ts-completed         { background: #e8f5e9; color: #2e7d32; }
.ts-error             { background: #ffebee; color: #c62828; }
.ts-agent_unreachable { background: #fff3e0; color: #e65100; }
.ts-task_timeout      { background: #fff3e0; color: #e65100; }
.ts-pending           { background: #e3f2fd; color: #1565c0; }
.ts-dispatched        { background: #f3e5f5; color: #6a1b9a; }
.ts-executing         { background: #e0f2f1; color: #00695c; }

/* 报文详情弹窗 */
.trace-detail {
  max-height: 70vh;
  overflow-y: auto;
}
.detail-meta {
  margin-bottom: 16px;
}
.detail-section-title {
  font-size: 14px;
  font-weight: 600;
  margin: 16px 0 12px;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

/* Span 时间线 */
.span-timeline {
  padding-left: 8px;
}
.span-item {
  display: flex;
  gap: 12px;
  margin-bottom: 4px;
  position: relative;
}
.span-item:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 14px;
  bottom: -4px;
  width: 2px;
  background: var(--el-border-color-lighter);
}
.span-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-top: 4px;
  flex-shrink: 0;
}
.dot-normal { background: var(--el-color-primary-light-3); }
.dot-success { background: var(--el-color-success); }
.dot-error { background: var(--el-color-danger); }
.span-content {
  flex: 1;
  min-width: 0;
}
.span-header {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  margin-bottom: 4px;
}
.span-node {
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.span-event {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.span-ts {
  color: var(--el-text-color-placeholder);
  font-size: 11px;
  margin-left: auto;
  font-family: 'Menlo', monospace;
}
.span-detail {
  margin-bottom: 8px;
}
.msg-block {
  margin-bottom: 6px;
}
.msg-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.msg-code {
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  padding: 10px 12px;
  font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  max-height: 300px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
.meta-code {
  max-height: 80px;
}
</style>
