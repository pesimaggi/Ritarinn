# Third-party notices

Ritarinn is built on open-source Icelandic language technology and general
open-source infrastructure. This file records what Ritarinn uses, who wrote it,
and under what terms.

**This is not legal advice.** Licence fields were read from the installed
package metadata at the pinned versions listed below, and links point at the
upstream sources so they can be checked. Where the situation is not clear-cut
it is flagged rather than resolved. Anyone redistributing Ritarinn — especially
in a product, or bundled with model weights — should verify these terms
independently.

Versions below are the ones pinned in `backend/requirements.txt` and
`frontend/package.json`. Re-check this file whenever a pin moves.

---

## 1. Icelandic language technology

These components do the actual Icelandic analysis. Ritarinn is a user interface
and an integration layer around them; the linguistic work is theirs.

### GreynirCorrect

| | |
|---|---|
| **Name** | GreynirCorrect (`reynir-correct` 4.1.3) |
| **Author/organization** | Miðeind ehf. Original author: Vilhjálmur Þorsteinsson |
| **Source** | https://github.com/mideind/GreynirCorrect |
| **License** | MIT (`License-Expression: MIT`; copyright © 2025 Miðeind ehf.) |
| **Redistributed?** | No — installed from PyPI by the setup script |
| **Attribution requirement** | MIT copyright and permission notice must accompany copies |
| **Notes** | Ritarinn's entire v0.1 proofreading capability. Its error codes and Icelandic explanations are passed through to the user unchanged. |

### GreynirEngine

| | |
|---|---|
| **Name** | GreynirEngine (`reynir` 3.8.0) |
| **Author/organization** | Miðeind ehf. Original author: Vilhjálmur Þorsteinsson |
| **Source** | https://github.com/mideind/GreynirEngine |
| **License** | MIT (`License-Expression: MIT`; copyright © 2016–2024 Miðeind ehf.) |
| **Redistributed?** | No — transitive dependency of GreynirCorrect |
| **Attribution requirement** | MIT copyright and permission notice |
| **Notes** | The Icelandic parser. Ritarinn reaches it only through GreynirCorrect in v0.1. Note that GreynirEngine was GPL-licensed in earlier releases; the MIT terms recorded here apply to 3.8.0. Anyone pinning an older version must re-check. |

### BinPackage / BÍN

| | |
|---|---|
| **Name** | BinPackage (`islenska` 1.3.2) |
| **Author/organization** | Miðeind ehf. |
| **Source** | https://github.com/mideind/BinPackage |
| **License** | **Software: MIT.** **Embedded data: see below.** |
| **Redistributed?** | No — transitive dependency |
| **Attribution requirement** | MIT notice for the code; BÍN attribution for the data |
| **Notes** | ⚠️ **The package code and the linguistic data it embeds are under different licences.** Do not treat "BinPackage is MIT" as covering the data. |

The embedded data is *Beygingarlýsing íslensks nútímamáls* (BÍN), published by
Stofnun Árna Magnússonar í íslenskum fræðum under **CC BY 4.0**. BinPackage's
own source states the required credit, reproduced here as the licence asks:

> Beygingarlýsing íslensks nútímamáls.
> Stofnun Árna Magnússonar í íslenskum fræðum.
> Höfundur og ritstjóri Kristín Bjarnadóttir.

Terms: https://bin.arnastofnun.is/DMII/LTdata/conditions/ (English) and
https://bin.arnastofnun.is/gogn/mimisbrunnur/ (Icelandic).

This attribution is surfaced in the application itself, under **Stillingar →
Byggt á íslenskri máltækni**, not only in this file.

### Icegrams

| | |
|---|---|
| **Name** | Icegrams (`icegrams` 1.1.7) |
| **Author/organization** | Miðeind ehf. Original author: Vilhjálmur Þorsteinsson |
| **Source** | https://github.com/mideind/Icegrams |
| **License** | MIT (copyright © 2020–2025 Miðeind ehf.) |
| **Redistributed?** | No — transitive dependency |
| **Attribution requirement** | MIT notice |
| **Notes** | Icelandic trigram frequency model used for spelling candidate ranking. Its underlying corpus provenance is not restated in the package metadata; flagged as unverified. |

### Tokenizer

| | |
|---|---|
| **Name** | Tokenizer (`tokenizer` 3.6.4) |
| **Author/organization** | Miðeind ehf. Original author: Vilhjálmur Þorsteinsson |
| **Source** | https://github.com/mideind/Tokenizer |
| **License** | MIT (copyright © 2016–2025 Miðeind ehf.) |
| **Redistributed?** | No — transitive dependency |
| **Attribution requirement** | MIT notice |
| **Notes** | Ritarinn's character-offset mapping depends on this tokenizer preserving each token's verbatim source text. That dependency is asserted in `tests/backend/test_offsets.py`. |

### Yfirlestur

| | |
|---|---|
| **Name** | Yfirlestur |
| **Author/organization** | Miðeind ehf. / Icelandic language technology programme |
| **Source** | https://github.com/mideind/Yfirlestur |
| **License** | ⚠️ **Not verified** — not a Ritarinn dependency, so its terms were not established |
| **Redistributed?** | No |
| **Attribution requirement** | n/a at present |
| **Notes** | A web front end for GreynirCorrect. Ritarinn does not use its code; it is listed because it is prior art in the same space and was reviewed as background. |

### ByT5 Icelandic correction model

| | |
|---|---|
| **Name** | `yfirlestur-icelandic-correction-byt5` |
| **Author/organization** | Miðeind ehf. |
| **Source** | https://huggingface.co/mideind/yfirlestur-icelandic-correction-byt5 |
| **License** | ⚠️ **Must be verified before the model is enabled.** Not established here, because v0.1 neither downloads nor loads it |
| **Redistributed?** | No — and Ritarinn will not bundle model weights |
| **Attribution requirement** | To be determined with the licence |
| **Notes** | Milestone 4. Its licence, the licence of any base model it derives from, and checksums for the weights must all be recorded before the engine is enabled by default. |

---

## 2. Local inference runtime

### Ollama

| | |
|---|---|
| **Name** | Ollama |
| **Author/organization** | Ollama Inc. |
| **Source** | https://github.com/ollama/ollama |
| **License** | MIT (verify against the version you install) |
| **Redistributed?** | No — installed separately by the user, as a localhost service |
| **Attribution requirement** | MIT notice if redistributed |
| **Notes** | A *runtime*, not a model. Ritarinn asks a locally running Ollama which models are installed, and sends prompts to it for Samantekt and Á mannamáli — over loopback only. Ollama's hosted services are not used and are not reachable from Ritarinn's configuration, which rejects any non-loopback endpoint with no override. |

### Local language models

Ritarinn ships **no model weights** and downloads none automatically. Any model
the user installs carries its own licence, which the user accepts directly with
its distributor.

A model's origin does not imply a network dependency: weights that are on disk
are executed locally by the runtime. A locally downloaded Qwen model, for
example, runs without contacting Alibaba, and Ritarinn provides no model with
network, shell or filesystem access.

**Models used during development.** `gemma3:4b` and `qwen3:4b` were pulled
through Ollama to verify the generation pipeline end to end. They are *not*
recommendations — both were chosen for download size and speed on a CPU, and
their Icelandic is visibly weak. They are not bundled, not referenced in code,
and not defaulted to anywhere.

Once a default model is recommended (Milestone 3), this section must record for
each candidate: name, origin, licence, download size, memory requirement, and
published checksums.

---

## 3. Backend infrastructure

| Name | Version | Author | Source | License | Redistributed? |
|---|---|---|---|---|---|
| FastAPI | 0.141.1 | Sebastián Ramírez | https://github.com/fastapi/fastapi | MIT | No |
| Starlette | 1.6.0 | Encode OSS Ltd | https://github.com/encode/starlette | BSD-3-Clause | No |
| Uvicorn | 0.52.4 | Encode OSS Ltd | https://github.com/encode/uvicorn | BSD-3-Clause | No |
| Pydantic | 2.13.4 | Pydantic Services Inc. and contributors | https://github.com/pydantic/pydantic | MIT | No |
| HTTPX | 0.28.1 | Encode OSS Ltd | https://github.com/encode/httpx | BSD-3-Clause | No |

All are installed from PyPI at setup time. Attribution requirement for each is
the standard MIT/BSD notice on redistribution.

---

## 4. Frontend infrastructure

| Name | Version | Author | Source | License | Redistributed? |
|---|---|---|---|---|---|
| React | 18.3.1 | Meta Platforms and contributors | https://github.com/facebook/react | MIT | Yes, in a production build |
| React DOM | 18.3.1 | Meta Platforms and contributors | https://github.com/facebook/react | MIT | Yes, in a production build |
| CodeMirror `@codemirror/state` | 6.5.2 | Marijn Haverbeke and contributors | https://github.com/codemirror/state | MIT | Yes, in a production build |
| CodeMirror `@codemirror/view` | 6.38.1 | Marijn Haverbeke and contributors | https://github.com/codemirror/view | MIT | Yes, in a production build |
| CodeMirror `@codemirror/commands` | 6.8.1 | Marijn Haverbeke and contributors | https://github.com/codemirror/commands | MIT | Yes, in a production build |
| Vite | 6.0.11 | Evan You and contributors | https://github.com/vitejs/vite | MIT | No (build tool) |
| TypeScript | 5.7.3 | Microsoft | https://github.com/microsoft/TypeScript | Apache-2.0 | No (build tool) |
| Vitest | 2.1.9 | Vitest contributors | https://github.com/vitest-dev/vitest | MIT | No (test tool) |
| `@vitejs/plugin-react` | 4.3.4 | Vite contributors | https://github.com/vitejs/vite-plugin-react | MIT | No (build tool) |
| jsdom | 25.0.1 | jsdom contributors | https://github.com/jsdom/jsdom | MIT | No (test tool) |
| `@testing-library/react` | 16.1.0 | Testing Library contributors | https://github.com/testing-library/react-testing-library | MIT | No (test tool) |

**⚠️ Bundled code carries its notices with it.** React and CodeMirror are
compiled into `frontend/dist`, so a distributed build redistributes them and
must carry their MIT notices. The build tools above are not shipped.

Ritarinn loads **no** remote fonts, scripts or stylesheets, so no web-hosted
asset licences apply. This is enforced by
`tests/backend/test_privacy.py::test_frontend_has_no_remote_assets`.

---

## 5. Ritarinn's own content

The Icelandic sample sentences in `corpus/` were written for this project and
are covered by the repository's MIT licence. No text, wording, visual design,
prompts or branding was taken from Málstaður, Málfríður or any other
proofreading product.

"Ritarinn" is a temporary working name. All branding is confined to
`frontend/src/i18n/is.ts` (the `appName` string) and `docs/`, so replacing it
is a small, contained change.

---

## 6. Open questions

Flagged rather than answered:

1. **ByT5 model licence** — unestablished. Must be resolved before Milestone 4
   enables the engine.
2. **Icegrams corpus provenance** — the package is MIT, but the metadata does
   not restate the licence of the corpus its frequency counts derive from.
3. **Yfirlestur** — not reviewed for licence terms, as it is not a dependency.
4. **BÍN data downstream** — CC BY 4.0 requires attribution to travel with the
   data. Anyone repackaging Ritarinn with BinPackage embedded must carry the
   credit in section 1, not merely link to this file.
5. **GreynirEngine version drift** — the MIT terms recorded here are for 3.8.0.
   Earlier releases were licensed differently.
