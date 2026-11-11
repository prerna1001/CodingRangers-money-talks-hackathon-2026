import EChart from '../charts/EChart'
import { baseOption, categoryAxis, valueAxis } from '../charts/chartTheme'
import { compactMoney, ledgerChange, ledgerMoney, toNumber } from '../../utils/format'
import './DriverCharts.css'

const MAX_ROWS = 8

// ECharts media query: swap in `narrow` overrides when the chart itself is
// under 480px wide (phones, or the half-width column on small laptops).
function withNarrow(option, narrow) {
  return { baseOption: option, media: [{ query: { maxWidth: 480 }, option: narrow }] }
}

// Prior vs current, one pair of bars per driver: shows the size of each
// base, not just the change, so a +60% on a tiny account reads as tiny.
function PriorCurrentChart({ drivers, periods, onSelectDriver }) {
  const rows = drivers.slice(0, MAX_ROWS).reverse()
  const names = rows.map((d) => d.driver)
  const build = (t) => withNarrow({
    ...baseOption(t),
    grid: { left: 4, right: 16, top: 30, bottom: 4, containLabel: true },
    legend: {
      top: 0,
      left: 0,
      itemWidth: 10,
      itemHeight: 10,
      itemGap: 18,
      textStyle: { color: t.textDim, fontSize: 12.5 },
    },
    tooltip: {
      ...baseOption(t).tooltip,
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: t.chartGrid } },
      formatter: (items) => {
        const d = rows[items[0].dataIndex]
        return `<b>${d.driver}</b> <span style="color:${t.textDim}">${d.account}</span><br/>${periods.prior}: ${ledgerMoney(d.prior)}<br/>${periods.current}: ${ledgerMoney(d.current)}<br/>Change: ${ledgerChange(d.amount)}`
      },
    },
    xAxis: valueAxis(t, (v) => compactMoney(v)),
    yAxis: categoryAxis(t, names, { axisLabel: { color: t.text, fontSize: 12.5, fontWeight: 600, width: 120, overflow: 'truncate' } }),
    series: [
      {
        name: periods.prior,
        type: 'bar',
        barGap: '15%',
        barMaxWidth: 14,
        itemStyle: { color: t.borderStrong, borderRadius: 2 },
        data: rows.map((d) => toNumber(d.prior)),
      },
      {
        name: periods.current,
        type: 'bar',
        barMaxWidth: 14,
        itemStyle: { color: t.chartTotal, borderRadius: 2 },
        data: rows.map((d) => toNumber(d.current)),
      },
    ],
  }, { xAxis: { splitNumber: 3 } })

  return (
    <figure className="driver-chart">
      <figcaption>
        <h3>Prior and current, by driver</h3>
        <p>How big each driver was before and after the change</p>
      </figcaption>
      <EChart
        build={build}
        deps={[drivers, periods.prior, periods.current]}
        height={Math.max(220, rows.length * 38 + 50)}
        label={`Prior and current by driver: ${rows.slice().reverse().map((d) => `${d.driver} ${ledgerMoney(d.prior)} to ${ledgerMoney(d.current)}`).join(', ')}`}
        onSelect={(index) => onSelectDriver?.(rows[index])}
      />
    </figure>
  )
}

// Pareto: each driver's share of the gross movement, largest first, with the
// running total. Answers "how concentrated is this change?" at a glance.
function ConcentrationChart({ drivers, onSelectDriver }) {
  const rows = [...drivers].sort((a, b) => Math.abs(toNumber(b.amount)) - Math.abs(toNumber(a.amount))).slice(0, MAX_ROWS)
  const gross = drivers.reduce((sum, d) => sum + Math.abs(toNumber(d.amount)), 0) || 1
  const shares = rows.map((d) => (Math.abs(toNumber(d.amount)) / gross) * 100)
  const cumulative = shares.map((_, i) => shares.slice(0, i + 1).reduce((sum, s) => sum + s, 0))
  const topThree = cumulative[Math.min(2, cumulative.length - 1)] ?? 0

  const build = (t) => withNarrow({
    ...baseOption(t),
    grid: { left: 4, right: 4, top: 30, bottom: 4, containLabel: true },
    tooltip: {
      ...baseOption(t).tooltip,
      trigger: 'axis',
      axisPointer: { type: 'shadow', shadowStyle: { color: t.chartGrid } },
      formatter: (items) => {
        const i = items[0].dataIndex
        const d = rows[i]
        return `<b>${d.driver}</b><br/>${ledgerChange(d.amount)}, ${Math.round(shares[i])}% of all movement<br/>Top ${i + 1} together: ${Math.round(cumulative[i])}%`
      },
    },
    xAxis: categoryAxis(t, rows.map((d) => d.driver), {
      axisLabel: { color: t.text, fontSize: 12, fontWeight: 600, interval: 0, width: 84, overflow: 'truncate' },
    }),
    yAxis: valueAxis(t, (v) => `${v}%`, { max: 100, interval: 25 }),
    series: [
      {
        type: 'bar',
        barMaxWidth: 40,
        data: rows.map((d, i) => ({
          value: Math.round(shares[i] * 10) / 10,
          itemStyle: { color: toNumber(d.amount) < 0 ? t.chartDown : t.chartUp, borderRadius: 2 },
        })),
      },
      {
        type: 'line',
        data: cumulative.map((v) => Math.round(v * 10) / 10),
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: { color: t.accent, width: 2 },
        itemStyle: { color: t.accent },
        label: { show: true, position: 'top', color: t.accent, fontWeight: 700, fontSize: 12, formatter: ({ value }) => `${Math.round(value)}%` },
      },
    ],
  }, { xAxis: { axisLabel: { rotate: 35, width: 70 } } })

  return (
    <figure className="driver-chart">
      <figcaption>
        <h3>How concentrated the change is</h3>
        <p>
          {rows.length >= 3
            ? `The top three drivers account for ${Math.round(topThree)}% of all movement`
            : 'Each driver’s share of all movement, with the running total'}
        </p>
      </figcaption>
      <EChart
        build={build}
        deps={[drivers]}
        height={Math.max(220, rows.length * 38 + 50)}
        label={`Share of movement by driver: ${rows.map((d, i) => `${d.driver} ${Math.round(shares[i])}%`).join(', ')}`}
        onSelect={(index) => onSelectDriver?.(rows[index])}
      />
    </figure>
  )
}

export default function DriverCharts({ drivers, periods, onSelectDriver }) {
  if (!drivers.length) return null
  return (
    <div className="driver-charts">
      <PriorCurrentChart drivers={drivers} periods={periods} onSelectDriver={onSelectDriver} />
      <ConcentrationChart drivers={drivers} onSelectDriver={onSelectDriver} />
    </div>
  )
}
