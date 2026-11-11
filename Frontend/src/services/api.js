// Real calls to the FastAPI backend (backend/main.py), proxied by Vite
// (see vite.config.js) to http://localhost:8000.

import { API_ENDPOINTS } from '../constants/api'

// POST /api/upload — the file is sent as real multipart form-data (the
// standard way to upload a file), not embedded as JSON text. The backend
// parses it into canonical transactions and returns { file_id, sha256,
// row_count, preview }.
// Uploads several CSVs (transactions and/or period summaries) in parallel.
// The backend auto-detects each file's type from its headers.
export async function uploadFiles(files) {
  return Promise.all(Array.from(files).map(uploadFile))
}

export async function uploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(API_ENDPOINTS.upload, {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    // The backend explains *why* a CSV was rejected (bad date format, missing
    // column, and which headers it actually saw). Showing only the status code
    // throws that away and leaves the user guessing.
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail || `Upload failed with status ${res.status}`)
  }

  return res.json()
}

const POLL_INTERVAL_MS = 1000
// The guardrail can send the analyst back twice, so a slow run is several
// sequential LLM calls, not one. 3 minutes was not enough for that.
const POLL_TIMEOUT_MS = 420000

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

// POST /api/analyze starts the multi-agent run in the background and returns
// { run_id, status: 'running' } immediately — the pipeline makes several real
// LLM calls and takes far longer than a request should be held open for.
// So this resolves the way callers expect (one await -> the finished
// analysis) by polling GET /api/runs/{run_id}, which answers 202 while the
// run is still in flight and 200 with the dashboard-shaped analysis once
// it completes. App.jsx is unchanged: it still just awaits analyzeRun().
export async function analyzeRun(uploads) {
  // `uploads` is the array of /api/upload responses (each carries the
  // backend's auto-detected file_type). Split them into the two id lists
  // the analyze endpoint expects. Nothing uploaded -> built-in demo dataset.
  const list = Array.isArray(uploads) ? uploads : uploads ? [uploads] : []
  const body = {}
  const txnIds = list.filter((u) => u?.file_type !== 'period_summary_csv').map((u) => u.file_id)
  const sumIds = list.filter((u) => u?.file_type === 'period_summary_csv').map((u) => u.file_id)
  if (txnIds.length) body.transaction_file_ids = txnIds
  if (sumIds.length) body.period_summary_file_ids = sumIds

  const startRes = await fetch(API_ENDPOINTS.analyze, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!startRes.ok) {
    const detail = await startRes.json().catch(() => null)
    throw new Error(detail?.detail || `Analyze failed with status ${startRes.status}`)
  }

  const { run_id: runId } = await startRes.json()
  if (!runId) {
    throw new Error('Analyze did not return a run_id')
  }

  const deadline = Date.now() + POLL_TIMEOUT_MS
  while (Date.now() < deadline) {
    const res = await fetch(API_ENDPOINTS.run(runId))

    if (res.status === 200) {
      return res.json()
    }
    // 202 = still running. Anything else is a real failure.
    if (res.status !== 202) {
      const detail = await res.json().catch(() => null)
      throw new Error(detail?.detail || `Analysis failed with status ${res.status}`)
    }

    await sleep(POLL_INTERVAL_MS)
  }

  throw new Error('Analysis timed out')
}

// POST /api/chat — answers grounded in this run's analysis (backend
// api/routes/chat.py: LLM when a key is configured, rule-based otherwise).
export async function sendChatMessage(runId, message, history) {
  const res = await fetch(API_ENDPOINTS.chat, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ run_id: runId, message, history }),
  })

  if (!res.ok) {
    throw new Error(await errorDetail(res, `Chat failed with status ${res.status}`))
  }

  return res.json()
}

// POST /api/voice/speak — text-to-speech via the backend (local Kokoro by
// default). Returns an MP3 blob. A 503 means the voice provider isn't set up;
// the error carries the backend's explanation.
//
// `language` is the language to speak in. Pass translate: true when the text
// is still English but should be spoken in `language` — the backend
// translates it first, so the audio matches what the screen shows.
export async function synthesizeSpeech(text, { language = 'en', translate = false } = {}) {
  const res = await fetch(API_ENDPOINTS.voiceSpeak, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, language, translate }),
  })

  if (!res.ok) {
    throw new Error(await errorDetail(res, `Voice synthesis failed with status ${res.status}`))
  }

  return res.blob()
}

// POST /api/voice/transcribe — speech-to-text via the backend (local
// faster-whisper by default). Takes the recorded audio blob, returns the
// transcribed text. `language` picks the decoding language, so a Spanish
// question isn't forced through an English-only model.
export async function transcribeAudio(blob, { language = 'en' } = {}) {
  const ext = blob.type.includes('mp4') ? 'mp4' : blob.type.includes('ogg') ? 'ogg' : 'webm'
  const form = new FormData()
  form.append('file', blob, `recording.${ext}`)
  form.append('language', language)

  const res = await fetch(API_ENDPOINTS.voiceTranscribe, { method: 'POST', body: form })

  if (!res.ok) {
    throw new Error(await errorDetail(res, `Transcription failed with status ${res.status}`))
  }

  const { text } = await res.json()
  return text ?? ''
}

// POST /api/translate — batch screen translation (Helsinki-NLP OPUS-MT on
// the backend). Returns translations in the same order as `texts`; on any
// failure the caller keeps showing the original text, so this never blanks
// the UI.
export async function translateTexts(texts, target, source = 'en') {
  if (!texts.length || target === source) return texts

  const res = await fetch(API_ENDPOINTS.translate, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ texts, target, source }),
  })

  if (!res.ok) {
    throw new Error(await errorDetail(res, `Translation failed with status ${res.status}`))
  }

  const { translations } = await res.json()
  return Array.isArray(translations) ? translations : texts
}

async function errorDetail(res, fallback) {
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') return body.detail
  } catch {
    // response wasn't JSON — keep the generic message
  }
  return fallback
}
