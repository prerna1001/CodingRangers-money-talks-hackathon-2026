import { createContext, useContext } from 'react'

// Kept out of LanguageProvider.jsx so that file exports only a component
// (what React Fast Refresh needs to hot-reload it).
export const LanguageContext = createContext(null)

export const LANGUAGES = [
  { code: 'en', label: 'English', short: 'EN' },
  { code: 'es', label: 'Spanish', short: 'ES' },
]

export function useLanguage() {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used inside a LanguageProvider')
  return ctx
}
