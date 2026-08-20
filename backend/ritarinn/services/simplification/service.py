"""Á mannamáli — plain-language rewriting with a local model.

Rewriting differs from summarizing in one way that matters for the mechanics:
the output is roughly as long as the input, and it has to keep the source's
structure. So a long document is rewritten chunk by chunk and the results are
joined in order, rather than being combined by a second model pass — a combine
step would be free to drop material, which is exactly what a rewrite must not
do.

The author's text is never replaced automatically. The rewrite is offered for
comparison, and only an explicit acceptance changes the document.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from ritarinn.config import Settings
from ritarinn.services.correction.registry import EngineRegistry
from ritarinn.services.generation.base import GenerationOutcome
from ritarinn.services.generation.postprocess import proofread_generated_text
from ritarinn.services.generation.prompts import SIMPLIFY_SYSTEM, simplify_user_prompt
from ritarinn.services.llm.base import (
    GenerationRequest,
    LocalLLMProvider,
    ProviderUnavailableError,
)
from ritarinn.text.chunking import chunk_document

logger = logging.getLogger(__name__)

#: Output tokens allowed per source character. A plain-language rewrite is
#: usually a little shorter than its source, but splitting long sentences can
#: make it longer, so the cap allows growth rather than truncating mid-thought.
_TOKENS_PER_CHAR = 0.75
_MIN_TOKENS = 256
_MAX_TOKENS = 4096


@dataclass(frozen=True)
class SimplifyOptions:
    audience: str = "general"
    style: str = "plain"
    #: Run the result through GreynirCorrect and report issues (never apply).
    proofread: bool = True


class SimplificationService:
    def __init__(
        self,
        settings: Settings,
        provider: LocalLLMProvider,
        engines: EngineRegistry,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._engines = engines

    def simplify(self, text: str, options: SimplifyOptions) -> GenerationOutcome:
        model = self._settings.llm_model
        if not model:
            raise ProviderUnavailableError(
                self._provider.name,
                "Ekkert staðbundið líkan er valið. Veldu líkan í stillingum.",
            )

        started = time.perf_counter()
        chunks = chunk_document(text, self._settings.llm_context_chars)
        if not chunks:
            raise ValueError("empty text")

        rewritten: list[str] = []
        truncated = False
        for chunk in chunks:
            result = self._provider.generate(
                GenerationRequest(
                    system_prompt=SIMPLIFY_SYSTEM,
                    user_prompt=simplify_user_prompt(
                        chunk.text, options.audience, options.style
                    ),
                    model=model,
                    temperature=self._settings.llm_temperature,
                    max_tokens=_token_budget(len(chunk.text)),
                )
            )
            rewritten.append(result.text.strip())
            truncated = truncated or result.truncated

        # Paragraph breaks between chunks: the chunker splits on structural
        # boundaries, so joining with a blank line restores the document's shape.
        simplified = "\n\n".join(part for part in rewritten if part)

        issues = (
            proofread_generated_text(self._engines, simplified) if options.proofread else ()
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "simplify completed | chunks=%d | chars=%d | %.0f ms",
            len(chunks),
            len(simplified),
            elapsed_ms,
        )
        return GenerationOutcome(
            text=simplified,
            model=model,
            elapsed_ms=elapsed_ms,
            chunks=len(chunks),
            passes=1,
            issues=issues,
            truncated=truncated,
        )


def _token_budget(source_chars: int) -> int:
    return max(_MIN_TOKENS, min(_MAX_TOKENS, int(source_chars * _TOKENS_PER_CHAR)))
