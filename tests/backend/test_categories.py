"""The GreynirCorrect code → category mapping."""

from __future__ import annotations

import pytest

from ritarinn.services.correction.categories import (
    CATEGORIES,
    SENTENCE_SCOPE,
    SPAN_SCOPE,
    classify,
    strip_warning_suffix,
)


@pytest.mark.parametrize(
    ("code", "category"),
    [
        ("S004", "spelling"),
        ("C002", "spelling"),
        ("U001", "spelling"),
        ("Z002", "spelling"),
        ("N001", "punctuation"),
        ("P_WRONG_CASE_þgf_þf", "grammar"),
        ("P_NT_ÍTölu", "grammar"),
        ("T001/w", "style"),
        ("Y001/w", "style"),
        ("E005", "style"),
        ("E001", "unknown"),
    ],
)
def test_known_codes_are_categorised(code: str, category: str) -> None:
    assert classify(code).category == category


def test_unknown_codes_fall_back_rather_than_guess() -> None:
    """An unrecognised prefix is reported as unknown, not assigned a guess."""
    family = classify("QQ999")
    assert family.category == "unknown"
    assert family.label


def test_every_family_uses_a_declared_category() -> None:
    for code in ["S004", "C002", "N001", "P_X", "T001", "E001", "QQ999"]:
        assert classify(code).category in CATEGORIES


@pytest.mark.parametrize(
    ("code", "expected"),
    [("N002/w", ("N002", True)), ("S004", ("S004", False)), ("T001/w", ("T001", True))],
)
def test_warning_suffix_is_upstreams_own_signal(code: str, expected: tuple[str, bool]) -> None:
    assert strip_warning_suffix(code) == expected


def test_sentence_level_codes_are_marked_as_such() -> None:
    for code in ["E001", "E004", "E005"]:
        assert classify(code).scope == SENTENCE_SCOPE
    for code in ["S004", "N001", "P_WRONG_CASE_þgf_þf"]:
        assert classify(code).scope == SPAN_SCOPE
