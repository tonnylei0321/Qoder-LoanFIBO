<template>
  <div class="agent-status">
    <div class="page-header">
      <h2>代理连接状态</h2>
      <el-button @click="fetchStatus" :loading="loading">刷新</el-button>
    </div>

    <div class="status-grid" v-loading="loading">
      <el-card v-for="agent in agents" :key="`${agent.org_id}-${agent.datasource}`" class="status-card">
        <template #header>
          <div class="card-header">
            <span>{{ agent.datasource }}</span>
            <el-tag :type="statusTagType(agent.status)" effect="dark">
              {{ agent.status }}
            </el-tag>
          </div>
        </template>
        <el-descriptions :column="1" size="small" border>
          <el-descriptions-item label="企业ID">{{ agent.org_id }}</el-descriptions-item>
          <el-descriptions-item label="数据源">{{ agent.datasource }}</el-descriptions-item>
          <el-descriptions-item label="版本">{{ agent.version }}</el-descriptions-item>
          <el-descriptions-item label="IP">{{ agent.ip }}</el-descriptions-item>
          <el-descriptions-item label="最后心跳">{{ formatTime(agent.last_seen) }}</el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-empty v-if="!loading && agents.length === 0" description="暂无在线代理" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { agentApi } from '@/api/agent'

interface AgentInfo {
  org_id: string
  datasource: string
  status: string
  version: string
  ip: string
  last_seen: string
}

const loading = ref(false)
const agents = ref<AgentInfo[]>([])
let pollTimer: ReturnType<typeof setInterval> | null = null

const fetchStatus = async () => {
  loading.value = true
  try {
    const data = (await agentApi.getAgentStatus()) as unknown as AgentInfo[]
    agents.value = data
  } catch (e) {
    // ignore
  } finally {
    loading.value = false
  }
}

const statusTagType = (status: string) => {
  switch (status) {
    case 'ONLINE': return 'success'
    case 'DEGRADED': return 'warning'
    case 'OFFLINE': return 'danger'
    default: return 'info'
  }
}

const formatTime = (iso: string) => {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

onMounted(() => {
  fetchStatus()
  // 10 秒轮询刷新
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
.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
