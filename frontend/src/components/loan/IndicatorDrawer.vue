<template>
  <el-drawer
    v-model="visible"
    title=""
    :size="480"
    direction="rtl"
    class="indicator-drawer"
  >
    <template #header>
      <div class="drawer-header">
        <div class="drawer-title">
          <el-icon><Connection /></el-icon>
          指标详情
        </div>
        <AlertBadge v-if="indicator" :level="indicator.alert_level || 'normal'" />
      </div>
    </template>

    <div v-if="indicator" class="drawer-content">
      <!-- Indicator name & value -->
      <div class="detail-hero">
        <h3 class="detail-name">{{ indicator.indicator_name }}</h3>
        <div class="detail-value-row">
          <span class="detail-value" :class="indicator.alert_level">
            {{ formatValue(indicator.value, indicator.unit) }}
          </span>
          <span class="detail-prev" v-if="indicator.value_prev != null">
            上期：{{ formatValue(indicator.value_prev, indicator.unit) }}
          </span>
        </div>
        <div class="change-row" v-if="indicator.change_pct != null">
          <el-icon :class="getChangeClass(indicator)">
            <component :is="indicator.change_pct >= 0 ? 'ArrowUp' : 'ArrowDown'" />
          </el-icon>
          <span :class="getChangeClass(indicator)">
            环比 {{ indicator.change_pct >= 0 ? '+' : '' }}{{ indicator.change_pct.toFixed(2) }}%
          </span>
        </div>
      </div>

      <!-- Threshold gauge -->
      <div class="threshold-section">
        <div class="section-label">阈值对比</div>
        <div class="threshold-grid">
          <div class="threshold-item">
            <span class="thr-label">关注阈值</span>
            <span class="thr-value warning">
              {{ indicator.threshold_warning != null ? formatValue(indicator.threshold_warning, indicator.unit) : '未配置' }}
            </span>
          </div>
          <div class="threshold-item">
            <span class="thr-label">预警阈值</span>
            <span class="thr-value alert">
              {{ indicator.threshold_alert != null ? formatValue(indicator.threshold_alert, indicator.unit) : '未配置' }}
            </span>
          </div>
          <div class="threshold-item">
            <span class="thr-label">阈值方向</span>
            <span class="thr-value">
              {{ indicator.threshold_direction === 'above' ? '↑ 高于为好' : '↓ 低于为好' }}
            </span>
          </div>
          <div class="threshold-item" v-if="indicator.dimension_name">
            <span class="thr-label">所属维度</span>
            <span class="thr-value">{{ indicator.dimension_name }}</span>
          </div>
        </div>
      </div>

      <!-- FIBO path -->
      <div class="fibo-section" v-if="indicator.fibo_path">
        <div class="section-label">
          <el-icon><Connection /></el-icon>
          FIBO 本体路径
        </div>
        <div class="fibo-path-box">
          <code>{{ indicator.fibo_path }}</code>
        </div>
      </div>

      <!-- Formula -->
      <div class="formula-section" v-if="indicator.formula">
        <div class="section-label">
          <el-icon><Operation /></el-icon>
          计算公式
        </div>
        <div class="formula-box">
          <pre>{{ indicator.formula }}</pre>
        </div>
      </div>

      <!-- Data source -->
      <div class="datasource-section" v-if="indicator.data_source">
        <div class="section-label">
          <el-icon><DataLine /></el-icon>
          数据来源
        </div>
        <div class="datasource-text">{{ indicator.data_source }}</div>
      </div>

      <!-- Code -->
      <div class="code-section" v-if="indicator.indicator_code">
        <div class="section-label">指标编码</div>
        <code class="indicator-code">{{ indicator.indicator_code }}</code>
      </div>
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { IndicatorValue } from '@/api/loanAnalysis'
import AlertBadge from './AlertBadge.vue'

const props = defineProps<{
  modelValue: boolean
  indicator?: IndicatorValue | null
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

function formatValue(v?: number | null, unit?: string) {
  if (v == null) return '—'
  const f = Math.abs(v) >= 10000
    ? (v / 10000).toFixed(2) + '万'
    : v.toFixed(4)
  return unit ? `${f} ${unit}` : f
}

function getChangeClass(row: IndicatorValue) {
  if (row.change_pct == null) return ''
  const positive = row.change_pct >= 0
  const direction = row.threshold_direction ?? 'above'
  return (direction === 'above' ? positive : !positive) ? 'change-good' : 'change-bad'
}
</script>

<style scoped>
:deep(.indicator-drawer .el-drawer__header) {
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--card-border);
  margin-bottom: 0;
}

:deep(.indicator-drawer .el-drawer__body) {
  padding: 0;
  overflow-y: auto;
}

:deep(.indicator-drawer .el-drawer__wrapper) {
  background: rgba(0,0,0,0.5);
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.drawer-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.drawer-content {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Hero section */
.detail-hero {
  background: rgba(102,126,234,0.06);
  border: 1px solid rgba(102,126,234,0.2);
  border-radius: 14px;
  padding: 20px;
}

.detail-name {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 12px;
}

.detail-value-row {
  display: flex;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 8px;
}

.detail-value {
  font-size: 2rem;
  font-weight: 700;
  font-family: 'Fira Code', monospace;
}

.detail-value.normal  { color: var(--table-cell-color); }
.detail-value.warning { color: #f59e0b; }
.detail-value.alert   { color: #ef4444; }

.detail-prev {
  font-size: 0.85rem;
  color: var(--threshold-color);
}

.change-row {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 0.85rem;
  font-weight: 600;
}

.change-good { color: #10b981; }
.change-bad  { color: #ef4444; }

/* Section */
.section-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--card-title-color);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Threshold grid */
.threshold-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.threshold-item {
  background: var(--card-bg-subtle);
  border: 1px solid var(--card-border);
  border-radius: 10px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.thr-label {
  font-size: 0.75rem;
  color: var(--threshold-color);
}

.thr-value {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--card-title-color);
  font-family: 'Fira Code', monospace;
}

.thr-value.warning { color: #f59e0b; }
.thr-value.alert   { color: #ef4444; }

/* FIBO path */
.fibo-path-box {
  background: rgba(102,126,234,0.08);
  border: 1px solid rgba(102,126,234,0.2);
  border-radius: 10px;
  padding: 12px 16px;
  overflow-x: auto;
}

.fibo-path-box code {
  font-family: 'Fira Code', monospace;
  font-size: 0.8rem;
  color: #818cf8;
  white-space: nowrap;
}

/* Formula */
.formula-box {
  background: var(--bg-tertiary);
  border: 1px solid var(--card-border);
  border-radius: 10px;
  padding: 14px 16px;
}

.formula-box pre {
  margin: 0;
  font-family: 'Fira Code', monospace;
  font-size: 0.82rem;
  color: var(--suggestion-text-color);
  white-space: pre-wrap;
  line-height: 1.6;
}

/* Data source */
.datasource-text {
  color: var(--suggestion-text-color);
  font-size: 0.875rem;
  line-height: 1.6;
}

/* Code */
.indicator-code {
  font-family: 'Fira Code', monospace;
  font-size: 0.8rem;
  color: #667eea;
  background: rgba(102,126,234,0.1);
  padding: 4px 10px;
  border-radius: 6px;
}
</style>
