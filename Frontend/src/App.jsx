import { useEffect, useRef, useState } from 'react'
import UploadCard from './components/UploadCard'
import AgentTimeline from './components/AgentTimeline'
import Dashboard from './components/dashboard/Dashboard'
import { analyzeRun, fetchAuthStatus } from './services/api'
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

// The Auth0 session is a cookie, so whether it exists is a question only the
// backend can answer. We ask once on mount and hold the app back until it
// replies -- otherwise the dashboard would flash on screen for the ~50ms
// before we redirect an anonymous visitor to the login screen. `replace` (not
// `assign`) so the back button doesn't bounce them into the redirect loop.
function useAuthGate() {
  const [auth, setAuth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    fetchAuthStatus()
      .then((status) => {
        if (cancelled) return
        if (status.auth_required && !status.authenticated) {
          // Record where the visitor came from so /auth/callback can send
          // them back here even though Vite is on a different port than the
          // backend. Cookies ignore ports, so localhost is enough to carry
          // this across the Auth0 round trip.
          document.cookie =
            `ledgerlight_app_origin=${encodeURIComponent(window.location.origin)}` +
            '; path=/; max-age=600; SameSite=Lax'
          window.location.replace(status.login_url)
          return
        }
        setAuth(status)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err.message || 'Could not reach the backend')
      })

    return () => {
      cancelled = true
    }
  }, [])

  return { auth, error }
}

// phase: 'upload' -> 'analyzing' -> 'dashboard'
// 'analyzing' waits on two independent things: the timeline animation
// finishing its playback, and the real /api/analyze call resolving.
// Only once both are true do we move to 'dashboard' — so a slow backend
// doesn't cut the animation short, and a fast backend doesn't skip it.
// Tracked via refs (not effect-derived state) since the transition is
// triggered from two separate callbacks, not from a render-time value.
function App() {
  const { auth, error: authError } = useAuthGate()
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

  // `uploaded` is the array of /api/upload responses (UploadCard passes it
  // through). analyzeRun splits them into transaction vs period-summary ids;
  // with none, the backend falls back to its built-in demo dataset.
  const handleUploaded = async (uploaded) => {
    timelineDoneRef.current = false
    analysisRef.current = null
    setPhase('analyzing')
    setAnalysis(null)
    setError(null)
    try {
      const res = await analyzeRun(uploaded)
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

  // Nothing renders until the session check resolves, so an anonymous
  // visitor never sees the dashboard flash before the redirect.
  if (authError) {
    return (
      <div className="page">
        <main className="page__main">
          <div className="page__stack">
            <div className="banner banner--error">
              {authError} — is the backend running on port 8000?
            </div>
          </div>
        </main>
      </div>
    )
  }

  if (!auth) {
    return (
      <div className="page">
        <main className="page__main">
          <div className="page__stack">
            <div className="banner">Checking your session&hellip;</div>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="page">
      <header className="page__header">
        <div className="brand">
          <span className="brand__mark">FE</span>
          <span className="brand__name">FinOps Explain AI</span>
        </div>
        <span className="page__tagline">Money operations, explained with evidence</span>
        {auth.authenticated && auth.logout_url && (
          <a className="page__signout" href={auth.logout_url}>Sign out</a>
        )}
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
