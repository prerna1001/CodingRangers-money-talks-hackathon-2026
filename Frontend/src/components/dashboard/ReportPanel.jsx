import { useState } from 'react'
import { downloadAnalysisPdf } from '../../utils/pdfReport'
import './ReportPanel.css'

export default function ReportPanel({ analysis }) {
  const [status, setStatus] = useState('idle') // idle | generating | done
  const [filename, setFilename] = useState(null)

  const handleDownload = () => {
    setStatus('generating')
    // Synchronous but felt instant enough that a frame is worth forcing
    // so the "Generating…" state is visible before the browser's save
    // dialog takes over.
    requestAnimationFrame(() => {
      const name = downloadAnalysisPdf(analysis)
      setFilename(name)
      setStatus('done')
    })
  }

  return (
    <div className="report-panel">
      <div className="panel-heading">
        <div>
          <h3>Board-ready report</h3>
          <p>Download this run as a PDF — headline, drivers, evidence, risks, and the agent timeline</p>
        </div>
      </div>

      <button
        type="button"
        className="btn btn--primary"
        onClick={handleDownload}
        disabled={status === 'generating'}
      >
        {status === 'generating' ? (
          <>
            <span className="spinner" /> Generating PDF…
          </>
        ) : (
          '⬇ Download PDF report'
        )}
      </button>

      {status === 'done' && (
        <div className="report-panel__confirm">
          <span className="call-confirm__dot" />
          Downloaded <code>{filename}</code>
        </div>
      )}
    </div>
  )
}
