"""SSE event shapes and the pub/sub bus that feeds the Agent Timeline
(plan section 7.3).

Also provides `agent_step`, a context manager every graph node uses to:
  - append a running -> passed/warning/failed entry to RunState['timeline']
  - record duration into RunState['timings']
  - publish the same transition as an SSE event via EventBus

The frontend must render a plausible timeline even if SSE drops, so this
module doesn't do anything the REST fallback (`GET /api/runs/{run_id}`)
couldn't also reconstruct from RunState alone -- SSE is a convenience
layer over state that already exists.
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from models.schemas import AgentStatus, AgentTimelineEntry


def emit_agent_status(agent: str, status: str, detail: str | None = None) -> dict[str, Any]:
    return {
        "type": "agent_status",
        "agent": agent,
        "status": status,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "detail": detail,
    }


def emit_partial_result(agent: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"type": "partial_result", "agent": agent, "payload": payload}


def emit_run_complete(run_id: str, duration_ms: float) -> dict[str, Any]:
    return {"type": "run_complete", "run_id": run_id, "duration_ms": duration_ms}


class EventBus:
    """Minimal in-process per-run pub/sub, backing the SSE route.

    Not durable and not multi-process -- fine for a hackathon single-worker
    deployment. If that ever changes, this is the one class to swap for a
    Redis pub/sub without touching any agent code.
    """

    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue]] = defaultdict(list)

    def publish(self, run_id: str, event: dict[str, Any]) -> None:
        for queue in self._queues.get(run_id, []):
            queue.put_nowait(event)

    async def subscribe(self, run_id: str) -> Iterator[dict[str, Any]]:
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[run_id].append(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            self._queues[run_id].remove(queue)


EVENT_BUS = EventBus()


class _Step:
    """Handle yielded by `agent_step`. `entry` is populated when the `with`
    block exits (success or failure) -- read it AFTER the block, not inside.
    """

    def __init__(self) -> None:
        self.output_summary: str | None = None
        self.safety_notes: list[str] = []
        self.entry: AgentTimelineEntry | None = None


@contextmanager
def agent_step(run_id: str, agent: str, *, detail: str | None = None) -> Iterator[_Step]:
    """Wrap one graph node's execution for timeline + event tracking.

    Usage:
        with agent_step(state["run_id"], "analyst", detail="Explaining 4 variances") as step:
            ... do work ...
            step.output_summary = "Headline: revenue up 18%"
        return {
            "timeline": [step.entry],
            "timings": {"analyst": step.entry.duration_ms},
            ...
        }

    Deliberately does NOT read or mutate RunState directly -- it only
    returns a single new AgentTimelineEntry, because parallel branches
    (plan section 7.1) each need to contribute their OWN delta to the
    additive `timeline`/`timings` reducers (models/schemas.py), not a
    full copy of a shared list that would collide with the other
    branches' updates.

    On an unhandled exception inside the block, the entry is marked
    FAILED and the exception re-raised -- the caller decides whether to
    convert that into a RunState `errors` entry and continue, or let it
    propagate and fail the run.
    """
    step = _Step()
    started_at = datetime.now(timezone.utc)
    EVENT_BUS.publish(run_id, emit_agent_status(agent, "running", detail))
    start = time.perf_counter()
    try:
        yield step
    except Exception:
        step.entry = AgentTimelineEntry(
            agent=agent,
            status=AgentStatus.FAILED,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            duration_ms=(time.perf_counter() - start) * 1000,
            input_summary=detail,
        )
        EVENT_BUS.publish(run_id, emit_agent_status(agent, "failed", detail))
        raise
    else:
        status = AgentStatus.PASSED if not step.safety_notes else AgentStatus.WARNING
        step.entry = AgentTimelineEntry(
            agent=agent,
            status=status,
            started_at=started_at,
            finished_at=datetime.now(timezone.utc),
            duration_ms=(time.perf_counter() - start) * 1000,
            input_summary=detail,
            output_summary=step.output_summary,
            safety_notes=step.safety_notes,
        )
        EVENT_BUS.publish(run_id, emit_agent_status(agent, status.value, step.output_summary))
