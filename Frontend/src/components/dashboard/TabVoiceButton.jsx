import { useEffect, useRef, useState } from 'react'
import { useLanguage } from '../../i18n/context'
import Icon from '../Icon'

const LOCALES = { en: 'en-US', es: 'es-ES' }

export default function TabVoiceButton({ targetRef }) {
  const { t, language } = useLanguage()
  const [speaking, setSpeaking] = useState(false)
  const utteranceRef = useRef(null)

  useEffect(() => () => window.speechSynthesis?.cancel(), [])

  const toggle = () => {
    if (!window.speechSynthesis) return
    if (speaking) {
      window.speechSynthesis.cancel()
      setSpeaking(false)
      return
    }
    const text = targetRef.current?.innerText?.replace(/\s+/g, ' ').trim()
    if (!text) return
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = LOCALES[language] || 'en-US'
    utterance.onend = () => setSpeaking(false)
    utterance.onerror = () => setSpeaking(false)
    utteranceRef.current = utterance
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(utterance)
    setSpeaking(true)
  }

  return (
    <button
      type="button"
      className={`btn btn--ghost btn--sm tab-voice-button ${speaking ? 'tab-voice-button--active' : ''}`}
      onClick={toggle}
      disabled={typeof window !== 'undefined' && !window.speechSynthesis}
      aria-label={speaking ? t('Stop reading tab') : t('Read this tab aloud')}
      title={speaking ? t('Stop reading tab') : t('Read this tab aloud')}
    >
      <Icon name={speaking ? 'stop' : 'speaker'} /> {speaking ? t('Stop') : t('Read tab')}
    </button>
  )
}
