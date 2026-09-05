from __future__ import annotations


def component_bridge(prior: float, components: list[tuple[str, float]]) -> dict[str, float]:
    bridge = {"prior": round(prior, 2)}
    for label, value in components:
        bridge[label] = round(value, 2)
    bridge["current"] = round(prior + sum(value for _, value in components), 2)
    return bridge


def identity_delta(components: list[tuple[str, float]]) -> float:
    return round(sum(value for _, value in components), 2)

