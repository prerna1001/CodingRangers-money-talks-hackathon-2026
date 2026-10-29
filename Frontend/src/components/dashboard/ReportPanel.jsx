import { useState } from 'react'
import { downloadPitchDeck, downloadPowerBiPackage } from '../../services/api'
import Tick from '../Tick'
import './ReportPanel.css'

export default function ReportPanel({ analysis }) {
  const [pdf, setPdf] = useState({ status: 'idle', filename: null })
  const [powerbi, setPowerbi] = useState({ status: 'idle', filename: null, error: null })
  const [deck, setDeck] = useState({ status: 'idle', theme: null, filename: null, error: null })

  // jsPDF is loaded on demand so it stays out of the first page load.
  const handlePdf = async () => {
    setPdf({ status: 'working', filename: null })
    const { downloadAnalysisPdf } = await import('../../utils/pdfReport')
    const filename = downloadAnalysisPdf(analysis)
    setPdf({ status: 'done', filename })
  }

  const handlePowerBi = async () => {
    setPowerbi({ status: 'working', filename: null, error: null })
    try {
      const filename = await downloadPowerBiPackage(analysis.run_id)
      setPowerbi({ status: 'done', filename, error: null })
    } catch (err) {
      setPowerbi({ status: 'error', filename: null, error: err.message })
    }
  }

  const handleDeck = async (theme) => {
    setDeck({ status: 'working', theme, filename: null, error: null })
    try {
      const filename = await downloadPitchDeck(analysis.run_id, theme)
      setDeck({ status: 'done', theme, filename, error: null })
    } catch (err) {
      setDeck({ status: 'error', theme, filename: null, error: err.message })
    }
  }

  return (
    <div className="report-panel">
      <section className="report-option">
        <div className="report-option__text">
          <h2>Board-ready report</h2>
          <p>A PDF of this run with the headline, revenue bridge, drivers, risks and the agent run, ready to attach to a board update.</p>
        </div>
        <div className="report-option__action">
          <button type="button" className="btn btn--primary" onClick={handlePdf} disabled={pdf.status === 'working'}>
            {pdf.status === 'working' ? <><span className="spinner" /> Creating PDF…</> : 'Download PDF report'}
          </button>
          {pdf.status === 'done' && (
            <p className="report-panel__confirm" role="status"><Tick /> Saved as <code>{pdf.filename}</code></p>
          )}
        </div>
      </section>

      <section className="report-option">
        <div className="report-option__text">
          <h2>Open in Power BI</h2>
          <p>
            Two ready-made Power BI reports for this run, one in corporate navy and one in dark executive. Each has an
            overview with KPIs and the revenue bridge, an evidence page that traces every figure to its transactions,
            and a trend page. This run&rsquo;s data is built in. The zip also holds the tables as Excel and CSV, Power
            Query scripts and the themes, if you&rsquo;d rather build your own.
          </p>
          <ol className="report-option__steps">
            <li>Unzip to a short folder such as <code>C:\Ledgerlight</code>. Deep folders can hit Windows&rsquo; path length limit.</li>
            <li>Double-click <code>reports\Ledgerlight Finance.pbip</code> or <code>Ledgerlight Executive Dark.pbip</code>.</li>
            <li>When Power BI says some tables have no data, click Refresh now once.</li>
            <li>To keep it as a single file, use File &gt; Save As &gt; Power BI file (.pbix).</li>
          </ol>
        </div>
        <div className="report-option__action">
          <button type="button" className="btn btn--ghost" onClick={handlePowerBi} disabled={powerbi.status === 'working' || !analysis.run_id}>
            {powerbi.status === 'working' ? <><span className="spinner" /> Packaging…</> : 'Download for Power BI'}
          </button>
          {powerbi.status === 'done' && (
            <p className="report-panel__confirm" role="status"><Tick /> Saved as <code>{powerbi.filename}</code></p>
          )}
          {powerbi.status === 'error' && (
            <p className="report-panel__error" role="alert">
              {powerbi.error}
            </p>
          )}
        </div>
      </section>
      <section className="report-option">
        <div className="report-option__text">
          <h2>Pitch deck (PowerPoint)</h2>
          <p>
            A seven-slide deck for another team, a client or senior leadership. It opens with the headline and the
            problem, walks through the revenue bridge, the ranked drivers and the evidence behind them, then closes with
            conclusions, risks and next steps. Charts are native PowerPoint charts you can edit, and each slide has
            speaker notes. Choose the same two looks as the Power BI reports.
          </p>
        </div>
        <div className="report-option__action">
          {[['finance', 'Corporate navy'], ['dark', 'Executive dark']].map(([theme, label]) => (
            <button
              key={theme}
              type="button"
              className="btn btn--ghost"
              onClick={() => handleDeck(theme)}
              disabled={deck.status === 'working' || !analysis.run_id}
            >
              {deck.status === 'working' && deck.theme === theme ? <><span className="spinner" /> Building…</> : `Download deck, ${label}`}
            </button>
          ))}
          {deck.status === 'done' && (
            <p className="report-panel__confirm" role="status"><Tick /> Saved as <code>{deck.filename}</code></p>
          )}
          {deck.status === 'error' && (
            <p className="report-panel__error" role="alert">
              {deck.error}
            </p>
          )}
        </div>
      </section>
    </div>
  )
}
