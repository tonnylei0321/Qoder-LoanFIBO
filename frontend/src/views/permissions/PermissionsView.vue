<template>
  <div class="permissions-page">
    <div class="page-header">
      <h2>权限管理</h2>
    </div>

    <div class="split-layout">
      <!-- 左侧：角色列表 -->
      <div class="left-panel">
        <div class="panel-title">角色列表</div>
        <div v-loading="rolesLoading" class="role-list">
          <div
            v-for="role in roles"
            :key="role.id"
            class="role-item"
            :class="{ active: selectedRole?.id === role.id }"
            @click="selectRole(role)"
          >
            <div class="role-name">{{ role.name }}</div>
            <div class="role-meta">
              <el-tag size="small" type="info">{{ role.code }}</el-tag>
              <el-tag :type="role.status === 'active' ? 'success' : 'warning'" size="small">
                {{ role.status === 'active' ? '启用' : '禁用' }}
              </el-tag>
            </div>
            <div class="role-perm-count">
              已授权 <strong>{{ role.menu_codes?.length || 0 }}</strong> 个菜单
            </div>
          </div>
          <el-empty v-if="!rolesLoading && roles.length === 0" description="暂无角色" :image-size="60" />
        </div>
      </div>

      <!-- 右侧：菜单树打勾授权 -->
      <div class="right-panel">
        <template v-if="selectedRole">
          <div class="panel-title">
            <span>{{ selectedRole.name }} — 菜单与页面权限</span>
            <div style="display:flex;gap:8px;align-items:center">
              <span class="count-badge">
                {{ selectedMenuCodes.length }} / {{ totalLeafCount }} 项已授权
              </span>
              <el-button type="primary" size="small" :loading="saving" @click="saveMenuPermissions">
                保存授权
              </el-button>
            </div>
          </div>

          <div class="menu-tree-container">
            <!-- 全选 -->
            <div class="select-all-row">
              <el-checkbox
                :model-value="isAllSelected"
                :indeterminate="isIndeterminate"
                @change="toggleAll"
              >
                <span class="select-all-label">全选 / 全不选</span>
              </el-checkbox>
            </div>

            <!-- 树节点 -->
            <div v-for="node in MENU_TREE" :key="nodeKey(node)" class="tree-node">
              <!-- 顶级叶子（如 dashboard）-->
              <div v-if="node.type === 'leaf'" class="leaf-row top-leaf">
                <el-checkbox
                  :model-value="selectedMenuCodes.includes(node.routeName)"
                  @change="(v: boolean) => toggleLeaf(node.routeName, v)"
                >
                  <el-icon class="leaf-icon"><Monitor /></el-icon>
                  <span class="leaf-label">{{ node.label }}</span>
                  <el-tag size="small" class="route-tag">{{ node.routeName }}</el-tag>
                </el-checkbox>
              </div>

              <!-- 分组 -->
              <div v-else class="group-node">
                <div class="group-header">
                  <el-checkbox
                    :model-value="isGroupChecked(node)"
                    :indeterminate="isGroupIndeterminate(node)"
                    @change="toggleGroup(node)"
                  >
                    <el-icon class="group-icon"><Menu /></el-icon>
                    <span class="group-label">{{ node.label }}</span>
                    <el-tag size="small" type="primary" class="group-count-tag">
                      {{ checkedCountInGroup(node) }}/{{ node.children.length }}
                    </el-tag>
                  </el-checkbox>
                </div>
                <div class="group-children">
                  <div
                    v-for="child in node.children"
                    :key="child.routeName"
                    class="leaf-row"
                  >
                    <el-checkbox
                      :model-value="selectedMenuCodes.includes(child.routeName)"
                      @change="(v: boolean) => toggleLeaf(child.routeName, v)"
                    >
                      <el-icon class="leaf-icon"><Document /></el-icon>
                      <span class="leaf-label">{{ child.label }}</span>
                      <el-tag size="small" class="route-tag">{{ child.routeName }}</el-tag>
                    </el-checkbox>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </template>

        <div v-else class="empty-right">
          <el-empty description="请从左侧选择一个角色" :image-size="80" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Menu, Document, Monitor } from '@element-plus/icons-vue'
import { getRoles, assignRoleMenuCodes } from '@/api/rbac'
import { MENU_TREE, ALL_MENU_ROUTE_NAMES } from '@/utils/menuTree'
import type { MenuGroup } from '@/utils/menuTree'
import type { Role } from '@/types'

// ── 状态 ──────────────────────────────────────────────────────────────────
const rolesLoading = ref(false)
const saving = ref(false)

const roles = ref<Role[]>([])
const selectedRole = ref<Role | null>(null)
const selectedMenuCodes = ref<string[]>([])

// ── 计算 ──────────────────────────────────────────────────────────────────
const totalLeafCount = computed(() => ALL_MENU_ROUTE_NAMES.length)

const isAllSelected = computed(() =>
  ALL_MENU_ROUTE_NAMES.every(r => selectedMenuCodes.value.includes(r))
)

const isIndeterminate = computed(() => {
  const cnt = ALL_MENU_ROUTE_NAMES.filter(r => selectedMenuCodes.value.includes(r)).length
  return cnt > 0 && cnt < ALL_MENU_ROUTE_NAMES.length
})

function nodeKey(node: typeof MENU_TREE[number]): string {
  return node.type === 'group' ? node.key : node.routeName
}

function isGroupChecked(node: MenuGroup): boolean {
  return node.children.every(c => selectedMenuCodes.value.includes(c.routeName))
}

function isGroupIndeterminate(node: MenuGroup): boolean {
  const cnt = node.children.filter(c => selectedMenuCodes.value.includes(c.routeName)).length
  return cnt > 0 && cnt < node.children.length
}

function checkedCountInGroup(node: MenuGroup): number {
  return node.children.filter(c => selectedMenuCodes.value.includes(c.routeName)).length
}

// ── 交互 ──────────────────────────────────────────────────────────────────
function toggleAll(checked: boolean) {
  selectedMenuCodes.value = checked ? [...ALL_MENU_ROUTE_NAMES] : []
}

function toggleLeaf(routeName: string, checked: boolean) {
  if (checked) {
    if (!selectedMenuCodes.value.includes(routeName)) {
      selectedMenuCodes.value = [...selectedMenuCodes.value, routeName]
    }
  } else {
    selectedMenuCodes.value = selectedMenuCodes.value.filter(r => r !== routeName)
  }
}

function toggleGroup(node: MenuGroup) {
  const allChecked = isGroupChecked(node)
  if (allChecked) {
    selectedMenuCodes.value = selectedMenuCodes.value.filter(
      r => !node.children.some(c => c.routeName === r)
    )
  } else {
    const toAdd = node.children.map(c => c.routeName).filter(r => !selectedMenuCodes.value.includes(r))
    selectedMenuCodes.value = [...selectedMenuCodes.value, ...toAdd]
  }
}

// ── 数据加载 ──────────────────────────────────────────────────────────────
const loadRoles = async () => {
  rolesLoading.value = true
  try {
    roles.value = await getRoles()
  } finally {
    rolesLoading.value = false
  }
}

function selectRole(role: Role) {
  selectedRole.value = role
  selectedMenuCodes.value = [...(role.menu_codes || [])]
}

async function saveMenuPermissions() {
  if (!selectedRole.value) return
  saving.value = true
  try {
    const updatedRole = await assignRoleMenuCodes(selectedRole.value.id, selectedMenuCodes.value)
    const idx = roles.value.findIndex(r => r.id === selectedRole.value!.id)
    if (idx >= 0) roles.value[idx] = updatedRole
    selectedRole.value = updatedRole
    ElMessage.success('菜单权限已保存')
  } catch (e: any) {
    ElMessage.error('保存失败: ' + (e.message || e))
  } finally {
    saving.value = false
  }
}

onMounted(() => loadRoles())
</script>

<style scoped>
.permissions-page {
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
  font-size: 1.25rem;
}

.split-layout {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.left-panel {
  width: 240px;
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

.count-badge {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* ── 左侧角色列表 ── */
.role-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 0;
}

.role-item {
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.15s;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.role-item:hover { background: var(--el-fill-color-light); }

.role-item.active {
  background: var(--el-color-primary-light-9);
  border-left: 3px solid var(--el-color-primary);
}

.role-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}

.role-meta {
  display: flex;
  gap: 4px;
  margin-bottom: 4px;
}

.role-perm-count {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* ── 右侧菜单树 ── */
.menu-tree-container {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.select-all-row {
  padding: 8px 12px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  margin-bottom: 12px;
  border: 1px solid var(--el-border-color-lighter);
}

.select-all-label {
  font-weight: 600;
  font-size: 13px;
}

.tree-node {
  margin-bottom: 10px;
}

/* 顶级叶子 */
.top-leaf {
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
}

/* 分组 */
.group-node {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  overflow: hidden;
}

.group-header {
  padding: 10px 14px;
  background: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--el-border-color-lighter);
  font-weight: 600;
}

.group-children {
  padding: 4px 0;
  display: flex;
  flex-wrap: wrap;
  gap: 2px 0;
}

.leaf-row {
  padding: 7px 14px 7px 32px;
  width: 50%;
  box-sizing: border-box;
  transition: background 0.1s;
}

.leaf-row:hover {
  background: var(--el-fill-color-light);
}

/* 图标和标签 */
.leaf-icon {
  color: var(--el-text-color-secondary);
  margin-right: 5px;
  vertical-align: middle;
}

.group-icon {
  color: var(--el-color-primary);
  margin-right: 5px;
  vertical-align: middle;
}

.leaf-label {
  font-size: 13px;
  vertical-align: middle;
}

.group-label {
  font-size: 13px;
  font-weight: 600;
  vertical-align: middle;
}

.route-tag {
  margin-left: 6px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 10px;
  vertical-align: middle;
}

.group-count-tag {
  margin-left: 8px;
  vertical-align: middle;
}

.empty-right {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
