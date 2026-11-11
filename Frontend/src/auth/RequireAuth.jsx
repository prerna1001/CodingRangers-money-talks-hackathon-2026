import { Navigate } from 'react-router-dom'
import { AuthCheck } from './AuthProvider'
import { canEnterApp, useAuth } from './authContext'

// Guards /app: anonymous visitors are sent to the sign-in page (never
// straight to Auth0 -- that page owns the Log in and Sign up buttons),
// `replace` so the back button doesn't return them to a route they cannot see.
export default function RequireAuth({ children }) {
  const { auth, error } = useAuth()

  if (!auth) {
    return <AuthCheck error={error} />
  }

  if (!canEnterApp(auth)) {
    return <Navigate to="/signin" replace />
  }

  return children
}
