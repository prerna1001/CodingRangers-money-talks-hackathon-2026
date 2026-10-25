import './PipelinePanel.css'

const STATUS_META = {
  passed: { label: 'Passed', className: 'badge--success' },
  passed_with_warnings: { label: 'Passed with warnings', className: 'badge--warn' },
  failed: { label: 'Failed', className: 'badge--fail' },
}

export default function PipelinePanel({ steps }) {
  return (
    <div className="pipeline-panel">
      <div className="panel-heading">
        <div>
          <h2>Agent run</h2>
          <p>Every agent that worked on this analysis, in the order it ran, and what it concluded</p>
        </div>
      </div>

      {steps.length === 0 && <p className="panel-loading">This run did not report its agent steps.</p>}
      <ol className="pipeline-list">
        {steps.map((step, idx) => {
          const meta = STATUS_META[step.status] || { label: step.status, className: 'badge--success' }
          return (
            <li key={`${idx}-${step.name}`} className="pipeline-row">
              <span className="pipeline-row__index">{idx + 1}</span>
              <span className="pipeline-row__name">{step.name}</span>
              <span className="pipeline-row__duration">{(Number(step.duration_ms) || 0).toLocaleString('en-US')} ms</span>
              <span className={`badge ${meta.className}`}>{meta.label}</span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
