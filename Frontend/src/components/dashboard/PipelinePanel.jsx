import './PipelinePanel.css'

const STATUS_META = {
  passed: { label: 'Passed', className: 'badge--success' },
  passed_with_warnings: { label: 'Warning', className: 'badge--warn' },
  failed: { label: 'Failed', className: 'badge--fail' },
}

export default function PipelinePanel({ steps }) {
  return (
    <div className="pipeline-panel">
      <div className="panel-heading">
        <div>
          <h3>Agent run timeline</h3>
          <p>Every agent that ran for this analysis, in order, with its result</p>
        </div>
      </div>

      <ul className="pipeline-list">
        {steps.map((step, idx) => {
          const meta = STATUS_META[step.status] || { label: step.status, className: 'badge--success' }
          return (
            <li key={step.name} className="pipeline-row">
              <span className="pipeline-row__index">{idx + 1}</span>
              <span className="pipeline-row__name">{step.name}</span>
              <span className="pipeline-row__duration">{step.duration_ms}ms</span>
              <span className={`badge ${meta.className}`}>{meta.label}</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
