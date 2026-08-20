"""Cross-language character offset correctness.

Python indexes strings by code point, JavaScript by UTF-16 code unit. Every
correction Ritarinn applies depends on the two agreeing, so the conversion is
tested against ground truth rather than by inspection.
"""

from __future__ import annotations

import pytest

from ritarinn.text.offsets import Utf16OffsetMap, trim_span, utf16_length

from conftest import js_slice

ICELANDIC_ALPHABET = "áéíóúýþæöðÁÉÍÓÚÝÞÆÖÐ"

SAMPLES = [
    "",
    "Halló heimur",
    ICELANDIC_ALPHABET,
    "Þinngið samþikkti tilöguna.",
    "Hann sagði „þetta er gott“ — og fór.",
    "Til hamingju 🎉 með daginn! 😀",
    "🇮🇸🇮🇸🇮🇸 fánar",
    "Ólafur og ólafur",  # precomposed vs combining acute
    "𝄞 tónlist 𝄞",
    "á́́ margir samsettir stafir",
    "lína ein\nlína tvö\r\nlína þrjú",
    "\t\ttabs\tog   bil",
]


def reference_utf16_offset(text: str, code_point_offset: int) -> int:
    """Ground truth: how long the prefix is when encoded as UTF-16."""
    return len(text[:code_point_offset].encode("utf-16-le")) // 2


@pytest.mark.parametrize("text", SAMPLES)
def test_every_offset_converts_correctly(text: str) -> None:
    mapping = Utf16OffsetMap(text)
    for offset in range(len(text) + 1):
        assert mapping.to_utf16(offset) == reference_utf16_offset(text, offset)


@pytest.mark.parametrize("text", SAMPLES)
def test_utf16_length_matches_javascript(text: str) -> None:
    assert utf16_length(text) == len(text.encode("utf-16-le")) // 2


def test_icelandic_letters_need_no_conversion() -> None:
    """The whole Icelandic alphabet is in the BMP, so offsets coincide."""
    mapping = Utf16OffsetMap(ICELANDIC_ALPHABET)
    assert mapping.is_identity
    assert mapping.to_utf16(len(ICELANDIC_ALPHABET)) == len(ICELANDIC_ALPHABET)


def test_astral_characters_shift_later_offsets() -> None:
    """An emoji occupies two UTF-16 units, so everything after it moves."""
    text = "😀 Þingið"
    mapping = Utf16OffsetMap(text)
    assert not mapping.is_identity
    # "Þingið" starts at code point 2, but at UTF-16 unit 3.
    assert text[2:] == "Þingið"
    assert mapping.to_utf16(2) == 3
    assert js_slice(text, 3, mapping.to_utf16(len(text))) == "Þingið"


def test_offsets_outside_the_text_are_rejected() -> None:
    mapping = Utf16OffsetMap("Halló")
    with pytest.raises(IndexError):
        mapping.to_utf16(6)
    with pytest.raises(IndexError):
        mapping.to_utf16(-1)


# -- span trimming ------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "start", "end", "expected"),
    [
        ("  orð  ", 0, 7, (2, 5)),
        ("\n\nÞingið", 0, 8, (2, 8)),
        ("orð", 0, 3, (0, 3)),
        ("a orð b", 1, 5, (2, 5)),
    ],
)
def test_trim_span_excludes_surrounding_whitespace(
    text: str, start: int, end: int, expected: tuple[int, int]
) -> None:
    assert trim_span(text, start, end) == expected


def test_trim_span_leaves_all_whitespace_spans_alone() -> None:
    """A span that is nothing but whitespace stays valid rather than empty."""
    assert trim_span("   ", 0, 3) == (0, 3)


def test_greynir_token_originals_reconstruct_the_input() -> None:
    """The invariant the whole offset scheme rests on.

    GreynirCorrect keeps each token's verbatim source in ``token.original``, so
    concatenating them reproduces the input — except for trailing whitespace at
    the very end of the document, which cannot shift any earlier offset. If a
    future version of GreynirCorrect broke this, every span would silently
    drift, so it is asserted directly.
    """
    import reynir_correct

    api = reynir_correct.GreynirCorrectAPI.from_options()
    for text in SAMPLES:
        if not text.strip():
            continue
        result = api.correct(text)
        reconstructed = "".join(
            token.original if token.original is not None else (token.txt or "")
            for sentence in result.sentences
            for token in sentence.tokens
        )
        assert text.startswith(reconstructed), f"token stream diverged from input: {text!r}"
        assert text[len(reconstructed) :].strip() == "", "only trailing whitespace may be dropped"
