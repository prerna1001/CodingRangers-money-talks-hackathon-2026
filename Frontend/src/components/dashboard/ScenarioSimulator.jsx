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
          <h3>Scenario simulator</h3>
          <p>Ask "what if" — recomputed against this run's evidence</p>
        </div>
      </div>

      <div className="scenario-buttons">
        {SCENARIOS.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`btn btn--ghost btn--sm ${activeId === s.id ? 'scenario-btn--active' : ''}`}
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
              <span className="scenario-result__label">Actual</span>
              <span className="scenario-result__value">+{result.baseline_pct}%</span>
            </div>
            <span className="scenario-result__arrow">→</span>
            <div>
              <span className="scenario-result__label">Simulated</span>
              <span className="scenario-result__value scenario-result__value--sim">
                +{result.adjusted_change_pct}%
              </span>
            </div>
          </div>
          <p className="scenario-result__note">{result.note}</p>
        </div>
      )}
    </div>
  )
}
