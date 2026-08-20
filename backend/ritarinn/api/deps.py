"""Shared application state.

The engine registry and LLM provider are built once at startup and stashed on
the FastAPI app, so routes never construct them per-request (GreynirCorrect's
load is expensive) and tests can substitute their own.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request

from ritarinn.config import Settings
from ritarinn.services.correction.registry import EngineRegistry
from ritarinn.services.llm.base import LocalLLMProvider


@dataclass
class AppState:
    settings: Settings
    engines: EngineRegistry
    llm: LocalLLMProvider


def get_state(request: Request) -> AppState:
    return request.app.state.ritarinn
