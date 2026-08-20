"""Request and response schemas for every endpoint.

Kept apart from :mod:`ritarinn.models.issue` because the issue shape is the
durable part of the contract — shared by every engine and mirrored in the
editor's state — while these are the envelopes around it.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from ritarinn.models.base import RitarinnModel
from ritarinn.models.issue import WritingIssue

# -- yfirlestur ---------------------------------------------------------------


class ProofreadRequest(RitarinnModel):
    """A document submitted for proofreading.

    The text is analysed exactly as given: Ritarinn never normalises, trims or
    re-encodes it, because the offsets in the response have to index the
    document the editor is holding.
    """

    text: str
    #: Engines to run. None or empty means the default selection, so a client
    #: does not have to know which engines exist.
    engines: Optional[list[str]] = None
    #: Engine rule codes the user has chosen to silence entirely.
    ignore_codes: list[str] = Field(default_factory=list)


class ProofreadResponse(RitarinnModel):
    """Individual findings — never a rewritten document.

    Deciding what to change is the author's job, so the response carries issues
    the user can accept or reject one at a time.
    """

    issues: list[WritingIssue]
    #: Stated rather than implied: a client must not have to guess how offsets
    #: are counted. See ``docs/architecture.md`` section 4.
    offset_unit: Literal["utf16"] = "utf16"
    #: The engines that actually ran, in the order their issues were collected.
    engines: list[str]
    #: Counts and timings only. Never contains user text — these are logged.
    stats: dict[str, int | float | str] = Field(default_factory=dict)


# -- staða --------------------------------------------------------------------


class HealthResponse(RitarinnModel):
    """Liveness, plus whether proofreading can actually serve a request."""

    status: Literal["ok"]
    version: str
    proofreading_ready: bool


class EngineStatusModel(RitarinnModel):
    """A correction engine's readiness, as shown in the first-run panel."""

    name: str
    label: str
    available: bool
    version: Optional[str] = None
    #: Icelandic, user-facing explanation shown when ``available`` is False. An
    #: engine that is off must say why, so it reads as an option rather than a
    #: missing feature.
    detail: Optional[str] = None
    local_only: bool = True
    #: Where the underlying component comes from, for the attribution panel.
    provenance: Optional[str] = None


class ModelInfoModel(RitarinnModel):
    """A model the local runtime already has on disk."""

    name: str
    size_bytes: Optional[int] = None
    family: Optional[str] = None
    #: Quantisation and parameter details as reported by the runtime.
    details: dict[str, str] = Field(default_factory=dict)


class ProviderStatusModel(RitarinnModel):
    """A local inference runtime: reachable, and what it can run."""

    name: str
    label: str
    available: bool
    #: Always a loopback URL — the configuration that would allow anything else
    #: is refused at startup.
    endpoint: Optional[str] = None
    version: Optional[str] = None
    models: list[ModelInfoModel] = Field(default_factory=list)
    selected_model: Optional[str] = None
    detail: Optional[str] = None
    local_only: bool = True
    #: A reachable runtime with no model selected cannot produce text, so the
    #: UI is told this directly instead of deriving it.
    can_generate: bool = False


class ModelsStatusResponse(RitarinnModel):
    """What language technology is installed. Nothing here downloads anything."""

    correction_engines: list[EngineStatusModel]
    llm_providers: list[ProviderStatusModel]
    proofreading_ready: bool
    generation_ready: bool


class PrivacyStatusResponse(RitarinnModel):
    """The machine-checkable basis for the "Staðbundið" indicator.

    Every field is a computed fact about the running configuration, so the
    interface can only claim the work is local when it actually is. ``local_only``
    is the conjunction the badge reads; the rest is what the user can inspect
    instead of taking that claim on trust.
    """

    local_only: bool
    bind_host: str
    binds_to_loopback_only: bool
    allowed_origins: list[str]
    wildcard_cors: bool
    remote_provider_configured: bool
    telemetry_enabled: bool
    #: Every endpoint the backend is permitted to contact.
    outbound_endpoints: list[str]
    #: Icelandic one-line summary shown next to the indicator.
    summary: str


# -- features that are deliberately not in this version -----------------------


class FeatureUnavailableResponse(RitarinnModel):
    """Why a reserved endpoint is not answering.

    Returned instead of quietly falling back to a hosted model: the detail text
    states that no cloud service is used, and the version says when the feature
    is expected.
    """

    detail: str
    feature: str
    available_in: str
