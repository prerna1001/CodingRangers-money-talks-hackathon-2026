from __future__ import annotations

from collections import defaultdict
from statistics import mean, pstdev

from models.schemas import CanonicalTransaction


def find_duplicate_count(transactions: list[CanonicalTransaction], window_days: int = 2) -> int:
    grouped: dict[tuple[str | None, float], list[CanonicalTransaction]] = defaultdict(list)
    for txn in transactions:
        counterparty = txn.counterparty_id or txn.counterparty_name
        grouped[(counterparty, round(txn.amount, 2))].append(txn)

    duplicates = 0
    for txns in grouped.values():
        if len(txns) < 2:
            continue
        ordered = sorted(txns, key=lambda t: t.posted_date)
        for idx in range(1, len(ordered)):
            delta = (ordered[idx].posted_date - ordered[idx - 1].posted_date).days
            if 0 <= delta <= window_days:
                duplicates += 1
    return duplicates


def outlier_txn_ids(transactions: list[CanonicalTransaction], z_threshold: float = 4.0) -> list[str]:
    if len(transactions) < 3:
        return []
    amounts = [abs(t.amount) for t in transactions]
    mu = mean(amounts)
    sd = pstdev(amounts)
    if sd == 0:
        return []
    return [txn.txn_id for txn in transactions if (abs(txn.amount) - mu) / sd >= z_threshold]

