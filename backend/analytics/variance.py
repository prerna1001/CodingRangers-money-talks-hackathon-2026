from __future__ import annotations

from dataclasses import dataclass

from models.schemas import PeriodSummary


@dataclass(frozen=True)
class VarianceRow:
    account_id: str
    account_name: str
    current: float
    prior: float
    change: float
    pct_change: float | None


def period_line_amounts(summary: PeriodSummary) -> dict[str, tuple[str, float]]:
    return {line.account_id: (line.account_name, line.amount) for line in summary.lines}


def account_variances(current: PeriodSummary, prior: PeriodSummary) -> list[VarianceRow]:
    current_lines = period_line_amounts(current)
    prior_lines = period_line_amounts(prior)
    account_ids = sorted(set(current_lines) | set(prior_lines))
    rows: list[VarianceRow] = []
    for account_id in account_ids:
        account_name = current_lines.get(account_id, prior_lines.get(account_id, ("Unknown account", 0.0)))[0]
        current_value = current_lines.get(account_id, (account_name, 0.0))[1]
        prior_value = prior_lines.get(account_id, (account_name, 0.0))[1]
        change = current_value - prior_value
        pct_change = None if prior_value == 0 else change / abs(prior_value)
        rows.append(
            VarianceRow(
                account_id=account_id,
                account_name=account_name,
                current=round(current_value, 2),
                prior=round(prior_value, 2),
                change=round(change, 2),
                pct_change=round(pct_change, 4) if pct_change is not None else None,
            )
        )
    return rows

