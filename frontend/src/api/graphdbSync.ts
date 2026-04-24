/** GraphDB Sync API - 版本管理、实例管理、同步任务、外键推断 */
import request from './request'

// ─── 版本管理 ──────────────────────────────────────────────────

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

// ─── 实例管理 ──────────────────────────────────────────────────

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

// ─── 同步任务 ──────────────────────────────────────────────────

export interface SyncTask {
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

// ─── 外键推断 ──────────────────────────────────────────────────

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

// ─── API 方法 ──────────────────────────────────────────────────

export const graphdbSyncApi = {
  // 版本管理
  createVersion: (data: VersionCreateForm): Promise<SyncVersion> => {
    return request.post('/versions', data)
  },

  listVersions: (params?: { status_filter?: string; limit?: number; offset?: number }): Promise<SyncVersion[]> => {
    return request.get('/versions', { params })
  },

  getVersion: (id: string): Promise<SyncVersion> => {
    return request.get(`/versions/${id}`)
  },

  publishVersion: (id: string, data?: { description?: string }): Promise<SyncVersion> => {
    return request.patch(`/versions/${id}/publish`, data)
  },

  // 实例管理
  createInstance: (data: InstanceCreateForm): Promise<GraphDBInstance> => {
    return request.post('/instances', data)
  },

  listInstances: (): Promise<GraphDBInstance[]> => {
    return request.get('/instances')
  },

  getInstance: (id: string): Promise<GraphDBInstance> => {
    return request.get(`/instances/${id}`)
  },

  updateInstance: (id: string, data: InstanceCreateForm): Promise<GraphDBInstance> => {
    return request.put(`/instances/${id}`, data)
  },

  deleteInstance: (id: string): Promise<void> => {
    return request.delete(`/instances/${id}`)
  },

  checkHealth: (id: string): Promise<InstanceHealth> => {
    return request.get(`/instances/${id}/health`)
  },

  // 同步任务
  createSyncTask: (data: SyncTaskCreateForm): Promise<SyncTask> => {
    return request.post('/tasks', data)
  },

  listSyncTasks: (): Promise<SyncTask[]> => {
    return request.get('/tasks')
  },

  getSyncTask: (id: string): Promise<SyncTask> => {
    return request.get(`/tasks/${id}`)
  },

  getTaskProgress: (id: string): Promise<SyncTask> => {
    return request.get(`/tasks/${id}/progress`)
  },

  // 外键推断
  inferForeignKeys: (data: ForeignKeyInferForm): Promise<ForeignKey[]> => {
    return request.post('/infer-foreign-keys', data)
  },

  listForeignKeys: (params?: { source_table?: string; status_filter?: string }): Promise<ForeignKey[]> => {
    return request.get('/foreign-keys', { params })
  },

  approveForeignKey: (id: string, action: 'approve' | 'reject'): Promise<ForeignKey> => {
    return request.patch(`/foreign-keys/${id}`, { action })
  },
}
