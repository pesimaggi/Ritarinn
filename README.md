# Ritarinn

**Staðbundinn íslenskur ritaðstoðarmaður.** Opinn hugbúnaður sem les yfir
íslenskan texta á þinni eigin tölvu — enginn texti fer í skýjaþjónustu.

*A local-first, open-source Icelandic writing assistant. Your text is
proofread on your own computer and is never sent to a cloud service.*

> **Version 0.1 — Milestone 1.** Proofreading (Yfirlestur) works. Summarization
> and plain-language rewriting need a local language model and are not yet
> implemented; the application says so rather than quietly using a hosted one.
>
> "Ritarinn" is a temporary working name.

---

## Hvað þetta gerir / What it does

Skrifaðu eða límdu íslenskan texta, smelltu á **Yfirlesa**, og fáðu einstakar
ábendingar um stafsetningu, málfræði, greinarmerki og málfar. Hver ábending er
skoðuð sérstaklega — þú **Samþykkir** eða **Hunsar**. Ritarinn breytir aldrei
textanum þínum af sjálfsdáðum.

Write or paste Icelandic text, press **Yfirlesa**, and get individual
suggestions covering spelling, grammar, punctuation and style. Each one is
reviewed on its own — you **accept** or **ignore** it. Ritarinn never silently
rewrites your document.

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
| `POST /api/summarize` | 501 — needs a local LLM (Milestone 2) |
| `POST /api/simplify` | 501 — needs a local LLM (Milestone 2) |

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
.venv/bin/python -m pytest tests/backend     # 146 backend tests
cd frontend && npm test                      # 47 frontend tests
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
| `RITARINN_OLLAMA_ENABLED` | `1` | Detection only in v0.1 |
| `RITARINN_OLLAMA_URL` | `http://127.0.0.1:11434` | **Must be loopback — no override** |
| `RITARINN_LLM_MODEL` | *(unset)* | No model is chosen for you |
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
