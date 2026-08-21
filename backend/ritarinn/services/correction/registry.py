"""Correction-provider lookup and selection.

Keeping the registry separate from the providers means the API layer never
imports a concrete one, so adding a provider — or a hybrid of two — is a
registration change rather than a routing change.

Which providers run by default is configuration (``RITARINN_CORRECTION_ENGINES``),
not a constant here, so ByT5 can be switched on without editing application
code. A name that does not exist is rejected when the registry is built, which
turns a typo into a startup error rather than a puzzling 400 on the first
proofread.
"""

from __future__ import annotations

import logging
from typing import Iterator, Sequence

from ritarinn.config import ConfigurationError, Settings
from ritarinn.services.correction.base import CorrectionEngine, EngineStatus
from ritarinn.services.correction.byt5 import ByT5CorrectionEngine
from ritarinn.services.correction.greynir import GreynirCorrectEngine

logger = logging.getLogger(__name__)


class UnknownEngineError(KeyError):
    """Raised when a request names an engine that does not exist."""


class EngineRegistry:
    """Holds one instance of each correction provider for the process lifetime.

    One instance, not one per request: a provider may hold seconds of loading
    and gigabytes of memory behind it, and reusing it is what keeps a proofread
    to the cost of the analysis itself.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        engines: list[CorrectionEngine] = [
            GreynirCorrectEngine(),
            ByT5CorrectionEngine(settings),
        ]
        self._engines: dict[str, CorrectionEngine] = {e.name: e for e in engines}

        unknown = [name for name in settings.correction_engines if name not in self._engines]
        if unknown:
            raise ConfigurationError(
                f"RITARINN_CORRECTION_ENGINES names unknown engines: {', '.join(unknown)}. "
                f"Available: {', '.join(self._engines)}."
            )

    @property
    def default_names(self) -> tuple[str, ...]:
        """The configured default selection."""
        return tuple(self._settings.correction_engines)

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
        """Return the providers named, or the configured default selection."""
        requested = list(names) if names else list(self.default_names)
        return [self.get(name) for name in requested]

    def statuses(self) -> list[EngineStatus]:
        return [engine.status() for engine in self._engines.values()]

    def warm_up(self) -> None:
        for engine in self._engines.values():
            try:
                engine.warm_up()
            except Exception:  # pragma: no cover - warm-up is best effort
                logger.exception("Warm-up failed for engine %s", engine.name)
