from __future__ import annotations

import csv
import hashlib
from datetime import date, datetime
from io import StringIO
from typing import Iterable

from models.schemas import AccountType, CanonicalTransaction, CounterpartyType, PeriodLine, PeriodSummary


_COLUMN_ALIASES = {
    "txn_id": ("txn_id", "transaction_id", "id"),
    "posted_date": ("posted_date", "date", "transaction_date"),
    "period_id": ("period_id", "period", "month"),
    "account_id": ("account_id", "account_code"),
    "account_name": ("account_name", "account"),
    "account_type": ("account_type", "type"),
    "category": ("category", "class"),
    "counterparty_name": ("counterparty_name", "customer", "vendor", "name"),
    "counterparty_type": ("counterparty_type", "counterparty_kind"),
    "amount": ("amount", "value"),
    "currency": ("currency",),
    "memo": ("memo", "description", "notes"),
}


def _pick(row: dict[str, str], field: str, default: str = "") -> str:
    lowered = {key.strip().lower(): value for key, value in row.items()}
    for alias in _COLUMN_ALIASES[field]:
        if alias in lowered:
            return str(lowered[alias]).strip()
    return default


# Real exports (Excel, QuickBooks, bank portals) rarely hand you ISO dates.
# ISO is still tried first so nothing about the existing behavior changes;
# these are only consulted when it fails.
_FALLBACK_DATE_FORMATS = (
    "%m/%d/%Y",  # US
    "%d/%m/%Y",  # UK/EU
    "%m-%d-%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%d %b %Y",  # 05 Aug 2026
    "%d %B %Y",  # 05 August 2026
    "%b %d, %Y",  # Aug 5, 2026
    "%B %d, %Y",
    "%m/%d/%y",
    "%d/%m/%y",
)


def _parse_date(value: str) -> date:
    value = (value or "").strip()
    if not value:
        raise ValueError(
            "row is missing a date -- expected a column named one of: "
            f"{', '.join(_COLUMN_ALIASES['posted_date'])}"
        )
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        pass
    for fmt in _FALLBACK_DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(
        f"could not parse date {value!r}. Use ISO format (YYYY-MM-DD), or one of: "
        "MM/DD/YYYY, DD/MM/YYYY, 'Aug 5, 2026'"
    )


def _parse_amount(value: str) -> float:
    cleaned = value.replace("$", "").replace(",", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    return round(float(cleaned), 2)


def read_csv_text(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(text)))


def parse_transactions(rows: Iterable[dict[str, str]], *, source_file_id: str) -> list[CanonicalTransaction]:
    transactions: list[CanonicalTransaction] = []
    for idx, row in enumerate(rows, start=2):
        posted_date = _parse_date(_pick(row, "posted_date"))
        period_id = _pick(row, "period_id") or posted_date.strftime("%Y-%m")
        account_type = AccountType(_pick(row, "account_type", "opex").lower())
        counterparty_type_raw = _pick(row, "counterparty_type")
        counterparty_type = CounterpartyType(counterparty_type_raw.lower()) if counterparty_type_raw else None
        amount = _parse_amount(_pick(row, "amount", "0"))
        txn_id = _pick(row, "txn_id") or hashlib.sha256(f"{source_file_id}:{idx}:{row}".encode()).hexdigest()[:16]
        transactions.append(
            CanonicalTransaction(
                txn_id=txn_id,
                source_file_id=source_file_id,
                source_row=idx,
                posted_date=posted_date,
                period_id=period_id,
                account_id=_pick(row, "account_id"),
                account_name=_pick(row, "account_name"),
                account_type=account_type,
                category=_pick(row, "category", "uncategorized"),
                counterparty_name=_pick(row, "counterparty_name") or None,
                counterparty_type=counterparty_type,
                amount=amount,
                currency=_pick(row, "currency", "USD") or "USD",
                memo=_pick(row, "memo"),
                raw=dict(row),
            )
        )
    return transactions


def parse_period_summaries(rows: Iterable[dict[str, str]]) -> list[PeriodSummary]:
    grouped: dict[str, list[PeriodLine]] = {}
    bounds: dict[str, tuple[date, date]] = {}
    for row in rows:
        period_id = _pick(row, "period_id")
        start = _parse_date(row.get("start_date", f"{period_id}-01"))
        end = _parse_date(row.get("end_date", f"{period_id}-28"))
        grouped.setdefault(period_id, []).append(
            PeriodLine(
                account_id=_pick(row, "account_id"),
                account_name=_pick(row, "account_name"),
                account_type=AccountType(_pick(row, "account_type", "opex").lower()),
                amount=_parse_amount(_pick(row, "amount", "0")),
            )
        )
        bounds[period_id] = (start, end)
    return [
        PeriodSummary(period_id=period_id, start_date=bounds[period_id][0], end_date=bounds[period_id][1], lines=lines)
        for period_id, lines in sorted(grouped.items())
    ]
