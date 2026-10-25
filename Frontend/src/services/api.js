// Real calls to the FastAPI backend (backend/main.py), proxied by Vite
// (see vite.config.js) to http://localhost:8000.

import { API_ENDPOINTS } from '../constants/api'

// POST /api/upload — the file is sent as real multipart form-data (the
// standard way to upload a file), not embedded as JSON text. The backend
// parses it into canonical transactions and returns { file_id, sha256,
// row_count, preview }.
// Uploads several CSVs (transactions and/or period summaries) in parallel.
// The backend auto-detects each file's type from its headers.
export async function uploadFiles(files, metadata = {}) {
  return Promise.all(Array.from(files).map((file) => uploadFile(file, metadata)))
}

export async function uploadFile(file, metadata = {}) {
  const formData = new FormData()
  formData.append('file', file)
  if (metadata.companyId) formData.append('company_id', metadata.companyId)

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

export async function confirmUpload(fileId, useAs, rows = null) {
  const res = await fetch(`${API_ENDPOINTS.upload}s/${fileId}/confirm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ use_as: useAs, ...(rows ? { rows } : {}) }),
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail || `Review confirmation failed with status ${res.status}`)
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
export async function analyzeRun(uploads, context = {}) {
  // `uploads` is the array of /api/upload responses (each carries the
  // backend's auto-detected file_type). Split them into the two id lists
  // the analyze endpoint expects. Nothing uploaded -> built-in demo dataset.
  const list = Array.isArray(uploads) ? uploads : uploads ? [uploads] : []
  const body = {}
  const ready = list.filter((u) => u?.review_status === 'ready' && u?.file_type)
  const txnIds = ready.filter((u) => u.file_type !== 'period_summary_csv').map((u) => u.file_id)
  const sumIds = ready.filter((u) => u.file_type === 'period_summary_csv').map((u) => u.file_id)
  if (txnIds.length) body.transaction_file_ids = txnIds
  if (sumIds.length) body.period_summary_file_ids = sumIds
  if (context.company_name?.trim()) body.company_name = context.company_name.trim()
  if (context.industry?.trim()) body.industry = context.industry.trim()
  if (context.business_model?.trim()) body.business_model = context.business_model.trim()
  if (context.business_context?.trim()) body.business_context = context.business_context.trim()
  if (context.company_name?.trim()) {
    body.company_id = context.company_name.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g) || 'analysis'
  }

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

// GET /api/runs/{run_id}/powerbi — zip of the run's tables, Power Query
// scripts and theme (backend/services/powerbi_export.py). Saves it through
// a temporary link and returns the filename the backend chose.
export async function downloadPowerBiPackage(runId) {
  const res = await fetch(API_ENDPOINTS.powerbi(runId))
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail
    // FastAPI answers a bare "Not Found" when the route itself is missing
    // (backend started before this feature); a missing run names the run.
    if (res.status === 404 && detail === 'Not Found') {
      throw new Error('The backend is running an older version without the Power BI export. Restart it, run the analysis again, then retry.')
    }
    if (res.status === 404) {
      throw new Error('The server no longer has this analysis, most likely because it was restarted. Run the analysis again, then retry.')
    }
    throw new Error(detail || `Power BI export failed with status ${res.status}.`)
  }
  const disposition = res.headers.get('Content-Disposition') || ''
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] || `ledgerlight_${runId}_powerbi.zip`
  const url = URL.createObjectURL(await res.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return filename
}

// GET /api/runs/{run_id}/pitch-deck?theme=finance|dark — seven-slide .pptx
// pitch deck (backend/services/pitch_deck.py), saved through a temporary link.
export async function downloadPitchDeck(runId, theme) {
  const res = await fetch(API_ENDPOINTS.pitchDeck(runId, theme))
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail
    if (res.status === 404 && detail === 'Not Found') {
      throw new Error('The backend is running an older version without the pitch deck export. Restart it, run the analysis again, then retry.')
    }
    if (res.status === 404) {
      throw new Error('The server no longer has this analysis, most likely because it was restarted. Run the analysis again, then retry.')
    }
    throw new Error(detail || `Pitch deck export failed with status ${res.status}.`)
  }
  const disposition = res.headers.get('Content-Disposition') || ''
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] || `ledgerlight_${runId}_pitch_${theme}.pptx`
  const url = URL.createObjectURL(await res.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return filename
}
