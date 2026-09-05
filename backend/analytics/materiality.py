from __future__ import annotations

from config import PRIORITY_SCORE_WEIGHTS


def priority_score(
    *,
    absolute_change: float,
    pct_change: float | None,
    materiality_threshold_usd: float,
    outside_control_limits: bool = False,
    novelty_score: float = 0.0,
) -> float:
    abs_component = min(abs(absolute_change) / max(materiality_threshold_usd, 1.0), 1.0)
    pct_component = min(abs(pct_change or 0.0), 1.0)
    materiality_component = 1.0 if abs(absolute_change) >= materiality_threshold_usd else abs_component
    surprise_component = 1.0 if outside_control_limits else 0.0
    weights = PRIORITY_SCORE_WEIGHTS
    return round(
        abs_component * weights["normalized_absolute_change"]
        + pct_component * weights["normalized_percentage_change"]
        + materiality_component * weights["business_materiality"]
        + surprise_component * weights["statistical_surprise"]
        + max(0.0, min(1.0, novelty_score)) * weights["novelty_score"],
        4,
    )

