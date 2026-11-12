import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { translateTexts } from '../services/api'
import { catalogLookup } from './catalog'
import { LanguageContext } from './context'

const STORAGE_KEY = 'finops.language'
const CACHE_KEY = 'finops.translations'
// Collect every t() miss from one render pass and send them as a single
// request, instead of one fetch per label.
const BATCH_DELAY_MS = 40

function loadCache() {
  try {
    return JSON.parse(sessionStorage.getItem(CACHE_KEY)) ?? {}
  } catch {
    return {}
  }
}

function saveCache(cache) {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(cache))
  } catch {
    // sessionStorage can be unavailable or full — the in-memory cache still works
  }
}

/**
 * Screen translation for the whole app.
 *
 * t(text) is synchronous and always returns something renderable:
 *   1. English unchanged when the language is English;
 *   2. the hand-written catalog entry when there is one (UI chrome);
 *   3. a cached machine translation;
 *   4. the English text, while the backend translates it in the background.
 *
 * Step 4 is what makes this work for text nobody wrote by hand — the LLM's
 * headline, drivers and chat answers — without blocking the first paint.
 * Misses are batched, cached in sessionStorage, and the model itself caches
 * per string on the backend, so a toggle back and forth is instant.
 */
export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(() => {
    try {
      return sessionStorage.getItem(STORAGE_KEY) || 'en'
    } catch {
      return 'en'
    }
  })
  const [cache, setCache] = useState(loadCache)
  const [failed, setFailed] = useState(false)

  // Strings waiting to go out, and the timer that will send them.
  const pendingRef = useRef(new Set())
  // Strings already sent and not yet answered, so a re-render while a slow
  // CPU translation is running does not send them again.
  const sentRef = useRef(new Set())
  const timerRef = useRef(null)

  const setLanguage = useCallback((next) => {
    setLanguageState(next)
    setFailed(false)
    try {
      sessionStorage.setItem(STORAGE_KEY, next)
    } catch {
      // not fatal — the choice just won't survive a reload
    }
  }, [])

  const flush = useCallback(async (target) => {
    const texts = [...pendingRef.current]
    pendingRef.current = new Set()
    timerRef.current = null
    if (texts.length === 0) return
    texts.forEach((text) => sentRef.current.add(text))

    try {
      const translations = await translateTexts(texts, target)
      setCache((prev) => {
        const next = { ...prev }
        texts.forEach((text, i) => {
          next[`${target}:${text}`] = translations[i] ?? text
        })
        saveCache(next)
        return next
      })
    } catch {
      // Leave the English text on screen rather than blanking the UI; the
      // toggle shows that translation is unavailable.
      setFailed(true)
    } finally {
      texts.forEach((text) => sentRef.current.delete(text))
    }
  }, [])

  const request = useCallback(
    (target, text) => {
      if (sentRef.current.has(text)) return
      pendingRef.current.add(text)
      if (timerRef.current) return
      timerRef.current = setTimeout(() => flush(target), BATCH_DELAY_MS)
    },
    [flush],
  )

  useEffect(() => () => clearTimeout(timerRef.current), [])

  const t = useCallback(
    (text) => {
      if (typeof text !== 'string' || !text.trim()) return text
      if (language === 'en') return text

      const fromCatalog = catalogLookup(language, text)
      if (fromCatalog) return fromCatalog

      const hit = cache[`${language}:${text}`]
      if (hit) return hit

      if (!failed) request(language, text)
      return text
    },
    [language, failed, request, cache],
  )

  // Lets the page-wide translator (PageTranslator) share this cache, so a
  // string translated once is never sent twice, whichever path asked for it.
  const remember = useCallback((target, texts, translations) => {
    setCache((prev) => {
      const next = { ...prev }
      texts.forEach((text, i) => {
        next[`${target}:${text}`] = translations[i] ?? text
      })
      saveCache(next)
      return next
    })
  }, [])

  const value = useMemo(
    () => ({ language, setLanguage, t, translationFailed: failed, cache, remember, setFailed }),
    [language, setLanguage, t, failed, cache, remember],
  )

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}
