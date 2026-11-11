"""Multi-format upload and review endpoints.

Documents are extracted locally, classified, and kept out of the financial
engine until a deterministic parser or a user confirmation makes their role
explicit. This protects calculations from ambiguous OCR and narrative text.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

import auth0_setup
from models.schemas import AvailableFile, CanonicalTransaction, PeriodSummary
from services import csv_parser
from services.ingestion import ExtractionResult, IngestionService
from services.injection_filter import detect, sanitize
from services.rag_store import Document
from services.reference_store import add as add_reference_document

router = APIRouter()

FileType = Literal["transaction_csv", "period_summary_csv"]
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_TABLE_ROWS = 50_000


@dataclass
class UploadedFile:
    file_id: str
    user_id: str
    filename: str
    detected_type: str
    classification: str
    company_id: str
    period_id: str
    sha256: str
    extraction: ExtractionResult
    file_type: FileType | None = None
    review_status: Literal["ready", "review_required", "reference", "rejected"] = "review_required"
    row_count: int = 0
    transactions: list[CanonicalTransaction] = field(default_factory=list)
    period_summaries: list[PeriodSummary] = field(default_factory=list)
    reference_document_ids: list[str] = field(default_factory=list)


class ConfirmUploadRequest(BaseModel):
    use_as: Literal["transaction_csv", "period_summary_csv", "reference_document"]
    table_index: int = Field(default=0, ge=0)
    rows: list[dict[str, str]] | None = None


_UPLOADED_FILES: dict[str, UploadedFile] = {}
_ingestion = IngestionService()


def _sanitize_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[str]]:
    clean_rows: list[dict[str, str]] = []
    warnings: list[str] = []
    for index, row in enumerate(rows, start=1):
        clean: dict[str, str] = {}
        for key, value in row.items():
            value = str(value or "")
            if detect(value):
                warnings.append(f"Potential prompt injection quarantined in extracted row {index}, field {key}.")
            clean[str(key)] = sanitize(value)
        clean_rows.append(clean)
    return clean_rows, warnings


def _parse_rows(uploaded: UploadedFile, rows: list[dict[str, str]], file_type: FileType) -> None:
    if len(rows) > MAX_TABLE_ROWS:
        raise HTTPException(status_code=413, detail=f"Extracted table exceeds the {MAX_TABLE_ROWS:,} row limit")
    clean_rows, warnings = _sanitize_rows(rows)
    uploaded.extraction.warnings.extend(warnings)
    try:
        if file_type == "transaction_csv":
            uploaded.transactions = csv_parser.parse_transactions(clean_rows, source_file_id=uploaded.file_id)
            uploaded.period_summaries = []
            uploaded.row_count = len(uploaded.transactions)
        else:
            uploaded.period_summaries = csv_parser.parse_period_summaries(clean_rows)
            uploaded.transactions = []
            uploaded.row_count = len(uploaded.period_summaries)
    except (ValueError, KeyError) as exc:
        headers = list(clean_rows[0]) if clean_rows else []
        raise HTTPException(
            status_code=400,
            detail=(f"Could not normalize extracted table: {exc}. Columns found: {headers or '(none)'}. "
                    "Confirm the mapped date, account, type, and amount columns."),
        ) from exc
    uploaded.file_type = file_type
    uploaded.review_status = "ready"


def _store_reference(uploaded: UploadedFile) -> None:
    text = sanitize(uploaded.extraction.text, max_len=20_000)
    if not text:
        raise HTTPException(status_code=400, detail="No extractable reference text was found in this document")
    document_id = f"upload:{uploaded.file_id}:reference"
    add_reference_document(
        uploaded.user_id,
        uploaded.company_id,
        Document(
            chunk_id=document_id,
            source=uploaded.filename,
            text=text,
            metadata={"file_id": uploaded.file_id, "classification": "reference_document"},
        ),
    )
    uploaded.reference_document_ids = [document_id]
    uploaded.review_status = "reference"


def _response(uploaded: UploadedFile) -> dict:
    return {
        "file_id": uploaded.file_id,
        "filename": uploaded.filename,
        "file_type": uploaded.file_type,
        "detected_type": uploaded.detected_type,
        "classification": uploaded.classification,
        "sha256": uploaded.sha256,
        "row_count": uploaded.row_count,
        "review_status": uploaded.review_status,
        "preview": [item.model_dump() for item in (uploaded.transactions or uploaded.period_summaries)[:5]],
        **uploaded.extraction.to_dict(),
    }


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    company_id: str = Form(""),
    period_id: str = Form(""),
    user_id: str = Depends(auth0_setup.get_current_user_id),
) -> dict:
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB limit")
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded files require a filename")
    try:
        extraction = _ingestion.inspect(file.filename, raw, file.content_type)
    except (UnicodeDecodeError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    uploaded = UploadedFile(
        file_id=f"file_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        filename=file.filename,
        detected_type=extraction.detected_type,
        classification=extraction.classification,
        company_id=company_id.strip() or "default",
        period_id=period_id,
        sha256=_ingestion.fingerprint(raw),
        extraction=extraction,
    )
    _UPLOADED_FILES[uploaded.file_id] = uploaded

    # Any confidently classified table follows the same deterministic
    # normalizer as CSV. Users can upload a whole batch once rather than
    # identifying each document by hand.
    if extraction.classification in {"transaction_data", "period_summary"} and extraction.tables:
        file_type: FileType = "period_summary_csv" if extraction.classification == "period_summary" else "transaction_csv"
        _parse_rows(uploaded, extraction.tables[0].rows, file_type)
    elif extraction.classification == "reference_document":
        _store_reference(uploaded)
    elif extraction.classification == "unusable":
        uploaded.review_status = "rejected"
    return _response(uploaded)


def _get_owned_upload(file_id: str, user_id: str) -> UploadedFile:
    uploaded = _UPLOADED_FILES.get(file_id)
    if uploaded is None or uploaded.user_id != user_id:
        # Deliberately 404, not 403: knowing a file_id must not confirm that
        # another account has that upload.
        raise HTTPException(status_code=404, detail=f"Uploaded file {file_id} not found")
    return uploaded


@router.get("/uploads/{file_id}")
def get_upload(file_id: str, user_id: str = Depends(auth0_setup.get_current_user_id)) -> dict:
    return _response(_get_owned_upload(file_id, user_id))


@router.post("/uploads/{file_id}/confirm")
def confirm_upload(
    file_id: str,
    request: ConfirmUploadRequest,
    user_id: str = Depends(auth0_setup.get_current_user_id),
) -> dict:
    uploaded = _get_owned_upload(file_id, user_id)
    if request.use_as == "reference_document":
        _store_reference(uploaded)
        return _response(uploaded)
    rows = request.rows
    if rows is None:
        if request.table_index >= len(uploaded.extraction.tables):
            raise HTTPException(status_code=400, detail="Choose a detected table or provide reviewed rows")
        rows = uploaded.extraction.tables[request.table_index].rows
    _parse_rows(uploaded, rows, request.use_as)
    return _response(uploaded)


def get_uploaded_transactions(file_ids: list[str], *, user_id: str) -> list[CanonicalTransaction]:
    transactions: list[CanonicalTransaction] = []
    for file_id in file_ids:
        uploaded = _get_owned_upload(file_id, user_id)
        if uploaded.review_status != "ready" or uploaded.file_type != "transaction_csv":
            raise HTTPException(status_code=400, detail=f"File {uploaded.filename} must be reviewed as transaction data before analysis")
        transactions.extend(uploaded.transactions)
    return transactions


def get_uploaded_period_summaries(file_ids: list[str], *, user_id: str) -> list[PeriodSummary]:
    summaries: list[PeriodSummary] = []
    for file_id in file_ids:
        uploaded = _get_owned_upload(file_id, user_id)
        if uploaded.review_status != "ready" or uploaded.file_type != "period_summary_csv":
            raise HTTPException(status_code=400, detail=f"File {uploaded.filename} must be reviewed as period summaries before analysis")
        summaries.extend(uploaded.period_summaries)
    return summaries


def get_available_files(file_ids: list[str], *, user_id: str) -> list[AvailableFile]:
    files: list[AvailableFile] = []
    for file_id in file_ids:
        uploaded = _get_owned_upload(file_id, user_id)
        files.append(
            AvailableFile(
                file_id=uploaded.file_id,
                type=uploaded.file_type or "transaction_csv",
                period_id=uploaded.period_id,
                sha256=uploaded.sha256,
                row_count=uploaded.row_count,
                source_format=uploaded.filename.rsplit(".", 1)[-1].lower() if "." in uploaded.filename else None,
                mime_type=uploaded.detected_type,
                classification=uploaded.classification,
                review_status=uploaded.review_status,
                ocr_confidence=uploaded.extraction.ocr_confidence,
                page_count=uploaded.extraction.page_count,
            )
        )
    return files
