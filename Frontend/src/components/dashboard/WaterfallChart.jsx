import './WaterfallChart.css'

const COLORS = {
  start: 'var(--chart-baseline)',
  end: 'var(--chart-end)',
  increase: 'var(--chart-up)',
  decrease: 'var(--chart-down)',
}

const WIDTH = 920
const HEIGHT = 330
const PLOT = {
  left: 70,
  right: 26,
  top: 28,
  bottom: 82,
}

function formatMoney(value, compact = true) {
  const numeric = Number(value) || 0
  const abs = Math.abs(numeric)
  const sign = numeric > 0 ? '+' : numeric < 0 ? '-' : ''
  if (compact && abs >= 1000) return `${sign}$${(abs / 1000).toFixed(abs >= 10000 ? 0 : 1)}K`
  return `${sign}$${abs.toLocaleString('en-US')}`
}

function truncateLabel(label) {
  if (!label) return ''
  if (/^\d{4}-\d{2}$/.test(label)) return label
  return label.length > 18 ? `${label.slice(0, 16)}...` : label
}

function AxisLabel({ x, y, label }) {
  if (label.includes(': ')) {
    const [account, counterparty] = label.split(': ')
    return (
      <text x={x} y={y - 5} textAnchor="middle" className="waterfall-chart__label">
        <tspan x={x}>{truncateLabel(account)}</tspan>
        <tspan x={x} dy="15" className="waterfall-chart__label-muted">{truncateLabel(counterparty)}</tspan>
      </text>
    )
  }
  return (
    <text x={x} y={y} textAnchor="middle" className="waterfall-chart__label">
      {truncateLabel(label)}
    </text>
  )
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
    if (step.type === 'start' || step.type === 'end') {
      const value = Number(step.value) || 0
      cumulative = value
      return {
        ...step,
        id: `${step.type}-${index}-${step.name}`,
        label,
        start: 0,
        end: value,
        delta: value,
      }
    }
    const start = cumulative
    const delta = Number(step.value) || 0
    cumulative += delta
    return {
      ...step,
      id: `${step.type}-${index}-${step.name}`,
      label,
      start,
      end: cumulative,
      delta,
    }
  })
}

function scaleFor(data) {
  if (!data.length) return { min: 0, max: 1 }
  const values = data.flatMap((d) => [d.start, d.end, 0])
  const max = Math.max(...values)
  const min = Math.min(...values)
  const pad = Math.max((max - min) * 0.12, 1)
  return { min: Math.min(0, min - pad), max: max + pad }
}

export default function WaterfallChart({ waterfall, drivers = [] }) {
  const data = buildWaterfallData(waterfall, drivers)
  const { min, max } = scaleFor(data)
  const plotWidth = WIDTH - PLOT.left - PLOT.right
  const plotHeight = HEIGHT - PLOT.top - PLOT.bottom
  const stepWidth = plotWidth / Math.max(data.length, 1)
  const barWidth = Math.min(112, Math.max(52, stepWidth * 0.58))
  const y = (value) => PLOT.top + ((max - value) / (max - min)) * plotHeight
  const zeroY = y(0)
  const ticks = Array.from({ length: 5 }, (_, i) => min + ((max - min) * i) / 4)

  return (
    <div className="waterfall-chart">
      <div className="panel-heading">
        <div>
          <h3>Variance Waterfall</h3>
          <p>How prior-period revenue bridged to current-period revenue</p>
        </div>
        <span className="waterfall-chart__badge">{Math.max(data.length - 2, 0)} drivers</span>
      </div>

      <div className="waterfall-chart__frame">
        {!data.length && (
          <div className="waterfall-chart__empty">
            No waterfall data returned for this run.
          </div>
        )}
        <svg className="waterfall-chart__svg" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Variance waterfall chart">
          <defs>
            <linearGradient id="waterfallBaseline" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="rgba(164, 174, 193, 0.96)" />
              <stop offset="100%" stopColor="rgba(119, 130, 151, 0.9)" />
            </linearGradient>
            <linearGradient id="waterfallUp" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="rgba(44, 211, 157, 0.98)" />
              <stop offset="100%" stopColor="rgba(16, 154, 112, 0.96)" />
            </linearGradient>
            <linearGradient id="waterfallDown" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="rgba(255, 116, 96, 0.98)" />
              <stop offset="100%" stopColor="rgba(221, 71, 64, 0.96)" />
            </linearGradient>
          </defs>

          {ticks.map((tick) => (
            <g key={tick}>
              <line x1={PLOT.left} x2={WIDTH - PLOT.right} y1={y(tick)} y2={y(tick)} className="waterfall-chart__grid" />
              <text x={PLOT.left - 14} y={y(tick) + 4} textAnchor="end" className="waterfall-chart__axis">
                {formatMoney(tick, true).replace('+', '')}
              </text>
            </g>
          ))}
          <line x1={PLOT.left} x2={WIDTH - PLOT.right} y1={zeroY} y2={zeroY} className="waterfall-chart__zero" />

          {data.slice(0, -1).map((point, index) => {
            const nextX = PLOT.left + (index + 1) * stepWidth
            const currentX = PLOT.left + index * stepWidth + stepWidth / 2 + barWidth / 2
            return (
              <line
                key={`connector-${point.id}`}
                x1={currentX}
                x2={nextX - barWidth / 2}
                y1={y(point.end)}
                y2={y(point.end)}
                className="waterfall-chart__connector"
              />
            )
          })}

          {data.map((point, index) => {
            const x = PLOT.left + index * stepWidth + (stepWidth - barWidth) / 2
            const top = Math.min(y(point.start), y(point.end))
            const bottom = Math.max(y(point.start), y(point.end))
            const height = Math.max(bottom - top, 3)
            const isTotal = point.type === 'start' || point.type === 'end'
            const fill = point.type === 'start' ? 'url(#waterfallBaseline)' : point.type === 'end' || point.type === 'increase' ? 'url(#waterfallUp)' : 'url(#waterfallDown)'
            const labelY = top < 44 ? bottom + 18 : top - 10
            return (
              <g key={point.id} className="waterfall-chart__bar-group">
                <rect x={x} y={top} width={barWidth} height={height} rx="5" fill={fill} />
                <text x={x + barWidth / 2} y={labelY} textAnchor="middle" className={`waterfall-chart__value ${point.delta < 0 ? 'waterfall-chart__value--down' : ''}`}>
                  {isTotal ? formatMoney(point.end, true).replace('+', '') : formatMoney(point.delta, true)}
                </text>
                <AxisLabel x={x + barWidth / 2} y={HEIGHT - 42} label={point.label} />
              </g>
            )
          })}
        </svg>
      </div>
      <div className="waterfall-chart__legend">
        <span><i style={{ background: COLORS.start }} /> Baseline</span>
        <span><i style={{ background: COLORS.increase }} /> Increase</span>
        <span><i style={{ background: COLORS.decrease }} /> Decrease</span>
      </div>
    </div>
  )
}
