# Íslenskt prófunarsafn / Icelandic development corpus

Short Icelandic samples used to exercise the proofreading pipeline across
registers and error types.

## Ground truth

`cases.json` records what each sample *is* — its register, and which error
types were deliberately written into it. It does **not** record expected
corrections.

That is deliberate. GreynirCorrect's behaviour is the source of truth for what
Ritarinn reports; asserting a hand-written expected correction would test our
opinion of Icelandic rather than the integration. The tests therefore assert
properties that must hold for any engine — offsets land on real characters,
suggestions are applicable, categories are known — and pin only a small number
of corrections that were verified against the installed engine version.

`observed.json` is a snapshot of what GreynirCorrect 4.1.3 actually reports for
each sample, regenerated with:

```bash
python scripts/snapshot_corpus.py
```

It is a review aid for humans, not a test fixture: a diff in it after a
dependency upgrade shows exactly what changed upstream.

## Licensing

All sample sentences here were written for this project and are covered by the
repository's MIT licence. No text was taken from Málstaður, Málfríður, or any
other proofreading product, and none was copied from a copyrighted corpus.
