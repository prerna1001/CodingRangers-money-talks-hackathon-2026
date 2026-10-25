"""Unit tests for agents/data_qa.py -- the gate policy is this agent's own
job (plan section 6.2); reconciliation/duplicate math is Codex's, called
through the lazy-import fallback pattern (BACKEND_TASK_SPLIT.md section 5).
These tests exercise the gate policy and warnings regardless of which
implementation (Codex's real module or the local fallback) answers the
reconciliation/duplicate calls.
"""

from __future__ import annotations

from datetime import date

from agents import data_qa
from models.schemas import (
    CanonicalTransaction,
    PeriodLine,
    PeriodSummary,
    RunSafety,
)


def _txn(txn_id, account_id, amount, *, account_type="revenue", counterparty_name="Acme",
         category="enterprise_subscription", period_id="2026-08", posted_date=date(2026, 8, 1)):
    return CanonicalTransaction(
        txn_id=txn_id,
        source_file_id="f1",
        source_row=1,
        posted_date=posted_date,
        period_id=period_id,
        account_id=account_id,
        account_name="Account",
        account_type=account_type,
        category=category,
        counterparty_name=counterparty_name,
        amount=amount,
    )


def _summary(period_id, account_id, amount, account_type="revenue"):
    return PeriodSummary(
        period_id=period_id,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
        lines=[PeriodLine(account_id=account_id, account_name="Account", account_type=account_type, amount=amount)],
    )


def test_clean_reconciliation_passes_with_no_warnings():
    transactions = [_txn("t1", "4000", 100000.0)]
    summaries = [_summary("2026-08", "4000", 100000.0)]
    report = data_qa.run_data_qa(transactions=transactions, period_summaries=summaries)
    assert report.status == RunSafety.PASS
    assert report.safe_to_analyze is True
    assert report.reconciliation.worst_difference_pct == 0.0


def test_large_reconciliation_gap_blocks_the_run():
    transactions = [_txn("t1", "4000", 50000.0)]
    summaries = [_summary("2026-08", "4000", 100000.0)]  # 50% gap
    report = data_qa.run_data_qa(transactions=transactions, period_summaries=summaries)
    assert report.status == RunSafety.BLOCKED
    assert report.safe_to_analyze is False
    assert report.blocking_issues


def test_missing_counterparty_produces_warning_not_a_block():
    transactions = [
        _txn("t1", "4000", 50000.0, counterparty_name="Acme"),
        _txn("t2", "4000", 50000.0, counterparty_name=None),
    ]
    summaries = [_summary("2026-08", "4000", 100000.0)]
    report = data_qa.run_data_qa(transactions=transactions, period_summaries=summaries)
    assert report.safe_to_analyze is True
    assert any(w.code == "missing_counterparty" for w in report.warnings)
    assert report.status == RunSafety.PASS_WITH_WARNINGS


def test_data_quality_score_decreases_with_warnings():
    clean_transactions = [_txn("t1", "4000", 100000.0)]
    summaries = [_summary("2026-08", "4000", 100000.0)]
    clean_report = data_qa.run_data_qa(transactions=clean_transactions, period_summaries=summaries)

    dirty_transactions = [
        _txn("t1", "4000", 50000.0, counterparty_name=None),
        _txn("t2", "4000", 50000.0, category=""),
    ]
    dirty_report = data_qa.run_data_qa(transactions=dirty_transactions, period_summaries=summaries)

    assert dirty_report.data_quality_score < clean_report.data_quality_score
