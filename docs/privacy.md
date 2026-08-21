# Persónuvernd / Privacy

## The claim

**In its default configuration, Ritarinn does not send your text anywhere.**

Not "we don't store it". Not "our vendor doesn't train on it". The text does
not leave your computer, because there is no code path that would take it
there.

## Why you should not have to take that on trust

Ritarinn's status endpoint reports computed facts about the running
configuration, and the "Staðbundið" badge in the interface is derived from
them. If the configuration stopped being local, the badge would stop claiming
it was.

```bash
curl http://127.0.0.1:8756/api/privacy/status
```

```json
{
  "localOnly": true,
  "bindHost": "127.0.0.1",
  "bindsToLoopbackOnly": true,
  "allowedOrigins": ["http://127.0.0.1:5173", "http://localhost:5173", "http://[::1]:5173"],
  "wildcardCors": false,
  "remoteProviderConfigured": false,
  "telemetryEnabled": false,
  "outboundEndpoints": ["http://127.0.0.1:11434"],
  "summary": "Textinn er unninn á þessari tölvu. Engin textagögn eru send í skýjaþjónustu."
}
```

`outboundEndpoints` lists every endpoint the backend is *permitted* to contact.
In the default configuration the only entry is a loopback address, and it is
used solely to ask a local Ollama which models you have installed — never to
send text.

## Generation is local too

Samantekt and Á mannamáli send your text to a language model — one running on
your own machine, over loopback, loaded from weights already on your disk.

- Ritarinn never downloads a model for you.
- The inference endpoint **must** be a loopback address. There is no override,
  and the check is enforced twice: once when configuration loads, and again on
  every generation request, because that is the one code path carrying your
  document.
- The model is given no network, shell or filesystem access.
- If no local model is configured, generation fails and says so. It does not
  fall back to a hosted service, because no such code exists.
- Prompts and model output are never logged.

A model's *origin* does not imply a network dependency. A locally downloaded
Qwen model runs without contacting Alibaba; the weights are just a file.

## Correction is local, and opens no socket at all

Proofreading does not even have a loopback endpoint. GreynirCorrect runs
in-process, and the optional ByT5 corrector runs a model file through PyTorch in
the same process — there is nothing to connect to.

- The ByT5 adapter loads weights with downloads disabled, unconditionally. There
  is no setting that turns that off, so no startup and no proofread can fetch
  anything. A missing model is reported as a missing model.
- Getting the weights onto the disk is `python scripts/install_byt5.py`, run by
  you, once. It is the only thing in the repository that downloads a model, it
  tells you what it is fetching and under what licence before it starts, and the
  application never invokes it.
- `tests/backend/test_byt5_correction.py` runs a full proofread with both
  providers while every way of opening a socket is made to raise. It passes.

## Verify it yourself

The strongest check is the simplest one:

1. Disconnect the machine from the network.
2. Start Ritarinn (and Ollama, if you use the generative features).
3. Proofread, summarize and rewrite a document.

Everything works. Without Ollama installed, the status panel reports "Ollama
fannst ekki" and proofreading continues unaffected.

You can also watch the traffic:

```bash
# macOS / Linux
sudo tcpdump -i any -n 'not (host 127.0.0.1 or host ::1)'
```

Proofreading, summarization and rewriting should all produce nothing.

## What is enforced structurally

These are startup errors, not guidelines. The backend refuses to run otherwise:

| Rule | Where |
|---|---|
| Bind address must be loopback | `config.py` — override requires `RITARINN_ALLOW_NON_LOOPBACK=1` |
| CORS origins must be loopback | `config.py` — no override |
| No wildcard CORS | `config.py` — no override |
| Inference endpoint must be loopback | `config.py` — **no override at all** |

Hostnames are not resolved through DNS when deciding whether something is
loopback: DNS is attacker-influenced, and it would make the answer depend on
the network we are trying not to use. A name like `localhost.example.com` is
treated as remote.

## What is enforced by tests

`tests/backend/test_privacy.py` fails the build if:

- the default bind address is not loopback;
- CORS is wildcarded or contains a remote origin;
- a remote inference endpoint can be configured;
- a hosted AI, analytics or error-reporting endpoint appears in application
  source (OpenAI, Anthropic, Gemini, Vertex, Azure, Alibaba/DashScope, Bedrock,
  Sentry, Google Analytics, Google Fonts, jsDelivr, unpkg, cdnjs);
- any non-loopback URL appears in application source;
- the frontend references a remote font, script or stylesheet;
- a dependency is not pinned to an exact version.

The scan reads *code*, not comments — a comment explaining that Ritarinn avoids
Google Fonts must not fail the test that checks it avoids them. The comment
stripper that makes this distinction is itself tested
(`tests/backend/test_source_scan.py`), because one that silently removed too
much would turn the check into a no-op.

## Logging

Logs contain counts and timings:

```text
proofread completed | engines=greynir | chars=412 | issues=8
```

They do not contain your document, your prompts, or model output. A filter on
the root logger drops overlong messages as a backstop.

## Storage

v0.1 stores nothing. No accounts, no sync, no server database. Your text lives
in the browser tab and is gone when you close it.

Milestone 5 adds IndexedDB drafts — still local, still yours, with **Eyða
staðbundnum gögnum** to clear everything.

## Local models and provenance

Ritarinn distinguishes the **model**, the **runtime**, and the **service
provider**. A model made by a given company does not require talking to that
company: weights on disk are executed by a local runtime.

- Ritarinn ships no weights and downloads none automatically — not for
  generation, and not for correction.
- Models are given no network, shell or filesystem access.
- Ollama detection uses `trust_env=False`, so an ambient `HTTP_PROXY` cannot
  route loopback traffic off the loopback interface.
- GGUF and Safetensors are preferred over formats that execute code on load.
  This is enforced, not merely preferred, for the ByT5 checkpoint: the pickled
  `pytorch_model.bin` published alongside it is neither downloaded nor loaded,
  and a directory containing only that file is not recognised as installed.

## If remote providers are ever added

They are not implemented, and v0.1 has no way to configure one. If a future
version adds them, they must be: opt-in, disabled by default, clearly labelled,
keyed by the user, explicit that text will leave the device, reflected in the
privacy indicator, and completely disableable for people handling sensitive
documents.
