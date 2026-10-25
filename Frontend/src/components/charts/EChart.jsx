import { useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { AriaComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'

// Only the pieces the dashboard uses are registered, which keeps ECharts'
// share of the bundle small. SVG renders crisp text at any zoom level.
echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, AriaComponent, SVGRenderer])

const TOKEN_NAMES = [
  'text', 'text-h', 'text-dim', 'border', 'border-strong', 'surface', 'surface-raised',
  'accent', 'up', 'danger', 'chart-up', 'chart-down', 'chart-total', 'chart-grid', 'sans',
]

// Charts draw with the same CSS tokens as the rest of the page, so they
// follow light/dark mode instead of carrying their own palette.
function readTokens() {
  const style = getComputedStyle(document.documentElement)
  return Object.fromEntries(
    TOKEN_NAMES.map((name) => [name.replace(/-(\w)/g, (_, c) => c.toUpperCase()), style.getPropertyValue(`--${name}`).trim()]),
  )
}

function useColorScheme() {
  const [scheme, setScheme] = useState(() => (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'))
  useEffect(() => {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (event) => setScheme(event.matches ? 'dark' : 'light')
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])
  return scheme
}

/**
 * <EChart build={(tokens) => option} onSelect={(dataIndex, params) => ...} />
 * `build` receives the resolved color tokens and returns an ECharts option.
 */
export default function EChart({ build, deps = [], onSelect, height = 320, label }) {
  const nodeRef = useRef(null)
  const chartRef = useRef(null)
  const onSelectRef = useRef(onSelect)
  const scheme = useColorScheme()

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
  }, [scheme, ...deps])

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
