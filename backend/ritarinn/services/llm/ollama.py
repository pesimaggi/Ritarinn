"""Ollama adapter — detection only in v0.1.

Ollama is a *runtime*: it loads model weights that are already on disk and
serves them over a loopback HTTP API. It is not itself a language model, and
Ritarinn never uses Ollama's hosted services.

This module does two things: it asks a locally running Ollama which models the
user has, so the status panel can tell the truth about what is installed; and
it runs generation against a model the user has chosen.

Every request is guarded by a loopback check on the configured URL, so a
mistyped or tampered-with configuration fails closed instead of quietly posting
documents to a remote host. That check is the one place where user text could
leave the machine, so it is enforced twice — once at configuration load, and
again on each request.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Optional

import httpx

from ritarinn.config import Settings, is_loopback_host
from ritarinn.services.llm.base import (
    GenerationRequest,
    GenerationResult,
    LocalLLMProvider,
    ModelInfo,
    ProviderStatus,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)

PROVIDER_NAME = "ollama"

DISABLED_DETAIL = "Slökkt er á tengingu við Ollama í stillingum."
NOT_FOUND_DETAIL = (
    "Ollama fannst ekki á þessari tölvu. Yfirlestur virkar áfram án þess; "
    "Ollama þarf aðeins fyrir samantekt og einföldun texta."
)
NO_MODEL_DETAIL = "Ekkert líkan valið."
UNREACHABLE_DETAIL = (
    "Náði ekki sambandi við Ollama á þessari tölvu. Athugaðu hvort Ollama sé í gangi."
)
MODEL_MISSING_DETAIL = (
    "Líkanið {model!r} fannst ekki í Ollama. Sæktu það með: ollama pull {model}"
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

    def _require_local_endpoint(self) -> str:
        """Return the base URL, refusing anything that is not on loopback.

        ``Settings.validate()`` already rejects a non-loopback endpoint at load
        time. This is a second, independent gate, because generation is the one
        code path that carries the user's document — and a guarantee this
        central is worth checking twice.
        """
        if not self._endpoint_is_local():
            raise ProviderUnavailableError(
                PROVIDER_NAME,
                "Neita að senda texta á vistfang sem er ekki staðbundið.",
            )
        return self._settings.ollama_url.rstrip("/")

    def _get(self, path: str) -> Optional[dict]:
        """GET a JSON document from the local Ollama, or None if unreachable."""
        try:
            url = self._require_local_endpoint() + path
        except ProviderUnavailableError:
            logger.error("Refusing to contact non-loopback Ollama endpoint")
            return None
        try:
            if self._client is not None:
                response = self._client.get(url, timeout=self._settings.ollama_timeout_seconds)
            else:
                with self._new_client(self._settings.ollama_timeout_seconds) as client:
                    response = client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            logger.debug("Ollama not reachable at %s (%s)", url, type(exc).__name__)
            return None

    @staticmethod
    def _new_client(timeout: float) -> httpx.Client:
        # trust_env=False so an ambient HTTP_PROXY cannot pull loopback traffic
        # off the loopback interface.
        return httpx.Client(timeout=timeout, trust_env=False)

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
        """Run one generation against a locally held model.

        Uses Ollama's chat endpoint with streaming disabled: Ritarinn shows a
        result only once it is complete and reviewable, so there is nothing to
        do with partial output yet. Streaming would improve the wait on slow
        hardware and is noted as future work in docs/roadmap.md.
        """
        if not self._settings.ollama_enabled:
            raise ProviderUnavailableError(PROVIDER_NAME, DISABLED_DETAIL)
        if not request.model:
            raise ProviderUnavailableError(PROVIDER_NAME, NO_MODEL_DETAIL)

        url = self._require_local_endpoint() + "/api/chat"
        payload = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "stream": False,
            "options": {"temperature": request.temperature},
            # Reasoning models otherwise emit a chain of thought before the
            # answer, which is not what the user asked to put in their document.
            # Runtimes that do not know this flag ignore it, and the response
            # cleaning below catches what slips through.
            "think": False,
        }
        if request.max_tokens is not None:
            # An output cap is not optional for local generation: an unbounded
            # reasoning model on a CPU will happily run past any timeout, and
            # the user sees a hang rather than a result.
            payload["options"]["num_predict"] = request.max_tokens

        started = time.perf_counter()
        try:
            if self._client is not None:
                response = self._client.post(
                    url, json=payload, timeout=self._settings.llm_timeout_seconds
                )
            else:
                with self._new_client(self._settings.llm_timeout_seconds) as client:
                    response = client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(
                PROVIDER_NAME,
                "Líkanið svaraði ekki í tæka tíð. Prófaðu styttri texta eða minna líkan.",
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(PROVIDER_NAME, UNREACHABLE_DETAIL) from exc

        if response.status_code == 404:
            raise ProviderUnavailableError(
                PROVIDER_NAME, MODEL_MISSING_DETAIL.format(model=request.model)
            )
        if response.status_code >= 400:
            # Ollama's error body is developer-facing; it is logged, not shown.
            logger.warning("Ollama returned HTTP %d for a generation request", response.status_code)
            raise ProviderUnavailableError(
                PROVIDER_NAME, "Staðbundna líkanið skilaði villu. Sjá annál bakendans."
            )

        body = response.json()
        message = body.get("message") or {}
        text = clean_model_output(str(message.get("content", "")))
        if not text:
            # Nothing left after cleaning. When the runtime also reports that it
            # stopped at the output cap, the model spent its whole budget
            # reasoning and never reached an answer — a different problem for
            # the user than a model that simply returned nothing, and one they
            # can act on.
            if body.get("done_reason") == "length":
                raise ProviderUnavailableError(
                    PROVIDER_NAME,
                    "Líkanið notaði allt svigrúmið í hugsanaferli og skilaði engri "
                    "samantekt. Veldu líkan sem ekki 'hugsar' upphátt, eða uppfærðu "
                    "Ollama svo hægt sé að slökkva á því.",
                )
            raise ProviderUnavailableError(
                PROVIDER_NAME, "Staðbundna líkanið skilaði engum texta."
            )

        elapsed_ms = (time.perf_counter() - started) * 1000
        # Counts and timings only; never the prompt or the output.
        logger.info(
            "generation completed | model=%s | chars=%d | %.0f ms",
            request.model,
            len(text),
            elapsed_ms,
        )
        return GenerationResult(
            text=text,
            model=request.model,
            elapsed_ms=elapsed_ms,
            # Ollama reports "length" when it stopped at num_predict.
            truncated=body.get("done_reason") == "length",
        )


#: Chain-of-thought wrappers emitted by reasoning models that ignore `think`.
_THINK_BLOCK = re.compile(r"<(think|thinking)>.*?</\1>", re.DOTALL | re.IGNORECASE)
#: A closing tag with no opening tag. Some reasoning models put the opening tag
#: in the chat template's assistant prefix rather than generating it, so the
#: runtime returns a completion that *starts* mid-thought and is terminated by
#: a bare ``</think>``. Everything up to that tag is reasoning, not an answer.
_ORPHAN_THINK_CLOSE = re.compile(r"\A.*?</(think|thinking)>", re.DOTALL | re.IGNORECASE)
#: An unterminated block, which happens when generation is cut off by the cap.
_UNCLOSED_THINK = re.compile(r"<(think|thinking)>.*\Z", re.DOTALL | re.IGNORECASE)
#: A whole-response markdown fence, e.g. ```text ... ```
_FENCED = re.compile(r"\A```[a-zA-Z]*\n(.*?)\n?```\Z", re.DOTALL)


def clean_model_output(text: str) -> str:
    """Strip artefacts local models add around the text the user asked for.

    Local models are much less consistent than hosted ones about returning bare
    prose. Two artefacts show up often enough to handle here rather than in
    every prompt: chain-of-thought blocks from reasoning models, and a markdown
    fence wrapped around the whole answer.

    Only whole-response wrappers are removed. Markdown *inside* the text is left
    alone, because the user may legitimately have asked for bullet points.
    """
    cleaned = _THINK_BLOCK.sub("", text)
    cleaned = _ORPHAN_THINK_CLOSE.sub("", cleaned)
    cleaned = _UNCLOSED_THINK.sub("", cleaned)
    cleaned = cleaned.strip()

    fenced = _FENCED.match(cleaned)
    if fenced:
        cleaned = fenced.group(1).strip()
    return cleaned


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
