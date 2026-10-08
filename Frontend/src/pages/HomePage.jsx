import { Link } from 'react-router-dom'
import { AuthCheck } from '../auth/AuthProvider'
import { canEnterApp, useAuth } from '../auth/authContext'

// Public landing page: reachable signed in or not, never redirects on its
// own. The only outbound hop is the explicit "Log in" click.
export default function HomePage() {
  const { auth, error } = useAuth()

  if (!auth) {
    return <AuthCheck error={error} />
  }

  const handleLogin = () => {
    // Record where the visitor came from so /auth/callback can send them
    // back to the app even though Vite is on a different port than the
    // backend. Cookies ignore ports, so localhost is enough to carry this
    // across the Auth0 round trip; the /app path makes the callback land
    // straight in the app instead of back on this homepage.
    document.cookie =
      `ledgerlight_app_origin=${encodeURIComponent(`${window.location.origin}/app`)}` +
      '; path=/; max-age=600; SameSite=Lax'
    window.location.replace(auth.login_url)
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

      <main className="page__main home__main">
        <div className="home__card">
          <h1 className="home__title">FinOps Explain AI</h1>
          <p className="home__lead">
            Upload monthly account summaries or transaction-level CSVs and get an
            evidence-backed explanation of your numbers.
          </p>
          {canEnterApp(auth) ? (
            <Link className="btn btn--primary home__cta" to="/app">
              Navigate to app
            </Link>
          ) : (
            <button className="btn btn--primary home__cta" type="button" onClick={handleLogin}>
              Log in
            </button>
          )}
        </div>
      </main>
    </div>
  )
}
