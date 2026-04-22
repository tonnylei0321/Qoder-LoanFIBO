<template>
  <div class="org-manage">
    <div class="page-header">
      <h2>企业管理 & 凭证管理</h2>
      <el-button type="primary" @click="showRegisterDialog = true">注册新企业</el-button>
    </div>

    <!-- 企业列表 -->
    <el-table :data="orgs" v-loading="loading" stripe>
      <el-table-column prop="org_id" label="企业ID" width="280" />
      <el-table-column prop="name" label="企业名称" />
      <el-table-column prop="industry" label="行业" />
      <el-table-column prop="datasource" label="数据源" width="120" />
      <el-table-column label="凭证" width="200">
        <template #default="{ row }">
          <el-button size="small" @click="handleCreateCredential(row.org_id, row.datasource)">
            生成凭证
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 注册对话框 -->
    <el-dialog v-model="showRegisterDialog" title="注册新企业" width="500px">
      <el-form :model="registerForm" label-width="80px">
        <el-form-item label="企业名称">
          <el-input v-model="registerForm.name" placeholder="如：中天科技" />
        </el-form-item>
        <el-form-item label="行业">
          <el-input v-model="registerForm.industry" placeholder="如：制造业" />
        </el-form-item>
        <el-form-item label="数据源">
          <el-input v-model="registerForm.datasource" placeholder="如：NCC" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRegisterDialog = false">取消</el-button>
        <el-button type="primary" @click="handleRegister" :loading="registering">注册</el-button>
      </template>
    </el-dialog>

    <!-- 凭证展示对话框 -->
    <el-dialog v-model="showCredentialDialog" title="凭证信息（仅展示一次）" width="500px">
      <el-alert type="warning" :closable="false" show-icon style="margin-bottom: 16px">
        client_secret 仅展示一次，请立即复制保存！
      </el-alert>
      <el-form label-width="120px">
        <el-form-item label="client_id">
          <el-input :model-value="credentialData.client_id" readonly>
            <template #append>
              <el-button @click="copyText(credentialData.client_id || '')">复制</el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label="client_secret">
          <el-input :model-value="credentialData.client_secret" readonly type="password" show-password>
            <template #append>
              <el-button @click="copyText(credentialData.client_secret || '')">复制</el-button>
            </template>
          </el-input>
        </el-form-item>
      </el-form>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { agentApi } from '@/api/agent'

interface OrgItem {
  org_id: string
  name: string
  industry: string
  datasource: string
}

const loading = ref(false)
const orgs = ref<OrgItem[]>([])
const showRegisterDialog = ref(false)
const registering = ref(false)
const registerForm = ref({ name: '', industry: '', datasource: 'NCC' })

const showCredentialDialog = ref(false)
const credentialData = ref<Record<string, string>>({})

const fetchOrgs = async () => {
  // 暂时从状态接口获取企业信息
  // TODO: 需要后端提供 /agent/orgs GET 接口
  loading.value = true
  try {
    const status = (await agentApi.getAgentStatus()) as unknown as any[]
    orgs.value = status.map(s => ({
      org_id: s.org_id,
      name: s.org_id,
      industry: '',
      datasource: s.datasource,
    }))
  } catch (e) {
    // ignore
  } finally {
    loading.value = false
  }
}

const handleRegister = async () => {
  if (!registerForm.value.name) {
    ElMessage.warning('请输入企业名称')
    return
  }
  registering.value = true
  try {
    const result = await agentApi.registerOrg(registerForm.value) as any
    ElMessage.success('企业注册成功')
    showRegisterDialog.value = false
    // 展示凭证
    if (result.credential) {
      credentialData.value = result.credential
      showCredentialDialog.value = true
    }
    registerForm.value = { name: '', industry: '', datasource: 'NCC' }
    await fetchOrgs()
  } catch (e) {
    // error handled by interceptor
  } finally {
    registering.value = false
  }
}

const handleCreateCredential = async (orgId: string, datasource: string) => {
  try {
    const result = await agentApi.createCredential(orgId, datasource) as any
    credentialData.value = result
    showCredentialDialog.value = true
  } catch (e) {
    // error handled by interceptor
  }
}

const copyText = (text: string) => {
  navigator.clipboard.writeText(text)
  ElMessage.success('已复制到剪贴板')
}

onMounted(fetchOrgs)
</script>

<style scoped>
.org-manage {
  padding: 20px;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
</style>
