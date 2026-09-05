"""Prompt-injection defense for free-text cells (plan section 10.3).

Uploaded CSVs are attacker-controlled. Every memo/description field is
treated as hostile before it can reach a prompt. This module implements
layers 1-2 of the plan's defense (detection + neutralization); layer 3
(spotlighting) lives in the prompt templates in agents/analyst.py, and
layer 4 (structural defense -- the Analyst only sees the fact table, never
raw cells) is enforced by the graph wiring itself, not by any one function.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_CELL_LENGTH = 200

# Patterns are intentionally broad -- a false positive here just means a
# memo gets flagged and quarantined for review, which is a much cheaper
# mistake than an injected instruction reaching the model.
_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ignore_instructions", re.compile(r"\bignore\s+(all\s+|the\s+)?(previous|prior|above)\s+instructions?\b", re.I)),
    ("role_marker", re.compile(r"\b(system|assistant|user)\s*:\s", re.I)),
    ("persona_override", re.compile(r"\byou\s+are\s+now\b|\bact\s+as\b|\bpretend\s+(to\s+be|you)\b", re.I)),
    ("fenced_block", re.compile(r"```|<\s*(system|instructions?|prompt)\s*>", re.I)),
    ("directive_verb", re.compile(r"\b(disregard|override|forget)\s+(everything|all|your)\b", re.I)),
    ("say_directive", re.compile(r"\bsay\s+(that\s+)?revenue\s+(doubled|tripled|increased)\b", re.I)),
    ("base64_blob", re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b")),
    ("control_chars", re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")),
]


@dataclass
class InjectionMatch:
    pattern_name: str
    matched_text: str


def detect(text: str) -> list[InjectionMatch]:
    """Return every injection-like pattern found in `text`. Empty if clean."""
    if not text:
        return []
    matches: list[InjectionMatch] = []
    for name, pattern in _INJECTION_PATTERNS:
        m = pattern.search(text)
        if m:
            matches.append(InjectionMatch(pattern_name=name, matched_text=m.group(0)[:80]))
    return matches


def is_suspicious(text: str) -> bool:
    return len(detect(text)) > 0


def sanitize(text: str, max_len: int = MAX_CELL_LENGTH) -> str:
    """Neutralize a free-text cell: strip control chars, cap length, escape
    delimiter-like characters that could break out of a prompt fence.
    """
    if not text:
        return ""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    cleaned = cleaned.replace("```", "'''")
    cleaned = cleaned.strip()
    return cleaned[:max_len]


@dataclass
class QuarantinedCell:
    source_row: int
    field: str
    matches: list[InjectionMatch]
    original_excerpt: str


def scan_transactions(transactions: list) -> list[QuarantinedCell]:
    """Scan every transaction's memo field for injection attempts.

    Used by agents/data_qa.py (to surface warnings) and
    agents/stress_tester.py (to score injection-resistance scenario #1 --
    plan section 12).
    """
    quarantined: list[QuarantinedCell] = []
    for txn in transactions:
        memo = getattr(txn, "memo", "") or ""
        matches = detect(memo)
        if matches:
            quarantined.append(
                QuarantinedCell(
                    source_row=getattr(txn, "source_row", -1),
                    field="memo",
                    matches=matches,
                    original_excerpt=memo[:120],
                )
            )
    return quarantined
