"""SQLite-backed memory store implementing the lifecycle in plan section 8.

Deliberately its own tiny store (a single JSON-blob table) rather than
sharing Codex's `models/db.py` (which owns runs/files/audit persistence,
per BACKEND_TASK_SPLIT.md section 2/3) -- memories have their own schema,
their own lifecycle, and are cheap to keep separate and simple.

Full CRUD backs the Memory Panel's edit/delete/correct controls (plan
section 15.2); the confidence/lifecycle update functions back the "runs
that use and update memory" behavior that is the rubric's "iterate and
learn across runs" line (plan section 2).
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from config import (
    MEMORY_CONFIDENCE_CEILING,
    MEMORY_CONFIDENCE_FLOOR,
    MEMORY_CONFIRM_AFTER_CORROBORATIONS,
    MEMORY_CONTRADICTION_PENALTY,
    MEMORY_CORROBORATION_BOOST,
    MEMORY_DECAY_PER_UNOBSERVED_PERIOD,
    MEMORY_DISPUTE_AFTER_CONTRADICTIONS,
    MEMORY_RETIRE_AFTER_CONTRADICTIONS,
    MEMORY_RETRIEVAL_FLOOR,
)
from models.schemas import Memory, MemoryStatus

_DEFAULT_DB_PATH = "./ledgerlight_memory.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    memory_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    status TEXT NOT NULL,
    data_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_company ON memories(company_id);
"""


class MemoryStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        # Resolved at call time (not baked into the signature default) so
        # tests can monkeypatch module-level `_DEFAULT_DB_PATH` and redirect
        # every no-arg `MemoryStore()` call -- including the ones inside
        # graph/workflow.py's node functions -- without passing db_path
        # through the whole call chain.
        self.db_path = str(db_path) if db_path is not None else _DEFAULT_DB_PATH
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def create(self, memory: Memory) -> Memory:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO memories (memory_id, company_id, status, data_json) VALUES (?, ?, ?, ?)",
                (memory.memory_id, memory.company_id, memory.status.value, memory.model_dump_json()),
            )
        return memory

    def get(self, memory_id: str) -> Memory | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data_json FROM memories WHERE memory_id = ?", (memory_id,)
            ).fetchone()
        return Memory.model_validate_json(row[0]) if row else None

    def list_for_company(
        self, company_id: str, statuses: set[MemoryStatus] | None = None
    ) -> list[Memory]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data_json FROM memories WHERE company_id = ?", (company_id,)
            ).fetchall()
        memories = [Memory.model_validate_json(r[0]) for r in rows]
        if statuses:
            memories = [m for m in memories if m.status in statuses]
        return memories

    def save(self, memory: Memory) -> Memory:
        with self._connect() as conn:
            conn.execute(
                "UPDATE memories SET status = ?, data_json = ? WHERE memory_id = ?",
                (memory.status.value, memory.model_dump_json(), memory.memory_id),
            )
        return memory

    def delete(self, memory_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM memories WHERE memory_id = ?", (memory_id,))

    # -- lifecycle (plan section 8.3) ------------------------------------

    def corroborate(self, memory_id: str, run_id: str) -> Memory:
        memory = self.get(memory_id)
        if memory is None:
            raise KeyError(memory_id)
        memory.corroboration_count += 1
        memory.evidence_run_ids.append(run_id)
        memory.confidence = min(
            MEMORY_CONFIDENCE_CEILING, memory.confidence + MEMORY_CORROBORATION_BOOST
        )
        memory.last_reinforced_at = datetime.now(timezone.utc)
        if (
            memory.status == MemoryStatus.CANDIDATE
            and memory.corroboration_count >= MEMORY_CONFIRM_AFTER_CORROBORATIONS
        ):
            memory.status = MemoryStatus.CONFIRMED
        return self.save(memory)

    def contradict(self, memory_id: str) -> Memory:
        """The data always wins for this run's numbers, but the contradiction
        itself degrades the memory -- asymmetrically harder than a
        corroboration helps (plan section 8.3).
        """
        memory = self.get(memory_id)
        if memory is None:
            raise KeyError(memory_id)
        memory.contradiction_count += 1
        memory.confidence = max(
            MEMORY_CONFIDENCE_FLOOR, memory.confidence - MEMORY_CONTRADICTION_PENALTY
        )
        if not memory.user_edited:
            if memory.contradiction_count >= MEMORY_RETIRE_AFTER_CONTRADICTIONS:
                memory.status = MemoryStatus.RETIRED
            elif memory.contradiction_count >= MEMORY_DISPUTE_AFTER_CONTRADICTIONS:
                memory.status = MemoryStatus.DISPUTED
        return self.save(memory)

    def decay_unobserved(self, company_id: str, observed_memory_ids: set[str]) -> None:
        """Slow multiplicative decay for memories not touched this run.
        User-edited memories are locked from auto-decay (plan section 8.3).
        """
        for memory in self.list_for_company(company_id):
            if memory.memory_id in observed_memory_ids or memory.user_edited:
                continue
            memory.confidence = round(memory.confidence * MEMORY_DECAY_PER_UNOBSERVED_PERIOD, 4)
            self.save(memory)

    def user_correct(self, memory_id: str, new_content: str) -> Memory:
        memory = self.get(memory_id)
        if memory is None:
            raise KeyError(memory_id)
        memory.content = new_content
        memory.user_edited = True
        memory.status = MemoryStatus.CONFIRMED
        memory.confidence = MEMORY_CONFIDENCE_CEILING
        return self.save(memory)

    def retrievable_for_run(self, company_id: str) -> list[Memory]:
        """Memories eligible for the Memory Agent to load -- above the
        retrieval floor, and never retired.
        """
        return [
            m
            for m in self.list_for_company(company_id)
            if m.status != MemoryStatus.RETIRED and m.confidence >= MEMORY_RETRIEVAL_FLOOR
        ]
