/** 规则引擎 API - NLQ查询、规则管理、编译状态、租户配置 */
import request from './request'

// ─── 类型定义 ──────────────────────────────────────────────────────

/** NLQ查询请求 */
export interface QueryRequest {
  tenant_id: string
  query: string
  context?: Record<string, any>
  options?: Record<string, any>
}

/** NLQ查询响应 */
export interface QueryResponse {
  status: string
  data?: Record<string, any>
  sql?: string
  message: string
  retry_after?: number
  admin_alert: boolean
}

/** 创建规则请求 */
export interface RuleCreate {
  tenant_id: string
  name: string
  rule_type: string
  definition: Record<string, any>
  priority?: number
  enabled?: boolean
}

/** 规则响应 */
export interface RuleResponse {
  id: string
  tenant_id: string
  name: string
  rule_type: string
  definition: Record<string, any>
  priority: number
  enabled: boolean
}

/** 编译状态响应 */
export interface CompileStatusResponse {
  tenant_id: string
  status: string
  current_version?: string
  last_compiled_at?: string
  staleness_seconds: number
}

/** 租户配置 */
export interface TenantConfig {
  tenant_id: string
  db_schema: string
  compile_priority: number
  max_rules: number
  nlq_enabled: boolean
  custom_settings?: Record<string, any>
}

// ─── API 调用 ──────────────────────────────────────────────────────

export const rulesEngineApi = {
  // ── NLQ 查询 ──
  query: (data: QueryRequest): Promise<QueryResponse> =>
    request.post('/query', data),

  // ── 规则管理 ──
  createRule: (data: RuleCreate): Promise<RuleResponse> =>
    request.post('/rules', data),

  listRules: (tenantId: string): Promise<RuleResponse[]> =>
    request.get(`/rules/${tenantId}`),

  // ── 编译状态 ──
  getCompileStatus: (tenantId: string): Promise<CompileStatusResponse> =>
    request.get(`/compile-status/${tenantId}`),

  triggerCompile: (tenantId: string): Promise<{ tenant_id: string; status: string; version?: string; errors?: string[] }> =>
    request.post(`/compile/${tenantId}`),

  // ── 租户配置 ──
  getTenantConfig: (tenantId: string): Promise<TenantConfig> =>
    request.get(`/tenants/${tenantId}/config`),

  updateTenantConfig: (tenantId: string, data: Partial<TenantConfig>): Promise<TenantConfig> =>
    request.put(`/tenants/${tenantId}/config`, data),

  getTenantCompileStatus: (tenantId: string): Promise<CompileStatusResponse> =>
    request.get(`/tenants/${tenantId}/compile-status`),
}
