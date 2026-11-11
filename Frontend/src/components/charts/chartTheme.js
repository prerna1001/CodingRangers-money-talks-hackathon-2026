// Shared axis / tooltip / motion styling so every chart reads as one system:
// labels in the body face, figures in the mono face, ink rules, and marks
// that build in one after another instead of all at once.

export const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

// Per-mark stagger: mark n starts `step` ms after mark n-1.
export function stagger(step = 90, offset = 0) {
  return reducedMotion() ? 0 : (index) => offset + index * step
}

export function baseOption(t) {
  const still = reducedMotion()
  return {
    animation: !still,
    animationDuration: still ? 0 : 700,
    animationEasing: 'cubicOut',
    animationDurationUpdate: still ? 0 : 450,
    animationEasingUpdate: 'cubicInOut',
    textStyle: { fontFamily: t.sans, color: t.text },
    tooltip: {
      backgroundColor: t.surfaceRaised,
      borderColor: t.borderStrong,
      borderWidth: 1,
      padding: [10, 12],
      textStyle: { color: t.textH, fontFamily: t.sans, fontSize: 13, lineHeight: 20 },
      extraCssText: 'border-radius: 8px; box-shadow: 6px 5px 10px -6px rgba(60, 45, 30, 0.3);',
    },
  }
}

// Figures (money, percentages) are set in the mono face so they align.
export function figureLabel(t, extra = {}) {
  return { fontFamily: t.mono, fontSize: 12, color: t.textDim, ...extra }
}

export function valueAxis(t, formatter, extra = {}) {
  return {
    type: 'value',
    axisLabel: { ...figureLabel(t), formatter },
    splitLine: { lineStyle: { color: t.chartGrid } },
    axisLine: { show: false },
    axisTick: { show: false },
    ...extra,
  }
}

export function categoryAxis(t, data, extra = {}) {
  return {
    type: 'category',
    data,
    axisLabel: { color: t.text, fontSize: 12.5, fontWeight: 500 },
    axisLine: { lineStyle: { color: t.textH } },
    axisTick: { show: false },
    ...extra,
  }
}
