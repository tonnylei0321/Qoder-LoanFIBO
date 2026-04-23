<template>
  <div ref="chartEl" :style="{ width: '100%', height: height + 'px' }"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  DataZoomComponent,
  MarkLineComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([
  LineChart, TooltipComponent, LegendComponent, GridComponent,
  DataZoomComponent, MarkLineComponent, CanvasRenderer,
])

interface HistoryPoint {
  calc_date: string
  value?: number
  value_prev?: number
  change_pct?: number
  alert_level: string
}

const props = withDefaults(defineProps<{
  data: HistoryPoint[]
  height?: number
  indicatorName?: string
  warningThreshold?: number
  alertThreshold?: number
}>(), {
  height: 350,
  indicatorName: '',
  warningThreshold: undefined,
  alertThreshold: undefined,
})

const chartEl = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

function renderChart() {
  if (!chart || !props.data.length) return

  const dates = props.data.map(d => d.calc_date)
  const values = props.data.map(d => d.value ?? null)
  const prevValues = props.data.map(d => d.value_prev ?? null)

  const markLineData: any[] = []
  if (props.warningThreshold != null) {
    markLineData.push({
      yAxis: props.warningThreshold,
      name: 'warning',
      lineStyle: { color: '#E6A23C', type: 'dashed' },
      label: { formatter: 'warning: {c}', position: 'insideEndTop' },
    })
  }
  if (props.alertThreshold != null) {
    markLineData.push({
      yAxis: props.alertThreshold,
      name: 'alert',
      lineStyle: { color: '#F56C6C', type: 'dashed' },
      label: { formatter: 'alert: {c}', position: 'insideEndTop' },
    })
  }

  const series: any[] = [
    {
      name: 'current',
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      itemStyle: { color: '#409EFF' },
      markLine: markLineData.length ? { data: markLineData, silent: true } : undefined,
    },
  ]

  if (prevValues.some(v => v !== null)) {
    series.push({
      name: 'previous',
      type: 'line',
      data: prevValues,
      smooth: true,
      symbol: 'diamond',
      symbolSize: 5,
      lineStyle: { type: 'dashed' },
      itemStyle: { color: '#909399' },
    })
  }

  chart.setOption({
    title: { show: false },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        let html = `<b>${params[0]?.axisValue}</b><br/>`
        for (const p of params) {
          const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${p.color}"></span>`
          html += `${dot} ${p.seriesName}: <b>${p.value ?? '-'}</b><br/>`
        }
        return html
      },
    },
    legend: { data: series.map(s => s.name), bottom: 0 },
    grid: { left: 50, right: 20, top: 20, bottom: 50 },
    xAxis: { type: 'category', data: dates, boundaryGap: false },
    yAxis: { type: 'value' },
    dataZoom: [{ type: 'inside' }],
    series,
  }, true)
}

watch(() => props.data, renderChart, { deep: true })

onMounted(() => {
  if (chartEl.value) {
    chart = echarts.init(chartEl.value)
    renderChart()
  }
})

onBeforeUnmount(() => {
  chart?.dispose()
})
</script>
