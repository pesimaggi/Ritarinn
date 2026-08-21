"""Correction providers and their shared abstractions."""

from ritarinn.services.correction.base import (
    CorrectionEngine,
    CorrectionOutcome,
    CorrectionRequest,
    EngineStatus,
    EngineUnavailableError,
)
from ritarinn.services.correction.registry import EngineRegistry

__all__ = [
    "CorrectionEngine",
    "CorrectionOutcome",
    "CorrectionRequest",
    "EngineStatus",
    "EngineUnavailableError",
    "EngineRegistry",
]
