"""Data QA Agent (plan section 6.2). Pure code, no LLM.

Decides whether a run is even allowed to proceed. This module is an
ORCHESTRATOR: the actual reconciliation and anomaly math belongs to
Codex's `analytics/reconciliation.py` and `analytics/anomalies.py` (see
BACKEND_TASK_SPLIT.md section 2/3). It's imported lazily with a local
fallback so this agent -- and the graph it sits in -- runs standalone
before those modules exist, and picks up the real implementations
automatically once Codex lands them (same file path, same function
names, no code change required here).

What IS this agent's own job, not a hand-off: the gate policy (block vs.
warn threshold), missing-counterparty/category warnings, and assembling
the QAReport shape the rest of the pipeline depends on.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from config import RECONCILIATION_BLOCK_THRESHOLD_PCT
from models.schemas import (
    AccountType,
    CanonicalTransaction,
    PeriodSummary,
    QAReport,
    QAWarning,
    ReconciliationLine,
    ReconciliationReport,
    RunSafety,
    WarningSeverity,
)


# --------------------------------------------------------------------------
# Reconciliation -- prefers Codex's analytics.reconciliation, else fallback
# --------------------------------------------------------------------------


def _reconcile_fallback(
    transactions: list[CanonicalTransaction], period_summaries: list[PeriodSummary]
) -> ReconciliationReport:
    txn_sums: dict[str, float] = defaultdict(float)
    for txn in transactions:
        txn_sums[txn.account_id] += txn.amount

    lines: list[ReconciliationLine] = []
    worst = 0.0
    for summary in period_summaries:
        for line in summary.lines:
            summary_val = line.amount
            txn_val = txn_sums.get(line.account_id, 0.0)
            diff = summary_val - txn_val
            diff_pct = abs(diff) / abs(summary_val) if summary_val else (1.0 if txn_val else 0.0)
            if diff_pct <= RECONCILIATION_BLOCK_THRESHOLD_PCT:
                status = "pass"
            elif diff_pct <= RECONCILIATION_BLOCK_THRESHOLD_PCT * 2:
                status = "warn"
            else:
                status = "fail"
            lines.append(
                ReconciliationLine(
                    account_id=line.account_id,
                    summary=summary_val,
                    transactions=round(txn_val, 2),
                    difference=round(diff, 2),
                    difference_pct=round(diff_pct, 4),
                    status=status,
                )
            )
            worst = max(worst, diff_pct)
    return ReconciliationReport(by_account=lines, worst_difference_pct=round(worst, 4))


def reconcile(
    transactions: list[CanonicalTransaction], period_summaries: list[PeriodSummary]
) -> ReconciliationReport:
    try:
        from analytics import reconciliation  # Codex's module -- may not exist yet
    except ImportError:
        return _reconcile_fallback(transactions, period_summaries)
    return reconciliation.reconcile(transactions, period_summaries)


# --------------------------------------------------------------------------
# Duplicate / outlier detection -- prefers Codex's analytics.anomalies
# --------------------------------------------------------------------------


def _find_duplicates_fallback(transactions: list[CanonicalTransaction]) -> int:
    """Exact + near-duplicate (same counterparty/amount within 2 days)."""
    by_key: dict[tuple, list[CanonicalTransaction]] = defaultdict(list)
    for txn in transactions:
        by_key[(txn.counterparty_id or txn.counterparty_name, round(txn.amount, 2))].append(txn)

    duplicate_count = 0
    for group in by_key.values():
        if len(group) < 2:
            continue
        group_sorted = sorted(group, key=lambda t: t.posted_date)
        for i in range(1, len(group_sorted)):
            if group_sorted[i].posted_date - group_sorted[i - 1].posted_date <= timedelta(days=2):
                duplicate_count += 1
    return duplicate_count


def find_duplicate_count(transactions: list[CanonicalTransaction]) -> int:
    try:
        from analytics import anomalies  # Codex's module -- may not exist yet
    except ImportError:
        return _find_duplicates_fallback(transactions)
    return anomalies.find_duplicate_count(transactions)


# --------------------------------------------------------------------------
# QA agent's own job: warnings + gate policy
# --------------------------------------------------------------------------


def _missing_counterparty_warning(transactions: list[CanonicalTransaction]) -> QAWarning | None:
    revenue_txns = [t for t in transactions if t.account_type == AccountType.REVENUE]
    if not revenue_txns:
        return None
    missing = [t for t in revenue_txns if not t.counterparty_name]
    if not missing:
        return None
    total_dollars = sum(abs(t.amount) for t in revenue_txns) or 1.0
    missing_dollars = sum(abs(t.amount) for t in missing)
    share = missing_dollars / total_dollars
    severity = WarningSeverity.HIGH if share > 0.2 else WarningSeverity.MEDIUM if share > 0.05 else WarningSeverity.LOW
    return QAWarning(
        code="missing_counterparty",
        message=f"{len(missing)} transactions ({share:.1%} of revenue dollars) missing customer_name",
        severity=severity,
    )


def _uncategorized_warning(transactions: list[CanonicalTransaction]) -> QAWarning | None:
    uncategorized = [t for t in transactions if not t.category or t.category.lower() in {"uncategorized", "unknown", ""}]
    if not uncategorized:
        return None
    return QAWarning(
        code="uncategorized_category",
        message=f"{len(uncategorized)} transactions have no category assigned",
        severity=WarningSeverity.MEDIUM,
    )


def _duplicate_warning(transactions: list[CanonicalTransaction]) -> QAWarning | None:
    count = find_duplicate_count(transactions)
    if not count:
        return None
    return QAWarning(
        code="duplicate_transactions",
        message=f"{count} likely duplicate transaction(s) detected (same counterparty/amount within 2 days)",
        severity=WarningSeverity.MEDIUM,
    )


def _data_quality_score(reconciliation: ReconciliationReport, warnings: list[QAWarning]) -> float:
    score = 1.0 - min(reconciliation.worst_difference_pct * 5, 0.5)
    penalty_by_severity = {WarningSeverity.LOW: 0.02, WarningSeverity.MEDIUM: 0.06, WarningSeverity.HIGH: 0.15}
    for w in warnings:
        score -= penalty_by_severity[w.severity]
    return round(max(0.0, min(1.0, score)), 3)


def run_data_qa(
    *,
    transactions: list[CanonicalTransaction],
    period_summaries: list[PeriodSummary],
) -> QAReport:
    """Gate policy (plan section 6.2): worst_difference_pct beyond threshold
    on any material account blocks the run outright rather than narrating
    bad data.
    """
    reconciliation = reconcile(transactions, period_summaries)

    warnings = [
        w
        for w in (
            _missing_counterparty_warning(transactions),
            _uncategorized_warning(transactions),
            _duplicate_warning(transactions),
        )
        if w is not None
    ]

    blocking_issues: list[str] = []
    if reconciliation.worst_difference_pct > RECONCILIATION_BLOCK_THRESHOLD_PCT:
        blocking_issues.append(
            f"Reconciliation difference of {reconciliation.worst_difference_pct:.2%} "
            f"exceeds the {RECONCILIATION_BLOCK_THRESHOLD_PCT:.0%} threshold"
        )

    if blocking_issues:
        status = RunSafety.BLOCKED
    elif warnings:
        status = RunSafety.PASS_WITH_WARNINGS
    else:
        status = RunSafety.PASS

    return QAReport(
        status=status,
        data_quality_score=_data_quality_score(reconciliation, warnings),
        reconciliation=reconciliation,
        warnings=warnings,
        blocking_issues=blocking_issues,
        safe_to_analyze=not blocking_issues,
    )
