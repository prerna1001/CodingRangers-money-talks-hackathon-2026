from __future__ import annotations

from .types import Classification, ExtractionTable


TRANSACTION_DATE_HEADERS = {"date", "posted_date", "transaction_date"}
AMOUNT_HEADERS = {"amount", "value"}
SUMMARY_HEADERS = {"period_id", "period", "month", "start_date", "end_date"}
FINANCE_TERMS = {"revenue", "expense", "account", "balance", "invoice", "transaction", "amount"}


def classify(tables: list[ExtractionTable], text: str) -> Classification:
    """Classify by stable table structure before considering free-form text."""
    for table in tables:
        headers = {header.strip().lower() for header in table.headers}
        if headers & TRANSACTION_DATE_HEADERS and headers & AMOUNT_HEADERS:
            return "transaction_data"
        if headers & SUMMARY_HEADERS and headers & AMOUNT_HEADERS:
            return "period_summary"
        if len(table.headers) >= 2 and len(table.rows) > 0:
            return "financial_table"
    terms = {word.strip(".,:;()[]").lower() for word in text.split()}
    return "reference_document" if terms & FINANCE_TERMS or text.strip() else "unusable"
