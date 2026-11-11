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
    LEGACY_USER_ID,
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
    user_id TEXT NOT NULL,
    company_id TEXT NOT NULL,
    status TEXT NOT NULL,
    data_json TEXT NOT NULL
);
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
            self._migrate_ownership(conn)

    @staticmethod
    def _migrate_ownership(conn: sqlite3.Connection) -> None:
        """Add ``user_id`` to stores created before ownership existed.

        Pre-existing rows are assigned to ``LEGACY_USER_ID`` rather than
        being exposed to whichever account happens to query the database
        next. The column and index are created idempotently so every
        ``MemoryStore()`` call is safe.
        """
        columns = {row[1] for row in conn.execute("PRAGMA table_info(memories)")}
        if "user_id" not in columns:
            legacy = LEGACY_USER_ID.replace("'", "''")
            conn.execute(
                f"ALTER TABLE memories ADD COLUMN user_id TEXT NOT NULL DEFAULT '{legacy}'"
            )
        conn.execute("UPDATE memories SET user_id = ? WHERE user_id IS NULL OR user_id = ''", (LEGACY_USER_ID,))
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_user_company ON memories(user_id, company_id)"
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def create(self, memory: Memory, *, user_id: str) -> Memory:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO memories (memory_id, user_id, company_id, status, data_json) VALUES (?, ?, ?, ?, ?)",
                (
                    memory.memory_id,
                    user_id,
                    memory.company_id,
                    memory.status.value,
                    memory.model_dump_json(),
                ),
            )
        return memory

    def get(self, memory_id: str, *, user_id: str) -> Memory | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data_json FROM memories WHERE memory_id = ? AND user_id = ?",
                (memory_id, user_id),
            ).fetchone()
        return Memory.model_validate_json(row[0]) if row else None

    def list_for_company(
        self, company_id: str, *, user_id: str, statuses: set[MemoryStatus] | None = None
    ) -> list[Memory]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data_json FROM memories WHERE company_id = ? AND user_id = ?",
                (company_id, user_id),
            ).fetchall()
        memories = [Memory.model_validate_json(r[0]) for r in rows]
        if statuses:
            memories = [m for m in memories if m.status in statuses]
        return memories

    def save(self, memory: Memory, *, user_id: str) -> Memory:
        with self._connect() as conn:
            conn.execute(
                "UPDATE memories SET status = ?, data_json = ? WHERE memory_id = ? AND user_id = ?",
                (memory.status.value, memory.model_dump_json(), memory.memory_id, user_id),
            )
        return memory

    def delete(self, memory_id: str, *, user_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM memories WHERE memory_id = ? AND user_id = ?",
                (memory_id, user_id),
            )
            return cursor.rowcount > 0

    # -- lifecycle (plan section 8.3) ------------------------------------

    def corroborate(self, memory_id: str, run_id: str, *, user_id: str) -> Memory:
        memory = self.get(memory_id, user_id=user_id)
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
        return self.save(memory, user_id=user_id)

    def contradict(self, memory_id: str, *, user_id: str) -> Memory:
        """The data always wins for this run's numbers, but the contradiction
        itself degrades the memory -- asymmetrically harder than a
        corroboration helps (plan section 8.3).
        """
        memory = self.get(memory_id, user_id=user_id)
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
        return self.save(memory, user_id=user_id)

    def decay_unobserved(
        self, company_id: str, observed_memory_ids: set[str], *, user_id: str
    ) -> None:
        """Slow multiplicative decay for memories not touched this run.
        User-edited memories are locked from auto-decay (plan section 8.3).
        """
        for memory in self.list_for_company(company_id, user_id=user_id):
            if memory.memory_id in observed_memory_ids or memory.user_edited:
                continue
            memory.confidence = round(memory.confidence * MEMORY_DECAY_PER_UNOBSERVED_PERIOD, 4)
            self.save(memory, user_id=user_id)

    def user_correct(self, memory_id: str, new_content: str, *, user_id: str) -> Memory:
        memory = self.get(memory_id, user_id=user_id)
        if memory is None:
            raise KeyError(memory_id)
        memory.content = new_content
        memory.user_edited = True
        memory.status = MemoryStatus.CONFIRMED
        memory.confidence = MEMORY_CONFIDENCE_CEILING
        return self.save(memory, user_id=user_id)

    def retrievable_for_run(self, company_id: str, *, user_id: str) -> list[Memory]:
        """Memories eligible for the Memory Agent to load -- above the
        retrieval floor, and never retired.
        """
        return [
            m
            for m in self.list_for_company(company_id, user_id=user_id)
            if m.status != MemoryStatus.RETIRED and m.confidence >= MEMORY_RETRIEVAL_FLOOR
        ]
