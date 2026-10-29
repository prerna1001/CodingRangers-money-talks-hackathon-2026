import { Navigate } from 'react-router-dom'
import { AuthCheck } from './AuthProvider'
import { canEnterApp, useAuth } from './authContext'

// Guards /app: anonymous visitors are sent back to the homepage (never to
// Auth0 -- the homepage owns the "Log in" button), `replace` so the back
// button doesn't return them to a route they cannot see.
export default function RequireAuth({ children }) {
  const { auth, error } = useAuth()

  if (!auth) {
    return <AuthCheck error={error} />
  }

  if (!canEnterApp(auth)) {
    return <Navigate to="/" replace />
  }

  return children
}
