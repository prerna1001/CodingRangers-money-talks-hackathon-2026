import { useCallback, useRef, useState } from 'react'
import { uploadFiles } from '../services/api'
import './UploadCard.css'

const ACCEPTED_FORMATS = '.csv,.xlsx,.pdf,.docx,.txt,.json,.jpeg,.jpg,.png,.webp,.tiff,.heic'

function formatBytes(bytes) {
  if (!bytes) return '0 KB'
  const kb = bytes / 1024
  return kb < 1024 ? `${kb.toFixed(1)} KB` : `${(kb / 1024).toFixed(1)} MB`
}

function companyId(name) {
  return (name || 'analysis').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '') || 'analysis'
}

export default function UploadCard({ onUploaded }) {
  const [files, setFiles] = useState([])
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const [isDragging, setIsDragging] = useState(false)
  const [context, setContext] = useState({
    company_name: '',
    industry: '',
    business_model: '',
    business_context: '',
  })
  const inputRef = useRef(null)

  const updateContext = (event) => {
    const { name, value } = event.target
    setContext((current) => ({ ...current, [name]: value }))
  }

  const handleFile = useCallback((selected) => {
    const picked = Array.from(selected || []).filter(Boolean)
    if (!picked.length) return
    setFiles((current) => {
      const merged = [...current]
      picked.forEach((file) => {
        if (!merged.some((candidate) => candidate.name === file.name && candidate.size === file.size)) merged.push(file)
      })
      return merged
    })
    setError(null)
  }, [])

  const handleDrop = useCallback((event) => {
    event.preventDefault()
    setIsDragging(false)
    handleFile(event.dataTransfer.files)
  }, [handleFile])

  const removeFile = (file) => setFiles((current) => current.filter((candidate) => !(candidate.name === file.name && candidate.size === file.size)))

  const startAnalysis = async () => {
    if (!files.length) return
    setStatus('uploading')
    setError(null)
    try {
      const uploads = await uploadFiles(files, { companyId: companyId(context.company_name) })
      const ready = uploads.filter((upload) => upload.review_status === 'ready' && upload.file_type)
      if (!ready.length) {
        throw new Error('No uploaded file contains a recognizable transaction or period-summary table. Add a spreadsheet, statement, or document table with dates and amounts.')
      }
      onUploaded?.({ uploads, context })
    } catch (err) {
      setError(err.message || 'Could not extract the uploaded financial files')
      setStatus('error')
    }
  }

  return (
    <div className="upload-card upload-card--batch">
      <div className="upload-card__header">
        <h1>Explain what changed between two periods</h1>
        <p>Add the statements, exports and notes for both periods. Ledgerlight checks the data, works out what drove the change, and traces every figure back to its transactions.</p>
      </div>

      <fieldset className="context">
        <legend>About the business <span>optional, sharpens the explanation</span></legend>
        <div className="context-grid">
        <label>Company name<input name="company_name" autoComplete="organization" value={context.company_name} onChange={updateContext} placeholder="Northstar Commerce" /></label>
        <label>Industry<input name="industry" value={context.industry} onChange={updateContext} placeholder="E-commerce" /></label>
        <label className="context-grid__wide">Business model<input name="business_model" value={context.business_model} onChange={updateContext} placeholder="Subscription, marketplace, services..." /></label>
        <label className="context-grid__wide">Business context<textarea name="business_context" value={context.business_context} onChange={updateContext} placeholder="Seasonality, known campaigns, renewals, pricing changes, or questions to investigate" rows="3" /></label>
        </div>
      </fieldset>

      <div
        className={`dropzone ${isDragging ? 'dropzone--active' : ''} ${files.length ? 'dropzone--filled' : ''}`}
        onDragOver={(event) => { event.preventDefault(); setIsDragging(true) }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        {...(!files.length && {
          onClick: () => inputRef.current?.click(),
          onKeyDown: (event) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault()
              inputRef.current?.click()
            }
          },
          role: 'button',
          tabIndex: 0,
          'aria-label': 'Add financial files',
        })}
      >
        <input ref={inputRef} type="file" accept={ACCEPTED_FORMATS} multiple hidden onChange={(event) => handleFile(event.target.files)} />
        {!files.length ? (
          <>
            <svg className="dropzone__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 16V4M12 4L7 9M12 4L17 9M5 20H19" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" /></svg>
            <p className="dropzone__title">Drop files here, or browse</p>
            <p className="dropzone__subtitle">Spreadsheets, PDFs, documents and photos of statements</p>
          </>
        ) : (
          <div className="file-chip-list">
            {files.map((file) => (
              <div className="file-chip" key={`${file.name}-${file.size}`}>
                <svg className="file-chip__icon" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" /><path d="M14 3v5h5" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" /></svg>
                <div className="file-chip__meta"><span className="file-chip__name">{file.name}</span><span className="file-chip__size">{formatBytes(file.size)}</span></div>
                <button type="button" className="file-chip__remove" onClick={(event) => { event.stopPropagation(); removeFile(file) }} aria-label={`Remove ${file.name}`}>×</button>
              </div>
            ))}
            <div className="file-chip-list__more">
              <button type="button" className="btn btn--ghost btn--sm" onClick={() => inputRef.current?.click()}>
                Add more files
              </button>
              <span className="file-chip-list__hint">or drop them here</span>
            </div>
          </div>
        )}
      </div>

      <div className="upload-card__actions">
        <button type="button" className="btn btn--primary" disabled={!files.length || status === 'uploading'} onClick={startAnalysis}>
          {status === 'uploading' ? <><span className="spinner" /> Reading files…</> : files.length ? `Analyze ${files.length} ${files.length === 1 ? 'file' : 'files'}` : 'Analyze files'}
        </button>
      </div>
      {error && <div className="banner banner--error" role="alert">{error}</div>}
    </div>
  )
}
