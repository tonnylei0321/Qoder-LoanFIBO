/** Files API */
import request from './request'
import type { DDLFile, TTLFile, PaginatedData, PaginationParams } from '@/types'

export const filesApi = {
  // DDL Files
  getDDLFiles: (params?: PaginationParams & { sourceTag?: string }): Promise<PaginatedData<DDLFile>> => {
    return request.get('/files/ddl', { params })
  },

  getDDLFile: (id: number): Promise<DDLFile> => {
    return request.get(`/files/ddl/${id}`)
  },

  uploadDDLFile: (formData: FormData): Promise<DDLFile> => {
    return request.post('/files/ddl', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  deleteDDLFile: (id: number): Promise<void> => {
    return request.delete(`/files/ddl/${id}`)
  },

  parseDDLFile: (id: number): Promise<void> => {
    return request.post(`/files/ddl/${id}/parse`)
  },

  // TTL Files
  getTTLFiles: (params?: PaginationParams & { ontologyTag?: string }): Promise<PaginatedData<TTLFile>> => {
    return request.get('/files/ttl', { params })
  },

  getTTLFile: (id: number): Promise<TTLFile> => {
    return request.get(`/files/ttl/${id}`)
  },

  uploadTTLFile: (formData: FormData): Promise<TTLFile> => {
    return request.post('/files/ttl', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  deleteTTLFile: (id: number): Promise<void> => {
    return request.delete(`/files/ttl/${id}`)
  },

  indexTTLFile: (id: number): Promise<void> => {
    return request.post(`/files/ttl/${id}/index`)
  },
}
