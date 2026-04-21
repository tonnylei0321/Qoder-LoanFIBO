<template>
  <div class="modern-layout" :data-theme="theme">
    <!-- Animated Background -->
    <div class="ambient-bg">
      <div class="gradient-orb orb-1"></div>
      <div class="gradient-orb orb-2"></div>
      <div class="gradient-orb orb-3"></div>
    </div>
    
    <!-- Sidebar -->
    <aside class="modern-sidebar" :class="{ collapsed: sidebarCollapsed }">
      <div class="sidebar-header">
        <div class="brand">
          <div class="brand-icon">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L2 7L12 12L22 7L12 2Z" fill="url(#brand-gradient)"/>
              <path d="M2 17L12 22L22 17" stroke="url(#brand-gradient)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M2 12L12 17L22 12" stroke="url(#brand-gradient)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <defs>
                <linearGradient id="brand-gradient" x1="2" y1="12" x2="22" y2="12" gradientUnits="userSpaceOnUse">
                  <stop stop-color="#667eea"/>
                  <stop offset="1" stop-color="#764ba2"/>
                </linearGradient>
              </defs>
            </svg>
          </div>
          <span class="brand-text" v-show="!sidebarCollapsed">LoanFIBO</span>
        </div>
        <button class="collapse-btn" @click="sidebarCollapsed = !sidebarCollapsed">
          <el-icon><Fold v-if="!sidebarCollapsed" /><Expand v-else /></el-icon>
        </button>
      </div>
      
      <nav class="sidebar-nav">
        <div class="nav-section">
          <div class="nav-label" v-show="!sidebarCollapsed">主菜单</div>
          <router-link to="/dashboard" class="nav-item" :class="{ active: $route.path === '/dashboard' }">
            <div class="nav-icon">
              <el-icon><DataLine /></el-icon>
            </div>
            <span class="nav-text" v-show="!sidebarCollapsed">语义对齐看板</span>
            <div class="nav-glow"></div>
          </router-link>
        </div>
        
        <div class="nav-section">
          <div class="nav-label" v-show="!sidebarCollapsed">数据管理</div>
          <router-link to="/files/ddl" class="nav-item" :class="{ active: $route.path === '/files/ddl' }">
            <div class="nav-icon">
              <el-icon><Document /></el-icon>
            </div>
            <span class="nav-text" v-show="!sidebarCollapsed">DDL 文件</span>
            <div class="nav-glow"></div>
          </router-link>
          <router-link to="/files/ttl" class="nav-item" :class="{ active: $route.path === '/files/ttl' }">
            <div class="nav-icon">
              <el-icon><Connection /></el-icon>
            </div>
            <span class="nav-text" v-show="!sidebarCollapsed">TTL 文件</span>
            <div class="nav-glow"></div>
          </router-link>
          <router-link to="/jobs" class="nav-item" :class="{ active: $route.path.includes('/jobs') }">
            <div class="nav-icon">
              <el-icon><List /></el-icon>
            </div>
            <span class="nav-text" v-show="!sidebarCollapsed">任务管理</span>
            <div class="nav-glow"></div>
          </router-link>
        </div>
        
        <div class="nav-section">
          <div class="nav-label" v-show="!sidebarCollapsed">规则引擎</div>
          <router-link to="/rules/nlq-query" class="nav-item" :class="{ active: $route.path === '/rules/nlq-query' }">
            <div class="nav-icon">
              <el-icon><Search /></el-icon>
            </div>
            <span class="nav-text" v-show="!sidebarCollapsed">NLQ 查询</span>
            <div class="nav-glow"></div>
          </router-link>
          <router-link to="/rules/manager" class="nav-item" :class="{ active: $route.path === '/rules/manager' }">
            <div class="nav-icon">
              <el-icon><SetUp /></el-icon>
            </div>
            <span class="nav-text" v-show="!sidebarCollapsed">规则管理</span>
            <div class="nav-glow"></div>
          </router-link>
          <router-link to="/rules/compile-status" class="nav-item" :class="{ active: $route.path === '/rules/compile-status' }">
            <div class="nav-icon">
              <el-icon><Monitor /></el-icon>
            </div>
            <span class="nav-text" v-show="!sidebarCollapsed">编译状态</span>
            <div class="nav-glow"></div>
          </router-link>
        </div>

        <div class="nav-section">
          <div class="nav-label" v-show="!sidebarCollapsed">质量控制</div>
          <router-link to="/reviews" class="nav-item" :class="{ active: $route.path === '/reviews' }">
            <div class="nav-icon">
              <el-icon><Check /></el-icon>
            </div>
            <span class="nav-text" v-show="!sidebarCollapsed">稽核管理</span>
            <div class="nav-glow"></div>
          </router-link>
        </div>
        
        <div class="nav-section">
          <div class="nav-label" v-show="!sidebarCollapsed">信贷分析</div>
          <router-link to="/loan-analysis/pre-loan" class="nav-item" :class="{ active: $route.path === '/loan-analysis/pre-loan' }">
            <div class="nav-icon">
              <el-icon><DocumentChecked /></el-icon>
            </div>
            <span class="nav-text" v-show="!sidebarCollapsed">贷前尽调</span>
            <div class="nav-glow"></div>
          </router-link>
          <router-link to="/loan-analysis/post-loan" class="nav-item" :class="{ active: $route.path === '/loan-analysis/post-loan' }">
            <div class="nav-icon">
              <el-icon><Monitor /></el-icon>
            </div>
            <span class="nav-text" v-show="!sidebarCollapsed">贷后监控</span>
            <div class="nav-glow"></div>
          </router-link>
          <router-link to="/loan-analysis/supply-chain" class="nav-item" :class="{ active: $route.path === '/loan-analysis/supply-chain' }">
            <div class="nav-icon">
              <el-icon><Share /></el-icon>
            </div>
            <span class="nav-text" v-show="!sidebarCollapsed">供应链金融</span>
            <div class="nav-glow"></div>
          </router-link>
        </div>
        
        <div class="nav-section" v-if="authStore.isAdmin">
          <div class="nav-label" v-show="!sidebarCollapsed">系统</div>
          <router-link to="/users" class="nav-item" :class="{ active: $route.path === '/users' }">
            <div class="nav-icon">
              <el-icon><User /></el-icon>
            </div>
            <span class="nav-text" v-show="!sidebarCollapsed">用户管理</span>
            <div class="nav-glow"></div>
          </router-link>
          <router-link to="/settings" class="nav-item" :class="{ active: $route.path === '/settings' }">
            <div class="nav-icon">
              <el-icon><Setting /></el-icon>
            </div>
            <span class="nav-text" v-show="!sidebarCollapsed">系统设置</span>
            <div class="nav-glow"></div>
          </router-link>
        </div>
      </nav>
      
      <div class="sidebar-footer">
        <button class="theme-toggle" @click="toggleTheme">
          <el-icon><Sunny v-if="theme === 'dark'" /><Moon v-else /></el-icon>
          <span v-show="!sidebarCollapsed">{{ theme === 'dark' ? '浅色模式' : '深色模式' }}</span>
        </button>
      </div>
    </aside>
    
    <!-- Main Content -->
    <main class="modern-main">
      <!-- Header -->
      <header class="modern-header">
        <div class="header-left">
          <div class="breadcrumb">
            <router-link to="/dashboard" class="breadcrumb-home">
              <el-icon><HomeFilled /></el-icon>
            </router-link>
            <template v-if="$route.name !== 'dashboard'">
              <span class="breadcrumb-separator">/</span>
              <span class="breadcrumb-current">{{ routeTitle }}</span>
            </template>
          </div>
        </div>
        
        <div class="header-center">
          <div class="search-box">
            <el-icon><Search /></el-icon>
            <input type="text" placeholder="搜索..." />
          </div>
        </div>
        
        <div class="header-right">
          <button class="header-btn">
            <el-icon><Bell /></el-icon>
            <span class="notification-dot"></span>
          </button>
          
          <el-dropdown @command="handleCommand" trigger="click">
            <div class="user-profile">
              <div class="avatar">
                {{ authStore.user?.username?.charAt(0).toUpperCase() || 'U' }}
              </div>
              <div class="user-info" v-show="!sidebarCollapsed">
                <div class="user-name">{{ authStore.user?.username || 'User' }}</div>
                <div class="user-role">{{ authStore.isAdmin ? '管理员' : '用户' }}</div>
              </div>
              <el-icon class="dropdown-icon"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu class="modern-dropdown">
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon> 个人资料
                </el-dropdown-item>
                <el-dropdown-item command="settings">
                  <el-icon><Setting /></el-icon> 系统设置
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>
      
      <!-- Content Area -->
      <div class="content-wrapper">
        <router-view v-slot="{ Component }">
          <transition name="page" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

// Theme and sidebar state
const theme = ref('dark')
const sidebarCollapsed = ref(false)

// Toggle theme
const toggleTheme = () => {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  document.documentElement.setAttribute('data-theme', theme.value)
  localStorage.setItem('theme', theme.value)
}

// Initialize theme from localStorage
onMounted(() => {
  const savedTheme = localStorage.getItem('theme') || 'dark'
  theme.value = savedTheme
  document.documentElement.setAttribute('data-theme', savedTheme)
})

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const routeTitleMap: Record<string, string> = {
  'ddl-files': 'DDL 文件管理',
  'ttl-files': 'TTL 文件管理',
  'jobs': '任务管理',
  'new-job': '新建任务',
  'reviews': '稽核管理',
  'users': '用户管理',
  'settings': '系统设置',
  'job-dashboard': '任务详情',
  'pre-loan': '贷前尽调',
  'post-loan': '贷后监控',
  'supply-chain': '供应链金融',
  'nlq-query': 'NLQ 查询',
  'rules-manager': '规则管理',
  'compile-status': '编译状态',
}

const routeTitle = computed(() => {
  return routeTitleMap[route.name as string] || ''
})

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
/* Modern Layout Styles */
.modern-layout {
  display: flex;
  min-height: 100vh;
  background: var(--bg-primary);
  position: relative;
  overflow: hidden;
}

/* Ambient Background */
.ambient-bg {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}

.gradient-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.4;
}

.orb-1 {
  width: 600px;
  height: 600px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  top: -200px;
  right: -200px;
  animation: float 20s ease-in-out infinite;
}

.orb-2 {
  width: 400px;
  height: 400px;
  background: linear-gradient(135deg, #00d4ff 0%, #00b8d4 100%);
  bottom: -100px;
  left: 30%;
  animation: float 15s ease-in-out infinite reverse;
}

.orb-3 {
  width: 300px;
  height: 300px;
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  top: 40%;
  left: -100px;
  animation: float 18s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -30px) scale(1.1); }
  66% { transform: translate(-20px, 20px) scale(0.9); }
}

/* Sidebar */
.modern-sidebar {
  width: 260px;
  background: var(--sidebar-bg);
  backdrop-filter: blur(20px);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 10;
  transition: width 0.3s ease;
}

.modern-sidebar.collapsed {
  width: 80px;
}

.sidebar-header {
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--divider-color);
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-icon {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
}

.brand-icon svg {
  width: 100%;
  height: 100%;
}

.brand-text {
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 700;
  background: var(--gradient-primary);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  white-space: nowrap;
}

.collapse-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: all 0.2s ease;
}

.collapse-btn:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

/* Navigation */
.sidebar-nav {
  flex: 1;
  padding: 16px 12px;
  overflow-y: auto;
}

.nav-section {
  margin-bottom: 24px;
}

.nav-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  padding: 0 12px;
  margin-bottom: 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  position: relative;
  transition: all 0.2s ease;
  margin-bottom: 4px;
}

.nav-item:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--gradient-primary);
  color: white;
}

.nav-item.active .nav-icon {
  color: white;
}

.nav-icon {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.nav-text {
  font-size: 0.9rem;
  font-weight: 500;
  white-space: nowrap;
}

.nav-glow {
  position: absolute;
  inset: 0;
  border-radius: var(--radius-md);
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
}

.nav-item:hover .nav-glow {
  opacity: 1;
  box-shadow: 0 0 20px rgba(102, 126, 234, 0.3);
}

/* Sidebar Footer */
.sidebar-footer {
  padding: 16px;
  border-top: 1px solid var(--divider-color);
}

.theme-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: none;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.theme-toggle:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

/* Main Content */
.modern-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 5;
  overflow: hidden;
}

/* Header */
.modern-header {
  height: 72px;
  background: var(--header-bg);
  backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  gap: 24px;
}

.header-left {
  display: flex;
  align-items: center;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 12px;
}

.breadcrumb-home {
  color: var(--text-secondary);
  text-decoration: none;
  padding: 8px;
  border-radius: var(--radius-sm);
  transition: all 0.2s ease;
}

.breadcrumb-home:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.breadcrumb-separator {
  color: var(--text-muted);
}

.breadcrumb-current {
  font-weight: 500;
  color: var(--text-primary);
}

.header-center {
  flex: 1;
  max-width: 400px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: var(--bg-tertiary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  transition: all 0.2s ease;
}

.search-box:focus-within {
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px rgba(24, 144, 255, 0.1);
}

.search-box input {
  flex: 1;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 0.9rem;
  outline: none;
}

.search-box input::placeholder {
  color: var(--text-muted);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-btn {
  position: relative;
  width: 40px;
  height: 40px;
  border: none;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.header-btn:hover {
  background: var(--bg-elevated);
  color: var(--text-primary);
}

.notification-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 8px;
  height: 8px;
  background: var(--danger);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--danger);
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px 6px 6px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all 0.2s ease;
}

.user-profile:hover {
  background: var(--bg-elevated);
}

.avatar {
  width: 32px;
  height: 32px;
  background: var(--gradient-primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.9rem;
  color: white;
}

.user-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.user-name {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-primary);
}

.user-role {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.dropdown-icon {
  color: var(--text-muted);
  font-size: 0.8rem;
}

/* Content Wrapper */
.content-wrapper {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  position: relative;
}

/* Page Transitions */
.page-enter-active,
.page-leave-active {
  transition: all 0.3s ease;
}

.page-enter-from {
  opacity: 0;
  transform: translateY(20px);
}

.page-leave-to {
  opacity: 0;
  transform: translateY(-20px);
}

/* Modern Dropdown */
:deep(.modern-dropdown) {
  background: var(--bg-secondary) !important;
  border: 1px solid var(--border-color) !important;
  border-radius: var(--radius-lg) !important;
  box-shadow: var(--glass-shadow) !important;
  padding: 8px !important;
}

:deep(.modern-dropdown .el-dropdown-menu__item) {
  color: var(--text-secondary) !important;
  border-radius: var(--radius-md) !important;
  padding: 10px 16px !important;
  display: flex;
  align-items: center;
  gap: 10px;
}

:deep(.modern-dropdown .el-dropdown-menu__item:hover) {
  background: var(--bg-tertiary) !important;
  color: var(--text-primary) !important;
}

:deep(.modern-dropdown .el-dropdown-menu__item .el-icon) {
  font-size: 1.1rem;
}

/* Responsive */
@media (max-width: 768px) {
  .modern-sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    transform: translateX(-100%);
  }
  
  .modern-sidebar.open {
    transform: translateX(0);
  }
  
  .header-center {
    display: none;
  }
}
</style>
