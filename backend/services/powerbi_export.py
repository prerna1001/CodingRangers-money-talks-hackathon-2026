"""Power BI export -- packages one finished run for Power BI
(GET /api/runs/{run_id}/powerbi).

    README.txt
    reports/                          ready-made reports, open directly
        Ledgerlight Finance.pbip          corporate navy theme
        Ledgerlight Executive Dark.pbip   dark executive theme
        Ledgerlight Finance.Report/ ...   (report pages + theme)
        Ledgerlight.SemanticModel/        shared model: tables with the run's
                                          data embedded, relationships, DAX
    data/
        Ledgerlight_<run>.xlsx        every table as a sheet, one import
        csv/<Table>.csv               the same tables as CSV
        powerquery/<Table>.pq         Power Query script per CSV
    themes/                           the report themes as JSON

Tables: Summary, Bridge, BridgeChart, Drivers, Evidence, Facts, Transactions,
PeriodLines.
Evidence is flattened (each fact beside every transaction that proves it)
and the only column names shared between tables are fact_id and txn_id, so
nothing has to be linked by hand. Bridge is waterfall-ready: numbered bars,
closing total left to Power BI's own Total bar (still in Summary.to_revenue).

A real .pbix cannot be written outside Power BI Desktop (its data lives in
a compressed VertiPaq image), so the ready-made reports are a Power BI
Project -- see services/powerbi_report.py. If a team-built template exists
at data/powerbi/Ledgerlight.pbit it is included too.
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from api.presenters import _build_drivers, _build_waterfall, to_frontend_analysis
from models.schemas import RunState
from services.powerbi_report import THEMES as REPORT_THEMES
from services.powerbi_report import pbip_files

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "data" / "powerbi" / "Ledgerlight.pbit"

# Sheet -> column -> kind. Also the column order. Column names are unique
# across sheets except the two join keys (see module docstring).
SHEETS: dict[str, dict[str, str]] = {
    "Summary": {
        "run_id": "text",
        "company_id": "text",
        "from_period": "text",
        "to_period": "text",
        "from_revenue": "money",
        "to_revenue": "money",
        "revenue_change": "money",
        "headline": "text",
        "narrative": "text",
        "run_confidence": "pct",
        "data_quality_score": "pct",
        "numbers_verified": "text",
        "guardrail_status": "text",
    },
    "Bridge": {
        "bar": "text",
        "bridge_line": "text",
        "bridge_label": "text",
        "bridge_type": "text",
        "bridge_amount": "money",
        "bridge_order": "int",
    },
    # The bridge as stacked columns: revenue carried forward under each
    # driver's increase or decrease, with both period totals as full bars.
    "BridgeChart": {
        "chart_step": "text",
        "chart_order": "int",
        "chart_carried": "money",
        "chart_increase": "money",
        "chart_decrease": "money",
        "chart_total": "money",
    },
    "Drivers": {
        "rank": "int",
        "driver": "text",
        "driver_label": "text",
        "driver_account": "text",
        "driver_prior": "money",
        "driver_current": "money",
        "driver_change": "money",
        "driver_pct_change": "number",
        "driver_confidence": "pct",
    },
    "Evidence": {
        "fact_id": "text",
        "txn_id": "text",
        "fact": "text",
        "fact_figure": "text",
        "txn_date": "date",
        "txn_counterparty": "text",
        "txn_account": "text",
        "txn_amount": "money",
        "txn_memo": "text",
        "txn_source_row": "int",
    },
    "Facts": {
        "fact_id": "text",
        "kind": "text",
        "label": "text",
        "value": "number",
        "unit": "text",
        "formatted": "text",
        "pct": "number",
        "prior_period": "text",
        "prior_value": "number",
        "current_period": "text",
        "current_value": "number",
        "confidence": "pct",
        "evidence_count": "int",
    },
    "Transactions": {
        "txn_id": "text",
        "posted_date": "date",
        "period_id": "text",
        "account_id": "text",
        "account_name": "text",
        "account_type": "text",
        "category": "text",
        "counterparty": "text",
        "amount": "money",
        "currency": "text",
        "memo": "text",
        "is_recurring": "bool",
        "flags": "text",
        "source_file_id": "text",
        "source_row": "int",
    },
    "PeriodLines": {
        "summary_period": "text",
        "summary_start": "date",
        "summary_end": "date",
        "summary_account_id": "text",
        "summary_account": "text",
        "summary_account_type": "text",
        "summary_amount": "money",
    },
}

_NUMBER_FORMATS = {
    "money": "#,##0.00;(#,##0.00)",
    "pct": "0%",
    "date": "yyyy-mm-dd",
    "int": "0",
}

# Power BI theme built from the app's tokens (Frontend/src/index.css).
THEME = {
    "name": "Ledgerlight",
    "dataColors": ["#16233A", "#2A8A5C", "#C8453A", "#5B3FA8", "#9A5B00", "#637083", "#6E9BC4", "#B6A2F5"],
    "background": "#FAFBF8",
    "foreground": "#16233A",
    "tableAccent": "#5B3FA8",
    "good": "#1D7048",
    "neutral": "#9A5B00",
    "bad": "#B42318",
    "maximum": "#1D7048",
    "center": "#EEF1EC",
    "minimum": "#B42318",
    "textClasses": {
        "title": {"fontFace": "Segoe UI Semibold", "color": "#16233A", "fontSize": 14},
        "label": {"fontFace": "Segoe UI", "color": "#3A475A", "fontSize": 10},
    },
    "visualStyles": {
        "waterfallChart": {
            "*": {
                "sentimentColors": [{"increaseFill": {"solid": {"color": "#2A8A5C"}},
                                     "decreaseFill": {"solid": {"color": "#C8453A"}},
                                     "totalFill": {"solid": {"color": "#16233A"}}}]
            }
        }
    },
}

README = """Ledgerlight run {run_id}: {prior} to {current}
{rule}

Every figure here was computed from your source data, and every fact is
linked to the transactions that prove it.

{template_note}Open the ready-made report (Power BI Desktop)
--------------------------------------------
1. Unzip to a short folder such as C:\\Ledgerlight (Windows limits file
   paths to 260 characters, and a deeply nested folder
   can make Power BI report "Cannot read ... too long"). Keep everything
   inside "reports" together.
2. Double-click one of:
     reports/Ledgerlight Finance.pbip          corporate navy theme
     reports/Ledgerlight Executive Dark.pbip   dark executive theme
3. If Power BI shows empty visuals or a "refresh" prompt, click
   Home > Refresh once. The data is built into the report, so there is
   no file path or connection to set.
4. To get a single .pbix file: File > Save As > Power BI file (*.pbix).

Pages
-----
  Overview                headline, six KPI cards, revenue waterfall,
                          share-of-movement pie, change by driver,
                          drivers table (chart figures in thousands, $K)
  Evidence                pick a fact, see the exact transactions behind it
  Trend and transactions  account totals by period, every transaction

Build your own instead
----------------------
  data/Ledgerlight_{run_id}.xlsx
      Get data > Excel workbook > tick every sheet > Load.
  data/csv + data/powerquery
      Get data > Text/CSV per file, or paste a .pq script into
      Transform data > New Source > Blank Query > Advanced Editor and set
      the Folder line to where data/csv is on your disk.
  themes/*.json
      View > Themes > Browse for themes.

Tables
------
  Summary       headline, periods, revenue, scores, numbers verified
  Bridge        opening revenue and each driver, in bar order
  BridgeChart   the bridge as stacked columns: carried forward + change
  Drivers       the ranked driver table
  Evidence      each fact beside each transaction that proves it
  Facts         every computed fact
  Transactions  every transaction in the run, with its source file and row
  PeriodLines   period-summary lines, for trends
"""


def _rows(state: RunState) -> dict[str, list[dict[str, Any]]]:
    transactions = state.get("transactions", [])
    txns_by_id = {t.txn_id: t for t in transactions}
    facts = state.get("facts", [])
    analysis = to_frontend_analysis(state)
    drivers = _build_drivers(state)
    waterfall = _build_waterfall(state, drivers)
    prior, current = analysis["periods"]["prior"], analysis["periods"]["current"]

    # The closing total is Power BI's own Total bar, so it stays out of the
    # bars; its value lives on in Summary.to_revenue.
    bars = [step for step in waterfall if step["type"] != "end"]
    width = len(str(len(bars)))

    def bar_label(step: dict) -> str:
        return f"{step['name']} revenue" if step["type"] == "start" else step["name"]

    # Chart axis labels carry the percentage, so it shows on the bar itself:
    # bridge steps as a share of opening revenue, drivers as their own change.
    def bridge_label(step: dict) -> str:
        if step["type"] == "start" or not prior["revenue"]:
            return bar_label(step)
        return f"{bar_label(step)} ({step['value'] / abs(prior['revenue']):+.1%})"

    def chart_rows() -> list[dict]:
        rows, running = [], 0.0
        for index, step in enumerate(waterfall):
            row = {"chart_step": bridge_label(step) if step["type"] != "end" else f"{step['name']} revenue",
                   "chart_order": index + 1, "chart_carried": None, "chart_increase": None,
                   "chart_decrease": None, "chart_total": None}
            if step["type"] in ("start", "end"):
                row["chart_total"] = step["value"]
                running = step["value"]
            elif step["value"] >= 0:
                row["chart_carried"], row["chart_increase"] = running, step["value"]
                running += step["value"]
            else:
                running += step["value"]
                row["chart_carried"], row["chart_decrease"] = running, -step["value"]
            rows.append(row)
        return rows

    def driver_label(d: dict) -> str:
        return f"{d['driver']} (new)" if not d["prior"] else f"{d['driver']} ({d['share_of_change_pct']:+.1f}%)"

    return {
        "Summary": [
            {
                "run_id": analysis["run_id"],
                "company_id": state.get("company_id"),
                "from_period": prior["label"],
                "to_period": current["label"],
                "from_revenue": prior["revenue"],
                "to_revenue": current["revenue"],
                "revenue_change": round(current["revenue"] - prior["revenue"], 2),
                "headline": analysis["headline"],
                "narrative": analysis["summary"],
                "run_confidence": analysis["confidence"],
                "data_quality_score": analysis["data_quality_score"],
                "numbers_verified": analysis["grounding_badge"],
                "guardrail_status": analysis["guardrail_status"],
            }
        ],
        "Bridge": [
            {
                "bar": f"{index + 1:0{width}d}  {bar_label(step)}",
                "bridge_line": bar_label(step),
                "bridge_label": bridge_label(step),
                "bridge_type": step["type"],
                "bridge_amount": step["value"],
                "bridge_order": index + 1,
            }
            for index, step in enumerate(bars)
        ],
        "BridgeChart": chart_rows(),
        "Drivers": [
            {
                "rank": index + 1,
                "driver": d["driver"],
                "driver_label": driver_label(d),
                "driver_account": d["account"],
                "driver_prior": d["prior"],
                "driver_current": d["current"],
                "driver_change": d["amount"],
                "driver_pct_change": d["share_of_change_pct"],
                "driver_confidence": d["confidence"],
            }
            for index, d in enumerate(drivers)
        ],
        "Evidence": [
            {
                "fact_id": f.fact_id,
                "txn_id": t.txn_id,
                "fact": f.label,
                "fact_figure": f.formatted,
                "txn_date": t.posted_date,
                "txn_counterparty": t.counterparty_name or t.counterparty_id or "",
                "txn_account": t.account_name,
                "txn_amount": t.amount,
                "txn_memo": t.memo,
                "txn_source_row": t.source_row,
            }
            for f in facts
            for t in (txns_by_id[tid] for tid in f.evidence_txn_ids if tid in txns_by_id)
        ],
        "Facts": [
            {
                "fact_id": f.fact_id,
                "kind": f.kind,
                "label": f.label,
                "value": f.value,
                "unit": f.unit,
                "formatted": f.formatted,
                "pct": f.pct,
                "prior_period": f.basis.prior.period if f.basis else None,
                "prior_value": f.basis.prior.value if f.basis else None,
                "current_period": f.basis.current.period if f.basis else None,
                "current_value": f.basis.current.value if f.basis else None,
                "confidence": f.confidence,
                "evidence_count": f.evidence_count or len(f.evidence_txn_ids),
            }
            for f in facts
        ],
        "Transactions": [
            {
                "txn_id": t.txn_id,
                "posted_date": t.posted_date,
                "period_id": t.period_id,
                "account_id": t.account_id,
                "account_name": t.account_name,
                "account_type": t.account_type.value,
                "category": t.category,
                "counterparty": t.counterparty_name or t.counterparty_id or "",
                "amount": t.amount,
                "currency": t.currency,
                "memo": t.memo,
                "is_recurring": t.is_recurring,
                "flags": ";".join(t.flags),
                "source_file_id": t.source_file_id,
                "source_row": t.source_row,
            }
            for t in transactions
        ],
        "PeriodLines": [
            {
                "summary_period": summary.period_id,
                "summary_start": summary.start_date,
                "summary_end": summary.end_date,
                "summary_account_id": line.account_id,
                "summary_account": line.account_name,
                "summary_account_type": line.account_type.value,
                "summary_amount": line.amount,
            }
            for summary in state.get("period_summaries", [])
            for line in summary.lines
        ],
    }


def _workbook(rows: dict[str, list[dict[str, Any]]]) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="16233A")

    for sheet_name, columns in SHEETS.items():
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(list(columns))
        for cell in sheet[1]:
            cell.font = header_font
            cell.fill = header_fill

        for row in rows[sheet_name]:
            values = []
            for column in columns:
                value = row.get(column)
                values.append("" if value is None and columns[column] == "text" else value)
            sheet.append(values)
            for cell, kind in zip(sheet[sheet.max_row], columns.values()):
                if isinstance(cell.value, str):
                    # openpyxl turns any string starting with "=" into a
                    # formula. Memos come from user uploads (and the stress
                    # suite injects formulas on purpose), so force plain text.
                    cell.data_type = "s"
                elif kind in _NUMBER_FORMATS and cell.value is not None:
                    cell.number_format = _NUMBER_FORMATS[kind]

        for index, column in enumerate(columns, start=1):
            longest = max(
                [len(column)] + [len(str(r.get(column) or "")) for r in rows[sheet_name][:200]]
            )
            sheet.column_dimensions[get_column_letter(index)].width = min(max(longest + 2, 10), 60)
        sheet.freeze_panes = "A2"
        if sheet.max_row > 1:
            sheet.auto_filter.ref = sheet.dimensions

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


_M_TYPES = {"text": "type text", "money": "type number", "number": "type number", "pct": "type number",
            "int": "Int64.Type", "date": "type date", "bool": "type logical"}
_SIGNED_FIGURE = re.compile(r"^[+-]\(?\$?[\d.,]+[KMB%]?\)?$")


def _clean(value: Any) -> Any:
    """CSV cell value. Text a spreadsheet would read as a formula gets a
    leading apostrophe -- memos come from user uploads."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str) and value[:1] in ("=", "@", "\t", "\r"):
        return "'" + value
    if isinstance(value, str) and value[:1] in ("+", "-") and not _SIGNED_FIGURE.match(value):
        return "'" + value
    return value


def _csv(columns: dict[str, str], rows: list[dict[str, Any]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(list(columns))
    for row in rows:
        writer.writerow([_clean(row.get(col)) for col in columns])
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")  # BOM: Excel/Power BI detect UTF-8


def _power_query(table: str, columns: dict[str, str]) -> str:
    types = ", ".join(f'{{"{col}", {_M_TYPES[kind]}}}' for col, kind in columns.items())
    return (
        "let\n"
        '    Folder = "C:\\path\\to\\data\\csv\\",\n'
        f'    Source = Csv.Document(File.Contents(Folder & "{table}.csv"), '
        '[Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),\n'
        "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),\n"
        f'    Typed = Table.TransformColumnTypes(Promoted, {{{types}}}, "en-US")\n'
        "in\n"
        "    Typed\n"
    )


def build_powerbi_zip(state: RunState) -> bytes:
    run_id = state["run_id"]
    rows = _rows(state)
    has_template = TEMPLATE_PATH.is_file()
    template_note = "Also included: Ledgerlight.pbit, your team's template.\n\n" if has_template else ""
    title = f"Ledgerlight run {run_id}: {state['prior_period']} to {state['current_period']}"

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "README.txt",
            README.format(
                run_id=run_id,
                prior=state["prior_period"],
                current=state["current_period"],
                rule="=" * len(title),
                template_note=template_note,
            ),
        )
        for path, content in pbip_files(SHEETS, rows).items():
            archive.writestr(f"reports/{path}", content)
        archive.writestr(f"data/Ledgerlight_{run_id}.xlsx", _workbook(rows))
        for table, columns in SHEETS.items():
            archive.writestr(f"data/csv/{table}.csv", _csv(columns, rows[table]))
            archive.writestr(f"data/powerquery/{table}.pq", _power_query(table, columns))
        for theme in REPORT_THEMES.values():
            archive.writestr(f"themes/{theme['name']}.json", json.dumps(theme, indent=2))
        archive.writestr("themes/Ledgerlight App.json", json.dumps(THEME, indent=2))
        if has_template:
            archive.write(TEMPLATE_PATH, "Ledgerlight.pbit")
    return buffer.getvalue()
