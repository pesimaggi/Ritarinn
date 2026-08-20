"""The local inference provider.

v0.1 detects a local Ollama so the status panel can tell the truth about what is
installed. It never sends text, and it must fail closed if pointed anywhere but
loopback.
"""

from __future__ import annotations

import httpx
import pytest

from ritarinn.config import Settings
from ritarinn.services.llm.base import FeatureNotAvailableError, GenerationRequest
from ritarinn.services.llm.ollama import OllamaProvider


def _provider_with_response(handler) -> OllamaProvider:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    return OllamaProvider(Settings(), client=client)


def test_reports_unavailable_when_ollama_is_not_running() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    status = _provider_with_response(refuse).status()
    assert status.available is False
    assert status.detail and "Ollama" in status.detail
    assert status.can_generate is False


def test_lists_locally_installed_models() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "127.0.0.1"
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "name": "mistral:7b",
                        "size": 4_100_000_000,
                        "details": {"family": "llama", "parameter_size": "7B"},
                    }
                ]
            },
        )

    status = _provider_with_response(respond).status()
    assert status.available is True
    assert [model.name for model in status.models] == ["mistral:7b"]
    assert status.local_only is True


def test_cannot_generate_without_a_selected_model() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "mistral:7b"}]})

    assert _provider_with_response(respond).status().can_generate is False


def test_disabled_provider_makes_no_request() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise AssertionError("a disabled provider must not contact anything")

    transport = httpx.MockTransport(fail)
    provider = OllamaProvider(
        Settings(ollama_enabled=False), client=httpx.Client(transport=transport)
    )
    assert provider.status().available is False


def test_generation_is_not_available_in_this_version() -> None:
    """The seam exists; the feature does not. It does not silently do nothing."""
    provider = OllamaProvider(Settings())
    with pytest.raises(FeatureNotAvailableError):
        provider.generate(
            GenerationRequest(system_prompt="", user_prompt="", model="mistral:7b")
        )


def test_provider_is_model_agnostic() -> None:
    """No model family is wired into the provider or its contract.

    Documentation may discuss model families — the point of the abstraction is
    easier to explain with examples — so only executable code is checked.
    """
    import inspect
    import re

    from _source_scan import python_code

    from ritarinn.services.llm import base, ollama

    for module in (base, ollama):
        code = python_code(inspect.getsource(module)).lower()
        for vendor in ["qwen", "alibaba", "openai", "gemini", "mistral", "llama"]:
            # Whole words only: "ollama" is the runtime, and it legitimately
            # contains "llama". The distinction between runtime and model is
            # exactly what this test is protecting.
            assert not re.search(rf"\b{vendor}\b", code), f"{module.__name__} hardcodes {vendor}"
