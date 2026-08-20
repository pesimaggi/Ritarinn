"""Shared result types and post-processing for generative features."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from ritarinn.models.issue import WritingIssue


@dataclass(frozen=True)
class GenerationOutcome:
    """What a generative feature produced, plus how it got there.

    The provenance fields are not decoration: a user reading a summary of a
    long document should be able to see that it was assembled from parts, and
    which model wrote it.
    """

    text: str
    model: str
    elapsed_ms: float
    #: Number of source chunks the document was divided into.
    chunks: int
    #: 1 for a single pass; 2 when chunk summaries were combined.
    passes: int
    #: Issues found by proofreading the *generated* text, when requested.
    #: Advisory only — the text is never altered on the strength of them.
    issues: Sequence[WritingIssue] = field(default_factory=tuple)
    #: True when the model stopped because it hit its output cap.
    truncated: bool = False
