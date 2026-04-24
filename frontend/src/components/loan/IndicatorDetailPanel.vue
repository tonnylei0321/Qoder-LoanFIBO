<template>
  <div class="detail-panel" v-if="indicatorDetail">
    <div class="detail-header">
      <h3>{{ indicatorDetail.tab1.label }}</h3>
      <el-button text size="small" @click="$emit('close')">
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
              <el-tag v-for="t in indicatorDetail.tab2.tables" :key="t.uri" size="small" class="mr-4">{{ t.label }}</el-tag>
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
                @click="$emit('navigate', r.uri)"
              >{{ r.label }}</el-tag>
            </div>
          </div>
          <div v-if="indicatorDetail.tab4.sharedSource.length" class="related-section">
            <h4>共享数据源</h4>
            <div class="related-list">
              <el-tag
                v-for="r in indicatorDetail.tab4.sharedSource"
                :key="r.uri" size="small" type="info" class="mr-4 clickable"
                @click="$emit('navigate', r.uri)"
              >{{ r.label }}</el-tag>
            </div>
          </div>
          <el-empty v-if="!indicatorDetail.tab4.sameTopic.length && !indicatorDetail.tab4.sharedSource.length" description="暂无关联指标" :image-size="40" />
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>

  <!-- Empty state -->
  <div v-else class="detail-panel detail-empty">
    <el-empty description="点击左侧指标行查看详情" :image-size="60" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { IndicatorDetail } from '@/api/graphExplore'

const props = defineProps<{
  indicatorDetail: IndicatorDetail | null
}>()

defineEmits<{
  close: []
  navigate: [uri: string]
}>()

const activeTab = ref('what')
const selectedOrg = ref('')

const availableOrgs = computed(() => {
  if (!props.indicatorDetail) return []
  const orgs = new Set(props.indicatorDetail.tab3.map(v => v.org))
  return Array.from(orgs).sort()
})

const filteredTab3Data = computed(() => {
  if (!props.indicatorDetail) return []
  if (!selectedOrg.value) return props.indicatorDetail.tab3
  return props.indicatorDetail.tab3.filter(v => v.org === selectedOrg.value)
})

function fiboShortName(uri: string): string {
  if (!uri) return ''
  const match = uri.match(/fibo\/ontology\/([^/]+)\/[^/]+\/([^/]+)/)
  if (match) return `${match[1]}:${match[2]}`
  const hashIdx = uri.lastIndexOf('#')
  const slashIdx = uri.lastIndexOf('/')
  const idx = Math.max(hashIdx, slashIdx)
  return idx >= 0 ? uri.substring(idx + 1) : uri
}
</script>

<style scoped>
.detail-panel {
  background: var(--el-bg-color-overlay, #1e293b);
  border-radius: 12px;
  border: 1px solid var(--el-border-color-lighter, #334155);
  padding: 12px 16px;
  overflow-y: auto;
}

.detail-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 200px;
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
</style>
