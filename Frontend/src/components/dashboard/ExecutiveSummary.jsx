import { useEffect, useRef, useState } from 'react'
import { synthesizeSpeech } from '../../services/api'
import { generateVoiceBriefing } from '../../services/mockApi'
import { useLanguage } from '../../i18n/context'
import './ExecutiveSummary.css'

function pct(value) {
  return `${Math.round((Number(value) || 0) * 100)}%`
}

function money(value) {
  return `$${(Number(value) || 0).toLocaleString('en-US')}`
}

export default function ExecutiveSummary({ analysis }) {
  const { t, language } = useLanguage()
  const [voice, setVoice] = useState(null)
  const [loadingVoice, setLoadingVoice] = useState(false)
  // idle | loading | playing | paused
  const [speakStatus, setSpeakStatus] = useState('idle')
  const [speakError, setSpeakError] = useState(null)
  const audioRef = useRef(null)

  const drivers = Array.isArray(analysis.drivers) ? analysis.drivers : []
  const risks = Array.isArray(analysis.risks_or_caveats) ? analysis.risks_or_caveats : []
  const topDrivers = [...drivers]
    .sort((a, b) => Math.abs(Number(b.amount) || 0) - Math.abs(Number(a.amount) || 0))
    .slice(0, 3)

  const stopPlayback = () => {
    const audio = audioRef.current
    if (audio) {
      audio.pause()
      URL.revokeObjectURL(audio.src)
    }
    audioRef.current = null
    setSpeakStatus('idle')
  }

  // Stop reading aloud if the user leaves the Summary tab mid-playback.
  useEffect(() => () => audioRef.current?.pause(), [])

  // A language switch mid-playback would otherwise keep reading the old
  // language: drop the loaded audio so the next play re-synthesizes.
  useEffect(() => {
    const audio = audioRef.current
    if (audio) {
      audio.pause()
      URL.revokeObjectURL(audio.src)
      audioRef.current = null
      setSpeakStatus('idle')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [language])

  const handleSpeak = async () => {
    // Pause keeps the audio loaded, so the next click resumes where it left off.
    if (speakStatus === 'playing') {
      audioRef.current?.pause()
      setSpeakStatus('paused')
      return
    }
    if (speakStatus === 'paused' && audioRef.current) {
      setSpeakStatus('playing')
      await audioRef.current.play()
      return
    }
    setSpeakError(null)
    setSpeakStatus('loading')
    try {
      const blob = await synthesizeSpeech(voice.script, { language, translate: language !== 'en' })
      const audio = new Audio(URL.createObjectURL(blob))
      audioRef.current = audio
      audio.onended = stopPlayback
      setSpeakStatus('playing')
      await audio.play()
    } catch (err) {
      stopPlayback()
      setSpeakError(err.message)
    }
  }

  const handleVoice = async () => {
    stopPlayback()
    setSpeakError(null)
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
          {loadingVoice
            ? t('Generating…')
            : voice
              ? t('Regenerate voice briefing')
              : t('🔊 Generate CFO voice briefing')}
        </button>
      </div>

      <h1 className="exec-summary__headline">
        {t(analysis.headline || 'Financial results analyzed')}
      </h1>
      <p className="exec-summary__body">
        {t(analysis.summary || 'The run completed, but no narrative summary was returned.')}
      </p>

      <div className="exec-summary__scores">
        <div className="score-card">
          <span className="score-card__label">{t('Confidence')}</span>
          <span className="score-card__value">{pct(analysis.confidence)}</span>
        </div>
        <div className="score-card">
          <span className="score-card__label">{t('Data quality')}</span>
          <span className="score-card__value">{pct(analysis.data_quality_score)}</span>
        </div>
        <div className="score-card">
          <span className="score-card__label">
            {t('Revenue')} ({analysis.periods.current.label})
          </span>
          <span className="score-card__value">{money(analysis.periods.current.revenue)}</span>
        </div>
      </div>

      <div className="exec-summary__drivers">
        <h3>{t('Top drivers')}</h3>
        <ul>
          {topDrivers.map((d) => (
            <li key={d.driver}>
              <span className={`driver-dot ${(Number(d.amount) || 0) >= 0 ? 'driver-dot--up' : 'driver-dot--down'}`} />
              <span className="exec-summary__driver-name">
                {t(d.driver || d.account || 'Unknown driver')}
              </span>
              <span className={`exec-summary__driver-amount ${(Number(d.amount) || 0) >= 0 ? 'text-up' : 'text-down'}`}>
                {(Number(d.amount) || 0) >= 0 ? '+' : ''}${Math.abs(Number(d.amount) || 0).toLocaleString('en-US')}
              </span>
            </li>
          ))}
        </ul>
      </div>

      {risks.length > 0 && (
        <div className="exec-summary__caveats">
          <h3>{t('Risks & caveats')}</h3>
          <ul>
            {risks.map((c) => (
              <li key={c}>{t(c)}</li>
            ))}
          </ul>
        </div>
      )}

      {voice && (
        <div className="voice-panel">
          <div className="voice-panel__header">
            <span className="badge badge--success">{t('audio ready')}</span>
            <span>
              {voice.duration_sec}s · {t('executive tone')}
            </span>
            <button
              type="button"
              className="btn btn--ghost btn--sm voice-panel__play"
              onClick={handleSpeak}
              disabled={speakStatus === 'loading'}
              aria-label={
                speakStatus === 'playing'
                  ? t('Pause briefing')
                  : speakStatus === 'paused'
                    ? t('Resume briefing')
                    : t('Read briefing aloud')
              }
            >
              {speakStatus === 'loading' ? (
                <>
                  <span className="spinner" /> {t('Loading…')}
                </>
              ) : speakStatus === 'playing' ? (
                t('⏸ Pause')
              ) : speakStatus === 'paused' ? (
                t('▶ Resume')
              ) : (
                t('▶ Play briefing')
              )}
            </button>
          </div>
          <p className="voice-panel__script">{t(voice.script)}</p>
          {speakError && <div className="voice-panel__error">{speakError}</div>}
        </div>
      )}
    </div>
  )
}
