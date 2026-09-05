import { useEffect, useRef, useState } from 'react'
import './AgentTimeline.css'

const STATUS_LABEL = {
  passed: 'Passed',
  passed_with_warnings: 'Passed with warnings',
}

// Plays back the analyze response's agent_timeline as a sequential
// running -> done animation (this is the "Agent Run Timeline" dashboard
// feature from the plan doc, reused as the processing state after upload).
export default function AgentTimeline({ steps, onComplete }) {
  const [activeIndex, setActiveIndex] = useState(-1)
  const [doneIndices, setDoneIndices] = useState([])
  const completedRef = useRef(false)

  useEffect(() => {
    let cancelled = false
    let i = 0

    const advance = () => {
      if (cancelled) return
      if (i >= steps.length) {
        if (!completedRef.current) {
          completedRef.current = true
          onComplete?.()
        }
        return
      }
      setActiveIndex(i)
      const stepDuration = Math.min(steps[i].duration_ms ?? 400, 700)
      setTimeout(() => {
        if (cancelled) return
        setDoneIndices((prev) => [...prev, i])
        i += 1
        advance()
      }, stepDuration)
    }

    advance()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [steps])

  const progressPct = Math.round((doneIndices.length / steps.length) * 100)

  return (
    <div className="agent-timeline">
      <div className="agent-timeline__header">
        <h2>Running analysis</h2>
        <p>Multi-agent pipeline is processing your data</p>
      </div>

      <div className="agent-timeline__bar">
        <div className="agent-timeline__bar-fill" style={{ width: `${progressPct}%` }} />
      </div>
      <div className="agent-timeline__pct">{progressPct}%</div>

      <ul className="agent-timeline__list">
        {steps.map((step, idx) => {
          const isDone = doneIndices.includes(idx)
          const isActive = activeIndex === idx && !isDone
          const state = isDone ? 'done' : isActive ? 'running' : 'pending'
          return (
            <li key={step.name} className={`agent-step agent-step--${state}`}>
              <span className="agent-step__icon">
                {state === 'done' && '✓'}
                {state === 'running' && <span className="agent-step__spinner" />}
                {state === 'pending' && idx + 1}
              </span>
              <span className="agent-step__name">{step.name}</span>
              {isDone && (
                <span className="agent-step__status">
                  {STATUS_LABEL[step.status] || step.status}
                </span>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
