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
const POLL_TIMEOUT_MS = 180000

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
