# Roadmap

Ritarinn is built incrementally, and each milestone has to work before the next
one depends on it. That is not the same as everything queueing behind one
question. Milestones 1 and 2 shipped a working proofreader and a working
generative pipeline; what remains is **two independent lines of work on two
independent model families**, and they run in parallel because neither is
waiting on the other's answer.

| | Generative models | Correction models |
|---|---|---|
| **What they do** | Samantekt, Á mannamáli | Yfirlestur |
| **Abstraction** | `LocalLLMProvider` | `CorrectionEngine` |
| **Runtime** | Ollama, on loopback | in-process (GreynirCorrect) or PyTorch (ByT5) |
| **Output** | a proposal, reviewed as a diff | individual reviewable issues |
| **Status** | comparative evaluation under way (Track A) | GreynirCorrect shipped; ByT5 installable now (Track B) |

The two abstractions are deliberately separate and must stay that way. ByT5 is a
**correction** model. It is not a general-purpose backend, it does not summarise
or rewrite, and nothing in Samantekt or Á mannamáli may come to depend on it.
Equally, whichever generative model wins Track A does not become the
proofreader. A change of model on one side must not be able to move the other.

Everything below inherits the guarantees the first two milestones established,
and none of this work may weaken them:

- **Local only.** All processing happens on the user's machine. There is no
  configuration that points inference at a remote host, and the correction
  providers never open a socket at all.
- **Explicit installation.** No model is downloaded on the user's behalf, at
  setup or at startup or mid-request. Every model is something the user chose.
- **Reviewable output.** Corrections are individual issues the user accepts or
  ignores. Generated text is a proposal shown beside the original.
- **Nothing is applied blindly.** No generated text and no corrected text ever
  replaces the user's document on its own — including a whole-sentence rewrite
  from a neural corrector, which is broken back down into word-level edits
  precisely so that it cannot.
- **Evidence, not preference.** No provider and no checkpoint becomes a
  permanent architectural dependency. Each is named in configuration, reached
  through an abstraction, and replaceable without touching application code.

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

## Milestone 2 — local generative AI ✅

Shipped in v0.2.

- `LocalLLMProvider.generate()` implemented for Ollama, alongside the
  availability detection from Milestone 1
- Configurable model name; still no automatic download
- `/api/summarize` — Lengd (Mjög stutt · Stutt · Miðlungs · Ítarleg), Form
  (Samfelldur texti · Punktar)
- `/api/simplify` — Markhópur (Almenningur · Sérfræðingar · Stjórnendur ·
  Viðskiptavinir · Ungmenni), Stíll (Einfalt mál · Hnitmiðað · Formlegt ·
  Hlutlaust · Vinalegt)
- Word-level diff with Samþykkja · Afrita · Hafna — never an automatic
  replacement, and accepting is a normal undoable edit
- Hierarchical summarization for long documents, chunking on paragraph and
  sentence boundaries and never mid-sentence; the original document is kept
  independent of any generated summary
- Generated Icelandic optionally passed back through GreynirCorrect, showing
  issues without altering the text

Prompts are written in Icelandic and instruct the model to preserve factual
meaning, numbers, names, dates and important qualifications; to invent nothing;
to preserve uncertainty; and to output Icelandic.

**Verified** end to end in a browser against a real local model, with every
network request confirmed to stay on loopback.

### Deferred from this milestone

- **Streaming.** Results appear only when complete. On CPU-only hardware a long
  summary is a visible wait — measured at roughly 10 tokens/second on 4 cores —
  with a cancel button but no progressive output. Streaming would improve this
  and changes no interfaces.
- **Model management from the UI.** Choosing a model is a configuration value
  (`RITARINN_LLM_MODEL`); the Stillingar tab reports what is installed but
  cannot yet select or install a model. That belongs with Milestone 5's
  local-model management.

---

# Track A — comparative evaluation of local generative models

**In progress. Nothing else is waiting on it.** Milestone 2 built the pipeline;
nothing in it judges whether a model's Icelandic is good enough to put in front
of a user. Ritarinn ships no default model and will not recommend one until this
track answers the question with evidence.

No model family is privileged. Candidates include Ministral, Qwen, Gemma,
Mistral and Icelandic fine-tunes, and the answer is expected to change as models
do — which is why the model is a configuration value and
`tests/backend/test_llm_provider.py::test_provider_is_model_agnostic` fails if
any family name reaches the provider's executable code.

Record for each candidate: model, origin, licence, download size, RAM/VRAM
requirement, Icelandic quality, summarization quality, plain-language quality,
speed.

Evaluate on an Icelandic corpus built for this project — factual preservation,
Icelandic fluency, retention of qualifications, concision, hallucination rate;
and for rewriting: natural Icelandic, meaning preservation, grammaticality,
reduction of bureaucratic language, preservation of legal/scientific nuance.

Only then recommend a default, and record checksums for the recommended
downloads.

## Preliminary testing snapshot

**This is a snapshot of testing performed so far, not a benchmark.** It is a
working record kept to make the current state of the question visible; it is not
a result, and no decision should be taken on it alone.

| Model | Understanding | Factual accuracy | Grammar | Natural Icelandic | Potential benefit from ByT5 |
|---|---:|---:|---:|---:|---|
| **Ministral 3 14B** | **8/10** | **7/10** | **5/10** | **5/10** | High |
| **Qwen** | 7/10 | 7/10 | 4/10 | 4/10 | High |
| **Ministral 3 8B** | 6/10 | 4/10 | 3/10 | 2/10 | Medium–low |
| **Gemma 3 4B** | 6/10 | 3/10 | 2/10 | 1/10 | Low |

How to read it:

- The scores summarise the testing done so far, and nothing beyond that.
- **Higher is better** on all four scored columns.
- **"Potential benefit from ByT5" is a working hypothesis**, not a measurement.
  It is a guess about how much a separate correction pass might help a given
  model's output. It is not a ByT5 score, not an accuracy figure, and not a
  confidence value, and it must not be presented as one.
- **The table is why Track B starts now.** The leading models are close to each
  other on understanding and factual accuracy — the things a correction pass
  cannot fix — while Icelandic grammar and naturalness are the weakest columns
  for every candidate, including the leaders. That is the shape of a problem a
  dedicated Icelandic correction model might address, and it is not a reason to
  wait for Track A to finish before finding out.
- **ByT5 has to be evaluated on its own.** Nothing here says it improves any
  model, and nothing may claim that until Track B has measured it against text
  these models actually produced.
- **A recommendation still needs much more than this.** Before any model is
  recommended as a default: a documented corpus, the exact prompts, exact model
  versions, runtime settings, the hardware it ran on, repeated runs rather than
  single impressions, and scoring criteria defined in advance by someone other
  than the person reading the output.
- **"Qwen" and "Ministral 3" are family names, not checkpoints.** Replace them
  with exact identifiers (`qwen3:14b`, a specific quantisation, a specific
  Ollama tag) as soon as the details are confirmed — a family name is not
  reproducible.
- **Update this table; do not copy it.** One table, revised as testing
  continues. A second copy somewhere else is a second answer that will disagree
  with this one.

---

# Track B — ByT5 for context-sensitive Icelandic correction

**Installation and integration: done. Evaluation: not started.** This track runs
alongside Track A, on a different model family, for a different job.

`mideind/yfirlestur-icelandic-correction-byt5` (Miðeind ehf., CC BY-SA 4.0,
fine-tuned from `google/byt5-base`, Apache-2.0, ~2.3 GB) rewrites an Icelandic
sentence into a corrected one. It reads the sentence in context, so it can see
things a rule-based engine cannot; it also reports no error codes, no
explanations and no confidence, and it will sometimes be wrong. Both halves of
that shape the integration.

**Licence: verified, with one open question.** The licence gate was a hard
precondition for writing any of this, and the evidence — repository tag, model
card front matter, base-model configuration match, file sizes — is recorded in
`THIRD_PARTY_NOTICES.md` section 1. What remains unresolved is whether
share-alike reaches *text the model produces*; that is flagged in section 6 and
is not represented as settled.

## Stage 1 — installation and integration ✅

- A correction provider behind the existing `CorrectionEngine` abstraction, with
  everything model-shaped — loading, tokenization, inference, device selection,
  the checkpoint identifier — inside `services/correction/byt5.py`. No
  Transformers or PyTorch object reaches a route, a schema or the editor, and a
  test fails if one starts to.
- Selected through configuration (`RITARINN_CORRECTION_ENGINES`,
  `RITARINN_BYT5_*`), never through a code change. The checkpoint is a setting,
  so replacing it is a setting change too.
- Optional dependencies in `backend/requirements-byt5.txt`, absent from the
  default install. PyTorch does not arrive with `./setup`.
- Explicit provisioning: `python scripts/install_byt5.py`. The application loads
  with downloads disabled, so neither startup nor a request can fetch weights —
  a missing model is reported as a missing model, in Icelandic, with the command
  that fixes it.
- Local model paths supported and preferred, so an installation is reproducible
  and works offline afterwards.
- Loaded once — at an intentional initialization step when enabled, lazily
  otherwise — then reused for the process lifetime. Never per sentence, never
  per request.
- Device configurable, auto-detected otherwise, CPU always supported.
- Sentence-by-sentence processing, as the model was trained.
- **The whole-sentence rewrite is diffed against the original and converted into
  word-level issues.** The document is never replaced. Provenance travels on the
  existing `source` and `scope` fields, so the sidebar attributes a finding
  without string-matching.
- No fabricated confidence. The model reports no score and no category, so its
  issues carry none — they land in `unknown`, the same treatment an
  unrecognised GreynirCorrect code gets, rather than being guessed into
  "spelling" or "grammar".
- GreynirCorrect is untouched and remains the default. An unavailable ByT5 in a
  configured selection is skipped, not fatal; proofreading carries on.

## Stage 2 — evaluation (not started)

The question Stage 1 exists to make answerable: **is this model's Icelandic
correction actually better, and better at what?** Nothing so far measures that,
and nothing may claim it.

- Build a correction evaluation set alongside `corpus/`, covering the error
  types GreynirCorrect handles well (token-level spelling, compound errors,
  case government) and the ones it cannot (context-dependent word choice,
  agreement across a clause, sentences that fail to parse).
- Measure precision and recall per error type against both providers
  separately — where each is right, where each is wrong, and crucially where
  ByT5 "corrects" text that was already correct, which is the failure mode a
  rule-based engine does not have.
- Record cost honestly: load time, memory resident, and seconds per page on CPU
  and on GPU. A correction that arrives after the user has moved on is not a
  usable correction.
- Evaluate it on output from the Track A models as well as on human-written
  text. The hypothesis in Track A's table is that a correction pass helps a
  strong-but-ungrammatical generative model; that is a claim to test, not to
  assume.
- Record weight checksums, and pin the installation to a revision.

Only then does a recommendation become possible, and even then it stays a
recommendation: a configuration default, not an architectural commitment.

## Stage 3 — categories, and hybrid mode (not started)

- ByT5's issues currently carry no category. Miðeind publishes a companion
  classifier, `mideind/yfirlestur-icelandic-classification-byt5`, which is the
  obvious candidate for supplying one — subject to the same licence gate, and to
  evidence that its labels are better than no label at all.
- Optional hybrid mode combining Greynir's grammatical categories and
  explanations with ByT5's context-sensitive corrections, and collapsing the
  duplicate findings the two produce for the same span today.

Where both providers independently agree on a span, the UI may say so.
**Agreement is reported as agreement.** It is not converted into a confidence
percentage, and two engines concurring is not evidence of a probability.

---

# Milestone 5 — polish

Independent of both tracks, and not waiting on either.

IndexedDB drafts, settings, improved categories, performance, keyboard
shortcuts, first-run experience, local-model management, a privacy page, better
onboarding, and **Eyða staðbundnum gögnum**.

# Later, deliberately not now

- **Speech recognition** (`services/speech/`) — kept in mind architecturally
- **Translation** (`services/translation/`) — kept in mind architecturally
- **Optional remote providers** — if ever added: opt-in, disabled by default,
  clearly labelled, user's own key, explicit that text leaves the device,
  reflected in the privacy indicator, and fully disableable

The current project is strictly the Icelandic writing assistant.
