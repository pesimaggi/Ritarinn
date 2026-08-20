"""Optional neural correction engine (ByT5) — placeholder for Milestone 4.

``mideind/yfirlestur-icelandic-correction-byt5`` is an Icelandic-specific
sequence-to-sequence correction model. Loading it requires PyTorch/Transformers
and a multi-gigabyte download, so Ritarinn does not install it, does not fetch
it, and does not let it delay first startup.

This module exists so the engine appears in the status panel as a deliberate,
switched-off option rather than as a missing feature — and so Milestone 4 has a
seam to fill in rather than an architecture to change.
"""

from __future__ import annotations

from ritarinn.config import Settings
from ritarinn.services.correction.base import (
    CorrectionEngine,
    CorrectionOutcome,
    CorrectionRequest,
    EngineStatus,
    EngineUnavailableError,
)

ENGINE_NAME = "byt5"
PROVENANCE = "yfirlestur-icelandic-correction-byt5 eftir Miðeind ehf."

NOT_INSTALLED_DETAIL = (
    "Tauganetsleiðrétting er ekki sett upp. Hana þarf að setja upp sérstaklega "
    "og hún er ekki nauðsynleg fyrir yfirlestur."
)


class ByT5CorrectionEngine(CorrectionEngine):
    """Reports itself unavailable until Milestone 4 implements loading."""

    name = ENGINE_NAME

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def status(self) -> EngineStatus:
        return EngineStatus(
            name=ENGINE_NAME,
            label="ByT5 tauganetsleiðrétting",
            available=False,
            detail=NOT_INSTALLED_DETAIL,
            local_only=True,
            provenance=PROVENANCE,
        )

    def analyze(self, request: CorrectionRequest) -> CorrectionOutcome:
        raise EngineUnavailableError(ENGINE_NAME, NOT_INSTALLED_DETAIL)
