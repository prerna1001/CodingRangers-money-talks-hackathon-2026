from __future__ import annotations


def top_share(amounts: list[float], n: int) -> float:
    gross = sum(abs(v) for v in amounts)
    if gross == 0:
        return 0.0
    return round(sum(sorted((abs(v) for v in amounts), reverse=True)[:n]) / gross, 4)


def hhi(amounts: list[float]) -> float:
    gross = sum(abs(v) for v in amounts)
    if gross == 0:
        return 0.0
    return round(sum((abs(v) / gross) ** 2 for v in amounts), 4)

