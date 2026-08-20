"""Ollama adapter — detection only in v0.1.

Ollama is a *runtime*: it loads model weights that are already on disk and
serves them over a loopback HTTP API. It is not itself a language model, and
Ritarinn never uses Ollama's hosted services.

What this module does in v0.1 is ask a locally running Ollama which models the
user has, so the status panel can tell the truth about what is installed. No
user text is sent. Text generation (``generate``) is Milestone 2 and raises
until then, rather than being half-wired.

Every request is guarded by a loopback check on the configured URL, so a
mistyped or tampered-with configuration fails closed instead of quietly posting
documents to a remote host.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

from ritarinn.config import Settings, is_loopback_host
from ritarinn.services.llm.base import (
    FeatureNotAvailableError,
    GenerationRequest,
    GenerationResult,
    LocalLLMProvider,
    ModelInfo,
    ProviderStatus,
)

logger = logging.getLogger(__name__)

PROVIDER_NAME = "ollama"

DISABLED_DETAIL = "Slökkt er á tengingu við Ollama í stillingum."
NOT_FOUND_DETAIL = (
    "Ollama fannst ekki á þessari tölvu. Yfirlestur virkar áfram án þess; "
    "Ollama þarf aðeins fyrir samantekt og einföldun texta."
)
NO_MODEL_DETAIL = "Ekkert líkan valið."
GENERATION_NOT_IN_V01 = (
    "Textagerð með staðbundnu líkani er ekki komin í þessa útgáfu (áfangi 2)."
)


class OllamaProvider(LocalLLMProvider):
    """Talks to a local Ollama instance over loopback."""

    name = PROVIDER_NAME

    def __init__(self, settings: Settings, client: Optional[httpx.Client] = None) -> None:
        self._settings = settings
        self._client = client

    # -- internal -------------------------------------------------------------

    def _endpoint_is_local(self) -> bool:
        host = httpx.URL(self._settings.ollama_url).host
        return is_loopback_host(host)

    def _get(self, path: str) -> Optional[dict]:
        """GET a JSON document from the local Ollama, or None if unreachable."""
        if not self._endpoint_is_local():
            # Should be unreachable: Settings.validate() rejects this at load
            # time. Kept as a second gate because this is the one code path that
            # could send data off the machine.
            logger.error("Refusing to contact non-loopback Ollama endpoint")
            return None
        url = self._settings.ollama_url.rstrip("/") + path
        try:
            if self._client is not None:
                response = self._client.get(url, timeout=self._settings.ollama_timeout_seconds)
            else:
                with httpx.Client(
                    timeout=self._settings.ollama_timeout_seconds,
                    # Never route local traffic through a proxy; a proxy would
                    # take the request off the loopback interface.
                    trust_env=False,
                ) as client:
                    response = client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.debug("Ollama not reachable at %s (%s)", url, type(exc).__name__)
            return None

    # -- public ---------------------------------------------------------------

    def status(self) -> ProviderStatus:
        selected = self._settings.llm_model or None

        if not self._settings.ollama_enabled:
            return ProviderStatus(
                name=PROVIDER_NAME,
                label="Ollama",
                available=False,
                endpoint=self._settings.ollama_url,
                selected_model=selected,
                detail=DISABLED_DETAIL,
            )

        payload = self._get("/api/tags")
        if payload is None:
            return ProviderStatus(
                name=PROVIDER_NAME,
                label="Ollama",
                available=False,
                endpoint=self._settings.ollama_url,
                selected_model=selected,
                detail=NOT_FOUND_DETAIL,
            )

        models = tuple(_parse_model(entry) for entry in payload.get("models", []))
        detail = None if selected else NO_MODEL_DETAIL
        return ProviderStatus(
            name=PROVIDER_NAME,
            label="Ollama",
            available=True,
            endpoint=self._settings.ollama_url,
            models=models,
            selected_model=selected,
            detail=detail,
            local_only=True,
        )

    def generate(self, request: GenerationRequest) -> GenerationResult:
        raise FeatureNotAvailableError(GENERATION_NOT_IN_V01)


def _parse_model(entry: dict) -> ModelInfo:
    details = entry.get("details") or {}
    return ModelInfo(
        name=str(entry.get("name", "")),
        size_bytes=entry.get("size") if isinstance(entry.get("size"), int) else None,
        family=details.get("family"),
        details={
            key: str(value)
            for key, value in details.items()
            if key in {"family", "parameter_size", "quantization_level", "format"}
        },
    )
