from __future__ import annotations

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover - fallback for minimal environments
    fuzz = None


def _normalize(value: str) -> str:
    return " ".join(value.casefold().replace(".", "").replace(",", "").split())


def resolve(name: str, known_aliases: dict[str, list[str]], threshold: float = 88.0) -> str | None:
    target = _normalize(name)
    best_id: str | None = None
    best_score = 0.0
    for canonical_id, aliases in known_aliases.items():
        for alias in aliases:
            candidate = _normalize(alias)
            if candidate == target:
                return canonical_id
            score = fuzz.token_sort_ratio(target, candidate) if fuzz else (100.0 if target == candidate else 0.0)
            if score > best_score:
                best_score = float(score)
                best_id = canonical_id
    return best_id if best_score >= threshold else None

