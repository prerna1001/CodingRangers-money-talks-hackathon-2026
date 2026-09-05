from __future__ import annotations

from dataclasses import dataclass, field

from models.schemas import Fact


@dataclass(frozen=True)
class MetricResult:
    name: str
    score: float
    detail: str


@dataclass(frozen=True)
class EvalResult:
    dataset: str
    metrics: list[MetricResult] = field(default_factory=list)

    @property
    def score(self) -> float:
        if not self.metrics:
            return 0.0
        return round(sum(m.score for m in self.metrics) / len(self.metrics), 4)


def find_variance(facts: list[Fact], account_label: str) -> Fact | None:
    account_label = account_label.casefold()
    return next(
        (fact for fact in facts if fact.kind == "variance" and account_label in fact.label.casefold()),
        None,
    )


def amount_accuracy(actual: float, expected: float, tolerance: float = 1.0) -> float:
    if abs(actual - expected) <= tolerance:
        return 1.0
    denominator = max(abs(expected), 1.0)
    return round(max(0.0, 1.0 - abs(actual - expected) / denominator), 4)


def driver_recall_at_k(facts: list[Fact], expected_names: list[str], k: int = 3) -> float:
    if not expected_names:
        return 1.0
    drivers = [fact.label.casefold() for fact in facts if fact.kind == "driver"][:k]
    hits = sum(1 for name in expected_names if any(name.casefold() in label for label in drivers))
    return round(hits / len(expected_names), 4)

