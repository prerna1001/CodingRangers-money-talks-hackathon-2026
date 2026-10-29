"""In-process registry for reviewed reference documents.

This mirrors the current in-memory upload/run registries. A database-backed
file store can replace it later without changing the ingestion or graph API.
"""

from __future__ import annotations

from services.rag_store import Document

_BY_OWNER_AND_COMPANY: dict[tuple[str, str], list[Document]] = {}


def add(user_id: str, company_id: str, document: Document) -> None:
    docs = _BY_OWNER_AND_COMPANY.setdefault((user_id, company_id), [])
    if not any(existing.chunk_id == document.chunk_id for existing in docs):
        docs.append(document)


def for_company(user_id: str, company_id: str) -> list[Document]:
    return list(_BY_OWNER_AND_COMPANY.get((user_id, company_id), []))
