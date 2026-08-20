"""FastAPI application factory.

Assembles the routes, restricts CORS to loopback origins, and applies response
headers that keep a browser from loading anything this application did not
serve. Nothing here reaches the network at startup.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ritarinn import __version__
from ritarinn.api import generation, health, models_status, privacy, proofread
from ritarinn.api.deps import AppState
from ritarinn.config import Settings, load_settings
from ritarinn.logging_conf import configure_logging
from ritarinn.services.correction.registry import EngineRegistry
from ritarinn.services.llm.ollama import OllamaProvider

logger = logging.getLogger(__name__)

# The API serves JSON only; it never returns HTML that a browser would execute.
# 'default-src none' plus an explicit connect-src is therefore the whole policy.
# The frontend ships its own, stricter policy for the document itself — see
# frontend/index.html and docs/privacy.md.
CONTENT_SECURITY_POLICY = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds conservative security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        # Turn off browser features the application never uses, so a future bug
        # cannot quietly start using them.
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=(), interest-cohort=()"
        )
        return response


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Build the application. Safe to call repeatedly (tests do)."""
    settings = settings or load_settings()
    configure_logging(settings.log_level)

    registry = EngineRegistry(settings)
    llm = OllamaProvider(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # Loading GreynirCorrect takes a moment; doing it here means the user's
        # first proofread is fast, and a failure is visible in /api/health
        # rather than surfacing as a slow first request.
        registry.warm_up()
        logger.info(
            "Ritarinn %s listening on %s port %d (local only)",
            __version__,
            settings.host,
            settings.port,
        )
        yield

    app = FastAPI(
        title="Ritarinn",
        version=__version__,
        description=(
            "Staðbundinn íslenskur ritaðstoðarmaður. Öll textavinnsla fer fram "
            "á þessari tölvu."
        ),
        lifespan=lifespan,
    )
    app.state.ritarinn = AppState(settings=settings, engines=registry, llm=llm)

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        # Explicit list, never a wildcard: the browser is the only client, and
        # it always runs on this machine.
        allow_origins=list(settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    for module in (health, proofread, models_status, privacy, generation):
        app.include_router(module.router, prefix="/api")

    return app


app = create_app  # Factory, not an instance: uvicorn is given the factory flag.
