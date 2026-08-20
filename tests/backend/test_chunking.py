"""Document chunking for local models.

The property that matters most is that chunking loses nothing: every character
of the source has to end up in exactly one chunk. A chunker that silently drops
a paragraph produces a summary that is confidently missing a fact, which is
worse than an error.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from ritarinn.text.chunking import (
    chunk_document,
    reassemble,
    split_paragraphs,
    split_sentences,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def long_icelandic_text() -> str:
    cases = json.loads((REPO_ROOT / "corpus" / "cases.json").read_text(encoding="utf-8"))
    return "\n\n".join(case["text"] for case in cases["cases"] if case["text"].strip())


# -- sentence splitting -------------------------------------------------------


def test_icelandic_abbreviations_do_not_split_sentences() -> None:
    """The reason a regex is not used.

    Icelandic legal citations are dense with full stops. Splitting on "." would
    turn one sentence into six fragments, and each fragment handed to a model
    separately would lose its subject.
    """
    text = "Sbr. 3. mgr. 12. gr. laga nr. 7/1998. Þetta er önnur setning."
    sentences = split_sentences(text)
    assert len(sentences) == 2
    assert sentences[0].strip().startswith("Sbr.")
    assert sentences[1].strip() == "Þetta er önnur setning."


def test_sentence_split_preserves_every_character() -> None:
    text = "Fyrsta setning. Önnur setning! Þriðja setning? Fjórða."
    assert "".join(split_sentences(text)) == text


def test_sentence_split_handles_empty_text() -> None:
    assert split_sentences("") == []


# -- paragraph splitting ------------------------------------------------------


def test_paragraph_split_preserves_every_character() -> None:
    text = "Fyrsta.\n\nÖnnur málsgrein.\n\n\nÞriðja."
    assert "".join(split_paragraphs(text)) == text


def test_paragraph_split_finds_paragraphs() -> None:
    assert len(split_paragraphs("Ein.\n\nTvö.\n\nÞrjú.")) == 3


# -- chunking -----------------------------------------------------------------


@pytest.mark.parametrize("budget", [120, 300, 700, 2000, 100_000])
def test_chunking_loses_nothing(long_icelandic_text: str, budget: int) -> None:
    chunks = chunk_document(long_icelandic_text, budget)
    assert reassemble(chunks) == long_icelandic_text


@pytest.mark.parametrize("budget", [300, 700, 2000])
def test_chunks_respect_the_budget(long_icelandic_text: str, budget: int) -> None:
    for chunk in chunk_document(long_icelandic_text, budget):
        assert len(chunk.text) <= budget


def test_chunk_offsets_locate_the_chunk_in_the_source(long_icelandic_text: str) -> None:
    for chunk in chunk_document(long_icelandic_text, 400):
        assert long_icelandic_text[chunk.start : chunk.end] == chunk.text


def test_short_text_is_a_single_chunk() -> None:
    text = "Stutt málsgrein."
    chunks = chunk_document(text, 6000)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].start == 0


def test_chunks_are_packed_rather_than_one_per_paragraph() -> None:
    """Short paragraphs should share a chunk, not each cost a model call."""
    text = "\n\n".join(f"Málsgrein númer {n}." for n in range(20))
    chunks = chunk_document(text, 400)
    assert len(chunks) < 20


def test_paragraph_boundaries_are_preferred_over_sentence_boundaries() -> None:
    paragraph_a = "Fyrsta málsgrein. Hún er með tveimur setningum."
    paragraph_b = "Önnur málsgrein. Líka með tveimur."
    text = f"{paragraph_a}\n\n{paragraph_b}"
    chunks = chunk_document(text, len(paragraph_a) + 5)
    assert len(chunks) == 2
    assert chunks[0].text.strip() == paragraph_a


def test_an_overlong_sentence_is_split_only_as_a_last_resort() -> None:
    sentence = "orð " * 500  # one "sentence", far past any budget
    chunks = chunk_document(sentence, 200)
    assert reassemble(chunks) == sentence
    assert all(len(chunk.text) <= 200 for chunk in chunks)


def test_empty_and_whitespace_text_produce_no_chunks() -> None:
    assert chunk_document("", 100) == []
    assert chunk_document("   \n\n ", 100) == []


def test_invalid_budget_is_rejected() -> None:
    with pytest.raises(ValueError):
        chunk_document("halló", 0)


def test_emoji_do_not_break_chunk_offsets() -> None:
    text = "Halló 🎉 heimur.\n\n" + ("Löng málsgrein. " * 60)
    for chunk in chunk_document(text, 300):
        assert text[chunk.start : chunk.end] == chunk.text
