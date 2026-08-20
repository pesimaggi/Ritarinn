"""Model-agnostic contract for local text generation.

Ritarinn's generative features must never be written against a particular model
family. Icelandic quality varies enormously between models and will keep
changing, so the application calls ``provider.generate(...)`` and the model is a
configuration value.

The abstraction separates three things that are easy to conflate:

* the **model** (e.g. a Qwen or Mistral checkpoint) — what produces the text;
* the **runtime** (e.g. Ollama) — what executes the model;
* the **provider** — Ritarinn's adapter for a runtime.

A model made by a given company does not imply talking to that company. Ritarinn
only ever loads weights that are already on disk, through a runtime listening on
loopback. ``docs/architecture.md`` covers the consequences for provenance.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional, Sequence


@dataclass(frozen=True)
class ModelInfo:
    """A model the runtime has locally available."""

    name: str
    size_bytes: Optional[int] = None
    family: Optional[str] = None
    #: Quantisation/parameter details as reported by the runtime, if any.
    details: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderStatus:
    """Whether a local runtime is reachable and what it can run."""

    name: str
    label: str
    available: bool
    #: Endpoint the provider talks to. Always a loopback URL in v0.1.
    endpoint: Optional[str] = None
    version: Optional[str] = None
    models: Sequence[ModelInfo] = field(default_factory=tuple)
    #: The model currently selected in configuration, if any.
    selected_model: Optional[str] = None
    #: Icelandic explanation shown when ``available`` is False.
    detail: Optional[str] = None
    #: True when the provider performs inference on this machine only.
    local_only: bool = True

    @property
    def can_generate(self) -> bool:
        """A runtime with no model selected cannot be asked to produce text."""
        return self.available and bool(self.selected_model)


@dataclass(frozen=True)
class GenerationRequest:
    """One generation job.

    The prompt pair is kept separate so providers can map them onto whatever
    chat/completion shape their runtime expects.
    """

    system_prompt: str
    user_prompt: str
    model: str
    temperature: float = 0.2
    max_tokens: Optional[int] = None


@dataclass(frozen=True)
class GenerationResult:
    text: str
    model: str
    elapsed_ms: float


class ProviderUnavailableError(RuntimeError):
    """Raised when a runtime is not reachable or has no model selected."""

    def __init__(self, provider: str, detail: str) -> None:
        super().__init__(detail)
        self.provider = provider
        self.detail = detail


class FeatureNotAvailableError(RuntimeError):
    """Raised for a capability that this version deliberately does not ship."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class LocalLLMProvider(abc.ABC):
    """Base class for a locally running inference runtime."""

    #: Stable identifier, e.g. "ollama".
    name: str = ""

    @abc.abstractmethod
    def status(self) -> ProviderStatus:
        """Report reachability and locally available models. Must not raise."""

    @abc.abstractmethod
    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Produce text from a locally held model."""
