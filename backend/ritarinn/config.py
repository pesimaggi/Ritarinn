"""Runtime configuration for the Ritarinn backend.

Configuration is read from environment variables prefixed with ``RITARINN_``.
Every network-related setting is validated against a loopback allowlist, so a
misconfiguration cannot quietly turn a local-first install into one that talks
to the network. The checks live here rather than in the server startup path so
that they are cheap to unit-test.
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from typing import Mapping, Sequence
from urllib.parse import urlparse

# Hostnames that resolve to the local machine by definition. Anything else is
# treated as remote, including names that merely look local such as
# "localhost.example.com".
LOOPBACK_HOSTNAMES = frozenset({"localhost", "ip6-localhost", "ip6-loopback"})

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8756
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_ALLOWED_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://[::1]:5173",
)

#: Correction engines used when a request names none. GreynirCorrect only:
#: it is the one engine every installation has.
DEFAULT_CORRECTION_ENGINES = ("greynir",)

#: The Icelandic correction checkpoint Ritarinn is written against. Recorded as
#: a default rather than a constant in the adapter, so it can be replaced from
#: configuration; licence and provenance are in ``THIRD_PARTY_NOTICES.md``.
DEFAULT_BYT5_MODEL_ID = "mideind/yfirlestur-icelandic-correction-byt5"


class ConfigurationError(ValueError):
    """Raised when configuration would violate Ritarinn's local-only guarantee."""


def is_loopback_host(host: str) -> bool:
    """Return True if *host* unambiguously refers to the local machine.

    Hostnames are not resolved through DNS: resolution is attacker-influenced
    and would make the answer depend on the network we are trying not to use.
    Only literal loopback addresses and a fixed set of reserved names pass.
    """
    if not host:
        return False
    host = host.strip().strip("[]").lower()
    if host in LOOPBACK_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _origin_host(origin: str) -> str:
    parsed = urlparse(origin)
    return parsed.hostname or ""


def _env_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(env: Mapping[str, str], name: str, default: int) -> int:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be an integer, got {raw!r}") from exc


def _env_float(env: Mapping[str, str], name: str, default: float) -> float:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(f"{name} must be a number, got {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    """Validated backend settings."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    allowed_origins: Sequence[str] = field(default_factory=lambda: list(DEFAULT_ALLOWED_ORIGINS))

    # Explicit, deliberate opt-out of the loopback bind. Nothing in the shipped
    # scripts sets this; it exists so that a user who genuinely wants LAN access
    # has to say so, in writing, rather than discovering it by accident.
    allow_non_loopback_bind: bool = False

    # Local inference runtime.
    ollama_enabled: bool = True
    ollama_url: str = DEFAULT_OLLAMA_URL
    #: Timeout for status/detection calls, which must stay snappy.
    ollama_timeout_seconds: float = 2.0

    # Name of the local model to use for generative features. Empty means the
    # user has not chosen one, and generative features stay switched off.
    llm_model: str = ""

    #: Timeout for a single generation. Generous, because a local model on a
    #: CPU can legitimately take minutes on a long chunk — a short timeout would
    #: make Ritarinn look broken on exactly the hardware it is meant to support.
    llm_timeout_seconds: float = 300.0

    #: Low by default: these features must preserve meaning, not write prose.
    llm_temperature: float = 0.2

    #: Extra output tokens granted to a model that has been caught reasoning, so
    #: that it can finish thinking *and* write the answer. Not every reasoning
    #: model can be told to stop; one that cannot needs room instead, and a
    #: response cut off mid-thought is the failure this budget prevents.
    #:
    #: Exposed as a setting because the right value is a property of the model
    #: and nothing else can know it. A model that reasons at length on a long
    #: document may need more; raise this before giving up on a model whose
    #: Icelandic you like, and run ``scripts/diagnose_model.py`` to find the
    #: value it actually needs. Costs nothing when unused — an output cap is a
    #: ceiling, not a target — but a large value on slow hardware makes the
    #: generation timeout the binding constraint instead.
    llm_reasoning_headroom: int = 4096

    #: Roughly how much source text to put in one prompt, in characters.
    #: Chosen in characters rather than tokens because tokenisation differs per
    #: model, and Icelandic tokenises worse than English in most vocabularies —
    #: a conservative character budget is more portable than a token estimate.
    llm_context_chars: int = 6000

    # Which correction engines run when a request does not name any. A
    # configuration value rather than a constant, so ByT5 can be switched on
    # without editing application code. Names are validated when the registry
    # is built, so a typo fails at startup rather than on the first request.
    correction_engines: Sequence[str] = field(
        default_factory=lambda: list(DEFAULT_CORRECTION_ENGINES)
    )

    # Optional neural correction engine (ByT5). Off until explicitly installed
    # and enabled; it must never gate first startup.
    byt5_enabled: bool = False

    #: Directory holding the model files. A local path is the reproducible,
    #: offline-after-setup case and is what the provisioning script produces.
    #: Empty means fall back to ``byt5_model_id``, resolved against the local
    #: Hugging Face cache.
    byt5_model_path: str = ""

    #: Model identifier used when no local path is set. Configurable because no
    #: checkpoint should become a permanent architectural dependency.
    #:
    #: There is deliberately no "download it for me" setting: the adapter always
    #: loads with downloads disabled, so neither startup nor a correction request
    #: can reach the network. Fetching weights is ``scripts/install_byt5.py``,
    #: which the user runs on purpose.
    byt5_model_id: str = DEFAULT_BYT5_MODEL_ID

    #: "auto" picks CUDA or Apple Silicon when present and CPU otherwise. An
    #: explicit torch device string ("cpu", "cuda", "cuda:1", "mps") overrides
    #: the detection, because the right answer on a multi-GPU machine is not
    #: something Ritarinn can work out.
    byt5_device: str = "auto"

    #: Sentences longer than this are passed through uncorrected. A byte-level
    #: seq2seq model costs time proportional to characters, not words, so one
    #: pathological line should not stall a whole document.
    byt5_max_sentence_chars: int = 2000

    #: Output cap for one sentence, in bytes. ByT5 emits bytes, so this is a
    #: character budget in effect; it is a multiple of the input length so a
    #: long sentence is not truncated mid-word.
    byt5_max_output_ratio: float = 1.5

    log_level: str = "INFO"
    max_text_chars: int = 100_000

    def __post_init__(self) -> None:
        self.validate()

    # -- validation -----------------------------------------------------------

    def validate(self) -> None:
        if not self.allow_non_loopback_bind and not is_loopback_host(self.host):
            raise ConfigurationError(
                f"Refusing to bind to non-loopback address {self.host!r}. "
                "Ritarinn listens on 127.0.0.1 by default; set "
                "RITARINN_ALLOW_NON_LOOPBACK=1 only if you understand that this "
                "exposes your documents to other machines on your network."
            )
        if not 1 <= self.port <= 65535:
            raise ConfigurationError(f"Port out of range: {self.port}")

        if "*" in self.allowed_origins:
            raise ConfigurationError("Wildcard CORS origins are not permitted.")
        for origin in self.allowed_origins:
            if not is_loopback_host(_origin_host(origin)):
                raise ConfigurationError(
                    f"CORS origin {origin!r} is not a loopback origin. Ritarinn "
                    "only accepts requests from browsers running on this machine."
                )

        # The Ollama URL has no escape hatch: a remote inference endpoint would
        # send user text off the machine, which v0.1 does not support at all.
        if not is_loopback_host(urlparse(self.ollama_url).hostname or ""):
            raise ConfigurationError(
                f"Ollama URL {self.ollama_url!r} is not on loopback. Ritarinn only "
                "supports a locally running inference runtime."
            )

    # -- derived properties ---------------------------------------------------

    @property
    def binds_to_loopback_only(self) -> bool:
        return is_loopback_host(self.host)

    @property
    def has_remote_provider_configured(self) -> bool:
        """True if any configured endpoint could send text off this machine.

        v0.1 has no remote provider implementation at all, so this is always
        False. It exists so the privacy endpoint reports a computed fact rather
        than a hardcoded reassurance, and so it starts returning the truth the
        moment a remote provider is ever added.
        """
        endpoints = [self.ollama_url] if self.ollama_enabled else []
        return any(not is_loopback_host(urlparse(url).hostname or "") for url in endpoints)


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Build :class:`Settings` from the environment (or an explicit mapping)."""
    env: Mapping[str, str] = os.environ if environ is None else environ

    origins_raw = env.get("RITARINN_ALLOWED_ORIGINS", "")
    origins = (
        [o.strip() for o in origins_raw.split(",") if o.strip()]
        if origins_raw.strip()
        else list(DEFAULT_ALLOWED_ORIGINS)
    )

    engines_raw = env.get("RITARINN_CORRECTION_ENGINES", "")
    engines = (
        [name.strip() for name in engines_raw.split(",") if name.strip()]
        if engines_raw.strip()
        else list(DEFAULT_CORRECTION_ENGINES)
    )
    return Settings(
        host=env.get("RITARINN_HOST", DEFAULT_HOST),
        port=_env_int(env, "RITARINN_PORT", DEFAULT_PORT),
        allowed_origins=origins,
        allow_non_loopback_bind=_env_bool(env, "RITARINN_ALLOW_NON_LOOPBACK", False),
        ollama_enabled=_env_bool(env, "RITARINN_OLLAMA_ENABLED", True),
        ollama_url=env.get("RITARINN_OLLAMA_URL", DEFAULT_OLLAMA_URL),
        ollama_timeout_seconds=_env_float(env, "RITARINN_OLLAMA_TIMEOUT", 2.0),
        llm_model=env.get("RITARINN_LLM_MODEL", ""),
        llm_timeout_seconds=_env_float(env, "RITARINN_LLM_TIMEOUT", 300.0),
        llm_temperature=_env_float(env, "RITARINN_LLM_TEMPERATURE", 0.2),
        llm_reasoning_headroom=_env_int(env, "RITARINN_LLM_REASONING_HEADROOM", 4096),
        llm_context_chars=_env_int(env, "RITARINN_LLM_CONTEXT_CHARS", 6000),
        correction_engines=engines,
        byt5_enabled=_env_bool(env, "RITARINN_BYT5_ENABLED", False),
        byt5_model_path=env.get("RITARINN_BYT5_MODEL_PATH", ""),
        byt5_model_id=env.get("RITARINN_BYT5_MODEL_ID", DEFAULT_BYT5_MODEL_ID),
        byt5_device=env.get("RITARINN_BYT5_DEVICE", "auto"),
        byt5_max_sentence_chars=_env_int(env, "RITARINN_BYT5_MAX_SENTENCE_CHARS", 2000),
        byt5_max_output_ratio=_env_float(env, "RITARINN_BYT5_MAX_OUTPUT_RATIO", 1.5),
        log_level=env.get("RITARINN_LOG_LEVEL", "INFO"),
        max_text_chars=_env_int(env, "RITARINN_MAX_TEXT_CHARS", 100_000),
    )
