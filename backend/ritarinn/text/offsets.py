"""Conversion between Python and JavaScript string offsets.

Python indexes strings by Unicode code point; JavaScript (and therefore
CodeMirror, and every browser API we hand a range to) indexes by UTF-16 code
unit. The two agree for the entire Icelandic alphabet, including á é í ó ú ý þ
æ ö ð, because those all live in the Basic Multilingual Plane. They diverge the
moment a document contains an astral-plane character — an emoji, a musical
symbol, some rare CJK — where Python counts 1 and JavaScript counts 2.

A document with a single emoji in the first paragraph would therefore shift
every later correction one character to the left in the editor. Ritarinn
resolves this by converting once, here, and publishing UTF-16 offsets over the
API. See ``docs/architecture.md`` for why the boundary was drawn on this side.
"""

from __future__ import annotations

from bisect import bisect_right

# Code points at or above this value are encoded as a surrogate pair in UTF-16,
# so they occupy two code units instead of one.
_ASTRAL_THRESHOLD = 0x10000


class Utf16OffsetMap:
    """Maps code-point offsets in a fixed string to UTF-16 code-unit offsets.

    Built once per document in O(n); each lookup is O(log k) where k is the
    number of astral characters, which is zero for ordinary Icelandic text.
    """

    __slots__ = ("_astral_positions", "_length")

    def __init__(self, text: str) -> None:
        self._length = len(text)
        # Position (in code points) of every character needing a surrogate pair.
        self._astral_positions: list[int] = [
            index for index, char in enumerate(text) if ord(char) >= _ASTRAL_THRESHOLD
        ]

    @property
    def is_identity(self) -> bool:
        """True when code-point and UTF-16 offsets coincide for this text."""
        return not self._astral_positions

    def to_utf16(self, offset: int) -> int:
        """Convert a code-point offset to a UTF-16 code-unit offset."""
        if offset < 0 or offset > self._length:
            raise IndexError(f"offset {offset} outside text of length {self._length}")
        if not self._astral_positions:
            return offset
        # Every astral character strictly before `offset` adds one extra unit.
        return offset + bisect_right(self._astral_positions, offset - 1)


def utf16_length(text: str) -> int:
    """Length of *text* as JavaScript would report it (``String.length``)."""
    return len(text) + sum(1 for char in text if ord(char) >= _ASTRAL_THRESHOLD)


def trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Shrink ``[start, end)`` so it excludes leading and trailing whitespace.

    GreynirCorrect annotates token spans, and a token's original text carries
    the whitespace that preceded it — including paragraph breaks. Underlining
    that whitespace looks wrong, and accepting such a correction would swallow
    the newline before the word. Spans that are entirely whitespace are left
    untouched so that callers still get a valid, non-empty range.
    """
    trimmed_start, trimmed_end = start, end
    while trimmed_start < trimmed_end and text[trimmed_start].isspace():
        trimmed_start += 1
    while trimmed_end > trimmed_start and text[trimmed_end - 1].isspace():
        trimmed_end -= 1
    if trimmed_start >= trimmed_end:
        return start, end
    return trimmed_start, trimmed_end
