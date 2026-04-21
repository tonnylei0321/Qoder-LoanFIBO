<template>
  <div class="login-container">
    <!-- Animated Background -->
    <div class="login-bg">
      <div class="gradient-orb orb-1"></div>
      <div class="gradient-orb orb-2"></div>
      <div class="gradient-orb orb-3"></div>
      <div class="grid-pattern"></div>
    </div>
    
    <!-- Login Card -->
    <div class="login-wrapper">
      <div class="login-brand">
        <div class="brand-logo">
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
        <h1 class="brand-name">LoanFIBO</h1>
        <p class="brand-tagline">智能金融数据语义对齐平台</p>
      </div>
      
      <div class="login-card-glass">
        <div class="card-header">
          <h2>欢迎回来</h2>
          <p>请登录您的账户</p>
        </div>
        
        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          class="login-form"
          @keyup.enter="handleLogin"
        >
          <el-form-item prop="username">
            <div class="input-wrapper">
              <el-icon class="input-icon"><User /></el-icon>
              <el-input
                v-model="form.username"
                placeholder="用户名"
                size="large"
                class="custom-input"
                data-testid="login-username"
              />
            </div>
          </el-form-item>
          
          <el-form-item prop="password">
            <div class="input-wrapper">
              <el-icon class="input-icon"><Lock /></el-icon>
              <el-input
                v-model="form.password"
                type="password"
                placeholder="密码"
                size="large"
                class="custom-input"
                show-password
                data-testid="login-password"
              />
            </div>
          </el-form-item>
          
          <div class="form-options">
            <el-checkbox v-model="rememberMe">记住我</el-checkbox>
            <a href="#" class="forgot-link">忘记密码？</a>
          </div>
          
          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              @click="handleLogin"
              class="login-btn"
              data-testid="login-submit"
            >
              <span v-if="!loading">登 录</span>
              <span v-else>登录中...</span>
            </el-button>
          </el-form-item>
        </el-form>
        
        <div class="login-footer">
          <p>DDL 到 FIBO 本体语义对齐系统</p>
          <p class="version">v2.0.0</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)
const rememberMe = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '长度在 3 到 20 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 4, max: 20, message: '长度在 4 到 20 个字符', trigger: 'blur' },
  ],
}

const handleLogin = async () => {
  if (!formRef.value) return
  
  await formRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        const success = await authStore.login(form)
        if (success) {
          ElMessage.success('登录成功')
          router.push('/dashboard')
        } else {
          ElMessage.error('用户名或密码错误')
        }
      } catch (error) {
        ElMessage.error('登录失败，请稍后重试')
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: var(--bg-primary);
  position: relative;
  overflow: hidden;
  padding: 20px;
}

/* Animated Background */
.login-bg {
  position: fixed;
  inset: 0;
  z-index: 0;
  overflow: hidden;
}

.gradient-orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.5;
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
  left: 20%;
  animation: float 15s ease-in-out infinite reverse;
}

.orb-3 {
  width: 300px;
  height: 300px;
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  top: 40%;
  right: 10%;
  animation: float 18s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(30px, -30px) scale(1.1); }
  66% { transform: translate(-20px, 20px) scale(0.9); }
}

.grid-pattern {
  position: absolute;
  inset: 0;
  background-image: 
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 50px 50px;
}

/* Login Wrapper */
.login-wrapper {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  width: 100%;
  max-width: 420px;
}

/* Brand Section */
.login-brand {
  text-align: center;
}

.brand-logo {
  width: 80px;
  height: 80px;
  margin: 0 auto 16px;
}

.brand-logo svg {
  width: 100%;
  height: 100%;
  filter: drop-shadow(0 4px 20px rgba(102, 126, 234, 0.4));
}

.brand-name {
  font-size: 32px;
  font-weight: 700;
  margin: 0 0 8px 0;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.brand-tagline {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

/* Login Card */
.login-card-glass {
  width: 100%;
  background: var(--card-bg);
  backdrop-filter: blur(20px);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-xl);
  padding: 40px;
  box-shadow: var(--glass-shadow);
}

.card-header {
  text-align: center;
  margin-bottom: 32px;
}

.card-header h2 {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px 0;
}

.card-header p {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

/* Login Form */
.login-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 16px;
  color: var(--text-muted);
  font-size: 18px;
  z-index: 1;
}

.custom-input :deep(.el-input__wrapper) {
  padding-left: 44px;
  background: var(--bg-tertiary);
  box-shadow: 0 0 0 1px var(--border-color) inset;
  border-radius: var(--radius-md);
}

.custom-input :deep(.el-input__inner) {
  color: var(--text-primary);
  height: 48px;
}

.custom-input :deep(.el-input__inner::placeholder) {
  color: var(--text-muted);
}

/* Form Options */
.form-options {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.form-options :deep(.el-checkbox__label) {
  color: var(--text-secondary);
}

.form-options :deep(.el-checkbox__input.is-checked + .el-checkbox__label) {
  color: var(--primary-400);
}

.forgot-link {
  color: var(--primary-400);
  text-decoration: none;
  font-size: 14px;
  transition: color 0.2s;
}

.forgot-link:hover {
  color: var(--primary-300);
}

/* Login Button */
.login-btn {
  width: 100%;
  height: 48px;
  font-size: 16px;
  font-weight: 600;
  background: var(--gradient-primary);
  border: none;
  border-radius: var(--radius-md);
  box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
  transition: all 0.3s ease;
}

.login-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
}

/* Login Footer */
.login-footer {
  text-align: center;
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--divider-color);
}

.login-footer p {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

.login-footer .version {
  margin-top: 4px;
  font-family: var(--font-mono);
}

/* Responsive */
@media (max-width: 480px) {
  .login-card-glass {
    padding: 32px 24px;
  }
  
  .brand-name {
    font-size: 28px;
  }
  
  .card-header h2 {
    font-size: 20px;
  }
}
</style>
