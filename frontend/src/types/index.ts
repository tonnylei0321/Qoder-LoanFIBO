/** LoanFIBO Frontend Type Definitions */

// User & Auth
export interface User {
  id: number
  username: string
  email?: string
  status: string
  roles: RoleItem[]
  permissions: string[]
  menu_codes: string[] | null  // null = no restriction (admin); array = allowed routes
  createdAt: string
}

export interface RoleItem {
  id: number
  name: string
  code: string
}

export interface Role {
  id: number
  name: string
  code: string
  description?: string
  status: string
  permissions: PermissionItem[]
  menu_codes: string[]  // menu route names assigned to this role
  createdAt: string
}

export interface PermissionItem {
  id: number
  name: string
  code: string
  module: string
}

export interface Permission {
  id: number
  name: string
  code: string
  module: string
  createdAt: string
}

export interface LoginForm {
  username: string
  password: string
}

// DDL File Version
export interface DDLFile {
  id: number
  fileName: string
  sourceTag: string // e.g., "BIPV5-财务域-v1.2"
  erpSource: string // e.g., "BIPV5", "SAP"
  version: string // e.g., "v1.2"
  fileSize: number
  uploadTime: string
  parseStatus: 'pending' | 'parsing' | 'completed' | 'failed'
  tableCount?: number
  errorMessage?: string
}

// TTL File Version
export interface TTLFile {
  id: number
  fileName: string
  ontologyTag: string // e.g., "FIBO-v4.4"
  ontologyType: string // e.g., "FIBO", "SASAC"
  version: string // e.g., "v4.4"
  fileSize: number
  uploadTime: string
  indexStatus: 'pending' | 'indexing' | 'completed' | 'failed'
  classCount?: number
  propertyCount?: number
  errorMessage?: string
}

// Job & Mapping
export interface Job {
  id: number
  name: string
  description?: string
  ddlFileId: number
  ddlFileTag: string
  ttlFileId: number
  ttlFileTag: string
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'stopped'
  progress: number // 0-100
  totalTables: number
  mappedTables: number
  totalFields: number
  mappedFields: number
  createdAt: string
  startedAt?: string
  completedAt?: string
  concurrency: number
  batchSize: number
}

export interface JobCreateForm {
  name: string
  description?: string
  ddlFileId: number | null
  ttlFileId: number | null
  concurrency: number
  batchSize: number
}

export interface JobProgress {
  jobId: number
  status: Job['status']
  progress: number
  currentPhase: string
  phaseProgress: number
  totalTables: number
  processedTables: number
  totalFields: number
  processedFields: number
  message?: string
}

// Pipeline Stages
export interface PipelineStats {
  totalTables: number
  mappedTables: number
  totalFields: number
  mappedFields: number
  stages: {
    ruleMatch: number
    vectorSearch: number
    llmMapping: number
    ignored: number
  }
}

// Mapping Result
export interface MappingResult {
  id: number
  databaseName: string
  tableName: string
  fieldName: string
  fieldType: string
  status: 'mapped' | 'unmapped' | 'pending' | 'review_required'
  fiboClassUri?: string
  fiboPropertyUri?: string
  confidenceLevel?: 'high' | 'medium' | 'low'
  mappingReason?: string
  reviewStatus: 'pending' | 'approved' | 'rejected'
}

// Review
export interface Review {
  id: number
  mappingId: number
  databaseName: string
  tableName: string
  fieldName: string
  issueType: string
  severity: 'high' | 'medium' | 'low'
  description: string
  suggestedFix?: string
  status: 'pending' | 'resolved'
  createdAt: string
}

// API Response
export interface ApiResponse<T> {
  code: number
  message?: string
  data: T
}

// Pagination
export interface PaginationParams {
  page: number
  pageSize: number
}

export interface PaginatedData<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
}

// ─── 图谱浏览 ──────────────────────────────────────────────────

export interface GraphEntity {
  uri: string
  type: string
  label: string
}

export interface GraphEntityDetail {
  uri: string
  properties: Array<{
    property: string
    value: string
    value_type: string
  }>
}

export interface GraphEdge {
  direction: string
  property: string
  target: string
  target_label: string
}

// ─── 同步管理 ──────────────────────────────────────────────────

export interface SyncVersion {
  id: string
  version_tag: string
  description: string | null
  status: string
  snapshot_data: Record<string, unknown> | null
  created_by: string | null
  published_at: string | null
  synced_at: string | null
  created_at: string | null
}

export interface VersionCreateForm {
  version_tag: string
  description?: string
  snapshot_data?: Record<string, unknown>
  created_by?: string
}

export interface GraphDBInstance {
  id: string
  name: string
  server_url: string
  repo_id: string
  domain: string | null
  namespace_prefix: string
  is_active: boolean
  created_at: string | null
}

export interface InstanceCreateForm {
  name: string
  server_url: string
  repo_id: string
  domain?: string
  namespace_prefix?: string
}

export interface InstanceHealth {
  instance_id: string
  status: string
  repository_size: number | null
  statement_count: number | null
  last_checked: string
}

export interface SyncTaskInfo {
  id: string
  version_id: string
  instance_id: string
  mode: string
  status: string
  progress: number
  triples_synced: number
  error_message: string | null
  created_at: string | null
  completed_at: string | null
}

export interface SyncTaskCreateForm {
  version_id: string
  instance_id: string
  mode?: string
}

export interface ForeignKey {
  id: string
  source_table: string
  source_column: string
  target_table: string
  target_column: string
  confidence: number
  status: string
  inferred_by: string
}

export interface ForeignKeyInferForm {
  table_names: string[]
}
