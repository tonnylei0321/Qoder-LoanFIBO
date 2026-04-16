<template>
  <el-container class="main-layout">
    <!-- Sidebar -->
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <el-icon size="28"><Connection /></el-icon>
        <span class="logo-text">LoanFIBO</span>
      </div>
      
      <el-menu
        :default-active="$route.path"
        router
        class="sidebar-menu"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
      >
        <el-menu-item index="/dashboard">
          <el-icon><DataLine /></el-icon>
          <span>语义对齐看板</span>
        </el-menu-item>
        
        <el-sub-menu index="/files">
          <template #title>
            <el-icon><Document /></el-icon>
            <span>文件管理</span>
          </template>
          <el-menu-item index="/files/ddl">DDL 版本管理</el-menu-item>
          <el-menu-item index="/files/ttl">TTL 版本管理</el-menu-item>
        </el-sub-menu>
        
        <el-menu-item index="/jobs">
          <el-icon><List /></el-icon>
          <span>任务管理</span>
        </el-menu-item>
        
        <el-menu-item index="/reviews">
          <el-icon><Check /></el-icon>
          <span>稽核管理</span>
        </el-menu-item>
        
        <el-menu-item index="/users" v-if="authStore.isAdmin">
          <el-icon><User /></el-icon>
          <span>用户管理</span>
        </el-menu-item>
        
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    
    <!-- Main Content -->
    <el-container>
      <!-- Header -->
      <el-header class="header">
        <div class="header-left">
          <breadcrumb />
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-info">
              <el-icon><User /></el-icon>
              {{ authStore.user?.username || 'User' }}
              <el-icon class="el-icon--right"><arrow-down /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人资料</el-dropdown-item>
                <el-dropdown-item command="settings">系统设置</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <!-- Content -->
      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const handleCommand = async (command: string) => {
  switch (command) {
    case 'profile':
      router.push('/settings')
      break
    case 'settings':
      router.push('/settings')
      break
    case 'logout':
      try {
        await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning',
        })
        authStore.logout()
        router.push('/login')
        ElMessage.success('已退出登录')
      } catch {
        // User cancelled
      }
      break
  }
}
</script>

<style scoped>
.main-layout {
  height: 100vh;
}

.sidebar {
  background-color: #304156;
  color: #fff;
}

.logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  border-bottom: 1px solid #1f2d3d;
}

.logo-text {
  font-size: 20px;
  font-weight: 600;
  color: #fff;
}

.sidebar-menu {
  border-right: none;
}

.header {
  background-color: #fff;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  color: #606266;
}

.main-content {
  background-color: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
