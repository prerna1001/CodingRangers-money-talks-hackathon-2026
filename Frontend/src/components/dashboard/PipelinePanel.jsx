import { useState } from 'react'
import './PipelinePanel.css'
import { useLanguage } from '../../i18n/context'

const STATUS_META = {
  passed: { label: 'Passed', className: 'badge--success' },
  passed_with_warnings: { label: 'Warning', className: 'badge--warn' },
  failed: { label: 'Failed', className: 'badge--fail' },
}

export default function PipelinePanel({ steps, analysis }) {
  const { t } = useLanguage()
  const [openStep, setOpenStep] = useState(null)
  return (
    <div className="pipeline-panel">
      <div className="panel-heading">
        <div>
          <h3>{t('Agent run timeline')}</h3>
          <p>{t('Every agent that ran for this analysis, in order, with its result')}</p>
        </div>
      </div>

      <ul className="pipeline-list">
        {steps.map((step, idx) => {
          const meta = STATUS_META[step.status] || { label: step.status, className: 'badge--success' }
          const notes = step.safety_notes || []
          const fallback = step.status === 'passed_with_warnings'
            ? (analysis?.risks_or_caveats?.length ? analysis.risks_or_caveats : [t('This step completed, but raised a caution for review.')])
            : [t('No warnings were reported for this step.')]
          const details = notes.length ? notes : fallback
          const isOpen = openStep === idx
          return (
            <li key={`${step.name}-${idx}`} className={`pipeline-row ${isOpen ? 'pipeline-row--open' : ''}`}>
              <span className="pipeline-row__index">{idx + 1}</span>
              <button type="button" className="pipeline-row__toggle" onClick={() => setOpenStep(isOpen ? null : idx)} aria-expanded={isOpen}>
                <span className="pipeline-row__name">{t(step.name)}</span>
                <span className="pipeline-row__chevron">{isOpen ? '▾' : '▸'}</span>
              </button>
              <span className="pipeline-row__duration">{step.duration_ms}ms</span>
              <span className={`badge ${meta.className}`}>{t(meta.label)}</span>
              {isOpen && (
                <div className="pipeline-row__details">
                  <div><strong>{t('Result')}</strong><span>{t(step.output_summary || (step.status === 'passed_with_warnings' ? 'Completed with warnings' : 'Completed successfully'))}</span></div>
                  {step.input_summary && <div><strong>{t('Input')}</strong><span>{t(step.input_summary)}</span></div>}
                  <div><strong>{t(step.status === 'passed_with_warnings' ? 'Warning source' : 'Warnings')}</strong><span>{details.map((detail, noteIdx) => <span key={noteIdx} className="pipeline-row__note">{t(detail)}</span>)}</span></div>
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
