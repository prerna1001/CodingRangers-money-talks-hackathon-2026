import EChart from '../charts/EChart'
import { baseOption, categoryAxis, valueAxis } from '../charts/chartTheme'
import { compactMoney, ledgerChange, ledgerMoney } from '../../utils/format'
import './WaterfallChart.css'

function truncateLabel(label) {
  if (!label) return ''
  return label.length > 18 ? `${label.slice(0, 16)}…` : label
}

function displayName(step, drivers = [], duplicateNames = new Set()) {
  if (step.type === 'start' || step.type === 'end' || !duplicateNames.has(step.name)) return step.name
  const match = drivers.find((driver) => driver.driver === step.name && Number(driver.amount) === Number(step.value))
  if (!match) return step.name
  return `${match.account}: ${step.name}`
}

function buildWaterfallData(waterfall = [], drivers = []) {
  const counts = waterfall.reduce((acc, step) => {
    if (step.type !== 'start' && step.type !== 'end') acc[step.name] = (acc[step.name] || 0) + 1
    return acc
  }, {})
  const duplicateNames = new Set(Object.entries(counts).filter(([, count]) => count > 1).map(([name]) => name))

  let cumulative = 0
  return waterfall.map((step, index) => {
    const label = displayName(step, drivers, duplicateNames)
    const isTotal = step.type === 'start' || step.type === 'end'
    const delta = Number(step.value) || 0
    const start = isTotal ? 0 : cumulative
    cumulative = isTotal ? delta : cumulative + delta
    return { ...step, id: `${step.type}-${index}-${step.name}`, label, isTotal, start, end: cumulative, delta }
  })
}

// The driver row a waterfall bar stands for, so a click can open its evidence.
function driverForStep(step, drivers) {
  if (!step || step.isTotal) return null
  return (
    drivers.find((d) => d.driver === step.name && Number(d.amount) === Number(step.value)) ||
    drivers.find((d) => d.driver === step.name || `${d.driver} (${d.account})` === step.name) ||
    null
  )
}

export default function WaterfallChart({ waterfall, drivers = [], onSelectDriver }) {
  const data = buildWaterfallData(waterfall, drivers)
  const summary = data
    .map((d) => `${d.label} ${d.isTotal ? ledgerMoney(d.end) : ledgerChange(d.delta)}`)
    .join(', ')

  // Classic stacked-bar waterfall: an invisible "base" bar lifts each
  // visible bar to where the running total stood before that step.
  const build = (t) => ({
    ...baseOption(t),
    grid: { left: 8, right: 8, top: 36, bottom: 8, containLabel: true },
    tooltip: {
      ...baseOption(t).tooltip,
      trigger: 'item',
      formatter: (p) => {
        const d = data[p.dataIndex]
        if (!d) return ''
        const figure = d.isTotal ? ledgerMoney(d.end) : ledgerChange(d.delta)
        const hint = d.isTotal ? 'Period total' : `Running total ${ledgerMoney(d.end)}<br/><span style="color:${t.textDim}">Click to see the transactions</span>`
        return `<b>${d.label}</b><br/>${figure}<br/>${hint}`
      },
    },
    xAxis: categoryAxis(t, data.map((d) => d.label), {
      axisLabel: { color: t.text, fontSize: 12.5, fontWeight: 600, interval: 0, formatter: truncateLabel, width: 110, overflow: 'truncate' },
    }),
    yAxis: valueAxis(t, (v) => compactMoney(v)),
    series: [
      {
        name: 'base',
        type: 'bar',
        stack: 'waterfall',
        silent: true,
        itemStyle: { color: 'transparent' },
        emphasis: { disabled: true },
        tooltip: { show: false },
        data: data.map((d) => (d.isTotal ? 0 : Math.min(d.start, d.end))),
      },
      {
        name: 'value',
        type: 'bar',
        stack: 'waterfall',
        barMaxWidth: 96,
        barCategoryGap: '38%',
        data: data.map((d) => ({
          value: d.isTotal ? d.end : Math.abs(d.delta),
          itemStyle: {
            color: d.isTotal ? t.chartTotal : d.delta < 0 ? t.chartDown : t.chartUp,
            borderRadius: 2,
          },
          label: {
            show: true,
            position: 'top',
            color: d.delta < 0 && !d.isTotal ? t.danger : t.textH,
            fontWeight: 700,
            fontSize: 13,
            formatter: () => (d.isTotal ? compactMoney(d.end) : `${d.delta > 0 ? '+' : ''}${compactMoney(d.delta)}`),
          },
        })),
      },
    ],
  })

  return (
    <div className="waterfall-chart">
      <div className="panel-heading">
        <div>
          <h2>Variance waterfall</h2>
          <p>How revenue moved from the prior period to the current one. Select a bar to see its transactions.</p>
        </div>
        <span className="waterfall-chart__badge">{Math.max(data.length - 2, 0)} drivers</span>
      </div>

      <div className="waterfall-chart__frame">
        {data.length ? (
          <EChart
            build={build}
            deps={[waterfall, drivers]}
            height={340}
            label={`Variance waterfall: ${summary}`}
            onSelect={(index) => {
              const driver = driverForStep(data[index], drivers)
              if (driver) onSelectDriver?.(driver)
            }}
          />
        ) : (
          <div className="waterfall-chart__empty">This run returned no revenue bridge to chart.</div>
        )}
      </div>
      <div className="waterfall-chart__legend">
        <span><i style={{ background: 'var(--chart-total)' }} /> Period total</span>
        <span><i style={{ background: 'var(--chart-up)' }} /> Increase</span>
        <span><i style={{ background: 'var(--chart-down)' }} /> Decrease</span>
      </div>
    </div>
  )
}
