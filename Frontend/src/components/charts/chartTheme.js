// Shared axis / tooltip styling so every chart reads as one system.
export function baseOption(t) {
  return {
    animationDuration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 500,
    textStyle: { fontFamily: t.sans, color: t.text },
    tooltip: {
      backgroundColor: t.surfaceRaised,
      borderColor: t.borderStrong,
      textStyle: { color: t.textH, fontFamily: t.sans, fontSize: 13 },
      extraCssText: 'box-shadow: 0 8px 24px -12px rgba(0,0,0,.35); border-radius: 6px;',
    },
  }
}

export function valueAxis(t, formatter, extra = {}) {
  return {
    type: 'value',
    axisLabel: { color: t.textDim, fontSize: 12, formatter },
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
    axisLabel: { color: t.text, fontSize: 12.5, fontWeight: 600 },
    axisLine: { lineStyle: { color: t.borderStrong } },
    axisTick: { show: false },
    ...extra,
  }
}
