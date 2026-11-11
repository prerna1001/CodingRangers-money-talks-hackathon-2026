"""Make spoken output say what an abbreviation means.

Two passes, in order:

1. Expand any acronym in the finance glossary (data/acronyms.json, built
   from the team's Financial Services Reporting Acronyms doc), so the
   briefing says "Month over Month" rather than "M O M".
2. Spell out whatever abbreviations are left ("ARR" -> "A R R"), since a
   TTS model otherwise reads short ones as words ("MoM" -> "mom").

Only the audio changes -- the on-screen text keeps the original. This runs
in services/voice_client.py, just before a provider sees the text.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

GLOSSARY_PATH = Path(__file__).resolve().parent.parent / "data" / "acronyms.json"

# Shaped like an abbreviation:
#   - 2-5 capitals, optional plural "s":    MOM, YOY, KPI, ARR, KPIs
#   - capital-lowercase-capital, 3 letters: MoM, YoY, QoQ, WoW
# Longer all-caps words (EBITDA) are left alone -- they're usually said as words.
_ABBR_RE = re.compile(r"\b(?:([A-Z]{2,5})(s?)|([A-Z][a-z][A-Z]))\b")


@lru_cache(maxsize=1)
def glossary() -> dict[str, str]:
    """Acronym -> expansion. Empty if the glossary file is missing, so a
    bad deploy costs us nicer audio, not the voice feature."""
    try:
        return json.loads(GLOSSARY_PATH.read_text())
    except (OSError, ValueError) as exc:  # noqa: BLE001 - degrade quietly
        logger.warning("speech_normalizer: no acronym glossary (%s)", exc)
        return {}


@lru_cache(maxsize=1)
def _glossary_re() -> re.Pattern | None:
    # Keys ending in "." (Adj., Seq.) can't take a trailing \b, and are
    # ambiguous next to sentence punctuation -- leave those spoken as-is.
    keys = [k for k in glossary() if k[-1].isalnum()]
    if not keys:
        return None
    # Longest first so "NII" wins over "NI" at the same position.
    alternation = "|".join(re.escape(k) for k in sorted(keys, key=len, reverse=True))
    # Case-sensitive on purpose: "MoM" is the metric, "mom" is a parent.
    return re.compile(rf"\b({alternation})(s?)\b")


def _expand(match: re.Match) -> str:
    expansion = glossary()[match.group(1)]
    return f"{expansion}s" if match.group(2) else expansion


def _spell(match: re.Match) -> str:
    caps, plural, mixed = match.groups()
    letters = " ".join((caps or mixed).upper())
    return f"{letters}'s" if plural else letters


def normalize(text: str) -> str:
    pattern = _glossary_re()
    if pattern is not None:
        text = pattern.sub(_expand, text)
    return _ABBR_RE.sub(_spell, text)
