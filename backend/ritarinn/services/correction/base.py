"""The correction-provider abstraction.

Ritarinn treats proofreading as a pluggable capability with two independent
families of provider behind it: a rule-based one (GreynirCorrect) and a neural
one (ByT5). "Engine" and "correction provider" are the same thing — the word
"engine" is in the wire contract (``engines: ["greynir"]``) and is kept.

This is deliberately *not* the same abstraction as
``ritarinn.services.llm.LocalLLMProvider``, which serves summarization and
rewriting. Correction and generation are different jobs with different models,
different failure modes and different review workflows; a change of correction
model must not be able to move a generative feature, or the reverse.

The contract below is what every provider satisfies, and it is narrow on
purpose:

* a provider reports its own readiness — it is never assumed to be installed;
* a provider returns issues, never a rewritten document;
* a provider is given the text exactly as the user typed it;
* a provider that answers with a rewrite converts it into reviewable issues
  itself (``diffing.py``), because the rest of the application has no way to
  review a whole replaced document.

The third point matters most. Ritarinn never normalises, trims or re-encodes
user text before analysis, because the offsets a provider returns have to index
the document the editor is holding.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional, Sequence

from ritarinn.models.issue import WritingIssue


@dataclass(frozen=True)
class EngineStatus:
    """Whether an engine can run right now, and why not if it cannot."""

    name: str
    #: Icelandic label for the UI, e.g. "GreynirCorrect".
    label: str
    available: bool
    #: Version of the underlying library or model, when it can be determined.
    version: Optional[str] = None
    #: Icelandic, user-facing explanation shown when ``available`` is False.
    detail: Optional[str] = None
    #: True if the engine performs all work on this machine. An engine that
    #: cannot honestly claim this must not be enabled by default.
    local_only: bool = True
    #: Where the underlying component comes from, for the attribution panel.
    provenance: Optional[str] = None


@dataclass(frozen=True)
class CorrectionRequest:
    """A single proofreading job.

    The same request goes to every selected provider, so it carries nothing
    provider-specific. A provider ignores what does not apply to it: ByT5
    publishes no rule codes, so there is nothing for ``ignore_codes`` to silence
    in its output, and it does not consult the field.
    """

    text: str
    #: Provider rule codes the user has chosen to silence entirely. Codes are the
    #: provider's own vocabulary — Ritarinn invents none — so a code only ever
    #: means something to the provider that emitted it.
    ignore_codes: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class CorrectionOutcome:
    """What an engine produced for one request."""

    issues: Sequence[WritingIssue]
    #: Engine-reported diagnostics. Must never contain user text — these are
    #: surfaced in logs. See ``docs/privacy.md``.
    stats: dict[str, float | int | str] = field(default_factory=dict)


class CorrectionEngine(abc.ABC):
    """Base class for anything that finds issues in Icelandic text.

    Implementations own everything specific to how they work — loading,
    tokenization, inference, their own configuration — so that none of it
    reaches routes, schemas or the editor.
    """

    #: Stable identifier used in the API (``engines: ["greynir"]``) and as the
    #: ``source`` of every issue the engine emits.
    name: str = ""

    @abc.abstractmethod
    def status(self) -> EngineStatus:
        """Report readiness. Must not raise, and must not be expensive."""

    @abc.abstractmethod
    def analyze(self, request: CorrectionRequest) -> CorrectionOutcome:
        """Find issues in ``request.text``.

        Implementations must return offsets in UTF-16 code units relative to
        ``request.text``, and must leave the text itself untouched.
        """

    def warm_up(self) -> None:
        """Optionally pre-load resources at startup.

        Called once during application startup: the intentional initialization
        step for a provider whose model is expensive to load. Whatever is loaded
        is then reused for the life of the process — never re-loaded per
        sentence or per request.

        Failures here must not prevent the application from starting. A provider
        that cannot warm up reports itself unavailable, and the rest of
        proofreading carries on without it.
        """
        return None


class EngineUnavailableError(RuntimeError):
    """Raised when an engine is asked to analyze but is not installed/ready."""

    def __init__(self, engine: str, detail: str) -> None:
        super().__init__(detail)
        self.engine = engine
        self.detail = detail
