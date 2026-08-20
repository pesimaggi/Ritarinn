"""Samantekt — summarization with a local model.

A local model has a bounded context and a document does not, so long text is
summarised hierarchically: divide on structural boundaries, summarise each
part, then combine the parts into one summary. Short documents skip straight to
a single pass, because an extra round trip on a CPU-bound model is a real cost
and buys nothing.

The source document is never modified. Summaries are produced alongside it and
handed back for the user to accept, copy or discard.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from ritarinn.config import Settings
from ritarinn.services.correction.registry import EngineRegistry
from ritarinn.services.generation.base import GenerationOutcome
from ritarinn.services.generation.postprocess import proofread_generated_text
from ritarinn.services.generation.prompts import (
    LENGTH_TOKEN_BUDGET,
    SUMMARY_SYSTEM,
    chunk_summary_user_prompt,
    combine_summaries_user_prompt,
    summary_user_prompt,
)
from ritarinn.services.llm.base import (
    GenerationRequest,
    LocalLLMProvider,
    ProviderUnavailableError,
)
from ritarinn.text.chunking import chunk_document

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SummaryOptions:
    length: str = "medium"
    form: str = "prose"
    #: Run the result through GreynirCorrect and report issues (never apply).
    proofread: bool = True


class SummarizationService:
    def __init__(
        self,
        settings: Settings,
        provider: LocalLLMProvider,
        engines: EngineRegistry,
    ) -> None:
        self._settings = settings
        self._provider = provider
        self._engines = engines

    def summarize(self, text: str, options: SummaryOptions) -> GenerationOutcome:
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

        token_budget = LENGTH_TOKEN_BUDGET[options.length]

        truncated = False

        if len(chunks) == 1:
            summary, truncated = self._generate(
                summary_user_prompt(chunks[0].text, options.length, options.form),
                model,
                token_budget,
            )
            passes = 1
        else:
            # Each part is summarised on its own terms; the model is told it is
            # seeing a fragment so it does not conclude from partial evidence.
            partials: list[str] = []
            for chunk in chunks:
                # Part summaries feed the combine step, so they can be fuller
                # than the final answer without costing the user anything.
                part, part_truncated = self._generate(
                    chunk_summary_user_prompt(chunk.text, chunk.index + 1, len(chunks)),
                    model,
                    max(token_budget, 400),
                )
                partials.append(part)
                truncated = truncated or part_truncated

            summary, final_truncated = self._generate(
                combine_summaries_user_prompt(partials, options.length, options.form),
                model,
                token_budget,
            )
            truncated = truncated or final_truncated
            passes = 2

        issues = (
            proofread_generated_text(self._engines, summary) if options.proofread else ()
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "summarize completed | chunks=%d | passes=%d | chars=%d | %.0f ms",
            len(chunks),
            passes,
            len(summary),
            elapsed_ms,
        )
        return GenerationOutcome(
            text=summary,
            model=model,
            elapsed_ms=elapsed_ms,
            chunks=len(chunks),
            passes=passes,
            issues=issues,
            truncated=truncated,
        )

    def _generate(self, user_prompt: str, model: str, max_tokens: int) -> tuple[str, bool]:
        result = self._provider.generate(
            GenerationRequest(
                system_prompt=SUMMARY_SYSTEM,
                user_prompt=user_prompt,
                model=model,
                temperature=self._settings.llm_temperature,
                max_tokens=max_tokens,
            )
        )
        return result.text, result.truncated
