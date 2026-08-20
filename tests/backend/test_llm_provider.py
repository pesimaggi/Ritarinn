"""The local inference provider.

v0.1 detects a local Ollama so the status panel can tell the truth about what is
installed. It never sends text, and it must fail closed if pointed anywhere but
loopback.
"""

from __future__ import annotations

import json

import httpx
import pytest

from ritarinn.config import Settings
from ritarinn.services.llm.base import GenerationRequest, ProviderUnavailableError
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


def test_generation_requires_a_model() -> None:
    """Asking without naming a model fails loudly rather than picking one."""
    provider = OllamaProvider(Settings())
    with pytest.raises(ProviderUnavailableError):
        provider.generate(GenerationRequest(system_prompt="", user_prompt="", model=""))


def test_generation_sends_the_prompt_to_the_local_runtime() -> None:
    captured: dict = {}

    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "127.0.0.1", "generation must stay on loopback"
        captured.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(
            200,
            json={
                "message": {"role": "assistant", "content": "Niðurstaða."},
                "done_reason": "stop",
            },
        )

    provider = _provider_with_response(respond)
    result = provider.generate(
        GenerationRequest(
            system_prompt="kerfi",
            user_prompt="notandi",
            model="prófunarlíkan",
            max_tokens=128,
        )
    )
    assert result.text == "Niðurstaða."
    assert result.truncated is False
    assert captured["stream"] is False, "Ritarinn shows complete results only"
    assert captured["options"]["num_predict"] == 128


def test_disabled_provider_refuses_to_generate() -> None:
    provider = OllamaProvider(Settings(ollama_enabled=False))
    with pytest.raises(ProviderUnavailableError):
        provider.generate(
            GenerationRequest(system_prompt="", user_prompt="", model="prófunarlíkan")
        )


def test_a_missing_model_is_reported_with_the_command_to_fix_it() -> None:
    def not_found(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model not found"})

    provider = _provider_with_response(not_found)
    with pytest.raises(ProviderUnavailableError) as caught:
        provider.generate(
            GenerationRequest(system_prompt="", user_prompt="", model="vantar:latest")
        )
    assert "ollama pull vantar:latest" in caught.value.detail


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
