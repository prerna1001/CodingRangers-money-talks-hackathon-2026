import { useState } from 'react'
import { runScenario } from '../../services/mockApi'
import './ScenarioSimulator.css'

const SCENARIOS = [
  { id: 'remove_top_customer', label: 'What if the top customer had not expanded?' },
  { id: 'normalize_refunds', label: 'What if refunds were normalized to trailing average?' },
  { id: 'exclude_onetime', label: 'What if we exclude one-time services engagements?' },
]

export default function ScenarioSimulator({ baselinePct }) {
  const [activeId, setActiveId] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleRun = async (scenario) => {
    setActiveId(scenario.id)
    setLoading(true)
    const res = await runScenario(scenario.id, baselinePct)
    setResult(res)
    setLoading(false)
  }

  return (
    <div className="scenario-panel">
      <div className="panel-heading">
        <div>
          <h2>Scenario simulator</h2>
          <p>Change one assumption and see how the period-over-period growth would move.</p>
        </div>
      </div>

      <div className="scenario-buttons">
        {SCENARIOS.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`scenario-btn ${activeId === s.id ? 'scenario-btn--active' : ''}`}
            aria-pressed={activeId === s.id}
            onClick={() => handleRun(s)}
            disabled={loading && activeId === s.id}
          >
            {loading && activeId === s.id ? 'Computing…' : s.label}
          </button>
        ))}
      </div>

      {result && !loading && (
        <div className="scenario-result">
          <div className="scenario-result__compare">
            <div>
              <span className="scenario-result__label">Actual growth</span>
              <span className="scenario-result__value">{result.baseline_pct >= 0 ? '+' : ''}{result.baseline_pct}%</span>
            </div>
            <span className="scenario-result__arrow" aria-hidden="true">becomes</span>
            <div>
              <span className="scenario-result__label">In this scenario</span>
              <span className="scenario-result__value scenario-result__value--sim">
                {result.adjusted_change_pct >= 0 ? '+' : ''}{result.adjusted_change_pct}%
              </span>
            </div>
          </div>
          <p className="scenario-result__note">{result.note}</p>
        </div>
      )}
    </div>
  )
}
