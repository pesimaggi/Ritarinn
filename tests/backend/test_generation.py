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


class ScriptedOllama(FakeOllama):
    """A fake that answers each successive call differently.

    The retry path cannot be exercised with a single canned reply: its whole
    point is that the second response differs from the first. Each turn is a
    dict of ``content`` / ``thinking`` / ``done_reason``, or ``status`` for an
    HTTP error. The last turn repeats once the script runs out, so a test that
    wants "and it fails again" writes one turn.
    """

    def __init__(self, turns: list[dict]) -> None:
        super().__init__()
        self.turns = turns

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path != "/api/chat":
            return super().handler(request)
        body = json.loads(request.content.decode("utf-8"))
        self.requests.append(body)
        turn = self.turns[min(len(self.requests) - 1, len(self.turns) - 1)]

        if "status" in turn:
            return httpx.Response(turn["status"], json={"error": turn.get("error", "")})

        message = {"role": "assistant", "content": turn.get("content", "")}
        if turn.get("thinking"):
            message["thinking"] = turn["thinking"]
        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "message": message,
                "done": True,
                "done_reason": turn.get("done_reason", "stop"),
            },
        )


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


def test_reasoning_is_stripped_when_the_model_never_opened_a_tag() -> None:
    """The opening tag can come from the chat template, not the model.

    Some reasoning models are primed with ``<think>`` in the assistant prefix,
    so the completion starts mid-thought and only the closing tag is generated.
    Without this, a whole chain of thought reaches the document.
    """
    fake = FakeOllama(
        reply="Okay, let's tackle this. The user wants a summary.\n</think>\n"
        "Samantekt á íslensku."
    )
    with make_client(fake) as client:
        body = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        ).json()
    assert body["text"] == "Samantekt á íslensku."


def test_a_response_that_is_only_reasoning_is_reported_not_returned() -> None:
    """A model that spent its whole cap thinking has produced no summary.

    Cleaning leaves nothing, and the cap is what stopped it, so the user is
    told that rather than handed an empty result.
    """
    fake = FakeOllama(
        reply="Okay, let's tackle this. The user wants a summary.\n</think>",
        done_reason="length",
    )
    with make_client(fake) as client:
        response = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        )
    assert response.status_code == 503
    assert "hugsanaferli" in response.json()["detail"]


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


# -- the schema and the prompt tables must agree ------------------------------


@pytest.mark.parametrize(
    ("annotation", "table_names"),
    [
        ("length", ("_LENGTH_GUIDANCE", "LENGTH_TOKEN_BUDGET")),
        ("form", ("_FORM_GUIDANCE",)),
        ("audience", ("_AUDIENCE_GUIDANCE",)),
        ("style", ("_STYLE_GUIDANCE",)),
    ],
)
def test_every_accepted_option_has_prompt_guidance(
    annotation: str, table_names: tuple[str, ...]
) -> None:
    """A value the schema accepts must be one the prompt builder can serve.

    The tables are indexed directly, so a value that passes validation but is
    missing from one of them is a 500 on a well-formed request. The literal
    types are the single definition of the vocabulary; this pins the tables to
    them, in both directions — an unreachable table entry is just as wrong.
    """
    from typing import get_args

    from ritarinn.models import api as schemas
    from ritarinn.services.generation import prompts

    request_model = schemas.SummarizeRequest if annotation in {"length", "form"} else (
        schemas.SimplifyRequest
    )
    accepted = set(get_args(request_model.model_fields[annotation].annotation))
    assert accepted, f"{annotation} is not constrained to a set of values"

    for table_name in table_names:
        assert accepted == set(getattr(prompts, table_name)), (
            f"{table_name} does not cover exactly the values the schema accepts"
        )


@pytest.mark.parametrize(
    "request_model_name", ["SummarizeRequest", "SimplifyRequest"]
)
def test_generation_option_defaults_match_the_service_defaults(request_model_name: str) -> None:
    """The wire defaults and the service dataclass defaults are one behaviour.

    A client may send only ``text``; the two layers disagreeing would mean the
    documented default and the applied default are different things.
    """
    import dataclasses

    from ritarinn.models import api as schemas
    from ritarinn.services.simplification import SimplifyOptions
    from ritarinn.services.summarization import SummaryOptions

    request_model = getattr(schemas, request_model_name)
    options = SummaryOptions if request_model_name == "SummarizeRequest" else SimplifyOptions

    service_defaults = {f.name: f.default for f in dataclasses.fields(options)}
    for name, default in service_defaults.items():
        assert request_model.model_fields[name].default == default, (
            f"{request_model_name}.{name} defaults differently from {options.__name__}"
        )


# -- reasoning that carries no tag at all -------------------------------------
#
# The hard case, and the one seen in practice. A reasoning model whose chat
# template puts ``<think>`` in the assistant prefix never generates an opening
# tag, so the completion begins mid-thought; if the output cap arrives before
# the model finishes reasoning, no closing tag is generated either. The response
# is then a chain of thought with nothing whatsoever marking it as one, and tag
# stripping — which is all Ritarinn had — cannot see it.


LEAKED_REASONING = (
    "Okay, let's tackle this problem. The user wants me to create two sentences "
    "that capture the main points of the given Icelandic text. The text is about "
    "a trip the narrator and friends took, specifically around Borgarnes.\n\n"
    "First, I need to understand the key points. The main events are: they went "
    "to a summer house, cooked food, had some issues with packing.\n\n"
    "Wait, the user wants two sentences that summarize the main points. Let me check"
)


def test_untagged_reasoning_never_reaches_the_document() -> None:
    """The reported failure: a chain of thought returned as the summary.

    Nothing in the response is a tag, so it is caught by how it reads or not at
    all. Handing this to the user would put a model's private notes about them
    into their document.
    """
    fake = ScriptedOllama([{"content": LEAKED_REASONING, "done_reason": "length"}])
    with make_client(fake) as client:
        response = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        )

    assert response.status_code == 503
    assert "hugsanaferli" in response.json()["detail"]


def test_leaked_reasoning_is_retried_by_letting_the_model_reason() -> None:
    """The retry stops fighting the model rather than pushing harder.

    Suppression is tried first because it is fastest. When it does not take, the
    answer is to let the model think and take what it writes afterwards — a
    model that reasons is frequently the one the user chose *because* it
    reasons. A second local generation is a real cost on a CPU, so this happens
    only after the model has demonstrated the problem, never speculatively.
    """
    fake = ScriptedOllama(
        [
            {"content": LEAKED_REASONING, "done_reason": "length"},
            {"content": "Vinahópur fór í sumarbústað og ferðin heppnaðist vel."},
        ]
    )
    with make_client(fake) as client:
        response = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        )

    assert response.status_code == 200
    assert response.json()["text"] == "Vinahópur fór í sumarbústað og ferðin heppnaðist vel."
    assert len(fake.requests) == 2, "exactly one retry"

    assert fake.requests[0]["think"] is False, "suppression is tried first, it is fastest"
    assert fake.requests[1]["think"] is True, "then the runtime is asked to separate it"
    assert "á íslensku" in fake.system_prompts[1], "and the language is restated"
    assert fake.system_prompts[0] != fake.system_prompts[1]


def test_a_successful_first_attempt_is_never_retried() -> None:
    """The retry must not become a second generation on the happy path."""
    fake = ScriptedOllama([{"content": "Samantekt á íslensku um ferðalagið."}])
    with make_client(fake) as client:
        client.post("/api/summarize", json={"text": LEGAL_TEXT, "proofread": False})
    assert len(fake.requests) == 1


def test_a_model_that_keeps_thinking_is_reported_not_returned() -> None:
    fake = ScriptedOllama([{"content": LEAKED_REASONING, "done_reason": "length"}])
    with make_client(fake) as client:
        response = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        )
    assert len(fake.requests) == 2, "tried twice before giving up"
    assert response.status_code == 503
    detail = response.json()["detail"]
    assert "hugsanaferli" in detail
    assert "líkan" in detail, "the message says what the user can do about it"


# -- answers in the wrong language --------------------------------------------


ENGLISH_ANSWER = (
    "The group of friends travelled to a summer house near Borgarnes for the "
    "weekend. They cooked dinner together and agreed to plan the next trip more "
    "carefully, writing a list of what to bring."
)


def test_an_answer_in_english_is_retried_in_icelandic() -> None:
    """A correct summary in the wrong language is still not the feature."""
    fake = ScriptedOllama(
        [
            {"content": ENGLISH_ANSWER},
            {"content": "Vinahópur fór í sumarbústað og ætlar að skipuleggja sig betur."},
        ]
    )
    with make_client(fake) as client:
        body = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        ).json()
    assert body["text"].startswith("Vinahópur")
    assert len(fake.requests) == 2


def test_an_answer_that_stays_english_is_reported() -> None:
    fake = ScriptedOllama([{"content": ENGLISH_ANSWER}])
    with make_client(fake) as client:
        response = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        )
    assert response.status_code == 503
    assert "íslensku" in response.json()["detail"]


def test_icelandic_containing_an_english_quotation_is_not_retried() -> None:
    """The language check must not fire on a document's own English material."""
    quoted = (
        "Í samningnum er vísað til skjalsins „Terms and Conditions of Service“ "
        "frá 2019, og þar kemur fram að réttindi verði ekki framseld án samþykkis."
    )
    fake = ScriptedOllama([{"content": quoted}])
    with make_client(fake) as client:
        body = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        ).json()
    assert body["text"] == quoted
    assert len(fake.requests) == 1


# -- the runtime's own thinking field -----------------------------------------


def test_the_runtimes_thinking_field_is_never_part_of_the_answer() -> None:
    """A runtime that understands thinking returns it separately. It is not output."""
    fake = ScriptedOllama(
        [
            {
                "thinking": "The user wants a summary. Let me identify the key points.",
                "content": "Samantekt á íslensku um efni skjalsins.",
            }
        ]
    )
    with make_client(fake) as client:
        body = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        ).json()
    assert body["text"] == "Samantekt á íslensku um efni skjalsins."


def test_thinking_with_no_answer_is_reported_as_a_thinking_model() -> None:
    """Separated reasoning and an empty answer is the same failure, reported the same."""
    fake = ScriptedOllama(
        [{"thinking": "Let me work out what to say.", "content": "", "done_reason": "stop"}]
    )
    with make_client(fake) as client:
        response = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        )
    assert response.status_code == 503
    assert "hugsanaferli" in response.json()["detail"]


def test_a_runtime_that_rejects_the_thinking_flag_is_retried_without_it() -> None:
    """Some runtime versions 400 the flag for a model with no thinking capability.

    The flag is an optimisation — output cleaning handles a model that thinks
    anyway — so a runtime that refuses it must not cost the user the feature.
    """
    fake = ScriptedOllama(
        [
            {"status": 400, "error": "model does not support thinking"},
            {"content": "Samantekt á íslensku um efni skjalsins."},
        ]
    )
    with make_client(fake) as client:
        body = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        ).json()

    assert body["text"] == "Samantekt á íslensku um efni skjalsins."
    assert "think" in fake.requests[0], "the flag is tried first"
    assert "think" not in fake.requests[1], "and dropped when the runtime refuses it"


def test_other_runtime_errors_are_not_retried_as_a_thinking_problem() -> None:
    fake = ScriptedOllama([{"status": 500, "error": "internal server error"}])
    with make_client(fake) as client:
        response = client.post("/api/summarize", json={"text": LEGAL_TEXT})
    assert response.status_code == 503
    assert len(fake.requests) == 1, "a server error is not a thinking-flag problem"


# -- the output cap -----------------------------------------------------------


def test_every_length_leaves_room_to_finish_a_sentence() -> None:
    """A cap that bites truncates mid-sentence, which is the worst failure mode.

    Icelandic tokenises to noticeably more tokens per word than English in most
    vocabularies, so budgets sized by eye from English are too small.
    """
    from ritarinn.services.generation.prompts import LENGTH_TOKEN_BUDGET

    assert LENGTH_TOKEN_BUDGET["very_short"] >= 256
    for shorter, longer in [
        ("very_short", "short"),
        ("short", "medium"),
        ("medium", "detailed"),
    ]:
        assert LENGTH_TOKEN_BUDGET[shorter] < LENGTH_TOKEN_BUDGET[longer]


def test_a_model_known_to_reason_skips_straight_to_the_second_strategy() -> None:
    """A long document is many generations; the discovery is paid for once.

    Without this, every chunk of a long document would repeat the leak and the
    retry, doubling the wait on exactly the slow hardware Ritarinn is meant to
    stay usable on.
    """
    fake = ScriptedOllama(
        [
            {"content": LEAKED_REASONING, "done_reason": "length"},
            {"content": "Samantekt á hluta skjalsins."},
        ]
    )
    long_text = "\n\n".join(f"Málsgrein {n}. {LEGAL_TEXT}" for n in range(12))
    with make_client(fake, llm_context_chars=400) as client:
        response = client.post(
            "/api/summarize", json={"text": long_text, "proofread": False}
        )

    assert response.status_code == 200
    # The first chunk leaked and was retried; every call after it starts there.
    assert fake.requests[0]["think"] is False
    assert all(body["think"] is True for body in fake.requests[1:])
    # One extra call in total — the retry — not one per chunk.
    assert len(fake.requests) == response.json()["chunks"] + 2


# -- the reasoning model that cannot be talked out of it ----------------------
#
# The soft switch is a chat-template convention. Some model families honour it;
# others have no equivalent, and a template that opens the reasoning block
# unconditionally reasons whatever it is told. Such a model is not broken and
# its Icelandic may be excellent — it just has to think first, and the only
# thing it needs is room to finish. Given that room it closes the block, and
# tag stripping works as it always did.


class AlwaysThinkingOllama(FakeOllama):
    """A model that reasons before answering and ignores every request not to.

    Behaviour depends on the output budget it is given, which is the whole point:
    below what its reasoning costs, the response is cut off mid-thought with no
    closing tag to strip, which is the reported failure. Above it, the model
    closes the block and writes the summary.

    The opening tag is never emitted, because the chat template supplied it —
    the response begins mid-thought, exactly as the real ones do.
    """

    #: What this model's reasoning costs before it writes anything.
    THINKING_TOKENS = 1600

    ANSWER = "Vinahópur fór í sumarbústað og ferðin heppnaðist vel þrátt fyrir rigningu."

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path != "/api/chat":
            return super().handler(request)
        body = json.loads(request.content.decode("utf-8"))
        self.requests.append(body)

        budget = body["options"]["num_predict"]
        reasoning = "Okay, let's tackle this. The user wants a summary of the text. "
        if budget < self.THINKING_TOKENS:
            # Cut off mid-thought: no closing tag is ever generated.
            content, done = reasoning + "First, I need to identify the main", "length"
        else:
            content, done = f"{reasoning}</think>\n{self.ANSWER}", "stop"

        return httpx.Response(
            200,
            json={
                "model": body["model"],
                "message": {"role": "assistant", "content": content},
                "done": True,
                "done_reason": done,
            },
        )


def test_a_model_that_must_think_is_given_room_to_finish() -> None:
    """The retry does not only try to suppress reasoning — it also allows it.

    Suppression alone would fail this model on every request, and refuse the
    user a summary it is perfectly capable of writing.
    """
    fake = AlwaysThinkingOllama()
    with make_client(fake) as client:
        response = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        )

    assert response.status_code == 200
    assert response.json()["text"] == AlwaysThinkingOllama.ANSWER
    assert len(fake.requests) == 2
    first, second = (body["options"]["num_predict"] for body in fake.requests)
    assert second > first, "the retry raises the cap, not only the instructions"
    assert second >= AlwaysThinkingOllama.THINKING_TOKENS


def test_the_headroom_is_kept_for_later_chunks_of_the_same_document() -> None:
    """Otherwise every chunk of a long document repeats the whole discovery."""
    fake = AlwaysThinkingOllama()
    long_text = "\n\n".join(f"Málsgrein {n}. {LEGAL_TEXT}" for n in range(12))
    with make_client(fake, llm_context_chars=400) as client:
        response = client.post(
            "/api/summarize", json={"text": long_text, "proofread": False}
        )

    assert response.status_code == 200
    budgets = [body["options"]["num_predict"] for body in fake.requests]
    assert budgets[0] < AlwaysThinkingOllama.THINKING_TOKENS, "the first try is the plain one"
    assert all(
        budget >= AlwaysThinkingOllama.THINKING_TOKENS for budget in budgets[1:]
    ), "and every call after the discovery carries the headroom"
    assert len(fake.requests) == response.json()["chunks"] + 2, "one retry in total"


def test_headroom_is_not_spent_on_a_model_that_does_not_reason() -> None:
    """A ceiling is not a target, but it must not be raised speculatively either."""
    fake = ScriptedOllama([{"content": "Samantekt á íslensku um efni skjalsins."}])
    with make_client(fake) as client:
        client.post("/api/summarize", json={"text": LEGAL_TEXT, "proofread": False})

    from ritarinn.services.generation.prompts import LENGTH_TOKEN_BUDGET

    assert len(fake.requests) == 1
    assert fake.requests[0]["options"]["num_predict"] == LENGTH_TOKEN_BUDGET["medium"]


# -- never refuse Icelandic ---------------------------------------------------
#
# A chain of thought is overwhelmingly English, so the reasoning detector is far
# more certain about English than about Icelandic. "Allt í lagi, hér kemur
# samantektin" is a summary with a conversational opening, not a model talking to
# itself, and the two are not distinguishable from the first line alone. Refusing
# it would cost the user a generation they already waited through, on a guess.


ICELANDIC_WITH_A_CHATTY_OPENING = (
    "Allt í lagi, hér kemur samantektin: hópur vina fór í sumarbústað nálægt "
    "Borgarnesi um helgi og elduðu saman kvöldmat. Ferðin heppnaðist vel þrátt "
    "fyrir rigningu og hópurinn ætlar að skipuleggja sig betur næst."
)


def test_icelandic_that_only_looks_like_reasoning_is_retried_first() -> None:
    """A retry is cheap insurance; it just must not end in a refusal."""
    fake = ScriptedOllama(
        [
            {"content": ICELANDIC_WITH_A_CHATTY_OPENING},
            {"content": "Hópur vina fór í sumarbústað og ferðin heppnaðist vel."},
        ]
    )
    with make_client(fake) as client:
        body = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        ).json()
    assert body["text"] == "Hópur vina fór í sumarbústað og ferðin heppnaðist vel."
    assert len(fake.requests) == 2


def test_icelandic_that_only_looks_like_reasoning_is_shown_rather_than_refused() -> None:
    """The user gets the text and can judge it in a second.

    An error after two local generations leaves them with nothing, and the
    judgement that this was reasoning at all was never certain.
    """
    fake = ScriptedOllama([{"content": ICELANDIC_WITH_A_CHATTY_OPENING}])
    with make_client(fake) as client:
        response = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        )
    assert response.status_code == 200
    assert response.json()["text"] == ICELANDIC_WITH_A_CHATTY_OPENING


def test_english_reasoning_is_still_never_shown() -> None:
    """The fallback must not become a way for a trace to reach the document."""
    fake = ScriptedOllama([{"content": LEAKED_REASONING, "done_reason": "length"}])
    with make_client(fake) as client:
        response = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        )
    assert response.status_code == 503


def test_an_english_answer_is_still_never_shown() -> None:
    fake = ScriptedOllama([{"content": ENGLISH_ANSWER}])
    with make_client(fake) as client:
        response = client.post(
            "/api/summarize", json={"text": LEGAL_TEXT, "proofread": False}
        )
    assert response.status_code == 503


def test_the_reasoning_headroom_is_configurable() -> None:
    """The right value is a property of the model; nothing else can know it.

    A user who likes a model's Icelandic must be able to give it more room
    without editing code.
    """
    fake = ScriptedOllama(
        [
            {"content": LEAKED_REASONING, "done_reason": "length"},
            {"content": "Samantekt á íslensku um efni skjalsins."},
        ]
    )
    with make_client(fake, llm_reasoning_headroom=9000) as client:
        client.post("/api/summarize", json={"text": LEGAL_TEXT, "proofread": False})

    from ritarinn.services.generation.prompts import LENGTH_TOKEN_BUDGET

    first, second = (body["options"]["num_predict"] for body in fake.requests)
    assert first == LENGTH_TOKEN_BUDGET["medium"]
    assert second == LENGTH_TOKEN_BUDGET["medium"] + 9000
