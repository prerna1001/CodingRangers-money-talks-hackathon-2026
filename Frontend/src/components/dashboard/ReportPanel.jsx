import { useEffect, useState } from 'react'
import { downloadAnalysisPdf } from '../../utils/pdfReport'
import './ReportPanel.css'
import { useLanguage } from '../../i18n/context'
import { translateTexts } from '../../services/api'

export default function ReportPanel({ analysis }) {
  const { t, language } = useLanguage()
  const [status, setStatus] = useState('idle') // idle | generating | done
  const [filename, setFilename] = useState(null)
  const [reportLanguage, setReportLanguage] = useState(language)
  const [translatedReport, setTranslatedReport] = useState(null)
  const [error, setError] = useState(null)

  // Warm Spanish text in the background. The first local OPUS-MT request can
  // download/load model weights, so PDF generation must never wait on it.
  useEffect(() => {
    let cancelled = false
    if (reportLanguage === 'en') return undefined

    const texts = [
      analysis.headline,
      analysis.summary,
      ...(analysis.waterfall || []).map((step) => step.name),
      ...(analysis.drivers || []).flatMap((driver) => [driver.driver, driver.account]),
      ...(analysis.risks_or_caveats || []),
      ...(analysis.agent_timeline || []).map((step) => step.name),
    ]
    translateTexts(texts, reportLanguage)
      .then((translated) => {
        if (cancelled) return
        let i = 0
        setTranslatedReport({
          ...analysis,
          headline: translated[i++],
          summary: translated[i++],
          waterfall: (analysis.waterfall || []).map((step) => ({ ...step, name: translated[i++] })),
          drivers: analysis.drivers.map((driver) => ({
            ...driver,
            driver: translated[i++],
            account: translated[i++],
          })),
          risks_or_caveats: (analysis.risks_or_caveats || []).map(() => translated[i++]),
          agent_timeline: (analysis.agent_timeline || []).map((step) => ({
            ...step,
            name: translated[i++],
          })),
        })
      })
      .catch(() => {
        // Spanish PDF labels still render immediately if offline translation
        // is unavailable; the original analysis text is retained.
      })
    return () => { cancelled = true }
  }, [analysis, reportLanguage])

  const handleDownload = () => {
    setStatus('generating')
    setError(null)
    // jsPDF is synchronous. Use any prepared Spanish copy, but never make a
    // user wait for background translation just to download their report.
    requestAnimationFrame(() => {
      try {
        const name = downloadAnalysisPdf(translatedReport || analysis, { language: reportLanguage })
        setFilename(name)
        setStatus('done')
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unable to generate the PDF.')
        setStatus('idle')
      }
    })
  }

  return (
    <div className="report-panel">
      <div className="panel-heading">
        <div>
          <h3>{t('Board-ready report')}</h3>
          <p>{t('Download this run as a PDF — headline, drivers, evidence, risks, and the agent timeline')}</p>
        </div>
      </div>

      <div className="report-language" role="group" aria-label={t('Report language')}>
        <span>{t('Report language')}</span>
        {['en', 'es'].map((code) => (
          <button
            key={code}
            type="button"
            className={reportLanguage === code ? 'report-language__active' : ''}
            onClick={() => {
              setTranslatedReport(null)
              setReportLanguage(code)
            }}
          >
            {code === 'en' ? 'English' : 'Español'}
          </button>
        ))}
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
          reportLanguage === 'es' ? '⬇ Descargar informe PDF' : '⬇ Download PDF report'
        )}
      </button>

      {status === 'done' && (
        <div className="report-panel__confirm">
          <span className="call-confirm__dot" />
          Downloaded <code>{filename}</code>
        </div>
      )}
      {error && <div className="report-panel__error">{error}</div>}
    </div>
  )
}
