#!/usr/bin/env python3
"""Find out what a local model actually returns, and which strategy suits it.

Ritarinn's generative features fail in ways that look identical from the outside:
the summary is missing and the error says the model was reasoning. Underneath,
several different things cause that, and they need opposite fixes — an old
runtime that ignores the reasoning flag, a chat template that reasons whatever
it is told, an output cap that arrives mid-thought, or a model that answered in
English. Guessing between them by re-running the application is slow and tells
you almost nothing.

So this asks the model directly, under each strategy in turn, and prints what
came back: whether the runtime separated the reasoning into its own field, how
many tokens were generated, why generation stopped, what survived cleaning, and
what Ritarinn would have decided. Then it says which strategy worked and what to
put in your environment.

Every request goes to the same loopback endpoint the application uses, carrying
the same prompts. Nothing is sent anywhere else, and no model is downloaded.

Usage:
    python scripts/diagnose_model.py --model <model>
    python scripts/diagnose_model.py --model <model> --text-file mitt_skjal.txt

Run it with the model you want to work, and paste the output into a bug report:
it contains everything needed to tell these failures apart.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import httpx  # noqa: E402

from ritarinn.config import DEFAULT_OLLAMA_URL, is_loopback_host  # noqa: E402
from ritarinn.services.generation.prompts import (  # noqa: E402
    LENGTH_TOKEN_BUDGET,
    SUMMARY_SYSTEM,
    summary_user_prompt,
)
from ritarinn.services.llm.ollama import clean_model_output  # noqa: E402
from ritarinn.text.language import looks_like_english, looks_like_reasoning  # noqa: E402

#: A short Icelandic document with enough going on to summarise. Deliberately
#: not a fixture from the test corpus: this has to look like something a user
#: would actually paste in.
SAMPLE_TEXT = """\
Um síðustu helgi fór ég með nokkrum vinum mínum í sumarbústað rétt fyrir utan \
Borgarnes. Við lögðum af stað snemma á laugardagsmorgni og ætluðum að vera \
komin fyrir hádegi, en umferðin var meiri en við bjuggumst við og ferðalagið \
tók næstum tvo klukkutíma.

Um kvöldið elduðum við saman kvöldmat. Við höfðum keypt lambakjöt, kartöflur og \
ýmislegt grænmeti, en enginn hafði munað eftir sósunni. Sem betur fer fann \
einhver sinnep og smjör í ísskápnum og við náðum að búa til ágætis sósu úr því.

Daginn eftir vöknuðum við frekar seint. Veðrið hafði versnað töluvert og það \
rigndi nánast látlaust. Ferðin var samt mjög skemmtileg og við vorum öll \
sammála um að gera eitthvað svipað aftur fljótlega."""


class Strategy:
    """One way of asking, and what it is meant to establish."""

    def __init__(self, name: str, explains: str, think, budget_multiplier: float, nudge: str = ""):
        self.name = name
        self.explains = explains
        #: None means "do not send the field at all".
        self.think = think
        self.budget_multiplier = budget_multiplier
        self.nudge = nudge


def build_strategies(headroom: int, base: int) -> list[Strategy]:
    big = (base + headroom) / base
    return [
        Strategy(
            "think=false",
            "what Ritarinn tries first: ask the runtime to switch reasoning off",
            think=False,
            budget_multiplier=1.0,
        ),
        Strategy(
            "think=true + room",
            "what Ritarinn retries with: ask the runtime to SEPARATE the reasoning",
            think=True,
            budget_multiplier=big,
        ),
        Strategy(
            "no think field + room",
            "for a runtime too old to know the flag: just give it room to finish",
            think=None,
            budget_multiplier=big,
        ),
        Strategy(
            "/no_think + room",
            "the chat-template soft switch, for templates that honour it",
            think=None,
            budget_multiplier=big,
            nudge="/no_think",
        ),
        Strategy(
            "lots of room",
            "is the output cap the only thing in the way?",
            think=None,
            budget_multiplier=big * 2,
        ),
    ]


def ollama_version(client: httpx.Client, url: str) -> str:
    try:
        return str(client.get(f"{url}/api/version", timeout=5).json().get("version", "?"))
    except Exception:
        return "unknown (no /api/version — this runtime is old)"


def model_capabilities(client: httpx.Client, url: str, model: str) -> list[str]:
    """What the runtime believes this model can do.

    "thinking" in this list is the single most useful fact in the whole report:
    with it, the runtime parses reasoning out by itself and none of the rest
    matters. Without it, every reasoning the model does lands in the answer and
    has to be recognised and stripped.
    """
    try:
        response = client.post(f"{url}/api/show", json={"model": model}, timeout=15)
        response.raise_for_status()
        return list(response.json().get("capabilities") or [])
    except Exception:
        return []


def run(client: httpx.Client, url: str, model: str, text: str, base: int, s: Strategy) -> dict:
    system = SUMMARY_SYSTEM + (f"\n\n{s.nudge}" if s.nudge else "")
    budget = int(base * s.budget_multiplier)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": summary_user_prompt(text, "medium", "prose")},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": budget},
    }
    if s.think is not None:
        payload["think"] = s.think

    started = time.perf_counter()
    try:
        response = client.post(f"{url}/api/chat", json=payload, timeout=600)
    except Exception as exc:
        return {"budget": budget, "error": f"{type(exc).__name__}: {exc}"}
    elapsed = time.perf_counter() - started

    if response.status_code >= 400:
        return {
            "budget": budget,
            "error": f"HTTP {response.status_code}: {response.text.strip()[:200]}",
        }

    body = response.json()
    message = body.get("message") or {}
    raw = str(message.get("content", ""))
    cleaned = clean_model_output(raw)
    return {
        "budget": budget,
        "seconds": elapsed,
        "done_reason": body.get("done_reason"),
        "tokens": body.get("eval_count"),
        "separated_thinking": bool(str(message.get("thinking") or "").strip()),
        "raw": raw,
        "cleaned": cleaned,
        "verdict": verdict_for(cleaned),
    }


def verdict_for(cleaned: str) -> str:
    """What Ritarinn would decide about this text."""
    if not cleaned:
        return "NOTHING LEFT — the whole response was reasoning"
    if looks_like_reasoning(cleaned):
        if looks_like_english(cleaned):
            return "REASONING IN ENGLISH — refused, never shown"
        return "looks like reasoning but is Icelandic — retried once, then shown"
    if looks_like_english(cleaned):
        return "ANSWER IN ENGLISH — refused"
    return "OK — a usable Icelandic answer"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", required=True, help="the model to test, e.g. from `ollama list`")
    parser.add_argument("--url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--text-file", type=pathlib.Path, help="your own Icelandic text")
    parser.add_argument("--budget", type=int, default=LENGTH_TOKEN_BUDGET["medium"])
    parser.add_argument("--headroom", type=int, default=4096)
    parser.add_argument("--show-chars", type=int, default=300)
    args = parser.parse_args()

    host = httpx.URL(args.url).host
    if not is_loopback_host(host):
        print(f"Refusing to contact a non-loopback endpoint: {args.url}", file=sys.stderr)
        return 2

    text = args.text_file.read_text(encoding="utf-8") if args.text_file else SAMPLE_TEXT
    client = httpx.Client(trust_env=False)

    print("=" * 78)
    print(f"Ritarinn model diagnosis — {args.model}")
    print("=" * 78)
    print(f"endpoint         {args.url}")
    print(f"runtime version  {ollama_version(client, args.url)}")

    capabilities = model_capabilities(client, args.url, args.model)
    print(f"capabilities     {', '.join(capabilities) if capabilities else '(none reported)'}")
    if "thinking" in capabilities:
        print("                 ^ the runtime knows this model reasons and can separate it")
    else:
        print("                 ^ no 'thinking' capability: any reasoning lands in the answer,")
        print("                   so it has to be recognised and stripped by Ritarinn instead")
    print(f"source text      {len(text)} characters")
    print(f"base budget      {args.budget} tokens (+{args.headroom} headroom on retries)")
    print()

    results: list[tuple[Strategy, dict]] = []
    for strategy in build_strategies(args.headroom, args.budget):
        print("-" * 78)
        print(f"[{strategy.name}]  {strategy.explains}")
        outcome = run(client, args.url, args.model, text, args.budget, strategy)
        results.append((strategy, outcome))

        if "error" in outcome:
            print(f"  FAILED: {outcome['error']}")
            print()
            continue

        print(
            f"  budget {outcome['budget']} · generated {outcome['tokens']} tokens"
            f" · stopped: {outcome['done_reason']} · {outcome['seconds']:.1f}s"
        )
        print(f"  runtime separated the reasoning: {'YES' if outcome['separated_thinking'] else 'no'}")
        print(f"  {len(outcome['raw'])} chars raw -> {len(outcome['cleaned'])} chars after cleaning")
        print(f"  VERDICT: {outcome['verdict']}")
        shown = (outcome["cleaned"] or outcome["raw"])[: args.show_chars].replace("\n", " ")
        print(f'  text: "{shown}…"')
        print()

    print("=" * 78)
    working = [(s, o) for s, o in results if o.get("verdict", "").startswith("OK")]
    if not working:
        print("No strategy produced a usable Icelandic answer.")
        print()
        capped = [o for _, o in results if o.get("done_reason") == "length"]
        if capped:
            print("Every attempt hit its output cap, so the model never finished thinking.")
            print(f"Re-run with a bigger allowance, e.g. --headroom {args.headroom * 3}.")
            print("If that works, set it for the application:")
            print(f"    RITARINN_LLM_REASONING_HEADROOM={args.headroom * 3}")
        else:
            print("The model finished but did not produce Icelandic. Its Icelandic may")
            print("simply not be up to the task; the text above shows what it did write.")
        return 1

    best = working[0]
    print(f"Works: {', '.join(s.name for s, _ in working)}")
    print()
    if best[1]["budget"] > args.budget:
        needed = best[1]["budget"] - args.budget
        print("This model needs room to finish thinking. Set:")
        print(f"    RITARINN_LLM_REASONING_HEADROOM={max(needed, args.headroom)}")
    else:
        print("This model answers without extra room; Ritarinn's defaults suit it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
