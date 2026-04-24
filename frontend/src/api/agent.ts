/** Agent 管理 API 客户端 */
import request from './request'

export const agentApi = {
  // 企业列表
  listOrgs: (params?: { search?: string; limit?: number; offset?: number }) => {
    return request.get('/agent/orgs', { params })
  },

  // 企业注册
  registerOrg: (data: { name: string; industry?: string; datasource?: string }) => {
    return request.post('/agent/orgs', data)
  },

  // 凭证列表
  listCredentials: (orgId: string) => {
    return request.get(`/agent/orgs/${orgId}/credentials`)
  },

  // 凭证管理
  createCredential: (orgId: string, datasource: string = 'NCC') => {
    return request.post(`/agent/orgs/${orgId}/credentials`, null, { params: { datasource } })
  },

  revokeCredential: (clientId: string) => {
    return request.put(`/agent/credentials/${clientId}/revoke`)
  },

  // 代理状态
  getAgentStatus: (orgId?: string) => {
    return request.get('/agent/status', { params: { org_id: orgId } })
  },

  // 安装包下载
  getDownloadUrl: (platform: string = 'linux') => {
    return request.get('/agent/downloads', { params: { platform } })
  },

  // 审计日志
  getAuditLogs: (params: { org_id?: string; start?: string; end?: string; limit?: number; offset?: number }) => {
    return request.get('/agent/audit-logs', { params })
  },

  // 版本管理
  uploadVersion: (data: { version: string; platform: string; download_url: string; min_version?: string }) => {
    return request.post('/agent/versions', data)
  },

  getVersions: (platform?: string) => {
    return request.get('/agent/versions', { params: { platform } })
  },

  // 追踪
  getTraces: (params: { org_id?: string; limit?: number; offset?: number }) => {
    return request.get('/agent/traces', { params })
  },

  getTraceDetail: (traceId: string) => {
    return request.get(`/agent/traces/${traceId}`)
  },

  // 提交任务
  submitTask: (data: { org_id: string; datasource: string; action: string; payload: Record<string, unknown>; timeout_ms?: number }) => {
    return request.post('/agent/task', data)
  },

  // 手动触发指标采集
  triggerCollect: (data?: { org_id: string; datasource?: string }) => {
    return request.post('/agent/collect', data || {})
  },
}
