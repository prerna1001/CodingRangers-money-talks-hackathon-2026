from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


Classification = Literal[
    "transaction_data",
    "period_summary",
    "financial_table",
    "reference_document",
    "unusable",
]


@dataclass(frozen=True)
class SourceLocation:
    page: int | None = None
    sheet: str | None = None
    table: int | None = None
    row: int | None = None
    cell: str | None = None
    bbox: tuple[float, float, float, float] | None = None

    def to_dict(self) -> dict:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass
class ExtractionTable:
    headers: list[str]
    rows: list[dict[str, str]]
    source: SourceLocation
    confidence: float = 1.0

    def preview(self, limit: int = 10) -> dict:
        return {
            "headers": self.headers,
            "rows": self.rows[:limit],
            "source": self.source.to_dict(),
            "confidence": round(self.confidence, 3),
        }


@dataclass
class ExtractionResult:
    detected_type: str
    classification: Classification
    tables: list[ExtractionTable] = field(default_factory=list)
    text: str = ""
    warnings: list[str] = field(default_factory=list)
    page_count: int | None = None
    requires_ocr: bool = False
    ocr_confidence: float | None = None

    @property
    def review_required(self) -> bool:
        return self.classification in {"financial_table", "unusable"} or self.requires_ocr or (
            self.ocr_confidence is not None and self.ocr_confidence < 0.9
        )

    def to_dict(self) -> dict:
        return {
            "detected_type": self.detected_type,
            "classification": self.classification,
            "tables": [table.preview() for table in self.tables],
            "text_preview": self.text[:2000],
            "warnings": self.warnings,
            "page_count": self.page_count,
            "requires_ocr": self.requires_ocr,
            "ocr_confidence": self.ocr_confidence,
            "review_required": self.review_required,
        }
