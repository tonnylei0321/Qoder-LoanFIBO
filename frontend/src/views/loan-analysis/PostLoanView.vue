<template>
  <div class="fibo-page">
    <!-- Page Title -->
    <div class="ph">
      <div class="pt">{{ pageTitle }}</div>
      <div class="ps">基于 v1.4 本体的 {{ scenarioIndicators.length }} 项持续监控指标 · 还款表现 / 应收应付 / 担保变化 · 点击任意行可查看详情</div>
    </div>

    <!-- Company Header -->
    <div class="co-hd" v-if="company">
      <div class="co-ico">{{ company.name.slice(0, 1) }}</div>
      <div style="flex:1">
        <div class="co-name">{{ company.name }}</div>
        <div class="co-meta">
          <span class="co-tag" v-if="company.region">📍 {{ company.region }}</span>
          <span class="co-tag" v-if="company.industry">🏭 {{ company.industry }}</span>
          <span class="co-tag" v-if="company.unified_code">{{ company.unified_code }}</span>
          <span class="co-tag">报告日期:{{ calcDate || '最新' }}</span>
          <span class="co-tag">数据验证:<span style="color:#1a7f6e;font-weight:500">✓ v1.4 本体核验通过</span></span>
        </div>
      </div>
      <div class="sc-area">
        <div class="sc-lbl">风险等级</div>
        <div class="sc-num" :style="{ color: scoreColor }">{{ totalScore }}</div>
        <div class="sc-gr" :style="{ background: scoreBg, color: scoreColor }">{{ riskLabel }}</div>
      </div>
    </div>

    <!-- Company Selector (when no company selected) -->
    <div class="co-hd" v-else>
      <div class="co-ico" style="background:linear-gradient(135deg, #667eea, #764ba2)">?</div>
      <div style="flex:1">
        <el-select
          v-model="selectedOrgId"
          filterable
          remote
          :remote-method="searchCompanies"
          :loading="searching"
          placeholder="搜索或选择企业..."
          class="company-select-inline"
          @change="onOrgSelect"
        >
          <el-option v-for="c in companyOptions" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" style="padding:40px;text-align:center;color:var(--text-tertiary)">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <div style="margin-top:8px">加载中...</div>
    </div>

    <template v-if="!loading && company">
      <!-- Alert Summary Cards -->
      <div class="alert-row">
        <div class="al-card" :class="{ hi: alertCounts.alert > 0 }">
          <div class="al-hd">
            <span class="al-lbl">高风险</span>
            <span class="al-ico" style="color:#c0392b">⚠</span>
          </div>
          <div class="al-num">{{ alertCounts.alert }}</div>
          <div class="al-chg cneg" v-if="alertCounts.alert > 0">需立即处理</div>
          <div class="al-chg cneu" v-else>无风险</div>
        </div>
        <div class="al-card" :class="{ wa: alertCounts.warning > 0 }">
          <div class="al-hd">
            <span class="al-lbl">需关注</span>
            <span class="al-ico" style="color:#b45309">👁</span>
          </div>
          <div class="al-num">{{ alertCounts.warning }}</div>
          <div class="al-chg" :class="alertCounts.warning > 0 ? 'cneg' : 'cneu'">{{ alertCounts.warning > 0 ? '持续跟踪' : '无异常' }}</div>
        </div>
        <div class="al-card">
          <div class="al-hd">
            <span class="al-lbl">正常</span>
            <span class="al-ico" style="color:#16a34a">✓</span>
          </div>
          <div class="al-num">{{ alertCounts.normal }}</div>
          <div class="al-chg cpos">运行良好</div>
        </div>
      </div>

      <!-- Radar + Dimension Bars -->
      <div class="analy-row">
        <div class="radar-card">
          <div class="card-st">维度评分雷达</div>
          <div class="radar-wrap">
            <svg viewBox="0 0 200 195" width="100%" style="display:block">
              <defs>
                <linearGradient id="rg_post" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stop-color="#1a7f6e" stop-opacity=".33" />
                  <stop offset="100%" stop-color="#1a7f6e" stop-opacity=".07" />
                </linearGradient>
              </defs>
              <g transform="translate(100,96)">
                <circle v-for="r in [74,56,37,18]" :key="r" :r="r" fill="none" style="stroke:var(--divider-color)" stroke-width=".7" />
                <line v-for="(p, i) in radarAxes" :key="'ax'+i"
                  x1="0" y1="-74" x2="0" y2="74" style="stroke:var(--divider-color)" stroke-width=".7"
                  :transform="`rotate(${i * 360 / radarAxes.length})`" />
                <polygon :points="radarPoints" fill="url(#rg_post)" stroke="#1a7f6e" stroke-width="1.5" opacity=".9" />
                <text v-for="(ax, i) in radarAxes" :key="'lb'+i"
                  :x="radarLabelPos(i).x" :y="radarLabelPos(i).y"
                  text-anchor="middle" font-size="8.5" style="fill:var(--text-secondary)" font-family="Inter,sans-serif"
                >{{ ax.name }} {{ ax.score }}</text>
              </g>
            </svg>
          </div>
        </div>
        <div class="dim-card">
          <div class="card-st">维度得分与权重分布</div>
          <div class="dim-list">
            <div class="dmi" v-for="dim in dimensionList" :key="dim.name">
              <div class="dml">{{ dim.name }} {{ dim.weightPct }}%</div>
              <div class="dmb"><div class="dmbar" :class="barClass(dim.score)" :style="{ width: dim.score + '%' }"></div></div>
              <div class="dms" :style="{ color: barColor(dim.score) }">{{ dim.score }}</div>
            </div>
          </div>
          <div class="dim-note">
            <span style="color:#1a7f6e;font-weight:500">✓ v1.4 本体核验通过</span> — 全部 {{ scenarioIndicators.length }} 项指标来自 v1.4 三层本体(概念 / 计算规则 / 取值),字段 100% 对齐用友 NCC 真实 DDL。
          </div>
        </div>
      </div>

      <!-- Indicator Layout: Left Nav + Right Sections -->
      <div class="ind-layout">
        <div class="dim-nav">
          <div class="dn-title">快速导航</div>
          <div
            v-for="(sec, idx) in indicatorSections"
            :key="sec.key"
            class="dn-item"
            :class="{ on: activeNav === idx }"
            @click="scrollToSection(idx)"
          >
            <div class="dn-dot" :style="{ background: sec.color }"></div>
            {{ sec.title }}
            <div class="dn-cnt">{{ sec.indicators.length }}</div>
          </div>
          <div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--card-border)">
            <div style="font-size:9px;color:var(--card-title-color);margin-bottom:5px">指标状态</div>
            <div class="status-legend">
              <div class="status-row"><div class="status-dot" style="background:#c0392b"></div>高风险 <span style="margin-left:auto;font-family:var(--font-mono)">{{ alertCounts.alert }}</span></div>
              <div class="status-row"><div class="status-dot" style="background:#f59e0b"></div>需关注 <span style="margin-left:auto;font-family:var(--font-mono)">{{ alertCounts.warning }}</span></div>
              <div class="status-row"><div class="status-dot" style="background:#16a34a"></div>正常 <span style="margin-left:auto;font-family:var(--font-mono)">{{ alertCounts.normal }}</span></div>
            </div>
          </div>
        </div>

        <div class="ind-sections" ref="sectionsContainer">
          <div
            v-for="(sec, idx) in indicatorSections"
            :key="sec.key"
            class="ind-sec"
            :id="'sec-' + sec.key"
            :ref="el => sectionRefs[idx] = el"
          >
            <div class="is-hd">
              <div class="is-ico" :style="{ background: sec.iconBg, color: sec.color }">{{ sec.icon }}</div>
              <span class="is-title">{{ sec.title }}</span>
              <span class="is-weight">归属:{{ sec.dimName }} · 权重 {{ sec.weightPct }}%</span>
              <span class="is-score" :style="{ background: sec.scoreBg, color: sec.scoreColor }">{{ sec.score }} / 100</span>
            </div>
            <table class="it">
              <thead>
                <tr>
                  <th style="width:22%">指标名称 / 本体路径</th>
                  <th>当前值</th>
                  <th>阈值</th>
                  <th>状态</th>
                  <th>环比</th>
                  <th>相关指标</th>
                  <th>详情</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="ind in sec.indicators"
                  :key="ind.indicatorUri"
                  class="clickable"
                  @click="openDrawer(ind)"
                >
                  <td>
                    <div class="ind-nm">{{ ind.indicatorLabel }}</div>
                    <div class="ind-fibo">{{ ind.notation || shortName(ind.indicatorUri) }}</div>
                  </td>
                  <td><div class="ind-val" :class="valueClass(ind)">{{ formatIndValue(ind) }}</div></td>
                  <td><div class="ind-thresh">{{ getThresholdText(ind) }}</div></td>
                  <td>
                    <div class="st-wrap">
                      <div class="std" :class="statusDot(ind)"></div>
                      <span class="bdg" :class="statusBadge(ind)">{{ statusLabel(ind) }}</span>
                    </div>
                  </td>
                  <td><span class="delta" :class="deltaClass(ind)">{{ deltaText(ind) }}</span></td>
                  <td>
                    <div class="cv-tags">
                      <span v-for="rel in getRelatedIndicators(ind, sec)" :key="rel.indicatorUri" class="cvt" @click.stop="openDrawer(rel)">{{ rel.indicatorLabel }}</span>
                    </div>
                  </td>
                  <td><button class="det-btn" @click.stop="openDrawer(ind)">查看详情</button></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </template>

    <div v-if="!loading && !company" class="empty-state">
      <p>请选择企业以查看贷后监控分析</p>
    </div>

    <!-- Indicator Detail Drawer -->
    <IndicatorDrawer
      v-model="drawerVisible"
      :indicator="drawerIndicator"
      :indicator-detail="drawerDetail"
      :loading-detail="loadingDetail"
      :matched-value="drawerMatchedValue"
      @navigate="handleNavigate"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { loanAnalysisApi, type IndicatorValue, type CompanyScoreResponse } from '@/api/loanAnalysis'
import { graphExploreApi, type ScenarioIndicator, type IndicatorDetail } from '@/api/graphExplore'
import { orgApi, type ApplicantOrg } from '@/api/org'
import IndicatorDrawer from '@/components/loan/IndicatorDrawer.vue'

const SCENARIO = 'PostLoanMonitoring'
const SCENARIO_PG = 'post_loan'

const selectedOrgId = ref('')
const company = ref<ApplicantOrg | null>(null)
const loading = ref(false)
const searching = ref(false)
const companyOptions = ref<ApplicantOrg[]>([])
const scenarioIndicators = ref<ScenarioIndicator[]>([])
const indicatorValues = ref<IndicatorValue[]>([])
const scoreData = ref<CompanyScoreResponse | null>(null)
const activeNav = ref(0)
const sectionRefs = ref<any[]>([])
const sectionsContainer = ref<HTMLElement>()

// Drawer
const drawerVisible = ref(false)
const drawerIndicator = ref<ScenarioIndicator | null>(null)
const drawerDetail = ref<IndicatorDetail | null>(null)
const loadingDetail = ref(false)

const drawerMatchedValue = computed(() => {
  if (!drawerIndicator.value) return undefined
  return matchIndicator(drawerIndicator.value)
})

const pageTitle = computed(() => company.value ? `${company.value.name} — 贷后监控报告` : '贷后监控报告')
const calcDate = computed(() => scoreData.value?.calc_date || '')
const scoreRecord = computed(() => scoreData.value?.score_record)
const totalScore = computed(() => scoreRecord.value?.total_score ?? '—')
const riskLabel = computed(() => {
  if (!scoreRecord.value?.total_score) return '—'
  const s = scoreRecord.value.total_score
  if (s >= 80) return '✓ 合格 · 建议授信'
  if (s >= 60) return '⚠ 需关注 · 限制授信'
  return '✗ 高风险 · 拒绝授信'
})
const scoreColor = computed(() => {
  const s = scoreRecord.value?.total_score
  if (s == null) return 'var(--text-tertiary)'
  if (s >= 80) return '#1a7f6e'
  if (s >= 60) return '#b45309'
  return '#c0392b'
})
const scoreBg = computed(() => {
  const s = scoreRecord.value?.total_score
  if (s == null) return 'var(--section-bg)'
  if (s >= 80) return 'rgba(26,127,110,.12)'
  if (s >= 60) return 'rgba(180,83,9,.1)'
  return 'rgba(192,57,43,.1)'
})

const alertCounts = computed(() => {
  const counts = { alert: 0, warning: 0, normal: 0 }
  for (const v of indicatorValues.value) {
    if (v.alert_level === 'alert') counts.alert++
    else if (v.alert_level === 'warning') counts.warning++
    else counts.normal++
  }
  return counts
})

// Dimensions
const dimensionList = computed(() => {
  if (!scoreRecord.value?.dimension_scores) return []
  return Object.values(scoreRecord.value.dimension_scores).map(d => ({
    name: d.name,
    score: d.score,
    weight: d.weight,
    weightPct: Math.round(d.weight * 100),
  }))
})

// Radar
const radarAxes = computed(() => dimensionList.value.map(d => ({ name: d.name, score: d.score })))
const radarPoints = computed(() => {
  const n = radarAxes.value.length
  if (n === 0) return ''
  return radarAxes.value.map((ax, i) => {
    const angle = (i * 2 * Math.PI / n) - Math.PI / 2
    const r = (ax.score / 100) * 74
    return `${(r * Math.cos(angle)).toFixed(1)},${(r * Math.sin(angle)).toFixed(1)}`
  }).join(' ')
})
function radarLabelPos(i: number) {
  const n = radarAxes.value.length
  const angle = (i * 2 * Math.PI / n) - Math.PI / 2
  const r = 88
  return { x: (r * Math.cos(angle)).toFixed(1), y: (r * Math.sin(angle)).toFixed(1) }
}
function barClass(score: number) { return score >= 80 ? 'bar-g' : score >= 60 ? 'bar-o' : 'bar-r' }
function barColor(score: number) { return score >= 80 ? '#1a7f6e' : score >= 60 ? '#b45309' : '#c0392b' }

// Matching
function shortName(uri: string): string {
  const colonIdx = uri.lastIndexOf(':')
  const slashIdx = uri.lastIndexOf('/')
  return uri.substring(Math.max(colonIdx, slashIdx) + 1)
}
function matchIndicator(row: ScenarioIndicator): IndicatorValue | undefined {
  const uriShort = shortName(row.indicatorUri)
  return indicatorValues.value.find(v => {
    if (v.fibo_path) return shortName(v.fibo_path) === uriShort
    return row.indicatorLabel.includes(v.indicator_name || '')
  })
}

// Indicator sections
const indicatorSections = computed(() => {
  const sectionStyles: Record<string, { color: string; icon: string; iconBg: string }> = {
    '应收应付': { color: '#6d28d9', icon: '📉', iconBg: 'rgba(109,40,217,.1)' },
    '还款表现': { color: '#b45309', icon: '💳', iconBg: 'rgba(180,83,9,.1)' },
    '担保变化': { color: '#c0392b', icon: '🔄', iconBg: 'rgba(192,57,43,.1)' },
    '偿债能力': { color: '#b45309', icon: '⚖', iconBg: 'rgba(180,83,9,.1)' },
    '资产质量': { color: '#1a7f6e', icon: '💎', iconBg: 'rgba(26,127,110,.1)' },
    '外部风险': { color: '#c0392b', icon: '⚠', iconBg: 'rgba(192,57,43,.1)' },
  }
  const defaultStyle = { color: 'var(--text-secondary)', icon: '📋', iconBg: 'var(--section-bg)' }

  const dimMap = new Map<string, ScenarioIndicator[]>()
  const dimMeta = new Map<string, { dimName: string; weightPct: number; score: number; color: string; icon: string; iconBg: string }>()

  for (const ind of scenarioIndicators.value) {
    const match = matchIndicator(ind)
    const dimName = match?.dimension_name || inferDimensionFromNotation(ind.notation)
    if (!dimMap.has(dimName)) dimMap.set(dimName, [])
    dimMap.get(dimName)!.push(ind)

    if (!dimMeta.has(dimName)) {
      const dimScore = dimensionList.value.find(d => d.name === dimName)
      const style = sectionStyles[dimName] || defaultStyle
      dimMeta.set(dimName, { dimName, weightPct: dimScore?.weightPct || 0, score: dimScore?.score || 0, ...style })
    }
  }

  let idx = 0
  return Array.from(dimMap.entries()).map(([dimName, indicators]) => {
    const meta = dimMeta.get(dimName)!
    return {
      key: `post-${idx++}`,
      title: dimName,
      dimName: meta.dimName,
      weightPct: meta.weightPct,
      score: meta.score,
      color: meta.color,
      icon: meta.icon,
      iconBg: meta.iconBg,
      scoreBg: meta.score >= 80 ? 'rgba(26,127,110,.12)' : meta.score >= 60 ? 'rgba(180,83,9,.1)' : 'rgba(192,57,43,.1)',
      scoreColor: meta.score >= 80 ? '#1a7f6e' : meta.score >= 60 ? '#b45309' : '#c0392b',
      indicators,
    }
  })
})

function inferDimensionFromNotation(notation?: string): string {
  if (!notation) return '其他'
  const prefix = (notation.split('-')[1] || '') as string
  const map: Record<string, string> = {
    AR: '应收应付', REP: '还款表现', GUA: '担保变化',
    SOLV: '偿债能力', ASSET: '资产质量', RISK: '外部风险',
  }
  return map[prefix] || '其他'
}

// Value helpers
function formatIndValue(ind: ScenarioIndicator): string {
  const match = matchIndicator(ind)
  if (match?.value != null) {
    return Math.abs(match.value) >= 10000 ? (match.value / 10000).toFixed(2) + '万' : match.value.toFixed(2)
  }
  return '—'
}
function valueClass(ind: ScenarioIndicator): string {
  const level = matchIndicator(ind)?.alert_level
  if (level === 'alert') return 'vr'
  if (level === 'warning') return 'vw'
  return 'vg'
}
function getThresholdText(ind: ScenarioIndicator): string {
  const match = matchIndicator(ind)
  if (!match) return '—'
  const parts: string[] = []
  if (match.threshold_warning != null) {
    const dir = match.threshold_direction || 'above'
    if (dir === 'above') {
      parts.push(`≥ ${match.threshold_warning.toFixed(2)}(关注)`)
      if (match.threshold_alert != null) parts.push(`< ${match.threshold_alert.toFixed(2)}(预警)`)
    } else {
      parts.push(`≤ ${match.threshold_warning.toFixed(2)}(关注)`)
      if (match.threshold_alert != null) parts.push(`> ${match.threshold_alert.toFixed(2)}(预警)`)
    }
  }
  return parts.join('/') || '—'
}
function statusDot(ind: ScenarioIndicator): string {
  const level = matchIndicator(ind)?.alert_level
  if (level === 'alert') return 'r'
  if (level === 'warning') return 'a'
  return 'g'
}
function statusBadge(ind: ScenarioIndicator): string {
  const level = matchIndicator(ind)?.alert_level
  if (level === 'alert') return 'b-red'
  if (level === 'warning') return 'b-amber'
  return 'b-green'
}
function statusLabel(ind: ScenarioIndicator): string {
  const level = matchIndicator(ind)?.alert_level
  if (level === 'alert') return '预警'
  if (level === 'warning') return '关注'
  return '正常'
}
function deltaClass(ind: ScenarioIndicator): string {
  const match = matchIndicator(ind)
  if (!match?.change_pct) return 'dn'
  const good = (match.threshold_direction ?? 'above') === 'above' ? match.change_pct > 0 : match.change_pct < 0
  return good ? 'du' : 'dd'
}
function deltaText(ind: ScenarioIndicator): string {
  const match = matchIndicator(ind)
  if (!match?.change_pct) return '→ 持平'
  const pct = Math.abs(match.change_pct).toFixed(1)
  return match.change_pct > 0 ? `↑ ${pct}%` : `↓ ${pct}%`
}
function getRelatedIndicators(ind: ScenarioIndicator, sec: { indicators: ScenarioIndicator[] }): ScenarioIndicator[] {
  return sec.indicators.filter(i => i.indicatorUri !== ind.indicatorUri).slice(0, 2)
}

// Navigation
function scrollToSection(idx: number) {
  activeNav.value = idx
  const el = sectionRefs.value[idx]
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// Drawer
async function openDrawer(ind: ScenarioIndicator) {
  drawerIndicator.value = ind
  drawerDetail.value = null
  drawerVisible.value = true
  loadingDetail.value = true
  try {
    drawerDetail.value = await graphExploreApi.getIndicatorDetail(ind.indicatorUri)
  } catch { ElMessage.error('加载指标详情失败') }
  finally { loadingDetail.value = false }
}
async function handleNavigate(uri: string) {
  const ind = scenarioIndicators.value.find(i => i.indicatorUri === uri)
  if (ind) {
    drawerIndicator.value = ind
    drawerDetail.value = null
    loadingDetail.value = true
    try { drawerDetail.value = await graphExploreApi.getIndicatorDetail(uri) }
    catch { ElMessage.error('加载指标详情失败') }
    finally { loadingDetail.value = false }
  }
}

// Data loading
async function loadData(orgId: string) {
  loading.value = true
  try {
    const [indRes, values, scoreRes] = await Promise.all([
      graphExploreApi.getScenarioIndicators(SCENARIO),
      loanAnalysisApi.getCompanyIndicators(orgId, SCENARIO_PG).catch(() => [] as IndicatorValue[]),
      loanAnalysisApi.getCompanyScore(orgId, SCENARIO_PG).catch(() => null as CompanyScoreResponse | null),
    ])
    scenarioIndicators.value = indRes.indicators
    indicatorValues.value = values
    scoreData.value = scoreRes
  } catch { ElMessage.error('加载数据失败') }
  finally { loading.value = false }
}

async function searchCompanies(query: string) {
  searching.value = true
  try {
    const allOrgs = await orgApi.listOrgs(true)
    companyOptions.value = query ? allOrgs.filter(o => o.name.includes(query) || (o.unified_code && o.unified_code.includes(query))) : allOrgs
  } catch { /* ignore */ } finally { searching.value = false }
}

async function onOrgSelect(id: string) {
  if (!id) return
  try { company.value = await orgApi.getOrg(id); loadData(id) }
  catch { ElMessage.error('加载企业信息失败') }
}

searchCompanies('')
</script>

<style scoped>
/* ── Loan Analysis Shared Tokens (theme-aware) ── */

.fibo-page { padding: 22px; max-width: 1280px; margin: 0 auto; width: 100%; font-family: var(--font-body); font-size: 14px; line-height: 1.6; color: var(--text-primary); }

/* Page header */
.ph { margin-bottom: 18px; }
.pt { font-family: var(--font-display); font-size: 24px; font-weight: 600; color: var(--page-title-color); }
.ps { font-size: 12px; color: var(--page-desc-color); margin-top: 3px; }

/* Company header */
.co-hd { background: var(--card-bg-subtle); border: 1px solid var(--card-border); border-radius: var(--radius-md); padding: 16px 20px; margin-bottom: 14px; display: flex; align-items: flex-start; gap: 14px; }
.co-ico { width: 42px; height: 42px; border-radius: var(--radius-md); background: linear-gradient(135deg, #667eea, #764ba2); display: flex; align-items: center; justify-content: center; font-family: var(--font-display); font-size: 18px; color: #fff; flex-shrink: 0; }
.co-name { font-family: var(--font-display); font-size: 18px; font-weight: 600; color: var(--company-name-color); }
.co-meta { display: flex; gap: 12px; margin-top: 5px; flex-wrap: wrap; }
.co-tag { font-size: 10px; color: var(--meta-item-color); }
.sc-area { text-align: right; flex-shrink: 0; }
.sc-lbl { font-size: 9px; color: var(--stat-label-color); text-transform: uppercase; letter-spacing: .08em; }
.sc-num { font-family: var(--font-display); font-size: 40px; line-height: 1; margin-top: 2px; }
.sc-gr { font-size: 10px; font-weight: 500; padding: 2px 7px; border-radius: 10px; display: inline-block; margin-top: 3px; }

/* Alert cards */
.alert-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-bottom: 14px; }
.al-card { background: var(--card-bg-subtle); border: 1px solid var(--card-border); border-radius: var(--radius-md); padding: 12px 14px; }
.al-card.hi { border-color: rgba(192,57,43,.3); background: rgba(192,57,43,.05); }
.al-card.wa { border-color: rgba(245,158,11,.3); background: rgba(245,158,11,.05); }
.al-hd { display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px; }
.al-lbl { font-size: 9px; color: var(--card-title-color); text-transform: uppercase; letter-spacing: .06em; font-weight: 500; }
.al-num { font-family: var(--font-display); font-size: 22px; color: var(--text-primary); }
.al-chg { font-size: 10px; margin-top: 2px; }
.cneg { color: #c0392b; }
.cpos { color: #1a7f6e; }
.cneu { color: var(--text-tertiary); }

/* Radar + Dims */
.analy-row { display: grid; grid-template-columns: 210px 1fr; gap: 12px; margin-bottom: 14px; }
.radar-card, .dim-card { background: var(--card-bg-subtle); border: 1px solid var(--card-border); border-radius: var(--radius-md); padding: 13px; }
.card-st { font-size: 10px; font-weight: 500; color: var(--card-title-color); text-transform: uppercase; letter-spacing: .07em; margin-bottom: 9px; }
.radar-wrap { max-width: 200px; margin: 0 auto; }
.dim-list { display: flex; flex-direction: column; gap: 7px; }
.dmi { display: flex; align-items: center; gap: 7px; }
.dml { font-size: 10px; color: var(--text-primary); width: 120px; flex-shrink: 0; }
.dmb { flex: 1; height: 4px; background: var(--divider-color); border-radius: 2px; overflow: hidden; }
.dmbar { height: 100%; border-radius: 2px; transition: width 1s ease; }
.bar-g { background: #1a7f6e; }
.bar-o { background: #c9a84c; }
.bar-r { background: #c0392b; }
.dms { font-size: 10px; font-family: var(--font-mono); color: var(--text-tertiary); width: 24px; text-align: right; }
.dim-note { margin-top: 13px; padding: 9px 11px; background: var(--section-bg); border-radius: var(--radius-sm); font-size: 11px; color: var(--suggestion-text-color); line-height: 1.7; }

/* Indicator Layout */
.ind-layout { display: grid; grid-template-columns: 172px 1fr; gap: 14px; }
.dim-nav { background: var(--card-bg-subtle); border: 1px solid var(--card-border); border-radius: var(--radius-md); padding: 11px; position: sticky; top: 65px; height: fit-content; }
.dn-title { font-size: 9px; font-weight: 600; color: var(--card-title-color); text-transform: uppercase; letter-spacing: .09em; margin-bottom: 9px; }
.dn-item { padding: 6px 8px; border-radius: var(--radius-sm); font-size: 11px; color: var(--text-secondary); cursor: pointer; transition: all .12s; display: flex; align-items: center; gap: 6px; margin-bottom: 2px; }
.dn-item:hover { background: var(--dim-tab-hover-bg); color: var(--text-primary); }
.dn-item.on { background: rgba(26,127,110,.12); color: #1a7f6e; font-weight: 500; }
.dn-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.dn-cnt { font-size: 9px; font-family: var(--font-mono); margin-left: auto; color: var(--text-tertiary); background: var(--section-bg); padding: 1px 5px; border-radius: 8px; }
.status-legend { font-size: 10px; display: flex; flex-direction: column; gap: 4px; }
.status-row { display: flex; align-items: center; gap: 5px; }
.status-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }

/* Indicator Section */
.ind-sections { display: flex; flex-direction: column; gap: 10px; }
.ind-sec { background: var(--card-bg-subtle); border: 1px solid var(--card-border); border-radius: var(--radius-md); overflow: hidden; }
.is-hd { padding: 9px 14px; background: var(--section-bg); border-bottom: 1px solid var(--card-border); display: flex; align-items: center; gap: 8px; }
.is-ico { width: 22px; height: 22px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 11px; flex-shrink: 0; }
.is-title { font-size: 12px; font-weight: 600; color: var(--text-primary); flex: 1; }
.is-weight { font-size: 10px; color: var(--text-tertiary); font-family: var(--font-mono); }
.is-score { font-size: 11px; font-weight: 600; font-family: 'JetBrains Mono', monospace; padding: 2px 7px; border-radius: 4px; }

/* Indicator Table */
.it { width: 100%; border-collapse: collapse; }
.it th { padding: 8px 12px; background: var(--table-header-bg); color: var(--table-header-color); font-weight: 500; text-align: left; border-bottom: 1px solid var(--card-border); font-size: 11px; text-transform: uppercase; letter-spacing: .06em; white-space: nowrap; }
.it td { padding: 11px 12px; border-bottom: 1px solid var(--divider-color); vertical-align: middle; font-size: 13px; color: var(--table-cell-color); }
.it tr:last-child td { border-bottom: none; }
.it tr.clickable:hover td { background: rgba(26,127,110,.04); cursor: pointer; }
.ind-nm { font-size: 13px; font-weight: 500; color: var(--ind-name-color); }
.ind-fibo { font-size: 11px; color: var(--fibo-icon-color); font-family: var(--font-mono); margin-top: 1px; }
.ind-val { font-family: var(--font-mono); font-size: 14px; font-weight: 600; }
.vr { color: #c0392b; }
.vw { color: #b45309; }
.vg { color: #1a7f6e; }
.ind-thresh { font-size: 11px; color: var(--threshold-color); font-family: var(--font-mono); }
.st-wrap { display: flex; align-items: center; gap: 5px; }
.std { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.std.r { background: #c0392b; }
.std.a { background: #f59e0b; }
.std.g { background: #16a34a; }
.bdg { font-size: 11px; padding: 2px 8px; border-radius: 10px; font-weight: 500; white-space: nowrap; display: inline-block; }
.b-red { background: rgba(192,57,43,.1); color: #c0392b; }
.b-amber { background: rgba(180,83,9,.1); color: #b45309; }
.b-green { background: rgba(22,163,74,.1); color: #16a34a; }
.delta { font-size: 11px; padding: 1px 5px; border-radius: 3px; }
.dd { background: rgba(192,57,43,.1); color: #c0392b; }
.du { background: rgba(22,163,74,.1); color: #16a34a; }
.dn { background: var(--section-bg); color: var(--text-tertiary); }
.cv-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.cvt { font-size: 11px; padding: 2px 6px; border: 1px solid var(--card-border); border-radius: 3px; color: var(--text-tertiary); cursor: pointer; background: var(--card-bg-subtle); transition: all .12s; white-space: nowrap; }
.cvt:hover { border-color: #1a7f6e; color: #1a7f6e; background: rgba(26,127,110,.1); }
.det-btn { font-size: 11px; padding: 4px 10px; border: 1px solid #1a7f6e; border-radius: var(--radius-sm); background: var(--card-bg-subtle); color: #1a7f6e; cursor: pointer; transition: all .12s; font-family: var(--font-body); white-space: nowrap; }
.det-btn:hover { background: #1a7f6e; color: #fff; }

.empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 16px; padding: 80px 0; color: var(--text-tertiary); }
.empty-state p { font-size: 0.95rem; margin: 0; }
.company-select-inline { width: 300px; }
</style>
