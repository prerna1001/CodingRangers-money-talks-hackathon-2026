import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, AuthCheck } from './auth/AuthProvider'
import { canEnterApp, useAuth } from './auth/authContext'
import RequireAuth from './auth/RequireAuth'
import HomePage from './pages/HomePage'
import AppShell from './pages/AppShell'
import SignInPage from './pages/SignInPage'
import { LanguageProvider } from './i18n/LanguageProvider'
import './App.css'

// Unknown paths resolve by session: signed-in users end up in the app,
// everyone else on the sign-in page. `replace` keeps these off the history stack.
function CatchAll() {
  const { auth, error } = useAuth()

  if (!auth) {
    return <AuthCheck error={error} />
  }

  return <Navigate to={canEnterApp(auth) ? '/app' : '/signin'} replace />
}

function App() {
  return (
    <AuthProvider>
      <LanguageProvider>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/signin" element={<SignInPage />} />
          <Route
            path="/app"
            element={
              <RequireAuth>
                <AppShell />
              </RequireAuth>
            }
          />
          <Route path="*" element={<CatchAll />} />
        </Routes>
      </LanguageProvider>
    </AuthProvider>
  )
}

export default App
