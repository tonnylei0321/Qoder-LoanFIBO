/** Auth Store - Pinia */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, LoginForm } from '@/types'

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string>(localStorage.getItem('token') || '')
  const user = ref<User | null>(null)

  // Getters
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  // Actions
  const setToken = (newToken: string) => {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  const setUser = (userData: User) => {
    user.value = userData
  }

  const login = async (form: LoginForm): Promise<boolean> => {
    // TODO: Call real API
    // Mock login for now
    if (form.username && form.password) {
      setToken('mock_token_' + Date.now())
      setUser({
        id: 1,
        username: form.username,
        role: 'admin',
        createdAt: new Date().toISOString(),
      })
      return true
    }
    return false
  }

  const logout = () => {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  const fetchUserInfo = async () => {
    // TODO: Call real API to get user info
    if (token.value && !user.value) {
      setUser({
        id: 1,
        username: 'admin',
        role: 'admin',
        createdAt: new Date().toISOString(),
      })
    }
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    setToken,
    setUser,
    login,
    logout,
    fetchUserInfo,
  }
})
