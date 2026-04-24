/** Auth Store - Pinia */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User, LoginForm } from '@/types'
import request from '@/api/request'

export const useAuthStore = defineStore('auth', () => {
  // State
  const token = ref<string>(localStorage.getItem('token') || '')
  const user = ref<User | null>(null)

  // Getters
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => {
    if (!user.value) return false
    return user.value.roles?.some(r => r.code === 'admin') || false
  })

  /**
   * menuCodes:
   *  - null  → admin / no restriction, can see all menus
   *  - string[] → the list of route names this user can access
   */
  const menuCodes = computed<string[] | null>(() => {
    if (!user.value) return []
    return user.value.menu_codes  // null = unrestricted (admin)
  })

  /** Returns true if the given routeName is accessible */
  const canAccessMenu = (routeName: string): boolean => {
    if (menuCodes.value === null) return true  // admin
    return menuCodes.value.includes(routeName)
  }

  // Actions
  const setToken = (newToken: string) => {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  const setUser = (userData: User) => {
    user.value = userData
  }

  const login = async (form: LoginForm): Promise<boolean> => {
    try {
      const res = await request.post<any, { token: string }>('/auth/login', {
        username: form.username,
        password: form.password,
      })
      setToken(res.token)
      await fetchUserInfo()
      return true
    } catch {
      return false
    }
  }

  const logout = () => {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  const fetchUserInfo = async () => {
    if (!token.value) return
    try {
      const res = await request.get<any, User>('/auth/me')
      setUser(res)
    } catch {
      // Token invalid — clear
      logout()
    }
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    menuCodes,
    canAccessMenu,
    setToken,
    setUser,
    login,
    logout,
    fetchUserInfo,
  }
})
