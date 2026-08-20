"""What language technology is installed and ready.

Feeds the first-run panel described in the product brief: which correction
engines work, whether a local inference runtime was found, and which model (if
any) is selected. Nothing here downloads anything.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ritarinn.api.deps import AppState, get_state
from ritarinn.models.api import (
    EngineStatusModel,
    ModelInfoModel,
    ModelsStatusResponse,
    ProviderStatusModel,
)

router = APIRouter()


@router.get(
    "/models/status",
    response_model=ModelsStatusResponse,
    summary="Staða málgreiningar og staðbundinna líkana",
)
def models_status(state: AppState = Depends(get_state)) -> ModelsStatusResponse:
    engines = [
        EngineStatusModel(
            name=s.name,
            label=s.label,
            available=s.available,
            version=s.version,
            detail=s.detail,
            local_only=s.local_only,
            provenance=s.provenance,
        )
        for s in state.engines.statuses()
    ]

    provider = state.llm.status()
    providers = [
        ProviderStatusModel(
            name=provider.name,
            label=provider.label,
            available=provider.available,
            endpoint=provider.endpoint,
            version=provider.version,
            models=[
                ModelInfoModel(
                    name=m.name,
                    size_bytes=m.size_bytes,
                    family=m.family,
                    details=m.details,
                )
                for m in provider.models
            ],
            selected_model=provider.selected_model,
            detail=provider.detail,
            local_only=provider.local_only,
            can_generate=provider.can_generate,
        )
    ]

    return ModelsStatusResponse(
        correction_engines=engines,
        llm_providers=providers,
        proofreading_ready=any(e.available for e in engines),
        # True only when a runtime is reachable *and* a model has been chosen.
        # A reachable Ollama with no model selected cannot generate anything.
        generation_ready=provider.can_generate,
    )
