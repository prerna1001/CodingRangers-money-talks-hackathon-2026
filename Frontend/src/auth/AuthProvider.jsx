import { useEffect, useState } from 'react'
import { fetchAuthStatus } from '../services/api'
import { AuthContext } from './authContext'

// The Auth0 session is a cookie, so whether it exists is a question only the
// backend can answer. Ask once on mount and share the answer with every route
// (homepage, guard, app shell) so the status is fetched a single time per page
// load. Nothing here redirects: signed-out visitors stay on the homepage and
// only leave when they click "Log in".
export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    fetchAuthStatus()
      .then((status) => {
        if (cancelled) return
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

  return <AuthContext.Provider value={{ auth, error }}>{children}</AuthContext.Provider>
}

// Full-page stand-in rendered while the session check is in flight or has
// failed, so nothing gated (and no CTA) flashes before we know who is asking.
export function AuthCheck({ error }) {
  return (
    <div className="page">
      <main className="page__main">
        <div className="page__stack">
          <div className={error ? 'banner banner--error' : 'banner'}>
            {error ? `${error} — is the backend running on port 8000?` : 'Checking your session…'}
          </div>
        </div>
      </main>
    </div>
  )
}
