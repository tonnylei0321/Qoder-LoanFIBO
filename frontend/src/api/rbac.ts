/** RBAC API — User / Role / Permission management */
import request from './request'
import type { User, Role, Permission, PaginatedData } from '@/types'

// ── Users ──────────────────────────────────────────────────────────────

export const getUsers = (params?: { page?: number; page_size?: number; search?: string }) =>
  request.get<any, PaginatedData<User>>('/rbac/users', { params })

export const createUser = (data: { username: string; password: string; email?: string; role_ids?: number[] }) =>
  request.post<any, User>('/rbac/users', data)

export const updateUser = (id: number, data: { username?: string; email?: string; password?: string }) =>
  request.put<any, User>(`/rbac/users/${id}`, data)

export const deleteUser = (id: number) =>
  request.delete(`/rbac/users/${id}`)

export const assignUserRoles = (id: number, role_ids: number[]) =>
  request.put<any, User>(`/rbac/users/${id}/roles`, { role_ids })

export const toggleUserStatus = (id: number, status: string) =>
  request.put<any, User>(`/rbac/users/${id}/status`, { status })

// ── Roles ──────────────────────────────────────────────────────────────

export const getRoles = () =>
  request.get<any, Role[]>('/rbac/roles')

export const createRole = (data: { name: string; code: string; description?: string }) =>
  request.post<any, Role>('/rbac/roles', data)

export const updateRole = (id: number, data: { name?: string; description?: string; status?: string }) =>
  request.put<any, Role>(`/rbac/roles/${id}`, data)

export const deleteRole = (id: number) =>
  request.delete(`/rbac/roles/${id}`)

export const assignRolePermissions = (id: number, permission_ids: number[]) =>
  request.put<any, Role>(`/rbac/roles/${id}/permissions`, { permission_ids })

export const assignRoleMenuCodes = (id: number, menu_codes: string[]) =>
  request.put<any, Role>(`/rbac/roles/${id}/menu-permissions`, { menu_codes })

// ── Permissions ────────────────────────────────────────────────────────

export const getPermissions = () =>
  request.get<any, Permission[]>('/rbac/permissions')

export const createPermission = (data: { name: string; code: string; module: string }) =>
  request.post<any, Permission>('/rbac/permissions', data)

export const updatePermission = (id: number, data: { name?: string; code?: string; module?: string }) =>
  request.put<any, Permission>(`/rbac/permissions/${id}`, data)

export const deletePermission = (id: number) =>
  request.delete(`/rbac/permissions/${id}`)
