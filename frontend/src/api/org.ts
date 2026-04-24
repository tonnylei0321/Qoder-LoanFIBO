/** 融资企业 & 授权项 API */
import request from './request'

// ─── 融资企业 ─────────────────────────────────────────────

export interface ApplicantOrg {
  id: string
  name: string
  unified_code?: string
  short_name?: string
  industry?: string
  region?: string
  legal_person?: string
  registered_capital?: string
  contact_info?: string
  is_active: boolean
  security_id_masked?: string
  security_id?: string  // 仅创建时返回明文
  graph_uri?: string
  reg_tags?: Record<string, boolean>
  extra?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface ApplicantOrgCreate {
  name: string
  unified_code?: string
  short_name?: string
  industry?: string
  region?: string
  legal_person?: string
  registered_capital?: string
  contact_info?: string
  extra?: Record<string, unknown>
}

export interface ApplicantOrgUpdate extends Partial<ApplicantOrgCreate> {
  is_active?: boolean
}

// ─── 授权项 ───────────────────────────────────────────────

export interface AuthorizationScope {
  id: string
  code: string
  label: string
  category?: string
  description?: string
  is_active: boolean
  graph_uri?: string
  extra?: Record<string, unknown>
  created_at?: string
  updated_at?: string
}

export interface AuthorizationScopeCreate {
  code: string
  label: string
  category?: string
  description?: string
  extra?: Record<string, unknown>
}

export interface AuthorizationScopeUpdate extends Partial<AuthorizationScopeCreate> {
  is_active?: boolean
}

// ─── API ──────────────────────────────────────────────────

export const orgApi = {
  // 融资企业
  listOrgs: (activeOnly = false): Promise<ApplicantOrg[]> =>
    request.get('/org/orgs', { params: { active_only: activeOnly } }),

  getOrg: (id: string): Promise<ApplicantOrg> =>
    request.get(`/org/orgs/${id}`),

  createOrg: (data: ApplicantOrgCreate): Promise<ApplicantOrg> =>
    request.post('/org/orgs', data),

  updateOrg: (id: string, data: ApplicantOrgUpdate): Promise<ApplicantOrg> =>
    request.put(`/org/orgs/${id}`, data),

  deleteOrg: (id: string): Promise<void> =>
    request.delete(`/org/orgs/${id}`),

  regenerateSecurityId: (id: string): Promise<{ code: number; data: { org_id: string; security_id: string; security_id_masked: string } }> =>
    request.post(`/org/orgs/${id}/regenerate-security-id`),

  // 授权项
  listAuthScopes: (activeOnly = false): Promise<AuthorizationScope[]> =>
    request.get('/org/auth-scopes', { params: { active_only: activeOnly } }),

  getAuthScope: (id: string): Promise<AuthorizationScope> =>
    request.get(`/org/auth-scopes/${id}`),

  createAuthScope: (data: AuthorizationScopeCreate): Promise<AuthorizationScope> =>
    request.post('/org/auth-scopes', data),

  updateAuthScope: (id: string, data: AuthorizationScopeUpdate): Promise<AuthorizationScope> =>
    request.put(`/org/auth-scopes/${id}`, data),

  deleteAuthScope: (id: string): Promise<void> =>
    request.delete(`/org/auth-scopes/${id}`),

  // 企业-授权项关联
  getOrgAuthScopes: (orgId: string): Promise<{ scope_ids: string[] }> =>
    request.get(`/org/orgs/${orgId}/auth-scopes`),

  updateOrgAuthScopes: (orgId: string, scopeIds: string[]): Promise<{ scope_ids: string[] }> =>
    request.put(`/org/orgs/${orgId}/auth-scopes`, { scope_ids: scopeIds }),

  // 种子数据
  seedDefaultData: (): Promise<{ seeded_auth_scopes: number }> =>
    request.post('/org/seed'),
}
