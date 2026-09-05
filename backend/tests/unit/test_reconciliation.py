from __future__ import annotations

from datetime import date

from analytics.reconciliation import reconcile
from models.schemas import AccountType, CanonicalTransaction, PeriodLine, PeriodSummary


def test_reconcile_keys_by_period_and_account() -> None:
    txns = [
        CanonicalTransaction(
            txn_id="t1",
            source_file_id="f",
            source_row=2,
            posted_date=date(2026, 7, 1),
            period_id="2026-07",
            account_id="4000",
            account_name="Revenue",
            account_type=AccountType.REVENUE,
            category="subscription",
            amount=100.0,
        ),
        CanonicalTransaction(
            txn_id="t2",
            source_file_id="f",
            source_row=3,
            posted_date=date(2026, 8, 1),
            period_id="2026-08",
            account_id="4000",
            account_name="Revenue",
            account_type=AccountType.REVENUE,
            category="subscription",
            amount=125.0,
        ),
    ]
    summaries = [
        PeriodSummary(period_id="2026-07", start_date=date(2026, 7, 1), end_date=date(2026, 7, 31), lines=[PeriodLine(account_id="4000", account_name="Revenue", account_type=AccountType.REVENUE, amount=100.0)]),
        PeriodSummary(period_id="2026-08", start_date=date(2026, 8, 1), end_date=date(2026, 8, 31), lines=[PeriodLine(account_id="4000", account_name="Revenue", account_type=AccountType.REVENUE, amount=125.0)]),
    ]

    report = reconcile(txns, summaries)

    assert report.worst_difference_pct == 0.0
    assert [line.transactions for line in report.by_account] == [100.0, 125.0]

