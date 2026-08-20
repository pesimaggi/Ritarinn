"""Entry point: ``python -m ritarinn``.

Reads configuration, refuses to start on a configuration that would break the
local-only guarantee, and hands off to uvicorn.
"""

from __future__ import annotations

import sys

import uvicorn

from ritarinn.config import ConfigurationError, load_settings


def main() -> int:
    try:
        settings = load_settings()
    except ConfigurationError as exc:
        print(f"Ritarinn: {exc}", file=sys.stderr)
        return 2

    uvicorn.run(
        "ritarinn.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
        # Reload is a development convenience and watches the filesystem; it is
        # left to the caller to enable via the dev script.
        reload=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
