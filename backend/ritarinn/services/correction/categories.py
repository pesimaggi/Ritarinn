"""Mapping from GreynirCorrect error codes to Ritarinn's issue categories.

GreynirCorrect emits its own code vocabulary (``S004``, ``P_WRONG_CASE_þgf_þf``,
``N002/w`` …). Ritarinn does not invent codes and does not rewrite Greynir's
Icelandic explanations; it only groups codes so the sidebar can be organised and
filtered. The raw code is always passed through to the client untouched.

The grouping below was derived by reading GreynirCorrect 4.1.3's source
(``errtokenizer.py``, ``errfinder.py``, ``pattern.py``, ``settings.py``). It is
an interpretation, not an upstream-published taxonomy — unrecognised prefixes
deliberately fall through to ``unknown`` rather than being guessed at. See
``docs/error-codes.md``.
"""

from __future__ import annotations

from typing import NamedTuple

# Ritarinn's coarse categories, as used by the UI filter chips.
SPELLING = "spelling"
GRAMMAR = "grammar"
PUNCTUATION = "punctuation"
STYLE = "style"
UNKNOWN = "unknown"

CATEGORIES = (SPELLING, GRAMMAR, PUNCTUATION, STYLE, UNKNOWN)


class CodeFamily(NamedTuple):
    """A group of related GreynirCorrect codes."""

    category: str
    #: Icelandic label for the family, shown as the issue's group heading.
    label: str


# Whole-code overrides, checked before prefix rules.
_EXACT: dict[str, CodeFamily] = {
    # Sentence-level observations produced by the parser stage.
    "E001": CodeFamily(UNKNOWN, "Ógreind málsgrein"),
    "E004": CodeFamily(UNKNOWN, "Ekki íslenska"),
    "E005": CodeFamily(STYLE, "Löng málsgrein"),
    "E006": CodeFamily(STYLE, "Skammstafanir"),
    "E007": CodeFamily(STYLE, "Upphrópunarmerki"),
    # Emitted by the grammar stage for numerals written as digits.
    "number4word": CodeFamily(STYLE, "Tölur og bókstafir"),
}

# Prefix rules, longest prefix wins.
_PREFIXES: tuple[tuple[str, CodeFamily], ...] = (
    # Grammar patterns found after parsing: case government, agreement, mood,
    # preposition choice, definiteness.
    ("P_", CodeFamily(GRAMMAR, "Málfræði")),
    # Token-level spelling correction.
    ("S", CodeFamily(SPELLING, "Stafsetning")),
    # Compound-word errors — writing a compound apart, or joining what should
    # stay apart. A distinctively Icelandic error class, worth its own label.
    ("C", CodeFamily(SPELLING, "Samsett orð")),
    # Word not found in BÍN and no confident correction available.
    ("U", CodeFamily(SPELLING, "Óþekkt orð")),
    # Wrong word from the curated WrongWords list.
    ("W", CodeFamily(SPELLING, "Ruglingsleg orð")),
    # Capitalisation.
    ("Z", CodeFamily(SPELLING, "Há- og lágstafir")),
    # Abbreviations corrected against the known-abbreviation table.
    ("A", CodeFamily(SPELLING, "Skammstafanir")),
    # Non-standard written forms graded by BÍN's Ritmyndir data.
    ("R", CodeFamily(SPELLING, "Ritmyndir")),
    # Punctuation: quotation marks, ellipses, repeated periods.
    ("N", CodeFamily(PUNCTUATION, "Greinarmerki")),
    # Taboo / sensitive vocabulary.
    ("T", CodeFamily(STYLE, "Varúðarorð")),
    # Tone-of-voice vocabulary.
    ("V", CodeFamily(STYLE, "Tónn")),
    # Forms flagged in BÍN as belonging to a marked register.
    ("Y", CodeFamily(STYLE, "Málsnið")),
)

_FALLBACK = CodeFamily(UNKNOWN, "Annað")


def strip_warning_suffix(code: str) -> tuple[str, bool]:
    """Split GreynirCorrect's ``/w`` warning marker off a code.

    Returns ``(bare_code, is_warning)``. The marker is upstream's own signal
    that an annotation is advisory rather than an outright error, so Ritarinn
    surfaces it instead of guessing at severity.
    """
    if code.endswith("/w"):
        return code[:-2], True
    return code, False


def classify(code: str) -> CodeFamily:
    """Return the family for a GreynirCorrect error code."""
    bare, _ = strip_warning_suffix(code)
    if bare in _EXACT:
        return _EXACT[bare]
    for prefix, family in _PREFIXES:
        if bare.startswith(prefix):
            return family
    return _FALLBACK
