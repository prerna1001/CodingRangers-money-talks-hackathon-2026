import { useEffect, useRef, useState } from 'react'
import { sendChatMessage, synthesizeSpeech, transcribeAudio } from '../../services/api'
import { useLanguage } from '../../i18n/context'
import './ChatPanel.css'

// Browser speech recognition (Chrome, Edge, Safari) gives live word-by-word
// transcripts. Where it's missing (Firefox) the mic falls back to recording
// a clip and transcribing it on the backend (local Whisper) once you stop.
const SpeechRecognition =
  typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : undefined

// The browser recognizer wants a BCP-47 tag, not our two-letter code.
const SPEECH_LOCALES = { en: 'en-US', es: 'es-ES' }

const SUGGESTIONS = [
  'Why did revenue increase?',
  'Tell me about the churn',
  'Any risks I should know about?',
  'How confident are you in this?',
]

function Message({ msg, onSpeak, t }) {
  const isUser = msg.role === 'user'
  return (
    <div className={`chat-msg ${isUser ? 'chat-msg--user' : 'chat-msg--assistant'}`}>
      <div className="chat-msg__bubble">
        {/* The user's own words stay as typed; only the AI's answer is translated. */}
        {isUser ? msg.content : t(msg.content)}
        {!isUser && (
          <button
            type="button"
            className="chat-msg__speak"
            onClick={() => onSpeak(msg)}
            disabled={msg.speakStatus === 'loading'}
            aria-label={msg.speakStatus === 'playing' ? t('Stop reading') : t('Read answer aloud')}
            title={msg.speakStatus === 'playing' ? t('Stop reading') : t('Read answer aloud')}
          >
            {msg.speakStatus === 'loading' ? (
              <span className="spinner" />
            ) : msg.speakStatus === 'playing' ? (
              '⏹'
            ) : (
              '🔈'
            )}
          </button>
        )}
      </div>
      {msg.speakError && <div className="chat-msg__error">{msg.speakError}</div>}
    </div>
  )
}

export default function ChatPanel({ analysis, compact = false }) {
  const { t, language } = useLanguage()
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: `Ask me anything about this run — "${analysis.headline}" Try a question about drivers, risks, or confidence.`,
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  // idle | recording | transcribing
  const [micStatus, setMicStatus] = useState('idle')
  const [micError, setMicError] = useState(null)
  const audioRef = useRef(null)
  const playingIndexRef = useRef(null)
  const recorderRef = useRef(null)
  const recognitionRef = useRef(null)
  const scrollRef = useRef(null)
  const inputRef = useRef(null)

  // Stop any playback / recording when the panel unmounts (tab switch).
  useEffect(
    () => () => {
      audioRef.current?.pause()
      recognitionRef.current?.abort()
      const recorder = recorderRef.current
      if (recorder && recorder.state !== 'inactive') recorder.stop()
    },
    [],
  )

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const updateMessage = (index, patch) => {
    setMessages((prev) => prev.map((m, i) => (i === index ? { ...m, ...patch } : m)))
  }

  const handleSend = async (textOverride) => {
    const text = (textOverride ?? input).trim()
    if (!text || sending) return
    // Sending mid-dictation ends it, so late results don't refill the box.
    recognitionRef.current?.abort()

    const history = messages.map(({ role, content }) => ({ role, content }))
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setInput('')
    setSending(true)

    try {
      const res = await sendChatMessage(analysis.run_id, text, history)
      setMessages((prev) => [...prev, { role: 'assistant', content: res.reply }])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `Something went wrong: ${err.message}` },
      ])
    } finally {
      setSending(false)
    }
  }

  const stopPlayback = () => {
    audioRef.current?.pause()
    audioRef.current = null
    if (playingIndexRef.current !== null) {
      updateMessage(playingIndexRef.current, { speakStatus: 'idle' })
      playingIndexRef.current = null
    }
  }

  const handleSpeak = async (msg) => {
    const index = messages.indexOf(msg)
    if (index === -1) return

    // Clicking the playing message's button stops it.
    if (msg.speakStatus === 'playing') {
      stopPlayback()
      return
    }

    stopPlayback()
    updateMessage(index, { speakStatus: 'loading', speakError: null })
    try {
      const blob = await synthesizeSpeech(msg.content, {
        language,
        translate: language !== 'en',
      })
      const url = URL.createObjectURL(blob)
      const audio = new Audio(url)
      audioRef.current = audio
      playingIndexRef.current = index
      updateMessage(index, { speakStatus: 'playing' })
      audio.onended = () => {
        URL.revokeObjectURL(url)
        if (playingIndexRef.current === index) playingIndexRef.current = null
        updateMessage(index, { speakStatus: 'idle' })
      }
      await audio.play()
    } catch (err) {
      updateMessage(index, { speakStatus: 'idle', speakError: err.message })
    }
  }

  const startLiveDictation = () => {
    setMicError(null)
    stopPlayback()

    // Whatever was already typed stays; speech is appended after it.
    const base = input.trim() ? `${input.trim()} ` : ''
    const recognition = new SpeechRecognition()
    recognition.lang = SPEECH_LOCALES[language] ?? 'en-US'
    recognition.continuous = true
    recognition.interimResults = true

    recognition.onresult = (event) => {
      let transcript = ''
      for (let i = 0; i < event.results.length; i += 1) {
        transcript += event.results[i][0].transcript
      }
      setInput(base + transcript.trimStart())
    }
    recognition.onerror = (event) => {
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        setMicError(t('Microphone access was blocked. Allow it in the browser to speak your question.'))
      } else if (event.error !== 'no-speech' && event.error !== 'aborted') {
        setMicError(`Voice input error: ${event.error}`)
      }
    }
    recognition.onend = () => {
      recognitionRef.current = null
      setMicStatus('idle')
      inputRef.current?.focus()
    }

    recognitionRef.current = recognition
    recognition.start()
    setMicStatus('recording')
  }

  const startRecording = async () => {
    setMicError(null)
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setMicError(t('Voice input is not supported in this browser.'))
      return
    }

    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      setMicError('Microphone access was blocked. Allow it in the browser to speak your question.')
      return
    }

    stopPlayback()
    const recorder = new MediaRecorder(stream)
    const chunks = []
    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data)
    }
    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop())
      recorderRef.current = null
      const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' })
      if (!blob.size) {
        setMicStatus('idle')
        return
      }

      setMicStatus('transcribing')
      try {
        const text = await transcribeAudio(blob, { language })
        if (text) {
          // Drop the transcript into the input, ready to review and send.
          setInput((prev) => (prev.trim() ? `${prev.trim()} ${text}` : text))
          inputRef.current?.focus()
        } else {
          setMicError(t("Didn't catch that — try speaking again."))
        }
      } catch (err) {
        setMicError(err.message)
      } finally {
        setMicStatus('idle')
      }
    }

    recorderRef.current = recorder
    recorder.start()
    setMicStatus('recording')
  }

  const handleMic = () => {
    if (micStatus === 'recording') {
      recognitionRef.current?.stop()
      recorderRef.current?.stop()
    } else if (micStatus === 'idle') {
      if (SpeechRecognition) startLiveDictation()
      else startRecording()
    }
  }

  return (
    <div className={`chat-panel ${compact ? 'chat-panel--compact' : ''}`}>
      <div className="panel-heading">
        <div>
          <h3>{t('Ask FinOps AI')}</h3>
          <p>
            {t(
              "Chat about this run's drivers, risks, and confidence — speak or listen in your language",
            )}
          </p>
        </div>
        <span className="source-tag">
          <code>POST</code> <code>/api/chat</code>
        </span>
      </div>

      <div className="chat-window" ref={scrollRef}>
        {messages.map((msg, i) => (
          <Message key={i} msg={msg} onSpeak={handleSpeak} t={t} />
        ))}
        {sending && (
          <div className="chat-msg chat-msg--assistant">
            <div className="chat-msg__bubble chat-msg__bubble--typing">
              <span className="spinner" /> {t('thinking…')}
            </div>
          </div>
        )}
      </div>

      <div className="chat-suggestions">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            type="button"
            className="chat-suggestion"
            onClick={() => handleSend(t(suggestion))}
          >
            {t(suggestion)}
          </button>
        ))}
      </div>

      <form
        className="chat-input-row"
        onSubmit={(e) => {
          e.preventDefault()
          handleSend()
        }}
      >
        <button
          type="button"
          className={`chat-mic ${micStatus === 'recording' ? 'chat-mic--recording' : ''}`}
          onClick={handleMic}
          disabled={micStatus === 'transcribing'}
          aria-label={micStatus === 'recording' ? t('Stop recording') : t('Speak your question')}
          title={micStatus === 'recording' ? t('Stop recording') : t('Speak your question')}
        >
          {micStatus === 'transcribing' ? <span className="spinner" /> : micStatus === 'recording' ? '⏹' : '🎤'}
        </button>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            micStatus === 'recording'
              ? t('Listening… click ⏹ when done')
              : micStatus === 'transcribing'
                ? t('Transcribing…')
                : t('Ask about this run, or click 🎤 to speak…')
          }
          className="chat-input"
        />
        <button type="submit" className="btn btn--primary btn--sm" disabled={!input.trim() || sending}>
          {t('Send')}
        </button>
      </form>
      {micError && <div className="chat-msg__error">{micError}</div>}
    </div>
  )
}
