# GreynirCorrect error codes and Ritarinn's grouping

Ritarinn does not invent error codes. Every `code` in an API response is
GreynirCorrect's own, passed through unchanged, and every `title` and
`explanation` is upstream's Icelandic wording.

What Ritarinn adds is a **grouping** so the sidebar can be organised and
filtered: a coarse `category` and an Icelandic `family` label.

## Status of this mapping

This grouping is **Ritarinn's interpretation**, derived by reading
GreynirCorrect 4.1.3's source (`errtokenizer.py`, `errfinder.py`, `pattern.py`,
`settings.py`). It is not an upstream-published taxonomy, and upstream is free
to change its codes.

Accordingly, an unrecognised code falls through to `unknown` / "Annað" rather
than being guessed at, and the raw code is always shown in the UI so the user
can see what actually fired.

Implementation: `backend/ritarinn/services/correction/categories.py`.
Tests: `tests/backend/test_categories.py`.

## Prefix mapping

| Prefix | Category | Family (Icelandic) | Scope | What it covers |
|---|---|---|---|---|
| `S` | spelling | Stafsetning | span | Token-level spelling correction |
| `C` | spelling | Samsett orð | span | Compound-word errors — a compound split apart, or words wrongly joined |
| `U` | spelling | Óþekkt orð | span | Word absent from BÍN with no confident correction |
| `W` | spelling | Ruglingsleg orð | span | Confusable words from the curated list |
| `Z` | spelling | Há- og lágstafir | span | Capitalisation |
| `A` | spelling | Skammstafanir | span | Abbreviations corrected against the known-abbreviation table |
| `R` | spelling | Ritmyndir | span | Non-standard written forms graded by BÍN's Ritmyndir data |
| `N` | punctuation | Greinarmerki | span | Quotation marks, ellipses, repeated periods |
| `P_` | grammar | Málfræði | span | Post-parse grammar patterns: case government, agreement, mood, preposition choice, definiteness |
| `T` | style | Varúðarorð | span | Taboo / sensitive vocabulary |
| `V` | style | Tónn | span | Tone-of-voice vocabulary |
| `Y` | style | Málsnið | span | Forms marked in BÍN as belonging to a particular register |
| *(other)* | unknown | Annað | span | Fallback — never a guess |

Longest prefix wins, so `P_` is matched before any single letter.

## Whole-code overrides

| Code | Category | Family | Scope |
|---|---|---|---|
| `E001` | unknown | Ógreind málsgrein | **sentence** |
| `E004` | unknown | Ekki íslenska | **sentence** |
| `E005` | style | Löng málsgrein | **sentence** |
| `E006` | style | Skammstafanir | span |
| `E007` | style | Upphrópunarmerki | span |
| `number4word` | style | Tölur og bókstafir | span |

## Scope

`scope` distinguishes two different things a span can mean:

- **`span`** — the offsets delimit the problem itself. The editor underlines
  them, and a replacement can be applied to exactly that range.
- **`sentence`** — the annotation is *about* a whole sentence: it failed to
  parse, it is very long, it is not Icelandic. Its span covers the entire
  sentence.

Sentence-scope issues are listed in the sidebar but **not underlined**.
Underlining them would draw a line beneath a whole paragraph and bury the
word-level issues inside it. They are still selectable, so clicking one in the
sidebar still reveals the sentence.

## The `/w` warning marker

GreynirCorrect appends `/w` to a code that is advisory rather than an outright
error (`N002/w`, `T001/w`, `C005/w`). Ritarinn splits the marker off, keeps the
bare code, and maps it to `severity: "warning"`.

This is upstream's own error/warning distinction. Ritarinn does not invent
severities, and it does not convert them into confidence scores.

## Codes observed on the development corpus

Running `corpus/cases.json` through GreynirCorrect 4.1.3 produces:

`S004`, `C001`, `C004/w`, `U001`, `Z002`, `E001`, `E005`, `E006`, `E007`,
`P_WRONG_CASE_þgf_þf`, `P_NT_ÍTölu`

This is a small sample of the vocabulary, not the whole of it — it is what the
corpus happens to exercise. Regenerate it with:

```bash
python scripts/snapshot_corpus.py
```
