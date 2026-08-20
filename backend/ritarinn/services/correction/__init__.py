"""Correction engines and their shared abstractions."""

from ritarinn.services.correction.base import CorrectionEngine, EngineStatus
from ritarinn.services.correction.registry import EngineRegistry

__all__ = ["CorrectionEngine", "EngineStatus", "EngineRegistry"]
