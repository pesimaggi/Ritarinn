"""GreynirCorrect-backed proofreading.

GreynirCorrect (Miðeind, MIT) tokenises Icelandic text, corrects spelling at the
token level, parses each sentence with GreynirEngine, and reports annotations
covering token spans. This module's job is to turn those sentence-relative token
spans into character offsets into the original document, without ever altering
the document.

Two properties of GreynirCorrect make that possible and are relied on here:

1. every token keeps its verbatim source text in ``token.original``, including
   the whitespace that preceded it, so concatenating them reproduces the input;
2. annotations index into the sentence's own token list.

Property 1 holds exactly, except that trailing whitespace at the very end of the
document is dropped. That cannot shift any earlier offset, so it is harmless —
and ``tests/backend/test_offsets.py`` asserts the prefix invariant that makes
this safe.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Iterable, Optional

from ritarinn.models.issue import WritingIssue
from ritarinn.services.correction.base import (
    CorrectionEngine,
    CorrectionOutcome,
    CorrectionRequest,
    EngineStatus,
    EngineUnavailableError,
)
from ritarinn.services.correction.categories import classify, strip_warning_suffix
from ritarinn.text.offsets import Utf16OffsetMap, trim_span

logger = logging.getLogger(__name__)

ENGINE_NAME = "greynir"
PROVENANCE = "GreynirCorrect eftir Miðeind ehf. (MIT), byggt á BÍN og GreynirEngine"


class GreynirCorrectEngine(CorrectionEngine):
    """Deterministic Icelandic spelling and grammar analysis."""

    name = ENGINE_NAME

    def __init__(self) -> None:
        self._api = None
        self._version: Optional[str] = None
        self._load_error: Optional[str] = None
        # GreynirCorrect's parser holds mutable state across a parse, so calls
        # are serialised. Proofreading a page of text takes well under a second,
        # and a single-user local application has no concurrency to speak of.
        self._lock = threading.Lock()

    # -- lifecycle ------------------------------------------------------------

    def warm_up(self) -> None:
        """Load GreynirCorrect and its BÍN data once, at startup.

        The first call builds sizeable in-memory structures; doing it here keeps
        the user's first proofread from paying that cost.
        """
        try:
            self._ensure_loaded()
        except EngineUnavailableError:
            # Already recorded in ``self._load_error`` and reported by status().
            logger.warning("GreynirCorrect is not available; proofreading is disabled")

    def _ensure_loaded(self) -> object:
        if self._api is not None:
            return self._api
        with self._lock:
            if self._api is not None:
                return self._api
            try:
                import reynir_correct

                started = time.perf_counter()
                self._api = reynir_correct.GreynirCorrectAPI.from_options()
                self._version = getattr(reynir_correct, "__version__", None)
                logger.info(
                    "GreynirCorrect %s loaded in %.0f ms",
                    self._version or "?",
                    (time.perf_counter() - started) * 1000,
                )
            except Exception as exc:  # pragma: no cover - depends on install state
                self._load_error = str(exc)
                raise EngineUnavailableError(
                    ENGINE_NAME,
                    "Ekki tókst að hlaða GreynirCorrect. Keyrðu uppsetninguna aftur.",
                ) from exc
        return self._api

    def status(self) -> EngineStatus:
        if self._api is not None:
            return EngineStatus(
                name=ENGINE_NAME,
                label="GreynirCorrect",
                available=True,
                version=self._version,
                local_only=True,
                provenance=PROVENANCE,
            )
        # Not loaded yet: report installability without paying the load cost.
        try:
            import importlib.metadata as metadata

            version = metadata.version("reynir-correct")
        except Exception:
            return EngineStatus(
                name=ENGINE_NAME,
                label="GreynirCorrect",
                available=False,
                detail=self._load_error or "GreynirCorrect er ekki uppsett.",
                local_only=True,
                provenance=PROVENANCE,
            )
        return EngineStatus(
            name=ENGINE_NAME,
            label="GreynirCorrect",
            available=self._load_error is None,
            version=version,
            detail=self._load_error,
            local_only=True,
            provenance=PROVENANCE,
        )

    # -- analysis -------------------------------------------------------------

    def analyze(self, request: CorrectionRequest) -> CorrectionOutcome:
        api = self._ensure_loaded()
        text = request.text
        if not text.strip():
            return CorrectionOutcome(issues=[], stats={"sentences": 0})

        started = time.perf_counter()
        with self._lock:
            result = api.correct(text, ignore_rules=frozenset(request.ignore_codes) or None)  # type: ignore[attr-defined]

        offsets = Utf16OffsetMap(text)
        issues = list(self._to_issues(result, text, offsets))
        elapsed_ms = (time.perf_counter() - started) * 1000

        stats: dict[str, float | int | str] = {
            "sentences": len(result.sentences),
            "issues": len(issues),
            "elapsed_ms": round(elapsed_ms, 1),
        }
        if result.parse_result_stats is not None:
            stats["parsed_sentences"] = result.parse_result_stats.num_parsed
            stats["tokens"] = result.parse_result_stats.num_tokens
        return CorrectionOutcome(issues=issues, stats=stats)

    def _to_issues(
        self, result: object, text: str, offsets: Utf16OffsetMap
    ) -> Iterable[WritingIssue]:
        """Convert GreynirCorrect annotations into normalized issues."""
        cursor = 0  # Code-point offset of the next token's source text.
        counter = 0

        for sentence in result.sentences:  # type: ignore[attr-defined]
            # Character span of every token in this sentence, in document
            # coordinates. Built before reading annotations because annotation
            # indices refer into this same token list.
            token_starts: list[int] = []
            token_ends: list[int] = []
            for token in sentence.tokens:
                source = token.original if token.original is not None else (token.txt or "")
                token_starts.append(cursor)
                cursor += len(source)
                token_ends.append(cursor)

            for annotation in sentence.annotations or []:
                issue = self._to_issue(
                    annotation, text, offsets, token_starts, token_ends, counter
                )
                if issue is not None:
                    counter += 1
                    yield issue

    def _to_issue(
        self,
        annotation: object,
        text: str,
        offsets: Utf16OffsetMap,
        token_starts: list[int],
        token_ends: list[int],
        index: int,
    ) -> Optional[WritingIssue]:
        start_token = annotation.start  # type: ignore[attr-defined]
        end_token = annotation.end  # type: ignore[attr-defined]
        if not token_starts or start_token >= len(token_starts):
            # Defensive: an annotation outside the token list cannot be anchored
            # in the document, and a wrongly-anchored underline is worse than a
            # missing one.
            logger.debug("Dropping annotation with out-of-range token span")
            return None
        end_token = min(end_token, len(token_ends) - 1)

        start = token_starts[start_token]
        end = token_ends[end_token]
        # A token's source text carries the whitespace in front of it, so the
        # raw span would underline the preceding space or paragraph break.
        start, end = trim_span(text, start, end)

        code_raw: str = annotation.code  # type: ignore[attr-defined]
        bare_code, is_warning = strip_warning_suffix(code_raw)
        family = classify(code_raw)

        original = text[start:end]
        suggestion = _clean_suggestion(getattr(annotation, "suggest", None))
        alternatives = [
            cleaned
            for cleaned in (
                _clean_suggestion(item) for item in (getattr(annotation, "suggestlist", None) or [])
            )
            if cleaned and cleaned != suggestion
        ]

        return WritingIssue(
            id=f"{ENGINE_NAME}-{index}-{start}-{end}-{bare_code}",
            source="greynir",
            category=family.category,
            code=code_raw,
            family=family.label,
            start_char=offsets.to_utf16(start),
            end_char=offsets.to_utf16(end),
            scope=family.scope,
            original=original,
            replacement=suggestion,
            alternatives=alternatives,
            title=annotation.text,  # type: ignore[attr-defined]
            explanation=getattr(annotation, "detail", None),
            severity="warning" if is_warning else "error",
            references=list(getattr(annotation, "references", None) or []),
            # GreynirCorrect reports no numeric confidence, so none is invented.
            confidence=None,
        )


def _clean_suggestion(suggestion: Optional[str]) -> Optional[str]:
    """Render a GreynirCorrect suggestion as it should appear in the document.

    Suggestions come back as token text joined by single spaces, so they need
    detokenising before they can replace a span — otherwise accepting a
    correction would insert a space before a comma.
    """
    if not suggestion:
        return None
    try:
        from reynir_correct import correct_spaces

        return correct_spaces(suggestion)
    except Exception:  # pragma: no cover - only if upstream API changes
        return suggestion
