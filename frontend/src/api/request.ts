/** Axios Request Configuration */
import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

// Create axios instance
const request: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - add token
request.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const authStore = useAuthStore()
    if (authStore.token) {
      config.headers.Authorization = `Bearer ${authStore.token}`
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// Response interceptor - handle errors
request.interceptors.response.use(
  (response) => {
    const { data } = response
    // 兼容两种后端响应格式：
    // 1. 标准包装格式 { code: 0, data: ..., message: ... }
    // 2. 直接返回的业务数据（explore 等新接口）
    if (data && typeof data === 'object' && 'code' in data) {
      // 标准包装格式
      if (data.code !== 0) {
        ElMessage.error(data.message || '请求失败')
        return Promise.reject(new Error(data.message))
      }
      // 如果有 total/overflow 等分页字段，一并返回
      const extraKeys = ['total', 'overflow']
      const extra: Record<string, any> = {}
      for (const key of extraKeys) {
        if (key in data) {
          extra[key] = data[key]
        }
      }
      // 如果 data.data 是数组且有额外分页字段，返回 { data: [...], total: N }
      if (Array.isArray(data.data) && Object.keys(extra).length > 0) {
        return { data: data.data, ...extra }
      }
      return data.data
    }
    // 直接返回的业务数据
    return data
  },
  (error: AxiosError) => {
    const { response } = error
    
    if (response) {
      const detail = (response.data as any)?.detail || (response.data as any)?.message || ''
      switch (response.status) {
        case 401:
          ElMessage.error('登录已过期，请重新登录')
          useAuthStore().logout()
          window.location.href = '/login'
          break
        case 403:
          ElMessage.error('没有权限执行此操作')
          break
        case 404:
          ElMessage.error(detail || '请求的资源不存在')
          break
        case 500:
          ElMessage.error(detail ? `服务器错误: ${detail}` : '服务器内部错误')
          console.error(`[API 500] ${response.config.method?.toUpperCase()} ${response.config.url}`, response.data)
          break
        case 502:
          ElMessage.error(detail || '上游服务不可用')
          console.error(`[API 502] ${response.config.method?.toUpperCase()} ${response.config.url}`, response.data)
          break
        default:
          ElMessage.error(detail || '网络错误')
      }
    } else {
      ElMessage.error('网络连接失败')
    }
    
    return Promise.reject(error)
  }
)

export default request
