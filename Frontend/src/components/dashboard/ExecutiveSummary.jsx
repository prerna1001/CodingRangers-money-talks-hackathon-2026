import { useState } from 'react'
import { generateVoiceBriefing } from '../../services/mockApi'
import './ExecutiveSummary.css'

function pct(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`
}

function money(value) {
  return `$${(Number(value) || 0).toLocaleString('en-US')}`
}

export default function ExecutiveSummary({ analysis }) {
  const [voice, setVoice] = useState(null)
  const [loadingVoice, setLoadingVoice] = useState(false)

  const drivers = Array.isArray(analysis.drivers) ? analysis.drivers : []
  const risks = Array.isArray(analysis.risks_or_caveats) ? analysis.risks_or_caveats : []
  const topDrivers = [...drivers]
    .sort((a, b) => Math.abs(Number(b.amount) || 0) - Math.abs(Number(a.amount) || 0))
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

      <h1 className="exec-summary__headline">{analysis.headline || 'Financial results analyzed'}</h1>
      <p className="exec-summary__body">{analysis.summary || 'The run completed, but no narrative summary was returned.'}</p>

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
          <span className="score-card__value">{money(analysis.periods.current.revenue)}</span>
        </div>
      </div>

      <div className="exec-summary__drivers">
        <h3>Top drivers</h3>
        <ul>
          {topDrivers.map((d) => (
            <li key={d.driver}>
              <span className={`driver-dot ${(Number(d.amount) || 0) >= 0 ? 'driver-dot--up' : 'driver-dot--down'}`} />
              <span className="exec-summary__driver-name">{d.driver || d.account || 'Unknown driver'}</span>
              <span className={`exec-summary__driver-amount ${(Number(d.amount) || 0) >= 0 ? 'text-up' : 'text-down'}`}>
                {(Number(d.amount) || 0) >= 0 ? '+' : ''}${Math.abs(Number(d.amount) || 0).toLocaleString('en-US')}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {risks.length > 0 && (
        <div className="exec-summary__caveats">
          <h3>Risks & caveats</h3>
          <ul>
            {risks.map((c) => (
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
