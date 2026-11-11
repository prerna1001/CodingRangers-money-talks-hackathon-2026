import { Link, Navigate } from 'react-router-dom'
import { AuthCheck } from '../auth/AuthProvider'
import { useAuth } from '../auth/authContext'
import Tick from '../components/Tick'
import './SignInPage.css'

// Where "Navigate to app" lands for anyone not signed in. Log in and Sign up
// both hand off to Auth0's hosted page; sign-up only asks Auth0 to open on
// its sign-up screen (the backend's /auth/login forwards screen_hint).
export default function SignInPage() {
  const { auth, error } = useAuth()

  if (!auth) {
    return <AuthCheck error={error} />
  }

  // Already signed in: nothing to do here.
  if (auth.authenticated) {
    return <Navigate to="/app" replace />
  }

  const configured = Boolean(auth.login_url)

  const startAuth = (signup) => {
    // Record where the visitor came from so /auth/callback can send them
    // back to the app even though Vite is on a different port than the
    // backend. Cookies ignore ports, so localhost is enough to carry this
    // across the Auth0 round trip; the /app path makes the callback land
    // straight in the app instead of back on the homepage.
    document.cookie =
      `ledgerlight_app_origin=${encodeURIComponent(`${window.location.origin}/app`)}` +
      '; path=/; max-age=600; SameSite=Lax'
    const url = new URL(auth.login_url)
    if (signup) url.searchParams.set('screen_hint', 'signup')
    window.location.replace(url.toString())
  }

  return (
    <div className="page signin desk">
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="page__header signin__nav">
        <Link className="brand" to="/">
          <span className="brand__mark"><Tick /></span>
          <span className="brand__name">Ledgerlight</span>
        </Link>
      </header>

      <main id="main" tabIndex={-1} className="signin__main">
        <div className="signin__card stock">
          <h1>Sign in to Ledgerlight</h1>
          <p className="signin__lead">Your analyses and memories stay with your account.</p>

          <div className="signin__actions">
            <button
              type="button"
              className="btn btn--primary btn--lg"
              onClick={() => startAuth(false)}
              disabled={!configured}
            >
              Log in
            </button>
            <button
              type="button"
              className="btn btn--lg"
              onClick={() => startAuth(true)}
              disabled={!configured}
            >
              Create an account
            </button>
          </div>

          {configured ? (
            <p className="signin__fine">You will continue on Auth0, then come straight back to the app.</p>
          ) : (
            <div className="signin__notice" role="status">
              <p>
                Sign-in is not set up on this server yet. Add the Auth0 keys to <code>backend/.env</code> and
                restart the backend. Until then the app is open to everyone.
              </p>
              {!auth.auth_required && (
                <Link className="signin__continue" to="/app">
                  Continue to the app
                </Link>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
