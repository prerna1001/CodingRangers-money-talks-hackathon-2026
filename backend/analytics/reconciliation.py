from __future__ import annotations

from collections import defaultdict

from config import RECONCILIATION_BLOCK_THRESHOLD_PCT
from models.schemas import CanonicalTransaction, PeriodSummary, ReconciliationLine, ReconciliationReport


def reconcile(
    transactions: list[CanonicalTransaction],
    period_summaries: list[PeriodSummary],
) -> ReconciliationReport:
    """Reconcile summary lines to transaction totals by period/account.

    Account IDs can repeat across periods, so the internal key includes the
    period. The returned line keeps the public contract's account_id field and
    uses deterministic warn/fail thresholds from config.py.
    """
    txn_sums: dict[tuple[str, str], float] = defaultdict(float)
    for txn in transactions:
        txn_sums[(txn.period_id, txn.account_id)] += txn.amount

    lines: list[ReconciliationLine] = []
    worst = 0.0
    for summary in period_summaries:
        for line in summary.lines:
            summary_val = round(line.amount, 2)
            txn_val = round(txn_sums.get((summary.period_id, line.account_id), 0.0), 2)
            diff = round(summary_val - txn_val, 2)
            diff_pct = abs(diff) / abs(summary_val) if summary_val else (1.0 if txn_val else 0.0)
            status = "pass"
            if diff_pct > RECONCILIATION_BLOCK_THRESHOLD_PCT * 2:
                status = "fail"
            elif diff_pct > RECONCILIATION_BLOCK_THRESHOLD_PCT:
                status = "warn"

            lines.append(
                ReconciliationLine(
                    account_id=line.account_id,
                    summary=summary_val,
                    transactions=txn_val,
                    difference=diff,
                    difference_pct=round(diff_pct, 4),
                    status=status,
                )
            )
            worst = max(worst, diff_pct)

    return ReconciliationReport(by_account=lines, worst_difference_pct=round(worst, 4))

