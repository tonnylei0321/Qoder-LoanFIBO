<template>
  <div class="roles-page">
    <div class="admin-page-header">
      <div class="title-area">
        <h2>角色管理</h2>
        <span class="subtitle">配置系统角色并分配相应权限</span>
      </div>
      <div class="actions">
        <el-button type="primary" @click="openDialog()">
          <el-icon><Plus /></el-icon> 添加角色
        </el-button>
      </div>
    </div>

    <div class="admin-table-card">
      <el-table :data="roles" v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column label="角色" min-width="200">
          <template #default="{ row }">
            <div class="entity-row">
              <div class="entity-avatar purple">{{ row.name.charAt(0) }}</div>
              <div class="entity-info">
                <span class="entity-name">{{ row.name }}</span>
                <span class="code-badge" style="margin-top:2px">{{ row.code }}</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="描述" min-width="180">
          <template #default="{ row }">
            <span v-if="row.description" style="font-size:13px">{{ row.description }}</span>
            <span v-else class="empty-placeholder">-</span>
          </template>
        </el-table-column>
        <el-table-column label="权限数" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="primary">{{ row.permissions?.length || 0 }}项</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <span class="pill" :class="row.status === 'active' ? 'pill-success' : 'pill-info'">
              {{ row.status === 'active' ? '启用' : '禁用' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right" align="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openDialog(row)">编辑</el-button>
            <el-button type="warning" link size="small" @click="openPermDialog(row)">权限</el-button>
            <el-button type="danger" link size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Add/Edit Dialog -->
    <el-dialog v-model="showDialog" :title="editingRole ? '编辑角色' : '添加角色'" width="480px" destroy-on-close>
      <el-form :model="roleForm" label-width="80px">
        <el-form-item label="角色名称" required>
          <el-input v-model="roleForm.name" placeholder="如：操作员" @input="onNameInput" />
        </el-form-item>
        <el-form-item label="角色编码">
          <el-input
            v-model="roleForm.code"
            :placeholder="editingRole ? '编辑时不可修改' : '自动生成，可手动修改'"
            :disabled="!!editingRole"
          >
            <template v-if="!editingRole" #suffix>
              <el-tooltip content="根据名称自动生成" placement="top">
                <el-icon style="cursor:pointer" @click="generateCode"><MagicStick /></el-icon>
              </el-tooltip>
            </template>
          </el-input>
          <div v-if="!editingRole" style="font-size:12px;color:var(--el-text-color-secondary);margin-top:4px">当前：{{ roleForm.code || '(输入名称自动生成)' }}</div>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="roleForm.description" type="textarea" :rows="2" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitRole">确定</el-button>
      </template>
    </el-dialog>

    <!-- Permission Assignment Dialog -->
    <el-dialog v-model="showPermDialog" title="分配权限" width="560px" destroy-on-close>
      <div v-for="mod in permissionsByModule" :key="mod.module" style="margin-bottom:16px">
        <div style="font-weight:600;margin-bottom:6px;color:var(--text-primary)">{{ mod.module }}</div>
        <el-checkbox-group v-model="selectedPermIds">
          <el-checkbox v-for="p in mod.items" :key="p.id" :value="p.id" :label="p.id">
            {{ p.name }} <span style="color:var(--text-muted);font-size:0.8em">({{ p.code }})</span>
          </el-checkbox>
        </el-checkbox-group>
      </div>
      <template #footer>
        <el-button @click="showPermDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitPermissions">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MagicStick } from '@element-plus/icons-vue'
import { getRoles, createRole, updateRole, deleteRole, assignRolePermissions } from '@/api/rbac'
import { getPermissions } from '@/api/rbac'
import type { Role, Permission } from '@/types'

const loading = ref(false)
const submitting = ref(false)
const showDialog = ref(false)
const showPermDialog = ref(false)
const editingRole = ref<Role | null>(null)
const permTargetRole = ref<Role | null>(null)

const roles = ref<Role[]>([])
const allPermissions = ref<Permission[]>([])
const selectedPermIds = ref<number[]>([])

const roleForm = reactive({ name: '', code: '', description: '' })

/** 将中文字符转换为拼音首字母（简单映射），英文则直接保留 */
function toPinyinInitial(char: string): string {
  const code = char.charCodeAt(0)
  // 英文、数字、下划线直接保留
  if ((code >= 65 && code <= 90) || (code >= 97 && code <= 122) || (code >= 48 && code <= 57) || char === '_') {
    return char.toLowerCase()
  }
  // 中文字符：根据 Unicode 区间判断拼音首字母
  if (code >= 0x4e00 && code <= 0x9fff) {
    // Unicode 区间范围判断（简化版）
    if (code < 0x4e16) return 'a'
    if (code < 0x516c) return 'b'
    if (code < 0x5587) return 'c'
    if (code < 0x591a) return 'd'
    if (code < 0x5c18) return 'e'
    if (code < 0x5fef) return 'f'
    if (code < 0x62c6) return 'g'
    if (code < 0x6c1f) return 'h'
    if (code < 0x6fef) return 'j'
    if (code < 0x72fa) return 'k'
    if (code < 0x76d7) return 'l'
    if (code < 0x79dd) return 'm'
    if (code < 0x7eca) return 'n'
    if (code < 0x818f) return 'o'
    if (code < 0x84c6) return 'p'
    if (code < 0x897e) return 'q'
    if (code < 0x8c30) return 'r'
    if (code < 0x9019) return 's'
    if (code < 0x9164) return 't'
    if (code < 0x9685) return 'w'
    if (code < 0x9af2) return 'x'
    if (code < 0x9de0) return 'y'
    return 'z'
  }
  return ''
}

/** 生成角色编码：中文名转拼音首字母 + 加内容描述语义 */
function generateCodeFromName(name: string): string {
  if (!name) return ''
  const initials = Array.from(name)
    .map(c => toPinyinInitial(c))
    .filter(Boolean)
    .join('')
  return 'role_' + initials
}

function generateCode() {
  if (!editingRole.value) {
    roleForm.code = generateCodeFromName(roleForm.name)
  }
}

function onNameInput(val: string) {
  // 新建时自动生成编码
  if (!editingRole.value) {
    roleForm.code = generateCodeFromName(val)
  }
}

const permissionsByModule = computed(() => {
  const map: Record<string, Permission[]> = {}
  for (const p of allPermissions.value) {
    const module = p.module
    if (!map[module]) {
      map[module] = []
    }
    const items = map[module]
    if (items) items.push(p)
  }
  return Object.entries(map).map(([module, items]) => ({ module, items }))
})

const loadRoles = async () => {
  loading.value = true
  try { roles.value = await getRoles() }
  finally { loading.value = false }
}

const loadPermissions = async () => {
  allPermissions.value = await getPermissions()
}

const openDialog = (row?: Role) => {
  editingRole.value = row || null
  roleForm.name = row?.name || ''
  roleForm.code = row?.code || ''
  roleForm.description = row?.description || ''
  showDialog.value = true
}

const openPermDialog = (row: Role) => {
  permTargetRole.value = row
  selectedPermIds.value = row.permissions?.map(p => p.id) || []
  showPermDialog.value = true
}

const submitRole = async () => {
  if (!roleForm.name) { ElMessage.warning('请填写角色名称'); return }
  // 新建时自动生成编码（如果还没有）
  if (!editingRole.value && !roleForm.code) {
    roleForm.code = generateCodeFromName(roleForm.name)
  }
  if (!editingRole.value && !roleForm.code) { ElMessage.warning('无法生成角色编码，请手动输入'); return }
  submitting.value = true
  try {
    if (editingRole.value) {
      await updateRole(editingRole.value.id, { name: roleForm.name, description: roleForm.description })
      ElMessage.success('更新成功')
    } else {
      await createRole({ name: roleForm.name, code: roleForm.code, description: roleForm.description || undefined })
      ElMessage.success('创建成功')
    }
    showDialog.value = false
    loadRoles()
  } finally { submitting.value = false }
}

const submitPermissions = async () => {
  if (!permTargetRole.value) return
  submitting.value = true
  try {
    await assignRolePermissions(permTargetRole.value.id, selectedPermIds.value)
    ElMessage.success('权限分配成功')
    showPermDialog.value = false
    loadRoles()
  } finally { submitting.value = false }
}

const handleDelete = async (row: Role) => {
  try {
    await ElMessageBox.confirm('确定要删除该角色吗？', '提示', { type: 'warning' })
    await deleteRole(row.id)
    ElMessage.success('删除成功')
    loadRoles()
  } catch { /* cancelled */ }
}

onMounted(() => { loadRoles(); loadPermissions() })
</script>

<style scoped>
.roles-page {
  padding-bottom: 40px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
</style>
