"""The proofreading endpoint.

These tests assert properties that must hold for any correction engine — spans
land on real text, suggestions are applicable, categories are known — rather
than pinning GreynirCorrect's exact opinions. Where a specific correction *is*
asserted, it is one verified against the pinned engine version and central to
the product working at all.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from conftest import js_slice


def proofread(client: TestClient, text: str, **kwargs) -> dict:
    response = client.post("/api/proofread", json={"text": text, **kwargs})
    assert response.status_code == 200, response.text
    return response.json()


def test_finds_obvious_spelling_errors(client: TestClient) -> None:
    body = proofread(client, "Þinngið samþikkti tilöguna.")
    corrections = {issue["original"]: issue["replacement"] for issue in body["issues"]}
    assert corrections == {
        "Þinngið": "Þingið",
        "samþikkti": "samþykkti",
        "tilöguna": "tillöguna",
    }
    assert all(issue["category"] == "spelling" for issue in body["issues"])


def test_finds_case_government_error(client: TestClient) -> None:
    """The impersonal-verb case error from the product brief."""
    body = proofread(client, "Páli, vini mínum, langaði að horfa á sjónnvarpið.")
    grammar = [issue for issue in body["issues"] if issue["category"] == "grammar"]
    assert len(grammar) == 1
    issue = grammar[0]
    assert issue["original"] == "Páli, vini mínum,"
    assert issue["replacement"] == "Pál, vin minn"
    assert issue["explanation"], "a grammar issue should explain itself"


def test_empty_text_returns_no_issues(client: TestClient) -> None:
    body = proofread(client, "")
    assert body["issues"] == []


def test_whitespace_only_text_returns_no_issues(client: TestClient) -> None:
    assert proofread(client, "   \n\n  ")["issues"] == []


def test_long_paragraph_is_handled(client: TestClient, corpus: list[dict]) -> None:
    case = next(c for c in corpus if c["id"] == "long-paragraph")
    body = proofread(client, case["text"])
    assert isinstance(body["issues"], list)


def test_response_declares_its_offset_unit(client: TestClient) -> None:
    """Clients must not have to guess how offsets are counted."""
    assert proofread(client, "Þinngið samþikkti.")["offsetUnit"] == "utf16"


def test_issue_spans_match_the_submitted_text(client: TestClient, corpus: list[dict]) -> None:
    """Every reported span must select exactly the text it claims to.

    Sliced the way JavaScript slices, because that is what CodeMirror will do
    with these offsets.
    """
    for case in corpus:
        body = proofread(client, case["text"])
        for issue in body["issues"]:
            assert js_slice(case["text"], issue["startChar"], issue["endChar"]) == issue[
                "original"
            ], f"span mismatch in corpus case {case['id']} ({issue['code']})"


def test_spans_never_start_or_end_on_whitespace(client: TestClient, corpus: list[dict]) -> None:
    """Underlines cover words, not the spaces and newlines around them.

    GreynirCorrect's token spans include preceding whitespace; accepting such a
    span would swallow the line break before a word.
    """
    for case in corpus:
        for issue in proofread(client, case["text"])["issues"]:
            original = issue["original"]
            assert original == original.strip(), f"untrimmed span in {case['id']}"


def test_categories_and_scopes_are_known_values(client: TestClient, corpus: list[dict]) -> None:
    valid_categories = {"spelling", "grammar", "punctuation", "style", "unknown"}
    for case in corpus:
        for issue in proofread(client, case["text"])["issues"]:
            assert issue["category"] in valid_categories
            assert issue["scope"] in {"span", "sentence"}
            assert issue["source"] == "greynir"


def test_no_fabricated_confidence(client: TestClient, corpus: list[dict]) -> None:
    """GreynirCorrect reports no confidence score, so neither do we."""
    for case in corpus:
        for issue in proofread(client, case["text"])["issues"]:
            assert issue["confidence"] is None


def test_error_codes_come_from_the_engine(client: TestClient) -> None:
    """Codes are passed through verbatim, not invented."""
    body = proofread(client, "Þinngið samþikkti tilöguna.")
    assert {issue["code"] for issue in body["issues"]} == {"S004"}


def test_applying_every_suggestion_reproduces_valid_text(client: TestClient) -> None:
    """Suggestions must be directly applicable to their own span.

    Applied back to front so earlier offsets stay valid — the same order the
    frontend's "Samþykkja allt" uses.
    """
    text = "Þinngið samþikkti tilöguna."
    issues = [
        issue
        for issue in proofread(client, text)["issues"]
        if issue["replacement"] is not None and issue["scope"] == "span"
    ]
    result = text
    for issue in sorted(issues, key=lambda i: i["startChar"], reverse=True):
        result = result[: issue["startChar"]] + issue["replacement"] + result[issue["endChar"] :]
    assert result == "Þingið samþykkti tillöguna."


def test_sentence_scope_issues_cover_a_sentence(client: TestClient, corpus: list[dict]) -> None:
    """Sentence-scope annotations span more than a word and offer no fix."""
    case = next(c for c in corpus if c["id"] == "bureaucratic")
    body = proofread(client, case["text"])
    sentence_level = [issue for issue in body["issues"] if issue["scope"] == "sentence"]
    assert sentence_level, "the very long bureaucratic sentence should be flagged"
    for issue in sentence_level:
        assert issue["endChar"] - issue["startChar"] > 20


def test_ignore_codes_suppresses_a_rule(client: TestClient) -> None:
    text = "Hvað ætlar þú að gera á morgun.. Ég veit það ekki!!!"
    codes = {issue["code"] for issue in proofread(client, text)["issues"]}
    assert "E007" in codes

    filtered = proofread(client, text, ignoreCodes=["E007"])
    assert "E007" not in {issue["code"] for issue in filtered["issues"]}


def test_issues_are_ordered_by_position(client: TestClient, corpus: list[dict]) -> None:
    for case in corpus:
        issues = proofread(client, case["text"])["issues"]
        starts = [issue["startChar"] for issue in issues]
        assert starts == sorted(starts)


# -- malformed requests -------------------------------------------------------


def test_missing_text_field_is_rejected(client: TestClient) -> None:
    assert client.post("/api/proofread", json={}).status_code == 422


def test_wrong_type_for_text_is_rejected(client: TestClient) -> None:
    assert client.post("/api/proofread", json={"text": 42}).status_code == 422


def test_invalid_json_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/proofread",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422


def test_unknown_engine_is_rejected_with_a_helpful_message(client: TestClient) -> None:
    response = client.post("/api/proofread", json={"text": "Halló.", "engines": ["gpt"]})
    assert response.status_code == 400
    assert "gpt" in response.json()["detail"]


def test_unavailable_engine_reports_service_unavailable(client: TestClient) -> None:
    """Asking for ByT5 fails cleanly instead of pretending to work."""
    response = client.post("/api/proofread", json={"text": "Halló.", "engines": ["byt5"]})
    assert response.status_code == 503


def test_oversized_text_is_rejected(client: TestClient, settings) -> None:
    response = client.post(
        "/api/proofread", json={"text": "a" * (settings.max_text_chars + 1)}
    )
    assert response.status_code == 413


@pytest.mark.parametrize(
    "text",
    [
        "Halló 🇮🇸 heimur! Þinngið samþikkti tilöguna.",
        "Hann sagði „þetta er ágætt“ — en bætti svo við: „við sjáum til.“",
        "Ást, épli, ís, ól, úr, ýmis, þök, æði, öl.",
        "𝄞 Þinngið samþikkti tilöguna.",
    ],
)
def test_tricky_unicode_does_not_break_spans(client: TestClient, text: str) -> None:
    for issue in proofread(client, text)["issues"]:
        assert js_slice(text, issue["startChar"], issue["endChar"]) == issue["original"]
