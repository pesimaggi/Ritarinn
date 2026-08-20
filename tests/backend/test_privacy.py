"""Configuration checks that enforce the local-only guarantee.

These are the tests that would fail if someone made Ritarinn quietly stop being
a local-first application: a wildcard CORS policy, a bind on all interfaces, a
remote inference endpoint, telemetry. They assert on configuration rather than
on behaviour, because a privacy property has to hold before any request is
served, not be discovered afterwards.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from fastapi.testclient import TestClient

from ritarinn.config import (
    DEFAULT_ALLOWED_ORIGINS,
    ConfigurationError,
    Settings,
    is_loopback_host,
    load_settings,
)

from _source_scan import strip_comments, url_host

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


# -- defaults -----------------------------------------------------------------


def test_default_bind_address_is_loopback() -> None:
    assert load_settings({}).host == "127.0.0.1"
    assert load_settings({}).binds_to_loopback_only is True


def test_default_cors_origins_are_all_local() -> None:
    settings = load_settings({})
    assert "*" not in settings.allowed_origins
    for origin in settings.allowed_origins:
        assert re.match(r"^http://(127\.0\.0\.1|localhost|\[::1\]):\d+$", origin), origin


def test_default_inference_endpoint_is_loopback() -> None:
    assert load_settings({}).ollama_url.startswith("http://127.0.0.1")


def test_no_remote_provider_is_configured_by_default() -> None:
    assert load_settings({}).has_remote_provider_configured is False


def test_no_model_is_selected_by_default() -> None:
    """Nothing is downloaded or enabled without the user asking."""
    assert load_settings({}).llm_model == ""
    assert load_settings({}).byt5_enabled is False


# -- refusals -----------------------------------------------------------------


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.10", "example.com"])
def test_non_loopback_bind_is_refused(host: str) -> None:
    with pytest.raises(ConfigurationError):
        Settings(host=host)


def test_non_loopback_bind_requires_an_explicit_opt_in() -> None:
    """LAN exposure is possible, but only deliberately."""
    settings = Settings(host="0.0.0.0", allow_non_loopback_bind=True)
    assert settings.binds_to_loopback_only is False


def test_wildcard_cors_is_refused() -> None:
    with pytest.raises(ConfigurationError):
        Settings(allowed_origins=["*"])


@pytest.mark.parametrize(
    "origin",
    ["https://example.com", "http://localhost.example.com:5173", "http://10.0.0.5:5173"],
)
def test_remote_cors_origin_is_refused(origin: str) -> None:
    with pytest.raises(ConfigurationError):
        Settings(allowed_origins=[*DEFAULT_ALLOWED_ORIGINS, origin])


@pytest.mark.parametrize(
    "url",
    ["http://ollama.example.com:11434", "https://api.openai.com", "http://10.0.0.5:11434"],
)
def test_remote_inference_endpoint_is_refused(url: str) -> None:
    """There is no configuration that points inference at a remote host."""
    with pytest.raises(ConfigurationError):
        Settings(ollama_url=url)


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("127.0.0.1", True),
        ("127.5.5.5", True),
        ("::1", True),
        ("[::1]", True),
        ("localhost", True),
        ("LOCALHOST", True),
        # A hostname that merely starts with "localhost" resolves wherever its
        # owner wants it to.
        ("localhost.attacker.example", False),
        ("0.0.0.0", False),
        ("", False),
    ],
)
def test_loopback_detection(host: str, expected: bool) -> None:
    assert is_loopback_host(host) is expected


# -- reported status ----------------------------------------------------------


def test_privacy_endpoint_reports_local_only(client: TestClient) -> None:
    body = client.get("/api/privacy/status").json()
    assert body["localOnly"] is True
    assert body["bindsToLoopbackOnly"] is True
    assert body["wildcardCors"] is False
    assert body["remoteProviderConfigured"] is False
    assert body["telemetryEnabled"] is False


def test_privacy_endpoint_lists_only_loopback_outbound_endpoints(client: TestClient) -> None:
    body = client.get("/api/privacy/status").json()
    for endpoint in body["outboundEndpoints"]:
        assert is_loopback_host(url_host(endpoint))


def test_privacy_claim_is_computed_not_hardcoded() -> None:
    """The badge must go dark if the configuration stops being local.

    Binding to every interface means other machines can post documents to this
    backend, so the interface should stop claiming the work is private to this
    computer.
    """
    exposed = Settings(host="0.0.0.0", allow_non_loopback_bind=True)
    with TestClient(_app_for(exposed)) as client:
        assert client.get("/api/privacy/status").json()["localOnly"] is False


def _app_for(settings: Settings):
    from ritarinn.main import create_app

    return create_app(settings)


# -- generative features never fall back to a hosted service ------------------


@pytest.mark.parametrize("path", ["/api/summarize", "/api/simplify"])
def test_generative_endpoints_fail_rather_than_reach_for_the_cloud(
    client: TestClient, path: str
) -> None:
    """With no local model configured, generation stops.

    The failure mode that must never appear is a summary produced anyway — by
    a hosted model. There is no code path that could do it, and this asserts
    the observable consequence: the request fails, and the message tells the
    user to choose a *local* model.
    """
    response = client.post(path, json={"text": "Þetta er texti sem á að vinna."})
    assert response.status_code == 503
    assert "líkan" in response.json()["detail"]


def test_generation_is_not_reported_ready_without_a_model(client: TestClient) -> None:
    assert client.get("/api/models/status").json()["generationReady"] is False


# -- source-level checks ------------------------------------------------------

#: Hosted AI, analytics and error-reporting services that must not appear
#: anywhere in the shipped source. Matched case-insensitively against source
#: text, so a stray import or URL fails the suite.
FORBIDDEN_HOSTS = [
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
    "aiplatform.googleapis.com",
    "openai.azure.com",
    "dashscope.aliyuncs.com",
    "qwen.ai",
    "bedrock-runtime",
    "sentry.io",
    "google-analytics.com",
    "googletagmanager.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "cdn.jsdelivr.net",
    "unpkg.com",
    "cdnjs.cloudflare.com",
]

SOURCE_GLOBS = ["backend/ritarinn/**/*.py", "frontend/src/**/*.ts", "frontend/src/**/*.tsx"]


def _source_files() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for pattern in SOURCE_GLOBS:
        files.extend(REPO_ROOT.glob(pattern))
    assert files, "source globs matched nothing — the scan would pass vacuously"
    return files


def _code_of(path: pathlib.Path) -> str:
    """File contents with comments and documentation removed.

    Prose explaining which services Ritarinn avoids must not trip the checks
    that verify it avoids them. See ``_source_scan``.
    """
    return strip_comments(path.suffix, path.read_text(encoding="utf-8"))


def test_no_hosted_service_endpoints_in_source() -> None:
    offenders: list[str] = []
    for path in _source_files():
        code = _code_of(path).lower()
        for host in FORBIDDEN_HOSTS:
            if host in code:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {host}")
    assert not offenders, "hosted service referenced in application source: " + ", ".join(offenders)


def test_no_remote_urls_in_application_source() -> None:
    """Application code may only address loopback.

    Documentation links live in docs/ and THIRD_PARTY_NOTICES.md, not in code
    that runs.
    """
    url_pattern = re.compile(r"https?://[^\s\"'`)>,;]+", re.IGNORECASE)
    offenders: list[str] = []
    for path in _source_files():
        for match in url_pattern.finditer(_code_of(path)):
            if not is_loopback_host(url_host(match.group(0))):
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {match.group(0)}")
    assert not offenders, "non-loopback URL in application source: " + ", ".join(offenders)


def test_frontend_has_no_remote_assets() -> None:
    """No CDN scripts and no remote fonts in the HTML shell or stylesheet."""
    index_path = REPO_ROOT / "frontend" / "index.html"
    index = strip_comments(".html", index_path.read_text(encoding="utf-8"))
    for match in re.finditer(r"https?://[^\s\"'`)>,;]+", index):
        assert is_loopback_host(url_host(match.group(0))), match.group(0)

    css_path = REPO_ROOT / "frontend" / "src" / "styles" / "app.css"
    css = strip_comments(".css", css_path.read_text(encoding="utf-8"))
    assert "@import" not in css
    assert "@font-face" not in css
    assert "url(" not in css, "the stylesheet must not fetch anything"


def test_frontend_dependencies_are_pinned_and_minimal() -> None:
    """Exact pins only: a floating range is a supply-chain decision by accident."""
    import json

    manifest = json.loads(
        (REPO_ROOT / "frontend" / "package.json").read_text(encoding="utf-8")
    )
    for section in ("dependencies", "devDependencies"):
        for name, spec in manifest.get(section, {}).items():
            assert re.fullmatch(r"\d+\.\d+\.\d+", spec), f"{name} is not pinned exactly: {spec}"


def test_backend_dependencies_are_pinned() -> None:
    requirements = (REPO_ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")
    for line in requirements.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert "==" in line, f"unpinned backend dependency: {line}"
