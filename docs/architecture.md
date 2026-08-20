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
   ├── ByT5 neural correction        [not installed in v0.1]
   │
   └── Ollama (127.0.0.1:11434)      [detection only in v0.1]
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
│   │   ├── api.ts                typed client for the local backend
│   │   └── types.ts              mirrors the backend schemas
│   └── i18n/is.ts           every user-visible string
│
└── backend/ritarinn/
    ├── config.py            settings + the loopback refusals
    ├── main.py              app factory, CORS, security headers
    ├── api/                 HTTP routes only; no language logic
    ├── models/              Pydantic schemas (the wire contract)
    ├── text/offsets.py      UTF-16 ↔ code-point conversion
    └── services/
        ├── correction/      base.py · greynir.py · byt5.py · registry.py
        ├── llm/             base.py · ollama.py
        ├── summarization/   (Milestone 2)
        └── simplification/  (Milestone 2)
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

## 7. Model-agnosticism

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

## 8. What v0.1 deliberately does not do

- **No generation.** Samantekt and Á mannamáli need a local LLM. Rather than
  reaching for a hosted model, `/api/summarize` and `/api/simplify` return 501
  and say so — including that no cloud fallback is used.
- **No ByT5.** It reports itself as an installable option, not a missing
  feature. It never gates first startup.
- **No automatic model download.** Nothing multi-gigabyte is fetched on the
  user's behalf.
- **No remote providers.** None exist. The architecture leaves room for opt-in
  remote providers later (`AIProvider → Local | Remote`), and the privacy
  endpoint would report them, but nothing of the sort is implemented.
- **No persistence yet.** Drafts and settings are Milestone 5, in IndexedDB. No
  accounts, no sync, no server database.

## 9. Logging

Logs record what happened, never what was written: counts, durations, error
codes. A `NoDocumentTextFilter` on the root logger drops overlong messages as a
backstop, but the real defence is that no call site passes document text to the
logger. Prompts and model output are not logged either.

## 10. Security posture

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

## 11. Editor choice

CodeMirror 6, for stable document positions that survive edits, range
decorations, a real undo history, and correct paste/IME behaviour — all of which
issue review depends on. Writing a `contentEditable` editor would have meant
reimplementing exactly the parts that are hardest to get right. v0.1 needs plain
Icelandic text only, so no language mode or rich formatting is loaded, and DOCX
fidelity is out of scope.
