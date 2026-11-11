import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { AriaComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

// Only the pieces the dashboard uses are registered, which keeps ECharts'
// share of the bundle small. SVG renders crisp text at any zoom level.
echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, AriaComponent, SVGRenderer])

const COLOR_TOKENS = [
  'text', 'text-h', 'text-dim', 'border', 'border-strong', 'surface', 'surface-raised',
  'accent', 'up', 'danger', 'chart-up', 'chart-down', 'chart-total', 'chart-carry', 'chart-grid', 'chart-line',
]
const FONT_TOKENS = ['sans', 'mono']

const camel = (name) => name.replace(/-(\w)/g, (_, c) => c.toUpperCase())

// The tokens are written in oklch, which ECharts' colour parser does not
// read. Painting one pixel and reading it back gives the same colour as rgb.
let probe = null
function toRgb(value) {
  if (!value) return value
  if (!probe) {
    const canvas = document.createElement('canvas')
    canvas.width = 1
    canvas.height = 1
    probe = canvas.getContext('2d', { willReadFrequently: true })
  }
  if (!probe) return value
  probe.clearRect(0, 0, 1, 1)
  probe.fillStyle = value
  probe.fillRect(0, 0, 1, 1)
  const [r, g, b, a] = probe.getImageData(0, 0, 1, 1).data
  return a === 255 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${(a / 255).toFixed(3)})`
}

// Charts draw with the same CSS tokens as the rest of the page instead of
// carrying their own palette.
function readTokens() {
  const style = getComputedStyle(document.documentElement)
  const read = (name) => style.getPropertyValue(`--${name}`).trim()
  return {
    ...Object.fromEntries(COLOR_TOKENS.map((name) => [camel(name), toRgb(read(name))])),
    ...Object.fromEntries(FONT_TOKENS.map((name) => [camel(name), read(name)])),
  }
}

/**
 * <EChart build={(tokens) => option} onSelect={(dataIndex, params) => ...} />
 * `build` receives the resolved color tokens and returns an ECharts option.
 */
export default function EChart({ build, deps = [], onSelect, height = 320, label }) {
  const nodeRef = useRef(null)
  const chartRef = useRef(null)
  const onSelectRef = useRef(onSelect)

  useEffect(() => {
    onSelectRef.current = onSelect
  }, [onSelect])

  useEffect(() => {
    const chart = echarts.init(nodeRef.current, null, { renderer: 'svg' })
    chartRef.current = chart
    chart.on('click', (params) => onSelectRef.current?.(params.dataIndex, params))
    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(nodeRef.current)
    return () => {
      observer.disconnect()
      chart.dispose()
      chartRef.current = null
    }
  }, [])

  useEffect(() => {
    chartRef.current?.setOption(build(readTokens()), { notMerge: true })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return (
    <div
      ref={nodeRef}
      className="echart"
      style={{ height, cursor: onSelect ? 'pointer' : undefined }}
      role="img"
      aria-label={label}
    />
  )
}
