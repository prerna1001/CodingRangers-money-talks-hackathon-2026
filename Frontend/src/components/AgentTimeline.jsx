import { useEffect, useRef, useState } from 'react'
import Tick from './Tick'
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

  const totalSteps = Math.max(steps.length, 1)
  const progressPct = Math.round((doneIndices.length / totalSteps) * 100)
  const finalizing = doneIndices.length >= steps.length

  return (
    <div className={`agent-timeline ${finalizing ? 'agent-timeline--finalizing' : ''}`}>
      <div className="agent-timeline__header">
        <h1>{finalizing ? 'Writing up the results' : 'Working through your files'}</h1>
        <p>
          {finalizing
            ? 'Every check has run. Waiting for the finished explanation.'
            : 'Each step below checks or builds on the one before it.'}
        </p>
      </div>

      <div className="agent-timeline__bar" role="progressbar" aria-valuenow={progressPct} aria-valuemin={0} aria-valuemax={100} aria-label="Analysis progress">
        <div className="agent-timeline__bar-fill" style={{ width: `${progressPct}%` }} />
      </div>

      <ol className="agent-timeline__list" aria-live="polite">
        {steps.map((step, idx) => {
          const isDone = doneIndices.includes(idx)
          const isActive = activeIndex === idx && !isDone
          const state = isDone ? 'done' : isActive ? 'running' : 'pending'
          return (
            <li key={step.name} className={`agent-step agent-step--${state}`}>
              <span className="agent-step__icon">
                {state === 'done' && <Tick />}
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
        {finalizing && (
          <li className="agent-step agent-step--running">
            <span className="agent-step__icon">
              <span className="agent-step__spinner" />
            </span>
            <span className="agent-step__name">Explanation and dashboard</span>
            <span className="agent-step__status">In progress</span>
          </li>
        )}
      </ol>
    </div>
  )
}
