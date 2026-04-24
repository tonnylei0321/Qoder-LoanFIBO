<template>
  <div class="org-manage">
    <div class="page-header">
      <h2>企业管理 & 凭证管理</h2>
      <div class="header-actions">
        <el-input
          v-model="searchText"
          placeholder="搜索企业名称"
          clearable
          style="width: 220px; margin-right: 12px"
          @clear="fetchOrgs"
          @keyup.enter="fetchOrgs"
        >
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="showRegisterDialog = true">
          <el-icon><Plus /></el-icon>注册新企业
        </el-button>
      </div>
    </div>

    <!-- 企业列表 -->
    <el-table :data="orgs" v-loading="loading" stripe row-key="org_id"
      @row-click="handleRowClick" highlight-current-row>
      <el-table-column prop="name" label="企业名称" min-width="160" />
      <el-table-column prop="industry" label="行业" width="120" />
      <el-table-column prop="datasource" label="数据源" width="100" />
      <el-table-column label="安全ID" width="200">
        <template #default="{ row }">
          <span v-if="row.security_id_masked" style="font-family: monospace; font-size: 12px; margin-right: 4px">{{ row.security_id_masked }}</span>
          <el-button v-if="row.security_id_masked" text size="small" type="primary" @click.stop="copyText(row.security_id_masked)">复制</el-button>
        </template>
      </el-table-column>
      <el-table-column label="凭证" width="160" align="center">
        <template #default="{ row }">
          <span>{{ row.active_credential_count }} 有效 / {{ row.credential_count }} 总计</span>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="注册时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click.stop="handleCreateCredential(row.org_id, row.datasource)">
            生成凭证
          </el-button>
          <el-button size="small" @click.stop="handleViewCredentials(row.org_id, row.name)">
            凭证列表
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
          <el-select v-model="registerForm.datasource" style="width: 100%">
            <el-option label="NCC（用友）" value="NCC" />
            <el-option label="SAP" value="SAP" />
            <el-option label="U8（用友）" value="U8" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRegisterDialog = false">取消</el-button>
        <el-button type="primary" @click="handleRegister" :loading="registering">注册</el-button>
      </template>
    </el-dialog>

    <!-- 凭证展示对话框（仅展示一次） -->
    <el-dialog v-model="showCredentialDialog" title="凭证信息（仅展示一次）" width="600px">
      <el-alert type="warning" :closable="false" show-icon style="margin-bottom: 16px">
        client_secret 和安全ID 仅展示一次，请立即复制保存！关闭后无法再次查看。
      </el-alert>
      <!-- 安全ID -->
      <el-form label-width="120px" v-if="credentialData.security_id">
        <el-form-item label="安全ID">
          <el-input :model-value="credentialData.security_id" readonly>
            <template #append>
              <el-button @click="copyText(credentialData.security_id || '')">复制</el-button>
            </template>
          </el-input>
        </el-form-item>
      </el-form>
      <div style="margin-bottom: 12px; padding: 12px; background: var(--el-fill-color-light); border-radius: 6px;" v-if="credentialData.security_id">
        <p style="margin: 0 0 6px; font-weight: 600;">安全ID使用说明</p>
        <p style="margin: 0; font-size: 13px; color: var(--el-text-color-secondary)">
          请将安全ID线下提供给融资企业，由企业在ERP代理服务配置文件中配置使用。
        </p>
      </div>
      <el-divider v-if="credentialData.security_id" />
      <!-- 凭证信息 -->
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
      <div style="margin-top: 12px; padding: 12px; background: var(--el-fill-color-light); border-radius: 6px;">
        <p style="margin: 0 0 6px; font-weight: 600;">ERP 代理连接参数</p>
        <p style="margin: 0; font-size: 13px; color: var(--el-text-color-secondary)">
          WebSocket: ws://&lt;SaaS服务地址&gt;/api/v1/agent/connect<br/>
          Client ID: {{ credentialData.client_id }}<br/>
          Client Secret: 见上方（仅展示一次）
        </p>
      </div>
    </el-dialog>

    <!-- 凭证列表抽屉 -->
    <el-drawer v-model="showCredDrawer" :title="`${credDrawerOrgName} - 凭证列表`" size="520px">
      <el-table :data="credList" v-loading="credListLoading" stripe>
        <el-table-column prop="client_id" label="Client ID" min-width="220">
          <template #default="{ row }">
            <span style="font-family: monospace; font-size: 12px">{{ row.client_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="datasource" label="数据源" width="80" />
        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <el-tag :type="row.revoked ? 'danger' : 'success'" size="small">
              {{ row.revoked ? '已吊销' : '有效' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="160">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="!row.revoked"
              size="small"
              type="danger"
              text
              @click="handleRevoke(row.client_id)"
            >吊销</el-button>
            <span v-else style="color: var(--el-text-color-placeholder); font-size: 12px">-</span>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top: 16px; padding: 12px; background: var(--el-fill-color-light); border-radius: 6px;">
        <p style="margin: 0; font-size: 13px; color: var(--el-text-color-secondary)">
          <strong>提示：</strong>client_secret 只在生成时展示一次，无法再次查看。如需新凭证请点击"生成凭证"。
        </p>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { agentApi } from '@/api/agent'

interface OrgItem {
  org_id: string
  name: string
  industry: string
  datasource: string
  security_id_masked?: string
  credential_count: number
  active_credential_count: number
  created_at: string
}

interface CredItem {
  client_id: string
  datasource: string
  revoked: boolean
  revoked_at: string | null
  created_at: string
}

const loading = ref(false)
const orgs = ref<OrgItem[]>([])
const searchText = ref('')

const showRegisterDialog = ref(false)
const registering = ref(false)
const registerForm = ref({ name: '', industry: '', datasource: 'NCC' })

const showCredentialDialog = ref(false)
const credentialData = ref<Record<string, string>>({})

const showCredDrawer = ref(false)
const credDrawerOrgName = ref('')
const credDrawerOrgId = ref('')
const credList = ref<CredItem[]>([])
const credListLoading = ref(false)

const formatTime = (iso: string | null) => {
  if (!iso) return '-'
  return new Date(iso).toLocaleString('zh-CN')
}

const fetchOrgs = async () => {
  loading.value = true
  try {
    const result = (await agentApi.listOrgs({ search: searchText.value || undefined })) as any
    orgs.value = result.data || []
  } catch (e) {
    // error handled by interceptor
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
    const result = (await agentApi.registerOrg(registerForm.value)) as any
    ElMessage.success('企业注册成功')
    showRegisterDialog.value = false
    // 展示凭证和安全ID
    if (result.data?.credential) {
      credentialData.value = {
        ...result.data.credential,
        security_id: result.data.security_id || '',
      }
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
    const result = (await agentApi.createCredential(orgId, datasource)) as any
    credentialData.value = result.data
    showCredentialDialog.value = true
    await fetchOrgs()
  } catch (e) {
    // error handled by interceptor
  }
}

const handleViewCredentials = async (orgId: string, orgName: string) => {
  credDrawerOrgId.value = orgId
  credDrawerOrgName.value = orgName
  showCredDrawer.value = true
  credListLoading.value = true
  try {
    const result = (await agentApi.listCredentials(orgId)) as any
    credList.value = result.data || []
  } catch (e) {
    // error handled by interceptor
  } finally {
    credListLoading.value = false
  }
}

const handleRevoke = async (clientId: string) => {
  try {
    await ElMessageBox.confirm(
      `确定吊销凭证 ${clientId}？吊销后使用该凭证的 ERP 代理将立即断开连接。`,
      '吊销确认',
      { confirmButtonText: '确定吊销', cancelButtonText: '取消', type: 'warning' }
    )
    await agentApi.revokeCredential(clientId)
    ElMessage.success('凭证已吊销')
    // 刷新凭证列表和企业列表
    await handleViewCredentials(credDrawerOrgId.value, credDrawerOrgName.value)
    await fetchOrgs()
  } catch (e) {
    if (e !== 'cancel') {
      // error handled by interceptor
    }
  }
}

const handleRowClick = (row: OrgItem) => {
  handleViewCredentials(row.org_id, row.name)
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
.header-actions {
  display: flex;
  align-items: center;
}
</style>
