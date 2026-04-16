<template>
  <div class="users">
    <div class="page-header">
      <h1>用户管理</h1>
      <el-button type="primary" @click="showAddDialog = true">
        <el-icon><Plus /></el-icon>
        添加用户
      </el-button>
    </div>

    <el-card>
      <el-table :data="users" v-loading="loading" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="username" label="用户名" width="150" />
        <el-table-column prop="role" label="角色" width="120">
          <template #default="{ row }">
            <el-tag :type="getRoleType(row.role)" size="small">
              {{ getRoleText(row.role) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="180" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="editUser(row)">
              编辑
            </el-button>
            <el-button type="danger" link size="small" @click="deleteUser(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Add/Edit Dialog -->
    <el-dialog
      v-model="showAddDialog"
      :title="editingUser ? '编辑用户' : '添加用户'"
      width="500px"
    >
      <el-form :model="userForm" label-width="80px">
        <el-form-item label="用户名" required>
          <el-input v-model="userForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码" :required="!editingUser">
          <el-input
            v-model="userForm.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="角色" required>
          <el-select v-model="userForm.role" placeholder="请选择角色" style="width: 100%">
            <el-option label="管理员" value="admin" />
            <el-option label="操作员" value="operator" />
            <el-option label="访客" value="viewer" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showAddDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitUser">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { User } from '@/types'

const loading = ref(false)
const showAddDialog = ref(false)
const submitting = ref(false)
const editingUser = ref<User | null>(null)
const users = ref<User[]>([])

const userForm = reactive({
  username: '',
  password: '',
  role: 'operator' as 'admin' | 'operator' | 'viewer',
})

const getRoleType = (role: string) => {
  const map: Record<string, string> = {
    admin: 'danger',
    operator: 'primary',
    viewer: 'info',
  }
  return map[role] || 'info'
}

const getRoleText = (role: string) => {
  const map: Record<string, string> = {
    admin: '管理员',
    operator: '操作员',
    viewer: '访客',
  }
  return map[role] || role
}

const loadUsers = async () => {
  loading.value = true
  // TODO: Call API
  users.value = [
    {
      id: 1,
      username: 'admin',
      role: 'admin',
      createdAt: '2026-04-15T00:00:00Z',
    },
  ]
  loading.value = false
}

const editUser = (row: User) => {
  editingUser.value = row
  userForm.username = row.username
  userForm.role = row.role
  userForm.password = ''
  showAddDialog.value = true
}

const deleteUser = async (row: User) => {
  try {
    await ElMessageBox.confirm('确定要删除该用户吗？', '提示', {
      type: 'warning',
    })
    ElMessage.success('删除成功')
    loadUsers()
  } catch {
    // Cancelled
  }
}

const submitUser = async () => {
  if (!userForm.username) {
    ElMessage.warning('请输入用户名')
    return
  }
  if (!editingUser.value && !userForm.password) {
    ElMessage.warning('请输入密码')
    return
  }

  submitting.value = true
  // TODO: Call API
  setTimeout(() => {
    ElMessage.success(editingUser.value ? '更新成功' : '添加成功')
    showAddDialog.value = false
    editingUser.value = null
    userForm.username = ''
    userForm.password = ''
    userForm.role = 'operator'
    loadUsers()
    submitting.value = false
  }, 500)
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.users {
  padding-bottom: 40px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}
</style>
