# Ritarinn — architecture

Ritarinn is a local-first Icelandic writing assistant. This document explains
how it is put together and, more importantly, *why* the boundaries fall where
they do.

## 1. The constraint everything else follows from

> The default installation processes the user's text entirely on the user's own
> computer.

This is a structural property, not a promise in a privacy policy. The system is
built so that external communication is technically unnecessary during normal
use: once dependencies are installed, proofreading works with the machine's
network interface switched off.

Consequences that show up throughout the codebase:

- the backend binds to `127.0.0.1` and **refuses to start** on any other address
  unless explicitly overridden (`backend/ritarinn/config.py`);
- CORS is an explicit loopback allowlist; a wildcard is a startup error;
- the only outbound endpoint the backend may hold is a loopback inference
  runtime, and a non-loopback value is a startup error with no override;
- the frontend loads no remote script, style or font, so the interface renders
  identically offline;
- `/api/privacy/status` reports *computed* facts, so the "Staðbundið" indicator
  cannot claim more than is true.

## 2. Runtime topology

```text
Browser (127.0.0.1:5173)
   │  same-origin /api requests
   ▼
Local backend (127.0.0.1:8756)
   │
   ├── GreynirCorrect ──► GreynirEngine ──► BÍN (in-process, no network)
   │
   ├── ByT5 neural correction        [not installed]
   │
   └── Ollama (127.0.0.1:11434) ──► a model already on disk
```

There is no path of the form *user text → internet → AI vendor*, and no
configuration that creates one.

In development, Vite proxies `/api` to the backend, so the browser makes no
cross-origin request at all. The CORS allowlist covers the case of running a
production build directly against the backend.

## 3. Layering

Separation is maintained between the editor, proofreading, Icelandic NLP,
neural correction, generative AI, the model runtime, and storage. Each layer
knows only the one beneath it.

```text
ritarinn/
├── frontend/src/
│   ├── components/          React UI
│   ├── lib/
│   │   ├── issueDecorations.ts   editor state: anchoring, accept, ignore
│   │   ├── proofreadScheduler.ts debounce + ordering guarantees
│   │   ├── useGeneration.ts      run/cancel a local model, ordering guarantees
│   │   ├── diff.ts               word-level diff for reviewing rewrites
│   │   ├── editorKeymap.ts       key bindings
│   │   ├── api.ts                typed client for the local backend
│   │   └── types.ts              mirrors the backend schemas
│   └── i18n/is.ts           every user-visible string
│
└── backend/ritarinn/
    ├── config.py            settings + the loopback refusals
    ├── main.py              app factory, CORS, security headers
    ├── api/                 HTTP routes only; no language logic
    ├── models/              Pydantic schemas (the wire contract)
    ├── text/
    │   ├── offsets.py       UTF-16 ↔ code-point conversion
    │   ├── chunking.py      structure-aware document splitting
    │   └── language.py      is this an Icelandic answer, or the model thinking?
    └── services/
        ├── correction/      base.py · greynir.py · byt5.py · registry.py
        ├── llm/             base.py · ollama.py
        ├── generation/      prompts.py · base.py · postprocess.py
        ├── summarization/   service.py  (hierarchical)
        └── simplification/  service.py  (chunk-wise)
```

The API layer never imports a concrete engine — it goes through
`EngineRegistry` — so adding ByT5 or a hybrid engine is a registration change,
not a routing change.

## 4. Character offsets: the decision worth understanding

This is where a proofreader quietly corrupts documents if it gets things wrong.

**The problem.** Python indexes strings by Unicode code point. JavaScript — and
therefore CodeMirror, and every browser API a range is handed to — indexes by
UTF-16 code unit. The two agree across the whole Icelandic alphabet (á é í ó ú
ý þ æ ö ð all sit in the Basic Multilingual Plane) and diverge the moment a
document contains an astral-plane character such as an emoji, where Python
counts 1 and JavaScript counts 2. A single 🎉 in the first paragraph would shift
every later underline one character to the left.

**The decision.** The backend converts once, at the boundary, and the API emits
**UTF-16 code unit offsets**. The response states this in an `offsetUnit` field
rather than leaving clients to assume it.

**Why this way round.** The consumer is a browser editor, so offsets arrive
ready to use and the frontend needs no conversion code at all. Concentrating
the conversion in one place in Python makes it something that can be tested
exhaustively — which it is, against ground truth, from *both* languages
(`tests/backend/test_offsets.py`, `frontend/src/lib/text.test.ts`).

**Getting from GreynirCorrect to offsets.** GreynirCorrect annotates *token
index* spans within a sentence, not character positions. Two upstream properties
bridge the gap:

1. each token keeps its verbatim source text in `token.original`, including the
   whitespace that preceded it, so concatenating tokens reproduces the input;
2. annotation indices refer to the sentence's own token list.

So the engine walks the token stream once, accumulating character offsets, and
resolves each annotation against that. Property (1) holds exactly, except that
whitespace trailing the very end of the document is dropped — which cannot
shift any earlier offset. Because the whole scheme rests on this, it is
asserted directly rather than assumed.

**Trimming.** A token's source text carries the whitespace before it, so a raw
span would underline the preceding space — or the paragraph break — and
accepting the correction would swallow it. Spans are trimmed to the word.

## 5. Issue positions while the user is typing

Issues are computed against a snapshot, and the user keeps typing. Two failure
modes follow, both of which put confidently wrong underlines on screen:

**Stale results.** A slow response for old text arriving after a fast response
for new text. Aborting a superseded request is not enough — it can already be
past the point of cancellation — so every run carries a sequence number and only
the newest may publish (`proofreadScheduler.ts`).

**Drifting anchors.** Issues live in CodeMirror state and are mapped through
every subsequent change. When an edit actually *touches* an issue's range, the
issue is dropped rather than stretched: the text it described no longer exists.
A missing underline for 800 ms is a much smaller problem than a wrong one.

## 6. Issue model

Every engine — deterministic, neural, or generative — emits the same
`WritingIssue` shape, so the editor never learns which engine found what.

Three fields deserve comment:

- **`code`** is the engine's own code (`S004`, `P_WRONG_CASE_þgf_þf`), passed
  through verbatim. Ritarinn invents no codes. `category` and `family` are a
  documented grouping over those codes (`docs/error-codes.md`), and an
  unrecognised code becomes `unknown` rather than a guess.
- **`confidence`** is left unset unless an engine reports a genuine score.
  GreynirCorrect does not, so Greynir issues never carry one. When Milestone 4
  adds hybrid mode, agreement between two engines will be reported *as
  agreement*, not converted into a percentage.
- **`scope`** distinguishes an issue whose span *is* the problem from one that
  describes the whole sentence containing it (unparseable, very long, not
  Icelandic). Sentence-scope issues are listed in the sidebar but not
  underlined, because a line under an entire paragraph buries the word-level
  issues inside it.

`severity` comes from GreynirCorrect's own `/w` warning marker — upstream's
distinction, not a heuristic of ours.

## 7. Generation: chunking, faithfulness, review

Summarization (Samantekt) and plain-language rewriting (Á mannamáli) both run a
local model over the user's document. Three problems have to be solved before
that is safe to offer.

**The document is bigger than the context.** Long text is divided in
`text/chunking.py`, which splits on structure and never mid-sentence: paragraphs
first, then sentences within an over-long paragraph, and only then — for a
single sentence longer than the budget — a hard cut. Sentence boundaries come
from Miðeind's tokenizer, not a regular expression, because Icelandic legal
prose is dense with abbreviations: `sbr. 3. mgr. 12. gr. laga nr. 7/1998.` is
one sentence, and splitting on full stops turns it into six fragments with no
subject. The chunker's central property is that it loses nothing — every
character lands in exactly one chunk, asserted directly in the tests.

The two features then diverge, because their outputs differ in kind:

- **Summarization is hierarchical.** Each chunk is summarised on its own (told
  it is a fragment, so it does not conclude from evidence it cannot see), then a
  combine pass merges the parts. Short documents skip straight to one pass.
- **Rewriting is not.** Each chunk is rewritten and the results are joined in
  order. A combine pass would be free to drop material, which is exactly what a
  rewrite must not do.

**A model will invent things.** The shared faithfulness rules in
`services/generation/prompts.py` are stated once and reused: do not add
information, do not fill gaps from general knowledge, keep every number, date,
name and legal citation, and preserve uncertainty rather than resolving it.
Prompts are written in Icelandic — a model asked in English to produce Icelandic
tends to translate rather than compose, and the register slips.

**The output must be capped.** An uncapped reasoning model on a CPU runs until
it hits a timeout and the user sees a hang rather than a result. Every request
carries a `num_predict` derived from the requested length, and a response that
stopped at the cap is reported as `truncated` so the user knows the text may end
mid-sentence.

Local models are also inconsistent about returning bare prose, so
`clean_model_output` strips two whole-response artefacts: chain-of-thought
blocks from reasoning models, and a markdown fence wrapped around the entire
answer. Markdown *inside* the text is left alone — the user may have asked for
bullet points.

### When the model returns something that is not an answer

Stripping tags is not enough, because the worst case carries no tags. Ritarinn
sends the runtime's `think: false` flag, but it does not always take effect: an
older Ollama drops an unknown field, and a chat template that opens the
reasoning block in the assistant prefix means the model never generates an
opening tag at all. Cut that response off at the output cap, before the closing
tag, and what comes back is a chain of thought with nothing whatsoever marking
it as one. Tag stripping cannot see it, and the user gets the model's private
notes about them in place of their summary.

So the response is judged on content as well as on markup, in `text/language.py`:

- **a chain of thought** — the response opens by restating the request rather
  than by saying something about the document;
- **the wrong language** — English function words at a density Icelandic never
  reaches, together with no Icelandic orthography.

Both detectors are deliberately one-sided. Rejecting a real summary costs the
user a local generation they already waited through, so a false positive is
expensive: Icelandic that merely lacks the marker words is never rejected, and
only text that positively looks like English is. `tests/backend/test_language.py`
weights its fixtures accordingly — quoted English inside Icelandic, first-person
rewrites, bullet lists and single sentences all have to survive.

A response that fails either check is retried **once**. The retry changes two
things at once, because there are two kinds of reasoning model and suppression
reaches only one of them:

- **the chat-template reasoning switch**, plus an explicit Icelandic
  instruction, appended to the system prompt. This works for the model families
  that have such a switch, and is also the fix when the first attempt was simply
  in English.
- **`Settings.llm_reasoning_headroom` of extra output budget.** A template that
  opens the reasoning block unconditionally will reason whatever it is told, and
  such a model can still write a good summary — it just has to think first.
  Given room to finish it closes the block, and `clean_model_output` strips the
  trace on the tag as it always could. Starved of it, the response is cut off
  mid-thought and there is no tag to strip, which is the failure this path
  exists for. It is a setting rather than a constant because how much room a
  model needs is a property of that model, and nothing here can know it.

Doing both is what makes a reasoning model usable rather than merely diagnosed.
Neither is applied speculatively — only to a model that has already demonstrated
the problem — because a second generation on a CPU is a real cost; and the
headroom is free when the switch does work, since a cap is a ceiling and not a
target. Both are then remembered against the model name for the life of the
provider, so a long document pays for the discovery once rather than on every
chunk, and choosing a different model starts clean.

If the retry fails too, what happens depends on the language, because that is
what the reasoning check is actually certain about.

**English is refused.** A chain of thought in English is not a summary of an
Icelandic document under any reading, and neither is an English answer. The
request fails with an Icelandic explanation of which of the two went wrong and
what the user can do about it. There is no version of this feature where a
model's reasoning belongs in someone's document.

**Icelandic is never refused.** The same opening in Icelandic is ambiguous —
*"Allt í lagi, hér kemur samantektin"* is a summary with a conversational first
line, and nothing in the first line distinguishes the two. So it is retried like
anything else, and if the retry produces nothing better it is shown rather than
raised, carried on `_NoAnswer.fallback`. The asymmetry is deliberate: a false
positive here costs the user a generation they already waited through, on a
guess the detector was never confident in, and they can see in a second whether
the text is what they asked for.

The same round trip also drops the `think` flag and retries if the runtime
rejects it outright, which some versions do for a model with no thinking
capability. The flag is an optimisation, not a requirement, and a runtime that
refuses it must not cost the user the feature.

### Icelandic post-processing of generated text

Generated Icelandic is optionally passed back through GreynirCorrect, which
combines the model's semantic ability with real Icelandic linguistic analysis.
In practice this catches a lot: a 4B model will write `taksins` for `talsins`,
and GreynirCorrect says so.

What this must never do is apply those corrections. A summary is a claim about
meaning, and silently rewriting it on the strength of a grammar rule could
change that claim. The issues are shown; the user decides — the same contract as
the proofreading tab.

### Review before anything is applied

No generated text reaches the document on its own. The browser shows a proposal
beside the original — a word-level diff for rewrites, side by side for summaries
(a summary is a new artifact, so a word diff against the source is noise) — with
Samþykkja, Afrita and Hafna. Accepting dispatches one ordinary CodeMirror
transaction, so Ctrl+Z undoes it like any other edit, which is what makes trying
a rewrite safe.

## 8. Model-agnosticism

Generative features are written against `LocalLLMProvider.generate(...)`, never
against a model family. The model is a configuration value. This matters
because Icelandic quality differs substantially between model families and will
keep changing; the recommended default should be decided by Icelandic
evaluation (Milestone 3), not by generic benchmarks.

The abstraction keeps three things apart that are easy to conflate:

| | |
|---|---|
| **model** | the weights — what produces the text |
| **runtime** | Ollama — what executes them |
| **provider** | Ritarinn's adapter for a runtime |

A model made by a given company does not imply talking to that company.
Ritarinn only loads weights already on disk, through a runtime on loopback. A
locally downloaded Qwen model runs without contacting Alibaba; a model is given
no network, shell, or filesystem access.

`tests/backend/test_llm_provider.py::test_provider_is_model_agnostic` fails if
any model family is named in the provider's executable code.

## 9. What this version deliberately does not do

- **No generation without a local model.** Samantekt and Á mannamáli need a
  local model. If none is configured they return 503 and say so; there is no
  hosted fallback, and no configuration that could create one.
- **No streaming.** Results appear only when complete, since a partial summary
  is not reviewable. On slow hardware this means a visible wait, with a cancel
  button. Streaming is noted in the roadmap.
- **No ByT5.** It reports itself as an installable option, not a missing
  feature. It never gates first startup.
- **No automatic model download.** Nothing multi-gigabyte is fetched on the
  user's behalf.
- **No remote providers.** None exist. The architecture leaves room for opt-in
  remote providers later (`AIProvider → Local | Remote`), and the privacy
  endpoint would report them, but nothing of the sort is implemented.
- **No persistence yet.** Drafts and settings are Milestone 5, in IndexedDB. No
  accounts, no sync, no server database.

## 10. Logging

Logs record what happened, never what was written: counts, durations, error
codes. A `NoDocumentTextFilter` on the root logger drops overlong messages as a
backstop, but the real defence is that no call site passes document text to the
logger. Prompts and model output are not logged either.

## 11. Security posture

- Dependencies pinned exactly, with a resolved lock file
  (`backend/requirements.lock.txt`); enforced by test.
- Model formats: GGUF and Safetensors preferred; loading arbitrary
  Pickle/Python model objects is avoided where a safer format exists.
- The frontend ships a strict Content Security Policy that forbids every remote
  origin outright rather than listing trusted ones. The API sets
  `default-src 'none'` since it serves only JSON.
- Engine explanations may contain `<a>` markup; it is stripped and rendered as
  text. Local input is still untrusted input.
- Ollama detection uses `trust_env=False`, so an ambient proxy variable cannot
  pull loopback traffic off the loopback interface.

## 12. Editor choice

CodeMirror 6, for stable document positions that survive edits, range
decorations, a real undo history, and correct paste/IME behaviour — all of which
issue review depends on. Writing a `contentEditable` editor would have meant
reimplementing exactly the parts that are hardest to get right. v0.1 needs plain
Icelandic text only, so no language mode or rich formatting is loaded, and DOCX
fidelity is out of scope.
