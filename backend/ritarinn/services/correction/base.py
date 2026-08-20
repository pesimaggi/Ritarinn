"""The correction-engine abstraction.

Ritarinn treats proofreading as a pluggable capability. v0.1 ships one engine
(GreynirCorrect); Milestone 4 adds a neural one (ByT5) and a hybrid mode. The
API surface below is what those later engines have to satisfy, and it is
deliberately narrow:

* an engine reports its own readiness — it is never assumed to be installed;
* an engine returns issues, never a rewritten document;
* an engine is given the text exactly as the user typed it.

The last point matters. Ritarinn never normalises, trims or re-encodes user
text before analysis, because the offsets an engine returns have to index the
document the editor is holding.
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
    """A single proofreading job."""

    text: str
    #: GreynirCorrect rule codes the user has chosen to silence entirely.
    ignore_codes: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class CorrectionOutcome:
    """What an engine produced for one request."""

    issues: Sequence[WritingIssue]
    #: Engine-reported diagnostics. Must never contain user text — these are
    #: surfaced in logs. See ``docs/privacy.md``.
    stats: dict[str, float | int | str] = field(default_factory=dict)


class CorrectionEngine(abc.ABC):
    """Base class for anything that finds issues in Icelandic text."""

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

        Called once during application startup. Failures here must not prevent
        the application from starting — an engine that cannot warm up simply
        reports itself unavailable.
        """
        return None


class EngineUnavailableError(RuntimeError):
    """Raised when an engine is asked to analyze but is not installed/ready."""

    def __init__(self, engine: str, detail: str) -> None:
        super().__init__(detail)
        self.engine = engine
        self.detail = detail
