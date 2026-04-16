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
    // Handle business error codes
    if (data.code !== 0) {
      ElMessage.error(data.message || '请求失败')
      return Promise.reject(new Error(data.message))
    }
    return data.data
  },
  (error: AxiosError) => {
    const { response } = error
    
    if (response) {
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
          ElMessage.error('请求的资源不存在')
          break
        case 500:
          ElMessage.error('服务器内部错误')
          break
        default:
          ElMessage.error((response.data as any)?.message || '网络错误')
      }
    } else {
      ElMessage.error('网络连接失败')
    }
    
    return Promise.reject(error)
  }
)

export default request
