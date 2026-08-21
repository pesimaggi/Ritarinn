"""The model diagnosis script.

The script exists because these failures are indistinguishable from the outside:
the summary is missing and the error says the model was reasoning, whether the
cause was an old runtime, a stubborn chat template, an output cap that arrived
mid-thought, or a model answering in English. Its verdicts are what turn one of
those into the others, so they are worth pinning — a diagnosis that reports the
wrong cause is worse than none, because it sends the user to change the wrong
thing.
"""

from __future__ import annotations

import importlib.util
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "diagnose_model.py"


def _load():
    spec = importlib.util.spec_from_file_location("diagnose_model", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


diagnose = _load()


def test_the_script_is_executable_as_documented() -> None:
    assert SCRIPT.exists()
    assert SCRIPT.stat().st_mode & 0o111, "documented as `python scripts/...` but also chmod +x"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        pytest.param("", "NOTHING LEFT", id="the whole response was reasoning"),
        pytest.param(
            "Okay, let's tackle this. The user wants a summary of the text, so I "
            "need to identify the main points and condense them into two sentences.",
            "REASONING IN ENGLISH",
            id="a leaked chain of thought",
        ),
        pytest.param(
            "The group of friends travelled to a summer house near Borgarnes for "
            "the weekend and agreed to plan the next trip more carefully.",
            "ANSWER IN ENGLISH",
            id="a real summary in the wrong language",
        ),
        pytest.param(
            "Hópur vina fór í sumarbústað nálægt Borgarnesi um helgi og elduðu "
            "saman kvöldmat. Ferðin heppnaðist vel þrátt fyrir rigningu.",
            "OK",
            id="what the user actually wants",
        ),
        pytest.param(
            "Allt í lagi, hér kemur samantektin: hópur vina fór í sumarbústað "
            "nálægt Borgarnesi og ferðin heppnaðist vel þrátt fyrir rigningu.",
            "looks like reasoning but is Icelandic",
            id="Icelandic with a conversational opening",
        ),
    ],
)
def test_verdicts_name_the_right_cause(text: str, expected: str) -> None:
    assert diagnose.verdict_for(text).startswith(expected)


def test_the_verdicts_match_what_the_application_would_do() -> None:
    """The diagnosis is worthless if it disagrees with the code it diagnoses."""
    from ritarinn.text.language import looks_like_english, looks_like_reasoning

    samples = [
        "Hópur vina fór í sumarbústað nálægt Borgarnesi um helgi og elduðu saman.",
        "Okay, let's tackle this. The user wants a summary of the given text now.",
        "The group travelled to a summer house near Borgarnes for the weekend.",
    ]
    for text in samples:
        verdict = diagnose.verdict_for(text)
        assert verdict.startswith("OK") == (
            not looks_like_reasoning(text) and not looks_like_english(text)
        )


def test_every_strategy_explains_what_it_establishes() -> None:
    """The output is read by someone who does not know the failure modes."""
    strategies = diagnose.build_strategies(headroom=4096, base=1200)
    assert len(strategies) >= 4
    for strategy in strategies:
        assert strategy.explains, f"{strategy.name} says nothing about why it is tried"

    # The first is what the application itself does first, so the report opens
    # by reproducing the user's actual failure rather than a variation on it.
    assert strategies[0].think is False
    assert strategies[0].budget_multiplier == 1.0


def test_the_retry_strategy_asks_for_separation_not_suppression() -> None:
    """The lesson of this whole module, pinned where it is easy to undo."""
    by_name = {s.name: s for s in diagnose.build_strategies(headroom=4096, base=1200)}
    retry = by_name["think=true + room"]
    assert retry.think is True
    assert retry.budget_multiplier > 1.0
