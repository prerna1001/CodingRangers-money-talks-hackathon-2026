import { useEffect, useState } from 'react'
import { deleteMemory, fetchMemories } from '../../services/mockApi'
import './MemoryPanel.css'

export default function MemoryPanel() {
  const [memories, setMemories] = useState(null)
  const [source, setSource] = useState(null)

  useEffect(() => {
    fetchMemories().then((res) => {
      setMemories(res.memories)
      setSource(res)
    })
  }, [])

  const handleDelete = async (memoryId) => {
    setMemories((prev) => prev.map((m) => (m.memory_id === memoryId ? { ...m, deleting: true } : m)))
    await deleteMemory(memoryId)
    setMemories((prev) => prev.filter((m) => m.memory_id !== memoryId))
  }

  if (!memories) return <p className="panel-loading">Loading memories…</p>

  const usedCount = memories.filter((m) => m.used_in_this_run).length

  return (
    <div className="memory-panel">
      <div className="panel-heading">
        <div>
          <h2>Memory</h2>
          <p>What Ledgerlight remembers from earlier runs. Delete anything that is wrong and it will not be used again.</p>
        </div>
        {source && (
          <span className="source-tag">
            <code>{source.method}</code> <code>{source.url}</code>
          </span>
        )}
      </div>

      <p className="memory-panel__stat">
        <strong>{usedCount} of {memories.length}</strong> memories shaped this run
      </p>

      <ul className="memory-list">
        {memories.map((m) => (
          <li key={m.memory_id} className={`memory-item ${m.deleting ? 'memory-item--deleting' : ''}`}>
            <div className="memory-item__top">
              <span className="memory-item__type">{m.memory_type.charAt(0).toUpperCase() + m.memory_type.slice(1).replace(/_/g, ' ')}</span>
              {m.used_in_this_run && <span className="badge badge--success">Used in this run</span>}
            </div>
            <p className="memory-item__content">{m.content}</p>
            <div className="memory-item__footer">
              <span className="memory-item__confidence">{Math.round(m.confidence * 100)}% confidence</span>
              <span className="memory-item__evidence">Seen in {m.evidence.join(', ')}</span>
              <button
                type="button"
                className="memory-item__delete"
                onClick={() => handleDelete(m.memory_id)}
                disabled={m.deleting}
              >
                {m.deleting ? 'Deleting…' : 'Delete memory'}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
