<template>
  <div ref="chartEl" :style="{ width: '100%', height: height + 'px' }"></div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts/core'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([RadarChart, TooltipComponent, LegendComponent, CanvasRenderer])

interface RadarItem {
  name: string
  max?: number
  value: number
}

const props = withDefaults(defineProps<{
  items: RadarItem[]
  height?: number
  color?: string
}>(), {
  height: 320,
  color: '#667eea',
})

const chartEl = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function buildOption() {
  const indicators = props.items.map(i => ({ name: i.name, max: i.max ?? 100 }))
  const values = props.items.map(i => i.value)

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15,23,42,0.9)',
      borderColor: 'rgba(102,126,234,0.3)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
      formatter: (params: any) => {
        const vals = params.value
        return props.items
          .map((item, i) => `<b>${item.name}</b>: ${vals[i]?.toFixed(1)}`)
          .join('<br/>')
      },
    },
    radar: {
      center: ['50%', '50%'],
      radius: '68%',
      startAngle: 90,
      splitNumber: 5,
      shape: 'polygon',
      axisName: {
        color: '#94a3b8',
        fontSize: 11,
        fontFamily: 'Fira Sans, sans-serif',
        formatter: (name: string, indicator: any) => {
          // Find score for this dimension
          const item = props.items.find(i => i.name === name)
          return `{name|${name}}\n{score|${item?.value?.toFixed(1) ?? '-'}}`
        },
        rich: {
          name: { color: '#94a3b8', fontSize: 11, lineHeight: 16 },
          score: { color: '#e2e8f0', fontSize: 13, fontWeight: 'bold', lineHeight: 18 },
        },
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(102,126,234,0.03)', 'rgba(102,126,234,0.06)'],
        },
      },
      axisLine: { lineStyle: { color: 'rgba(148,163,184,0.2)' } },
      splitLine: { lineStyle: { color: 'rgba(148,163,184,0.15)', width: 1 } },
      indicator: indicators,
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: values,
            name: '维度得分',
            symbol: 'circle',
            symbolSize: 5,
            lineStyle: {
              color: props.color,
              width: 2,
            },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: props.color + 'cc' },
                { offset: 1, color: props.color + '22' },
              ]),
            },
            itemStyle: {
              color: props.color,
              borderColor: '#fff',
              borderWidth: 1.5,
            },
          },
        ],
      },
    ],
  }
}

function initChart() {
  if (!chartEl.value) return
  chart = echarts.init(chartEl.value, null, { renderer: 'canvas' })
  chart.setOption(buildOption())
}

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  chart?.dispose()
  window.removeEventListener('resize', handleResize)
})

function handleResize() {
  chart?.resize()
}

watch(() => props.items, () => {
  if (chart) {
    chart.setOption(buildOption(), true)
  }
}, { deep: true })
</script>
