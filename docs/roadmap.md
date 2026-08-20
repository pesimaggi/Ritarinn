# Roadmap

Ritarinn is built incrementally. Each milestone has to work before the next
one starts.

## Milestone 1 — working local proofreader ✅

Shipped in v0.1.

- Repository structure, FastAPI backend, React/TypeScript frontend
- CodeMirror 6 editor with issue underlining and click-to-select
- GreynirCorrect integration and `/api/proofread`
- Structured, individually reviewable issues; accept and ignore
- Localhost-only execution, enforced by configuration and tests

**Success criterion**, met: start the application, open it in a browser, paste
Icelandic text containing errors, press "Yfirlesa", see issues underlined,
click one and accept the proposed correction — while the text never leaves the
computer.

## Milestone 2 — local generative AI

- `LocalLLMProvider` implementation for Ollama (`generate`), availability
  detection is already in place
- Configurable model name; no automatic download
- `/api/summarize` — Lengd (Mjög stutt · Stutt · Miðlungs · Ítarleg), Form
  (Samfelldur texti · Punktar)
- `/api/simplify` — Markhópur (Almenningur · Sérfræðingar · Stjórnendur ·
  Viðskiptavinir · Ungmenni), Stíll (Einfalt mál · Hnitmiðað · Formlegt ·
  Hlutlaust · Vinalegt)
- Diff view with Samþykkja · Afrita · Hafna — never an automatic replacement
- Hierarchical summarization for long documents: chunk on paragraph/section
  boundaries, summarise each chunk, then combine. Never split mid-sentence, and
  keep the original document independent of any generated summary.
- Optionally pass generated Icelandic back through GreynirCorrect, showing
  potential issues without silently altering meaning

Prompts are written in Icelandic and instruct the model to preserve factual
meaning, numbers, names, dates and important qualifications; to invent nothing;
to preserve uncertainty; and to output Icelandic.

Verify with outbound internet access blocked.

## Milestone 3 — evaluate model alternatives

Qwen is **not** the default by default. Candidates to test include Qwen,
Mistral, Gemma and Icelandic fine-tunes.

Record for each: model, origin, licence, download size, RAM/VRAM requirement,
Icelandic quality, summarization quality, plain-language quality, speed.

Evaluate on an Icelandic corpus built for this project — factual preservation,
Icelandic fluency, retention of qualifications, concision, hallucination rate;
and for rewriting: natural Icelandic, meaning preservation, grammaticality,
reduction of bureaucratic language, preservation of legal/scientific nuance.

Only then recommend a default, and record checksums for the recommended
downloads.

## Milestone 4 — neural Icelandic correction (ByT5)

- Explicit installation; the model stays loaded after startup
- Sentence-by-sentence processing where appropriate
- Diff candidates against the original and convert differences into reviewable
  issues — never a blind replacement
- Optional hybrid mode combining Greynir's grammatical categories and
  explanations with ByT5's context-sensitive corrections

Where both engines independently agree, the UI may say so. Agreement is
reported *as agreement*; it is not converted into a confidence percentage.

The seam exists: `services/correction/byt5.py` and the `scope`/`source` fields
are already part of the issue model. Its licence must be established first —
see `THIRD_PARTY_NOTICES.md`, section 6.

## Milestone 5 — polish

IndexedDB drafts, settings, improved categories, performance, keyboard
shortcuts, first-run experience, local-model management, a privacy page, better
onboarding, and **Eyða staðbundnum gögnum**.

## Later, deliberately not now

- **Speech recognition** (`services/speech/`) — kept in mind architecturally
- **Translation** (`services/translation/`) — kept in mind architecturally
- **Optional remote providers** — if ever added: opt-in, disabled by default,
  clearly labelled, user's own key, explicit that text leaves the device,
  reflected in the privacy indicator, and fully disableable

The current project is strictly the Icelandic writing assistant.
