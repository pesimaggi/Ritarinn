"""Yfirlestur — the proofreading endpoint.

This is the one endpoint that receives the user's document. It runs the selected
engines locally, returns individual reviewable issues, and never returns a
rewritten document: deciding what to change is the author's job.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ritarinn.api.deps import AppState, get_state
from ritarinn.models.api import ProofreadRequest, ProofreadResponse
from ritarinn.models.issue import WritingIssue
from ritarinn.services.correction.base import CorrectionRequest, EngineUnavailableError
from ritarinn.services.correction.registry import UnknownEngineError

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/proofread", response_model=ProofreadResponse, summary="Lesa yfir texta")
def proofread(
    payload: ProofreadRequest, state: AppState = Depends(get_state)
) -> ProofreadResponse:
    if len(payload.text) > state.settings.max_text_chars:
        raise HTTPException(
            status_code=413,  # Content Too Large
            detail=(
                f"Textinn er of langur ({len(payload.text)} stafir). "
                f"Hámark er {state.settings.max_text_chars} stafir."
            ),
        )

    try:
        engines = state.engines.resolve(payload.engines)
    except UnknownEngineError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Óþekkt leiðréttingarvél: {exc.args[0]!r}. "
            f"Í boði eru: {', '.join(state.engines.names)}.",
        ) from exc

    request = CorrectionRequest(text=payload.text, ignore_codes=frozenset(payload.ignore_codes))

    issues: list[WritingIssue] = []
    stats: dict[str, float | int | str] = {}
    for engine in engines:
        try:
            outcome = engine.analyze(request)
        except EngineUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=exc.detail,
            ) from exc
        issues.extend(outcome.issues)
        for key, value in outcome.stats.items():
            stats[f"{engine.name}.{key}"] = value

    # Ordering by position lets the sidebar follow the document, and makes the
    # response stable across engines for a given input.
    issues.sort(key=lambda issue: (issue.start_char, issue.end_char))

    # Counts and timings only — never the text itself. See docs/privacy.md.
    logger.info(
        "proofread completed | engines=%s | chars=%d | issues=%d",
        ",".join(engine.name for engine in engines),
        len(payload.text),
        len(issues),
    )

    return ProofreadResponse(
        issues=issues,
        engines=[engine.name for engine in engines],
        stats=stats,
    )
