"""Spoken output should say what an abbreviation means.

The glossary comes from the team's Financial Services Reporting Acronyms
doc (data/acronyms.json). Anything it doesn't cover still gets spelled out
letter by letter, because a TTS model reads "MoM" as "mom" otherwise.
"""

from __future__ import annotations

from services.speech_normalizer import glossary, normalize


def test_glossary_loaded():
    assert len(glossary()) > 100
    assert glossary()["MoM"] == "Month over Month"


def test_expands_period_comparisons():
    assert normalize("Revenue grew 9% MoM") == "Revenue grew 9% Month over Month"
    assert normalize("up 22% YoY") == "up 22% Year over Year"


def test_expands_banking_metrics():
    assert normalize("NII rose") == "Net Interest Income rose"
    assert normalize("ROTCE held") == "Return on Tangible Common Equity held"


def test_pluralises_an_expansion():
    assert normalize("the KPIs") == "the Key Performance Indicators"


def test_is_case_sensitive():
    # "MoM" is the metric; "mom" is a parent. Only one should be expanded.
    assert normalize("My mom called") == "My mom called"


def test_unknown_abbreviations_are_still_spelled_out():
    # ARR is not in the glossary, so it falls back to letter-by-letter.
    assert normalize("the ARR bridge") == "the A R R bridge"


def test_long_all_caps_words_are_left_alone():
    # EBITDA is said as a word, not spelled, and has no glossary entry.
    assert normalize("EBITDA was flat") == "EBITDA was flat"


def test_leaves_ordinary_prose_untouched():
    assert normalize("Revenue increased this month.") == "Revenue increased this month."
