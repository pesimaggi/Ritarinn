"""Persónuvernd — the machine-checkable basis for the "Staðbundið" indicator.

The UI must only claim that text stays on the machine when that is actually
true. So this endpoint reports computed facts about the running configuration
rather than a constant, and ``local_only`` is a conjunction of those facts. If a
future version ever adds a remote provider, this flips to False on its own.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ritarinn.api.deps import AppState, get_state
from ritarinn.models.api import PrivacyStatusResponse

router = APIRouter()

LOCAL_SUMMARY = (
    "Textinn er unninn á þessari tölvu. Engin textagögn eru send í skýjaþjónustu."
)
NON_LOCAL_SUMMARY = (
    "Uppsetningin er ekki alfarið staðbundin. Farðu yfir stillingar áður en þú "
    "vinnur með viðkvæm gögn."
)


@router.get(
    "/privacy/status",
    response_model=PrivacyStatusResponse,
    summary="Er vinnslan alfarið staðbundin?",
)
def privacy_status(state: AppState = Depends(get_state)) -> PrivacyStatusResponse:
    settings = state.settings

    # Every endpoint the backend is permitted to contact. Settings.validate()
    # has already refused to start if any of these is not on loopback; listing
    # them here lets the user see the claim rather than take it on trust.
    outbound = [settings.ollama_url] if settings.ollama_enabled else []

    wildcard_cors = "*" in settings.allowed_origins
    remote_configured = settings.has_remote_provider_configured

    local_only = (
        settings.binds_to_loopback_only
        and not wildcard_cors
        and not remote_configured
        # Ritarinn has no telemetry to disable — there is no code that sends it.
        and True
    )

    return PrivacyStatusResponse(
        local_only=local_only,
        bind_host=settings.host,
        binds_to_loopback_only=settings.binds_to_loopback_only,
        allowed_origins=list(settings.allowed_origins),
        wildcard_cors=wildcard_cors,
        remote_provider_configured=remote_configured,
        telemetry_enabled=False,
        outbound_endpoints=outbound,
        summary=LOCAL_SUMMARY if local_only else NON_LOCAL_SUMMARY,
    )
