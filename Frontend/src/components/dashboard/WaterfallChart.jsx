import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import './WaterfallChart.css'

const COLORS = {
  start: '#8890a0',
  end: '#0f9d70',
  increase: '#0f9d70',
  decrease: '#e0433d',
}

function formatCurrency(value) {
  return `$${Math.round(value / 1000)}k`
}

function buildWaterfallData(waterfall) {
  let cumulative = 0
  return waterfall.map((step) => {
    if (step.type === 'start' || step.type === 'end') {
      cumulative = step.type === 'start' ? step.value : cumulative
      return { ...step, base: 0, display: step.value }
    }
    const base = step.value >= 0 ? cumulative : cumulative + step.value
    cumulative += step.value
    return { ...step, base, display: Math.abs(step.value) }
  })
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const point = payload.find((p) => p.dataKey === 'display')?.payload
  if (!point) return null
  return (
    <div className="waterfall-tooltip">
      <strong>{label}</strong>
      <span>
        {point.type === 'increase' && '+'}
        {point.type === 'decrease' && '−'}${Math.abs(point.value).toLocaleString()}
      </span>
    </div>
  )
}

export default function WaterfallChart({ waterfall }) {
  const data = buildWaterfallData(waterfall)

  return (
    <div className="waterfall-chart">
      <h3>Variance waterfall</h3>
      <p className="waterfall-chart__subtitle">How prior-period revenue became current-period revenue</p>
      <ResponsiveContainer width="100%" height={260}>
        <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <XAxis
            dataKey="name"
            tick={{ fontSize: 11, fill: 'var(--text-dim)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
            interval={0}
            angle={-12}
            textAnchor="end"
            height={50}
          />
          <YAxis
            tickFormatter={formatCurrency}
            tick={{ fontSize: 11, fill: 'var(--text-dim)' }}
            axisLine={false}
            tickLine={false}
            width={48}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--accent-bg)' }} />
          <Bar dataKey="base" stackId="wf" fill="transparent" isAnimationActive={false} />
          <Bar dataKey="display" stackId="wf" radius={[4, 4, 0, 0]} isAnimationActive={false}>
            {data.map((entry) => (
              <Cell key={entry.name} fill={COLORS[entry.type]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="waterfall-chart__legend">
        <span><i style={{ background: COLORS.start }} /> Baseline</span>
        <span><i style={{ background: COLORS.increase }} /> Increase</span>
        <span><i style={{ background: COLORS.decrease }} /> Decrease</span>
      </div>
    </div>
  )
}
