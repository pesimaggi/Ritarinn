"""Samantekt and Á mannamáli — reserved endpoints, not implemented in v0.1.

Both features need a local LLM. Ritarinn will not reach for a hosted model to
fill the gap, so rather than shipping something that appears to work, these
endpoints report the limitation explicitly. The routes exist so the frontend can
discover the state from the API instead of hardcoding it, and so Milestone 2
adds an implementation rather than a new surface.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from ritarinn.models.api import FeatureUnavailableResponse

router = APIRouter()

_NOT_YET = status.HTTP_501_NOT_IMPLEMENTED


def _unavailable(feature: str, detail: str) -> JSONResponse:
    body = FeatureUnavailableResponse(detail=detail, feature=feature, available_in="0.2")
    return JSONResponse(status_code=_NOT_YET, content=body.model_dump(by_alias=True))


@router.post("/summarize", status_code=_NOT_YET, summary="Samantekt (ekki komin)")
def summarize() -> JSONResponse:
    return _unavailable(
        "summarize",
        "Samantekt krefst staðbundins mállíkans og er ekki komin í þessa útgáfu. "
        "Ritarinn sendir aldrei texta í skýjaþjónustu í staðinn.",
    )


@router.post("/simplify", status_code=_NOT_YET, summary="Á mannamáli (ekki komin)")
def simplify() -> JSONResponse:
    return _unavailable(
        "simplify",
        "Einföldun texta krefst staðbundins mállíkans og er ekki komin í þessa "
        "útgáfu. Ritarinn sendir aldrei texta í skýjaþjónustu í staðinn.",
    )
