"""Liveness and readiness."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ritarinn import __version__
from ritarinn.api.deps import AppState, get_state
from ritarinn.models.api import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Er bakendinn í lagi?")
def health(state: AppState = Depends(get_state)) -> HealthResponse:
    ready = any(status.available for status in state.engines.statuses())
    return HealthResponse(status="ok", version=__version__, proofreading_ready=ready)
