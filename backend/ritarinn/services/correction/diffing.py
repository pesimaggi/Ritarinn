"""Turning a rewritten sentence back into individually reviewable edits.

A sequence-to-sequence corrector answers with a whole corrected sentence. That
is the wrong shape for Ritarinn: replacing the user's sentence with the model's
would be a blind replacement of text the user never agreed to, and it would
throw away the one thing that makes a correction reviewable — knowing *which
words* changed and what they were before.

So the pair is diffed, and each region that differs becomes one edit anchored to
a character span of the original. The user then accepts or rejects each of them
separately, exactly as with a rule-based engine.

Three properties this module is written for:

* **Deterministic.** The same pair always yields the same edits, so a proofread
  is reproducible and can be pinned in tests. ``difflib.SequenceMatcher`` is
  deterministic given the same inputs, and no other source of ordering is used.
* **Word-aligned.** Diffing bytes or characters produces edits like "insert *l*
  at offset 14", which is true and useless. Diffing whole words produces
  "*tilöguna* → *tillöguna*", which is a correction a person can judge.
* **Offset-exact.** Every returned span indexes the original text, so accepting
  an edit replaces precisely the words it claims to.

Nothing here knows what produced the corrected text: it is shared machinery for
any engine that answers with a rewrite rather than with annotations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Sequence

#: A word (any run of non-space characters) or a run of whitespace. Splitting
#: this way keeps every character of the input in exactly one token, so token
#: spans can be added up into character offsets without a separate accounting
#: of the gaps between them.
_TOKEN = re.compile(r"\s+|\S+")

#: Maximum number of word tokens either side may have before diffing is skipped.
#: SequenceMatcher is quadratic in the worst case; a sentence long enough to
#: matter has already been rejected upstream, and this is a second floor under
#: pathological input rather than an expected limit.
MAX_TOKENS = 4000


@dataclass(frozen=True)
class TextEdit:
    """One region where the corrected text differs from the original.

    ``start`` and ``end`` are code-point offsets into the original text and
    delimit exactly the characters ``replacement`` should take the place of.
    An insertion has ``start == end``; a deletion has an empty ``replacement``.
    """

    start: int
    end: int
    original: str
    replacement: str

    @property
    def is_insertion(self) -> bool:
        return self.start == self.end

    @property
    def is_deletion(self) -> bool:
        return not self.replacement


def tokenize(text: str) -> list[tuple[int, str]]:
    """Split *text* into ``(start_offset, token)`` pairs, losing nothing.

    Concatenating the tokens reproduces *text* exactly, which is what makes the
    offsets computed from them trustworthy.
    """
    return [(match.start(), match.group(0)) for match in _TOKEN.finditer(text)]


def diff_words(original: str, corrected: str) -> list[TextEdit]:
    """Return the edits that turn *original* into *corrected*.

    Edits are word-aligned, non-overlapping and ordered by position. When the
    two strings are equal — the common case for a sentence with nothing wrong
    with it — the result is empty and no work is wasted.
    """
    if original == corrected:
        return []

    source = tokenize(original)
    target = tokenize(corrected)
    if len(source) > MAX_TOKENS or len(target) > MAX_TOKENS:
        return []

    source_words = [token for _, token in source]
    target_words = [token for _, token in target]

    # autojunk heuristically ignores tokens that occur in more than 1% of the
    # sequence, which for ordinary prose means common words like "að" and "og".
    # That is a speed trade-off aimed at source code, and here it would silently
    # move corrections onto the wrong words.
    matcher = SequenceMatcher(a=source_words, b=target_words, autojunk=False)

    edits: list[TextEdit] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        start = _offset_at(source, i1, original)
        end = _offset_at(source, i2, original)
        replacement = "".join(target_words[j1:j2])
        edit = _tighten(original, start, end, replacement)
        if edit is not None:
            edits.append(edit)
    return edits


def similarity(original: str, corrected: str) -> float:
    """How much of *original* survives in *corrected*, from 0.0 to 1.0.

    Callers use this as a sanity floor: a corrector that returns something
    barely related to the sentence it was given has not corrected it, and its
    answer should be discarded rather than diffed into a suggestion to replace
    the whole sentence.

    Measured over **characters**, not words, and that choice is the entire point
    of the function. A sentence in which every word is misspelled — exactly the
    sentence a corrector is for — shares no whole words with its correction and
    would score zero on a word-level comparison, so the check would throw away
    the model's best work. Its characters barely move.

    ``difflib``'s cheap ``quick_ratio`` is not used: it compares bags of
    characters, and two unrelated Icelandic sentences of similar length score
    around 0.9 on it. The real ratio costs tens of milliseconds on the longest
    sentence this is ever called with, against a neural forward pass measured in
    hundreds.
    """
    if original == corrected:
        return 1.0
    if not original or not corrected:
        return 0.0
    return SequenceMatcher(a=original, b=corrected, autojunk=False).ratio()


def _offset_at(tokens: Sequence[tuple[int, str]], index: int, text: str) -> int:
    """Character offset where token *index* begins; the text length past the end."""
    if index < len(tokens):
        return tokens[index][0]
    return len(text)


def _tighten(text: str, start: int, end: int, replacement: str) -> TextEdit | None:
    """Trim whitespace off the edges of an edit, or drop it if it is a no-op.

    A word-level opcode often covers the space in front of the words it
    changes, because whitespace is a token in its own right. Underlining that
    space, or letting an accepted correction swallow the newline before a
    paragraph, is the same mistake the rule-based engine takes care to avoid.

    Leading and trailing whitespace common to both sides is therefore moved out
    of the edit. Whitespace-only changes are kept — a missing space between two
    words is a real correction — but an edit that changes nothing at all is
    dropped, since a "correction" identical to the text is not reviewable.
    """
    original = text[start:end]

    while original and replacement and original[0] == replacement[0] and original[0].isspace():
        start += 1
        original = original[1:]
        replacement = replacement[1:]
    while original and replacement and original[-1] == replacement[-1] and original[-1].isspace():
        end -= 1
        original = original[:-1]
        replacement = replacement[:-1]

    if original == replacement:
        return None
    return TextEdit(start=start, end=end, original=original, replacement=replacement)


def anchor_insertions(text: str, edits: Sequence[TextEdit]) -> list[TextEdit]:
    """Widen zero-width insertions onto a neighbouring word, dropping overlaps.

    An insertion has nothing to underline. The editor anchors every issue to a
    non-empty range and discards anything else, so an insertion emitted as a
    zero-width span would vanish silently — the user would never see that the
    engine wanted a word added.

    So an insertion is re-expressed as a replacement of the word it sits beside:
    inserting *ekki* before *kom* becomes "kom" → "ekki kom". The document ends
    up identical, the span is underlineable, and the suggestion still reads as
    the change it is. Which side it attaches to is decided by the whitespace the
    inserted text already carries, so no space is invented and none is doubled.

    An anchored insertion can land on a span another edit already claims, since
    a single space is enough to separate two opcodes. Overlaps are dropped
    rather than merged: two competing suggestions for one span cannot both be
    accepted, and the earlier one is the one the user sees underlined.
    """
    kept: list[TextEdit] = []
    for edit in edits:
        resolved = edit if not edit.is_insertion else _attach(text, edit)
        if resolved is None:
            continue
        if kept and resolved.start < kept[-1].end:
            continue
        kept.append(resolved)
    return kept


def _attach(text: str, edit: TextEdit) -> TextEdit | None:
    """Re-anchor a zero-width insertion onto the word before or after it.

    Returns None when the inserted text carries no whitespace on either edge,
    which would leave no way to join it to a neighbouring word without
    inventing a space. A silently dropped suggestion is better than one that
    would glue two words together if accepted.
    """
    inserted = edit.replacement
    if not inserted.strip():
        return None

    if inserted[-1].isspace():
        span = _word_after(text, edit.start)
        if span is not None:
            start, end = span
            return TextEdit(start, end, text[start:end], inserted.lstrip() + text[start:end])

    if inserted[0].isspace():
        span = _word_before(text, edit.start)
        if span is not None:
            start, end = span
            return TextEdit(start, end, text[start:end], text[start:end] + inserted.rstrip())

    return None


def _word_after(text: str, position: int) -> tuple[int, int] | None:
    match = re.compile(r"\S+").search(text, position)
    return (match.start(), match.end()) if match else None


def _word_before(text: str, position: int) -> tuple[int, int] | None:
    matches = list(re.compile(r"\S+").finditer(text, 0, position))
    return (matches[-1].start(), matches[-1].end()) if matches else None
