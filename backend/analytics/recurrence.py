from __future__ import annotations

from models.schemas import CanonicalTransaction, Recurrence


def classify_transaction(txn: CanonicalTransaction) -> Recurrence:
    if txn.is_recurring or txn.recurrence_key:
        return Recurrence.RECURRING
    lowered = f"{txn.category} {txn.memo}".lower()
    if any(token in lowered for token in ("one-time", "one time", "legal settlement", "refund")):
        return Recurrence.ONE_TIME
    if any(token in lowered for token in ("seasonal", "renewal", "quarter-end", "quarter end")):
        return Recurrence.SEASONAL
    return Recurrence.UNCLASSIFIED

