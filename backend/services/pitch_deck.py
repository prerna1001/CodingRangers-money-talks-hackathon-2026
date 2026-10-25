"""Pitch deck for one run, as a native PowerPoint file
(GET /api/runs/{run_id}/pitch-deck?theme=finance|dark).

Seven 16:9 slides written for a reader who was not in the room -- another
team, a client, senior leadership:

    1  Title and headline result
    2  Problem and approach
    3  Revenue bridge            (waterfall chart)
    4  Driver analysis           (bar chart + ranked table)
    5  Trust and evidence        (quality metrics + agent run chart)
    6  Conclusions and risks
    7  Future work and next steps

Charts are native PowerPoint charts, not pictures, so they stay editable
and can be restyled in PowerPoint. The two themes mirror the two Power BI
reports (services/powerbi_report.py): corporate navy and executive dark.
Everything shown comes from the same run state the Power BI export reads;
nothing is invented, so a number on a slide always matches the dashboard.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_TICK_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

from api.presenters import to_frontend_analysis
from models.schemas import RunState

FONT = "Calibri"
FONT_BOLD = "Calibri"
SLIDE_W, SLIDE_H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.6)
CONTENT_W = SLIDE_W - 2 * MARGIN

# ---------------------------------------------------------------------------
# Themes -- same palettes as the two Power BI reports
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Palette:
    key: str
    label: str
    page: str
    card: str
    border: str
    text: str
    muted: str
    accent: str       # titles, totals, header fills
    accent_2: str
    good: str
    bad: str
    on_accent: str
    series: tuple[str, ...]


PALETTES = {
    "finance": Palette(
        key="finance", label="Corporate Navy", page="F3F5F8", card="FFFFFF", border="DDE3EA",
        text="1F2A44", muted="5B6778", accent="1F3864", accent_2="2E75B6", good="2E7D32", bad="C62828",
        on_accent="FFFFFF", series=("1F3864", "2E75B6", "00A3A1", "F2A900", "7F8C9D", "C0504D"),
    ),
    "dark": Palette(
        key="dark", label="Executive Dark", page="0E1621", card="16212E", border="26364A",
        text="E6EDF5", muted="9AA8B8", accent="5B9BD5", accent_2="2BB3A3", good="3FB97A", bad="E5534B",
        on_accent="0E1621", series=("5B9BD5", "2BB3A3", "F2C14E", "A5B4C8", "E86A5F", "7CC47F"),
    ),
}


def _rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color)


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def _money(value: float, signed: bool = False) -> str:
    sign = "-" if value < 0 else ("+" if signed else "")
    v = abs(value)
    if v >= 1_000_000:
        body = f"${v / 1_000_000:,.2f}M"
    elif v >= 10_000:
        body = f"${v / 1_000:,.0f}K"
    elif v >= 1_000:
        body = f"${v / 1_000:,.1f}K"
    else:
        body = f"${v:,.0f}"
    return sign + body


def _pct(value: float, signed: bool = False) -> str:
    return f"{value:+.1f}%" if signed else f"{value:.1f}%"


def _clip(text: str, limit: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _first_sentence(text: str, limit: int = 220) -> str:
    text = " ".join((text or "").split())
    end = text.find(". ")
    if 0 < end < limit:
        return text[: end + 1]
    return _clip(text, limit)


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------


class _Deck:
    def __init__(self, palette: Palette):
        self.p = palette
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = SLIDE_W, SLIDE_H
        self.blank = self.prs.slide_layouts[6]
        self.count = 0

    # -- primitives ---------------------------------------------------------

    def rect(self, slide, x, y, w, h, fill: str | None, line: str | None = None, shape=MSO_SHAPE.RECTANGLE):
        shp = slide.shapes.add_shape(shape, x, y, w, h)
        shp.shadow.inherit = False
        if fill:
            shp.fill.solid()
            shp.fill.fore_color.rgb = _rgb(fill)
        else:
            shp.fill.background()
        if line:
            shp.line.color.rgb = _rgb(line)
            shp.line.width = Pt(0.75)
        else:
            shp.line.fill.background()
        return shp

    def text(self, slide, x, y, w, h, paragraphs, *, size=14, color=None, bold=False, align=PP_ALIGN.LEFT,
             anchor=MSO_ANCHOR.TOP, space_after=0, line_spacing=1.0):
        """paragraphs: str | list of str | list of (str, {size,bold,color,bullet}) tuples."""
        box = slide.shapes.add_textbox(x, y, w, h)
        frame = box.text_frame
        frame.word_wrap = True
        frame.vertical_anchor = anchor
        frame.margin_left = frame.margin_right = 0
        frame.margin_top = frame.margin_bottom = 0
        if isinstance(paragraphs, str):
            paragraphs = [paragraphs]
        for index, item in enumerate(paragraphs):
            content, opts = (item, {}) if isinstance(item, str) else item
            para = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
            para.alignment = align
            para.space_after = Pt(opts.get("space_after", space_after))
            para.line_spacing = line_spacing
            run = para.add_run()
            run.text = content
            font = run.font
            font.name = FONT_BOLD if opts.get("bold", bold) else FONT
            font.size = Pt(opts.get("size", size))
            font.bold = opts.get("bold", bold)
            font.color.rgb = _rgb(opts.get("color", color or self.p.text))
            if opts.get("bullet"):
                pPr = para._p.get_or_add_pPr()
                pPr.set("marL", str(Inches(0.2)))
                pPr.set("indent", str(-Inches(0.2)))
                for tag in ("a:buNone", "a:buChar"):
                    for el in pPr.findall(qn(tag)):
                        pPr.remove(el)
                bu_clr = pPr.makeelement(qn("a:buClr"), {})
                srgb = bu_clr.makeelement(qn("a:srgbClr"), {"val": self.p.accent_2})
                bu_clr.append(srgb)
                pPr.append(bu_clr)
                pPr.append(pPr.makeelement(qn("a:buChar"), {"char": "•"}))
        return box

    def notes(self, slide, text: str):
        slide.notes_slide.notes_text_frame.text = text

    # -- slide scaffolding --------------------------------------------------

    def slide(self, section: str, title: str, run_label: str):
        s = self.prs.slides.add_slide(self.blank)
        self.count += 1
        bg = s.background.fill
        bg.solid()
        bg.fore_color.rgb = _rgb(self.p.page)
        # Left accent rail + section label + action title
        self.rect(s, 0, 0, Inches(0.18), SLIDE_H, self.p.accent)
        self.text(s, MARGIN, Inches(0.38), CONTENT_W, Inches(0.3), section.upper(), size=11, bold=True,
                  color=self.p.accent_2)
        self.text(s, MARGIN, Inches(0.68), CONTENT_W, Inches(0.95), title, size=26, bold=True,
                  color=self.p.accent if self.p.key == "finance" else self.p.text, line_spacing=0.95)
        # Footer
        self.rect(s, MARGIN, Inches(7.0), CONTENT_W, Emu(9525), self.p.border)
        self.text(s, MARGIN, Inches(7.07), Inches(9), Inches(0.25), run_label, size=9, color=self.p.muted)
        self.text(s, SLIDE_W - MARGIN - Inches(1), Inches(7.07), Inches(1), Inches(0.25), str(self.count), size=9,
                  color=self.p.muted, align=PP_ALIGN.RIGHT)
        return s

    def card(self, slide, x, y, w, h):
        return self.rect(slide, x, y, w, h, self.p.card, self.p.border)

    def kpi(self, slide, x, y, w, h, value, label, tone: str | None = None, size=26):
        self.card(slide, x, y, w, h)
        self.rect(slide, x, y, Inches(0.06), h, tone or self.p.accent_2)
        self.text(slide, x + Inches(0.25), y + Inches(0.14), w - Inches(0.4), Inches(0.3), label.upper(), size=10,
                  bold=True, color=self.p.muted)
        self.text(slide, x + Inches(0.25), y + Inches(0.46), w - Inches(0.4), h - Inches(0.5), value, size=size,
                  bold=True, color=tone or self.p.text, anchor=MSO_ANCHOR.TOP)

    def panel_title(self, slide, x, y, w, label):
        self.text(slide, x, y, w, Inches(0.3), label, size=13, bold=True, color=self.p.text)
        self.rect(slide, x, y + Inches(0.32), Inches(0.5), Emu(25400), self.p.accent_2)

    # -- chart styling ------------------------------------------------------

    def style_chart(self, chart, *, legend=False):
        chart.font.name = FONT
        chart.font.size = Pt(10)
        chart.font.color.rgb = _rgb(self.p.muted)
        chart.has_legend = legend
        chart.has_title = False

    def style_axes(self, chart, *, value_format='$#,##0', gridlines=True):
        cat, val = chart.category_axis, chart.value_axis
        cat.format.line.color.rgb = _rgb(self.p.border)
        cat.tick_labels.font.size = Pt(10)
        cat.tick_labels.font.color.rgb = _rgb(self.p.text)
        cat.has_major_gridlines = False
        val.has_major_gridlines = gridlines
        if gridlines:
            val.major_gridlines.format.line.color.rgb = _rgb(self.p.border)
            val.major_gridlines.format.line.width = Pt(0.5)
        val.format.line.fill.background()
        val.tick_labels.number_format = value_format
        val.tick_labels.number_format_is_linked = False
        val.tick_labels.font.size = Pt(9)
        val.tick_labels.font.color.rgb = _rgb(self.p.muted)

    def table(self, slide, x, y, w, rows: list[list[str]], widths: list[float], *, row_h=0.36, align_right_from=1):
        shape = slide.shapes.add_table(len(rows), len(rows[0]), x, y, w, Inches(row_h * len(rows)))
        table = shape.table
        # Strip the default style so the cells carry the theme.
        tbl_pr = shape._element.graphic.graphicData.tbl.tblPr
        for attr in ("firstRow", "bandRow"):
            tbl_pr.set(attr, "0")
        style_id = tbl_pr.find(qn("a:tableStyleId"))
        if style_id is not None:
            style_id.text = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"  # No Style, No Grid
        total = sum(widths)
        for i, weight in enumerate(widths):
            table.columns[i].width = int(w * weight / total)
        for r, row in enumerate(rows):
            table.rows[r].height = Inches(row_h)
            for c, value in enumerate(row):
                cell = table.cell(r, c)
                cell.margin_left = cell.margin_right = Inches(0.08)
                cell.margin_top = cell.margin_bottom = Inches(0.03)
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                cell.fill.solid()
                header = r == 0
                cell.fill.fore_color.rgb = _rgb(self.p.accent if header else (self.p.card if r % 2 else self.p.page))
                para = cell.text_frame.paragraphs[0]
                para.alignment = PP_ALIGN.RIGHT if c >= align_right_from else PP_ALIGN.LEFT
                run = para.add_run()
                run.text = value
                run.font.name = FONT
                run.font.size = Pt(10.5 if not header else 10)
                run.font.bold = header
                tone = self.p.on_accent if header else self.p.text
                if not header and c in (3, 4) and value[:1] in "+-":
                    tone = self.p.good if value[0] == "+" else self.p.bad
                run.font.color.rgb = _rgb(tone)
        return shape


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------


def _agent_pipeline_names(analysis: dict) -> list[str]:
    # An agent can run more than once (e.g. a second analyst pass); list each once.
    return list(dict.fromkeys(step["name"] for step in analysis["agent_timeline"]))


def _merge_timeline(timeline: list[dict]) -> list[dict]:
    merged: dict[str, int] = {}
    for step in timeline:
        merged[step["name"]] = merged.get(step["name"], 0) + step["duration_ms"]
    return [{"name": n, "duration_ms": d} for n, d in merged.items()]


def _bridge_chart(deck: _Deck, slide, x, y, w, h, waterfall: list[dict]):
    """Waterfall as a stacked column: an invisible base lifts each floating bar."""
    cats, base, up, down, total = [], [], [], [], []
    running = 0.0
    for step in waterfall:
        cats.append(_clip(step["name"], 22))
        value = step["value"]
        if step["type"] in ("start", "end"):
            base.append(None); up.append(None); down.append(None); total.append(value)
            running = value
        elif value >= 0:
            base.append(running); up.append(value); down.append(None); total.append(None)
            running += value
        else:
            running += value
            base.append(running); up.append(None); down.append(-value); total.append(None)
    data = CategoryChartData()
    data.categories = cats
    for name, values in (("Base", base), ("Total", total), ("Increase", up), ("Decrease", down)):
        data.add_series(name, values)
    frame = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_STACKED, x, y, w, h, data)
    chart = frame.chart
    deck.style_chart(chart)
    deck.style_axes(chart)
    plot = chart.plots[0]
    plot.gap_width = 45
    plot.overlap = 100
    fills = {"Base": None, "Total": deck.p.accent, "Increase": deck.p.good, "Decrease": deck.p.bad}
    for series in plot.series:
        fill = fills[series.name]
        if fill is None:
            series.format.fill.background()
            series.format.line.fill.background()
            continue
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = _rgb(fill)
        labels = series.data_labels
        labels.show_value = True
        labels.number_format = '$#,##0;-$#,##0;;'
        labels.number_format_is_linked = False
        labels.font.size = Pt(10)
        labels.font.bold = True
        labels.font.color.rgb = _rgb(deck.p.on_accent if series.name == "Total" and deck.p.key == "finance"
                                     else deck.p.text)
        labels.position = XL_LABEL_POSITION.INSIDE_END if series.name == "Total" else XL_LABEL_POSITION.CENTER
        if series.name != "Total":
            labels.font.color.rgb = _rgb("FFFFFF")
    # Keep the axis from starting at zero when the bars sit near the top, so
    # the movements are visible instead of tiny slivers on a huge column.
    floor = min(v for v in base + total if v is not None)
    ceiling = max((b or 0) + (u or 0) + (t or 0) for b, u, t in zip(base, up, total))
    if floor > 0 and (ceiling - floor) < ceiling * 0.5:
        chart.value_axis.minimum_scale = max(0.0, round(floor * 0.8, -3))
    chart.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW


def _driver_chart(deck: _Deck, slide, x, y, w, h, drivers: list[dict]):
    top = drivers[:8]
    data = CategoryChartData()
    data.categories = [_clip(d["driver"], 24) for d in top]
    data.add_series("Change", [d["amount"] for d in top])
    frame = slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, x, y, w, h, data)
    chart = frame.chart
    deck.style_chart(chart)
    deck.style_axes(chart, value_format='$#,##0;-$#,##0')
    chart.category_axis.reverse_order = True
    chart.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
    chart.value_axis.visible = False
    chart.value_axis.has_major_gridlines = False
    plot = chart.plots[0]
    plot.gap_width = 55
    series = plot.series[0]
    series.invert_if_negative = False
    for index, driver in enumerate(top):
        point = series.points[index]
        point.format.fill.solid()
        point.format.fill.fore_color.rgb = _rgb(deck.p.good if driver["amount"] >= 0 else deck.p.bad)
    labels = series.data_labels
    labels.show_value = True
    labels.number_format = '$#,##0;-$#,##0'
    labels.number_format_is_linked = False
    labels.position = XL_LABEL_POSITION.OUTSIDE_END
    labels.font.size = Pt(10)
    labels.font.bold = True
    labels.font.color.rgb = _rgb(deck.p.text)


def _agent_chart(deck: _Deck, slide, x, y, w, h, timeline: list[dict]):
    data = CategoryChartData()
    data.categories = [_clip(s["name"], 26) for s in timeline]
    data.add_series("Duration (ms)", [s["duration_ms"] for s in timeline])
    frame = slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, x, y, w, h, data)
    chart = frame.chart
    deck.style_chart(chart)
    deck.style_axes(chart, value_format='#,##0" ms"')
    chart.category_axis.reverse_order = True
    chart.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
    chart.value_axis.visible = False
    chart.value_axis.has_major_gridlines = False
    chart.value_axis.maximum_scale = max(s["duration_ms"] for s in timeline) * 1.25
    plot = chart.plots[0]
    plot.gap_width = 50
    series = plot.series[0]
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = _rgb(deck.p.accent_2)
    labels = series.data_labels
    labels.show_value = True
    labels.number_format = '#,##0" ms"'
    labels.number_format_is_linked = False
    labels.position = XL_LABEL_POSITION.OUTSIDE_END
    labels.font.size = Pt(9)
    labels.font.color.rgb = _rgb(deck.p.text)


def build_pitch_deck(state: RunState, theme: str = "finance") -> bytes:
    palette = PALETTES.get(theme, PALETTES["finance"])
    deck = _Deck(palette)
    a = to_frontend_analysis(state)
    p = palette

    prior, current = a["periods"]["prior"], a["periods"]["current"]
    change = current["revenue"] - prior["revenue"]
    change_pct = (change / prior["revenue"] * 100) if prior["revenue"] else 0.0
    drivers = a["drivers"]
    steps = [s for s in a["waterfall"] if s["type"] in ("increase", "decrease")]
    gains = sorted((s for s in steps if s["value"] > 0), key=lambda s: -s["value"])
    losses = sorted((s for s in steps if s["value"] < 0), key=lambda s: s["value"])
    company = state.get("company_id") or "the business"
    profile = state.get("company_profile_core")
    if profile is not None and getattr(profile, "company_name", None):
        company = profile.company_name
    run_label = f"Ledgerlight  |  {company}  |  {prior['label']} to {current['label']}  |  Run {a['run_id']}"
    tone = p.good if change >= 0 else p.bad
    n_txn = len(state.get("transactions", []))
    n_facts = len(state.get("facts", []))
    n_evidence = sum(len(f.evidence_txn_ids) for f in state.get("facts", []))
    timeline = _merge_timeline(a["agent_timeline"])
    verified = a["grounding_badge"] or "n/a"
    risks = a["risks_or_caveats"]
    follow_ups = a["follow_up_questions"]

    # ---- 1. Title -------------------------------------------------------
    s = deck.prs.slides.add_slide(deck.blank)
    deck.count += 1
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = _rgb(p.accent if p.key == "finance" else p.page)
    on_dark = p.key == "finance"
    ink = "FFFFFF" if on_dark else p.text
    soft = "C9D6EA" if on_dark else p.muted
    deck.rect(s, 0, 0, Inches(0.18), SLIDE_H, p.accent_2)
    deck.text(s, MARGIN, Inches(0.7), Inches(9), Inches(0.3), "LEDGERLIGHT  |  REVENUE VARIANCE REVIEW", size=12,
              bold=True, color=p.accent_2 if not on_dark else "9CC3E8")
    deck.text(s, MARGIN, Inches(1.25), Inches(11.5), Inches(1.5),
              f"{company}: revenue {'grew' if change >= 0 else 'fell'} {_money(abs(change))} "
              f"({_pct(abs(change_pct))}) from {prior['label']} to {current['label']}",
              size=38, bold=True, color=ink, line_spacing=0.95)
    deck.text(s, MARGIN, Inches(3.0), Inches(10.5), Inches(1.0), _first_sentence(a["headline"], 260),
              size=18, color=soft, line_spacing=1.05)
    kpis = [
        (_money(prior["revenue"]), f"{prior['label']} revenue", None),
        (_money(current["revenue"]), f"{current['label']} revenue", None),
        (_money(change, True), "Net change", tone),
        (f"{a['data_quality_score'] * 100:.0f}%", "Data quality", None),
    ]
    kw, gap = Inches(2.85), Inches(0.2)
    for i, (value, label, k_tone) in enumerate(kpis):
        x = MARGIN + i * (kw + gap)
        deck.rect(s, x, Inches(4.7), kw, Inches(1.35), p.card if not on_dark else "FFFFFF", p.border)
        deck.rect(s, x, Inches(4.7), Inches(0.06), Inches(1.35), k_tone or p.accent_2)
        deck.text(s, x + Inches(0.25), Inches(4.85), kw - Inches(0.4), Inches(0.3), label.upper(), size=10,
                  bold=True, color=p.muted if not on_dark else "5B6778")
        deck.text(s, x + Inches(0.25), Inches(5.2), kw - Inches(0.4), Inches(0.7), value, size=30, bold=True,
                  color=k_tone or (p.text if not on_dark else p.accent))
    deck.text(s, MARGIN, Inches(6.6), Inches(11), Inches(0.3),
              f"Prepared for leadership and partner teams  |  Run {a['run_id']}  |  Every figure traced to source transactions",
              size=11, color=soft)
    deck.notes(s, f"Opening. {a['headline']} Revenue moved from {_money(prior['revenue'])} to "
                  f"{_money(current['revenue'])}. The rest of the deck explains why, how sure we are, and what we do next.")

    # ---- 2. Problem and approach ---------------------------------------
    s = deck.slide("Context", "Explaining a revenue swing takes days and is hard to audit; we made it traceable",
                   run_label)
    col_w = Inches(5.9)
    deck.panel_title(s, MARGIN, Inches(1.85), col_w, "The problem")
    deck.text(s, MARGIN, Inches(2.3), col_w, Inches(2.6), [
        ("Finance teams reconcile month-on-month revenue by hand across ledgers, exports and spreadsheets.",
         {"bullet": True, "space_after": 9}),
        ("Narratives drift from the numbers: a figure quoted in a board note is rarely linked to the entries behind it.",
         {"bullet": True, "space_after": 9}),
        ("Leaders need three answers fast: what moved, why, and how much to trust the explanation.",
         {"bullet": True, "space_after": 9}),
    ], size=14, line_spacing=1.05)

    deck.card(s, MARGIN, Inches(4.95), col_w, Inches(1.8))
    deck.text(s, MARGIN + Inches(0.25), Inches(5.08), col_w, Inches(0.3), "SCOPE OF THIS RUN", size=10, bold=True,
              color=p.muted)
    stats = [(f"{n_txn:,}", "transactions"), (f"{n_facts}", "computed facts"), (f"{n_evidence}", "evidence links")]
    sw = (col_w - Inches(0.5)) / 3
    for i, (value, label) in enumerate(stats):
        deck.text(s, MARGIN + Inches(0.25) + i * sw, Inches(5.45), sw, Inches(0.55), value, size=28, bold=True,
                  color=p.accent if p.key == "finance" else p.accent)
        deck.text(s, MARGIN + Inches(0.25) + i * sw, Inches(6.02), sw, Inches(0.3), label, size=11, color=p.muted)
    deck.text(s, MARGIN + Inches(0.25), Inches(6.38), col_w - Inches(0.4), Inches(0.3),
              f"{prior['label']} vs {current['label']}  |  {company}", size=10, color=p.muted)

    rx = MARGIN + col_w + Inches(0.5)
    rw = SLIDE_W - MARGIN - rx
    deck.panel_title(s, rx, Inches(1.85), rw, "Our approach: a pipeline of specialised agents")
    names = _agent_pipeline_names(a) or ["Ingest", "Quality check", "Analyse", "Explain", "Verify", "Report"]
    names = names[:8]
    row_h = min(Inches(0.52), int((Inches(4.45)) / max(len(names), 1)))
    for i, name in enumerate(names):
        y = Inches(2.35) + i * row_h
        deck.rect(s, rx, y, Inches(0.36), Inches(0.36), p.accent, shape=MSO_SHAPE.OVAL)
        deck.text(s, rx, y + Inches(0.045), Inches(0.36), Inches(0.3), str(i + 1), size=11, bold=True,
                  color=p.on_accent, align=PP_ALIGN.CENTER)
        deck.text(s, rx + Inches(0.55), y + Inches(0.04), rw - Inches(0.6), Inches(0.3), name, size=14,
                  color=p.text)
        if i < len(names) - 1:
            deck.rect(s, rx + Inches(0.175), y + Inches(0.38), Emu(12700), row_h - Inches(0.4), p.border)
    deck.text(s, rx, Inches(6.55), rw, Inches(0.4),
              "Deterministic maths computes every figure; the language model only explains them.", size=11,
              color=p.muted, line_spacing=1.0)
    deck.notes(s, "Problem and approach. Stress that numbers are computed in code, not generated by the model, and "
                  "every fact keeps a pointer to the transactions behind it.")

    # ---- 3. Revenue bridge ---------------------------------------------
    best = gains[0] if gains else None
    worst = losses[0] if losses else None
    title3 = (f"Revenue moved {_money(change, True)} ({_pct(change_pct, True)}); "
              f"{_clip(best['name'], 30)} was the largest lift" if best else
              f"Revenue moved {_money(change, True)} ({_pct(change_pct, True)}) between the two periods")
    s = deck.slide("Analysis  |  Revenue bridge", title3, run_label)
    deck.card(s, MARGIN, Inches(1.8), Inches(8.5), Inches(5.0))
    _bridge_chart(deck, s, MARGIN + Inches(0.1), Inches(1.9), Inches(8.3), Inches(4.5), a["waterfall"])
    deck.text(s, MARGIN + Inches(0.25), Inches(6.47), Inches(8.0), Inches(0.25),
              "Green adds revenue, red reduces it. Vertical axis is truncated to make the movements visible.",
              size=10, color=p.muted)
    rx = MARGIN + Inches(8.8)
    rw = SLIDE_W - MARGIN - rx
    deck.panel_title(s, rx, Inches(1.8), rw, "How to read it")
    reading = [
        (f"Starts at {_money(prior['revenue'])} in {prior['label']} and ends at {_money(current['revenue'])} "
         f"in {current['label']}.", {"bullet": True, "space_after": 8}),
    ]
    if best:
        reading.append((f"Biggest lift: {_clip(best['name'], 34)}, {_money(best['value'], True)}.",
                        {"bullet": True, "space_after": 8}))
    if worst:
        reading.append((f"Biggest drag: {_clip(worst['name'], 34)}, {_money(worst['value'], True)}.",
                        {"bullet": True, "space_after": 8}))
    other = next((x for x in steps if x["name"] == "Other"), None)
    reading.append((
        f"Unattributed remainder is shown as 'Other' ({_money(other['value'], True)}), never hidden."
        if other else "Drivers fully explain the movement; no unattributed remainder.",
        {"bullet": True, "space_after": 8}))
    deck.text(s, rx, Inches(2.3), rw, Inches(3.0), reading, size=13, line_spacing=1.05)
    deck.card(s, rx, Inches(5.4), rw, Inches(1.4))
    deck.text(s, rx + Inches(0.2), Inches(5.52), rw - Inches(0.4), Inches(0.3), "SO WHAT", size=10, bold=True,
              color=p.muted)
    sowhat = (f"{len(gains)} driver{'s' if len(gains) != 1 else ''} added revenue and {len(losses)} reduced it; "
              f"the net effect is {_money(change, True)}.")
    deck.text(s, rx + Inches(0.2), Inches(5.82), rw - Inches(0.4), Inches(0.9), sowhat, size=13, bold=True,
              color=tone, line_spacing=1.0)
    deck.notes(s, "Walk the chart left to right: opening revenue, each driver's contribution, closing revenue. "
                  "Green bars add revenue, red bars subtract. The bars tie exactly to both endpoints.")

    # ---- 4. Drivers -----------------------------------------------------
    lead = drivers[0] if drivers else None
    title4 = (f"{_clip(lead['driver'], 28)} alone accounts for {_money(lead['amount'], True)} of the movement"
              if lead else "Driver analysis")
    s = deck.slide("Analysis  |  Drivers", title4, run_label)
    deck.panel_title(s, MARGIN, Inches(1.8), Inches(5.6), "Change by driver, largest first")
    deck.card(s, MARGIN, Inches(2.25), Inches(5.6), Inches(4.55))
    if drivers:
        _driver_chart(deck, s, MARGIN + Inches(0.05), Inches(2.3), Inches(5.5), Inches(4.45), drivers)
    tx = MARGIN + Inches(5.9)
    tw = SLIDE_W - MARGIN - tx
    deck.panel_title(s, tx, Inches(1.8), tw, "Ranked drivers with confidence")
    rows = [["Driver", "Account", "Prior", "Change", "% chg", "Conf."]]
    for d in drivers[:8]:
        rows.append([_clip(d["driver"], 22), _clip(d["account"], 20), _money(d["prior"]),
                     _money(d["amount"], True), _pct(d["share_of_change_pct"], True), f"{d['confidence'] * 100:.0f}%"])
    deck.table(s, tx, Inches(2.3), tw, rows, [2.3, 2.1, 1.2, 1.3, 1.1, 0.9], row_h=0.38, align_right_from=2)
    note_y = Inches(2.3) + Inches(0.38 * len(rows)) + Inches(0.12)
    deck.text(s, tx, note_y, tw, Inches(0.5),
              "Prior is the driver's own total in the earlier period; % chg is measured against it. "
              "Confidence reflects how completely evidence supports each figure.",
              size=10, color=p.muted, line_spacing=1.0)
    if drivers and change:
        top3 = sum(d["amount"] for d in drivers[:3])
        share = top3 / change * 100
        avg_conf = sum(d["confidence"] for d in drivers) / len(drivers) * 100
        card_y = max(note_y + Inches(0.6), Inches(5.35))
        deck.card(s, tx, card_y, tw, Inches(6.8) - card_y)
        deck.rect(s, tx, card_y, Inches(0.06), Inches(6.8) - card_y, p.accent_2)
        deck.text(s, tx + Inches(0.25), card_y + Inches(0.1), tw - Inches(0.4), Inches(0.25), "CONCENTRATION",
                  size=10, bold=True, color=p.muted)
        deck.text(s, tx + Inches(0.25), card_y + Inches(0.38), tw - Inches(0.4), Inches(6.8) - card_y - Inches(0.4),
                  f"The top three drivers explain {share:.0f}% of the net change across {len(drivers)} drivers; "
                  f"average confidence is {avg_conf:.0f}%.", size=13, bold=True, line_spacing=1.0)
    deck.notes(s, "Drivers are counterparties or revenue lines whose totals moved most. Each carries a confidence "
                  "score derived from its evidence; low-confidence rows deserve a human look before external use.")

    # ---- 5. Trust and evidence ------------------------------------------
    s = deck.slide("Assurance", "Every number is verified against source data before it reaches a slide", run_label)
    kw, kh, kg = Inches(2.9), Inches(1.25), Inches(0.2)
    guard = (a["guardrail_status"] or "n/a").replace("_", " ").title()
    tiles = [
        (f"{a['data_quality_score'] * 100:.0f}%", "Data quality score", None),
        (f"{a['confidence'] * 100:.0f}%", "Overall confidence", None),
        (verified.replace(" numbers verified", ""), "Numbers verified", p.good),
        (guard, "Guardrail status", None),
    ]
    for i, (value, label, k_tone) in enumerate(tiles):
        deck.kpi(s, MARGIN + i * (kw + kg), Inches(1.85), kw, kh, value, label, k_tone,
                 size=26 if len(value) <= 8 else 17)
    deck.panel_title(s, MARGIN, Inches(3.35), Inches(6.5), "Agent run: time spent per stage")
    deck.card(s, MARGIN, Inches(3.8), Inches(7.0), Inches(3.0))
    if timeline:
        _agent_chart(deck, s, MARGIN + Inches(0.05), Inches(3.85), Inches(6.9), Inches(2.9), timeline)
    rx = MARGIN + Inches(7.3)
    rw = SLIDE_W - MARGIN - rx
    deck.panel_title(s, rx, Inches(3.35), rw, "What backs each claim")
    deck.text(s, rx, Inches(3.85), rw, Inches(3.0), [
        ("Figures are computed in code from the ledger, not written by the language model.",
         {"bullet": True, "space_after": 8}),
        (f"{n_facts} facts link to {n_evidence} source transactions, down to file and row.",
         {"bullet": True, "space_after": 8}),
        ("Quoted numbers in the narrative are checked against those facts; anything unverified is flagged.",
         {"bullet": True, "space_after": 8}),
        ("Guardrails screen the uploaded data for injected instructions and formula-style content.",
         {"bullet": True, "space_after": 8}),
    ], size=12.5, line_spacing=1.05)
    deck.notes(s, f"Assurance. {verified}. Data quality {a['data_quality_score'] * 100:.0f}%, overall confidence "
                  f"{a['confidence'] * 100:.0f}%. This is the answer to 'can I trust this?'.")

    # ---- 6. Conclusions and risks ---------------------------------------
    s = deck.slide("Conclusions", "What leadership should take away, and what to keep in mind", run_label)
    findings = [
        (f"Revenue {'rose' if change >= 0 else 'fell'} {_money(abs(change))} ({_pct(abs(change_pct))}) to "
         f"{_money(current['revenue'])}."),
    ]
    if best:
        findings.append(f"{_clip(best['name'], 40)} was the largest positive driver at {_money(best['value'], True)}.")
    if worst:
        findings.append(f"{_clip(worst['name'], 40)} was the largest drag at {_money(worst['value'], True)}.")
    if drivers and change:
        findings.append(f"The top three drivers explain {sum(d['amount'] for d in drivers[:3]) / change * 100:.0f}% "
                        f"of the change across {len(drivers)} drivers, so growth is concentrated.")
    findings.append(f"The explanation is evidence-backed: {verified.lower()}, data quality {a['data_quality_score'] * 100:.0f}%.")
    lw = Inches(6.1)
    deck.panel_title(s, MARGIN, Inches(1.85), lw, "Key findings")
    for i, text in enumerate(findings[:5]):
        y = Inches(2.35) + i * Inches(0.88)
        deck.rect(s, MARGIN, y, Inches(0.42), Inches(0.42), p.accent, shape=MSO_SHAPE.OVAL)
        deck.text(s, MARGIN, y + Inches(0.07), Inches(0.42), Inches(0.3), str(i + 1), size=13, bold=True,
                  color=p.on_accent, align=PP_ALIGN.CENTER)
        deck.text(s, MARGIN + Inches(0.65), y, lw - Inches(0.7), Inches(0.85), text, size=14, line_spacing=1.0)
    rx = MARGIN + lw + Inches(0.5)
    rw = SLIDE_W - MARGIN - rx
    deck.panel_title(s, rx, Inches(1.85), rw, "Risks and caveats")
    deck.card(s, rx, Inches(2.35), rw, Inches(2.5))
    risk_items = [(_clip(r, 150), {"bullet": True, "space_after": 7}) for r in risks[:4]] or [
        ("No material caveats were raised for this run.", {"bullet": True})]
    deck.text(s, rx + Inches(0.25), Inches(2.5), rw - Inches(0.5), Inches(2.4), risk_items, size=12, line_spacing=1.0)
    board = a.get("board_update")
    deck.card(s, rx, Inches(5.05), rw, Inches(1.75))
    deck.text(s, rx + Inches(0.25), Inches(5.17), rw - Inches(0.5), Inches(0.3), "BOARD UPDATE, ONE LINE",
              size=10, bold=True, color=p.muted)
    deck.text(s, rx + Inches(0.25), Inches(5.5), rw - Inches(0.5), Inches(1.25),
              _clip(board, 330) if board else _first_sentence(a["summary"], 330), size=12.5,
              line_spacing=1.0)
    deck.notes(s, (board or a["summary"] or "") + "\n\nRisks: " + "; ".join(risks))

    # ---- 7. Future work -------------------------------------------------
    s = deck.slide("Next steps", "From a one-off analysis to a monthly, always-on revenue review", run_label)
    cw = (CONTENT_W - Inches(0.6)) / 3
    columns = [
        ("Open questions from this run", [_clip(q, 105) for q in follow_ups[:4]] or
         ["Which drivers repeat month to month, and which were one-offs?"]),
        ("Product roadmap", [
            "Multi-period trends and seasonality, beyond a two-period comparison",
            "Forecasting and what-if scenarios on the top drivers",
            "Live connectors to the ledger and billing systems",
            "Scheduled monthly board pack, delivered automatically",
        ]),
        ("Asks of this audience", [
            "Confirm the drivers and caveats on slide 6 with account owners",
            "Nominate a pilot team and data source for the next close",
            "Agree the confidence threshold for external reporting",
            "Review the Power BI report for the same run",
        ]),
    ]
    for i, (heading, items) in enumerate(columns):
        x = MARGIN + i * (cw + Inches(0.3))
        deck.card(s, x, Inches(1.85), cw, Inches(4.2))
        deck.rect(s, x, Inches(1.85), cw, Inches(0.06), [p.accent, p.accent_2, p.good][i])
        deck.text(s, x + Inches(0.25), Inches(2.05), cw - Inches(0.5), Inches(0.35), heading, size=14, bold=True,
                  color=p.accent if p.key == "finance" else p.text)
        deck.text(s, x + Inches(0.25), Inches(2.6), cw - Inches(0.5), Inches(3.4),
                  [(t, {"bullet": True, "space_after": 9}) for t in items], size=12.5, line_spacing=1.0)
    deck.rect(s, MARGIN, Inches(6.25), CONTENT_W, Inches(0.55), p.accent)
    deck.text(s, MARGIN + Inches(0.3), Inches(6.25), CONTENT_W - Inches(0.6), Inches(0.55),
              "Next step: agree the pilot scope and run this review on the next period close.", size=14, bold=True,
              color=p.on_accent, anchor=MSO_ANCHOR.MIDDLE)
    deck.notes(s, "Close with the asks. The open questions on the left come straight from the analysis; "
                  "the roadmap is the proposal.")

    buffer = io.BytesIO()
    deck.prs.save(buffer)
    return buffer.getvalue()
