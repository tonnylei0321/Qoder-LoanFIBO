/**
 * 菜单树定义 — 与 MainLayout 侧边栏保持严格同步
 * routeName 对应 Vue Router 的 name 字段
 */

export interface MenuLeaf {
  type: 'leaf'
  label: string
  routeName: string
}

export interface MenuGroup {
  type: 'group'
  label: string
  key: string // 分组唯一 key（也可加入 menu_codes 作为父级授权）
  children: MenuLeaf[]
}

export type MenuTreeNode = MenuGroup | MenuLeaf

export const MENU_TREE: MenuTreeNode[] = [
  {
    type: 'leaf',
    label: '语义对齐看板',
    routeName: 'dashboard',
  },
  {
    type: 'group',
    key: 'data',
    label: '数据管理',
    children: [
      { type: 'leaf', label: 'DDL 文件管理', routeName: 'ddl-files' },
      { type: 'leaf', label: 'TTL 文件管理', routeName: 'ttl-files' },
      { type: 'leaf', label: '任务管理', routeName: 'jobs' },
    ],
  },
  {
    type: 'group',
    key: 'rules',
    label: '规则引擎',
    children: [
      { type: 'leaf', label: 'NLQ 查询', routeName: 'nlq-query' },
      { type: 'leaf', label: '规则管理', routeName: 'rules-manager' },
      { type: 'leaf', label: '编译状态', routeName: 'compile-status' },
    ],
  },
  {
    type: 'group',
    key: 'quality',
    label: '质量控制',
    children: [
      { type: 'leaf', label: '稽核管理', routeName: 'reviews' },
    ],
  },
  {
    type: 'group',
    key: 'loan',
    label: '信贷分析',
    children: [
      { type: 'leaf', label: '贷前尽调', routeName: 'pre-loan' },
      { type: 'leaf', label: '贷后监控', routeName: 'post-loan' },
      { type: 'leaf', label: '供应链金融', routeName: 'supply-chain' },
    ],
  },
  {
    type: 'group',
    key: 'sync',
    label: 'GraphDB 同步',
    children: [
      { type: 'leaf', label: '图谱浏览', routeName: 'graph-explorer' },
      { type: 'leaf', label: '实例管理', routeName: 'instances' },
      { type: 'leaf', label: '版本管理', routeName: 'versions' },
      { type: 'leaf', label: '同步任务', routeName: 'sync-tasks' },
    ],
  },
  {
    type: 'group',
    key: 'org',
    label: '主体管理',
    children: [
      { type: 'leaf', label: '融资企业', routeName: 'org-manager' },
      { type: 'leaf', label: '授权项管理', routeName: 'auth-scopes' },
    ],
  },
  {
    type: 'group',
    key: 'agent',
    label: '代理管理',
    children: [
      { type: 'leaf', label: '企业管理', routeName: 'agent-orgs' },
      { type: 'leaf', label: '代理状态', routeName: 'agent-status' },
      { type: 'leaf', label: '审计日志', routeName: 'agent-audit' },
    ],
  },
  {
    type: 'group',
    key: 'system',
    label: '系统',
    children: [
      { type: 'leaf', label: '用户管理', routeName: 'users' },
      { type: 'leaf', label: '角色管理', routeName: 'roles' },
      { type: 'leaf', label: '权限管理', routeName: 'permissions' },
      { type: 'leaf', label: '系统设置', routeName: 'settings' },
    ],
  },
]

/** 所有叶子节点的 routeName 列表 */
export const ALL_MENU_ROUTE_NAMES: string[] = MENU_TREE.flatMap(node =>
  node.type === 'group' ? node.children.map(c => c.routeName) : [node.routeName]
)
