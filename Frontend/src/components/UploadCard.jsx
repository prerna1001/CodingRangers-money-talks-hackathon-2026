import { useCallback, useRef, useState } from 'react'
import { uploadFiles } from '../services/api'
import './UploadCard.css'

function formatBytes(bytes) {
  if (!bytes) return '0 KB'
  const kb = bytes / 1024
  if (kb < 1024) return `${kb.toFixed(1)} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

export default function UploadCard({ onUploaded }) {
  const [files, setFiles] = useState([])
  const [status, setStatus] = useState('idle') // idle | uploading | success | error
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [callInfo, setCallInfo] = useState(null) // { url, method, ms }
  const inputRef = useRef(null)

  const reset = () => {
    setFiles([])
    setStatus('idle')
    setResult(null)
    setError(null)
    setCallInfo(null)
  }

  // Accepts several CSVs at once -- typically transactions.csv plus
  // period_summaries.csv. The backend detects which is which.
  const handleFile = useCallback((selected) => {
    const picked = Array.from(selected || []).filter(Boolean)
    if (!picked.length) return
    setFiles((prev) => {
      const merged = [...prev]
      picked.forEach((f) => {
        if (!merged.some((m) => m.name === f.name && m.size === f.size)) merged.push(f)
      })
      return merged
    })
    setStatus('idle')
    setResult(null)
    setError(null)
  }, [])

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault()
      setIsDragging(false)
      handleFile(e.dataTransfer.files)
    },
    [handleFile],
  )

  const handleUpload = async () => {
    if (!files.length) return
    setStatus('uploading')
    setError(null)
    const startedAt = performance.now()
    try {
      const res = await uploadFiles(files)
      setResult(res)
      setCallInfo({
        url: `${window.location.origin}/api/upload`,
        method: 'POST',
        ms: Math.round(performance.now() - startedAt),
      })
      setStatus('success')
    } catch (err) {
      setError(err.message || 'Upload failed')
      setStatus('error')
    }
  }

  return (
    <div className="upload-card">
      <div className="upload-card__header">
        <h2>Upload financial data</h2>
        <p>Monthly account summaries or transaction-level CSVs</p>
      </div>

      <div
        className={`dropzone ${isDragging ? 'dropzone--active' : ''} ${files.length ? 'dropzone--filled' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".csv"
          multiple
          hidden
          onChange={(e) => handleFile(e.target.files)}
        />

        {!files.length ? (
          <>
            <svg className="dropzone__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M12 16V4M12 4L7 9M12 4L17 9M5 20H19"
                stroke="currentColor"
                strokeWidth="1.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            <p className="dropzone__title">Drag &amp; drop CSV files here</p>
            <p className="dropzone__subtitle">transactions.csv and period_summaries.csv — .csv only</p>
          </>
        ) : (
          <div className="file-chip-list">
            {files.map((f) => (
              <div className="file-chip" key={`${f.name}-${f.size}`}>
                <svg className="file-chip__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"
                    stroke="currentColor"
                    strokeWidth="1.6"
                    strokeLinejoin="round"
                  />
                  <path d="M14 3v5h5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
                </svg>
                <div className="file-chip__meta">
                  <span className="file-chip__name">{f.name}</span>
                  <span className="file-chip__size">{formatBytes(f.size)}</span>
                </div>
                <button
                  type="button"
                  className="file-chip__remove"
                  onClick={(e) => {
                    e.stopPropagation()
                    setFiles((prev) => prev.filter((x) => !(x.name === f.name && x.size === f.size)))
                  }}
                  aria-label={`Remove ${f.name}`}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="upload-card__actions">
        <button
          type="button"
          className="btn btn--primary"
          disabled={!files.length || status === 'uploading'}
          onClick={handleUpload}
        >
          {status === 'uploading' ? (
            <>
              <span className="spinner" /> Uploading…
            </>
          ) : (
            'Upload'
          )}
        </button>
        {(status === 'success' || status === 'error') && (
          <button type="button" className="btn btn--ghost" onClick={reset}>
            Upload another
          </button>
        )}
        {status === 'success' && result && (
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => onUploaded?.(result)}
          >
            Run analysis →
          </button>
        )}
      </div>

      {status === 'error' && <div className="banner banner--error">{error}</div>}

      {status === 'success' && result && (
        <div className="result">
          {callInfo && (
            <div className="call-confirm">
              <span className="call-confirm__dot" />
              Live call confirmed — <code>{callInfo.method}</code>{' '}
              <code>{callInfo.url}</code> responded in{' '}
              <strong>{callInfo.ms}ms</strong>
            </div>
          )}
          <div className="result__header">
            <span className="badge badge--success">success</span>
            <span className="result__label">API response</span>
          </div>
          <pre className="result__json">{JSON.stringify(result, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}
