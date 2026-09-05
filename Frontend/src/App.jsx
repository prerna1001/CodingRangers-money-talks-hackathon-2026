import { useRef, useState } from 'react'
import UploadCard from './components/UploadCard'
import AgentTimeline from './components/AgentTimeline'
import Dashboard from './components/dashboard/Dashboard'
import { analyzeRun } from './services/api'
import './App.css'

const PIPELINE_STEPS = [
  { name: 'Profile Builder', status: 'passed', duration_ms: 450 },
  { name: 'Fetch Tester / Data QA', status: 'passed_with_warnings', duration_ms: 380 },
  { name: 'Memory Agent', status: 'passed', duration_ms: 260 },
  { name: 'RAG Agent', status: 'passed', duration_ms: 320 },
  { name: 'Analyzer / Researcher', status: 'passed', duration_ms: 600 },
  { name: 'Safety Guardrail', status: 'passed', duration_ms: 260 },
  { name: 'Stress Test', status: 'passed', duration_ms: 340 },
  { name: 'Report Writer', status: 'passed', duration_ms: 200 },
]

// phase: 'upload' -> 'analyzing' -> 'dashboard'
// 'analyzing' waits on two independent things: the timeline animation
// finishing its playback, and the real /api/analyze call resolving.
// Only once both are true do we move to 'dashboard' — so a slow backend
// doesn't cut the animation short, and a fast backend doesn't skip it.
// Tracked via refs (not effect-derived state) since the transition is
// triggered from two separate callbacks, not from a render-time value.
function App() {
  const [phase, setPhase] = useState('upload')
  const [analysis, setAnalysis] = useState(null)
  const [error, setError] = useState(null)
  const timelineDoneRef = useRef(false)
  const analysisRef = useRef(null)

  const tryEnterDashboard = () => {
    if (timelineDoneRef.current && analysisRef.current) {
      setPhase('dashboard')
    }
  }

  const handleUploaded = async () => {
    timelineDoneRef.current = false
    analysisRef.current = null
    setPhase('analyzing')
    setAnalysis(null)
    setError(null)
    try {
      const res = await analyzeRun()
      analysisRef.current = res
      setAnalysis(res)
      tryEnterDashboard()
    } catch (err) {
      setError(err.message || 'Analysis failed')
      setPhase('upload')
    }
  }

  const handleTimelineComplete = () => {
    timelineDoneRef.current = true
    tryEnterDashboard()
  }

  const handleReset = () => {
    setPhase('upload')
    setAnalysis(null)
    timelineDoneRef.current = false
    analysisRef.current = null
    setError(null)
  }

  return (
    <div className="page">
      <header className="page__header">
        <div className="brand">
          <span className="brand__mark">FE</span>
          <span className="brand__name">FinOps Explain AI</span>
        </div>
        <span className="page__tagline">Money operations, explained with evidence</span>
      </header>

      <main className="page__main">
        {phase === 'upload' && (
          <div className="page__stack">
            {error && <div className="banner banner--error">{error}</div>}
            <UploadCard onUploaded={handleUploaded} />
          </div>
        )}

        {phase === 'analyzing' && (
          <AgentTimeline steps={PIPELINE_STEPS} onComplete={handleTimelineComplete} />
        )}

        {phase === 'dashboard' && analysis && (
          <Dashboard analysis={analysis} onReset={handleReset} />
        )}
      </main>
    </div>
  )
}

export default App
