<template>
  <div class="users-page">
    <div class="admin-page-header">
      <div class="title-area">
        <h2>用户管理</h2>
        <span class="subtitle">管理系统用户帐号、角色分配与状态控制</span>
      </div>
      <div class="actions">
        <el-input v-model="searchKey" placeholder="搜索用户名..." style="width:200px" clearable @clear="loadUsers" @keyup.enter="loadUsers">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="openDialog()">
          <el-icon><Plus /></el-icon> 添加用户
        </el-button>
      </div>
    </div>

    <div class="admin-table-card">
      <el-table :data="users" v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="用户" min-width="180">
          <template #default="{ row }">
            <div class="entity-row">
              <div class="entity-avatar">{{ row.username.charAt(0).toUpperCase() }}</div>
              <div class="entity-info">
                <span class="entity-name">{{ row.username }}</span>
                <span v-if="row.email" class="entity-meta">{{ row.email }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="角色" min-width="200">
          <template #default="{ row }">
            <el-tag v-for="r in row.roles" :key="r.id" size="small" style="margin-right:4px;margin-bottom:2px">{{ r.name }}</el-tag>
            <span v-if="!row.roles?.length" class="empty-placeholder">未分配</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <span class="pill" :class="row.status === 'active' ? 'pill-success' : 'pill-info'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="开关" width="80" align="center">
          <template #default="{ row }">
            <el-switch :model-value="row.status === 'active'" inline-prompt active-text="开" inactive-text="关" @change="(v: boolean) => toggleStatus(row, v)" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="155">
          <template #default="{ row }">
            <span class="mono-text" style="font-size:12px;color:var(--el-text-color-secondary)">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="170" fixed="right" align="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openDialog(row)">编辑</el-button>
            <el-button type="warning" link size="small" @click="openRoleDialog(row)">角色</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="display:flex;justify-content:flex-end;padding:12px 16px;border-top:1px solid var(--el-border-color-lighter)">
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" layout="total, prev, pager, next" @current-change="loadUsers" />
      </div>
    </div>

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="showDialog" :title="editingUser ? '编辑用户' : '添加用户'" width="480px" destroy-on-close>
      <el-form :model="userForm" label-width="80px">
        <el-form-item label="用户名" required>
          <el-input v-model="userForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" :required="!editingUser">
          <el-input v-model="userForm.password" type="password" :placeholder="editingUser ? '留空则不修改' : '请输入密码'" show-password />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="userForm.email" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitUser">确定</el-button>
      </template>
    </el-dialog>

    <!-- Role Assignment Dialog -->
    <el-dialog v-model="showRoleDialog" title="分配角色" width="400px" destroy-on-close>
      <el-checkbox-group v-model="selectedRoleIds">
        <div v-for="role in allRoles" :key="role.id" style="margin-bottom:8px">
          <el-checkbox :value="role.id" :label="role.id">
            {{ role.name }} <span style="color:var(--text-muted);font-size:0.8em">({{ role.code }})</span>
          </el-checkbox>
        </div>
      </el-checkbox-group>
      <template #footer>
        <el-button @click="showRoleDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRoles">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getUsers, createUser, updateUser, deleteUser, assignUserRoles, toggleUserStatus } from '@/api/rbac'
import { getRoles } from '@/api/rbac'
import type { User, Role } from '@/types'

const loading = ref(false)
const submitting = ref(false)
const showDialog = ref(false)
const showRoleDialog = ref(false)
const editingUser = ref<User | null>(null)
const roleTargetUser = ref<User | null>(null)

const users = ref<User[]>([])
const allRoles = ref<Role[]>([])
const searchKey = ref('')
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const userForm = reactive({ username: '', password: '', email: '' })
const selectedRoleIds = ref<number[]>([])

const formatDate = (d: string) => {
  if (!d) return '-'
  return new Date(d).toLocaleString('zh-CN')
}

const loadUsers = async () => {
  loading.value = true
  try {
    const data = await getUsers({ page: page.value, page_size: pageSize.value, search: searchKey.value || undefined })
    users.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

const loadRoles = async () => {
  allRoles.value = await getRoles()
}

const openDialog = (row?: User) => {
  editingUser.value = row || null
  userForm.username = row?.username || ''
  userForm.password = ''
  userForm.email = row?.email || ''
  showDialog.value = true
}

const openRoleDialog = (row: User) => {
  roleTargetUser.value = row
  selectedRoleIds.value = row.roles?.map(r => r.id) || []
  showRoleDialog.value = true
}

const toggleStatus = async (row: User, active: boolean) => {
  const newStatus = active ? 'active' : 'disabled'
  await toggleUserStatus(row.id, newStatus)
  row.status = newStatus
  ElMessage.success(active ? '已启用' : '已禁用')
}

const submitUser = async () => {
  if (!userForm.username) { ElMessage.warning('请输入用户名'); return }
  if (!editingUser.value && !userForm.password) { ElMessage.warning('请输入密码'); return }

  submitting.value = true
  try {
    if (editingUser.value) {
      const data: Record<string, string> = { username: userForm.username, email: userForm.email }
      if (userForm.password) data.password = userForm.password
      await updateUser(editingUser.value.id, data)
      ElMessage.success('更新成功')
    } else {
      await createUser({ username: userForm.username, password: userForm.password, email: userForm.email || undefined })
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    loadUsers()
  } finally {
    submitting.value = false
  }
}

const submitRoles = async () => {
  if (!roleTargetUser.value) return
  submitting.value = true
  try {
    await assignUserRoles(roleTargetUser.value.id, selectedRoleIds.value)
    ElMessage.success('角色分配成功')
    showRoleDialog.value = false
    loadUsers()
  } finally {
    submitting.value = false
  }
}

const handleDelete = async (row: User) => {
  try {
    await ElMessageBox.confirm('确定要删除该用户吗？', '提示', { type: 'warning' })
    await deleteUser(row.id)
    ElMessage.success('删除成功')
    loadUsers()
  } catch { /* cancelled */ }
}

onMounted(() => {
  loadUsers()
  loadRoles()
})
</script>

<style scoped>
.users-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 40px;
}
</style>
