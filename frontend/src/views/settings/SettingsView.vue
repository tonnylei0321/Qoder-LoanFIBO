<template>
  <div class="settings">
    <div class="page-header">
      <h1>系统设置</h1>
    </div>

    <el-card>
      <el-tabs v-model="activeTab">
        <el-tab-pane label="个人信息" name="profile">
          <el-form :model="profileForm" label-width="100px" style="max-width: 500px">
            <el-form-item label="用户名">
              <el-input v-model="profileForm.username" disabled />
            </el-form-item>
            <el-form-item label="当前密码">
              <el-input v-model="profileForm.currentPassword" type="password" show-password />
            </el-form-item>
            <el-form-item label="新密码">
              <el-input v-model="profileForm.newPassword" type="password" show-password />
            </el-form-item>
            <el-form-item label="确认密码">
              <el-input v-model="profileForm.confirmPassword" type="password" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" @click="updateProfile">保存修改</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane label="系统配置" name="system">
          <el-empty description="系统配置功能开发中" />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()
const activeTab = ref('profile')

const profileForm = reactive({
  username: '',
  currentPassword: '',
  newPassword: '',
  confirmPassword: '',
})

const updateProfile = () => {
  if (profileForm.newPassword && profileForm.newPassword !== profileForm.confirmPassword) {
    ElMessage.error('两次输入的密码不一致')
    return
  }
  ElMessage.success('保存成功')
}

onMounted(() => {
  profileForm.username = authStore.user?.username || ''
})
</script>

<style scoped>
.settings {
  padding-bottom: 40px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}
</style>
