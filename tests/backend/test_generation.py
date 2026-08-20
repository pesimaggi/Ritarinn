"""Summarization and plain-language rewriting.

These run against a scripted fake Ollama rather than a real model, so they are
deterministic and fast. What they verify is the machinery Ritarinn is
responsible for — chunking, hierarchical combination, output cleaning, token
caps, error mapping, and the promise that nothing is applied automatically —
not the quality of a model's Icelandic, which is Milestone 3's subject and
cannot be asserted in a unit test.

A real model is exercised separately; see docs/roadmap.md.
"""

from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from ritarinn.config import Settings
from ritarinn.main import create_app
from ritarinn.services.llm.base import GenerationRequest, ProviderUnavailableError
from ritarinn.services.llm.ollama import OllamaProvider, clean_model_output


class FakeOllama:
    """A scripted stand-in for a local Ollama, recording what it was asked."""

    def __init__(self, reply: str = "Samantekt á íslensku.", done_reason: str = "stop") -> None:
        self.reply = reply
        self.done_reason = done_reason
        self.requests: list[dict] = []
        self.installed_models = [{"name": "prófunarlíkan:latest", "size": 1234}]

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert request.url.host in {"127.0.0.1", "localhost", "::1"}, "left loopback"
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": self.installed_models})
        if request.url.path == "/api/chat":
            body = json.loads(request.content.decode("utf-8"))
            self.requests.append(body)
            reply = self.reply(body) if callable(self.reply) else self.reply
            return httpx.Response(
                200,
                json={
                    "model": body["model"],
                    "message": {"role": "assistant", "content": reply},
                    "done": True,
                    "done_reason": self.done_reason,
                },
            )
        return httpx.Response(404, json={"error": "not found"})

    @property
    def prompts(self) -> list[str]:
        return [body["messages"][1]["content"] for body in self.requests]

    @property
    def system_prompts(self) -> list[str]:
        return [body["messages"][0]["content"] for body in self.requests]


def make_client(fake: FakeOllama, **settings_kwargs) -> TestClient:
    settings = Settings(llm_model="prófunarlíkan:latest", **settings_kwargs)
    app = create_app(settings)
    app.state.ritarinn.llm = OllamaProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(fake.handler))
    )
    return TestClient(app)


LEGAL_TEXT = (
    "Óheimilt er að framselja réttindi samkvæmt samningi þessum án skriflegs "
    "samþykkis gagnaðila, sbr. 3. mgr. 12. gr. laga nr. 7/1998."
)


# -- summarization ------------------------------------------------------------


def test_summarize_returns_the_models_text() -> None:
    fake = FakeOllama(reply="Þetta er samantekt.")
    with make_client(fake) as client:
        response = client.post("/api/summarize", json={"text": LEGAL_TEXT, "proofread": False})
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "Þetta er samantekt."
    assert body["model"] == "prófunarlíkan:latest"
    assert body["chunks"] == 1
    assert body["passes"] == 1


def test_short_text_uses_a_single_pass() -> None:
    fake = FakeOllama()
    with make_client(fake) as client:
        client.post("/api/summarize", json={"text": LEGAL_TEXT, "proofread": False})
    assert len(fake.requests) == 1, "a short document should not be chunked"


def test_long_text_is_summarised_hierarchically() -> None:
    """Chunk summaries, then one combine pass."""
    fake = FakeOllama()
    long_text = "\n\n".join(f"Málsgrein {n}. {LEGAL_TEXT}" for n in range(12))
    with make_client(fake, llm_context_chars=400) as client:
        body = client.post(
            "/api/summarize", json={"text": long_text, "proofread": False}
        ).json()

    assert body["chunks"] > 1
    assert body["passes"] == 2
    # One call per chunk, plus the combine call.
    assert len(fake.requests) == body["chunks"] + 1
    assert "SAMANTEKTIR" in fake.prompts[-1], "the last call should be the combine step"


def test_chunk_prompts_say_they_are_fragments() -> None:
    """So the model does not conclude from a part it cannot see the whole of."""
    fake = FakeOllama()
    long_text = "\n\n".join(f"Málsgrein {n}. {LEGAL_TEXT}" for n in range(12))
    with make_client(fake, llm_context_chars=400) as client:
        client.post("/api/summarize", json={"text": long_text, "proofread": False})
    assert "hluti 1 af" in fake.prompts[0]


@pytest.mark.parametrize(
    ("length", "marker"),
    [
        ("very_short", "eina til tvær setningar"),
        ("short", "stutta samantekt"),
        ("medium", "einni til tveimur málsgreinum"),
        ("detailed", "ítarlega samantekt"),
    ],
)
def test_length_option_reaches_the_prompt(length: str, marker: str) -> None:
    fake = FakeOllama()
    with make_client(fake) as client:
        client.post(
            "/api/summarize",
            json={"text": LEGAL_TEXT, "length": length, "proofread": False},
        )
    assert marker in fake.prompts[0]


@pytest.mark.parametrize(
    ("form", "marker"),
    [("prose", "samfelldan texta"), ("bullets", "punktalista")],
)
def test_form_option_reaches_the_prompt(form: str, marker: str) -> None:
    fake = FakeOllama()
    with make_client(fake) as client:
        client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "form": form, "proofread": False}
        )
    assert marker in fake.prompts[0]


def test_output_is_always_capped() -> None:
    """An uncapped local model can run past any timeout; the user sees a hang."""
    fake = FakeOllama()
    with make_client(fake) as client:
        client.post("/api/summarize", json={"text": LEGAL_TEXT, "proofread": False})
    assert fake.requests[0]["options"]["num_predict"] > 0


def test_truncation_is_reported() -> None:
    fake = FakeOllama(done_reason="length")
    with make_client(fake) as client:
        body = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        ).json()
    assert body["truncated"] is True


def test_completion_is_not_reported_as_truncated() -> None:
    fake = FakeOllama(done_reason="stop")
    with make_client(fake) as client:
        body = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        ).json()
    assert body["truncated"] is False


# -- simplification -----------------------------------------------------------


def test_simplify_returns_the_rewritten_text() -> None:
    fake = FakeOllama(reply="Þú mátt ekki selja réttindin án leyfis.")
    with make_client(fake) as client:
        body = client.post(
            "/api/simplify", json={"text": LEGAL_TEXT, "proofread": False}
        ).json()
    assert body["text"] == "Þú mátt ekki selja réttindin án leyfis."
    assert body["passes"] == 1


def test_simplify_rewrites_every_chunk_without_a_combine_pass() -> None:
    """A combine pass would be free to drop material, which a rewrite must not."""
    fake = FakeOllama(reply="Einfaldaður hluti.")
    long_text = "\n\n".join(f"Málsgrein {n}. {LEGAL_TEXT}" for n in range(12))
    with make_client(fake, llm_context_chars=400) as client:
        body = client.post(
            "/api/simplify", json={"text": long_text, "proofread": False}
        ).json()
    assert len(fake.requests) == body["chunks"], "no extra combine call"
    assert body["passes"] == 1


@pytest.mark.parametrize(
    ("audience", "marker"),
    [
        ("general", "almennur borgari"),
        ("experts", "sérfræðingur"),
        ("managers", "stjórnandi"),
        ("customers", "viðskiptavinur"),
        ("youth", "ungmenni"),
    ],
)
def test_audience_option_reaches_the_prompt(audience: str, marker: str) -> None:
    fake = FakeOllama()
    with make_client(fake) as client:
        client.post(
            "/api/simplify",
            json={"text": LEGAL_TEXT, "audience": audience, "proofread": False},
        )
    assert marker in fake.prompts[0]


@pytest.mark.parametrize(
    ("style", "marker"),
    [
        ("plain", "einfalt mál"),
        ("concise", "hnitmiðaður"),
        ("formal", "formlegt málsnið"),
        ("neutral", "hlutlaust málsnið"),
        ("friendly", "vinalegt"),
    ],
)
def test_style_option_reaches_the_prompt(style: str, marker: str) -> None:
    fake = FakeOllama()
    with make_client(fake) as client:
        client.post(
            "/api/simplify", json={"text": LEGAL_TEXT, "style": style, "proofread": False}
        )
    assert marker in fake.prompts[0]


# -- faithfulness instructions ------------------------------------------------


@pytest.mark.parametrize("endpoint", ["/api/summarize", "/api/simplify"])
def test_prompts_forbid_invention_and_preserve_detail(endpoint: str) -> None:
    """The instructions that keep generated text faithful to the source."""
    fake = FakeOllama()
    with make_client(fake) as client:
        client.post(endpoint, json={"text": LEGAL_TEXT, "proofread": False})
    system = fake.system_prompts[0]
    assert "Ekki bæta við upplýsingum" in system
    assert "tölum, dagsetningum" in system
    assert "nöfnum" in system
    assert "óvissu" in system
    assert "lagatilvísunum" in system


@pytest.mark.parametrize("endpoint", ["/api/summarize", "/api/simplify"])
def test_prompts_are_written_in_icelandic(endpoint: str) -> None:
    fake = FakeOllama()
    with make_client(fake) as client:
        client.post(endpoint, json={"text": LEGAL_TEXT, "proofread": False})
    system = fake.system_prompts[0]
    assert any(letter in system for letter in "áéíóúýþæöð")


# -- post-processing ----------------------------------------------------------


def test_generated_text_can_be_proofread_without_being_altered() -> None:
    """The §22 combination: model semantics, Icelandic linguistic tools."""
    fake = FakeOllama(reply="Þinngið samþikkti tilöguna.")
    with make_client(fake) as client:
        body = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": True}
        ).json()

    assert body["issues"], "GreynirCorrect should flag the misspellings"
    # The crucial part: the text is reported on, not rewritten.
    assert body["text"] == "Þinngið samþikkti tilöguna."


def test_proofreading_can_be_switched_off() -> None:
    fake = FakeOllama(reply="Þinngið samþikkti tilöguna.")
    with make_client(fake) as client:
        body = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        ).json()
    assert body["issues"] == []


def test_issues_in_generated_text_carry_valid_offsets() -> None:
    from conftest import js_slice

    generated = "Þinngið samþikkti tilöguna."
    fake = FakeOllama(reply=generated)
    with make_client(fake) as client:
        body = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": True}
        ).json()
    assert body["offsetUnit"] == "utf16"
    for issue in body["issues"]:
        assert js_slice(generated, issue["startChar"], issue["endChar"]) == issue["original"]


# -- failure handling ---------------------------------------------------------


def test_missing_model_reports_service_unavailable() -> None:
    fake = FakeOllama()
    settings = Settings(llm_model="")
    app = create_app(settings)
    app.state.ritarinn.llm = OllamaProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(fake.handler))
    )
    with TestClient(app) as client:
        response = client.post("/api/summarize", json={"text": LEGAL_TEXT})
    assert response.status_code == 503
    assert "líkan" in response.json()["detail"]


def test_unreachable_runtime_reports_service_unavailable() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    settings = Settings(llm_model="prófunarlíkan:latest")
    app = create_app(settings)
    app.state.ritarinn.llm = OllamaProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(refuse))
    )
    with TestClient(app) as client:
        response = client.post("/api/summarize", json={"text": LEGAL_TEXT})
    assert response.status_code == 503


@pytest.mark.parametrize("endpoint", ["/api/summarize", "/api/simplify"])
def test_empty_text_is_rejected(endpoint: str) -> None:
    fake = FakeOllama()
    with make_client(fake) as client:
        assert client.post(endpoint, json={"text": "   "}).status_code == 400


@pytest.mark.parametrize("endpoint", ["/api/summarize", "/api/simplify"])
def test_missing_or_wrongly_typed_text_is_rejected(endpoint: str) -> None:
    fake = FakeOllama()
    with make_client(fake) as client:
        assert client.post(endpoint, json={}).status_code == 422
        assert client.post(endpoint, json={"text": 42}).status_code == 422


@pytest.mark.parametrize(
    ("endpoint", "payload"),
    [
        ("/api/summarize", {"text": "halló", "length": "enormous"}),
        ("/api/summarize", {"text": "halló", "form": "haiku"}),
        ("/api/simplify", {"text": "halló", "audience": "cats"}),
        ("/api/simplify", {"text": "halló", "style": "baroque"}),
    ],
)
def test_unknown_option_values_are_rejected(endpoint: str, payload: dict) -> None:
    """An option Ritarinn has no prompt for must fail, not fall back silently."""
    fake = FakeOllama()
    with make_client(fake) as client:
        assert client.post(endpoint, json=payload).status_code == 422


def test_oversized_text_is_rejected() -> None:
    fake = FakeOllama()
    with make_client(fake, max_text_chars=100) as client:
        assert client.post("/api/summarize", json={"text": "a" * 200}).status_code == 413


def test_empty_model_output_is_an_error_not_an_empty_result() -> None:
    fake = FakeOllama(reply="   ")
    with make_client(fake) as client:
        assert client.post("/api/summarize", json={"text": LEGAL_TEXT}).status_code == 503


# -- output cleaning ----------------------------------------------------------


def test_reasoning_traces_are_stripped_from_output() -> None:
    fake = FakeOllama(reply="<think>Let me consider...</think>\nSamantekt á íslensku.")
    with make_client(fake) as client:
        body = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        ).json()
    assert body["text"] == "Samantekt á íslensku."


def test_whole_response_markdown_fence_is_removed() -> None:
    fake = FakeOllama(reply="```\nSamantekt á íslensku.\n```")
    with make_client(fake) as client:
        body = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        ).json()
    assert body["text"] == "Samantekt á íslensku."


def test_bullet_lists_survive_cleaning() -> None:
    """Markdown *inside* the answer is content when bullets were requested."""
    assert clean_model_output("- Fyrsti punktur\n- Annar punktur") == (
        "- Fyrsti punktur\n- Annar punktur"
    )


def test_reasoning_models_are_asked_not_to_think() -> None:
    fake = FakeOllama()
    with make_client(fake) as client:
        client.post("/api/summarize", json={"text": LEGAL_TEXT, "proofread": False})
    assert fake.requests[0]["think"] is False


# -- the local-only guarantee -------------------------------------------------


def test_generation_refuses_a_non_loopback_endpoint() -> None:
    """The one code path that carries the document must fail closed.

    Settings.validate() already refuses this at startup; the provider checks
    again, because a guarantee this central is worth enforcing twice.
    """
    settings = Settings(llm_model="prófunarlíkan:latest")
    provider = OllamaProvider(settings)
    object.__setattr__(settings, "ollama_url", "http://evil.example.com:11434")

    with pytest.raises(ProviderUnavailableError):
        provider.generate(
            GenerationRequest(
                system_prompt="", user_prompt="leyniskjal", model="prófunarlíkan:latest"
            )
        )


def test_generation_is_reported_ready_only_with_a_model_selected() -> None:
    fake = FakeOllama()
    with make_client(fake) as client:
        assert client.get("/api/models/status").json()["generationReady"] is True

    settings = Settings(llm_model="")
    app = create_app(settings)
    app.state.ritarinn.llm = OllamaProvider(
        settings, client=httpx.Client(transport=httpx.MockTransport(fake.handler))
    )
    with TestClient(app) as client:
        assert client.get("/api/models/status").json()["generationReady"] is False


def test_privacy_status_stays_local_with_generation_configured() -> None:
    fake = FakeOllama()
    with make_client(fake) as client:
        body = client.get("/api/privacy/status").json()
    assert body["localOnly"] is True
    assert body["remoteProviderConfigured"] is False
