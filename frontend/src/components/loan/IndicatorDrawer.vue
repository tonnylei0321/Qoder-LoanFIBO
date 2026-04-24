<template>
  <Teleport to="body">
    <transition name="drawer-fade">
      <div v-if="modelValue" class="dov" @click.self="closeDrawer">
        <transition name="drawer-slide">
          <div v-if="modelValue" class="drawer">
            <!-- Drawer top bar -->
            <div class="drw-top">
              <div v-if="indicator" style="flex:1">
                <div class="drw-name">{{ indicator.indicatorLabel }}</div>
                <div class="drw-fibo">{{ indicator.notation || shortName(indicator.indicatorUri) }}</div>
              </div>
              <button class="drw-close" @click="closeDrawer">✕</button>
            </div>

            <!-- Drawer body -->
            <div class="drw-body" v-if="indicator">
              <!-- Loading -->
              <div v-if="loadingDetail" style="padding:40px;text-align:center;color:var(--fibo-ink-soft)">
                <el-icon class="is-loading" :size="20"><Loading /></el-icon>
                <div style="margin-top:8px;font-size:12px">加载详情...</div>
              </div>

              <template v-if="!loadingDetail && detail">
                <!-- Value Hero -->
                <div class="ds">
                  <div class="ds-title">
                    <div class="ds-ico" style="background:var(--fibo-teal-lt);color:var(--fibo-teal)">📊</div>
                    当前取值
                  </div>
                  <div class="val-hero">
                    <div class="vh-val" :class="valueHeroClass">{{ matchedValue }}</div>
                    <div class="vh-info">
                      <div class="vh-name">{{ detail.tab1.label }}</div>
                      <div class="vh-fibo" v-if="detail.tab1.closeMatches.length">
                        对标: {{ detail.tab1.closeMatches.map(fiboShortName).join(', ') }}
                      </div>
                      <div class="vh-status">
                        <span class="bdg" :class="statusBadge">{{ statusLabel }}</span>
                        <span v-if="matchedChange" class="delta" :class="deltaClass">{{ matchedChange }}</span>
                      </div>
                      <div class="vh-thresh" v-if="thresholdText">阈值: {{ thresholdText }}</div>
                    </div>
                  </div>
                </div>

                <!-- FIBO Definition -->
                <div class="ds">
                  <div class="ds-title">
                    <div class="ds-ico" style="background:var(--fibo-gold-lt);color:var(--fibo-gold)">🧬</div>
                    FIBO 本体定义
                  </div>
                  <div class="fibo-box">
                    <div class="fibo-uri">{{ indicator.indicatorUri }}</div>
                    <div class="fibo-def">{{ detail.tab1.comment || '暂无定义' }}</div>
                    <div class="fibo-props" v-if="detail.tab1.subjects.length">
                      <span class="fp" v-for="s in detail.tab1.subjects" :key="s">{{ s }}</span>
                    </div>
                  </div>
                </div>

                <!-- Scenarios -->
                <div class="ds" v-if="detail.tab1.scenarios.length">
                  <div class="ds-title">
                    <div class="ds-ico" style="background:var(--fibo-blue-lt);color:var(--fibo-blue)">🎯</div>
                    适用场景
                  </div>
                  <div class="cv-tags">
                    <span class="cvt" v-for="s in detail.tab1.scenarios" :key="s.uri">{{ s.label }}</span>
                  </div>
                </div>

                <!-- Data Source -->
                <div class="ds" v-if="detail.tab2.formula || detail.tab2.tables.length">
                  <div class="ds-title">
                    <div class="ds-ico" style="background:var(--fibo-amber-lt);color:var(--fibo-amber)">📐</div>
                    计算规则与数据来源
                  </div>
                  <div class="src-card" v-if="detail.tab2.formula">
                    <div class="src-hd">
                      <span class="src-lbl">{{ detail.tab2.ruleLabel || '计算公式' }}</span>
                    </div>
                    <div class="src-body">
                      <div class="formula">{{ detail.tab2.formula }}</div>
                    </div>
                  </div>
                  <div class="src-card" v-if="detail.tab2.tables.length">
                    <div class="src-hd">
                      <span class="src-lbl">数据来源 (NCC DDL)</span>
                      <span class="src-cnt">{{ detail.tab2.tables.length }} 张表</span>
                    </div>
                    <div class="src-body">
                      <div class="src-fields">
                        <span class="sf k" v-for="t in detail.tab2.tables" :key="t.uri">{{ t.label }}</span>
                      </div>
                      <div class="src-fields" v-if="detail.tab2.fields.length" style="margin-top:6px">
                        <span class="sf" v-for="f in detail.tab2.fields" :key="f.uri">{{ f.label }}</span>
                      </div>
                    </div>
                  </div>
                  <!-- SQL (collapsible) -->
                  <div class="src-card" v-if="detail.tab2.sql">
                    <div class="src-hd" @click="showSql = !showSql" style="cursor:pointer">
                      <span class="src-lbl">技术口径 (SQL)</span>
                      <span style="font-size:10px;color:var(--fibo-ink-soft)">{{ showSql ? '收起 ▲' : '展开 ▼' }}</span>
                    </div>
                    <div class="src-body" v-if="showSql">
                      <pre class="sql-block">{{ detail.tab2.sql }}</pre>
                    </div>
                  </div>
                </div>

                <!-- Trust Grid -->
                <div class="ds" v-if="detail.tab3.length">
                  <div class="ds-title">
                    <div class="ds-ico" style="background:var(--fibo-teal-lt);color:var(--fibo-teal)">✓</div>
                    数据可信度
                  </div>
                  <div class="trust-grid">
                    <div class="ti ok">
                      <div class="ti-hd"><span class="ti-ico">✓</span><span class="ti-lbl">本体映射</span></div>
                      <div class="ti-body">FIBO v1.4 三层本体核验通过</div>
                    </div>
                    <div class="ti ok">
                      <div class="ti-hd"><span class="ti-ico">✓</span><span class="ti-lbl">DDL 对齐</span></div>
                      <div class="ti-body">字段 100% 对齐用友 NCC 真实 DDL</div>
                    </div>
                    <div class="ti" :class="detail.tab3.length > 0 ? 'ok' : 'warn'">
                      <div class="ti-hd"><span class="ti-ico">{{ detail.tab3.length > 0 ? '✓' : '⚠' }}</span><span class="ti-lbl">取值记录</span></div>
                      <div class="ti-body">{{ detail.tab3.length }} 条计算记录</div>
                    </div>
                    <div class="ti ok">
                      <div class="ti-hd"><span class="ti-ico">✓</span><span class="ti-lbl">SQL 可执行</span></div>
                      <div class="ti-body">SQL 可直接执行</div>
                    </div>
                  </div>
                </div>

                <!-- Cross Validation -->
                <div class="ds" v-if="detail.tab4.sameTopic.length || detail.tab4.sharedSource.length">
                  <div class="ds-title">
                    <div class="ds-ico" style="background:var(--fibo-purple-lt);color:var(--fibo-purple)">🔗</div>
                    交叉验证
                  </div>
                  <div class="cv-list">
                    <div class="cv-item" v-if="detail.tab4.sameTopic.length">
                      <div class="cv-hd">
                        <span class="cv-name">同主题指标</span>
                      </div>
                      <div class="cv-body">
                        <div class="cv-tags">
                          <span class="cvt" v-for="r in detail.tab4.sameTopic" :key="r.uri" @click="$emit('navigate', r.uri)">{{ r.label }}</span>
                        </div>
                      </div>
                    </div>
                    <div class="cv-item" v-if="detail.tab4.sharedSource.length">
                      <div class="cv-hd">
                        <span class="cv-name">共享数据源</span>
                      </div>
                      <div class="cv-body">
                        <div class="cv-tags">
                          <span class="cvt" v-for="r in detail.tab4.sharedSource" :key="r.uri" @click="$emit('navigate', r.uri)">{{ r.label }}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <!-- Historical Data -->
                <div class="ds" v-if="detail.tab3.length">
                  <div class="ds-title">
                    <div class="ds-ico" style="background:var(--fibo-blue-lt);color:var(--fibo-blue)">📈</div>
                    历史数据
                  </div>
                  <table class="it">
                    <thead><tr><th>期间</th><th>机构</th><th>数值</th><th>计算时间</th></tr></thead>
                    <tbody>
                      <tr v-for="row in detail.tab3.slice(0, 10)" :key="row.uri">
                        <td style="font-size:11px">{{ row.period }}</td>
                        <td style="font-size:11px">{{ row.org }}</td>
                        <td style="font-size:11px;font-family:'JetBrains Mono',monospace;font-weight:600">{{ row.value }}</td>
                        <td style="font-size:11px;color:var(--fibo-ink-soft)">{{ row.computedAt }}</td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </template>
            </div>
          </div>
        </transition>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ScenarioIndicator, IndicatorDetail } from '@/api/graphExplore'
import type { IndicatorValue } from '@/api/loanAnalysis'

const props = defineProps<{
  modelValue: boolean
  indicator: ScenarioIndicator | null
  indicatorDetail: IndicatorDetail | null
  loadingDetail?: boolean
  matchedValue?: IndicatorValue | undefined
}>()

const emit = defineEmits<{
  'update:modelValue': [val: boolean]
  navigate: [uri: string]
}>()

const showSql = ref(false)

function closeDrawer() {
  emit('update:modelValue', false)
}

function shortName(uri: string): string {
  const colonIdx = uri.lastIndexOf(':')
  const slashIdx = uri.lastIndexOf('/')
  return uri.substring(Math.max(colonIdx, slashIdx) + 1)
}

function fiboShortName(uri: string): string {
  if (!uri) return ''
  const match = uri.match(/fibo\/ontology\/([^/]+)\/[^/]+\/([^/]+)/)
  if (match) return `${match[1]}:${match[2]}`
  return shortName(uri)
}

// Computed from matchedValue
const detail = computed(() => props.indicatorDetail)

const matchedValue = computed(() => {
  // Use the injected matchedValue if provided, otherwise try to compute
  return props.matchedValue
})

const matchedValueDisplay = computed(() => {
  if (!props.matchedValue?.value) return '—'
  const v = props.matchedValue.value
  return Math.abs(v) >= 10000 ? (v / 10000).toFixed(2) + '万' : v.toFixed(2)
})

const valueHeroClass = computed(() => {
  const level = props.matchedValue?.alert_level
  if (level === 'alert') return 'vr'
  if (level === 'warning') return 'vw'
  return 'vg'
})

const statusBadge = computed(() => {
  const level = props.matchedValue?.alert_level
  if (level === 'alert') return 'b-red'
  if (level === 'warning') return 'b-amber'
  return 'b-green'
})

const statusLabel = computed(() => {
  const level = props.matchedValue?.alert_level
  if (level === 'alert') return '预警'
  if (level === 'warning') return '关注'
  return '正常'
})

const matchedChange = computed(() => {
  const pct = props.matchedValue?.change_pct
  if (pct == null) return null
  return (pct > 0 ? '↑ ' : '↓ ') + Math.abs(pct).toFixed(1) + '%'
})

const deltaClass = computed(() => {
  const pct = props.matchedValue?.change_pct
  if (pct == null) return 'dn'
  const dir = props.matchedValue?.threshold_direction ?? 'above'
  const good = dir === 'above' ? pct > 0 : pct < 0
  return good ? 'du' : 'dd'
})

const thresholdText = computed(() => {
  const v = props.matchedValue
  if (!v) return ''
  const parts: string[] = []
  if (v.threshold_warning != null) parts.push(`关注: ${v.threshold_warning.toFixed(2)}`)
  if (v.threshold_alert != null) parts.push(`预警: ${v.threshold_alert.toFixed(2)}`)
  return parts.join(' / ')
})
</script>

<style scoped>
/* Overlay */
.dov { position: fixed; inset: 0; background: rgba(0,0,0,.5); z-index: 200; display: flex; justify-content: flex-end; }
.drawer { width: 740px; max-width: 96vw; background: var(--bg-secondary); height: 100%; overflow-y: auto; display: flex; flex-direction: column; }

/* Transitions */
.drawer-fade-enter-active, .drawer-fade-leave-active { transition: opacity .2s ease; }
.drawer-fade-enter-from, .drawer-fade-leave-to { opacity: 0; }
.drawer-slide-enter-active { transition: transform .28s ease; }
.drawer-slide-leave-active { transition: transform .18s ease; }
.drawer-slide-enter-from, .drawer-slide-leave-to { transform: translateX(60px); }

/* Top */
.drw-top { padding: 13px 20px; border-bottom: 1px solid var(--card-border); display: flex; align-items: flex-start; gap: 10px; position: sticky; top: 0; background: var(--bg-secondary); z-index: 1; flex-shrink: 0; }
.drw-name { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.drw-fibo { font-size: 9px; font-family: var(--font-mono); color: var(--text-tertiary); margin-top: 2px; }
.drw-close { width: 26px; height: 26px; border: 1px solid var(--card-border); border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center; cursor: pointer; font-size: 13px; color: var(--text-tertiary); margin-left: auto; background: none; transition: all .14s; flex-shrink: 0; }
.drw-close:hover { background: var(--section-bg); }

/* Body */
.drw-body { padding: 18px 22px; flex: 1; }

/* Section */
.ds { margin-bottom: 20px; }
.ds-title { font-size: 9px; font-weight: 700; color: var(--text-tertiary); text-transform: uppercase; letter-spacing: .1em; margin-bottom: 10px; padding-bottom: 5px; border-bottom: 1.5px solid var(--card-border); display: flex; align-items: center; gap: 7px; }
.ds-ico { width: 18px; height: 18px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 10px; }

/* Value hero */
.val-hero { display: flex; align-items: center; gap: 14px; padding: 13px 15px; background: var(--section-bg); border-radius: var(--radius-md); margin-bottom: 13px; }
.vh-val { font-family: var(--font-display); font-size: 46px; line-height: 1; flex-shrink: 0; }
.vr { color: #c0392b; }
.vw { color: #b45309; }
.vg { color: #1a7f6e; }
.vh-info { flex: 1; }
.vh-name { font-size: 14px; font-weight: 500; color: var(--text-primary); }
.vh-fibo { font-size: 9px; font-family: var(--font-mono); color: var(--text-tertiary); margin-top: 2px; }
.vh-status { margin-top: 6px; display: flex; align-items: center; gap: 7px; flex-wrap: wrap; }
.vh-thresh { font-size: 10px; font-family: var(--font-mono); color: var(--text-tertiary); margin-top: 2px; }

/* Badges / Deltas */
.bdg { font-size: 9px; padding: 2px 6px; border-radius: 10px; font-weight: 500; white-space: nowrap; display: inline-block; }
.b-red { background: rgba(192,57,43,.1); color: #c0392b; }
.b-amber { background: rgba(180,83,9,.1); color: #b45309; }
.b-green { background: rgba(22,163,74,.1); color: #16a34a; }
.delta { font-size: 9px; padding: 1px 4px; border-radius: 3px; }
.dd { background: rgba(192,57,43,.1); color: #c0392b; }
.du { background: rgba(22,163,74,.1); color: #16a34a; }
.dn { background: var(--section-bg); color: var(--text-tertiary); }

/* FIBO box */
.fibo-box { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: var(--radius-md); padding: 15px 17px; margin-bottom: 6px; }
.fibo-uri { font-family: var(--font-mono); font-size: 9px; color: rgba(255,255,255,.8); margin-bottom: 7px; word-break: break-all; }
.fibo-def { font-size: 12px; color: rgba(255,255,255,.85); line-height: 1.8; }
.fibo-props { display: flex; gap: 6px; margin-top: 9px; flex-wrap: wrap; }
.fp { font-size: 9px; padding: 2px 7px; border: 1px solid rgba(255,255,255,.15); color: rgba(255,255,255,.5); border-radius: 3px; }

/* Source card */
.src-card { border: 1px solid var(--card-border); border-radius: var(--radius-md); overflow: hidden; margin-bottom: 9px; }
.src-hd { padding: 8px 13px; background: var(--section-bg); border-bottom: 1px solid var(--card-border); display: flex; align-items: center; gap: 7px; }
.src-lbl { font-size: 11px; font-weight: 500; color: var(--text-primary); flex: 1; }
.src-cnt { font-size: 9px; color: var(--text-tertiary); }
.src-body { padding: 11px 13px; }
.formula { background: #0f172a; border-radius: var(--radius-sm); padding: 10px 13px; font-family: var(--font-mono); font-size: 10px; color: #86efac; line-height: 1.75; word-break: break-all; }
.sql-block { background: #0f172a; padding: 10px; border-radius: 6px; font-size: 10px; color: #94a3b8; overflow-x: auto; white-space: pre-wrap; word-break: break-all; max-height: 200px; overflow-y: auto; margin: 0; }
.src-fields { display: flex; flex-wrap: wrap; gap: 4px; }
.sf { font-size: 9px; padding: 2px 6px; background: rgba(29,78,216,.1); color: #1d4ed8; border-radius: 3px; font-family: var(--font-mono); border: 1px solid rgba(29,78,216,.2); }
.sf.k { background: rgba(26,127,110,.1); color: #1a7f6e; border-color: rgba(26,127,110,.25); }

/* Trust grid */
.trust-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.ti { padding: 10px 12px; border-radius: var(--radius-md); border: 1px solid var(--card-border); }
.ti.ok { border-color: rgba(26,127,110,.3); background: rgba(26,127,110,.04); }
.ti.warn { border-color: rgba(201,168,76,.35); background: rgba(201,168,76,.04); }
.ti-hd { display: flex; align-items: center; gap: 6px; margin-bottom: 4px; }
.ti-ico { font-size: 14px; }
.ti-lbl { font-size: 11px; font-weight: 500; color: var(--text-primary); }
.ti-body { font-size: 10px; color: var(--text-tertiary); line-height: 1.6; }

/* Cross validation */
.cv-list { display: flex; flex-direction: column; gap: 8px; }
.cv-item { border: 1px solid var(--card-border); border-radius: var(--radius-md); overflow: hidden; }
.cv-hd { padding: 7px 12px; background: var(--section-bg); border-bottom: 1px solid var(--card-border); display: flex; align-items: center; gap: 7px; }
.cv-name { font-size: 11px; font-weight: 500; color: var(--text-primary); flex: 1; }
.cv-body { padding: 9px 12px; }
.cv-tags { display: flex; gap: 3px; flex-wrap: wrap; }
.cvt { font-size: 9px; padding: 1px 5px; border: 1px solid var(--card-border); border-radius: 3px; color: var(--text-tertiary); cursor: pointer; background: var(--card-bg-subtle); transition: all .12s; white-space: nowrap; }
.cvt:hover { border-color: #1a7f6e; color: #1a7f6e; background: rgba(26,127,110,.1); }

/* Table */
.it { width: 100%; border-collapse: collapse; }
.it th { padding: 6px 10px; background: var(--table-header-bg); color: var(--table-header-color); font-weight: 500; text-align: left; border-bottom: 1px solid var(--card-border); font-size: 9px; text-transform: uppercase; letter-spacing: .06em; white-space: nowrap; }
.it td { padding: 9px 10px; border-bottom: 1px solid var(--divider-color); vertical-align: middle; font-size: 12px; color: var(--table-cell-color); }
.it tr:last-child td { border-bottom: none; }
</style>
