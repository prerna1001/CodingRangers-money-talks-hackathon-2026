// Accounting-style number formatting shared by the dashboard: negatives in
// parentheses, whole dollars, tabular figures come from the CSS.

export function toNumber(value) {
  return Number(value) || 0
}

// 183000 -> "$183,000"; -9000 -> "($9,000)"
export function ledgerMoney(value) {
  const n = toNumber(value)
  const body = `$${Math.round(Math.abs(n)).toLocaleString('en-US')}`
  return n < 0 ? `(${body})` : body
}

// Same, but positive changes carry an explicit "+" so a variance reads as one.
export function ledgerChange(value) {
  const n = toNumber(value)
  return n > 0 ? `+${ledgerMoney(n)}` : ledgerMoney(n)
}

// 183000 -> "$183K", 1500 -> "$1.5K"; used where space is tight (chart axes).
export function compactMoney(value) {
  const n = toNumber(value)
  const abs = Math.abs(n)
  let body
  if (abs >= 1_000_000) body = `$${(abs / 1_000_000).toFixed(abs >= 10_000_000 ? 0 : 1)}M`
  else if (abs >= 1000) body = `$${(abs / 1000).toFixed(abs >= 10000 ? 0 : 1)}K`
  else body = `$${Math.round(abs)}`
  return n < 0 ? `(${body})` : body
}

export function percent(fraction) {
  return `${Math.round(toNumber(fraction) * 100)}%`
}
