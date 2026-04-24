<template>
  <div class="modern-layout" :data-theme="theme">
    <!-- Animated Background -->
    <div class="ambient-bg">
      <div class="gradient-orb orb-1"></div>
      <div class="gradient-orb orb-2"></div>
      <div class="gradient-orb orb-3"></div>
    </div>
    
    <!-- Drawer Overlay (hidden when pinned) -->
    <div v-if="!sidebarPinned" class="drawer-overlay" :class="{ visible: drawerOpen }" @click="closeDrawer"></div>

    <!-- Sidebar: pinned or drawer -->
    <aside class="modern-sidebar" :class="{ open: drawerOpen || sidebarPinned, pinned: sidebarPinned }">
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
          <span class="brand-text">LoanFIBO</span>
        </div>
        <button class="close-btn" @click="closeDrawer">
          <el-icon><Close /></el-icon>
        </button>
        <button class="pin-btn" @click="toggleSidebarPin" :title="sidebarPinned ? '取消固定（抽屉模式）' : '固定侧边栏（常驻）'" :class="{ active: sidebarPinned }">
          <el-icon><Finished v-if="sidebarPinned" /><Grid v-else /></el-icon>
        </button>
      </div>
      
      <nav class="sidebar-nav">
        <div class="nav-section">
          <div class="nav-label" @click="toggleSection('main')">
            <span>主菜单</span>
            <el-icon class="collapse-arrow" :class="{ rotated: isSectionCollapsed('main') }"><ArrowRight /></el-icon>
          </div>
          <div class="nav-items" v-show="!isSectionCollapsed('main')">
            <router-link v-if="authStore.canAccessMenu('dashboard')" to="/dashboard" class="nav-item" :class="{ active: $route.path === '/dashboard' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><DataLine /></el-icon>
              </div>
              <span class="nav-text">语义对齐看板</span>
              <div class="nav-glow"></div>
            </router-link>
          </div>
        </div>
        
        <div class="nav-section" v-if="authStore.canAccessMenu('ddl-files') || authStore.canAccessMenu('ttl-files') || authStore.canAccessMenu('jobs')">
          <div class="nav-label" @click="toggleSection('data')">
            <span>数据管理</span>
            <el-icon class="collapse-arrow" :class="{ rotated: isSectionCollapsed('data') }"><ArrowRight /></el-icon>
          </div>
          <div class="nav-items" v-show="!isSectionCollapsed('data')">
            <router-link v-if="authStore.canAccessMenu('ddl-files')" to="/files/ddl" class="nav-item" :class="{ active: $route.path === '/files/ddl' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Document /></el-icon>
              </div>
              <span class="nav-text">DDL 文件</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('ttl-files')" to="/files/ttl" class="nav-item" :class="{ active: $route.path === '/files/ttl' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Connection /></el-icon>
              </div>
              <span class="nav-text">TTL 文件</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('jobs')" to="/jobs" class="nav-item" :class="{ active: $route.path.includes('/jobs') }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><List /></el-icon>
              </div>
              <span class="nav-text">任务管理</span>
              <div class="nav-glow"></div>
            </router-link>
          </div>
        </div>
        
        <div class="nav-section" v-if="authStore.canAccessMenu('nlq-query') || authStore.canAccessMenu('rules-manager') || authStore.canAccessMenu('compile-status')">
          <div class="nav-label" @click="toggleSection('rules')">
            <span>规则引擎</span>
            <el-icon class="collapse-arrow" :class="{ rotated: isSectionCollapsed('rules') }"><ArrowRight /></el-icon>
          </div>
          <div class="nav-items" v-show="!isSectionCollapsed('rules')">
            <router-link v-if="authStore.canAccessMenu('nlq-query')" to="/rules/nlq-query" class="nav-item" :class="{ active: $route.path === '/rules/nlq-query' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Search /></el-icon>
              </div>
              <span class="nav-text">NLQ 查询</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('rules-manager')" to="/rules/manager" class="nav-item" :class="{ active: $route.path === '/rules/manager' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><SetUp /></el-icon>
              </div>
              <span class="nav-text">规则管理</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('compile-status')" to="/rules/compile-status" class="nav-item" :class="{ active: $route.path === '/rules/compile-status' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Monitor /></el-icon>
              </div>
              <span class="nav-text">编译状态</span>
              <div class="nav-glow"></div>
            </router-link>
          </div>
        </div>

        <div class="nav-section" v-if="authStore.canAccessMenu('reviews')">
          <div class="nav-label" @click="toggleSection('quality')">
            <span>质量控制</span>
            <el-icon class="collapse-arrow" :class="{ rotated: isSectionCollapsed('quality') }"><ArrowRight /></el-icon>
          </div>
          <div class="nav-items" v-show="!isSectionCollapsed('quality')">
            <router-link v-if="authStore.canAccessMenu('reviews')" to="/reviews" class="nav-item" :class="{ active: $route.path === '/reviews' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Check /></el-icon>
              </div>
              <span class="nav-text">稽核管理</span>
              <div class="nav-glow"></div>
            </router-link>
          </div>
        </div>

        <div class="nav-section" v-if="authStore.canAccessMenu('graph-explorer') || authStore.canAccessMenu('instances') || authStore.canAccessMenu('versions') || authStore.canAccessMenu('sync-tasks')">
          <div class="nav-label" @click="toggleSection('sync')">
            <span>图谱同步</span>
            <el-icon class="collapse-arrow" :class="{ rotated: isSectionCollapsed('sync') }"><ArrowRight /></el-icon>
          </div>
          <div class="nav-items" v-show="!isSectionCollapsed('sync')">
            <router-link v-if="authStore.canAccessMenu('graph-explorer')" to="/sync/graph-explorer" class="nav-item" :class="{ active: $route.path === '/sync/graph-explorer' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Connection /></el-icon>
              </div>
              <span class="nav-text">图谱浏览</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('instances')" to="/sync/instances" class="nav-item" :class="{ active: $route.path === '/sync/instances' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Monitor /></el-icon>
              </div>
              <span class="nav-text">实例管理</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('versions')" to="/sync/versions" class="nav-item" :class="{ active: $route.path === '/sync/versions' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Collection /></el-icon>
              </div>
              <span class="nav-text">版本管理</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('sync-tasks')" to="/sync/tasks" class="nav-item" :class="{ active: $route.path === '/sync/tasks' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Refresh /></el-icon>
              </div>
              <span class="nav-text">同步任务</span>
              <div class="nav-glow"></div>
            </router-link>
          </div>
        </div>
        
        <div class="nav-section" v-if="authStore.canAccessMenu('pre-loan') || authStore.canAccessMenu('post-loan') || authStore.canAccessMenu('supply-chain')">
          <div class="nav-label" @click="toggleSection('loan')">
            <span>信贷分析</span>
            <el-icon class="collapse-arrow" :class="{ rotated: isSectionCollapsed('loan') }"><ArrowRight /></el-icon>
          </div>
          <div class="nav-items" v-show="!isSectionCollapsed('loan')">
            <router-link v-if="authStore.canAccessMenu('pre-loan')" to="/loan-analysis/pre-loan" class="nav-item" :class="{ active: $route.path === '/loan-analysis/pre-loan' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><DocumentChecked /></el-icon>
              </div>
              <span class="nav-text">贷前尽调</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('post-loan')" to="/loan-analysis/post-loan" class="nav-item" :class="{ active: $route.path === '/loan-analysis/post-loan' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Monitor /></el-icon>
              </div>
              <span class="nav-text">贷后监控</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('supply-chain')" to="/loan-analysis/supply-chain" class="nav-item" :class="{ active: $route.path === '/loan-analysis/supply-chain' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Share /></el-icon>
              </div>
              <span class="nav-text">供应链金融</span>
              <div class="nav-glow"></div>
            </router-link>
          </div>
        </div>

        <div class="nav-section" v-if="authStore.canAccessMenu('org-manager') || authStore.canAccessMenu('auth-scopes')">
          <div class="nav-label" @click="toggleSection('org')">
            <span>主体管理</span>
            <el-icon class="collapse-arrow" :class="{ rotated: isSectionCollapsed('org') }"><ArrowRight /></el-icon>
          </div>
          <div class="nav-items" v-show="!isSectionCollapsed('org')">
            <router-link v-if="authStore.canAccessMenu('org-manager')" to="/org/orgs" class="nav-item" :class="{ active: $route.path === '/org/orgs' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><OfficeBuilding /></el-icon>
              </div>
              <span class="nav-text">融资企业</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('auth-scopes')" to="/org/auth-scopes" class="nav-item" :class="{ active: $route.path === '/org/auth-scopes' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Lock /></el-icon>
              </div>
              <span class="nav-text">授权项管理</span>
              <div class="nav-glow"></div>
            </router-link>
          </div>
        </div>
        
        <div class="nav-section" v-if="authStore.canAccessMenu('agent-orgs') || authStore.canAccessMenu('agent-status') || authStore.canAccessMenu('agent-audit')">
          <div class="nav-label" @click="toggleSection('agent')">
            <span>代理管理</span>
            <el-icon class="collapse-arrow" :class="{ rotated: isSectionCollapsed('agent') }"><ArrowRight /></el-icon>
          </div>
          <div class="nav-items" v-show="!isSectionCollapsed('agent')">
            <router-link v-if="authStore.canAccessMenu('agent-orgs')" to="/agent/orgs" class="nav-item" :class="{ active: $route.path === '/agent/orgs' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><OfficeBuilding /></el-icon>
              </div>
              <span class="nav-text">企业管理</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('agent-status')" to="/agent/status" class="nav-item" :class="{ active: $route.path === '/agent/status' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Connection /></el-icon>
              </div>
              <span class="nav-text">代理状态</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('agent-audit')" to="/agent/audit" class="nav-item" :class="{ active: $route.path === '/agent/audit' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><List /></el-icon>
              </div>
              <span class="nav-text">审计日志</span>
              <div class="nav-glow"></div>
            </router-link>
          </div>
        </div>

        <div class="nav-section" v-if="authStore.canAccessMenu('users') || authStore.canAccessMenu('roles') || authStore.canAccessMenu('permissions') || authStore.canAccessMenu('settings')">
          <div class="nav-label" @click="toggleSection('system')">
            <span>系统</span>
            <el-icon class="collapse-arrow" :class="{ rotated: isSectionCollapsed('system') }"><ArrowRight /></el-icon>
          </div>
          <div class="nav-items" v-show="!isSectionCollapsed('system')">
            <router-link v-if="authStore.canAccessMenu('users')" to="/users" class="nav-item" :class="{ active: $route.path === '/users' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><User /></el-icon>
              </div>
              <span class="nav-text">用户管理</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('roles')" to="/roles" class="nav-item" :class="{ active: $route.path === '/roles' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Avatar /></el-icon>
              </div>
              <span class="nav-text">角色管理</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('permissions')" to="/permissions" class="nav-item" :class="{ active: $route.path === '/permissions' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Lock /></el-icon>
              </div>
              <span class="nav-text">权限管理</span>
              <div class="nav-glow"></div>
            </router-link>
            <router-link v-if="authStore.canAccessMenu('settings')" to="/settings" class="nav-item" :class="{ active: $route.path === '/settings' }" @click="closeDrawer">
              <div class="nav-icon">
                <el-icon><Setting /></el-icon>
              </div>
              <span class="nav-text">系统设置</span>
              <div class="nav-glow"></div>
            </router-link>
          </div>
        </div>
      </nav>
      
      <div class="sidebar-footer">
        <button class="theme-toggle" @click="toggleTheme">
          <el-icon><Sunny v-if="theme === 'dark'" /><Moon v-else /></el-icon>
          <span >{{ theme === 'dark' ? '浅色模式' : '深色模式' }}</span>
        </button>
      </div>
    </aside>
    
    <!-- Main Content -->
    <main class="modern-main">
      <!-- Header -->
      <header class="modern-header">
        <div class="header-left">
          <button class="menu-btn" :class="{ pinned: sidebarPinned }" @click="sidebarPinned ? toggleSidebarPin() : (drawerOpen = true)" :title="sidebarPinned ? '取消固定侧边栏' : '打开菜单'">
            <el-icon><Operation /></el-icon>
          </button>
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
              <div class="user-info" >
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

// Theme and drawer state
const theme = ref('dark')
const drawerOpen = ref(false)

// Sidebar pinned (always visible) mode
const sidebarPinned = ref(false)

const toggleSidebarPin = () => {
  sidebarPinned.value = !sidebarPinned.value
  localStorage.setItem('sidebarPinned', sidebarPinned.value ? '1' : '0')
  if (sidebarPinned.value) drawerOpen.value = false
}

// Close drawer (no-op when pinned)
const closeDrawer = () => {
  if (!sidebarPinned.value) drawerOpen.value = false
}

// Collapsible nav sections
const collapsedSections = ref<Set<string>>(new Set())

const toggleSection = (section: string) => {
  if (collapsedSections.value.has(section)) {
    collapsedSections.value.delete(section)
  } else {
    collapsedSections.value.add(section)
  }
}

const isSectionCollapsed = (section: string) => collapsedSections.value.has(section)

// Toggle theme
const toggleTheme = () => {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
  document.documentElement.setAttribute('data-theme', theme.value)
  localStorage.setItem('theme', theme.value)
}

// Initialize theme and pinned state from localStorage
onMounted(() => {
  const savedTheme = localStorage.getItem('theme') || 'dark'
  theme.value = savedTheme
  document.documentElement.setAttribute('data-theme', savedTheme)

  const savedPinned = localStorage.getItem('sidebarPinned')
  sidebarPinned.value = savedPinned === '1'
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
  'graph-explorer': '图谱浏览',
  'instances': '实例管理',
  'versions': '版本管理',
  'sync-tasks': '同步任务',
  'org-manager': '融资企业管理',
  'auth-scopes': '授权项管理',
  'agent-orgs': '企业管理',
  'agent-status': '代理状态',
  'agent-audit': '审计日志',
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

/* Drawer Overlay */
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  z-index: 99;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
}

.drawer-overlay.visible {
  opacity: 1;
  pointer-events: auto;
}

/* Drawer Sidebar */
.modern-sidebar {
  width: 280px;
  background: var(--bg-secondary);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  z-index: 100;
  transform: translateX(-100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 4px 0 24px rgba(0, 0, 0, 0.15);
}

.modern-sidebar.open {
  transform: translateX(0);
}

/* Pinned (always visible) — sits in normal flow, no overlay */
.modern-sidebar.pinned {
  position: relative;
  transform: none !important;
  height: 100vh;
  flex-shrink: 0;
  box-shadow: none;
  border-right: 1px solid var(--border-color);
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

.close-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: all 0.2s ease;
}

.close-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

/* Pin button */
.pin-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  transition: all 0.2s ease;
}

.pin-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.pin-btn.active {
  color: var(--primary-500);
  background: rgba(102, 126, 234, 0.12);
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
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--text-secondary);
  padding: 8px 12px;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: all 0.2s ease;
  user-select: none;
}

.nav-label:hover {
  color: var(--text-secondary);
  background: var(--bg-tertiary);
}

.collapse-arrow {
  font-size: 0.75rem;
  transition: transform 0.25s ease;
}

.collapse-arrow.rotated {
  transform: rotate(90deg);
}

.nav-items {
  overflow: hidden;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  position: relative;
  transition: all 0.2s ease;
  margin-bottom: 2px;
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
  font-size: 0.85rem;
  font-weight: 500;
  white-space: nowrap;
  color: var(--text-secondary);
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
  min-width: 0; /* prevent flex overflow when sidebar is pinned */
}

/* Header */
.modern-header {
  height: 64px;
  background: var(--bg-secondary);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  gap: 20px;
}

/* Menu Button */
.menu-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  margin-right: 8px;
  font-size: 1.1rem;
}

.menu-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.menu-btn.pinned {
  color: var(--primary-500);
  background: rgba(102, 126, 234, 0.12);
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
  font-size: 0.85rem;
  color: var(--text-primary);
}

.header-center {
  flex: 1;
  max-width: 400px;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
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
  font-size: 0.85rem;
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
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.header-btn:hover {
  background: var(--bg-tertiary);
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
  gap: 10px;
  padding: 5px 12px 5px 5px;
  background: transparent;
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: all 0.2s ease;
}

.user-profile:hover {
  background: var(--bg-tertiary);
}

.avatar {
  width: 30px;
  height: 30px;
  background: var(--gradient-primary);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.85rem;
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
  line-height: 1.2;
}

.user-role {
  font-size: 0.75rem;
  color: var(--text-secondary);
  line-height: 1.2;
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

/* Responsive — drawer works the same on all sizes */
</style>
