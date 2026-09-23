"""RAG store: Chroma + embeddings when available, BM25 keyword search as a
graceful fallback otherwise (plan section 9.2).

Chroma and sentence-transformers are optional dependencies -- the pipeline
must not hard-fail in an environment where a multi-hundred-MB embedding
model hasn't been downloaded. This mirrors the plan's own "every external
dependency has a cached fallback" principle (section 3, 18), just applied
to a local dependency instead of a network one.

Hard rule enforced by the caller (agents/rag_agent.py), not this module:
retrieved content is context, never arithmetic -- never embed raw
transaction rows, only rollups and prose (plan section 9.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from config import CHROMA_PERSIST_DIR, RAG_RETRIEVE_K
from models.schemas import RetrievedChunk


@dataclass
class Document:
    chunk_id: str
    source: str
    text: str
    metadata: dict = field(default_factory=dict)


class RagStore:
    def __init__(self, persist_dir: str = CHROMA_PERSIST_DIR) -> None:
        self._docs: dict[str, Document] = {}
        self._collection = None
        self._bm25 = None
        self._bm25_ids: list[str] = []

        try:
            import chromadb

            client = chromadb.PersistentClient(path=persist_dir)
            self._collection = client.get_or_create_collection("ledgerlight_rag")
        except ImportError:
            self._collection = None

    @property
    def backend(self) -> str:
        return "chroma" if self._collection is not None else "bm25" if self._bm25 is not None else "empty"

    def add_documents(self, docs: list[Document]) -> None:
        for doc in docs:
            self._docs[doc.chunk_id] = doc

        if self._collection is not None:
            self._collection.upsert(
                ids=[d.chunk_id for d in docs],
                documents=[d.text for d in docs],
                metadatas=[d.metadata or {} for d in docs],
            )
        self._rebuild_bm25()

    def _rebuild_bm25(self) -> None:
        try:
            # BM25Plus (not the classic BM25Okapi) -- Okapi's idf term goes
            # to exactly zero for any word appearing in precisely half of a
            # small corpus, which silently zeroes out real matches on the
            # handful-of-documents corpora this fallback typically serves.
            # Plus's idf floor avoids that degenerate case.
            from rank_bm25 import BM25Plus
        except ImportError:
            self._bm25 = None
            return
        self._bm25_ids = list(self._docs.keys())
        tokenized = [self._docs[cid].text.lower().split() for cid in self._bm25_ids]
        self._bm25 = BM25Plus(tokenized) if tokenized else None

    def query(self, query_text: str, k: int = RAG_RETRIEVE_K) -> list[RetrievedChunk]:
        if not self._docs:
            return []
        if self._collection is not None:
            return self._query_chroma(query_text, k)
        return self._query_bm25(query_text, k)

    def _query_chroma(self, query_text: str, k: int) -> list[RetrievedChunk]:
        result = self._collection.query(query_texts=[query_text], n_results=min(k, len(self._docs)))
        chunks: list[RetrievedChunk] = []
        ids = result.get("ids", [[]])[0]
        for i, chunk_id in enumerate(ids):
            distance = result["distances"][0][i]
            relevance = 1.0 / (1.0 + max(distance, 0.0))
            metadata = result["metadatas"][0][i] or {}
            chunks.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    source=metadata.get("source", chunk_id),
                    text=result["documents"][0][i],
                    relevance_score=round(relevance, 4),
                    metadata=metadata,
                )
            )
        return chunks

    def _query_bm25(self, query_text: str, k: int) -> list[RetrievedChunk]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(query_text.lower().split())
        ranked = sorted(zip(self._bm25_ids, scores), key=lambda pair: -pair[1])[:k]
        max_score = max((s for _, s in ranked), default=0.0) or 1.0
        return [
            RetrievedChunk(
                chunk_id=cid,
                source=self._docs[cid].source,
                text=self._docs[cid].text,
                relevance_score=round(score / max_score, 4),
                metadata=self._docs[cid].metadata,
            )
            for cid, score in ranked
            if score > 0
        ]
