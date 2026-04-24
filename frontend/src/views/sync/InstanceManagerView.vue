<template>
  <div class="instance-manager">
    <!-- Header -->
    <div class="page-header-modern">
      <div class="header-content">
        <div class="header-icon">
          <el-icon><Monitor /></el-icon>
        </div>
        <div class="header-text">
          <h1>实例管理</h1>
          <p class="subtitle">GraphDB 实例注册与健康监控</p>
        </div>
      </div>
      <el-button type="primary" class="btn-glow" @click="openCreateDialog">
        <el-icon><Plus /></el-icon>
        新增实例
      </el-button>
    </div>

    <!-- Instance Cards -->
    <div class="instance-grid" v-loading="loading">
      <div v-for="inst in instances" :key="inst.id" class="instance-card">
        <div class="card-header">
          <div class="instance-name">{{ inst.name }}</div>
          <el-tag :type="inst.is_active ? 'success' : 'info'" effect="dark" round size="small">
            {{ inst.is_active ? '活跃' : '停用' }}
          </el-tag>
        </div>
        <div class="card-body">
          <div class="info-row">
            <span class="info-label">服务器</span>
            <span class="info-value url-value">{{ inst.server_url }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">仓库 ID</span>
            <span class="info-value mono">{{ inst.repo_id }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">命名空间</span>
            <span class="info-value mono">{{ inst.namespace_prefix }}</span>
          </div>
          <div class="info-row" v-if="inst.domain">
            <span class="info-label">领域</span>
            <span class="info-value">{{ inst.domain }}</span>
          </div>
          <!-- Health Status -->
          <div class="health-row" v-if="healthMap[inst.id]">
            <span class="info-label">健康状态</span>
            <el-tag
              :type="getHealthTagType(healthMap[inst.id]!.status)"
              effect="plain"
              size="small"
            >
              {{ healthMap[inst.id]!.status }}
            </el-tag>
            <span v-if="healthMap[inst.id]!.statement_count" class="stmt-count">
              {{ healthMap[inst.id]!.statement_count }} 三元组
            </span>
          </div>
        </div>
        <div class="card-actions">
          <el-button size="small" @click="checkHealth(inst.id)" :loading="healthChecking === inst.id">
            <el-icon><Monitor /></el-icon> 健康检查
          </el-button>
          <el-button size="small" @click="openEditDialog(inst)">编辑</el-button>
          <el-button size="small" type="danger" plain @click="handleDelete(inst)">删除</el-button>
        </div>
      </div>

      <el-empty v-if="!loading && instances.length === 0" description="暂无 GraphDB 实例" />
    </div>

    <!-- Create/Edit Dialog -->
    <el-dialog v-model="showDialog" :title="editingId ? '编辑实例' : '新增实例'" width="520px" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px">
        <el-form-item label="实例名称" required>
          <el-input v-model="form.name" placeholder="如: Production GraphDB" />
        </el-form-item>
        <el-form-item label="服务器 URL" required>
          <el-input v-model="form.server_url" placeholder="如: http://localhost:7200" />
        </el-form-item>
        <el-form-item label="仓库 ID" required>
          <el-input v-model="form.repo_id" placeholder="如: loanfibo" />
        </el-form-item>
        <el-form-item label="命名空间前缀">
          <el-input v-model="form.namespace_prefix" placeholder="loanfibo" />
        </el-form-item>
        <el-form-item label="领域">
          <el-input v-model="form.domain" placeholder="如: finance" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSave" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { graphdbSyncApi, type GraphDBInstance, type InstanceCreateForm, type InstanceHealth } from '@/api/graphdbSync'
import { ElMessage, ElMessageBox } from 'element-plus'

const loading = ref(false)
const instances = ref<GraphDBInstance[]>([])
const healthMap = ref<Record<string, InstanceHealth>>({})
const healthChecking = ref<string | null>(null)

const showDialog = ref(false)
const saving = ref(false)
const editingId = ref<string | null>(null)
const form = ref<InstanceCreateForm>({
  name: '',
  server_url: '',
  repo_id: '',
  namespace_prefix: 'loanfibo',
  domain: '',
})

async function loadInstances() {
  loading.value = true
  try {
    instances.value = await graphdbSyncApi.listInstances()
  } catch {
    ElMessage.error('加载实例列表失败')
  } finally {
    loading.value = false
  }
}

async function checkHealth(id: string) {
  healthChecking.value = id
  try {
    const health = await graphdbSyncApi.checkHealth(id)
    healthMap.value[id] = health
    if (health.status === 'healthy') {
      ElMessage.success('实例健康')
    } else {
      ElMessage.warning(`实例状态: ${health.status}`)
    }
  } catch {
    ElMessage.error('健康检查失败')
  } finally {
    healthChecking.value = null
  }
}

function openCreateDialog() {
  editingId.value = null
  form.value = { name: '', server_url: '', repo_id: '', namespace_prefix: 'loanfibo', domain: '' }
  showDialog.value = true
}

function openEditDialog(inst: GraphDBInstance) {
  editingId.value = inst.id
  form.value = {
    name: inst.name,
    server_url: inst.server_url,
    repo_id: inst.repo_id,
    namespace_prefix: inst.namespace_prefix,
    domain: inst.domain || '',
  }
  showDialog.value = true
}

function getHealthTagType(status: string): string {
  if (status === 'healthy') return 'success'
  if (status === 'unhealthy') return 'danger'
  return 'warning'
}

async function handleSave() {
  if (!form.value.name || !form.value.server_url || !form.value.repo_id) {
    ElMessage.warning('请填写必要字段')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await graphdbSyncApi.updateInstance(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await graphdbSyncApi.createInstance(form.value)
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    await loadInstances()
  } catch {
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

async function handleDelete(inst: GraphDBInstance) {
  try {
    await ElMessageBox.confirm(`确定要删除实例 "${inst.name}" 吗？`, '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await graphdbSyncApi.deleteInstance(inst.id)
    ElMessage.success('已删除')
    await loadInstances()
  } catch {
    // cancelled
  }
}

onMounted(loadInstances)
</script>

<style scoped>
.instance-manager {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-header-modern {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 20px;
}

.header-text h1 {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.subtitle {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin: 0;
}

.instance-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 16px;
}

.instance-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
  transition: all 0.2s ease;
}

.instance-card:hover {
  border-color: #667eea;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.instance-name {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-primary);
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.info-label {
  font-size: 0.8rem;
  color: var(--text-muted);
  min-width: 80px;
}

.info-value {
  font-size: 0.85rem;
  color: var(--text-primary);
}

.url-value {
  word-break: break-all;
}

.mono {
  font-family: 'Fira Code', monospace;
  color: #667eea;
}

.health-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stmt-count {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-left: auto;
}

.card-actions {
  display: flex;
  gap: 8px;
  border-top: 1px solid var(--border-color);
  padding-top: 12px;
}
</style>
