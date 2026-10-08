import { createContext, useContext } from 'react'

export const AuthContext = createContext(null)

export function useAuth() {
  return useContext(AuthContext)
}

// Signed in, or auth switched off for local work -- either way the app opens.
export function canEnterApp(auth) {
  return Boolean(auth) && (!auth.auth_required || auth.authenticated)
}
