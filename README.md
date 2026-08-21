# Ritarinn

**Staðbundinn íslenskur ritaðstoðarmaður.** Opinn hugbúnaður sem les yfir
íslenskan texta á þinni eigin tölvu — enginn texti fer í skýjaþjónustu.

*A local-first, open-source Icelandic writing assistant. Your text is
proofread on your own computer and is never sent to a cloud service.*

> **Version 0.2 — Milestone 2.** Proofreading (Yfirlestur), summarization
> (Samantekt) and plain-language rewriting (Á mannamáli) all work, entirely on
> your own machine. The generative features need a local model through Ollama;
> without one the application says so rather than quietly using a hosted one.
>
> **No default model is recommended yet.** Choosing one requires evaluating
> Icelandic quality properly — that is Milestone 3.
>
> "Ritarinn" is a temporary working name.

---

## Hvað þetta gerir / What it does

### Yfirlestur — proofreading

Skrifaðu eða límdu íslenskan texta, smelltu á **Yfirlesa**, og fáðu einstakar
ábendingar um stafsetningu, málfræði, greinarmerki og málfar. Hver ábending er
skoðuð sérstaklega — þú **Samþykkir** eða **Hunsar**.

Write or paste Icelandic text, press **Yfirlesa**, and get individual
suggestions covering spelling, grammar, punctuation and style. Each one is
reviewed on its own — you accept or ignore it.

### Samantekt — summarization

Draga saman texta með staðbundnu mállíkani. Veldu **Lengd** (Mjög stutt · Stutt
· Miðlungs · Ítarleg) og **Form** (Samfelldur texti · Punktar). Langur texti er
brotinn upp á málsgreina- og setningamörkum og aldrei í miðri setningu.

### Á mannamáli — plain language

Umrita texta fyrir tiltekinn **Markhóp** (Almenningur · Sérfræðingar ·
Stjórnendur · Viðskiptavinir · Ungmenni) í völdum **Stíl** (Einfalt mál ·
Hnitmiðað · Formlegt · Hlutlaust · Vinalegt). Sérstaklega ætlað fyrir
stofnanamál, lagatexta og fræðilegan texta.

**Ritarinn breytir aldrei textanum þínum af sjálfsdáðum.** Allur texti frá
mállíkani er sýndur til hliðar við upprunalega textann, með orðamun þar sem það
á við, og þú velur **Samþykkja**, **Afrita** eða **Hafna**. Samþykkt breyting er
venjuleg breyting sem má afturkalla.

*Generated text is never applied automatically. It is shown beside your original
— with a word-level diff for rewrites — and you accept, copy or discard it.
Accepting is an ordinary undoable edit.*

Prompts instruct the model to preserve numbers, names, dates, legal citations
and stated uncertainty, and to invent nothing. Generated Icelandic can
optionally be run back through GreynirCorrect, which reports problems in the
model's output **without altering it**.

---

## Uppsetning / Installation

**Kröfur / Requirements:** Python 3.10+, Node.js 18+. Works on macOS, Linux and
Windows.

### macOS / Linux

```bash
git clone <repository-url>
cd Ritarinn
./setup
./start
```

### Windows (PowerShell)

```powershell
git clone <repository-url>
cd Ritarinn
.\setup.ps1
.\start.ps1
```

Opnaðu svo / then open:

**http://127.0.0.1:5173**

`setup` creates a Python virtual environment, installs dependencies, verifies
that GreynirCorrect actually corrects Icelandic, and reports whether Ollama is
present. **It downloads no language model.** Nothing multi-gigabyte is fetched
on your behalf.

### Samantekt og Á mannamáli / the generative features

These need a local model. Ritarinn does not download one for you.

```bash
# Install Ollama (https://ollama.com), then choose a model yourself:
ollama pull <model>

# Point Ritarinn at it:
RITARINN_LLM_MODEL=<model> ./start
```

Ollama is a *runtime*, not a model, and Ritarinn only ever talks to it on
`127.0.0.1`. Ollama's hosted services are not used and cannot be configured.

**Which model?** Ritarinn deliberately does not say yet. Icelandic quality
varies enormously between model families, and small models are noticeably weak
at it — during development `gemma3:4b` wrote *taksins* for *talsins* on a
two-sentence notice. Picking a recommended default is Milestone 3, and it should
be decided by Icelandic evaluation rather than by generic benchmarks. Expect to
need a larger model than you would for English.

Two failure modes are common enough to be worth knowing about before you choose.

*A small model invents Icelandic words.* Inflection and compounding give it many
plausible-looking ways to be wrong, and it takes them: forms that follow the
shape of the language without being words. Ritarinn cannot fix this — the fix is
a better model — but **Lesa yfir útkomuna** runs the generated text back through
GreynirCorrect and lists what it flags, so invented words are visible rather than
merely convincing. Leave it on.

*A reasoning model returns its thinking instead of an answer.* Ritarinn asks the
runtime to switch reasoning off, but the switch does not always arrive: an older
Ollama drops the flag, and some chat templates open the reasoning block
themselves, so the model never emits a tag that could be stripped. If the output
cap then arrives mid-thought, the response is a chain of thought with nothing at
all marking it as one.

Ritarinn recognises such a response by how it reads — English function words at
a density Icelandic never reaches, or an opening that restates the request — and
never shows it. It retries once with the reasoning switched off explicitly, and
if that also fails it says so instead of pasting the model's notes into your
document. The same check catches a model that summarises correctly but answers
in English.

If you keep hitting it, upgrade Ollama first (newer versions honour the
reasoning flag), and otherwise pick a model that does not reason aloud. The
detection is a backstop, not a substitute: every retry is a second local
generation, and on a CPU you will feel it.

<details>
<summary>Manual installation</summary>

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
.venv/bin/pip install -e backend

cd frontend && npm install && cd ..

# Two terminals:
.venv/bin/python -m ritarinn        # backend  → 127.0.0.1:8756
cd frontend && npm run dev          # frontend → 127.0.0.1:5173
```

On Windows use `.venv\Scripts\python.exe` and `.venv\Scripts\pip.exe`.
</details>

---

## Persónuvernd / Privacy

Þetta er ekki loforð í skilmálum — það er byggt inn í hugbúnaðinn:

- bakendinn hlustar aðeins á `127.0.0.1` og **neitar að ræsa sig** á öðru vistfangi;
- CORS leyfir aðeins staðbundnar vefslóðir; algildisstafur er ræsivilla;
- viðmótið sækir ekkert af neti — hvorki letur, skriftur né tölfræði;
- engin fjarlæg gervigreindarþjónusta er til staðar í uppsetningunni.

Prófaðu sjálf/ur: **aftengdu tölvuna frá netinu og notaðu Ritarann.** Allt
virkar.

*Structural, not a policy promise. Verify it by disconnecting from the network
and using the application — everything works.* The backend reports computed
facts about its own configuration:

```bash
curl http://127.0.0.1:8756/api/privacy/status
```

The **Staðbundið** badge in the interface is derived from that response, so it
cannot claim more than is true. Details: [`docs/privacy.md`](docs/privacy.md).

---

## Byggt á íslenskri máltækni / Built on Icelandic language technology

Ritarinn is an interface and integration layer. The Icelandic linguistic work
belongs to others, and this project exists to build an open alternative — not
to obscure where the foundation comes from.

- **[GreynirCorrect](https://github.com/mideind/GreynirCorrect)** — Miðeind ehf.
  Spelling and grammar analysis; all of v0.1's proofreading.
- **[GreynirEngine](https://github.com/mideind/GreynirEngine)** — Miðeind ehf.
  The Icelandic parser.
- **[BinPackage](https://github.com/mideind/BinPackage)** — Miðeind ehf.
  Morphology, wrapping BÍN.
- **[Tokenizer](https://github.com/mideind/Tokenizer)** and
  **[Icegrams](https://github.com/mideind/Icegrams)** — Miðeind ehf.

The morphological data is *Beygingarlýsing íslensks nútímamáls* (BÍN), used
under CC BY 4.0:

> Beygingarlýsing íslensks nútímamáls.
> Stofnun Árna Magnússonar í íslenskum fræðum.
> Höfundur og ritstjóri Kristín Bjarnadóttir.

Full details, licences and open questions:
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

---

## API

Öll vistföng eru staðbundin / all endpoints are local:

| Endpoint | |
|---|---|
| `GET /api/health` | Liveness and readiness |
| `POST /api/proofread` | Proofread text, return individual issues |
| `GET /api/models/status` | What is installed and ready |
| `GET /api/privacy/status` | Computed local-only facts |
| `POST /api/summarize` | Summarize with the local model |
| `POST /api/simplify` | Rewrite in plain language with the local model |

```bash
curl -X POST http://127.0.0.1:8756/api/proofread \
  -H 'Content-Type: application/json' \
  -d '{"text": "Þinngið samþikkti tilöguna."}'
```

```json
{
  "issues": [
    {
      "id": "greynir-0-0-7-S004",
      "source": "greynir",
      "category": "spelling",
      "code": "S004",
      "family": "Stafsetning",
      "startChar": 0,
      "endChar": 7,
      "scope": "span",
      "original": "Þinngið",
      "replacement": "Þingið",
      "alternatives": [],
      "title": "Orðið 'Þinngið' var leiðrétt í 'Þingið'",
      "severity": "error",
      "confidence": null
    }
  ],
  "offsetUnit": "utf16",
  "engines": ["greynir"]
}
```

Interactive docs while running: http://127.0.0.1:8756/docs

**Offsets are UTF-16 code units**, matching JavaScript's `String.length` and
CodeMirror's positions — so an emoji in a document cannot shift later
corrections. The response says so in `offsetUnit` rather than leaving clients to
assume. See [`docs/architecture.md`](docs/architecture.md#4-character-offsets-the-decision-worth-understanding).

Error codes come from GreynirCorrect verbatim; Ritarinn invents none, and
fabricates no confidence scores. See [`docs/error-codes.md`](docs/error-codes.md).

---

## Þróun / Development

```bash
.venv/bin/python -m pytest tests/backend     # 221 backend tests
cd frontend && npm test                      # 89 frontend tests
cd frontend && npm run build                 # typecheck + production build

python scripts/snapshot_corpus.py            # refresh corpus/observed.json
```

The suites include cross-language offset checks against UTF-16 ground truth,
and privacy checks that fail the build if a hosted endpoint, a wildcard CORS
policy, a non-loopback bind or an unpinned dependency appears.

### Configuration

All optional; the defaults are the local-first ones.

| Variable | Default | |
|---|---|---|
| `RITARINN_HOST` | `127.0.0.1` | Refuses non-loopback without the override below |
| `RITARINN_PORT` | `8756` | |
| `RITARINN_ALLOWED_ORIGINS` | loopback:5173 | Comma-separated; wildcards rejected |
| `RITARINN_ALLOW_NON_LOOPBACK` | `0` | Deliberate opt-in to LAN exposure |
| `RITARINN_OLLAMA_ENABLED` | `1` | Local inference runtime |
| `RITARINN_OLLAMA_URL` | `http://127.0.0.1:11434` | **Must be loopback — no override** |
| `RITARINN_LLM_MODEL` | *(unset)* | No model is chosen for you |
| `RITARINN_LLM_TIMEOUT` | `300` | Seconds; a local model on a CPU is slow |
| `RITARINN_LLM_TEMPERATURE` | `0.2` | Low: these features preserve meaning |
| `RITARINN_LLM_CONTEXT_CHARS` | `6000` | Source characters per model call |
| `RITARINN_LOG_LEVEL` | `INFO` | Logs never contain document text |

### Documentation

| | |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Layering, offsets, issue model, model-agnosticism |
| [`docs/privacy.md`](docs/privacy.md) | The guarantee, and how to verify it |
| [`docs/error-codes.md`](docs/error-codes.md) | GreynirCorrect codes and Ritarinn's grouping |
| [`docs/roadmap.md`](docs/roadmap.md) | Milestones 2–5 |
| [`corpus/README.md`](corpus/README.md) | The Icelandic development corpus |

Docker is available (`docker-compose.yml`) but is the optional path — Ritarinn
is a desktop application, and Ollama is a separately installed localhost
service.

---

## Leyfi / License

MIT — see [`LICENSE`](LICENSE).

Ritarinn is independently designed and implemented. No source code, visual
design, wording, prompts, assets or branding was taken from Málstaður,
Málfríður or any other proofreading product.
