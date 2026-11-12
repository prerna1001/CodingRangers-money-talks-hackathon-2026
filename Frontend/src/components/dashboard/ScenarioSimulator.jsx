import { useMemo, useState } from 'react'
import { ledgerChange, ledgerMoney, toNumber } from '../../utils/format'
import './ScenarioSimulator.css'

const MAX_SCENARIOS = 4

function pct(value, base) {
  return base ? ((value - base) / Math.abs(base)) * 100 : 0
}

function formatPct(value) {
  const rounded = Math.round(value * 10) / 10
  return `${rounded >= 0 ? '+' : ''}${rounded}%`
}

// Scenarios come from this run's own revenue bridge: each one takes a single
// bridge line out of the change and recomputes period-over-period growth.
// The same arithmetic as the backend's /api/scenarios/simulate (exclude a
// driver's amount from the variance), done here so the result is instant
// and uses exactly the figures the bridge shows.
function buildScenarios(analysis) {
  const prior = toNumber(analysis.periods?.prior?.revenue)
  const current = toNumber(analysis.periods?.current?.revenue)
  const lines = (analysis.waterfall || [])
    .filter((step) => step.type !== 'start' && step.type !== 'end' && step.name !== 'Other')
    .map((step) => ({ name: step.name, amount: toNumber(step.value) }))
    .filter((line) => line.amount !== 0)
    .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount))
    .slice(0, MAX_SCENARIOS)

  return lines.map((line) => {
    const adjustedCurrent = current - line.amount
    return {
      id: line.name,
      label: line.amount > 0 ? `What if ${line.name} had not grown?` : `What if ${line.name} had not declined?`,
      line,
      prior,
      current,
      adjustedCurrent,
      baselinePct: pct(current, prior),
      adjustedPct: pct(adjustedCurrent, prior),
    }
  })
}

export default function ScenarioSimulator({ analysis }) {
  const scenarios = useMemo(() => buildScenarios(analysis), [analysis])
  const [activeId, setActiveId] = useState(null)
  const result = scenarios.find((s) => s.id === activeId) || null
  const priorLabel = analysis.periods?.prior?.label ?? 'the prior period'
  const currentLabel = analysis.periods?.current?.label ?? 'this period'

  return (
    <div className="scenario-panel">
      <div className="panel-heading">
        <div>
          <h2>Scenario simulator</h2>
          <p>Take one driver out of the change and see how period-over-period revenue growth would move.</p>
        </div>
      </div>

      {scenarios.length === 0 ? (
        <p className="scenario-panel__empty">
          This run has no revenue bridge lines to take out, so there is nothing to simulate.
        </p>
      ) : (
        <div className="scenario-buttons" role="group" aria-label="Scenarios">
          {scenarios.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`scenario-btn ${activeId === s.id ? 'scenario-btn--active' : ''}`}
              aria-pressed={activeId === s.id}
              onClick={() => setActiveId(s.id)}
            >
              {s.label}
            </button>
          ))}
        </div>
      )}

      {result && (
        <div className="scenario-result" key={result.id} aria-live="polite">
          <div className="scenario-result__compare">
            <div>
              <span className="scenario-result__label">Actual growth</span>
              <span className="scenario-result__value">{formatPct(result.baselinePct)}</span>
            </div>
            <span className="scenario-result__arrow" aria-hidden="true">becomes</span>
            <div>
              <span className="scenario-result__label">In this scenario</span>
              <span className="scenario-result__value scenario-result__value--sim">{formatPct(result.adjustedPct)}</span>
            </div>
          </div>
          <p className="scenario-result__note">
            Without {result.line.name}&rsquo;s {ledgerChange(result.line.amount)}, {currentLabel} revenue would be{' '}
            {ledgerMoney(result.adjustedCurrent)} instead of {ledgerMoney(result.current)}, against{' '}
            {ledgerMoney(result.prior)} in {priorLabel}.
          </p>
        </div>
      )}
    </div>
  )
}
