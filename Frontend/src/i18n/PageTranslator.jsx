import { useEffect, useRef } from 'react'
import { translateTexts } from '../services/api'
import { CATALOG, catalogLookup } from './catalog'
import { useLanguage } from './context'

// Translates everything visible inside `rootRef` when the language is not
// English: labels, explanations, retrieved context, memories, stress-test
// results, evidence, chat answers, placeholders and tooltips.
//
// Components keep rendering English. This walks the rendered text, swaps
// each piece for its translation (the hand-written catalog first, then the
// shared machine-translation cache, then a batched request to
// /api/translate), and remembers the English so switching back restores it.
// A MutationObserver picks up whatever React renders next: a new tab, a
// chat reply, a run that just finished.
//
// Left alone: figures and code (`.fig`, `code`), charts (`svg`), form values,
// and anything marked `data-no-translate` or `translate="no"`.

const SKIP = 'svg, code, pre, script, style, textarea, input, select, .fig, [data-no-translate], [translate="no"]'
const ATTRS = ['placeholder', 'title', 'aria-label']
const HAS_LETTERS = /\p{L}{2,}/u
const MAX_CHARS = 2000
const BATCH = 80
const SETTLE_MS = 80

const catalogOutputs = new Set(Object.values(CATALOG).flatMap((table) => Object.values(table)))

function split(value) {
  const lead = value.match(/^\s*/)[0]
  const trail = value.slice(lead.length).match(/\s*$/)[0]
  return { lead, core: value.slice(lead.length, value.length - trail.length), trail }
}

function translatable(core) {
  return core.length > 1 && core.length <= MAX_CHARS && HAS_LETTERS.test(core)
}

export default function PageTranslator({ rootRef }) {
  const { language, cache, remember, setFailed } = useLanguage()
  const stateRef = useRef({
    texts: new Map(), // text node -> { src, out }
    attrs: new Map(), // element -> { [attr]: { src, out } }
    pending: new Set(),
    sent: new Set(), // strings already on their way to /api/translate
    inflight: false,
    broken: false,
    timer: null,
    observer: null,
  })

  useEffect(() => {
    const root = rootRef.current
    if (!root) return undefined
    const state = stateRef.current
    state.broken = false

    const lookup = (core) => catalogLookup(language, core) || cache[`${language}:${core}`]

    // Text that is already a translation (a t() call, the catalog) must not
    // be translated a second time. Built once per pass, not per node.
    let outputs = catalogOutputs
    const refreshOutputs = () => {
      outputs = new Set(catalogOutputs)
      const prefix = `${language}:`
      Object.entries(cache).forEach(([key, value]) => {
        if (key.startsWith(prefix) && value !== key.slice(prefix.length)) outputs.add(value)
      })
    }
    const isOutput = (core) => outputs.has(core)

    const restore = () => {
      state.texts.forEach((rec, node) => {
        if (node.isConnected && node.nodeValue === rec.out) node.nodeValue = rec.src
      })
      state.attrs.forEach((recs, el) => {
        Object.entries(recs).forEach(([attr, rec]) => {
          if (el.isConnected && el.getAttribute(attr) === rec.out) el.setAttribute(attr, rec.src)
        })
      })
      state.texts.clear()
      state.attrs.clear()
      state.observer?.takeRecords()
    }

    const flush = async () => {
      if (state.inflight || state.broken || state.pending.size === 0) return
      state.inflight = true
      const batch = [...state.pending].slice(0, BATCH)
      batch.forEach((text) => {
        state.pending.delete(text)
        state.sent.add(text)
      })
      try {
        const out = await translateTexts(batch, language)
        remember(language, batch, out)
        batch.forEach((text) => state.sent.delete(text))
      } catch {
        // Leave English on screen; the language toggle shows the warning.
        state.broken = true
        setFailed(true)
      } finally {
        state.inflight = false
        if (state.pending.size) flush()
      }
    }

    const pass = () => {
      state.timer = null
      if (language === 'en') {
        restore()
        return
      }

      refreshOutputs()
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        const parent = node.parentElement
        if (!parent || parent.closest(SKIP)) continue
        const rec = state.texts.get(node)
        const value = node.nodeValue
        if (rec && value === rec.out) continue
        const { lead, core, trail } = split(value)
        if (!translatable(core)) continue
        if (isOutput(core)) {
          state.texts.delete(node)
          continue
        }
        const hit = lookup(core)
        if (hit) {
          const out = `${lead}${hit}${trail}`
          state.texts.set(node, { src: value, out })
          if (out !== value) node.nodeValue = out
        } else {
          if (!state.sent.has(core)) state.pending.add(core)
        }
      }

      root.querySelectorAll(ATTRS.map((a) => `[${a}]`).join(',')).forEach((el) => {
        if (el.closest('[data-no-translate], [translate="no"]')) return
        ATTRS.forEach((attr) => {
          const value = el.getAttribute(attr)
          if (value == null) return
          const recs = state.attrs.get(el) || {}
          if (recs[attr] && value === recs[attr].out) return
          const core = value.trim()
          if (!translatable(core) || isOutput(core)) return
          const hit = lookup(core)
          if (hit) {
            recs[attr] = { src: value, out: hit }
            state.attrs.set(el, recs)
            if (hit !== value) el.setAttribute(attr, hit)
          } else {
            if (!state.sent.has(core)) state.pending.add(core)
          }
        })
      })

      // Our own writes are not new content: drop the records they caused.
      state.observer?.takeRecords()
      flush()
    }

    const schedule = () => {
      if (state.timer) return
      state.timer = setTimeout(pass, SETTLE_MS)
    }

    state.observer = new MutationObserver(schedule)
    state.observer.observe(root, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ATTRS,
    })
    pass()

    return () => {
      state.observer?.disconnect()
      state.observer = null
      clearTimeout(state.timer)
      state.timer = null
    }
    // cache: a finished batch re-runs the pass, which applies it.
  }, [language, cache, remember, setFailed, rootRef])

  return null
}
