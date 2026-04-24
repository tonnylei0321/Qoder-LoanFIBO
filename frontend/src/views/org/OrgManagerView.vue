<template>
  <div class="org-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="page-title-area">
        <h2>融资企业管理</h2>
        <span class="page-subtitle">管理贷款申请方企业信息及ERP系统接入配置</span>
      </div>
      <div class="header-actions">
        <div class="filter-toggle">
          <span class="filter-label">全部</span>
          <el-switch v-model="activeOnly" @change="loadOrgs" />
          <span class="filter-label active">仅有效</span>
        </div>
        <el-button type="primary" class="add-btn" @click="openCreateDialog">
          <el-icon><Plus /></el-icon>新增企业
        </el-button>
      </div>
    </div>

    <!-- Stats Bar -->
    <div class="stats-bar">
      <div class="stat-item">
        <span class="stat-number">{{ orgs.length }}</span>
        <span class="stat-label">全部企业</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-number success">{{ orgs.filter(o => o.is_active).length }}</span>
        <span class="stat-label">有效</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-number linked">{{ orgs.filter(o => o.extra?.erp_instance_id).length }}</span>
        <span class="stat-label">已关联GraphDB</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat-item">
        <span class="stat-number secured">{{ orgs.filter(o => o.security_id_masked).length }}</span>
        <span class="stat-label">已配安全ID</span>
      </div>
    </div>

    <!-- Table Card -->
    <div class="table-card">
      <el-table
        :data="orgs"
        v-loading="loading"
        class="org-table"
        row-key="id"
      >
        <!-- Expand column -->
        <el-table-column type="expand" width="40">
          <template #default="{ row }">
            <div class="expand-detail">
              <div class="detail-item" v-if="row.region">
                <span class="detail-label">注册地区</span>
                <span class="detail-value">{{ row.region }}</span>
              </div>
              <div class="detail-item" v-if="row.legal_person">
                <span class="detail-label">法定代表人</span>
                <span class="detail-value">{{ row.legal_person }}</span>
              </div>
              <div class="detail-item" v-if="row.registered_capital">
                <span class="detail-label">注册资本</span>
                <span class="detail-value">{{ row.registered_capital }}</span>
              </div>
              <div class="detail-item" v-if="row.graph_uri">
                <span class="detail-label">Graph URI</span>
                <span class="detail-value mono">{{ row.graph_uri }}</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="企业名称" min-width="180">
          <template #default="{ row }">
            <div class="org-name-cell">
              <div class="org-avatar">{{ row.name.charAt(0) }}</div>
              <div class="org-name-info">
                <span class="org-name">{{ row.name }}</span>
                <span v-if="row.short_name" class="org-short-name">{{ row.short_name }}</span>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="信用代码" prop="unified_code" width="190">
          <template #default="{ row }">
            <span v-if="row.unified_code" class="credit-code">{{ row.unified_code }}</span>
            <span v-else class="empty-cell">-</span>
          </template>
        </el-table-column>

        <el-table-column label="行业" prop="industry" width="110">
          <template #default="{ row }">
            <el-tag v-if="row.industry" size="small" class="industry-tag">{{ row.industry }}</el-tag>
            <span v-else class="empty-cell">-</span>
          </template>
        </el-table-column>

        <el-table-column label="GraphDB实例" width="160">
          <template #default="{ row }">
            <div class="instance-cell">
              <template v-if="getInstanceName(row)">
                <span class="instance-dot"></span>
                <el-tag size="small" type="success" class="instance-tag">{{ getInstanceName(row) }}</el-tag>
              </template>
              <span v-else class="unlinked">未关联</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="安全ID" width="270">
          <template #default="{ row }">
            <div class="security-id-cell">
              <code v-if="row.security_id_masked" class="sid-code">{{ row.security_id_masked }}</code>
              <span v-else class="unset">未生成</span>
              <div class="sid-actions">
                <el-button v-if="row.security_id_masked" text size="small" type="primary" :loading="copyingId === row.id" @click="copySecurityId(row)">
                  <el-icon v-if="!copyingId"><CopyDocument /></el-icon> 复制
                </el-button>
                <el-button text size="small" type="warning" :loading="regenId === row.id" @click="handleRegenerateSecurityId(row)">重新生成</el-button>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="状态" width="80" align="center">
          <template #default="{ row }">
            <span class="status-pill" :class="row.is_active ? 'active' : 'inactive'">
              {{ row.is_active ? '有效' : '停用' }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="130" fixed="right" align="right">
          <template #default="{ row }">
            <div class="action-cell">
              <el-button text size="small" type="primary" @click="openEditDialog(row)">编辑</el-button>
              <el-popconfirm
                :title="row.is_active ? '确定停用该企业？' : '确定删除该企业？'"
                @confirm="handleDelete(row)"
              >
                <template #reference>
                  <el-button text size="small" :type="row.is_active ? 'danger' : 'warning'">
                    {{ row.is_active ? '停用' : '删除' }}
                  </el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Create/Edit Dialog -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑融资企业' : '新增融资企业'"
      width="600px"
      destroy-on-close
    >
      <el-form :model="formData" label-width="120px" :rules="formRules" ref="formRef">
        <el-form-item label="企业名称" prop="name">
          <el-input v-model="formData.name" placeholder="如：华远集团有限公司" />
        </el-form-item>
        <el-form-item label="统一社会信用代码" prop="unified_code">
          <el-input v-model="formData.unified_code" placeholder="18位统一社会信用代码" />
        </el-form-item>
        <el-form-item label="企业简称">
          <el-input v-model="formData.short_name" placeholder="如：华远集团" />
        </el-form-item>
        <el-form-item label="GraphDB实例">
          <el-select
            v-model="formData.erp_instance_id"
            placeholder="选择关联的GraphDB实例"
            clearable
            style="width: 100%"
          >
            <el-option
              v-for="inst in graphdbInstances"
              :key="inst.id"
              :label="inst.name"
              :value="inst.id"
            >
              <span>{{ inst.name }}</span>
              <span style="color:var(--el-text-color-secondary);font-size:12px;margin-left:8px">
                {{ inst.repo_id }}
              </span>
            </el-option>
          </el-select>
        </el-form-item>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="行业分类">
              <el-select
                v-model="formData.industry"
                filterable
                clearable
                placeholder="搜索行业（支持编码/拼音首字母）"
                :filter-method="(q: string) => industryFilterOptions = INDUSTRY_CATEGORIES.filter(o => industryFilter(q, o))"
                style="width: 100%"
              >
                <el-option
                  v-for="item in (industryFilterOptions.length ? industryFilterOptions : INDUSTRY_CATEGORIES)"
                  :key="item.code"
                  :label="`${item.code} ${item.label}`"
                  :value="item.label"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="注册地区">
              <el-input v-model="formData.region" placeholder="如：北京" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="法定代表人">
              <el-input v-model="formData.legal_person" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="注册资本">
              <el-input v-model="formData.registered_capital" placeholder="如：5000万" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="联系方式">
          <el-input v-model="formData.contact_info" type="textarea" :rows="2" placeholder="JSON格式联系方式" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { orgApi, type ApplicantOrg, type ApplicantOrgCreate, type ApplicantOrgUpdate } from '@/api/org'
import { INDUSTRY_CATEGORIES, industryFilter } from '@/utils/industry'
import { ElMessageBox } from 'element-plus'
import { CopyDocument } from '@element-plus/icons-vue'
import request from '@/api/request'

interface GraphDBInstance {
  id: string
  name: string
  repo_id: string
  is_active: boolean
}

const orgs = ref<ApplicantOrg[]>([])
const loading = ref(false)
const activeOnly = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const editId = ref('')
const formRef = ref<FormInstance>()
const industryFilterOptions = ref<typeof INDUSTRY_CATEGORIES>([])
const graphdbInstances = ref<GraphDBInstance[]>([])
const copyingId = ref<string | null>(null)
const regenId = ref<string | null>(null)

const formData = reactive<ApplicantOrgCreate & { contact_info: string; erp_instance_id: string }>({
  name: '',
  unified_code: '',
  short_name: '',
  industry: '',
  region: '',
  legal_person: '',
  registered_capital: '',
  contact_info: '',
  erp_instance_id: '',
})

const formRules: FormRules = {
  name: [{ required: true, message: '请输入企业名称', trigger: 'blur' }],
}

async function loadGraphdbInstances() {
  try {
    const data = await request.get<any, GraphDBInstance[]>('/instances')
    graphdbInstances.value = Array.isArray(data) ? data.filter(i => i.is_active) : []
  } catch {
    graphdbInstances.value = []
  }
}

function getInstanceName(row: ApplicantOrg): string {
  const instanceId = row.extra?.erp_instance_id as string | undefined
  if (!instanceId) return ''
  const inst = graphdbInstances.value.find(i => i.id === instanceId)
  return inst ? inst.name : instanceId
}

async function loadOrgs() {
  loading.value = true
  try {
    orgs.value = await orgApi.listOrgs(activeOnly.value)
  } catch (e: any) {
    ElMessage.error('加载失败: ' + (e.message || e))
  } finally {
    loading.value = false
  }
}

function resetForm() {
  formData.name = ''
  formData.unified_code = ''
  formData.short_name = ''
  formData.industry = ''
  formData.region = ''
  formData.legal_person = ''
  formData.registered_capital = ''
  formData.contact_info = ''
  formData.erp_instance_id = ''
}

function openCreateDialog() {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

function openEditDialog(row: ApplicantOrg) {
  isEdit.value = true
  editId.value = row.id
  formData.name = row.name
  formData.unified_code = row.unified_code || ''
  formData.short_name = row.short_name || ''
  formData.industry = row.industry || ''
  formData.region = row.region || ''
  formData.legal_person = row.legal_person || ''
  formData.registered_capital = row.registered_capital || ''
  formData.contact_info = row.contact_info || ''
  formData.erp_instance_id = (row.extra?.erp_instance_id as string) || ''
  dialogVisible.value = true
}

async function handleSubmit() {
  if (!formRef.value) return
  await formRef.value.validate()
  submitting.value = true
  try {
    // 将 erp_instance_id 合并到 extra字段
    const extraData = formData.erp_instance_id ? { erp_instance_id: formData.erp_instance_id } : undefined
    if (isEdit.value) {
      const updateData: ApplicantOrgUpdate = {
        name: formData.name,
        unified_code: formData.unified_code,
        short_name: formData.short_name,
        industry: formData.industry,
        region: formData.region,
        legal_person: formData.legal_person,
        registered_capital: formData.registered_capital,
        contact_info: formData.contact_info,
        extra: extraData,
      }
      await orgApi.updateOrg(editId.value, updateData)
      ElMessage.success('更新成功')
    } else {
      const createData: ApplicantOrgCreate = {
        name: formData.name,
        unified_code: formData.unified_code,
        short_name: formData.short_name,
        industry: formData.industry,
        region: formData.region,
        legal_person: formData.legal_person,
        registered_capital: formData.registered_capital,
        contact_info: formData.contact_info,
        extra: extraData,
      }
      await orgApi.createOrg(createData)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    await loadOrgs()
  } catch (e: any) {
    ElMessage.error('操作失败: ' + (e.message || e))
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: ApplicantOrg) {
  try {
    await orgApi.deleteOrg(row.id)
    ElMessage.success(row.is_active ? '已停用' : '已删除')
    await loadOrgs()
  } catch (e: any) {
    ElMessage.error('操作失败: ' + (e.message || e))
  }
}

async function copySecurityId(row: ApplicantOrg) {
  copyingId.value = row.id
  try {
    const res = await request.get<any, { security_id: string }>(`/org/orgs/${row.id}/security-id`)
    await navigator.clipboard.writeText(res.security_id)
    ElMessage.success('安全ID 已复制到剪贴板')
  } catch (e: any) {
    ElMessage.error('复制失败: ' + (e.message || e))
  } finally {
    copyingId.value = null
  }
}

async function handleRegenerateSecurityId(row: ApplicantOrg) {
  regenId.value = row.id
  try {
    await ElMessageBox.confirm(
      '重新生成安全ID后，旧的安全ID将立即失效，使用旧ID的ERP代理将无法连接。确定继续？',
      '重新生成安全ID',
      { confirmButtonText: '确定重新生成', cancelButtonText: '取消', type: 'warning' }
    )
    const result = await orgApi.regenerateSecurityId(row.id) as any
    const newSid = result.data?.security_id || ''
    if (newSid) {
      await navigator.clipboard.writeText(newSid)
      ElMessage.success('新安全ID已生成并复制到剪贴板，请妥善保存！')
    }
    await loadOrgs()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('操作失败: ' + (e.message || e))
    }
  } finally {
    regenId.value = null
  }
}

onMounted(() => {
  loadOrgs()
  loadGraphdbInstances()
})
</script>

<style scoped>
.org-page {
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Page Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 24px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0,0,0,.04);
}

.page-title-area h2 {
  margin: 0 0 4px;
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.page-subtitle {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.filter-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  background: var(--el-fill-color-lighter);
  border-radius: 20px;
  border: 1px solid var(--el-border-color-lighter);
}

.filter-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.filter-label.active {
  color: var(--el-color-primary);
  font-weight: 500;
}

.add-btn {
  border-radius: 8px !important;
  font-weight: 600 !important;
  padding: 8px 18px !important;
}

/* Stats Bar */
.stats-bar {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 12px 24px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 0 24px;
}

.stat-number {
  font-size: 22px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1;
}

.stat-number.success { color: var(--el-color-success); }
.stat-number.linked  { color: var(--el-color-primary); }
.stat-number.secured { color: var(--el-color-warning); }

.stat-label {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.stat-divider {
  width: 1px;
  height: 32px;
  background: var(--el-border-color-lighter);
}

/* Table Card */
.table-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,.04);
}

/* Table Overrides */
:deep(.org-table) {
  border: none;
}

:deep(.org-table .el-table__header-wrapper th) {
  background: var(--el-fill-color-lighter) !important;
  font-weight: 600;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  border-bottom: 1px solid var(--el-border-color-lighter);
  padding: 12px 0;
}

:deep(.org-table .el-table__row) {
  transition: background 0.15s;
}

:deep(.org-table .el-table__row:hover > td) {
  background: var(--el-color-primary-light-9) !important;
}

:deep(.org-table .el-table__expand-icon) {
  color: var(--el-text-color-secondary);
}

/* Org Name Cell */
.org-name-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.org-avatar {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  background: linear-gradient(135deg, var(--el-color-primary-light-5), var(--el-color-primary));
  color: white;
  font-size: 14px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.org-name-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.org-name {
  font-weight: 600;
  font-size: 13px;
  color: var(--el-text-color-primary);
}

.org-short-name {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

/* Credit Code */
.credit-code {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 12px;
  letter-spacing: 0.02em;
  color: var(--el-text-color-regular);
}

/* Industry Tag */
:deep(.industry-tag) {
  border-radius: 4px;
  font-size: 11px;
}

/* Instance Cell */
.instance-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.instance-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--el-color-success);
  box-shadow: 0 0 6px var(--el-color-success);
  flex-shrink: 0;
}

:deep(.instance-tag) {
  border-radius: 4px;
  font-size: 11px;
}

.unlinked {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  font-style: italic;
}

/* Security ID Cell */
.security-id-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.sid-code {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 11px;
  background: var(--el-fill-color);
  padding: 2px 7px;
  border-radius: 4px;
  border: 1px solid var(--el-border-color-lighter);
  color: var(--el-text-color-primary);
  letter-spacing: 0.02em;
}

.unset {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  font-style: italic;
}

.sid-actions {
  display: flex;
  align-items: center;
  gap: 0;
  flex-shrink: 0;
}

/* Status Pill */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.03em;
}

.status-pill::before {
  content: '';
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-pill.active {
  background: rgba(103, 194, 58, 0.12);
  color: var(--el-color-success);
}

.status-pill.active::before {
  background: var(--el-color-success);
}

.status-pill.inactive {
  background: var(--el-fill-color);
  color: var(--el-text-color-secondary);
}

.status-pill.inactive::before {
  background: var(--el-text-color-placeholder);
}

.action-cell {
  display: flex;
  justify-content: flex-end;
  gap: 2px;
}

.empty-cell {
  color: var(--el-text-color-placeholder);
  font-size: 12px;
}

/* Expand Detail */
.expand-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 32px;
  padding: 14px 24px 14px 60px;
  background: var(--el-fill-color-lighter);
  border-top: 1px dashed var(--el-border-color-lighter);
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.detail-label {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.detail-value {
  font-size: 13px;
  color: var(--el-text-color-primary);
  font-weight: 500;
}

.detail-value.mono {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
</style>
