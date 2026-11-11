"""Hosted models return JSON that is *nearly* right.

Each case here is a shape a real provider actually returned during a demo
run; a whole analysis used to fail on any of them. The schema is still
validated downstream -- these only check that we get far enough to try.
"""

from __future__ import annotations

import pytest

from services import llm


def test_parses_a_plain_object():
    assert llm.extract_json('{"a": 1}', what="T") == {"a": 1}


def test_strips_markdown_fences():
    assert llm.extract_json('```json\n{"a": 1}\n```', what="T") == {"a": 1}


def test_ignores_prose_before_the_object():
    assert llm.extract_json('Here you go:\n{"a": 1}', what="T") == {"a": 1}


def test_ignores_text_after_the_object():
    # Previously fatal: slicing to the last "}" swept the commentary in and
    # json.loads reported "Extra data".
    assert llm.extract_json('{"a": 1}\nThat is my answer.', what="T") == {"a": 1}


def test_repairs_a_trailing_comma():
    assert llm.extract_json('{"a": 1, "b": [1, 2,],}', what="T") == {"a": 1, "b": [1, 2]}


def test_tolerates_raw_newlines_inside_strings():
    assert llm.extract_json('{"a": "line1\nline2"}', what="T") == {"a": "line1\nline2"}


def test_prefers_the_richest_object_when_several_are_returned():
    # Some models restate a worked example before the real answer.
    raw = '{"note": "example"}\n{"headline": "x", "summary": "y", "drivers": []}'
    assert llm.extract_json(raw, what="T")["headline"] == "x"


def test_raises_when_there_is_no_object():
    with pytest.raises(ValueError, match="did not contain a JSON object"):
        llm.extract_json("I could not answer that.", what="Analyst")


def test_raises_when_the_object_is_beyond_repair():
    with pytest.raises(ValueError, match="was not valid JSON"):
        llm.extract_json('{"a": 1 "b" 2}', what="Analyst")


def test_a_nested_object_never_outranks_its_parent():
    # A driver inside the payload can carry more keys than the payload
    # itself; picking it lost the headline and failed schema validation.
    raw = (
        '{"headline": "h", "summary": "s", "confidence": 0.88, '
        '"drivers": [{"driver": "Northwind", "account": "4000", "amount": 1, '
        '"pct": 2, "evidence": [], "confidence": 0.9, "recurrence": "x", "note": "y"}]}'
    )
    assert llm.extract_json(raw, what="Analyst")["headline"] == "h"


def test_null_driver_amount_is_derived_from_evidence_not_invented():
    from agents.analyst import _normalize_explanation_payload

    raw = _normalize_explanation_payload(
        {
            "drivers": [
                {
                    "driver": "Northwind",
                    "amount": None,
                    "evidence": [
                        {"counterparty_name": "a", "amount": 100.0},
                        {"counterparty_name": "b", "amount": 50.0},
                    ],
                }
            ]
        }
    )
    assert raw["drivers"][0]["amount"] == 150.0


def test_null_driver_amount_with_no_evidence_is_dropped_not_zeroed():
    # Defaulting to 0.0 would show a CFO a number the model never produced.
    from agents.analyst import _normalize_explanation_payload

    raw = _normalize_explanation_payload(
        {"drivers": [{"driver": "A", "amount": None, "evidence": []}, {"driver": "B", "amount": 5.0}]}
    )
    assert [d["driver"] for d in raw["drivers"]] == ["B"]
