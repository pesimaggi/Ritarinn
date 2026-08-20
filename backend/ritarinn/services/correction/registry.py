"""Engine lookup and selection.

Keeping the registry separate from the engines means the API layer never
imports a concrete engine, and adding the ByT5 or hybrid engine later is a
registration change rather than a routing change.
"""

from __future__ import annotations

import logging
from typing import Iterator, Sequence

from ritarinn.config import Settings
from ritarinn.services.correction.base import CorrectionEngine, EngineStatus
from ritarinn.services.correction.byt5 import ByT5CorrectionEngine
from ritarinn.services.correction.greynir import GreynirCorrectEngine

logger = logging.getLogger(__name__)

#: Used when a request does not name any engine.
DEFAULT_ENGINES: tuple[str, ...] = ("greynir",)


class UnknownEngineError(KeyError):
    """Raised when a request names an engine that does not exist."""


class EngineRegistry:
    """Holds one instance of each correction engine for the process lifetime."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        engines: list[CorrectionEngine] = [
            GreynirCorrectEngine(),
            ByT5CorrectionEngine(settings),
        ]
        self._engines: dict[str, CorrectionEngine] = {e.name: e for e in engines}

    def __iter__(self) -> Iterator[CorrectionEngine]:
        return iter(self._engines.values())

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._engines)

    def get(self, name: str) -> CorrectionEngine:
        try:
            return self._engines[name]
        except KeyError as exc:
            raise UnknownEngineError(name) from exc

    def resolve(self, names: Sequence[str] | None) -> list[CorrectionEngine]:
        """Return the engines named, or the default selection."""
        requested = list(names) if names else list(DEFAULT_ENGINES)
        return [self.get(name) for name in requested]

    def statuses(self) -> list[EngineStatus]:
        return [engine.status() for engine in self._engines.values()]

    def warm_up(self) -> None:
        for engine in self._engines.values():
            try:
                engine.warm_up()
            except Exception:  # pragma: no cover - warm-up is best effort
                logger.exception("Warm-up failed for engine %s", engine.name)
