from __future__ import annotations

from collections import defaultdict

from analytics.attribution import top_drivers
from analytics.concentration import top_share
from analytics.formatting import money
from analytics.variance import account_variances
from models.schemas import Basis, BasisPoint, Fact, PeriodSummary, Significance, CanonicalTransaction


def _summary_by_period(period_summaries: list[PeriodSummary], period_id: str) -> PeriodSummary:
    for summary in period_summaries:
        if summary.period_id == period_id:
            return summary
    raise ValueError(f"Missing period summary for {period_id!r}")


def build_facts(
    *,
    transactions: list[CanonicalTransaction],
    period_summaries: list[PeriodSummary],
    current_period: str,
    prior_period: str,
    min_abs_change: float = 1.0,
) -> list[Fact]:
    current_summary = _summary_by_period(period_summaries, current_period)
    prior_summary = _summary_by_period(period_summaries, prior_period)

    facts: list[Fact] = []
    for row in account_variances(current_summary, prior_summary):
        if abs(row.change) < min_abs_change:
            continue
        fact_id = f"variance_{row.account_id}_{prior_period}_to_{current_period}".replace("-", "_")
        facts.append(
            Fact(
                fact_id=fact_id,
                kind="variance",
                label=f"{row.account_name}, period over period",
                value=row.change,
                formatted=money(row.change),
                pct=row.pct_change,
                basis=Basis(
                    current=BasisPoint(period=current_period, value=row.current),
                    prior=BasisPoint(period=prior_period, value=row.prior),
                ),
                significance=Significance(insufficient_history=True),
                evidence_txn_ids=[
                    txn.txn_id
                    for txn in transactions
                    if txn.period_id == current_period and txn.account_id == row.account_id
                ][:25],
                evidence_count=sum(
                    1
                    for txn in transactions
                    if txn.period_id in {current_period, prior_period} and txn.account_id == row.account_id
                ),
                confidence=0.9,
            )
        )

        drivers = top_drivers(
            transactions,
            current_period=current_period,
            prior_period=prior_period,
            account_id=row.account_id,
            n=10,
        )
        drivers = sorted(
            drivers,
            key=lambda item: (item[1] * row.change > 0, abs(item[1])),
            reverse=True,
        )[:5]
        for name, amount, txn_ids in drivers:
            if abs(amount) < min_abs_change:
                continue
            driver_id = f"driver_{row.account_id}_{name}_{current_period}".lower()
            driver_id = "".join(ch if ch.isalnum() else "_" for ch in driver_id).strip("_")
            facts.append(
                Fact(
                    fact_id=driver_id,
                    kind="driver",
                    label=f"{name} contribution to {row.account_name}",
                    value=amount,
                    formatted=money(amount),
                    evidence_txn_ids=txn_ids[:25],
                    evidence_count=len(txn_ids),
                    confidence=0.88 if txn_ids else 0.72,
                )
            )

    driver_amounts_by_account: dict[str, list[float]] = defaultdict(list)
    for fact in facts:
        if fact.kind == "driver":
            parts = fact.fact_id.split("_")
            if len(parts) >= 2:
                driver_amounts_by_account[parts[1]].append(fact.value)

    for account_id, amounts in driver_amounts_by_account.items():
        share = top_share(amounts, 3)
        if share:
            facts.append(
                Fact(
                    fact_id=f"concentration_{account_id}_top3_{current_period}".replace("-", "_"),
                    kind="concentration",
                    label=f"Top 3 drivers share for account {account_id}",
                    value=round(share * 100, 1),
                    unit="pct",
                    formatted=f"{share * 100:.1f}%",
                    pct=share,
                    evidence_count=min(3, len(amounts)),
                    confidence=0.86,
                )
            )

    return facts
