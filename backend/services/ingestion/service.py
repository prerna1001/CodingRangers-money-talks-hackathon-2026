from __future__ import annotations

import hashlib
from pathlib import Path

from .classifier import classify
from .extractors import extract_csv, extract_docx, extract_image, extract_json, extract_pdf, extract_xlsx
from .types import ExtractionResult


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".pdf", ".docx", ".txt", ".json", ".jpeg", ".jpg", ".png", ".webp", ".tiff", ".heic"}
IMAGE_EXTENSIONS = {".jpeg", ".jpg", ".png", ".webp", ".tiff", ".heic"}
MAX_PDF_PAGES = 100
MAX_IMAGE_PIXELS = 30_000_000


class IngestionService:
    def inspect(self, filename: str, raw: bytes, declared_mime: str | None = None) -> ExtractionResult:
        suffix = Path(filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported format {suffix or '(no extension)'}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}.")
        if not raw:
            raise ValueError("The uploaded file is empty.")
        self._validate_signature(suffix, raw)
        if suffix == ".csv":
            tables, text, warnings = extract_csv(raw)
            page_count = None
            used_ocr = False
            score = None
        elif suffix == ".xlsx":
            tables, text, warnings = extract_xlsx(raw)
            page_count = None
            used_ocr = False
            score = None
        elif suffix == ".docx":
            tables, text, warnings = extract_docx(raw)
            page_count = None
            used_ocr = False
            score = None
        elif suffix == ".pdf":
            tables, text, warnings, page_count, used_ocr, score = extract_pdf(raw)
        elif suffix in IMAGE_EXTENSIONS:
            tables, text, warnings, score = extract_image(raw)
            page_count = 1
            used_ocr = True
        elif suffix == ".json":
            tables, text, warnings = extract_json(raw)
            page_count = None
            used_ocr = False
            score = None
        else:
            text = raw.decode("utf-8")
            tables, warnings, page_count, used_ocr, score = [], [], None, False, None
        return ExtractionResult(
            detected_type=declared_mime or self._detected_type(suffix),
            classification=classify(tables, text),
            tables=tables,
            text=text,
            warnings=warnings,
            page_count=page_count,
            requires_ocr=used_ocr,
            ocr_confidence=score,
        )

    @staticmethod
    def _validate_signature(suffix: str, raw: bytes) -> None:
        """Fail closed for formats with an unambiguous binary signature."""
        if suffix == ".pdf" and not raw.startswith(b"%PDF-"):
            raise ValueError("The file extension says PDF, but its binary signature is not a PDF.")
        if suffix in {".xlsx", ".docx"} and not raw.startswith(bytes((0x50, 0x4B, 0x03, 0x04))):
            raise ValueError("The file extension says Office Open XML, but its binary signature is invalid.")
        if suffix in IMAGE_EXTENSIONS:
            try:
                from PIL import Image
                from io import BytesIO

                image = Image.open(BytesIO(raw))
                if image.width * image.height > MAX_IMAGE_PIXELS:
                    raise ValueError(f"Image exceeds the {MAX_IMAGE_PIXELS:,} pixel safety limit.")
                image.verify()
            except ImportError:
                return
            except ValueError:
                raise
            except Exception as exc:
                raise ValueError("The image is malformed or does not match its file extension.") from exc

    @staticmethod
    def fingerprint(raw: bytes) -> str:
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _detected_type(suffix: str) -> str:
        return {
            ".csv": "text/csv", ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        }.get(suffix, "image/*" if suffix in IMAGE_EXTENSIONS else "text/plain")
