"""Local-first multi-format ingestion for finance documents.

Nothing in this package sends raw user documents to an LLM. Extractors
produce structured tables or reference text; normalization remains the only
path into the deterministic financial pipeline.
"""

from .service import IngestionService
from .types import ExtractionResult, ExtractionTable, SourceLocation

__all__ = ["ExtractionResult", "ExtractionTable", "IngestionService", "SourceLocation"]
