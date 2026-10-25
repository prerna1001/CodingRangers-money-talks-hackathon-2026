import { useState } from 'react'
import { generateVoiceBriefing } from '../../services/mockApi'
import Tick from '../Tick'
import { ledgerChange, ledgerMoney, percent, toNumber } from '../../utils/format'
import './ExecutiveSummary.css'

// Rebuilds the waterfall as a ledger footing: opening balance, each driver,
// closing balance. Falls back to the two period totals when the backend
// returned no waterfall.
function buildBridge(analysis) {
  const { prior, current } = analysis.periods
  const steps = analysis.waterfall.length
    ? analysis.waterfall
    : [
        { name: prior.label, value: prior.revenue, type: 'start' },
        { name: current.label, value: current.revenue, type: 'end' },
      ]
  const opening = steps.find((s) => s.type === 'start')
  const closing = steps.find((s) => s.type === 'end')
  const lines = steps.filter((s) => s.type !== 'start' && s.type !== 'end')
  const openingValue = toNumber(opening?.value ?? prior.revenue)
  const closingValue = toNumber(closing?.value ?? current.revenue)
  const footed = openingValue + lines.reduce((sum, s) => sum + toNumber(s.value), 0)
  return {
    opening: { label: opening?.name ?? prior.label, value: openingValue },
    closing: { label: closing?.name ?? current.label, value: closingValue },
    lines,
    difference: Math.round(closingValue - footed),
  }
}

function GroundingCheck({ analysis }) {
  if (!analysis.grounding_badge) return null
  const complete = toNumber(analysis.grounding_rate) >= 1
  return (
    <li className={`exec-check ${complete ? '' : 'exec-check--warn'}`}>
      {complete ? <Tick /> : <span className="exec-check__mark" aria-hidden="true">!</span>}
      <span>
        <b>{analysis.grounding_badge}</b> in this explanation against source data
      </span>
    </li>
  )
}

export default function ExecutiveSummary({ analysis }) {
  const [voice, setVoice] = useState(null)
  const [loadingVoice, setLoadingVoice] = useState(false)

  const risks = Array.isArray(analysis.risks_or_caveats) ? analysis.risks_or_caveats : []
  const followUps = Array.isArray(analysis.follow_up_questions) ? analysis.follow_up_questions : []
  const bridge = buildBridge(analysis)
  const netChange = bridge.closing.value - bridge.opening.value
  const netPct = bridge.opening.value ? netChange / Math.abs(bridge.opening.value) : 0

  const handleVoice = async () => {
    setLoadingVoice(true)
    const res = await generateVoiceBriefing(analysis.run_id, analysis.headline)
    setVoice(res)
    setLoadingVoice(false)
  }

  return (
    <div className="exec-summary">
      <article className="exec-summary__memo">
        <h2 className="exec-summary__headline">{analysis.headline || 'Financial results analyzed'}</h2>
        <p className="exec-summary__body">
          {analysis.summary || 'The run finished without a written explanation. The bridge and drivers are still computed from your data.'}
        </p>

        <ul className="exec-checks" aria-label="Checks on this explanation">
          <GroundingCheck analysis={analysis} />
          <li className="exec-check exec-check--plain">
            <span className="exec-check__figure">{percent(analysis.confidence)}</span>
            <span>confidence in the driver attribution</span>
          </li>
          <li className="exec-check exec-check--plain">
            <span className="exec-check__figure">{percent(analysis.data_quality_score)}</span>
            <span>data quality score from the pre-analysis checks</span>
          </li>
        </ul>

        {risks.length > 0 && (
          <section className="exec-summary__section">
            <h3>Risks and caveats</h3>
            <ul className="exec-summary__list">
              {risks.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </section>
        )}

        {followUps.length > 0 && (
          <section className="exec-summary__section">
            <h3>Worth asking next</h3>
            <ul className="exec-summary__list">
              {followUps.map((q) => (
                <li key={q}>{q}</li>
              ))}
            </ul>
          </section>
        )}

        <div className="exec-summary__voice">
          <button type="button" className="btn btn--ghost btn--sm" onClick={handleVoice} disabled={loadingVoice}>
            {loadingVoice ? <><span className="spinner" /> Writing briefing…</> : voice ? 'Rewrite voice briefing' : 'Create CFO voice briefing'}
          </button>
          {voice && (
            <div className="voice-panel" aria-live="polite">
              <p className="voice-panel__meta">Briefing script, {voice.duration_sec} seconds read aloud</p>
              <p className="voice-panel__script">{voice.script}</p>
            </div>
          )}
        </div>
      </article>

      <aside className="bridge" aria-labelledby="bridge-title">
        <div className="bridge__head">
          <h3 id="bridge-title">Revenue bridge</h3>
          <p className={netChange >= 0 ? 'text-up' : 'text-down'}>
            {ledgerChange(netChange)} ({netPct >= 0 ? '+' : ''}{Math.round(netPct * 1000) / 10}%)
          </p>
        </div>

        <table className="bridge__table">
          <caption className="visually-hidden">
            Revenue bridge from {bridge.opening.label} to {bridge.closing.label}
          </caption>
          <tbody>
            <tr className="bridge__row bridge__row--balance">
              <th scope="row">{bridge.opening.label} revenue</th>
              <td>{ledgerMoney(bridge.opening.value)}</td>
              <td className="bridge__tick" />
            </tr>
            {bridge.lines.map((line, index) => {
              const value = toNumber(line.value)
              const unattributed = line.name === 'Other'
              return (
                <tr key={`${line.name}-${index}`} className="bridge__row">
                  <th scope="row">
                    {unattributed ? 'Not attributed to a named driver' : line.name}
                  </th>
                  <td className={value < 0 ? 'text-down' : ''}>{ledgerChange(value)}</td>
                  <td className="bridge__tick">
                    {!unattributed && (
                      <Tick title="Computed from source transactions" style={{ '--i': index }} />
                    )}
                  </td>
                </tr>
              )
            })}
            <tr className="bridge__row bridge__row--total">
              <th scope="row">{bridge.closing.label} revenue</th>
              <td>{ledgerMoney(bridge.closing.value)}</td>
              <td className="bridge__tick" />
            </tr>
          </tbody>
        </table>

        {bridge.lines.length > 0 && (
          <p className={`bridge__foot ${bridge.difference ? 'bridge__foot--off' : ''}`}>
            {bridge.difference === 0 ? (
              <><Tick className="bridge__foot-tick" style={{ '--i': bridge.lines.length }} /> Lines add up to {bridge.closing.label} revenue.</>
            ) : (
              <>Lines are {ledgerMoney(Math.abs(bridge.difference))} {bridge.difference > 0 ? 'short of' : 'over'} {bridge.closing.label} revenue.</>
            )}
          </p>
        )}
        <p className="bridge__legend">
          <Tick /> Computed from the source transactions, not written by the model.
        </p>
      </aside>
    </div>
  )
}
