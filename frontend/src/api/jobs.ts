/** Jobs API */
import request from './request'
import type { Job, JobCreateForm, PaginatedData, PaginationParams, PipelineStats } from '@/types'

export const jobsApi = {
  getJobs: (params?: PaginationParams & { status?: string }): Promise<PaginatedData<Job>> => {
    return request.get('/jobs', { params })
  },

  getJob: (id: number): Promise<Job> => {
    return request.get(`/jobs/${id}`)
  },

  createJob: (data: JobCreateForm): Promise<Job> => {
    return request.post('/jobs', data)
  },

  pauseJob: (id: number): Promise<void> => {
    return request.post(`/jobs/${id}/pause`)
  },

  resumeJob: (id: number): Promise<void> => {
    return request.post(`/jobs/${id}/resume`)
  },

  stopJob: (id: number): Promise<void> => {
    return request.post(`/jobs/${id}/stop`)
  },

  getJobStats: (id: number): Promise<PipelineStats> => {
    return request.get(`/jobs/${id}/stats`)
  },
}
