from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RunRecord(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    company_id: Mapped[str] = mapped_column(String, index=True)
    current_period: Mapped[str] = mapped_column(String, index=True)
    prior_period: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, default="created")
    data_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FileRecord(Base):
    __tablename__ = "files"

    file_id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    filename: Mapped[str] = mapped_column(String)
    file_type: Mapped[str] = mapped_column(String)
    mime_type: Mapped[str | None] = mapped_column(String, nullable=True)
    source_format: Mapped[str | None] = mapped_column(String, nullable=True)
    classification: Mapped[str | None] = mapped_column(String, nullable=True)
    extraction_status: Mapped[str | None] = mapped_column(String, nullable=True)
    review_status: Mapped[str | None] = mapped_column(String, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str] = mapped_column(String)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLogRecord(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
