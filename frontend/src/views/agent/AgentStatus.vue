<template>
  <div class="agent-status">
    <div class="page-header">
      <h2>代理连接状态</h2>
      <el-button @click="fetchStatus" :loading="loading">刷新</el-button>
    </div>

    <el-table :data="agents" v-loading="loading" stripe style="width: 100%">
      <el-table-column label="企业名称" min-width="160">
        <template #default="{ row }">
          {{ getOrgName(row.org_id) }}
        </template>
      </el-table-column>
      <el-table-column prop="org_id" label="企业ID" width="280">
        <template #default="{ row }">
          <span style="font-family: monospace; font-size: 12px">{{ row.org_id }}</span>
        </template>
      </el-table-column>
      <el-table-column label="安全ID" width="200">
        <template #default="{ row }">
          <span v-if="getOrgSecurityId(row.org_id)" style="font-family: monospace; font-size: 12px">{{ getOrgSecurityId(row.org_id) }}</span>
          <span v-else style="color: var(--el-text-color-placeholder); font-size: 12px">-</span>
        </template>
      </el-table-column>
      <el-table-column prop="datasource" label="数据源" width="100" />
      <el-table-column label="链路状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)" effect="dark" size="small">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="version" label="代理版本" width="120" />
      <el-table-column prop="ip" label="IP" width="140" />
      <el-table-column label="最后心跳" width="180">
        <template #default="{ row }">{{ formatTime(row.last_seen) }}</template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && agents.length === 0" description="暂无在线代理" />
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

interface OrgInfo {
  org_id: string
  name: string
  security_id_masked?: string
}

const loading = ref(false)
const agents = ref<AgentInfo[]>([])
const orgMap = ref<Map<string, OrgInfo>>(new Map())
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

const fetchOrgs = async () => {
  try {
    const result = (await agentApi.listOrgs()) as any
    const orgs: OrgInfo[] = result.data || []
    const map = new Map<string, OrgInfo>()
    for (const org of orgs) {
      map.set(org.org_id, org)
    }
    orgMap.value = map
  } catch (e) {
    // ignore
  }
}

const getOrgName = (orgId: string): string => {
  return orgMap.value.get(orgId)?.name || orgId
}

const getOrgSecurityId = (orgId: string): string | undefined => {
  return orgMap.value.get(orgId)?.security_id_masked
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
  fetchOrgs()
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
</style>
