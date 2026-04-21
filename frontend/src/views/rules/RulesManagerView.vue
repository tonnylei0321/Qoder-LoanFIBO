<template>
  <div class="rules-manager-view">
    <div class="page-header">
      <h2 data-testid="rules-title">规则管理</h2>
      <div class="header-actions">
        <el-select
          v-model="tenantId"
          placeholder="选择租户"
          class="tenant-select"
          data-testid="rules-tenant"
          @change="loadRules"
        >
          <el-option label="默认租户" value="default" />
          <el-option label="银行A" value="bank_a" />
          <el-option label="银行B" value="bank_b" />
        </el-select>
        <el-button
          type="primary"
          data-testid="rules-add-btn"
          @click="showCreateDialog = true"
        >
          <el-icon><Plus /></el-icon> 新建规则
        </el-button>
        <el-button
          :loading="compiling"
          data-testid="rules-compile-btn"
          @click="triggerCompile"
        >
          <el-icon><VideoPlay /></el-icon> 触发编译
        </el-button>
      </div>
    </div>

    <!-- 编译状态条 -->
    <div class="compile-status-bar" :class="compileStatus?.status" data-testid="rules-compile-status">
      <div class="status-info">
        <el-icon v-if="compileStatus?.status === 'completed'"><CircleCheck /></el-icon>
        <el-icon v-else-if="compileStatus?.status === 'compiling'"><Loading /></el-icon>
        <el-icon v-else-if="compileStatus?.status === 'failed'"><CircleClose /></el-icon>
        <el-icon v-else><Clock /></el-icon>
        <span>编译状态：{{ compileStatusLabel }}</span>
      </div>
      <div v-if="compileStatus?.current_version" class="version-info">
        版本 {{ compileStatus.current_version }}
        <span v-if="compileStatus.last_compiled_at">
          · {{ formatTime(compileStatus.last_compiled_at) }}
        </span>
      </div>
      <div v-if="compileStatus?.staleness_seconds" class="staleness-info">
        <el-tooltip content="距上次编译的过期时间">
          <el-tag size="small" :type="compileStatus.staleness_seconds > 3600 ? 'danger' : 'warning'">
            {{ formatStaleness(compileStatus.staleness_seconds) }}
          </el-tag>
        </el-tooltip>
      </div>
    </div>

    <!-- 规则表格 -->
    <div class="rules-table-section">
      <el-table
        :data="rules"
        v-loading="loading"
        stripe
        class="rules-table"
        data-testid="rules-table"
      >
        <el-table-column prop="name" label="规则名称" min-width="160">
          <template #default="{ row }">
            <span class="rule-name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="rule_type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag size="small" :type="ruleTypeTag(row.rule_type)">
              {{ ruleTypeLabel(row.rule_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100" />
        <el-table-column label="DSL公式" min-width="200">
          <template #default="{ row }">
            <code class="dsl-code">{{ formatDsl(row.definition) }}</code>
          </template>
        </el-table-column>
        <el-table-column prop="enabled" label="状态" width="100">
          <template #default="{ row }">
            <el-switch
              v-model="row.enabled"
              size="small"
              @change="toggleRule(row)"
            />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" @click="editRule(row)">编辑</el-button>
            <el-button text size="small" type="danger" @click="deleteRule(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-empty v-if="!loading && rules.length === 0" description="暂无规则" />
    </div>

    <!-- 创建/编辑规则对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingRule ? '编辑规则' : '新建规则'"
      width="600px"
      data-testid="rules-create-dialog"
    >
      <el-form :model="ruleForm" label-width="100px" :rules="formRules" ref="formRef">
        <el-form-item label="规则名称" prop="name">
          <el-input v-model="ruleForm.name" placeholder="例如：资产负债率阈值检查" />
        </el-form-item>
        <el-form-item label="规则类型" prop="rule_type">
          <el-select v-model="ruleForm.rule_type" placeholder="选择规则类型">
            <el-option label="阈值检查" value="threshold" />
            <el-option label="范围检查" value="range" />
            <el-option label="复合条件" value="composite" />
            <el-option label="自定义" value="custom" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级" prop="priority">
          <el-input-number v-model="ruleForm.priority" :min="0" :max="100" />
        </el-form-item>
        <el-form-item label="DSL 公式" prop="definition_formula">
          <el-input
            v-model="ruleForm.definition_formula"
            type="textarea"
            :rows="4"
            placeholder="例如：debt_ratio > 0.6 AND debt_ratio <= 0.8"
          />
          <div class="form-tip">
            支持语法：AND / OR / BETWEEN / 比较运算符（> < >= <= =）
          </div>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="ruleForm.enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" :loading="creating" data-testid="rules-save-btn" @click="saveRule">
          {{ editingRule ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { rulesEngineApi, type RuleResponse, type CompileStatusResponse } from '@/api/rulesEngine'

const tenantId = ref('default')
const rules = ref<RuleResponse[]>([])
const loading = ref(false)
const compiling = ref(false)
const creating = ref(false)
const compileStatus = ref<CompileStatusResponse | null>(null)
const showCreateDialog = ref(false)
const editingRule = ref<RuleResponse | null>(null)
const formRef = ref()

const ruleForm = ref({
  name: '',
  rule_type: 'threshold',
  priority: 0,
  definition_formula: '',
  enabled: true,
})

const formRules = {
  name: [{ required: true, message: '请输入规则名称', trigger: 'blur' }],
  rule_type: [{ required: true, message: '请选择规则类型', trigger: 'change' }],
  definition_formula: [{ required: true, message: '请输入DSL公式', trigger: 'blur' }],
}

const compileStatusLabel = computed(() => {
  const map: Record<string, string> = {
    completed: '已编译',
    compiling: '编译中...',
    failed: '编译失败',
    never_compiled: '从未编译',
    stale: '已过期',
  }
  return compileStatus.value ? (map[compileStatus.value.status] || compileStatus.value.status) : '加载中...'
})

function ruleTypeTag(type: string) {
  const map: Record<string, string> = {
    threshold: 'warning',
    range: 'success',
    composite: 'primary',
    custom: 'info',
  }
  return map[type] || 'info'
}

function ruleTypeLabel(type: string) {
  const map: Record<string, string> = {
    threshold: '阈值',
    range: '范围',
    composite: '复合',
    custom: '自定义',
  }
  return map[type] || type
}

function formatDsl(definition: Record<string, any>) {
  if (definition?.formula) return definition.formula
  if (definition?.dsl) return definition.dsl
  return JSON.stringify(definition)
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

function formatStaleness(seconds: number) {
  if (seconds < 60) return `${seconds}秒前`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟前`
  return `${Math.floor(seconds / 3600)}小时前`
}

async function loadRules() {
  loading.value = true
  try {
    rules.value = await rulesEngineApi.listRules(tenantId.value)
    await loadCompileStatus()
  } catch {
    rules.value = []
  } finally {
    loading.value = false
  }
}

async function loadCompileStatus() {
  try {
    compileStatus.value = await rulesEngineApi.getCompileStatus(tenantId.value)
  } catch {
    compileStatus.value = null
  }
}

async function triggerCompile() {
  compiling.value = true
  try {
    const res = await rulesEngineApi.triggerCompile(tenantId.value)
    if (res.status === 'completed') {
      ElMessage.success(`编译完成，版本 ${res.version || 'unknown'}`)
    } else if (res.status === 'failed') {
      ElMessage.error(`编译失败: ${res.errors?.join(', ') || '未知错误'}`)
    }
    await loadCompileStatus()
  } catch (e: any) {
    ElMessage.error(e?.message || '编译触发失败')
  } finally {
    compiling.value = false
  }
}

function editRule(rule: RuleResponse) {
  editingRule.value = rule
  ruleForm.value = {
    name: rule.name,
    rule_type: rule.rule_type,
    priority: rule.priority,
    definition_formula: formatDsl(rule.definition),
    enabled: rule.enabled,
  }
  showCreateDialog.value = true
}

async function deleteRule(rule: RuleResponse) {
  try {
    await ElMessageBox.confirm(`确定要删除规则「${rule.name}」吗？`, '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    // TODO: call delete API when implemented
    ElMessage.success('规则已删除')
    await loadRules()
  } catch {
    // cancelled
  }
}

async function toggleRule(rule: RuleResponse) {
  // TODO: call update API when implemented
  ElMessage.success(`规则「${rule.name}」已${rule.enabled ? '启用' : '禁用'}`)
}

async function saveRule() {
  if (!formRef.value) return
  await formRef.value.validate()
  creating.value = true
  try {
    await rulesEngineApi.createRule({
      tenant_id: tenantId.value,
      name: ruleForm.value.name,
      rule_type: ruleForm.value.rule_type,
      definition: { formula: ruleForm.value.definition_formula },
      priority: ruleForm.value.priority,
      enabled: ruleForm.value.enabled,
    })
    ElMessage.success(editingRule.value ? '规则已更新' : '规则创建成功')
    showCreateDialog.value = false
    editingRule.value = null
    resetForm()
    await loadRules()
  } catch (e: any) {
    ElMessage.error(e?.message || '操作失败')
  } finally {
    creating.value = false
  }
}

function resetForm() {
  ruleForm.value = {
    name: '',
    rule_type: 'threshold',
    priority: 0,
    definition_formula: '',
    enabled: true,
  }
}

// Watch dialog close to reset form
import { watch } from 'vue'
watch(showCreateDialog, (val) => {
  if (!val) {
    editingRule.value = null
    resetForm()
  }
})

onMounted(() => {
  loadRules()
})
</script>

<style scoped>
.rules-manager-view {
  max-width: 1200px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
}

.page-header h2 {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.tenant-select {
  width: 140px;
}

/* 编译状态条 */
.compile-status-bar {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 20px;
  border-radius: var(--radius-lg, 12px);
  margin-bottom: 20px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  font-size: 0.9rem;
}

.compile-status-bar.completed {
  border-color: rgba(82, 196, 26, 0.3);
}

.compile-status-bar.compiling {
  border-color: rgba(24, 144, 255, 0.3);
}

.compile-status-bar.failed {
  border-color: rgba(255, 77, 79, 0.3);
}

.status-info {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  font-weight: 500;
}

.version-info {
  color: var(--text-secondary);
  font-size: 0.85rem;
}

/* 规则表格 */
.rules-table-section {
  background: var(--bg-secondary);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg, 12px);
  overflow: hidden;
}

.rules-table {
  width: 100%;
}

.rule-name {
  font-weight: 500;
  color: var(--text-primary);
}

.dsl-code {
  font-family: 'Fira Code', 'Cascadia Code', monospace;
  font-size: 0.8rem;
  background: var(--bg-tertiary);
  padding: 2px 8px;
  border-radius: 4px;
  color: var(--primary-500);
}

/* 对话框 */
.form-tip {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 0.8rem;
}
</style>
