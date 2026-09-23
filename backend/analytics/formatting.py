from __future__ import annotations


def money(value: float) -> str:
    sign = "+" if value > 0 else "-" if value < 0 else ""
    absolute = abs(value)
    if absolute >= 1_000_000:
        return f"{sign}${absolute / 1_000_000:.1f}M"
    if absolute >= 1_000:
        return f"{sign}${absolute / 1_000:.1f}K"
    return f"{sign}${absolute:,.0f}"


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"

