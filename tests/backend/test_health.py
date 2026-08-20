"""Health endpoint and startup."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"]


def test_greynir_is_ready_after_startup(client: TestClient) -> None:
    """GreynirCorrect must be usable without any extra installation step.

    This is the Milestone 1 promise: proofreading works out of the box, with no
    model download and no network access.
    """
    assert client.get("/api/health").json()["proofreadingReady"] is True

    statuses = client.get("/api/models/status").json()["correctionEngines"]
    greynir = next(engine for engine in statuses if engine["name"] == "greynir")
    assert greynir["available"] is True
    assert greynir["localOnly"] is True
    assert greynir["version"]


def test_byt5_is_absent_but_declared(client: TestClient) -> None:
    """The optional neural engine reports itself off, not missing."""
    statuses = client.get("/api/models/status").json()["correctionEngines"]
    byt5 = next(engine for engine in statuses if engine["name"] == "byt5")
    assert byt5["available"] is False
    assert byt5["detail"], "an unavailable engine must explain itself in Icelandic"


def test_security_headers_present(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'none'" in response.headers["content-security-policy"]
