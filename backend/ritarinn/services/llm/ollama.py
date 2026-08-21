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
from dataclasses import dataclass
from typing import Optional, Union

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
from ritarinn.text.language import looks_like_english, looks_like_reasoning

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
EMPTY_OUTPUT_DETAIL = "Staðbundna líkanið skilaði engum texta."
THINKING_BUDGET_DETAIL = (
    "Líkanið notaði allt svigrúmið í hugsanaferli og skilaði engri samantekt. "
    "Veldu líkan sem ekki „hugsar“ upphátt, eða uppfærðu Ollama svo hægt sé að "
    "slökkva á því."
)
REASONING_LEAK_DETAIL = (
    "Líkanið skilaði hugsanaferli sínu í stað niðurstöðu, líka eftir að beðið var "
    "sérstaklega um að sleppa því. Veldu líkan sem ekki „hugsar“ upphátt, eða "
    "uppfærðu Ollama svo hægt sé að slökkva á hugsanaferlinu."
)
NOT_ICELANDIC_DETAIL = (
    "Líkanið svaraði ekki á íslensku. Veldu líkan sem ræður betur við íslensku."
)

#: Appended to the system prompt on a retry, after the model has already
#: returned its own reasoning or answered in the wrong language once.
#:
#: The first line is the chat-template soft switch that several reasoning model
#: families honour when the runtime's own ``think`` flag does not reach them —
#: an older Ollama drops the flag, and a model whose template hardcodes the
#: opening tag ignores it. The rest restates the two requirements in Icelandic,
#: which is also the fix when the first attempt was simply in English.
#:
#: This is not model-specific configuration: it is sent only after this
#: particular model has demonstrated the problem, and a model that does not
#: recognise the switch is never sent it.
NO_THINKING_NUDGE = """\
/no_think

Svaraðu strax á íslensku og eingöngu á íslensku.
Ekki skrifa hugsanaferli, undirbúning, greiningu á verkefninu né skýringar á \
því hvað þú ætlar að gera. Skrifaðu aðeins lokatextann sjálfan."""


@dataclass(frozen=True)
class _Answer:
    """A usable response: Icelandic text the user asked for."""

    text: str
    truncated: bool


@dataclass(frozen=True)
class _NoAnswer:
    """A response that is not the text the user asked for.

    ``kind`` is for the log, ``detail`` is the Icelandic sentence shown to the
    user if a retry does not rescue the request.
    """

    kind: str
    detail: str


_Outcome = Union[_Answer, _NoAnswer]


class OllamaProvider(LocalLLMProvider):
    """Talks to a local Ollama instance over loopback."""

    name = PROVIDER_NAME

    def __init__(self, settings: Settings, client: Optional[httpx.Client] = None) -> None:
        self._settings = settings
        self._client = client
        # Models that have already returned reasoning, or the wrong language,
        # at least once. A long document is many generations, and paying the
        # retry on every one of them would double the wait on exactly the slow
        # hardware this is meant to stay usable on. Remembered per model name,
        # so choosing a different model starts clean.
        self._needs_nudge: set[str] = set()

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

        A response that is not an Icelandic answer — a chain of thought, or an
        answer in English — is retried once with the thinking soft switch and an
        explicit language instruction. The retry costs a second local
        generation, which on a CPU is not free; it is worth it because the
        alternative is pasting a model's private reasoning into the user's
        document, which is the worse outcome by a wide margin. A model that has
        needed the nudge once gets it immediately from then on, so a long
        document does not pay for the discovery on every chunk.
        """
        if not self._settings.ollama_enabled:
            raise ProviderUnavailableError(PROVIDER_NAME, DISABLED_DETAIL)
        if not request.model:
            raise ProviderUnavailableError(PROVIDER_NAME, NO_MODEL_DETAIL)

        started = time.perf_counter()

        # A model that has already misbehaved once is nudged from the start.
        nudged = request.model in self._needs_nudge
        outcome = self._attempt(request, nudge=NO_THINKING_NUDGE if nudged else None)

        if isinstance(outcome, _NoAnswer) and not nudged:
            logger.info(
                "model returned %s instead of an answer; retrying with thinking suppressed",
                outcome.kind,
            )
            self._needs_nudge.add(request.model)
            outcome = self._attempt(request, nudge=NO_THINKING_NUDGE)

        if isinstance(outcome, _NoAnswer):
            # Either the nudge did not help, or this model was already known to
            # need it and still failed. There is nothing further to try, and no
            # version of this feature puts a model's reasoning in a document.
            logger.warning("generation gave up | reason=%s", outcome.kind)
            raise ProviderUnavailableError(PROVIDER_NAME, outcome.detail)

        elapsed_ms = (time.perf_counter() - started) * 1000
        # Counts and timings only; never the prompt or the output.
        logger.info(
            "generation completed | model=%s | chars=%d | %.0f ms",
            request.model,
            len(outcome.text),
            elapsed_ms,
        )
        return GenerationResult(
            text=outcome.text,
            model=request.model,
            elapsed_ms=elapsed_ms,
            truncated=outcome.truncated,
        )

    # -- one round trip -------------------------------------------------------

    def _attempt(self, request: GenerationRequest, nudge: Optional[str]) -> _Outcome:
        """Send one chat request and judge what came back."""
        system_prompt = request.system_prompt
        if nudge:
            system_prompt = f"{system_prompt}\n\n{nudge}"

        payload = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": system_prompt},
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

        body = self._post_chat(payload)
        message = body.get("message") or {}
        # A runtime that understands thinking returns it in its own field, and
        # it is never part of the answer. Only its presence is of interest: it
        # says the model reasoned, which explains an otherwise empty response.
        thought = str(message.get("thinking") or "").strip()
        text = clean_model_output(str(message.get("content", "")))
        stopped_at_cap = body.get("done_reason") == "length"

        return _judge(text, thought=thought, stopped_at_cap=stopped_at_cap)

    def _post_chat(self, payload: dict) -> dict:
        """POST to the local chat endpoint and return the decoded body."""
        url = self._require_local_endpoint() + "/api/chat"
        response = self._post(url, payload)

        if response.status_code == 400 and "think" in response.text.lower():
            # Some runtime versions reject the thinking flag outright for a
            # model that has no thinking capability, rather than ignoring it.
            # The flag is an optimisation, not a requirement — the response
            # cleaning handles a model that thinks anyway — so drop it and go on.
            logger.info("runtime rejected the thinking flag; resending without it")
            payload = {key: value for key, value in payload.items() if key != "think"}
            response = self._post(url, payload)

        if response.status_code == 404:
            raise ProviderUnavailableError(
                PROVIDER_NAME, MODEL_MISSING_DETAIL.format(model=payload.get("model"))
            )
        if response.status_code >= 400:
            # Ollama's error body is developer-facing; it is logged, not shown.
            logger.warning("Ollama returned HTTP %d for a generation request", response.status_code)
            raise ProviderUnavailableError(
                PROVIDER_NAME, "Staðbundna líkanið skilaði villu. Sjá annál bakendans."
            )
        return response.json()

    def _post(self, url: str, payload: dict) -> httpx.Response:
        try:
            if self._client is not None:
                return self._client.post(
                    url, json=payload, timeout=self._settings.llm_timeout_seconds
                )
            with self._new_client(self._settings.llm_timeout_seconds) as client:
                return client.post(url, json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(
                PROVIDER_NAME,
                "Líkanið svaraði ekki í tæka tíð. Prófaðu styttri texta eða minna líkan.",
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(PROVIDER_NAME, UNREACHABLE_DETAIL) from exc


def _judge(text: str, thought: str, stopped_at_cap: bool) -> _Outcome:
    """Decide whether cleaned model output is the answer the user asked for.

    Four ways a local model fails to answer, each needing a different sentence
    to the user, because each has a different fix.
    """
    if not text:
        if stopped_at_cap or thought:
            # The model spent its whole output budget reasoning and never
            # reached an answer — a different problem for the user than a model
            # that simply returned nothing, and one they can act on.
            return _NoAnswer("only-reasoning", THINKING_BUDGET_DETAIL)
        return _NoAnswer("empty", EMPTY_OUTPUT_DETAIL)

    if looks_like_reasoning(text):
        # A chain of thought with no tag around it at all. This is what happens
        # when the chat template supplies the opening tag, so the model never
        # generates one, and the output cap arrives before the closing tag.
        # Nothing in the text marks it as reasoning except how it reads.
        return _NoAnswer("reasoning-leak", REASONING_LEAK_DETAIL)

    if looks_like_english(text):
        return _NoAnswer("wrong-language", NOT_ICELANDIC_DETAIL)

    return _Answer(text=text, truncated=stopped_at_cap)


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
