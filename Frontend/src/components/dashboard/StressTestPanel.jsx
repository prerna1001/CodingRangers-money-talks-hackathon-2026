import { useState } from 'react'
import { runStressTests } from '../../services/mockApi'
import './StressTestPanel.css'

const STATUS_META = {
  pass: { label: 'Pass', className: 'badge--success' },
  warn: { label: 'Warn', className: 'badge--warn' },
  fail: { label: 'Fail', className: 'badge--fail' },
}

export default function StressTestPanel() {
  const [checks, setChecks] = useState(null)
  const [running, setRunning] = useState(false)
  const [source, setSource] = useState(null)

  const handleRun = async () => {
    setRunning(true)
    const res = await runStressTests()
    setChecks(res.checks)
    setSource(res)
    setRunning(false)
  }

  const passCount = checks?.filter((c) => c.status === 'pass').length

  return (
    <div className="stress-panel">
      <div className="panel-heading">
        <div>
          <h3>Stress tests</h3>
          <p>Adversarial and messy-data scenarios run against this dataset</p>
        </div>
        <button type="button" className="btn btn--primary btn--sm" onClick={handleRun} disabled={running}>
          {running ? (
            <>
              <span className="spinner" /> Running…
            </>
          ) : checks ? (
            'Re-run stress tests'
          ) : (
            'Run stress tests'
          )}
        </button>
      </div>

      {source && (
        <span className="source-tag source-tag--block">
          <code>{source.method}</code> <code>{source.url}</code>
        </span>
      )}

      {!checks && !running && (
        <p className="stress-panel__empty">No stress tests run yet for this dataset.</p>
      )}

      {checks && (
        <>
          <p className="stress-panel__stat">
            <strong>{passCount}</strong> of {checks.length} checks passed clean
          </p>
          <div className="stress-grid">
            {checks.map((c) => (
              <div key={c.name} className="stress-check">
                <div className="stress-check__top">
                  <span className="stress-check__name">{c.name}</span>
                  <span className={`badge ${STATUS_META[c.status].className}`}>
                    {STATUS_META[c.status].label}
                  </span>
                </div>
                <p className="stress-check__detail">{c.detail}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
