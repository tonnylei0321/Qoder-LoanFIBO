/** Auth API */
import request from './request'
import type { ApiResponse, User, LoginForm } from '@/types'

export const authApi = {
  login: (form: LoginForm): Promise<string> => {
    return request.post('/auth/login', form)
  },

  getCurrentUser: (): Promise<User> => {
    return request.get('/auth/me')
  },
}
