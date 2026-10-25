import { useEffect, useState } from 'react'
import { fetchRagEvidence } from '../../services/mockApi'
import './RagPanel.css'

export default function RagPanel() {
  const [items, setItems] = useState(null)
  const [source, setSource] = useState(null)

  useEffect(() => {
    fetchRagEvidence().then((res) => {
      setItems(res.evidence)
      setSource(res)
    })
  }, [])

  if (!items) return <p className="panel-loading">Retrieving context…</p>

  return (
    <div className="rag-panel">
      <div className="panel-heading">
        <div>
          <h2>Retrieved context</h2>
          <p>Earlier reports, policies and definitions Ledgerlight looked up before writing the explanation</p>
        </div>
        {source && (
          <span className="source-tag">
            <code>{source.method}</code> <code>{source.url}</code>
          </span>
        )}
      </div>

      <ul className="rag-list">
        {items.map((item) => (
          <li key={item.title} className="rag-item">
            <div className="rag-item__top">
              <span className="rag-item__source">{item.source}</span>
              <span className="relevance">
                <span className="relevance__track" aria-hidden="true"><span style={{ width: `${Math.round(item.relevance * 100)}%` }} /></span>
                {Math.round(item.relevance * 100)}% match
              </span>
            </div>
            <p className="rag-item__title">{item.title}</p>
            <p className="rag-item__snippet">{item.snippet}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}
