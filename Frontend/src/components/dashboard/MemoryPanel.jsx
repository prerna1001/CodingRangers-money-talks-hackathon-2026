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
          <h3>Memory</h3>
          <p>What the agent remembers from previous runs — opt-in, editable, deletable</p>
        </div>
        {source && (
          <span className="source-tag">
            <code>{source.method}</code> <code>{source.url}</code>
          </span>
        )}
      </div>

      <p className="memory-panel__stat">
        <strong>{usedCount}</strong> of {memories.length} memories influenced this run
      </p>

      <ul className="memory-list">
        {memories.map((m) => (
          <li key={m.memory_id} className={`memory-item ${m.deleting ? 'memory-item--deleting' : ''}`}>
            <div className="memory-item__top">
              <span className="memory-item__type">{m.memory_type.replace(/_/g, ' ')}</span>
              {m.used_in_this_run && <span className="badge badge--success">used this run</span>}
            </div>
            <p className="memory-item__content">{m.content}</p>
            <div className="memory-item__footer">
              <span className="memory-item__confidence">confidence {Math.round(m.confidence * 100)}%</span>
              <span className="memory-item__evidence">{m.evidence.join(', ')}</span>
              <button
                type="button"
                className="memory-item__delete"
                onClick={() => handleDelete(m.memory_id)}
                disabled={m.deleting}
              >
                {m.deleting ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
