<template>
  <div class="loan-analysis-page">
    <!-- Page header -->
    <div class="page-header">
      <div class="page-title-wrap">
        <div class="page-icon pre-loan">
          <el-icon><DocumentChecked /></el-icon>
        </div>
        <div>
          <h1 class="page-title">贷前尽调</h1>
          <p class="page-desc">基于 FIBO 本体的企业财务健康度评估 · {{ indicatorRows.length }} 项指标</p>
        </div>
      </div>
      <div class="page-actions">
        <el-button
          v-if="selectedCompanyId && !loading"
          type="primary"
          :loading="calculating"
          @click="handleCalculate"
          class="calc-btn"
        >
          <el-icon><Refresh /></el-icon>
          重新计算
        </el-button>
      </div>
    </div>

    <!-- Company selector -->
    <div class="section-card">
      <CompanyHeader
        v-model="selectedCompanyId"
        :calc-date="latestDate"
        @company-change="onCompanyChange"
      />
    </div>

    <!-- Score Dashboard (only when company selected) -->
    <template v-if="selectedCompanyId">
      <div v-if="loading" class="loading-area">
        <el-skeleton :rows="6" animated />
      </div>

      <template v-else>
        <!-- Score + Radar -->
        <div class="score-section">
          <!-- Radar chart -->
          <div class="section-card radar-card">
            <div class="card-header">
              <span class="card-title">维度评分雷达图</span>
              <span class="card-date">{{ latestDate }}</span>
            </div>
            <RadarChart :items="radarItems" :height="300" />
          </div>

          <!-- Score summary -->
          <div class="score-summary-wrap">
            <!-- Total score -->
            <div class="section-card score-card">
              <div class="score-display">
                <div class="score-ring" :class="riskLevelClass">
                  <div class="score-number">{{ totalScore }}</div>
                  <div class="score-label">综合评分</div>
                </div>
                <div class="risk-info">
                  <div class="risk-level-badge" :class="riskLevelClass">
                    {{ scoreData?.score_record?.risk_level || '—' }}
                  </div>
                  <div class="risk-label">风险等级</div>
                </div>
              </div>
            </div>

            <!-- Alert summary -->
            <div class="section-card alert-summary-card">
              <div class="card-header">
                <span class="card-title">预警概览</span>
              </div>
              <div class="alert-stats">
                <div class="alert-stat-item normal">
                  <span class="stat-number">{{ alertSummary.normal }}</span>
                  <span class="stat-label">正常</span>
                </div>
                <div class="alert-stat-item warning">
                  <span class="stat-number">{{ alertSummary.warning }}</span>
                  <span class="stat-label">关注</span>
                </div>
                <div class="alert-stat-item alert">
                  <span class="stat-number">{{ alertSummary.alert }}</span>
                  <span class="stat-label">预警</span>
                </div>
              </div>
            </div>

            <!-- Suggestion -->
            <div class="section-card suggestion-card" v-if="suggestion">
              <div class="card-header">
                <span class="card-title">授信建议</span>
                <el-icon class="suggestion-icon"><ChatLineRound /></el-icon>
              </div>
              <p class="suggestion-text">{{ suggestion }}</p>
            </div>
          </div>
        </div>

        <!-- Indicator table -->
        <div class="section-card">
          <div class="card-header">
            <span class="card-title">指标明细</span>
            <span class="card-subtitle">点击行查看 FIBO 详情</span>
          </div>
          <IndicatorTable :rows="indicatorRows" />
        </div>
      </template>
    </template>

    <!-- Empty state -->
    <div v-else class="empty-state">
      <el-icon class="empty-icon"><OfficeBuilding /></el-icon>
      <p>请选择企业以查看贷前尽调分析</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { loanAnalysisApi, type Company, type CompanyScoreResponse, type IndicatorValue } from '@/api/loanAnalysis'
import CompanyHeader from '@/components/loan/CompanyHeader.vue'
import RadarChart from '@/components/charts/RadarChart.vue'
import IndicatorTable from '@/components/loan/IndicatorTable.vue'

const SCENARIO = 'pre_loan'

const selectedCompanyId = ref('')
const loading = ref(false)
const calculating = ref(false)
const scoreData = ref<CompanyScoreResponse | null>(null)
const indicatorRows = ref<IndicatorValue[]>([])
const latestDate = ref('')

async function loadData(companyId: string) {
  loading.value = true
  try {
    const [score, indicators] = await Promise.all([
      loanAnalysisApi.getCompanyScore(companyId, SCENARIO),
      loanAnalysisApi.getCompanyIndicators(companyId, SCENARIO),
    ])
    scoreData.value = score
    indicatorRows.value = indicators
    latestDate.value = score.calc_date || ''
  } catch (e: any) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

function onCompanyChange(_company: Company) {
  if (selectedCompanyId.value) {
    loadData(selectedCompanyId.value)
  }
}

async function handleCalculate() {
  if (!selectedCompanyId.value || !latestDate.value) return
  calculating.value = true
  try {
    await loanAnalysisApi.calculate(selectedCompanyId.value, SCENARIO, latestDate.value)
    ElMessage.success('计算完成')
    await loadData(selectedCompanyId.value)
  } catch {
    ElMessage.error('计算失败')
  } finally {
    calculating.value = false
  }
}

// Computed
const alertSummary = computed(() => scoreData.value?.alert_summary ?? { normal: 0, warning: 0, alert: 0 })

const totalScore = computed(() => {
  const s = scoreData.value?.score_record?.total_score
  return s != null ? s.toFixed(1) : '—'
})

const suggestion = computed(() => scoreData.value?.score_record?.suggestion ?? '')

const riskLevelClass = computed(() => {
  const level = scoreData.value?.score_record?.risk_level ?? ''
  if (['AAA', 'AA', 'A'].includes(level)) return 'level-good'
  if (['BBB', 'BB'].includes(level)) return 'level-warn'
  return level ? 'level-alert' : ''
})

const radarItems = computed(() => {
  const ds = scoreData.value?.score_record?.dimension_scores ?? {}
  return Object.values(ds).map((d: any) => ({
    name: d.name,
    value: d.score ?? 0,
    max: 100,
  }))
})
</script>

<style scoped>
.loan-analysis-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
  max-width: 1400px;
}

/* Page header */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-title-wrap {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.4rem;
  flex-shrink: 0;
}

.page-icon.pre-loan {
  background: linear-gradient(135deg, rgba(102,126,234,0.2), rgba(118,75,162,0.2));
  color: #818cf8;
  border: 1px solid rgba(102,126,234,0.3);
}

.page-title {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--page-title-color);
  margin: 0 0 4px;
}

.page-desc {
  font-size: 0.85rem;
  color: var(--page-desc-color);
  margin: 0;
}

.calc-btn :deep(.el-icon) {
  margin-right: 4px;
}

/* Section card */
.section-card {
  background: var(--card-bg-subtle);
  border: 1px solid var(--card-border);
  border-radius: 16px;
  padding: 20px 24px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.card-title {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--card-title-color);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.card-subtitle {
  font-size: 0.78rem;
  color: var(--card-date-color);
}

.card-date {
  font-size: 0.78rem;
  color: var(--card-date-color);
  font-family: 'Fira Code', monospace;
}

/* Score section */
.score-section {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: 20px;
  align-items: start;
}

.radar-card {
  /* takes remaining space */
}

.score-summary-wrap {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Score card */
.score-display {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 32px;
  padding: 12px 0;
}

.score-ring {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  border: 4px solid rgba(148,163,184,0.2);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
}

.score-ring.level-good {
  border-color: #10b981;
  box-shadow: 0 0 20px rgba(16,185,129,0.2);
}

.score-ring.level-warn {
  border-color: #f59e0b;
  box-shadow: 0 0 20px rgba(245,158,11,0.2);
}

.score-ring.level-alert {
  border-color: #ef4444;
  box-shadow: 0 0 20px rgba(239,68,68,0.2);
}

.score-number {
  font-size: 1.6rem;
  font-weight: 800;
  color: var(--score-number-color);
  line-height: 1;
  font-family: 'Fira Code', monospace;
}

.score-label {
  font-size: 0.68rem;
  color: var(--score-label-color);
  margin-top: 2px;
}

.risk-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.risk-level-badge {
  font-size: 1.4rem;
  font-weight: 800;
  padding: 6px 20px;
  border-radius: 10px;
  font-family: 'Fira Code', monospace;
  background: rgba(148,163,184,0.1);
  color: #94a3b8;
}

.risk-level-badge.level-good {
  background: rgba(16,185,129,0.15);
  color: #10b981;
}

.risk-level-badge.level-warn {
  background: rgba(245,158,11,0.15);
  color: #f59e0b;
}

.risk-level-badge.level-alert {
  background: rgba(239,68,68,0.15);
  color: #ef4444;
}

.risk-label {
  font-size: 0.75rem;
  color: var(--risk-label-color);
}

/* Alert stats */
.alert-stats {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}

.alert-stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 14px 8px;
  border-radius: 12px;
  border: 1px solid transparent;
}

.alert-stat-item.normal {
  background: rgba(16,185,129,0.06);
  border-color: rgba(16,185,129,0.15);
}

.alert-stat-item.warning {
  background: rgba(245,158,11,0.06);
  border-color: rgba(245,158,11,0.15);
}

.alert-stat-item.alert {
  background: rgba(239,68,68,0.06);
  border-color: rgba(239,68,68,0.15);
}

.stat-number {
  font-size: 1.6rem;
  font-weight: 800;
  font-family: 'Fira Code', monospace;
  line-height: 1;
}

.alert-stat-item.normal  .stat-number { color: #10b981; }
.alert-stat-item.warning .stat-number { color: #f59e0b; }
.alert-stat-item.alert   .stat-number { color: #ef4444; }

.stat-label {
  font-size: 0.75rem;
  color: var(--stat-label-color);
  margin-top: 4px;
}

/* Suggestion */
.suggestion-card {
  position: relative;
  overflow: hidden;
}

.suggestion-icon {
  color: #667eea;
}

.suggestion-text {
  font-size: 0.875rem;
  color: var(--suggestion-text-color);
  line-height: 1.7;
  margin: 0;
}

/* Loading */
.loading-area {
  padding: 24px;
}

/* Empty state */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 80px 0;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 3rem;
  color: var(--text-muted);
}

.empty-state p {
  font-size: 0.95rem;
  margin: 0;
}

/* Responsive */
@media (max-width: 1100px) {
  .score-section {
    grid-template-columns: 1fr;
  }
  .score-summary-wrap {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
  }
}
</style>
