"""Turning a rewritten sentence back into reviewable edits.

This is the piece that decides whether a neural corrector can be offered at all.
Get it wrong and accepting a suggestion corrupts the document — silently, in a
way the user only notices later. So the central assertion here is not that the
edits look sensible, but that *applying them reproduces the corrected text
exactly*, for every pair the tests try.

Nothing in this module needs a model, and nothing in it needs PyTorch.
"""

from __future__ import annotations

import pytest

from ritarinn.services.correction.diffing import (
    anchor_insertions,
    diff_words,
    similarity,
    tokenize,
)


def apply_edits(original: str, edits) -> str:
    """Apply *edits* to *original* in order, the way the editor would."""
    out: list[str] = []
    cursor = 0
    for edit in edits:
        assert edit.start >= cursor, "edits must be ordered and non-overlapping"
        out.append(original[cursor : edit.start])
        out.append(edit.replacement)
        cursor = edit.end
    out.append(original[cursor:])
    return "".join(out)


# -- the invariant everything else rests on -----------------------------------

PAIRS = [
    # Spelling, the ordinary case.
    ("Þinngið samþikkti tilöguna.", "Þingið samþykkti tillöguna."),
    # Nothing wrong: a corrector agreeing with the user must produce no edits.
    ("Þingið samþykkti tillöguna.", "Þingið samþykkti tillöguna."),
    # A word added.
    ("Hann kom heim.", "Hann kom ekki heim."),
    # A word removed.
    ("Hann kom ekki heim.", "Hann kom heim."),
    # Punctuation only.
    ("Hann kom heim", "Hann kom heim."),
    # Capitalisation of the first word.
    ("mig langar að fara", "Mig langar að fara"),
    # An insertion at the very beginning.
    ("Fyrsta orðið vantar.", "Alveg fyrsta orðið vantar."),
    # An insertion at the very end.
    ("Þetta er", "Þetta er rétt"),
    # Case government, the multi-word grammatical case.
    ("Páli, vini mínum, langaði að fara.", "Pál, vin minn, langaði að fara."),
    # A compound written apart, which is a distinctively Icelandic error.
    ("Hann er lang bestur.", "Hann er langbestur."),
    # Several changes in one sentence.
    ("ég fór í búðina og keipti mjólk", "Ég fór í búðina og keypti mjólk."),
    # Astral-plane characters must not shift anything.
    ("Halló 🎉 heimur", "Halló 🎉 heimur!"),
    # Whitespace-only correction: a missing space between two words.
    ("Hannkom heim.", "Hann kom heim."),
]


@pytest.mark.parametrize(("original", "corrected"), PAIRS)
def test_applying_the_edits_reproduces_the_corrected_text(original: str, corrected: str) -> None:
    """The property that makes accepting a suggestion safe."""
    edits = anchor_insertions(original, diff_words(original, corrected))
    assert apply_edits(original, edits) == corrected


@pytest.mark.parametrize(("original", "corrected"), PAIRS)
def test_every_span_selects_exactly_what_it_claims_to(original: str, corrected: str) -> None:
    for edit in anchor_insertions(original, diff_words(original, corrected)):
        assert original[edit.start : edit.end] == edit.original


@pytest.mark.parametrize(("original", "corrected"), PAIRS)
def test_no_span_is_empty(original: str, corrected: str) -> None:
    """The editor discards zero-width ranges, so an empty span is an invisible edit."""
    for edit in anchor_insertions(original, diff_words(original, corrected)):
        assert edit.end > edit.start, f"empty span for {edit.replacement!r}"


# -- determinism --------------------------------------------------------------


def test_the_same_pair_always_produces_the_same_edits() -> None:
    """Proofreading twice must not offer different suggestions the second time."""
    original = "ég fór í búðina og keipti mjólk"
    corrected = "Ég fór í búðina og keypti mjólk."
    first = anchor_insertions(original, diff_words(original, corrected))
    for _ in range(5):
        assert anchor_insertions(original, diff_words(original, corrected)) == first


# -- shape of the edits -------------------------------------------------------


def test_identical_text_produces_no_edits() -> None:
    assert diff_words("Sami texti.", "Sami texti.") == []


def test_edits_are_word_aligned_not_character_aligned() -> None:
    """One changed letter is reported as the whole word, which a person can judge."""
    edits = diff_words("tilöguna", "tillöguna")
    assert len(edits) == 1
    assert (edits[0].original, edits[0].replacement) == ("tilöguna", "tillöguna")


def test_an_insertion_is_anchored_to_a_neighbouring_word() -> None:
    original = "Hann kom heim."
    edits = anchor_insertions(original, diff_words(original, "Hann kom ekki heim."))
    assert len(edits) == 1
    assert edits[0].original == "heim."
    assert edits[0].replacement == "ekki heim."


def test_a_deletion_keeps_an_empty_replacement() -> None:
    """An empty string means "remove this"; None would mean "no suggestion"."""
    edits = diff_words("Hann kom ekki heim.", "Hann kom heim.")
    assert len(edits) == 1
    assert edits[0].replacement == ""
    assert edits[0].is_deletion


def test_spans_do_not_start_or_end_on_a_paragraph_break() -> None:
    """A correction must not swallow the blank line before the word it fixes."""
    original = "Fyrsta málsgrein.\n\ntilöguna"
    corrected = "Fyrsta málsgrein.\n\ntillöguna"
    for edit in anchor_insertions(original, diff_words(original, corrected)):
        assert not original[edit.start].isspace()
        assert not original[edit.end - 1].isspace()


def test_tokenize_loses_nothing() -> None:
    text = "Halló  heimur.\n\nNý málsgrein!  "
    assert "".join(token for _, token in tokenize(text)) == text


# -- the similarity floor -----------------------------------------------------


def test_identical_text_is_fully_similar() -> None:
    assert similarity("Þingið samþykkti.", "Þingið samþykkti.") == 1.0


def test_an_empty_answer_is_not_similar() -> None:
    """A model that returns nothing has not corrected the sentence."""
    assert similarity("Þingið samþykkti tillöguna.", "") == 0.0


def test_an_unrelated_answer_is_not_similar() -> None:
    original = "Þingið samþykkti tillöguna á fundi sínum í gær."
    assert similarity(original, "Ég veit ekki hvað þú átt við.") < 0.5


def test_a_corrected_sentence_stays_similar() -> None:
    assert similarity("Þinngið samþikkti tilöguna.", "Þingið samþykkti tillöguna.") >= 0.5
