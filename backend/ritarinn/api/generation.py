"""Samantekt and Á mannamáli — generation with a local model.

Both endpoints run entirely on this machine, through a local inference runtime
listening on loopback. If no local model is configured they report that and
stop; there is no hosted fallback, and adding one would break the guarantee the
rest of the application is built around.

Neither endpoint modifies the user's document. They return a proposal, and the
browser shows it beside the original for the author to accept, copy or discard.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ritarinn.api.deps import AppState, get_state
from ritarinn.models.api import (
    GenerationResponse,
    SimplifyRequest,
    SummarizeRequest,
)
from ritarinn.services.generation.base import GenerationOutcome
from ritarinn.services.llm.base import FeatureNotAvailableError, ProviderUnavailableError
from ritarinn.services.simplification import SimplificationService, SimplifyOptions
from ritarinn.services.summarization import SummarizationService, SummaryOptions

logger = logging.getLogger(__name__)

router = APIRouter()


def _check_text(text: str, state: AppState) -> None:
    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enginn texti til að vinna með.",
        )
    if len(text) > state.settings.max_text_chars:
        raise HTTPException(
            status_code=413,  # Content Too Large
            detail=(
                f"Textinn er of langur ({len(text)} stafir). "
                f"Hámark er {state.settings.max_text_chars} stafir."
            ),
        )


def _to_response(outcome: GenerationOutcome) -> GenerationResponse:
    return GenerationResponse(
        text=outcome.text,
        model=outcome.model,
        chunks=outcome.chunks,
        passes=outcome.passes,
        elapsed_ms=round(outcome.elapsed_ms, 1),
        issues=list(outcome.issues),
        truncated=outcome.truncated,
    )


def _unavailable(exc: Exception) -> HTTPException:
    """Map a provider failure onto a status the UI can act on.

    503 rather than 500: the request was fine, the local runtime is not ready.
    The detail is Icelandic and user-facing, because it tells the user what to
    do — start Ollama, pick a model, install one.
    """
    detail = getattr(exc, "detail", None) or str(exc)
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


@router.post("/summarize", response_model=GenerationResponse, summary="Samantekt")
def summarize(
    payload: SummarizeRequest, state: AppState = Depends(get_state)
) -> GenerationResponse:
    _check_text(payload.text, state)
    service = SummarizationService(state.settings, state.llm, state.engines)
    try:
        outcome = service.summarize(
            payload.text,
            SummaryOptions(
                length=payload.length, form=payload.form, proofread=payload.proofread
            ),
        )
    except (ProviderUnavailableError, FeatureNotAvailableError) as exc:
        raise _unavailable(exc) from exc
    return _to_response(outcome)


@router.post("/simplify", response_model=GenerationResponse, summary="Á mannamáli")
def simplify(
    payload: SimplifyRequest, state: AppState = Depends(get_state)
) -> GenerationResponse:
    _check_text(payload.text, state)
    service = SimplificationService(state.settings, state.llm, state.engines)
    try:
        outcome = service.simplify(
            payload.text,
            SimplifyOptions(
                audience=payload.audience, style=payload.style, proofread=payload.proofread
            ),
        )
    except (ProviderUnavailableError, FeatureNotAvailableError) as exc:
        raise _unavailable(exc) from exc
    return _to_response(outcome)
