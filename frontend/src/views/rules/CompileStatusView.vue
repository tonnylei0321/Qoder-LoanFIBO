<template>
  <div class="compile-status-view">
    <div class="page-header">
      <h2 data-testid="compile-title">编译状态看板</h2>
      <el-button
        :loading="refreshing"
        data-testid="compile-refresh-btn"
        @click="refreshAll"
      >
        <el-icon><Refresh /></el-icon> 刷新状态
      </el-button>
    </div>

    <!-- 概览统计 -->
    <div class="stats-row">
      <div class="stat-card completed">
        <div class="stat-icon"><el-icon><CircleCheck /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ stats.completed }}</div>
          <div class="stat-label">已编译</div>
        </div>
      </div>
      <div class="stat-card compiling">
        <div class="stat-icon"><el-icon><Loading /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ stats.compiling }}</div>
          <div class="stat-label">编译中</div>
        </div>
      </div>
      <div class="stat-card failed">
        <div class="stat-icon"><el-icon><CircleClose /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ stats.failed }}</div>
          <div class="stat-label">失败</div>
        </div>
      </div>
      <div class="stat-card never">
        <div class="stat-icon"><el-icon><Clock /></el-icon></div>
        <div class="stat-body">
          <div class="stat-value">{{ stats.never }}</div>
          <div class="stat-label">未编译</div>
        </div>
      </div>
    </div>

    <!-- 租户编译状态卡片 -->
    <div class="tenant-cards" v-loading="loading">
      <div
        v-for="tenant in tenants"
        :key="tenant.id"
        class="tenant-card"
        :class="tenant.status?.status"
        data-testid="compile-tenant-card"
      >
        <div class="card-header">
          <div class="tenant-name">
            <el-icon><OfficeBuilding /></el-icon>
            {{ tenant.label }}
          </div>
          <el-tag
            size="small"
            :type="statusTagType(tenant.status?.status)"
          >
            {{ statusLabel(tenant.status?.status) }}
          </el-tag>
        </div>

        <div class="card-body" v-if="tenant.status">
          <div class="info-row">
            <span class="info-label">版本</span>
            <span class="info-value">{{ tenant.status.current_version || '-' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">编译时间</span>
            <span class="info-value">{{ tenant.status.last_compiled_at ? formatTime(tenant.status.last_compiled_at) : '-' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">过期时间</span>
            <span class="info-value">
              <template v-if="tenant.status.staleness_seconds > 0">
                <el-tag
                  size="small"
                  :type="tenant.status.staleness_seconds > 3600 ? 'danger' : 'warning'"
                >
                  {{ formatStaleness(tenant.status.staleness_seconds) }}
                </el-tag>
              </template>
              <template v-else>-</template>
            </span>
          </div>

          <!-- 版本时间线 -->
          <div v-if="tenant.status.current_version" class="version-timeline">
            <div class="timeline-item active">
              <div class="timeline-dot"></div>
              <div class="timeline-content">
                <span class="version-tag">v{{ tenant.status.current_version }}</span>
                <span class="timeline-time">{{ formatTime(tenant.status.last_compiled_at!) }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="card-body" v-else>
          <el-empty :image-size="60" description="暂无编译记录" />
        </div>

        <div class="card-footer">
          <el-button
            size="small"
            type="primary"
            text
            @click="triggerCompileFor(tenant.id)"
            :loading="tenant.compiling"
          >
            <el-icon><VideoPlay /></el-icon> 触发编译
          </el-button>
          <el-button
            size="small"
            text
            @click="viewDetails(tenant.id)"
          >
            <el-icon><View /></el-icon> 详情
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { rulesEngineApi, type CompileStatusResponse } from '@/api/rulesEngine'

interface TenantInfo {
  id: string
  label: string
  status: CompileStatusResponse | null
  compiling: boolean
}

const loading = ref(false)
const refreshing = ref(false)
const tenants = reactive<TenantInfo[]>([
  { id: 'default', label: '默认租户', status: null, compiling: false },
  { id: 'bank_a', label: '银行A', status: null, compiling: false },
  { id: 'bank_b', label: '银行B', status: null, compiling: false },
])

const stats = computed(() => {
  const s = { completed: 0, compiling: 0, failed: 0, never: 0 }
  for (const t of tenants) {
    if (!t.status || t.status.status === 'never_compiled') s.never++
    else if (t.status.status === 'completed') s.completed++
    else if (t.status.status === 'compiling') s.compiling++
    else if (t.status.status === 'failed') s.failed++
    else s.never++
  }
  return s
})

function statusTagType(status?: string) {
  const map: Record<string, string> = {
    completed: 'success',
    compiling: 'primary',
    failed: 'danger',
    never_compiled: 'info',
    stale: 'warning',
  }
  return map[status || ''] || 'info'
}

function statusLabel(status?: string) {
  const map: Record<string, string> = {
    completed: '已编译',
    compiling: '编译中',
    failed: '失败',
    never_compiled: '未编译',
    stale: '已过期',
  }
  return map[status || ''] || status || '未知'
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

function formatStaleness(seconds: number) {
  if (seconds < 60) return `${seconds}秒前`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟前`
  return `${Math.floor(seconds / 3600)}小时前`
}

async function loadAllStatus() {
  loading.value = true
  const promises = tenants.map(async (t) => {
    try {
      t.status = await rulesEngineApi.getCompileStatus(t.id)
    } catch {
      t.status = null
    }
  })
  await Promise.all(promises)
  loading.value = false
}

async function refreshAll() {
  refreshing.value = true
  await loadAllStatus()
  refreshing.value = false
  ElMessage.success('状态已刷新')
}

async function triggerCompileFor(tenantId: string) {
  const tenant = tenants.find(t => t.id === tenantId)
  if (!tenant) return
  tenant.compiling = true
  try {
    const res = await rulesEngineApi.triggerCompile(tenantId)
    if (res.status === 'completed') {
      ElMessage.success(`${tenant.label} 编译完成`)
    } else if (res.status === 'failed') {
      ElMessage.error(`${tenant.label} 编译失败`)
    }
    tenant.status = await rulesEngineApi.getCompileStatus(tenantId)
  } catch (e: any) {
    ElMessage.error(e?.message || '编译失败')
  } finally {
    tenant.compiling = false
  }
}

function viewDetails(tenantId: string) {
  // Navigate to rules manager with this tenant
  ElMessage.info(`查看 ${tenantId} 详情（待实现）`)
}

onMounted(() => {
  loadAllStatus()
})
</script>

<style scoped>
.compile-status-view {
  max-width: 1200px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h2 {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

/* 统计行 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg, 12px);
  transition: transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.4rem;
}

.stat-card.completed .stat-icon {
  background: rgba(82, 196, 26, 0.15);
  color: #52c41a;
}

.stat-card.compiling .stat-icon {
  background: rgba(24, 144, 255, 0.15);
  color: #1890ff;
}

.stat-card.failed .stat-icon {
  background: rgba(255, 77, 79, 0.15);
  color: #ff4d4f;
}

.stat-card.never .stat-icon {
  background: rgba(191, 191, 191, 0.15);
  color: #bfbfbf;
}

.stat-value {
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1;
}

.stat-label {
  font-size: 0.85rem;
  color: var(--text-secondary);
  margin-top: 4px;
}

/* 租户卡片 */
.tenant-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 20px;
}

.tenant-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg, 12px);
  overflow: hidden;
  transition: transform 0.2s, box-shadow 0.2s;
}

.tenant-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.tenant-card.completed {
  border-left: 3px solid #52c41a;
}

.tenant-card.compiling {
  border-left: 3px solid #1890ff;
}

.tenant-card.failed {
  border-left: 3px solid #ff4d4f;
}

.tenant-card.never_compiled {
  border-left: 3px solid #bfbfbf;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-color);
}

.tenant-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-body {
  padding: 16px 20px;
}

.info-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 0;
}

.info-label {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.info-value {
  color: var(--text-primary);
  font-size: 0.9rem;
}

/* 版本时间线 */
.version-timeline {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.timeline-item {
  display: flex;
  align-items: center;
  gap: 10px;
  position: relative;
}

.timeline-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--primary-500);
  flex-shrink: 0;
}

.timeline-content {
  display: flex;
  align-items: center;
  gap: 10px;
}

.version-tag {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--primary-500);
}

.timeline-time {
  font-size: 0.8rem;
  color: var(--text-muted);
}

.card-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--border-color);
}

@media (max-width: 768px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
