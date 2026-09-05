"""RAG Agent (plan section 9).

Query construction is driven by the flagged variances/drivers themselves,
not by any user question -- for each material fact, build a query from
its label and pull the most relevant prior context (previous reports,
board notes, chart-of-accounts definitions, vendor mappings).

Hard rule: retrieved content is context, never arithmetic. It can explain
*why* something happened; it can never change a number the Analyst states.
This agent never returns anything that goes into the fact table.
"""

from __future__ import annotations

from config import RAG_RERANK_K, RAG_RETRIEVE_K
from models.schemas import Fact, RetrievedChunk
from services.rag_store import RagStore

_RELEVANT_KINDS = {"variance", "driver", "anomaly"}


def build_queries(facts: list[Fact]) -> list[str]:
    return [f"{f.label} {f.formatted}" for f in facts if f.kind in _RELEVANT_KINDS]


def retrieve_for_facts(
    store: RagStore,
    facts: list[Fact],
    *,
    k: int = RAG_RETRIEVE_K,
    rerank_k: int = RAG_RERANK_K,
) -> list[RetrievedChunk]:
    """Retrieve k candidates per flagged fact, keep the top `rerank_k` of
    each, then dedupe across facts by chunk id (keeping the higher score).
    """
    best_by_id: dict[str, RetrievedChunk] = {}
    for query in build_queries(facts):
        for chunk in store.query(query, k=k)[:rerank_k]:
            existing = best_by_id.get(chunk.chunk_id)
            if existing is None or chunk.relevance_score > existing.relevance_score:
                best_by_id[chunk.chunk_id] = chunk
    return sorted(best_by_id.values(), key=lambda c: -c.relevance_score)
