"""RunState construction helpers.

The RunState TypedDict itself lives in models/schemas.py (it's part of the
shared contract). This module just holds the factory that creates an empty,
well-typed initial state so every graph run starts from the same shape --
see plan section 7.2.
"""

from __future__ import annotations

import uuid

from models.schemas import (
    AvailableFile,
    CanonicalTransaction,
    CompanyProfileCore,
    PeriodSummary,
    RunState,
)


def new_run_state(
    *,
    company_id: str,
    current_period: str,
    prior_period: str,
    company_profile_core: CompanyProfileCore,
    transactions: list[CanonicalTransaction],
    period_summaries: list[PeriodSummary],
    available_files: list[AvailableFile] | None = None,
    known_aliases: dict[str, list[str]] | None = None,
    run_id: str | None = None,
) -> RunState:
    return RunState(
        run_id=run_id or f"run_{uuid.uuid4().hex[:12]}",
        company_id=company_id,
        current_period=current_period,
        prior_period=prior_period,
        company_profile_core=company_profile_core,
        available_files=available_files or [],
        known_aliases=known_aliases or {},
        transactions=transactions,
        period_summaries=period_summaries,
        facts=[],
        memories=[],
        retrieved=[],
        explanation=None,
        grounding_report=None,
        guardrail_result=None,
        stress_results=[],
        revision_count=0,
        errors=[],
        timeline=[],
        timings={},
        token_usage={},
    )
