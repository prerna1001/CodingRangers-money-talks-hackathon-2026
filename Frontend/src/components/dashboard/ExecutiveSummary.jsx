import { useState } from 'react'
import { generateVoiceBriefing } from '../../services/mockApi'
import './ExecutiveSummary.css'

function pct(value) {
  return `${Math.round(value * 100)}%`
}

export default function ExecutiveSummary({ analysis }) {
  const [voice, setVoice] = useState(null)
  const [loadingVoice, setLoadingVoice] = useState(false)

  const topDrivers = [...analysis.drivers]
    .sort((a, b) => Math.abs(b.amount) - Math.abs(a.amount))
    .slice(0, 3)

  const handleVoice = async () => {
    setLoadingVoice(true)
    const res = await generateVoiceBriefing(analysis.run_id, analysis.headline)
    setVoice(res)
    setLoadingVoice(false)
  }

  return (
    <div className="exec-summary">
      <div className="exec-summary__top">
        <div className="exec-summary__periods">
          <span>{analysis.periods.prior.label}</span>
          <span className="exec-summary__arrow">→</span>
          <span>{analysis.periods.current.label}</span>
        </div>
        <button type="button" className="btn btn--ghost btn--sm" onClick={handleVoice} disabled={loadingVoice}>
          {loadingVoice ? 'Generating…' : voice ? 'Regenerate voice briefing' : '🔊 Generate CFO voice briefing'}
        </button>
      </div>

      <h1 className="exec-summary__headline">{analysis.headline}</h1>
      <p className="exec-summary__body">{analysis.summary}</p>

      <div className="exec-summary__scores">
        <div className="score-card">
          <span className="score-card__label">Confidence</span>
          <span className="score-card__value">{pct(analysis.confidence)}</span>
        </div>
        <div className="score-card">
          <span className="score-card__label">Data quality</span>
          <span className="score-card__value">{pct(analysis.data_quality_score)}</span>
        </div>
        <div className="score-card">
          <span className="score-card__label">Revenue ({analysis.periods.current.label})</span>
          <span className="score-card__value">${analysis.periods.current.revenue.toLocaleString()}</span>
        </div>
      </div>

      <div className="exec-summary__drivers">
        <h3>Top drivers</h3>
        <ul>
          {topDrivers.map((d) => (
            <li key={d.driver}>
              <span className={`driver-dot ${d.amount >= 0 ? 'driver-dot--up' : 'driver-dot--down'}`} />
              <span className="exec-summary__driver-name">{d.driver}</span>
              <span className={`exec-summary__driver-amount ${d.amount >= 0 ? 'text-up' : 'text-down'}`}>
                {d.amount >= 0 ? '+' : ''}${d.amount.toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {analysis.risks_or_caveats?.length > 0 && (
        <div className="exec-summary__caveats">
          <h3>Risks & caveats</h3>
          <ul>
            {analysis.risks_or_caveats.map((c) => (
              <li key={c}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {voice && (
        <div className="voice-panel">
          <div className="voice-panel__header">
            <span className="badge badge--success">audio ready</span>
            <span>{voice.duration_sec}s · executive tone</span>
          </div>
          <p className="voice-panel__script">{voice.script}</p>
        </div>
      )}
    </div>
  )
}
