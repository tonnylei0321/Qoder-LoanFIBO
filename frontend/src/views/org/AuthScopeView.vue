<template>
  <div class="auth-scope-page">
    <div class="page-header">
      <h2>授权项管理</h2>
      <div class="header-actions">
        <el-button @click="handleSeed" :loading="seeding">初始化标准授权项</el-button>
        <el-button type="primary" @click="openCreateScopeDialog">
          <el-icon><Plus /></el-icon>新增授权项
        </el-button>
      </div>
    </div>

    <div class="split-layout">
      <!-- 左侧：融资企业列表 -->
      <div class="left-panel">
        <div class="panel-title">
          <span>融资企业</span>
          <el-switch v-model="activeOnly" size="small" active-text="有效" @change="loadOrgs" />
        </div>
        <div v-loading="orgsLoading" class="org-list">
          <div
            v-for="org in orgs"
            :key="org.id"
            class="org-item"
            :class="{ active: selectedOrg?.id === org.id }"
            @click="selectOrg(org)"
          >
            <div class="org-name">{{ org.name }}</div>
            <div class="org-sub">
              <span v-if="org.unified_code" class="org-code">{{ org.unified_code }}</span>
              <el-tag v-if="getOrgScopeCount(org.id) > 0" size="small" type="success">
                {{ getOrgScopeCount(org.id) }}项授权
              </el-tag>
              <el-tag v-else size="small" type="info">未授权</el-tag>
            </div>
          </div>
          <el-empty v-if="!orgsLoading && orgs.length === 0" description="暂无融资企业" :image-size="60" />
        </div>
      </div>

      <!-- 右侧：授权项配置 -->
      <div class="right-panel">
        <template v-if="selectedOrg">
          <div class="panel-title">
            <span>{{ selectedOrg.name }} — 授权项配置</span>
            <div style="display:flex;gap:8px;align-items:center">
              <span style="font-size:12px;color:var(--el-text-color-secondary)">
                {{ selectedScopeIds.length }}/{{ allScopes.length }} 项已授权
              </span>
              <el-button type="primary" size="small" :loading="saving" @click="saveOrgScopes">
                保存授权
              </el-button>
            </div>
          </div>

          <div v-loading="scopesLoading" class="scope-list">
            <div v-for="group in scopesByCategory" :key="group.category" class="scope-group">
              <div class="scope-group-header">
                <el-checkbox
                  :model-value="isGroupChecked(group)"
                  :indeterminate="isGroupIndeterminate(group)"
                  @change="toggleGroup(group)"
                >
                  {{ group.category || '其他' }}
                  <el-tag size="small" type="info" style="margin-left:6px">{{ group.items.length }}项</el-tag>
                </el-checkbox>
              </div>
              <div class="scope-items">
                <div v-for="scope in group.items" :key="scope.id" class="scope-item">
                  <el-checkbox
                    :model-value="selectedScopeIds.includes(scope.id)"
                    @change="(v: boolean) => toggleScope(scope.id, v)"
                  >
                    <div class="scope-info">
                      <span class="scope-label">{{ scope.label }}</span>
                      <el-tag size="small" type="info" style="margin-left:6px;font-size:11px">{{ scope.code }}</el-tag>
                    </div>
                  </el-checkbox>
                </div>
              </div>
            </div>
            <el-empty v-if="!scopesLoading && allScopes.length === 0" description="暂无授权项，请先初始化" :image-size="60" />
          </div>
        </template>

        <div v-else class="empty-right">
          <el-empty description="请从左侧选择一个融资企业" :image-size="80" />
        </div>
      </div>
    </div>

    <!-- 授权项新增弹框 -->
    <el-dialog
      v-model="scopeDialogVisible"
      :title="editingScope ? '编辑授权项' : '新增授权项'"
      width="500px"
      destroy-on-close
    >
      <el-form :model="scopeForm" label-width="80px" :rules="scopeFormRules" ref="scopeFormRef">
        <el-form-item label="编码" prop="code">
          <el-input v-model="scopeForm.code" placeholder="如：ERP_AR" :disabled="!!editingScope" />
        </el-form-item>
        <el-form-item label="名称" prop="label">
          <el-input v-model="scopeForm.label" placeholder="如：授权-ERP应收账款数据" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="scopeForm.category" clearable placeholder="选择分类" style="width: 100%">
            <el-option label="ERP" value="ERP" />
            <el-option label="财务" value="财务" />
            <el-option label="征信" value="征信" />
            <el-option label="税务" value="税务" />
            <el-option label="银行" value="银行" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="scopeForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scopeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleScopeSubmit" :loading="submitting">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { orgApi, type ApplicantOrg, type AuthorizationScope, type AuthorizationScopeCreate } from '@/api/org'

// ── 状态 ────────────────────────────────────────────────────────────────
const orgs = ref<ApplicantOrg[]>([])
const allScopes = ref<AuthorizationScope[]>([])
const orgsLoading = ref(false)
const scopesLoading = ref(false)
const activeOnly = ref(false)
const saving = ref(false)
const seeding = ref(false)

const selectedOrg = ref<ApplicantOrg | null>(null)
const selectedScopeIds = ref<string[]>([])

// 每个企业已授权的 scope id 列表（用于左侧列表的角标）
const orgScopeMap = ref<Record<string, string[]>>({})

// ── 授权项弹框 ──────────────────────────────────────────────────────────
const scopeDialogVisible = ref(false)
const editingScope = ref<AuthorizationScope | null>(null)
const submitting = ref(false)
const scopeFormRef = ref<FormInstance>()
const scopeForm = reactive<AuthorizationScopeCreate>({
  code: '',
  label: '',
  category: '',
  description: '',
})
const scopeFormRules: FormRules = {
  code: [{ required: true, message: '请输入编码', trigger: 'blur' }],
  label: [{ required: true, message: '请输入名称', trigger: 'blur' }],
}

// ── 计算属性 ──────────────────────────────────────────────────────────────
const scopesByCategory = computed(() => {
  const map: Record<string, AuthorizationScope[]> = {}
  for (const s of allScopes.value) {
    const cat = s.category || '其他'
    if (!map[cat]) map[cat] = []
    map[cat].push(s)
  }
  return Object.entries(map).map(([category, items]) => ({ category, items }))
})

function getOrgScopeCount(orgId: string): number {
  return (orgScopeMap.value[orgId] || []).length
}

function isGroupChecked(group: { category: string; items: AuthorizationScope[] }): boolean {
  return group.items.every(s => selectedScopeIds.value.includes(s.id))
}

function isGroupIndeterminate(group: { category: string; items: AuthorizationScope[] }): boolean {
  const checked = group.items.filter(s => selectedScopeIds.value.includes(s.id)).length
  return checked > 0 && checked < group.items.length
}

function toggleGroup(group: { category: string; items: AuthorizationScope[] }) {
  const allChecked = isGroupChecked(group)
  if (allChecked) {
    // 全部取消
    selectedScopeIds.value = selectedScopeIds.value.filter(id => !group.items.some(s => s.id === id))
  } else {
    // 全选
    const newIds = group.items.map(s => s.id).filter(id => !selectedScopeIds.value.includes(id))
    selectedScopeIds.value = [...selectedScopeIds.value, ...newIds]
  }
}

function toggleScope(scopeId: string, checked: boolean) {
  if (checked) {
    if (!selectedScopeIds.value.includes(scopeId)) {
      selectedScopeIds.value = [...selectedScopeIds.value, scopeId]
    }
  } else {
    selectedScopeIds.value = selectedScopeIds.value.filter(id => id !== scopeId)
  }
}

// ── 数据加载 ──────────────────────────────────────────────────────────────
async function loadOrgs() {
  orgsLoading.value = true
  try {
    orgs.value = await orgApi.listOrgs(activeOnly.value)
    // 加载所有企业的授权配置（批量）
    await loadAllOrgScopes()
  } catch (e: any) {
    ElMessage.error('加载失败: ' + (e.message || e))
  } finally {
    orgsLoading.value = false
  }
}

async function loadAllOrgScopes() {
  const map: Record<string, string[]> = {}
  await Promise.all(
    orgs.value.map(async (org) => {
      try {
        const res = await orgApi.getOrgAuthScopes(org.id)
        map[org.id] = res.scope_ids || []
      } catch {
        map[org.id] = []
      }
    })
  )
  orgScopeMap.value = map
}

async function loadScopes() {
  scopesLoading.value = true
  try {
    allScopes.value = await orgApi.listAuthScopes(false)
  } catch (e: any) {
    ElMessage.error('加载授权项失败: ' + (e.message || e))
  } finally {
    scopesLoading.value = false
  }
}

async function selectOrg(org: ApplicantOrg) {
  selectedOrg.value = org
  selectedScopeIds.value = [...(orgScopeMap.value[org.id] || [])]
}

async function saveOrgScopes() {
  if (!selectedOrg.value) return
  saving.value = true
  try {
    await orgApi.updateOrgAuthScopes(selectedOrg.value.id, selectedScopeIds.value)
    orgScopeMap.value[selectedOrg.value.id] = [...selectedScopeIds.value]
    ElMessage.success('授权保存成功')
  } catch (e: any) {
    ElMessage.error('保存失败: ' + (e.message || e))
  } finally {
    saving.value = false
  }
}

// ── 授权项 CRUD ───────────────────────────────────────────────────────────
function openCreateScopeDialog() {
  editingScope.value = null
  scopeForm.code = ''
  scopeForm.label = ''
  scopeForm.category = ''
  scopeForm.description = ''
  scopeDialogVisible.value = true
}

async function handleScopeSubmit() {
  if (!scopeFormRef.value) return
  await scopeFormRef.value.validate()
  submitting.value = true
  try {
    if (editingScope.value) {
      await orgApi.updateAuthScope(editingScope.value.id, { ...scopeForm })
      ElMessage.success('更新成功')
    } else {
      await orgApi.createAuthScope({ ...scopeForm })
      ElMessage.success('创建成功')
    }
    scopeDialogVisible.value = false
    await loadScopes()
  } catch (e: any) {
    ElMessage.error('操作失败: ' + (e.message || e))
  } finally {
    submitting.value = false
  }
}

async function handleSeed() {
  seeding.value = true
  try {
    const res = await orgApi.seedDefaultData()
    ElMessage.success(`初始化完成，新增 ${res.seeded_auth_scopes} 条标准授权项`)
    await loadScopes()
  } catch (e: any) {
    ElMessage.error('初始化失败: ' + (e.message || e))
  } finally {
    seeding.value = false
  }
}

onMounted(async () => {
  await Promise.all([loadOrgs(), loadScopes()])
})
</script>

<style scoped>
.auth-scope-page {
  padding: 0;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.page-header h2 {
  margin: 0;
  font-size: 1.3rem;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.split-layout {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.left-panel {
  width: 280px;
  flex-shrink: 0;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--el-bg-color);
}

.right-panel {
  flex: 1;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--el-bg-color);
  min-height: 400px;
}

.panel-title {
  padding: 12px 16px;
  font-weight: 600;
  font-size: 14px;
  border-bottom: 1px solid var(--el-border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  background: var(--el-fill-color-lighter);
}

.org-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.org-item {
  padding: 10px 16px;
  cursor: pointer;
  transition: background 0.15s;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.org-item:hover {
  background: var(--el-fill-color-light);
}

.org-item.active {
  background: var(--el-color-primary-light-9);
  border-left: 3px solid var(--el-color-primary);
}

.org-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.org-sub {
  display: flex;
  align-items: center;
  gap: 6px;
}

.org-code {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  font-family: monospace;
}

.scope-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.scope-group {
  margin-bottom: 16px;
}

.scope-group-header {
  padding: 6px 8px;
  background: var(--el-fill-color-lighter);
  border-radius: 4px;
  margin-bottom: 6px;
  font-weight: 600;
}

.scope-items {
  padding-left: 20px;
}

.scope-item {
  padding: 6px 0;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}

.scope-info {
  display: inline-flex;
  align-items: center;
}

.scope-label {
  font-size: 14px;
}

.empty-right {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
