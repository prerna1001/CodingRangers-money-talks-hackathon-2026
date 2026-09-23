"""POST /api/upload (plan section 14.3).

Parses an uploaded CSV via Codex's services/csv_parser.py into canonical
transactions or period summaries and stores them in an in-memory registry
keyed by file_id, so a subsequent POST /api/analyze can reference them
by id instead of always running the checked-in demo fixture.

Persistence here is the same kind of placeholder as api/routes/analyze.py's
`_RUNS` dict -- Codex's `models/db.py` FileRecord table already defines
the real schema (BACKEND_TASK_SPLIT.md section 2/3); this becomes a
drop-in swap once a session/engine layer exists on top of it.

Input guardrails enforced here (plan section 10.2): file size limit,
extension check, and UTF-8 validation. Free-text sanitization and
prompt-injection detection happen downstream, once these rows reach
agents/profile_builder.py -- never here, and never before ingestion.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from models.schemas import CanonicalTransaction, PeriodSummary
from services import csv_parser

router = APIRouter()

FileType = Literal["transaction_csv", "period_summary_csv"]

MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # plan section 10.2: file size limits


@dataclass
class UploadedFile:
    file_id: str
    file_type: FileType
    company_id: str
    period_id: str
    sha256: str
    row_count: int
    transactions: list[CanonicalTransaction] = field(default_factory=list)
    period_summaries: list[PeriodSummary] = field(default_factory=list)


_UPLOADED_FILES: dict[str, UploadedFile] = {}


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    # Defaulted rather than required: the dashboard's UploadCard posts just
    # the file (Frontend/src/services/api.js), and a transaction CSV for the
    # demo company is the overwhelmingly common case. Callers that need the
    # other file type still pass it explicitly.
    file_type: FileType = Form("transaction_csv"),
    company_id: str = Form("demo_saas"),
    period_id: str = Form(""),
) -> dict:
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit"
        )
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File is not valid UTF-8 text")

    file_id = f"file_{uuid.uuid4().hex[:12]}"
    sha256 = hashlib.sha256(raw).hexdigest()
    rows = csv_parser.read_csv_text(text)

    # Auto-detect the file type so the dashboard can accept a drop of several
    # CSVs at once without asking the user to label each one. A period summary
    # has period bounds and no transaction-level date; a transactions file has
    # the date. Explicitly-passed file_type still wins.
    if rows:
        headers = {h.strip().lower() for h in rows[0]}
        looks_like_summary = {"start_date", "end_date"} <= headers or (
            "period_id" in headers and not headers & {"posted_date", "date", "transaction_date", "txn_id"}
        )
        if looks_like_summary:
            file_type = "period_summary_csv"
        elif headers & {"posted_date", "date", "transaction_date"}:
            file_type = "transaction_csv"

    try:
        if file_type == "transaction_csv":
            transactions = csv_parser.parse_transactions(rows, source_file_id=file_id)
            uploaded = UploadedFile(
                file_id=file_id,
                file_type=file_type,
                company_id=company_id,
                period_id=period_id,
                sha256=sha256,
                row_count=len(transactions),
                transactions=transactions,
            )
            preview = [t.model_dump() for t in transactions[:5]]
        else:
            period_summaries = csv_parser.parse_period_summaries(rows)
            uploaded = UploadedFile(
                file_id=file_id,
                file_type=file_type,
                company_id=company_id,
                period_id=period_id,
                sha256=sha256,
                row_count=len(period_summaries),
                period_summaries=period_summaries,
            )
            preview = [p.model_dump() for p in period_summaries[:5]]
    except (ValueError, KeyError) as exc:
        # Surface the header row we actually saw -- when a CSV is rejected the
        # first question is always "which column is it unhappy about?", and
        # answering it here saves a round trip through the server logs.
        headers = list(rows[0].keys()) if rows else []
        raise HTTPException(
            status_code=400,
            detail=(
                f"Could not parse CSV: {exc}. "
                f"Columns found: {headers or '(no rows parsed)'}. "
                "A transactions file needs at least a date and an amount column; "
                "see test_data/ for working examples."
            ),
        )

    _UPLOADED_FILES[file_id] = uploaded
    return {
        "file_id": file_id,
        "file_type": file_type,
        "sha256": sha256,
        "row_count": uploaded.row_count,
        "preview": preview,
    }


def get_uploaded_transactions(file_ids: list[str]) -> list[CanonicalTransaction]:
    transactions: list[CanonicalTransaction] = []
    for file_id in file_ids:
        uploaded = _UPLOADED_FILES.get(file_id)
        if uploaded is None:
            raise HTTPException(status_code=404, detail=f"Uploaded file {file_id} not found")
        transactions.extend(uploaded.transactions)
    return transactions


def get_uploaded_period_summaries(file_ids: list[str]) -> list[PeriodSummary]:
    summaries: list[PeriodSummary] = []
    for file_id in file_ids:
        uploaded = _UPLOADED_FILES.get(file_id)
        if uploaded is None:
            raise HTTPException(status_code=404, detail=f"Uploaded file {file_id} not found")
        summaries.extend(uploaded.period_summaries)
    return summaries
