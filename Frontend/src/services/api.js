// POST /api/upload — proxied by Vite (see vite.config.js) to the dummy
// FastAPI backend at backend/main.py. The file is sent as real multipart
// form-data (the standard way to upload a file), not embedded as JSON text.
// Today the backend just echoes back canned metadata; once real CSV
// parsing/validation lands there, this call site does not need to change.

export async function uploadFile(file) {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch('/api/upload', {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    throw new Error(`Upload failed with status ${res.status}`)
  }

  return res.json()
}

// POST /api/analyze — also a real call to backend/main.py. Body is currently
// ignored server-side (dummy analysis is static), but file_id is sent so the
// contract matches what a real Analyzer endpoint will expect.
export async function analyzeRun(fileId) {
  const res = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ file_id: fileId }),
  })

  if (!res.ok) {
    throw new Error(`Analyze failed with status ${res.status}`)
  }

  return res.json()
}
