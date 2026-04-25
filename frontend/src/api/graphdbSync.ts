/** GraphDB Sync API - 版本管理、实例管理、同步任务 */
import request from './request'

// ─── 版本管理 ──────────────────────────────────────────────────

export interface SyncVersion {
  id: string
  version_tag: string
  description: string | null
  status: string
  snapshot_data: Record<string, unknown> | null
  created_by: string | null
  ttl_file_name: string | null
  ttl_file_size: number | null
  ttl_valid: boolean | null
  ttl_validation_msg: string | null
  class_count: number | null
  property_count: number | null
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

export interface VersionUpdateForm {
  version_tag?: string
  description?: string
}

// ─── 实例管理 ──────────────────────────────────────────────────

export interface GraphDBInstance {
  id: string
  name: string
  server_url: string
  repo_id: string
  domain: string | null
  namespace_prefix: string
  version_id: string | null
  is_active: boolean
  created_at: string | null
}

export interface InstanceCreateForm {
  name: string
  server_url: string
  repo_id: string
  domain?: string
  namespace_prefix?: string
  version_id?: string
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

// ─── API 方法 ──────────────────────────────────────────────────

export const graphdbSyncApi = {
  // 版本管理
  uploadVersionTTL: (formData: FormData): Promise<SyncVersion> => {
    return request.post('/versions/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  createVersion: (data: VersionCreateForm): Promise<SyncVersion> => {
    return request.post('/versions', data)
  },

  listVersions: (params?: { status_filter?: string; limit?: number; offset?: number }): Promise<SyncVersion[]> => {
    return request.get('/versions', { params })
  },

  getVersion: (id: string): Promise<SyncVersion> => {
    return request.get(`/versions/${id}`)
  },

  updateVersion: (id: string, data: VersionUpdateForm): Promise<SyncVersion> => {
    return request.patch(`/versions/${id}`, data)
  },

  publishVersion: (id: string, data?: { description?: string }): Promise<SyncVersion> => {
    return request.patch(`/versions/${id}/publish`, data)
  },

  deleteVersion: (id: string): Promise<void> => {
    return request.delete(`/versions/${id}`)
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
}
