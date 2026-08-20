"""The single issue shape every correction engine emits.

A deterministic engine, a neural one and (later) a generative one all produce
this same model, so the editor never learns which engine found what. The fields
that carry a decision rather than a value are documented at their definition;
``docs/architecture.md`` section 6 covers the reasoning.

Offsets are UTF-16 code units into the text exactly as the user submitted it.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from ritarinn.models.base import RitarinnModel

#: Which engine produced an issue. Part of the contract rather than free text,
#: so the sidebar can attribute a finding without string matching.
IssueSource = Literal["greynir", "byt5", "local-llm", "style"]

#: Ritarinn's coarse grouping over engine-specific codes. Kept in step with
#: ``ritarinn.services.correction.categories``, which decides which code lands
#: in which category; an unrecognised code becomes "unknown" rather than a guess.
IssueCategory = Literal["spelling", "grammar", "punctuation", "style", "unknown"]

#: "error" and "warning" come from GreynirCorrect's own ``/w`` marker — an
#: upstream distinction, not a heuristic of ours.
IssueSeverity = Literal["error", "warning"]

#: Whether the span *is* the problem ("span"), or merely the sentence containing
#: it ("sentence" — unparseable, very long, not Icelandic). Sentence-scope
#: issues are listed but not underlined: a line under a whole paragraph buries
#: the word-level issues inside it.
IssueScope = Literal["span", "sentence"]


class WritingIssue(RitarinnModel):
    """One reviewable finding in the user's text."""

    #: Stable within a single response; used by the editor to track decisions.
    id: str
    source: IssueSource
    category: IssueCategory
    #: The engine's own code (``S004``, ``P_WRONG_CASE_þgf_þf``), passed through
    #: verbatim. Ritarinn invents no codes.
    code: Optional[str] = None
    #: Icelandic label for the code's group, e.g. "Samsett orð".
    family: Optional[str] = None

    #: UTF-16 code-unit offsets into the submitted text, half-open [start, end).
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)
    scope: IssueScope

    #: The text the span selects, so a client can verify the offsets it was given.
    original: str
    #: The engine's suggested text for that span, ready to apply as-is. None when
    #: the engine has no confident fix — which is normal, not an error.
    replacement: Optional[str] = None
    #: Further suggestions, never including ``replacement``.
    alternatives: list[str] = Field(default_factory=list)

    #: Short Icelandic description, shown as the issue's heading.
    title: str
    #: Longer Icelandic explanation. May contain ``<a>`` markup from the engine,
    #: which the frontend strips before rendering.
    explanation: Optional[str] = None
    severity: IssueSeverity
    #: Rule or grammar references the engine supplied.
    references: list[str] = Field(default_factory=list)
    #: Set only when an engine reports a genuine score. GreynirCorrect reports
    #: none, so its issues carry none — a number is never invented to fill this in.
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
