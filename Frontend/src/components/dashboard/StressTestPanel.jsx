import { useState } from 'react'
import { runStressTests } from '../../services/mockApi'
import './StressTestPanel.css'

const STATUS_META = {
  pass: { label: 'Pass', className: 'badge--success' },
  warn: { label: 'Warning', className: 'badge--warn' },
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
          <h2>Stress tests</h2>
          <p>Messy data and hostile inputs thrown at this dataset, to show where the explanation holds and where it bends</p>
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
        <p className="stress-panel__empty">No stress tests yet. Run them to check duplicates, injected text, reconciliation and outliers.</p>
      )}

      {checks && (
        <>
          <p className="stress-panel__stat">
            <strong>{passCount} of {checks.length}</strong> checks passed without warnings
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
