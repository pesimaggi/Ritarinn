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

    # A client that asked for a specific engine gets told when it is not
    # installed. A default selection that happens to include an optional engine
    # must not take proofreading down with it, so an unavailable one is skipped
    # and the response reports which engines actually ran.
    named_by_client = bool(payload.engines)

    issues: list[WritingIssue] = []
    stats: dict[str, float | int | str] = {}
    ran: list[str] = []
    unavailable: list[EngineUnavailableError] = []
    for engine in engines:
        try:
            outcome = engine.analyze(request)
        except EngineUnavailableError as exc:
            if named_by_client:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=exc.detail,
                ) from exc
            unavailable.append(exc)
            # A marker, not the explanation. The explanation names a filesystem
            # path or an install command, and /api/models/status is where it
            # belongs; this response is about the document.
            stats[f"{engine.name}.skipped"] = "unavailable"
            continue
        ran.append(engine.name)
        issues.extend(outcome.issues)
        for key, value in outcome.stats.items():
            stats[f"{engine.name}.{key}"] = value

    if not ran and unavailable:
        # Nothing could run at all. Reporting an empty result would look like a
        # document with no problems in it, which is a different claim entirely.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=unavailable[0].detail,
        ) from unavailable[0]

    # Ordering by position lets the sidebar follow the document, and makes the
    # response stable across engines for a given input. ``source`` breaks ties
    # so that two engines reporting the same span come back in a fixed order
    # rather than in whichever order they happened to be registered.
    issues.sort(key=lambda issue: (issue.start_char, issue.end_char, issue.source))

    # Counts and timings only — never the text itself. See docs/privacy.md.
    logger.info(
        "proofread completed | engines=%s | chars=%d | issues=%d",
        ",".join(ran),
        len(payload.text),
        len(issues),
    )

    return ProofreadResponse(issues=issues, engines=ran, stats=stats)
