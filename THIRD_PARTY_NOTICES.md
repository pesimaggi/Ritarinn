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
| **License** | **CC BY-SA 4.0** — verified; see the evidence below. Note the share-alike clause and the open question in section 6 |
| **Base model** | `google/byt5-base` — **Apache-2.0** (https://huggingface.co/google/byt5-base) |
| **Redistributed?** | No — Ritarinn bundles no model weights and downloads none automatically. `scripts/install_byt5.py` fetches them to the user's own machine, deliberately |
| **Attribution requirement** | BY: credit Miðeind ehf. and link the licence. SA: an *adapted* version must be released under CC BY-SA 4.0 or a compatible licence |
| **Notes** | Optional correction provider. Ritarinn is fully usable without it, and it is off unless explicitly installed and enabled. |

**What was verified, and how.** Read from the Hugging Face model repository on
2026-08-21, at commit `d628a9359dd021051c8d49a099fd04ee2865ef86`
(last modified 2023-04-19):

- the repository metadata carries the tag `license:cc-by-sa-4.0`, and the model
  card's own YAML front matter states `license: cc-by-sa-4.0`. The two agree;
- the card states the model "is based on the pretrained ByT5 model
  (https://arxiv.org/abs/2105.13626) and finetuned on Icelandic error correction
  data along with synthetic error data", trained with "the HuggingFace and
  PyTorch libraries", and "trained to correct a single sentence at a time";
- the card does **not** name the exact base checkpoint. `config.json` does,
  implicitly and unambiguously: `d_model 1536`, `d_ff 3968`, `num_layers 18`,
  `num_decoder_layers 6`, `num_heads 12`, `vocab_size 384`,
  `tokenizer_class ByT5Tokenizer` — an exact match for `google/byt5-base`, whose
  own configuration differs only in fields added by later Transformers releases.
  `google/byt5-base` is tagged Apache-2.0;
- weights: 581,653,248 parameters, float32. `model.safetensors` is 2,326,643,636
  bytes. The repository also carries an identical `pytorch_model.bin`
  (2,326,697,929 bytes), which Ritarinn does **not** download and does **not**
  load — unpickling executes whatever is in the file, and the same weights are
  available in a format that cannot.

**What CC BY-SA 4.0 means here.** Attribution and share-alike attach to the
*licensed material* — the weights. Ritarinn does not redistribute them, does not
modify them, and does not bundle them, so the obligation that applies today is
attribution, which this file and the application's Stillingar panel both carry.
Anyone who fine-tunes this checkpoint, or ships an application with the weights
inside it, is in different territory and should read the licence themselves.

⚠️ **Unresolved, and deliberately not asserted either way:** whether text
*produced* by the model is an "adaptation" that share-alike reaches. Creative
Commons licences were written for creative works, not model weights, and CC
itself advises against using them for software; there is no clause covering
model output and no authoritative reading to cite. This does not affect a user
proofreading their own document on their own machine — the case Ritarinn is
built for — but it is a real question for anyone publishing corrected text under
terms incompatible with BY-SA, and it is recorded in section 6 rather than
answered here.

**Checksums.** Not recorded yet. `scripts/install_byt5.py` accepts `--revision`,
so an installation can be pinned to the commit above; per-file hashes should be
recorded here before the provider is ever recommended by default.

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

Once a default generative model is recommended (Track A in `docs/roadmap.md`),
this section must record for each candidate: name, origin, licence, download
size, memory requirement, and published checksums.

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

### Optional: the neural correction runtime

Installed only by someone who chooses to run the ByT5 provider
(`backend/requirements-byt5.txt`). None of it is part of a default installation,
and nothing in Ritarinn imports any of it unless that provider is enabled.

| Name | Version | Author | Source | License | Redistributed? |
|---|---|---|---|---|---|
| PyTorch | 2.13.0 | PyTorch contributors / Linux Foundation | https://github.com/pytorch/pytorch | BSD-3-Clause (the wheel also carries third-party components under their own terms) | No |
| Transformers | 5.15.1 | Hugging Face | https://github.com/huggingface/transformers | Apache-2.0 | No |
| huggingface-hub | 1.28.0 | Hugging Face | https://github.com/huggingface/huggingface_hub | Apache-2.0 | No |
| safetensors | 0.8.0 | Hugging Face | https://github.com/huggingface/safetensors | Apache-2.0 | No |

⚠️ The PyTorch wheels bundle a large set of third-party libraries, and the CUDA
builds bundle NVIDIA components under NVIDIA's own terms. Anyone redistributing
an environment with PyTorch in it should read `torch`'s bundled licence files
rather than the top-level BSD-3-Clause line.

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

1. **ByT5 output and share-alike** — the model's own licence is settled
   (CC BY-SA 4.0, verified above); what is *not* settled is whether share-alike
   reaches text the model produces. No clause covers it and no authoritative
   reading exists to cite. Local proofreading is unaffected; publishing
   model-corrected text under an incompatible licence is the case that needs an
   answer. Flagged, not resolved.
2. **Icegrams corpus provenance** — the package is MIT, but the metadata does
   not restate the licence of the corpus its frequency counts derive from.
3. **Yfirlestur** — not reviewed for licence terms, as it is not a dependency.
4. **BÍN data downstream** — CC BY 4.0 requires attribution to travel with the
   data. Anyone repackaging Ritarinn with BinPackage embedded must carry the
   credit in section 1, not merely link to this file.
5. **GreynirEngine version drift** — the MIT terms recorded here are for 3.8.0.
   Earlier releases were licensed differently.
6. **ByT5 training data** — the model card says "Icelandic error correction data
   along with synthetic error data" without naming a corpus or its terms. The
   card also says it "will be updated soon along with citation reference"; it has
   not been updated since April 2023. Unverified.
7. **ByT5 weight checksums** — not recorded. An installation can be pinned to a
   commit (`--revision`), which is weaker than a hash.
