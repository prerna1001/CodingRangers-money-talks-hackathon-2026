"""Ready-made Power BI reports for one run, as a Power BI Project (PBIP).

A .pbix stores its data in a compressed VertiPaq image that only Power BI
Desktop can write, so the backend cannot produce one per run. PBIP is
Microsoft's documented, file-based equivalent: double-click the .pbip and
Power BI Desktop opens the finished report; File > Save As turns it into a
.pbix.

The run's data is embedded in the semantic model itself (each table's
Power Query step decodes an inline, deflated JSON payload -- the same
technique Power BI's own "Enter data" uses), so the project opens from any
folder with no file paths to fix and nothing to connect.

Layout written into the zip:

    <name>.pbip                       one per report / theme
    <name>.Report/                    report pages + its theme
    Ledgerlight.SemanticModel/        tables, relationships, DAX measures
                                      (shared by both reports)
"""

from __future__ import annotations

import base64
import json
import uuid
import zlib
from datetime import date
from typing import Any

MODEL_FOLDER = "Ledgerlight.SemanticModel"

# ---------------------------------------------------------------------------
# Themes -- standard corporate finance palettes
# ---------------------------------------------------------------------------

_BASE_VISUAL_STYLE = {
    "title": [{"show": True, "fontFamily": "Segoe UI Semibold", "fontSize": 11, "alignment": "left"}],
    "border": [{"show": True, "radius": 4}],
    "dropShadow": [{"show": False}],
    "padding": [{"top": 8, "bottom": 8, "left": 12, "right": 12}],
}


def _theme(name: str, *, page: str, card: str, border: str, text: str, muted: str,
           data_colors: list[str], good: str, bad: str, total: str, header: str) -> dict:
    visual = json.loads(json.dumps(_BASE_VISUAL_STYLE))
    visual["title"][0]["fontColor"] = {"solid": {"color": text}}
    visual["border"][0]["color"] = {"solid": {"color": border}}
    visual["background"] = [{"show": True, "color": {"solid": {"color": card}}, "transparency": 0}]
    return {
        "name": name,
        "dataColors": data_colors,
        "background": card,
        "foreground": text,
        "tableAccent": header,
        "good": good,
        "neutral": "#F2A900",
        "bad": bad,
        "maximum": good,
        "center": muted,
        "minimum": bad,
        "textClasses": {
            "title": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": text},
            "header": {"fontFace": "Segoe UI Semibold", "fontSize": 10, "color": text},
            "label": {"fontFace": "Segoe UI", "fontSize": 9, "color": muted},
            "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 22, "color": text},
        },
        "visualStyles": {
            "*": {"*": visual},
            "page": {"*": {
                "background": [{"color": {"solid": {"color": page}}, "transparency": 0}],
                "outspace": [{"color": {"solid": {"color": page}}, "transparency": 0}],
            }},
            "waterfallChart": {"*": {"sentimentColors": [{
                "increaseFill": {"solid": {"color": good}},
                "decreaseFill": {"solid": {"color": bad}},
                "totalFill": {"solid": {"color": total}},
            }]}},
            "tableEx": {"*": {
                "columnHeaders": [{"backColor": {"solid": {"color": header}},
                                   "fontColor": {"solid": {"color": "#FFFFFF"}},
                                   "fontFamily": "Segoe UI Semibold"}],
                "grid": [{"gridHorizontal": True, "gridHorizontalColor": {"solid": {"color": border}},
                          "gridVertical": False, "rowPadding": 4}],
                "values": [{"fontColorPrimary": {"solid": {"color": text}},
                            "backColorPrimary": {"solid": {"color": card}},
                            "fontColorSecondary": {"solid": {"color": text}},
                            "backColorSecondary": {"solid": {"color": page}}}],
            }},
            "card": {"*": {
                "labels": [{"color": {"solid": {"color": text}}, "fontSize": 22,
                            "fontFamily": "Segoe UI Semibold"}],
                "categoryLabels": [{"show": True, "color": {"solid": {"color": muted}}, "fontSize": 10}],
            }},
        },
    }


THEMES = {
    "Finance": _theme(
        "Ledgerlight Corporate Navy",
        page="#F3F5F8", card="#FFFFFF", border="#DDE3EA", text="#1F2A44", muted="#5B6778",
        data_colors=["#1F3864", "#2E75B6", "#00A3A1", "#F2A900", "#7F8C9D", "#C0504D", "#70AD47", "#8064A2"],
        good="#2E7D32", bad="#C62828", total="#1F3864", header="#1F3864",
    ),
    "Executive Dark": _theme(
        "Ledgerlight Executive Dark",
        page="#0E1621", card="#16212E", border="#26364A", text="#E6EDF5", muted="#9AA8B8",
        data_colors=["#5B9BD5", "#2BB3A3", "#F2C14E", "#A5B4C8", "#E86A5F", "#7CC47F", "#B18CE0", "#4E79A7"],
        good="#3FB97A", bad="#E5534B", total="#5B9BD5", header="#1E3A5F",
    ),
}

# ---------------------------------------------------------------------------
# Semantic model (model.bim / TMSL)
# ---------------------------------------------------------------------------

_BIM_TYPES = {"text": "string", "money": "double", "number": "double", "pct": "double",
              "int": "int64", "date": "dateTime", "bool": "boolean"}
_M_TYPES = {"text": "type text", "money": "type number", "number": "type number", "pct": "type number",
            "int": "Int64.Type", "date": "type date", "bool": "type logical"}
_FORMATS = {"money": "\\$#,0;(\\$#,0);\\$#,0", "pct": "0%", "int": "0", "date": "yyyy-mm-dd"}
_NO_SUM = {"text", "int", "date", "bool", "pct"}
_COLUMN_FORMATS = {("Drivers", "driver_pct_change"): '+0.0"%";-0.0"%";0.0"%"'}
# Text columns shown in bar order rather than alphabetically.
_SORT_BY = {("Bridge", "bar"): "bridge_order", ("Bridge", "bridge_line"): "bridge_order"}

MEASURES = [
    ("Prior Revenue", "SUM(Summary[from_revenue])", _FORMATS["money"]),
    ("Current Revenue", "SUM(Summary[to_revenue])", _FORMATS["money"]),
    ("Revenue Change", "[Current Revenue] - [Prior Revenue]", "+\\$#,0;-\\$#,0;\\$#,0"),
    ("Revenue Change %", "DIVIDE([Revenue Change], [Prior Revenue])", "+0.0%;-0.0%;0.0%"),
    ("Data Quality", "AVERAGE(Summary[data_quality_score])", "0%"),
    ("Confidence", "AVERAGE(Summary[run_confidence])", "0%"),
    ("Numbers Verified",
     "VAR t = SELECTEDVALUE(Summary[numbers_verified]) RETURN IF(ISBLANK(t), \"n/a\", LEFT(t, SEARCH(\" \", t & \" \") - 1))",
     None),
    ("Driver Change", "SUM(Drivers[driver_change])", "+\\$#,0;-\\$#,0;\\$#,0"),
    ("Evidence Transactions", "DISTINCTCOUNT(Evidence[txn_id])", "#,0"),
    ("Evidence Amount", "SUMX(VALUES(Evidence[txn_id]), CALCULATE(MAX(Evidence[txn_amount])))", _FORMATS["money"]),
    ("Period Amount", "SUM(PeriodLines[summary_amount])", _FORMATS["money"]),
    ("Transaction Count", "COUNTROWS(Transactions)", "#,0"),
]


def _json_default(value: Any) -> Any:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"not serialisable: {type(value)}")


def _inline_m(columns: dict[str, str], rows: list[dict[str, Any]]) -> list[str]:
    """Power Query that rebuilds the table from an inline deflated JSON payload."""
    payload = json.dumps([[row.get(c) for c in columns] for row in rows], default=_json_default,
                         separators=(",", ":")).encode("utf-8")
    compressor = zlib.compressobj(9, zlib.DEFLATED, -15)  # raw deflate = Compression.Deflate
    packed = base64.b64encode(compressor.compress(payload) + compressor.flush()).decode("ascii")
    names = ", ".join(f'"{c}"' for c in columns)
    types = ", ".join(f'{{"{c}", {_M_TYPES[k]}}}' for c, k in columns.items())
    return [
        "let",
        f'    Source = Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("{packed}", '
        f"BinaryEncoding.Base64), Compression.Deflate)), {{{names}}}),",
        f'    Typed = Table.TransformColumnTypes(Source, {{{types}}}, "en-US")',
        "in",
        "    Typed",
    ]


def build_model_bim(sheets: dict[str, dict[str, str]], rows: dict[str, list[dict[str, Any]]]) -> dict:
    tables = []
    for name, columns in sheets.items():
        table_columns = []
        for column, kind in columns.items():
            entry = {
                "name": column,
                "dataType": _BIM_TYPES[kind],
                "sourceColumn": column,
                "summarizeBy": "none" if kind in _NO_SUM else "sum",
            }
            if (name, column) in _COLUMN_FORMATS:
                entry["formatString"] = _COLUMN_FORMATS[(name, column)]
            elif kind in _FORMATS:
                entry["formatString"] = _FORMATS[kind]
            if (name, column) in _SORT_BY:
                entry["sortByColumn"] = _SORT_BY[(name, column)]
            table_columns.append(entry)
        table = {
            "name": name,
            "columns": table_columns,
            "partitions": [{"name": name, "mode": "import",
                            "source": {"type": "m", "expression": _inline_m(columns, rows[name])}}],
        }
        if name == "Summary":
            table["measures"] = [
                {"name": m, "expression": expr, **({"formatString": fmt} if fmt else {})}
                for m, expr, fmt in MEASURES
            ]
        tables.append(table)

    return {
        "compatibilityLevel": 1567,
        "model": {
            "culture": "en-US",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "en-US",
            "tables": tables,
            "relationships": [
                {"name": "Evidence_to_Facts", "fromTable": "Evidence", "fromColumn": "fact_id",
                 "toTable": "Facts", "toColumn": "fact_id"},
                {"name": "Evidence_to_Transactions", "fromTable": "Evidence", "fromColumn": "txn_id",
                 "toTable": "Transactions", "toColumn": "txn_id"},
            ],
            "annotations": [
                {"name": "PBI_QueryOrder", "value": json.dumps(list(sheets))},
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
            ],
        },
    }

# ---------------------------------------------------------------------------
# Report (PBIR-Legacy report.json)
# ---------------------------------------------------------------------------


def _lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def _text(value: str) -> dict:
    return _lit("'" + value.replace("'", "''") + "'")


class _Visual:
    """Builds one visualContainer: fields -> prototypeQuery + projections."""

    def __init__(self, visual_type: str, box: tuple[int, int, int, int], title: str | None = None):
        self.visual_type = visual_type
        self.box = box
        self.title = title
        self.sources: dict[str, str] = {}
        self.select: list[dict] = []
        self.projections: dict[str, list[dict]] = {}
        self.order_by: list[dict] = []
        self.column_names: dict[str, str] = {}
        self.objects: dict[str, Any] = {}
        self.vc_objects: dict[str, Any] = {}

    def _source(self, table: str) -> str:
        if table not in self.sources:
            self.sources[table] = f"t{len(self.sources)}"
        return self.sources[table]

    def _field(self, table: str, field: str, kind: str) -> tuple[dict, str]:
        ref = {"SourceRef": {"Source": self._source(table)}}
        if kind == "measure":
            return {"Measure": {"Expression": ref, "Property": field}}, f"{table}.{field}"
        if kind == "sum":
            column = {"Column": {"Expression": ref, "Property": field}}
            return {"Aggregation": {"Expression": column, "Function": 0}}, f"Sum({table}.{field})"
        return {"Column": {"Expression": ref, "Property": field}}, f"{table}.{field}"

    def add(self, role: str, table: str, field: str, kind: str = "column", label: str | None = None) -> "_Visual":
        expr, query_ref = self._field(table, field, kind)
        if not any(s["Name"] == query_ref for s in self.select):
            self.select.append({**expr, "Name": query_ref})
        self.projections.setdefault(role, []).append({"queryRef": query_ref})
        if label:
            self.column_names[query_ref] = label
        return self

    def sort(self, table: str, field: str, kind: str = "column", descending: bool = False) -> "_Visual":
        expr, _ = self._field(table, field, kind)
        self.order_by.append({"Direction": 2 if descending else 1, "Expression": expr})
        return self

    def container(self, z: int) -> dict:
        x, y, w, h = self.box
        single: dict[str, Any] = {"visualType": self.visual_type, "drillFilterOtherVisuals": True}
        if self.select:
            query: dict[str, Any] = {
                "Version": 2,
                "From": [{"Name": alias, "Entity": table, "Type": 0} for table, alias in self.sources.items()],
                "Select": self.select,
            }
            if self.order_by:
                query["OrderBy"] = self.order_by
            single["projections"] = self.projections
            single["prototypeQuery"] = query
        if self.column_names:
            single["columnProperties"] = {k: {"displayName": v} for k, v in self.column_names.items()}
        if self.objects:
            single["objects"] = self.objects
        vc = dict(self.vc_objects)
        if self.title:
            vc["title"] = [{"properties": {"show": _lit("true"), "text": _text(self.title)}}]
        if vc:
            single["vcObjects"] = vc
        name = uuid.uuid4().hex[:20]
        config = {"name": name, "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": z, "width": w, "height": h}}],
                  "singleVisual": single}
        return {"x": x, "y": y, "z": z, "width": w, "height": h, "config": json.dumps(config), "filters": "[]"}


def _textbox(box: tuple[int, int, int, int], runs: list[tuple[str, dict]]) -> _Visual:
    visual = _Visual("textbox", box)
    visual.objects = {"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": text, "textStyle": style}]} for text, style in runs
    ]}}]}
    visual.vc_objects = {"background": [{"properties": {"show": _lit("false")}}],
                         "border": [{"properties": {"show": _lit("false")}}]}
    return visual


def _card(box: tuple[int, int, int, int], measure: str, label: str) -> _Visual:
    visual = _Visual("card", box).add("Values", "Summary", measure, "measure")
    visual.objects = {"categoryLabels": [{"properties": {"show": _lit("true")}}]}
    visual.column_names["Summary." + measure] = label
    return visual


def _table(box, title, table, columns, sort_field=None, descending=False) -> _Visual:
    """columns: (field, label, relative width). Widths are scaled so the
    columns fill the visual instead of bunching up on the left."""
    visual = _Visual("tableEx", box, title)
    for field, label, _ in columns:
        visual.add("Values", table, field, label=label)
    if sort_field:
        visual.sort(table, sort_field, descending=descending)
    usable = box[2] - 44
    total = sum(weight for _, _, weight in columns)
    visual.objects = {
        "total": [{"properties": {"totals": _lit("false")}}],
        "columnWidth": [
            {"properties": {"value": _lit(f"{usable * weight / total:.1f}D")},
             "selector": {"metadata": f"{table}.{field}"}}
            for field, _, weight in columns
        ],
    }
    return visual


def _header(title: str, subtitle: str, colors: dict) -> _Visual:
    return _textbox((24, 10, 1232, 74), [
        (title, {"fontFamily": "Segoe UI Semibold", "fontSize": "18pt", "color": colors["text"]}),
        (subtitle, {"fontFamily": "Segoe UI", "fontSize": "10pt", "color": colors["muted"]}),
    ])


def _pages(summary: dict[str, Any], theme: dict) -> list[tuple[str, list[_Visual]]]:
    colors = {"text": theme["foreground"], "muted": theme["textClasses"]["label"]["color"]}
    period = f"{summary['from_period']} to {summary['to_period']}"
    company = summary.get("company_id") or ""
    subtitle = f"{company}, {period}. Every figure traced to source transactions." if company else period

    gutter, top, width = 24, 96, 1232
    card_w = (width - 5 * 12) // 6
    cards = [
        ("Prior Revenue", f"{summary['from_period']} revenue"),
        ("Current Revenue", f"{summary['to_period']} revenue"),
        ("Revenue Change", "Change"),
        ("Revenue Change %", "Change %"),
        ("Data Quality", "Data quality"),
        ("Numbers Verified", "Numbers verified"),
    ]
    overview = [_header(summary["headline"] or "Revenue variance", subtitle, colors)]
    overview += [_card((gutter + i * (card_w + 12), top, card_w, 92), m, label) for i, (m, label) in enumerate(cards)]
    overview.append(
        _Visual("waterfallChart", (gutter, 200, 740, 292), f"Revenue bridge, {period}")
        .add("Category", "Bridge", "bridge_line", label="Step").add("Y", "Bridge", "bridge_amount", "sum", label="Amount")
        .sort("Bridge", "bridge_line")
    )
    overview.append(
        _Visual("clusteredBarChart", (776, 200, 480, 292), "Change by driver")
        .add("Category", "Drivers", "driver").add("Y", "Summary", "Driver Change", "measure", label="Change")
        .sort("Summary", "Driver Change", "measure", descending=True)
    )
    overview.append(_table((gutter, 504, width, 204), "Drivers, largest first", "Drivers", [
        ("rank", "Rank", 0.6), ("driver", "Driver", 2.2), ("driver_account", "Account", 2.2),
        ("driver_prior", "Prior", 1.3), ("driver_current", "Current", 1.3), ("driver_change", "Change", 1.3),
        ("driver_pct_change", "% change", 1.1), ("driver_confidence", "Confidence", 1.1),
    ], sort_field="rank"))

    evidence = [_header("Evidence", "Pick a fact to see the exact transactions behind it.", colors)]
    slicer = _Visual("slicer", (gutter, top, 360, 612), "Pick a fact").add("Values", "Evidence", "fact")
    slicer.objects = {"data": [{"properties": {"mode": _text("Basic")}}],
                      "selection": [{"properties": {"singleSelect": _lit("true")}}],
                      "header": [{"properties": {"show": _lit("false")}}]}
    evidence.append(slicer)
    evidence.append(_card((396, top, 420, 92), "Evidence Transactions", "Source transactions"))
    evidence.append(_card((828, top, 428, 92), "Evidence Amount", "Their total"))
    evidence.append(_table((396, 200, 860, 508), "Source transactions", "Evidence", [
        ("txn_date", "Date", 1.1), ("txn_counterparty", "Counterparty", 1.6), ("txn_account", "Account", 1.5),
        ("txn_amount", "Amount", 1.1), ("txn_memo", "Memo", 2.6), ("txn_source_row", "Row", 0.6),
        ("txn_id", "Transaction ID", 1.5),
    ], sort_field="txn_date"))

    trend = [_header("Trend and transactions", "Account totals by period, and every transaction in this run.", colors)]
    trend.append(
        _Visual("clusteredColumnChart", (gutter, top, width, 292), "Amount by account and period")
        .add("Category", "PeriodLines", "summary_period", label="Period")
        .add("Series", "PeriodLines", "summary_account", label="Account")
        .add("Y", "Summary", "Period Amount", "measure", label="Amount")
        .sort("PeriodLines", "summary_period")
    )
    trend.append(_table((gutter, 400, width, 308), "Transactions", "Transactions", [
        ("posted_date", "Date", 1.0), ("period_id", "Period", 0.8), ("account_name", "Account", 1.5),
        ("counterparty", "Counterparty", 1.5), ("category", "Category", 1.2), ("amount", "Amount", 1.0),
        ("memo", "Memo", 2.6), ("txn_id", "Transaction ID", 1.4),
    ], sort_field="posted_date"))

    return [("Overview", overview), ("Evidence", evidence), ("Trend and transactions", trend)]


def build_report_json(summary: dict[str, Any], theme_key: str) -> tuple[dict, str]:
    theme = THEMES[theme_key]
    theme_file = theme["name"].replace(" ", "") + ".json"
    sections = []
    for index, (display_name, visuals) in enumerate(_pages(summary, theme)):
        sections.append({
            "name": f"ReportSection{index + 1:02d}{uuid.uuid4().hex[:8]}",
            "displayName": display_name,
            "displayOption": 1,
            "width": 1280,
            "height": 720,
            "ordinal": index,
            "config": "{}",
            "filters": "[]",
            "visualContainers": [v.container(z * 1000) for z, v in enumerate(visuals)],
        })
    config = {
        "version": "5.59",
        "themeCollection": {"customTheme": {"name": theme_file, "version": "5.59", "type": 1}},
        "activeSectionIndex": 0,
        "defaultDrillFilterOtherVisuals": True,
        "linguisticSchemaSyncVersion": 0,
        "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True,
                     "useStylableVisualContainerHeader": True, "exportDataMode": 1},
        "objects": {"outspacePane": [{"properties": {"expanded": _lit("false")}}]},
    }
    report = {
        "config": json.dumps(config),
        "layoutOptimization": 0,
        "resourcePackages": [{"resourcePackage": {
            "name": "RegisteredResources", "type": 1, "disabled": False,
            "items": [{"type": 201, "name": theme_file, "path": theme_file}],
        }}],
        "sections": sections,
    }
    return report, theme_file


def pbip_files(sheets: dict[str, dict[str, str]], rows: dict[str, list[dict[str, Any]]]) -> dict[str, bytes]:
    """Every file of the project, keyed by its path inside the zip's reports/ folder."""
    files: dict[str, bytes] = {
        f"{MODEL_FOLDER}/definition.pbism": json.dumps({"version": "1.0", "settings": {}}, indent=2).encode(),
        f"{MODEL_FOLDER}/model.bim": json.dumps(build_model_bim(sheets, rows), indent=2).encode(),
    }
    summary = rows["Summary"][0]
    for theme_key in THEMES:
        name = f"Ledgerlight {theme_key}"
        report_folder = f"{name}.Report"
        report, theme_file = build_report_json(summary, theme_key)
        files[f"{name}.pbip"] = json.dumps({
            "version": "1.0",
            "artifacts": [{"report": {"path": report_folder}}],
            "settings": {"enableAutoRecovery": True},
        }, indent=2).encode()
        files[f"{report_folder}/definition.pbir"] = json.dumps({
            "version": "1.0",
            "datasetReference": {"byPath": {"path": f"../{MODEL_FOLDER}"}, "byConnection": None},
        }, indent=2).encode()
        files[f"{report_folder}/report.json"] = json.dumps(report, indent=2).encode()
        files[f"{report_folder}/StaticResources/RegisteredResources/{theme_file}"] = json.dumps(
            THEMES[theme_key], indent=2).encode()
    return files
