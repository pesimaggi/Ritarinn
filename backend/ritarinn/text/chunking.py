"""Splitting Icelandic documents into pieces a local model can handle.

A local model has a bounded context, and a user's document does not. Long text
therefore has to be divided — but *where* it is divided determines whether the
summary is any good. Cutting mid-sentence hands the model a fragment with no
subject, and it will invent one.

So this module splits on structure, preferring in order:

1. paragraph boundaries (blank lines) — the author's own division of the text;
2. sentence boundaries within an over-long paragraph;
3. a hard character split, only for a single sentence longer than the budget,
   which is rare and cannot be handled any better.

Sentence boundaries come from Miðeind's tokenizer rather than a regular
expression, because Icelandic abbreviations ("sbr.", "3. mgr.", "nr. 7/1998")
break naive full-stop splitting immediately.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Chunk:
    """A contiguous piece of the source document."""

    text: str
    #: Character offset of this chunk in the original document.
    start: int
    #: Index of this chunk in the sequence, from 0.
    index: int

    @property
    def end(self) -> int:
        return self.start + len(self.text)


def split_sentences(text: str) -> list[str]:
    """Split Icelandic text into sentences, preserving all characters.

    The concatenation of the result equals the input, so offsets computed from
    it stay valid.
    """
    if not text:
        return []
    try:
        from tokenizer import split_into_sentences
    except ImportError:  # pragma: no cover - tokenizer ships with GreynirCorrect
        return [text]

    sentences: list[str] = []
    cursor = 0
    for sentence in split_into_sentences(text, original=True):
        # The tokenizer normalises whitespace between tokens, so the returned
        # sentence text is not guaranteed to be character-identical to the
        # source. Locate it instead of trusting it, and fall back to keeping the
        # remainder whole rather than risk dropping characters.
        stripped = sentence.strip()
        if not stripped:
            continue
        found = text.find(stripped[:40], cursor) if len(stripped) >= 40 else text.find(stripped, cursor)
        if found == -1:
            continue
        sentences.append((found, len(stripped)))
        cursor = found + 1

    if not sentences:
        return [text]

    # Rebuild spans so that every character of the input lands in exactly one
    # sentence, including the whitespace between them.
    pieces: list[str] = []
    for position, (start, _length) in enumerate(sentences):
        next_start = sentences[position + 1][0] if position + 1 < len(sentences) else len(text)
        piece_start = start if position > 0 else 0
        pieces.append(text[piece_start:next_start])
    return [piece for piece in pieces if piece]


def split_paragraphs(text: str) -> list[str]:
    """Split on blank lines, keeping each paragraph's trailing separator.

    Concatenating the result reproduces the input exactly.
    """
    if not text:
        return []
    paragraphs: list[str] = []
    current: list[str] = []
    lines = text.splitlines(keepends=True)
    for line in lines:
        current.append(line)
        if line.strip() == "" and any(part.strip() for part in current):
            paragraphs.append("".join(current))
            current = []
    if current:
        paragraphs.append("".join(current))
    return [p for p in paragraphs if p]


def chunk_document(text: str, budget_chars: int) -> list[Chunk]:
    """Divide *text* into chunks of at most ``budget_chars`` where possible.

    Chunks are packed greedily: consecutive paragraphs are combined until
    adding another would exceed the budget, so a document of short paragraphs
    does not turn into one model call per paragraph.
    """
    if budget_chars <= 0:
        raise ValueError("budget_chars must be positive")
    if not text.strip():
        return []
    if len(text) <= budget_chars:
        return [Chunk(text=text, start=0, index=0)]

    units = _split_to_budget(text, budget_chars)

    chunks: list[Chunk] = []
    cursor = 0
    buffer: list[str] = []
    buffer_start = 0

    for unit in units:
        if buffer and len(("".join(buffer)) + unit) > budget_chars:
            joined = "".join(buffer)
            chunks.append(Chunk(text=joined, start=buffer_start, index=len(chunks)))
            buffer = []
            buffer_start = cursor
        if not buffer:
            buffer_start = cursor
        buffer.append(unit)
        cursor += len(unit)

    if buffer:
        chunks.append(Chunk(text="".join(buffer), start=buffer_start, index=len(chunks)))
    return chunks


def _split_to_budget(text: str, budget_chars: int) -> list[str]:
    """Break *text* into units no larger than the budget, structure first."""
    units: list[str] = []
    for paragraph in split_paragraphs(text):
        if len(paragraph) <= budget_chars:
            units.append(paragraph)
            continue
        for sentence in split_sentences(paragraph):
            if len(sentence) <= budget_chars:
                units.append(sentence)
                continue
            # A single sentence longer than the budget. Nothing structural is
            # left to split on, so this is the one place a hard cut happens.
            units.extend(_hard_split(sentence, budget_chars))
    return units


def _hard_split(text: str, budget_chars: int) -> Iterable[str]:
    for start in range(0, len(text), budget_chars):
        yield text[start : start + budget_chars]


def reassemble(chunks: Sequence[Chunk]) -> str:
    """Concatenate chunk texts. Used by tests to assert nothing was lost."""
    return "".join(chunk.text for chunk in chunks)
