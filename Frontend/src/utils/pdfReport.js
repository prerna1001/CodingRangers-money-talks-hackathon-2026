import jsPDF from 'jspdf'
import autoTable from 'jspdf-autotable'

const PAGE_WIDTH = 210
const PAGE_HEIGHT = 297
const MARGIN = 16
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN * 2

const COLOR = {
  accent: [15, 157, 112],
  accentDark: [10, 122, 86],
  accentBg: [223, 245, 236],
  textDark: [16, 20, 28],
  textDim: [110, 118, 132],
  textLight: [156, 163, 175],
  danger: [200, 48, 43],
  dangerBg: [252, 231, 230],
  amberText: [153, 105, 12],
  amberBg: [255, 243, 220],
  border: [228, 231, 236],
  panelBg: [247, 248, 250],
  white: [255, 255, 255],
}

function ensureSpace(doc, y, needed) {
  if (y + needed > PAGE_HEIGHT - MARGIN - 10) {
    doc.addPage()
    return MARGIN
  }
  return y
}

function setColor(doc, method, color) {
  doc[method](color[0], color[1], color[2])
}

function drawCoverHeader(doc, analysis) {
  doc.setFillColor(...COLOR.textDark)
  doc.rect(0, 0, PAGE_WIDTH, 34, 'F')

  doc.setFillColor(...COLOR.accent)
  doc.roundedRect(MARGIN, 10, 12, 12, 3, 3, 'F')
  doc.setFontSize(11)
  doc.setFont('helvetica', 'bold')
  setColor(doc, 'setTextColor', COLOR.white)
  doc.text('FE', MARGIN + 6, 17.5, { align: 'center' })

  doc.setFontSize(14)
  doc.setFont('helvetica', 'bold')
  doc.text('FinOps Explain AI', MARGIN + 18, 16)
  doc.setFontSize(9.5)
  doc.setFont('helvetica', 'normal')
  setColor(doc, 'setTextColor', [200, 210, 205])
  doc.text('Money operations, explained with evidence', MARGIN + 18, 21.5)

  doc.setFontSize(9)
  setColor(doc, 'setTextColor', [200, 210, 205])
  doc.text(`Run ${analysis.run_id || ''}`, PAGE_WIDTH - MARGIN, 14, { align: 'right' })
  doc.text(new Date().toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' }), PAGE_WIDTH - MARGIN, 19, {
    align: 'right',
  })

  return 46
}

function drawScoreCards(doc, y, analysis) {
  const gap = 6
  const cardWidth = (CONTENT_WIDTH - gap * 2) / 3
  const cardHeight = 24
  const cards = [
    { label: 'Confidence', value: `${Math.round(analysis.confidence * 100)}%` },
    { label: 'Data quality', value: `${Math.round(analysis.data_quality_score * 100)}%` },
    {
      label: `${analysis.periods.prior.label} -> ${analysis.periods.current.label}`,
      value: `$${(analysis.periods.current.revenue / 1000).toFixed(0)}k`,
    },
  ]

  cards.forEach((card, i) => {
    const x = MARGIN + i * (cardWidth + gap)
    doc.setFillColor(...COLOR.panelBg)
    doc.setDrawColor(...COLOR.border)
    doc.roundedRect(x, y, cardWidth, cardHeight, 2.5, 2.5, 'FD')

    doc.setFontSize(8.5)
    doc.setFont('helvetica', 'normal')
    setColor(doc, 'setTextColor', COLOR.textDim)
    doc.text(card.label.toUpperCase(), x + 6, y + 9)

    doc.setFontSize(17)
    doc.setFont('helvetica', 'bold')
    setColor(doc, 'setTextColor', COLOR.textDark)
    doc.text(card.value, x + 6, y + 18.5)
  })

  return y + cardHeight + 12
}

function buildWaterfallSeries(waterfall) {
  let cumulative = 0
  return waterfall.map((step) => {
    if (step.type === 'start' || step.type === 'end') {
      cumulative = step.type === 'start' ? step.value : cumulative
      return { ...step, base: 0, display: step.value }
    }
    const base = step.value >= 0 ? cumulative : cumulative + step.value
    cumulative += step.value
    return { ...step, base, display: Math.abs(step.value) }
  })
}

function drawWaterfallChart(doc, y, waterfall) {
  y = ensureSpace(doc, y, 78)

  doc.setFontSize(12.5)
  doc.setFont('helvetica', 'bold')
  setColor(doc, 'setTextColor', COLOR.textDark)
  doc.text('Variance waterfall', MARGIN, y)
  doc.setFontSize(8.5)
  doc.setFont('helvetica', 'normal')
  setColor(doc, 'setTextColor', COLOR.textDim)
  doc.text('How prior-period revenue became current-period revenue', MARGIN, y + 5)
  y += 12

  const data = buildWaterfallSeries(waterfall)
  const chartTop = y
  const chartHeight = 46
  const chartBottom = chartTop + chartHeight
  const maxValue = Math.max(...data.map((d) => d.base + d.display))
  const scale = chartHeight / (maxValue * 1.15)

  const slot = CONTENT_WIDTH / data.length
  const barWidth = slot * 0.52

  doc.setDrawColor(...COLOR.border)
  doc.line(MARGIN, chartBottom, MARGIN + CONTENT_WIDTH, chartBottom)

  data.forEach((d, i) => {
    const slotX = MARGIN + i * slot
    const barX = slotX + (slot - barWidth) / 2
    const barTop = chartBottom - (d.base + d.display) * scale
    const barHeight = Math.max(d.display * scale, 0.6)

    const color = d.type === 'decrease' ? COLOR.danger : COLOR.accent
    doc.setFillColor(...color)
    doc.roundedRect(barX, barTop, barWidth, barHeight, 1, 1, 'F')

    doc.setFontSize(8)
    doc.setFont('helvetica', 'bold')
    setColor(doc, 'setTextColor', COLOR.textDark)
    const valueLabel =
      (d.type === 'increase' ? '+' : d.type === 'decrease' ? '-' : '') +
      `$${Math.round(Math.abs(d.value) / 1000)}k`
    doc.text(valueLabel, slotX + slot / 2, barTop - 2.5, { align: 'center' })

    doc.setFontSize(7.5)
    doc.setFont('helvetica', 'normal')
    setColor(doc, 'setTextColor', COLOR.textDim)
    const nameLines = doc.splitTextToSize(d.name, slot - 2)
    doc.text(nameLines, slotX + slot / 2, chartBottom + 5, { align: 'center' })
  })

  return chartBottom + 16
}

function statusMeta(status) {
  if (status === 'passed_with_warnings') return { label: 'Warning', color: COLOR.amberText, bg: COLOR.amberBg }
  if (status === 'failed') return { label: 'Failed', color: COLOR.danger, bg: COLOR.dangerBg }
  return { label: 'Passed', color: COLOR.accentDark, bg: COLOR.accentBg }
}

function drawSectionTitle(doc, y, text, subtitle) {
  y = ensureSpace(doc, y, subtitle ? 16 : 12)
  doc.setFontSize(12.5)
  doc.setFont('helvetica', 'bold')
  setColor(doc, 'setTextColor', COLOR.textDark)
  doc.text(text, MARGIN, y)
  if (subtitle) {
    doc.setFontSize(8.5)
    doc.setFont('helvetica', 'normal')
    setColor(doc, 'setTextColor', COLOR.textDim)
    doc.text(subtitle, MARGIN, y + 5)
    y += 5
  }
  return y + 7
}

function tableTheme(doc, y, options) {
  autoTable(doc, {
    startY: y,
    margin: { left: MARGIN, right: MARGIN },
    theme: 'plain',
    styles: {
      font: 'helvetica',
      fontSize: 9,
      textColor: COLOR.textDark,
      cellPadding: { top: 3.2, bottom: 3.2, left: 3, right: 3 },
      lineColor: COLOR.border,
      lineWidth: 0.15,
    },
    headStyles: {
      fillColor: COLOR.textDark,
      textColor: COLOR.white,
      fontStyle: 'bold',
      fontSize: 8.5,
    },
    alternateRowStyles: { fillColor: COLOR.panelBg },
    ...options,
  })
  return doc.lastAutoTable.finalY + 10
}

function drawRiskCallout(doc, y, risks) {
  if (!risks?.length) return y
  y = drawSectionTitle(doc, y, 'Risks & caveats')

  const lineHeight = 5.2
  const wrapped = risks.map((r) => doc.splitTextToSize(`•  ${r}`, CONTENT_WIDTH - 10))
  const totalLines = wrapped.reduce((sum, lines) => sum + lines.length, 0)
  const boxHeight = totalLines * lineHeight + 8

  y = ensureSpace(doc, y, boxHeight)
  doc.setFillColor(...COLOR.amberBg)
  doc.setDrawColor(...COLOR.amberText)
  doc.roundedRect(MARGIN, y, CONTENT_WIDTH, boxHeight, 2, 2, 'FD')

  let cursorY = y + 7
  doc.setFontSize(9.5)
  doc.setFont('helvetica', 'normal')
  setColor(doc, 'setTextColor', [110, 75, 8])
  wrapped.forEach((lines) => {
    doc.text(lines, MARGIN + 5, cursorY)
    cursorY += lines.length * lineHeight
  })

  return y + boxHeight + 10
}

function drawFooters(doc) {
  const pageCount = doc.internal.getNumberOfPages()
  for (let i = 1; i <= pageCount; i += 1) {
    doc.setPage(i)
    doc.setDrawColor(...COLOR.border)
    doc.line(MARGIN, PAGE_HEIGHT - 14, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 14)
    doc.setFontSize(8)
    doc.setFont('helvetica', 'normal')
    setColor(doc, 'setTextColor', COLOR.textLight)
    doc.text('FinOps Explain AI — auto-generated, synthetic demo data', MARGIN, PAGE_HEIGHT - 9)
    doc.text(`Page ${i} of ${pageCount}`, PAGE_WIDTH - MARGIN, PAGE_HEIGHT - 9, { align: 'right' })
  }
}

// Builds a real, formatted PDF (header band, score cards, vector waterfall
// chart, and autoTable tables) from the analyze response and triggers a
// browser download. Nothing here is re-fetched — it's a pure render of the
// analysis object already held in state.
export function downloadAnalysisPdf(analysis) {
  const doc = new jsPDF({ unit: 'mm', format: 'a4' })

  let y = drawCoverHeader(doc, analysis)

  doc.setFontSize(19)
  doc.setFont('helvetica', 'bold')
  setColor(doc, 'setTextColor', COLOR.textDark)
  const headlineLines = doc.splitTextToSize(analysis.headline, CONTENT_WIDTH)
  doc.text(headlineLines, MARGIN, y)
  y += headlineLines.length * 7.2 + 3

  doc.setFontSize(10.5)
  doc.setFont('helvetica', 'normal')
  setColor(doc, 'setTextColor', COLOR.textDim)
  const summaryLines = doc.splitTextToSize(analysis.summary, CONTENT_WIDTH)
  doc.text(summaryLines, MARGIN, y)
  y += summaryLines.length * 5.2 + 10

  y = drawScoreCards(doc, y, analysis)
  y = drawWaterfallChart(doc, y, analysis.waterfall)

  y = drawSectionTitle(doc, y, 'Driver drilldown', 'Ranked by absolute contribution to the change')
  y = tableTheme(doc, y, {
    head: [['Driver', 'Account', 'Current', 'Prior', 'Change', '% Share', 'Conf.']],
    body: analysis.drivers.map((d) => [
      d.driver,
      d.account,
      `$${d.current.toLocaleString()}`,
      `$${d.prior.toLocaleString()}`,
      `${d.amount >= 0 ? '+' : ''}$${d.amount.toLocaleString()}`,
      `${d.share_of_change_pct >= 0 ? '+' : ''}${d.share_of_change_pct}%`,
      `${Math.round(d.confidence * 100)}%`,
    ]),
    columnStyles: {
      0: { cellWidth: 44, fontStyle: 'bold' },
      2: { halign: 'right' },
      3: { halign: 'right' },
      4: { halign: 'right' },
      5: { halign: 'right' },
      6: { halign: 'right' },
    },
    didParseCell: (data) => {
      if (data.section === 'body' && (data.column.index === 4 || data.column.index === 5)) {
        const raw = String(data.cell.raw)
        data.cell.styles.textColor = raw.includes('-') ? COLOR.danger : COLOR.accentDark
        data.cell.styles.fontStyle = 'bold'
      }
    },
  })

  y = drawSectionTitle(doc, y, 'Evidence', 'Source transactions cited for each driver')
  const evidenceRows = []
  analysis.drivers.forEach((d) => {
    d.evidence.forEach((e, idx) => {
      evidenceRows.push([idx === 0 ? d.driver : '', e])
    })
  })
  y = tableTheme(doc, y, {
    head: [['Driver', 'Evidence']],
    body: evidenceRows,
    columnStyles: {
      0: { cellWidth: 44, fontStyle: 'bold', textColor: COLOR.textDark },
      1: { textColor: COLOR.textDim },
    },
  })

  y = drawRiskCallout(doc, y, analysis.risks_or_caveats)

  if (analysis.agent_timeline?.length) {
    y = drawSectionTitle(doc, y, 'Agent run timeline')
    y = tableTheme(doc, y, {
      head: [['#', 'Agent', 'Status', 'Duration']],
      body: analysis.agent_timeline.map((step, idx) => [
        String(idx + 1),
        step.name,
        statusMeta(step.status).label,
        `${step.duration_ms}ms`,
      ]),
      columnStyles: {
        0: { cellWidth: 10, textColor: COLOR.textDim },
        2: { fontStyle: 'bold' },
        3: { halign: 'right', textColor: COLOR.textDim },
      },
      didParseCell: (data) => {
        if (data.section === 'body' && data.column.index === 2) {
          const step = analysis.agent_timeline[data.row.index]
          data.cell.styles.textColor = statusMeta(step.status).color
        }
      },
    })
  }

  drawFooters(doc)

  const filename = `finops-report-${analysis.run_id || 'run'}.pdf`
  doc.save(filename)
  return filename
}
