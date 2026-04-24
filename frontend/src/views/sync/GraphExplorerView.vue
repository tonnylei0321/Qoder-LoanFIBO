<template>
  <div class="graph-explorer">
    <!-- Header -->
    <div class="page-header-modern">
      <div class="header-content">
        <div class="header-icon">
          <el-icon><Connection /></el-icon>
        </div>
        <div class="header-text">
          <h1>风控指标体系</h1>
          <p class="subtitle">信贷风控指标知识网络</p>
        </div>
      </div>
      <!-- Instance Selector -->
      <el-select
        v-model="selectedInstanceId"
        placeholder="选择知识库"
        clearable
        style="width: 180px"
        @change="handleInstanceChange"
      >
        <el-option
          v-for="inst in instances"
          :key="inst.id"
          :label="inst.name"
          :value="inst.id"
        />
      </el-select>
    </div>

    <div class="explorer-body">
      <!-- Left Panel: Facet Tree + Search -->
      <aside class="left-panel">
        <div class="search-bar">
          <el-input
            v-model="searchQuery"
            placeholder="搜索指标或数据项，如：流动比率、应收账款"
            clearable
            @keyup.enter="handleBusinessSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          <el-button type="primary" @click="handleBusinessSearch" :loading="searching">
            搜索
          </el-button>
        </div>

        <!-- Search Results -->
        <div v-if="searchResults.length > 0" class="search-results">
          <div class="list-header">
            <span class="list-title">搜索结果</span>
            <el-button text size="small" @click="clearSearch">清除</el-button>
          </div>
          <div
            v-for="item in searchResults"
            :key="item.uri"
            class="entity-item"
            :class="{ active: selectedUri === item.uri }"
            @click="handleEntityClick(item.uri, item.label, item.facet)"
          >
            <div class="entity-label">
              <el-tag size="small" :type="facetTagType(item.facet)" class="facet-tag">{{ facetIcon(item.facet) }}</el-tag>
              {{ item.label }}
            </div>
          </div>
        </div>

        <!-- Facet Tree -->
        <div v-else class="facet-tree-wrapper">
          <div class="list-header">
            <span class="list-title">指标分类</span>
          </div>
          <div class="facet-tree" v-loading="loadingFacets">
            <div v-for="facet in facetTree" :key="facet.id" class="facet-group">
              <div
                class="facet-root"
                :class="{ active: activeFacet === facet.id }"
                @click="toggleFacet(facet.id)"
              >
                <el-icon class="facet-expand-icon">
                  <ArrowRight v-if="activeFacet !== facet.id" />
                  <ArrowDown v-else />
                </el-icon>
                <span class="facet-icon-label">{{ facetIcon(facet.icon) }}</span>
                <span class="facet-label">{{ facet.label }}</span>
              </div>
              <!-- Children -->
              <div v-if="activeFacet === facet.id && facet.children.length > 0" class="facet-children">
                <div
                  v-for="child in facet.children"
                  :key="child.id"
                  class="facet-child"
                  :class="{ active: activeSubFacet === child.id }"
                  @click="selectSubFacet(facet.id, child)"
                >
                  <span>{{ child.label }}</span>
                </div>
              </div>
              <!-- Leaf entities for active facet -->
              <div v-if="activeFacet === facet.id" class="facet-entities" v-loading="loadingEntities">
                <div
                  v-for="entity in facetEntities"
                  :key="entity.uri"
                  class="entity-item"
                  :class="{ active: selectedUri === entity.uri }"
                  @click="handleEntityClick(entity.uri, entity.label, facet.icon)"
                >
                  <div class="entity-label">{{ entity.label || shortUri(entity.uri) }}</div>
                </div>
                <el-empty v-if="!loadingEntities && facetEntities.length === 0" description="暂无数据" :image-size="40" />
              </div>
            </div>
          </div>
        </div>
      </aside>

      <!-- Right Panel: Graph + Details -->
      <main class="right-panel">
        <!-- Graph Area -->
        <div class="graph-container" ref="graphContainerRef">
          <div class="graph-toolbar">
            <el-button-group>
              <el-button size="small" @click="fitGraph">
                <el-icon><FullScreen /></el-icon> 适配
              </el-button>
              <el-button size="small" @click="resetGraph">
                <el-icon><RefreshRight /></el-icon> 重置
              </el-button>
            </el-button-group>
            <span class="graph-info" v-if="selectedLabel">
              当前: {{ selectedLabel }}
            </span>
          </div>
          <div class="cytoscape-mount" ref="cyMountRef"></div>
          <div class="graph-legend" v-if="hasGraphData">
            <span class="legend-item"><i class="legend-dot" style="background:#f59e0b"></i>当前选中</span>
            <span class="legend-item"><i class="legend-dot" style="background:#8b5cf6"></i>风控指标</span>
            <span class="legend-item"><i class="legend-dot" style="background:#6366f1"></i>数据来源</span>
            <span class="legend-item"><i class="legend-dot" style="background:#10b981"></i>会计科目</span>
            <span class="legend-item"><i class="legend-dot" style="background:#06b6d4"></i>应用场景</span>
            <span class="legend-item"><i class="legend-dot" style="background:#f97316"></i>融资企业</span>
            <span class="legend-item"><i class="legend-dot" style="background:#eab308"></i>授权项</span>
            <span class="legend-item"><i class="legend-dot" style="background:#94a3b8"></i>其他</span>
          </div>
          <el-empty v-if="!hasGraphData" description="选择左侧指标以查看关系网络" />
        </div>

        <!-- Indicator Detail Panel (4 Tabs) -->
        <div class="detail-panel" v-if="indicatorDetail">
          <div class="detail-header">
            <h3>{{ indicatorDetail.tab1.label }}</h3>
            <el-button text size="small" @click="indicatorDetail = null">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
          <el-tabs v-model="activeTab" class="detail-tabs">
            <!-- Tab 1: 它是什么 -->
            <el-tab-pane label="它是什么" name="what">
              <div class="tab-content">
                <div v-if="indicatorDetail.tab1.comment" class="info-row">
                  <span class="info-label">业务解释</span>
                  <span class="info-value highlight">{{ indicatorDetail.tab1.comment }}</span>
                </div>
                <div v-if="indicatorDetail.tab1.scenarios.length" class="info-row">
                  <span class="info-label">适用场景</span>
                  <span class="info-value">
                    <el-tag v-for="s in indicatorDetail.tab1.scenarios" :key="s.uri" type="success" size="small" class="mr-4">{{ s.label }}</el-tag>
                  </span>
                </div>
                <div v-if="indicatorDetail.tab1.subjects.length" class="info-row">
                  <span class="info-label">业务分类</span>
                  <span class="info-value">
                    <el-tag v-for="s in indicatorDetail.tab1.subjects" :key="s" type="info" size="small" class="mr-4">{{ s }}</el-tag>
                  </span>
                </div>
                <div v-if="indicatorDetail.tab1.closeMatches.length" class="info-row">
                  <span class="info-label">对标国际标准</span>
                  <span class="info-value">
                    <el-tag v-for="m in indicatorDetail.tab1.closeMatches" :key="m" type="warning" size="small" class="mr-4">{{ fiboShortName(m) }}</el-tag>
                  </span>
                </div>
              </div>
            </el-tab-pane>

            <!-- Tab 2: 怎么算 -->
            <el-tab-pane label="怎么算" name="how">
              <div class="tab-content">
                <div v-if="indicatorDetail.tab2.formula" class="info-row">
                  <span class="info-label">计算公式</span>
                  <span class="info-value formula">{{ indicatorDetail.tab2.formula }}</span>
                </div>
                <div v-if="indicatorDetail.tab2.tables.length" class="info-row">
                  <span class="info-label">数据来源</span>
                  <span class="info-value">
                    <el-tag v-for="t in indicatorDetail.tab2.tables" :key="t.uri" size="small" class="mr-4 clickable" @click="navigateToUri(t.uri)">{{ t.label }}</el-tag>
                  </span>
                </div>
                <div v-if="indicatorDetail.tab2.accounts.length" class="info-row">
                  <span class="info-label">涉及科目</span>
                  <span class="info-value">
                    <el-tag v-for="a in indicatorDetail.tab2.accounts" :key="a.uri" type="success" size="small" class="mr-4">{{ a.label }}</el-tag>
                  </span>
                </div>
                <div v-if="indicatorDetail.tab2.fields.length" class="info-row">
                  <span class="info-label">涉及字段</span>
                  <span class="info-value field-list">
                    <el-tag v-for="f in indicatorDetail.tab2.fields" :key="f.uri" size="small" type="info" class="mr-4">{{ f.label }}</el-tag>
                  </span>
                </div>
                <el-collapse v-if="indicatorDetail.tab2.sql" class="tech-collapse">
                  <el-collapse-item title="查看技术口径（仅技术人员查看）">
                    <pre class="sql-block">{{ indicatorDetail.tab2.sql }}</pre>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </el-tab-pane>

            <!-- Tab 3: 看数据 -->
            <el-tab-pane label="看数据" name="data">
              <div class="tab-content">
                <div v-if="indicatorDetail.tab3.length" class="data-filter">
                  <span class="info-label">选择机构</span>
                  <el-select
                    v-model="selectedOrg"
                    placeholder="全部机构"
                    clearable
                    size="small"
                    style="width: 160px"
                  >
                    <el-option
                      v-for="org in availableOrgs"
                      :key="org"
                      :label="org"
                      :value="org"
                    />
                  </el-select>
                  <span class="data-count">共 {{ filteredTab3Data.length }} 条记录</span>
                </div>
                <el-table v-if="filteredTab3Data.length" :data="filteredTab3Data" size="small" stripe>
                  <el-table-column label="期间" prop="period" width="100" />
                  <el-table-column label="机构" prop="org" width="120" />
                  <el-table-column label="数值" width="120">
                    <template #default="{ row }">
                      <span class="data-value">{{ row.value }}</span>
                    </template>
                  </el-table-column>
                  <el-table-column label="计算时间" prop="computedAt" />
                </el-table>
                <el-empty v-else :description="indicatorDetail.tab3.length ? '该机构暂无数据' : '暂无历史数据，需先执行计算任务生成指标值'" :image-size="40" />
              </div>
            </el-tab-pane>

            <!-- Tab 4: 关联指标 -->
            <el-tab-pane label="关联指标" name="related">
              <div class="tab-content">
                <div v-if="indicatorDetail.tab4.sameTopic.length" class="related-section">
                  <h4>同主题指标</h4>
                  <div class="related-list">
                    <el-tag
                      v-for="r in indicatorDetail.tab4.sameTopic"
                      :key="r.uri" size="small" class="mr-4 clickable"
                      @click="navigateToUri(r.uri)"
                    >{{ r.label }}</el-tag>
                  </div>
                </div>
                <div v-if="indicatorDetail.tab4.sharedSource.length" class="related-section">
                  <h4>共享数据源</h4>
                  <div class="related-list">
                    <el-tag
                      v-for="r in indicatorDetail.tab4.sharedSource"
                      :key="r.uri" size="small" type="info" class="mr-4 clickable"
                      @click="navigateToUri(r.uri)"
                    >{{ r.label }}</el-tag>
                  </div>
                </div>
                <el-empty v-if="!indicatorDetail.tab4.sameTopic.length && !indicatorDetail.tab4.sharedSource.length" description="暂无关联指标" :image-size="40" />
              </div>
            </el-tab-pane>
          </el-tabs>
        </div>

        <!-- Non-indicator entity detail (simplified) -->
        <div class="detail-panel" v-else-if="entityDetail">
          <div class="detail-header">
            <h3>{{ entityDetailLabel }}</h3>
            <el-button text size="small" @click="entityDetail = null">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item v-for="prop in businessProps" :key="prop.label" :label="prop.label">
              <span v-if="prop.isUri" class="prop-uri" @click="navigateToUri(prop.value!)" :title="prop.value">{{ prop.display }}</span>
              <span v-else>{{ prop.display }}</span>
            </el-descriptions-item>
          </el-descriptions>
          <el-collapse class="tech-collapse">
            <el-collapse-item title="更多技术信息">
              <el-table :data="entityDetail.properties" size="small" stripe max-height="200">
                <el-table-column label="属性" min-width="180">
                  <template #default="{ row }">
                    <span :title="row.property">{{ propDisplayName(row.property) }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="值" min-width="200">
                  <template #default="{ row }">
                    <span v-if="row.value_type === 'uri'" class="prop-uri" @click="navigateToUri(row.value)" :title="row.value">{{ shortUri(row.value) }}</span>
                    <span v-else>{{ row.value }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </el-collapse-item>
          </el-collapse>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import cytoscape, { type Core, type NodeSingular } from 'cytoscape'
import {
  graphExploreApi,
  type GraphEntity,
  type GraphEntityDetail,
  type GraphEdge,
  type FacetTree,
  type FacetNode,
  type IndicatorDetail,
  type BusinessSearchResult,
} from '@/api/graphExplore'
import { graphdbSyncApi, type GraphDBInstance } from '@/api/graphdbSync'
import { ElMessage } from 'element-plus'

// ─── State ──────────────────────────────────────────────────
const searchQuery = ref('')
const searching = ref(false)
const searchResults = ref<BusinessSearchResult[]>([])
const loadingFacets = ref(false)
const loadingEntities = ref(false)
const facetEntities = ref<GraphEntity[]>([])
const facetTree = ref<FacetNode[]>([])
const activeFacet = ref('')
const activeSubFacet = ref('')

const selectedUri = ref('')
const selectedLabel = ref('')
const selectedFacet = ref('')
const indicatorDetail = ref<IndicatorDetail | null>(null)
const entityDetail = ref<GraphEntityDetail | null>(null)
const activeTab = ref('what')
const hasGraphData = ref(false)

// Tab3 机构筛选
const selectedOrg = ref('')

const availableOrgs = computed(() => {
  if (!indicatorDetail.value) return []
  const orgs = new Set(indicatorDetail.value.tab3.map(v => v.org))
  return Array.from(orgs).sort()
})

const filteredTab3Data = computed(() => {
  if (!indicatorDetail.value) return []
  if (!selectedOrg.value) return indicatorDetail.value.tab3
  return indicatorDetail.value.tab3.filter(v => v.org === selectedOrg.value)
})

// Instance selector
const instances = ref<GraphDBInstance[]>([])
const selectedInstanceId = ref<string>('')

// Cytoscape
const cyMountRef = ref<HTMLElement>()
const graphContainerRef = ref<HTMLElement>()
let cy: Core | null = null

// ─── 术语映射 ────────────────────────────────────────────────
const facetIconMap: Record<string, string> = {
  indicator: '\u{1F4CA}', rule: '\u{1F4D0}', value: '\u{1F4C8}',
  datasource: '\u{1F5C2}', field: '\u{1F4DD}', account: '\u{1F3E6}', scenario: '\u{1F3AF}',
  org: '\u{1F3E2}', authscope: '\u{1F512}',
  other: '\u{25CB}',
}
function facetIcon(key: string): string { return facetIconMap[key] || '\u{25CB}' }

function facetTagType(facet: string): '' | 'success' | 'info' | 'warning' | 'danger' {
  const m: Record<string, '' | 'success' | 'info' | 'warning' | 'danger'> = {
    indicator: '', rule: 'warning', value: 'success', datasource: 'info',
    field: 'info', account: 'success', scenario: 'danger',
    org: 'warning', authscope: 'info',
  }
  return m[facet] || 'info'
}

const propNameMap: Record<string, string> = {
  appliedInScenario: '应用场景', mapsToField: '映射字段', mapToField: '映射字段',
  hasFormula: '计算公式', hasSQL: 'SQL查询', usesTable: '使用表',
  hasInput: '输入项', complexityTier: '复杂度等级', subject: '主题分类',
  label: '名称', comment: '说明', hasGreenThreshold: '绿色阈值',
  hasYellowThreshold: '黄色阈值', hasRedThreshold: '红色阈值',
  hasDescription: '描述', thresholdDirection: '阈值方向',
  isCompositeOf: '组合成分', hasComponent: '组成成分', dependsOn: '依赖',
  belongsToTable: '所属表', hasAccountCode: '科目编码',
  hasFieldType: '字段类型', hasFieldLength: '字段长度',
  hasDbColumn: '数据库列名', inBusinessDomain: '业务域',
  subClassOf: '属于...大类', type: '类型', computesIndicator: '计算指标',
  usesAccount: '涉及科目', ofIndicator: '对应指标', byRule: '依据规则',
  forOrg: '机构', forPeriod: '期间', numericValue: '数值',
  computedAt: '计算时间', ruleVersion: '规则版本',
  effectiveFrom: '生效日期', effectiveTo: '失效日期',
  inTable: '归属表', altLabel: '别名', notation: '编号',
  closeMatch: '对应国际标准',
}

function shortUri(uri: string): string {
  const hashIdx = uri.lastIndexOf('#')
  const slashIdx = uri.lastIndexOf('/')
  const idx = Math.max(hashIdx, slashIdx)
  return idx >= 0 ? uri.substring(idx + 1) : uri
}

function propDisplayName(propUri: string): string {
  const short = shortUri(propUri)
  return propNameMap[short] ? `${propNameMap[short]} (${short})` : short
}

function fiboShortName(uri: string): string {
  if (!uri) return ''
  // e.g. https://spec.edmcouncil.org/fibo/ontology/FND/Arrangements/Ratios/ -> FND:Ratio
  const match = uri.match(/fibo\/ontology\/([^/]+)\/[^/]+\/([^/]+)/)
  if (match) return `${match[1]}:${match[2]}`
  return shortUri(uri)
}

// ─── Helpers ────────────────────────────────────────────────
function instanceParams() {
  return selectedInstanceId.value ? { instance_id: selectedInstanceId.value } : {}
}

// ─── Instance Selector ───────────────────────────────────────
async function loadInstances() {
  try { instances.value = await graphdbSyncApi.listInstances() } catch { /* silent */ }
}
function handleInstanceChange() { loadFacetTree() }

// ─── Facet Tree ──────────────────────────────────────────────
async function loadFacetTree() {
  loadingFacets.value = true
  try {
    const res = await graphExploreApi.getFacetTree(selectedInstanceId.value || undefined)
    facetTree.value = res.facets
  } catch { /* GraphDB may be offline */ }
  finally { loadingFacets.value = false }
}

function toggleFacet(facetId: string) {
  if (activeFacet.value === facetId) {
    activeFacet.value = ''
    activeSubFacet.value = ''
    facetEntities.value = []
    return
  }
  activeFacet.value = facetId
  activeSubFacet.value = ''
  loadFacetEntities(facetId, '')
}

async function selectSubFacet(facetId: string, child: { id: string; topic?: string; prefix?: string; uri?: string }) {
  activeSubFacet.value = child.id
  loadFacetEntities(facetId, child.id, child)
}

async function loadFacetEntities(facetId: string, _subFacetId: string, subFacet?: { topic?: string; prefix?: string; uri?: string }) {
  loadingEntities.value = true
  try {
    const facet = facetTree.value.find(f => f.id === facetId)
    const facetIcon = facet?.icon || 'other'
    let typeFilter = ''
    const YQL = 'http://yql.example.com/ontology/credit-risk/'
    const facetTypeMap: Record<string, string> = {
      indicator: `${YQL}Indicator`, rule: `${YQL}CalculationRule`,
      value: `${YQL}IndicatorValue`, datasource: `${YQL}NCCTable`,
      field: `${YQL}NCCField`, account: `${YQL}AccountCode`,
      scenario: `${YQL}Scenario`,
      org: `${YQL}ApplicantOrg`, authscope: `${YQL}AuthorizationScope`,
    }
    if (facetTypeMap[facetIcon]) {
      if (facetIcon === 'indicator') {
        // Indicators are Classes, list via entities API with type=Indicator
        typeFilter = facetTypeMap[facetIcon]
      } else {
        typeFilter = facetTypeMap[facetIcon]
      }
    }
    const res = await graphExploreApi.listEntities({
      entity_type: typeFilter || undefined,
      limit: 200,
      ...instanceParams(),
    })
    // If subFacet selected, filter further
    if (subFacet?.topic) {
      // Filter by subject - need to get from label containing topic
      facetEntities.value = res.entities.filter(e => e.label?.includes(subFacet.topic!) || !subFacet.topic)
    } else if (subFacet?.uri) {
      // NCCField in specific table
      facetEntities.value = res.entities
    } else {
      facetEntities.value = res.entities
    }
  } catch { facetEntities.value = [] }
  finally { loadingEntities.value = false }
}

// ─── Search ──────────────────────────────────────────────────
async function handleBusinessSearch() {
  if (!searchQuery.value.trim()) { clearSearch(); return }
  searching.value = true
  try {
    const res = await graphExploreApi.searchBusiness({
      q: searchQuery.value.trim(),
      ...instanceParams(),
      limit: 30,
    })
    searchResults.value = res.results
  } catch { ElMessage.error('搜索失败') }
  finally { searching.value = false }
}

function clearSearch() {
  searchResults.value = []
  searchQuery.value = ''
}

// ─── Entity Selection ────────────────────────────────────────
async function handleEntityClick(uri: string, label: string, facet: string) {
  selectedUri.value = uri
  selectedLabel.value = label
  selectedFacet.value = facet
  indicatorDetail.value = null
  entityDetail.value = null
  selectedOrg.value = ''

  // If indicator (Class), load 4-tab detail
  if (facet === 'indicator') {
    try {
      indicatorDetail.value = await graphExploreApi.getIndicatorDetail(uri, selectedInstanceId.value || undefined)
      activeTab.value = 'what'
    } catch { /* fallback to generic detail */ }
  }

  // Also build graph and load generic detail
  await buildGraph(uri, label)
  if (!indicatorDetail.value) {
    try {
      entityDetail.value = await graphExploreApi.getEntity(uri, selectedInstanceId.value || undefined)
    } catch { entityDetail.value = null }
  }
}

async function navigateToUri(uri: string) {
  const match = facetEntities.value.find(e => e.uri === uri)
  const label = match?.label || shortUri(uri)
  // Determine facet from URI
  let facet = 'other'
  if (uri.includes('/credit-risk/')) facet = 'indicator'
  else if (uri.includes('/calculation-rule/')) facet = 'rule'
  else if (uri.includes('/indicator-value/')) facet = 'value'
  else if (uri.includes('/ncc-mapping/') && uri.includes('NCCField')) facet = 'field'
  else if (uri.includes('/ncc-mapping/')) facet = 'datasource'
  else if (uri.includes('/account-code/')) facet = 'account'
  else if (uri.includes('/scenario/')) facet = 'scenario'
  await handleEntityClick(uri, label, facet)
}

// ─── Computed for simplified detail panel ─────────────────────
const entityDetailLabel = computed(() => {
  if (!entityDetail.value) return ''
  const labelProp = entityDetail.value.properties.find(p => shortUri(p.property) === 'label')
  return labelProp?.value || shortUri(entityDetail.value.uri)
})

const businessProps = computed(() => {
  if (!entityDetail.value) return []
  const businessKeys = ['label', 'comment', 'subject', 'inTable', 'appliedInScenario', 'usesTable', 'subClassOf']
  return entityDetail.value.properties
    .filter(p => businessKeys.includes(shortUri(p.property)))
    .map(p => ({
      label: propNameMap[shortUri(p.property)] || shortUri(p.property),
      value: p.value,
      display: p.value_type === 'uri' ? shortUri(p.value) : p.value,
      isUri: p.value_type === 'uri',
    }))
})

// ─── Cytoscape Graph ────────────────────────────────────────
function initCytoscape() {
  if (!cyMountRef.value) return
  cy = cytoscape({
    container: cyMountRef.value,
    style: [
      {
        selector: 'node',
        style: {
          'label': 'data(label)',
          'text-valign': 'center',
          'text-halign': 'center',
          'font-size': '9px',
          'color': '#e2e8f0',
          'background-color': '#94a3b8',
          'border-width': 2,
          'border-color': '#64748b',
          'width': 45,
          'height': 45,
          'text-wrap': 'ellipsis',
          'text-max-width': '60px',
        },
      },
      {
        selector: 'node.root',
        style: {
          'background-color': '#f59e0b',
          'border-color': '#fbbf24',
          'width': 60,
          'height': 60,
          'font-weight': 'bold',
          'z-index': 10,
        },
      },
      {
        selector: 'node.type-indicator',
        style: { 'background-color': '#8b5cf6', 'border-color': '#a78bfa', 'width': 55, 'height': 55 },
      },
      {
        selector: 'node.type-datasource',
        style: { 'background-color': '#6366f1', 'border-color': '#818cf8' },
      },
      {
        selector: 'node.type-account',
        style: { 'background-color': '#10b981', 'border-color': '#34d399' },
      },
      {
        selector: 'node.type-scenario',
        style: { 'background-color': '#06b6d4', 'border-color': '#22d3ee' },
      },
      {
        selector: 'node.type-org',
        style: { 'background-color': '#f97316', 'border-color': '#fb923c' },
      },
      {
        selector: 'node.type-authscope',
        style: { 'background-color': '#eab308', 'border-color': '#facc15' },
      },
      {
        selector: 'edge',
        style: {
          'width': 2,
          'line-color': '#475569',
          'target-arrow-color': '#475569',
          'target-arrow-shape': 'triangle',
          'curve-style': 'bezier',
          'label': 'data(label)',
          'font-size': '8px',
          'color': '#94a3b8',
          'text-rotation': 'autorotate',
          'text-outline-color': '#1e293b',
          'text-outline-width': 2,
          'text-wrap': 'ellipsis',
          'text-max-width': '80px',
        },
      },
    ],
    elements: [],
    layout: { name: 'grid' },
  })

  cy.on('tap', 'node', async (evt) => {
    const node = evt.target as NodeSingular
    const uri = node.data('uri') as string
    if (uri) await expandGraph(uri)
  })
}

async function buildGraph(entityUri: string, entityLabel: string) {
  if (!cy) return
  cy.elements().remove()
  cy.resize()
  hasGraphData.value = false

  cy.add({
    data: { id: entityUri, label: entityLabel, uri: entityUri },
    classes: 'root',
  })

  try {
    const res = await graphExploreApi.getEntityEdges(entityUri, selectedInstanceId.value || undefined)
    addEdgesToGraph(entityUri, res.edges)
    hasGraphData.value = true
  } catch { /* offline */ }

  applyLayout()
}

async function expandGraph(entityUri: string) {
  if (!cy) return
  try {
    const res = await graphExploreApi.getEntityEdges(entityUri, selectedInstanceId.value || undefined)
    addEdgesToGraph(entityUri, res.edges)
    applyLayout()
  } catch { ElMessage.error('加载关系失败') }
}

function typeToClass(typeUri: string): string {
  if (!typeUri) return ''
  const short = shortUri(typeUri)
  if (['Indicator', 'RatioIndicator', 'AmountIndicator', 'CountIndicator'].includes(short)) return 'type-indicator'
  if (['NCCTable', 'NCCField'].includes(short)) return 'type-datasource'
  if (short === 'AccountCode') return 'type-account'
  if (short === 'Scenario') return 'type-scenario'
  return ''
}

// Edge label business mapping
function edgeBusinessLabel(propUri: string): string {
  const short = shortUri(propUri)
  return propNameMap[short] || short
}

function addEdgesToGraph(centerUri: string, edges: GraphEdge[]) {
  if (!cy) return
  for (const edge of edges) {
    const targetUri = edge.target
    const direction = edge.direction
    let sourceId: string, targetId: string
    if (direction === 'outgoing') { sourceId = centerUri; targetId = targetUri }
    else { sourceId = targetUri; targetId = centerUri }

    if (cy.getElementById(targetUri).length === 0) {
      const typeClass = typeToClass(edge.target_type)
      cy.add({
        data: {
          id: targetUri,
          label: edge.target_label || shortUri(targetUri),
          uri: targetUri,
        },
        classes: typeClass,
      })
    }

    const edgeId = `${sourceId}-${shortUri(edge.property)}-${targetId}`
    if (cy.getElementById(edgeId).length === 0) {
      cy.add({
        data: {
          id: edgeId,
          source: sourceId,
          target: targetId,
          label: edgeBusinessLabel(edge.property),
        },
      })
    }
  }
}

function applyLayout() {
  if (!cy) return
  cy.layout({
    name: 'cose',
    animate: true,
    animationDuration: 500,
    nodeRepulsion: () => 8000,
    idealEdgeLength: () => 100,
    gravity: 0.3,
    padding: 30,
    fit: true,
  }).run()
}

function fitGraph() { cy?.fit(undefined, 30) }
function resetGraph() {
  if (selectedUri.value) buildGraph(selectedUri.value, selectedLabel.value)
}

// ─── Lifecycle ──────────────────────────────────────────────
onMounted(async () => {
  await nextTick()
  initCytoscape()
  await Promise.all([loadInstances(), loadFacetTree()])
})

onBeforeUnmount(() => {
  cy?.destroy()
  cy = null
})
</script>

<style scoped>
.graph-explorer {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
}

.page-header-modern {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
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
  font-size: 1.2rem;
  font-weight: 600;
  margin: 0;
  color: var(--el-text-color-primary);
}

.subtitle {
  font-size: 0.8rem;
  color: var(--el-text-color-secondary);
  margin: 2px 0 0;
}

.explorer-body {
  display: flex;
  gap: 16px;
  flex: 1;
  min-height: 0;
}

/* ── Left Panel ── */
.left-panel {
  width: 280px;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--el-bg-color-overlay, #1e293b);
  border-radius: 12px;
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter, #334155);
  overflow: hidden;
}

.search-bar {
  display: flex;
  gap: 8px;
}

.search-bar .el-input {
  flex: 1;
}

.search-results, .facet-tree-wrapper {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.list-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

/* Facet tree */
.facet-group {
  margin-bottom: 2px;
}

.facet-root {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 6px;
  cursor: pointer;
  border-radius: 6px;
  transition: background 0.2s;
  font-size: 0.85rem;
  font-weight: 500;
}

.facet-root:hover { background: var(--el-fill-color-light, #334155); }
.facet-root.active { background: var(--el-color-primary-light-9, #1e3a5f); }

.facet-expand-icon { font-size: 12px; color: var(--el-text-color-secondary); }
.facet-icon-label { font-size: 14px; }
.facet-label { color: var(--el-text-color-primary); }

.facet-children {
  padding-left: 24px;
}

.facet-child {
  padding: 4px 8px;
  cursor: pointer;
  border-radius: 4px;
  font-size: 0.8rem;
  color: var(--el-text-color-regular);
  transition: background 0.2s;
}

.facet-child:hover { background: var(--el-fill-color-light, #334155); }
.facet-child.active { background: var(--el-color-primary-light-8, #1e3a5f); color: var(--el-color-primary); }

.facet-entities {
  padding-left: 16px;
  max-height: 300px;
  overflow-y: auto;
}

.entity-item {
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  margin-bottom: 2px;
  font-size: 0.8rem;
}

.entity-item:hover { background: var(--el-fill-color-light, #334155); }
.entity-item.active { background: var(--el-color-primary-light-8, #1e3a5f); }

.entity-label {
  color: var(--el-text-color-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.facet-tag { margin-right: 4px; }

/* ── Right Panel ── */
.right-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.graph-container {
  flex: 1;
  min-height: 300px;
  background: #0f172a;
  border-radius: 12px;
  border: 1px solid var(--el-border-color-lighter, #334155);
  position: relative;
  display: flex;
  flex-direction: column;
}

.graph-toolbar {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 12px;
}

.graph-info {
  font-size: 0.8rem;
  color: var(--el-text-color-secondary);
  background: rgba(15, 23, 42, 0.8);
  padding: 4px 10px;
  border-radius: 6px;
  border: 1px solid var(--el-border-color);
}

.cytoscape-mount { flex: 1; min-height: 0; }

.graph-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  padding: 6px 12px;
  background: rgba(15, 23, 42, 0.8);
  border-top: 1px solid var(--el-border-color);
  font-size: 0.7rem;
  color: #94a3b8;
}

.legend-item { display: inline-flex; align-items: center; gap: 4px; }
.legend-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; }

/* ── Detail Panel ── */
.detail-panel {
  background: var(--el-bg-color-overlay, #1e293b);
  border-radius: 12px;
  border: 1px solid var(--el-border-color-lighter, #334155);
  padding: 12px 16px;
  max-height: 340px;
  overflow-y: auto;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.detail-header h3 {
  font-size: 1rem;
  font-weight: 600;
  margin: 0;
  color: var(--el-text-color-primary);
}

.detail-tabs :deep(.el-tabs__item) {
  font-size: 0.85rem;
}

.tab-content { padding: 4px 0; }

.info-row {
  display: flex;
  gap: 12px;
  margin-bottom: 10px;
  align-items: flex-start;
}

.info-label {
  min-width: 80px;
  color: var(--el-text-color-secondary);
  font-size: 0.8rem;
  flex-shrink: 0;
  padding-top: 2px;
}

.info-value {
  color: var(--el-text-color-primary);
  font-size: 0.85rem;
  flex: 1;
}

.info-value.highlight {
  font-size: 0.95rem;
  font-weight: 500;
  color: var(--el-color-primary-light-3, #93c5fd);
}

.info-value.formula {
  font-size: 1.05rem;
  font-weight: 600;
  color: #fbbf24;
  font-family: 'Courier New', monospace;
}

.mr-4 { margin-right: 6px; margin-bottom: 4px; }
.clickable { cursor: pointer; }
.clickable:hover { opacity: 0.8; }

.field-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.sql-block {
  background: #0f172a;
  padding: 10px;
  border-radius: 6px;
  font-size: 0.75rem;
  color: #94a3b8;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 200px;
  overflow-y: auto;
}

.tech-collapse { margin-top: 8px; }
.tech-collapse :deep(.el-collapse-item__header) {
  font-size: 0.8rem;
  color: var(--el-text-color-secondary);
}

.related-section { margin-bottom: 12px; }
.related-section h4 { font-size: 0.8rem; color: var(--el-text-color-secondary); margin: 0 0 6px; }
.related-list { display: flex; flex-wrap: wrap; gap: 4px; }

.data-value { font-weight: 600; color: var(--el-color-primary); }

.data-filter {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.data-count {
  font-size: 0.75rem;
  color: var(--el-text-color-secondary);
}

.prop-uri {
  color: var(--el-color-primary);
  cursor: pointer;
  text-decoration: underline;
}
</style>
