/** LoanFIBO Frontend Type Definitions */

// User & Auth
export interface User {
  id: number
  username: string
  role: 'admin' | 'operator' | 'viewer'
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
