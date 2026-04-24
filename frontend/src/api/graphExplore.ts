/** Graph Explore API */
import request from './request'

export interface GraphEntity {
  uri: string
  type: string
  label: string
}

export interface GraphEntityDetail {
  uri: string
  properties: Array<{
    property: string
    value: string
    value_type: string
  }>
  provenance?: Record<string, string>
}

export interface GraphEdge {
  direction: string
  property: string
  target: string
  target_label: string
  target_type: string
}

// ── 业务化 API 类型 ──────────────────────────────────────────

export interface FacetChild {
  id: string
  label: string
  uri?: string
  topic?: string
  prefix?: string
  count: number
  isLeaf: boolean
}

export interface FacetNode {
  id: string
  label: string
  icon: string
  children: FacetChild[]
}

export interface FacetTree {
  facets: FacetNode[]
}

export interface IndicatorTab1 {
  label: string
  comment: string
  subjects: string[]
  closeMatches: string[]
  scenarios: Array<{ uri: string; label: string }>
}

export interface IndicatorTab2 {
  rule: string
  ruleLabel: string
  formula: string
  sql: string
  tables: Array<{ uri: string; label: string }>
  fields: Array<{ uri: string; label: string }>
  accounts: Array<{ uri: string; label: string }>
}

export interface IndicatorTab3Item {
  uri: string
  org: string
  period: string
  value: string
  computedAt: string
}

export interface IndicatorTab4 {
  sameTopic: Array<{ uri: string; label: string }>
  sharedSource: Array<{ uri: string; label: string }>
}

export interface IndicatorDetail {
  uri: string
  tab1: IndicatorTab1
  tab2: IndicatorTab2
  tab3: IndicatorTab3Item[]
  tab4: IndicatorTab4
}

export interface BusinessSearchResult {
  uri: string
  type: string
  label: string
  facet: string
}

export interface ScenarioIndicator {
  indicatorUri: string
  indicatorLabel: string
  ruleUri: string
  ruleLabel: string
  formula: string
  sql: string
  complexityTier: string
  notation: string
  tables: Array<{ uri: string; label: string }>
}

export const graphExploreApi = {
  listEntities: (params?: { entity_type?: string; instance_id?: string; limit?: number; offset?: number }): Promise<{ entities: GraphEntity[]; total: number }> => {
    return request.get('/explore/entities', { params })
  },

  getEntity: (uri: string, instanceId?: string): Promise<GraphEntityDetail> => {
    return request.get('/explore/entity-detail', { params: { uri, ...(instanceId ? { instance_id: instanceId } : {}) } })
  },

  getEntityEdges: (uri: string, instanceId?: string): Promise<{ edges: GraphEdge[]; total: number }> => {
    return request.get('/explore/entity-edges', { params: { uri, ...(instanceId ? { instance_id: instanceId } : {}) } })
  },

  searchEntities: (params: { q: string; instance_id?: string; limit?: number }): Promise<{ results: GraphEntity[]; total: number }> => {
    return request.get('/explore/search', { params })
  },

  // ── 业务化 API ──────────────────────────────────────────────

  getFacetTree: (instanceId?: string): Promise<FacetTree> => {
    return request.get('/explore/facet-tree', { params: instanceId ? { instance_id: instanceId } : {} })
  },

  getIndicatorDetail: (uri: string, instanceId?: string): Promise<IndicatorDetail> => {
    return request.get('/explore/indicator-detail', { params: { uri, ...(instanceId ? { instance_id: instanceId } : {}) } })
  },

  getScenarioIndicators: (scenario: string, instanceId?: string): Promise<{ indicators: ScenarioIndicator[]; total: number }> => {
    return request.get('/explore/scenario-indicators', { params: { scenario, ...(instanceId ? { instance_id: instanceId } : {}) } })
  },

  searchBusiness: (params: { q: string; facet?: string; instance_id?: string; limit?: number }): Promise<{ results: BusinessSearchResult[]; total: number }> => {
    return request.get('/explore/search-business', { params })
  },
}
