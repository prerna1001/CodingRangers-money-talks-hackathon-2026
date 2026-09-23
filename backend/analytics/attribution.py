from __future__ import annotations

from collections import defaultdict

from models.schemas import AccountType, CanonicalTransaction


def counterparty_deltas(
    transactions: list[CanonicalTransaction],
    *,
    account_id: str | None,
    current_period: str,
    prior_period: str,
) -> dict[str, float]:
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for txn in transactions:
        if account_id is not None and txn.account_id != account_id:
            continue
        if txn.period_id not in {current_period, prior_period}:
            continue
        name = txn.counterparty_name or txn.counterparty_id or "Unknown counterparty"
        totals[(txn.period_id, name)] += txn.amount

    names = {name for _, name in totals}
    return {
        name: round(totals.get((current_period, name), 0.0) - totals.get((prior_period, name), 0.0), 2)
        for name in names
    }


def top_drivers(
    transactions: list[CanonicalTransaction],
    *,
    current_period: str,
    prior_period: str,
    account_id: str | None = None,
    n: int = 5,
) -> list[tuple[str, float, list[str]]]:
    deltas = counterparty_deltas(
        transactions,
        account_id=account_id,
        current_period=current_period,
        prior_period=prior_period,
    )
    txn_ids_by_name: dict[str, list[str]] = defaultdict(list)
    for txn in transactions:
        if txn.period_id != current_period:
            continue
        if account_id is not None and txn.account_id != account_id:
            continue
        name = txn.counterparty_name or txn.counterparty_id or "Unknown counterparty"
        txn_ids_by_name[name].append(txn.txn_id)

    ranked = sorted(deltas.items(), key=lambda item: abs(item[1]), reverse=True)
    return [(name, amount, txn_ids_by_name.get(name, [])) for name, amount in ranked[:n] if amount != 0]


def revenue_account_ids(transactions: list[CanonicalTransaction]) -> set[str]:
    return {txn.account_id for txn in transactions if txn.account_type == AccountType.REVENUE}

