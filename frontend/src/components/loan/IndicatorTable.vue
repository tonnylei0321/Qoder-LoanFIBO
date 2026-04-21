<template>
  <div class="indicator-table-wrap">
    <!-- Dimension filter tabs -->
    <div class="dim-tabs" v-if="dimensions.length">
      <button
        class="dim-tab"
        :class="{ active: activeDim === '' }"
        @click="activeDim = ''"
      >全部 ({{ rows.length }})</button>
      <button
        v-for="dim in dimensions"
        :key="dim"
        class="dim-tab"
        :class="{ active: activeDim === dim }"
        @click="activeDim = dim"
      >
        {{ dim }}
        <span class="dim-count">{{ countByDim[dim] ?? 0 }}</span>
        <span v-if="alertByDim[dim]" class="dim-alert-dot"></span>
      </button>
    </div>

    <!-- Table -->
    <el-table
      :data="filteredRows"
      :row-class-name="rowClass"
      class="indicator-table"
      empty-text="暂无指标数据"
      @row-click="openDrawer"
    >
      <el-table-column label="指标名称" min-width="160">
        <template #default="{ row }">
          <div class="indicator-name-cell">
            <span class="ind-name">{{ row.indicator_name }}</span>
            <el-icon class="ind-info-icon"><InfoFilled /></el-icon>
          </div>
        </template>
      </el-table-column>

      <el-table-column label="当前值" width="130" align="right">
        <template #default="{ row }">
          <span class="value-display" :class="row.alert_level">
            {{ formatValue(row.value, row.unit) }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="关注阈值" width="110" align="right">
        <template #default="{ row }">
          <span class="threshold">
            {{ row.threshold_warning != null ? formatValue(row.threshold_warning, row.unit) : '-' }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="预警阈值" width="110" align="right">
        <template #default="{ row }">
          <span class="threshold">
            {{ row.threshold_alert != null ? formatValue(row.threshold_alert, row.unit) : '-' }}
          </span>
        </template>
      </el-table-column>

      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <AlertBadge :level="row.alert_level || 'normal'" />
        </template>
      </el-table-column>

      <el-table-column label="环比" width="100" align="right">
        <template #default="{ row }">
          <span v-if="row.change_pct != null" class="change-pct" :class="getChangeClass(row)">
            <el-icon>
              <component :is="row.change_pct > 0 ? 'ArrowUp' : 'ArrowDown'" />
            </el-icon>
            {{ Math.abs(row.change_pct).toFixed(2) }}%
          </span>
          <span v-else class="text-muted">—</span>
        </template>
      </el-table-column>

      <el-table-column label="FIBO" width="60" align="center">
        <template #default="{ row }">
          <el-tooltip :content="row.fibo_path || '未配置'" placement="left">
            <el-icon class="fibo-icon" :class="{ has: !!row.fibo_path }"><Connection /></el-icon>
          </el-tooltip>
        </template>
      </el-table-column>
    </el-table>
  </div>

  <!-- Detail Drawer (rendered outside table for proper z-index) -->
  <IndicatorDrawer v-model="drawerVisible" :indicator="drawerItem" />
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { IndicatorValue } from '@/api/loanAnalysis'
import AlertBadge from './AlertBadge.vue'
import IndicatorDrawer from './IndicatorDrawer.vue'

const props = defineProps<{
  rows: IndicatorValue[]
}>()

const activeDim = ref('')
const drawerVisible = ref(false)
const drawerItem = ref<IndicatorValue | null>(null)

const dimensions = computed(() => {
  const seen = new Set<string>()
  const list: string[] = []
  for (const r of props.rows) {
    const d = r.dimension_name
    if (d && !seen.has(d)) {
      seen.add(d)
      list.push(d)
    }
  }
  return list
})

const countByDim = computed(() => {
  const m: Record<string, number> = {}
  for (const r of props.rows) {
    const d = r.dimension_name ?? '其他'
    m[d] = (m[d] ?? 0) + 1
  }
  return m
})

const alertByDim = computed(() => {
  const m: Record<string, boolean> = {}
  for (const r of props.rows) {
    if (r.alert_level !== 'normal') {
      const d = r.dimension_name ?? '其他'
      m[d] = true
    }
  }
  return m
})

const filteredRows = computed(() => {
  if (!activeDim.value) return props.rows
  return props.rows.filter(r => r.dimension_name === activeDim.value)
})

function rowClass({ row }: { row: IndicatorValue }) {
  return row.alert_level === 'alert' ? 'row-alert' : row.alert_level === 'warning' ? 'row-warning' : ''
}

function formatValue(v?: number | null, unit?: string) {
  if (v == null) return '—'
  const formatted = Math.abs(v) >= 10000
    ? (v / 10000).toFixed(2) + '万'
    : v.toFixed(2)
  return unit ? `${formatted} ${unit}` : formatted
}

function getChangeClass(row: IndicatorValue) {
  if (row.change_pct == null) return ''
  const positive = row.change_pct > 0
  const direction = row.threshold_direction ?? 'above'
  const good = direction === 'above' ? positive : !positive
  return good ? 'change-good' : 'change-bad'
}

function openDrawer(row: IndicatorValue) {
  drawerItem.value = row
  drawerVisible.value = true
}
</script>

<style scoped>
.indicator-table-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Dimension tabs */
.dim-tabs {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--card-border);
}

.dim-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 0.8rem;
  font-weight: 500;
  border: 1px solid transparent;
  background: transparent;
  color: var(--dim-tab-color);
  cursor: pointer;
  transition: all 0.2s;
  position: relative;
}

.dim-tab:hover {
  background: var(--dim-tab-hover-bg);
  color: var(--dim-tab-hover-color);
}

.dim-tab.active {
  background: rgba(102,126,234,0.15);
  border-color: rgba(102,126,234,0.4);
  color: #818cf8;
}

.dim-count {
  background: rgba(148,163,184,0.15);
  border-radius: 10px;
  padding: 1px 6px;
  font-size: 0.7rem;
}

.dim-alert-dot {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 6px;
  height: 6px;
  background: #ef4444;
  border-radius: 50%;
  box-shadow: 0 0 4px #ef4444;
}

/* Table */
.indicator-table :deep(.el-table__inner-wrapper) {
  background: transparent !important;
}

.indicator-table :deep(th.el-table__cell) {
  background: var(--table-header-bg) !important;
  color: var(--table-header-color) !important;
  font-size: 0.78rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--table-border) !important;
}

.indicator-table :deep(td.el-table__cell) {
  background: transparent !important;
  border-bottom: 1px solid var(--table-border) !important;
  color: var(--table-cell-color);
}

.indicator-table :deep(tr:hover td.el-table__cell) {
  background: var(--table-row-hover) !important;
  cursor: pointer;
}

:deep(.row-warning td.el-table__cell) {
  background: rgba(245,158,11,0.04) !important;
}

:deep(.row-alert td.el-table__cell) {
  background: rgba(239,68,68,0.05) !important;
}

/* Cells */
.indicator-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ind-name {
  font-weight: 500;
  color: var(--ind-name-color);
}

.ind-info-icon {
  color: var(--ind-icon-color);
  transition: color 0.2s;
}

.indicator-table :deep(tr:hover) .ind-info-icon {
  color: #667eea;
}

.value-display {
  font-weight: 600;
  font-family: 'Fira Code', monospace;
  font-size: 0.9rem;
}

.value-display.normal  { color: var(--table-cell-color); }
.value-display.warning { color: #f59e0b; }
.value-display.alert   { color: #ef4444; }

.threshold {
  color: var(--threshold-color);
  font-family: 'Fira Code', monospace;
  font-size: 0.85rem;
}

.change-pct {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 0.8rem;
  font-weight: 600;
}

.change-good { color: #10b981; }
.change-bad  { color: #ef4444; }

.text-muted { color: var(--text-muted-cell); }

.fibo-icon {
  color: var(--fibo-icon-color);
  font-size: 1rem;
  transition: color 0.2s;
}

.fibo-icon.has { color: #667eea; }
</style>
