"""Telling an Icelandic answer apart from a model's own thinking.

Ritarinn's generative features have exactly one acceptable kind of output:
Icelandic prose about the user's own text. Local models produce two other
things often enough that the application has to recognise them rather than
paste them into a document:

* a **chain of thought** — the model reasoning aloud, in English, about what
  the user probably wants, before writing anything;
* an **English answer** — a correct summary, in the wrong language.

Both are detected here rather than in the runtime adapter, because neither is a
property of any particular runtime or model family: any model can do either.

The detectors are deliberately one-sided. Their job is to catch output that is
*clearly* not an Icelandic answer, and a false positive costs the user a real
summary, so every threshold is set so that plausible Icelandic passes. Icelandic
that merely lacks the markers below is never rejected; only text that positively
looks like English is.

No language-identification dependency is used. A model's chain of thought is
fluent English full of function words, which is the easiest possible case, and
the cost of a wrong answer here is high enough that a rule anyone can read and
adjust is worth more than a black box.
"""

from __future__ import annotations

import re

#: Word characters only — no digits, no punctuation. Unicode-aware, so Icelandic
#: letters are part of a word rather than a boundary.
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

#: Letters that exist in Icelandic and not in English. Their presence at any
#: real density is decisive: no amount of English function words makes text
#: written in Icelandic orthography an English answer.
_ICELANDIC_LETTERS = frozenset("áéíóúýþæöð")

#: High-frequency English function words. Chosen for frequency in ordinary
#: English prose, and checked against Icelandic: a word that is also an
#: Icelandic word ("of", "er", "til", "en") earns its place only if it is far
#: more common in English, and the thresholds below assume a handful of
#: coincidental matches in genuine Icelandic.
_ENGLISH_MARKERS = frozenset(
    """
    the and is are was were be been being to of in on for with that this these
    those it its there here what which who whom whose how why when while from
    by as at but or not no yes do does did done have has had will would can
    could should shall may might must about into over under between after
    before during without within through you your yours we our ours they them
    their he she his her him me my mine us so than then very just also only
    because if unless since about need needs needed want wants wanted let lets
    make makes made take takes given give gives using use used user users
    summary summarize summarise sentence sentences text texts paragraph
    paragraphs main points point key okay ok alright first second third next
    finally wait hmm sure right think thinking thought
    """.split()
)

#: High-frequency Icelandic words that are not English words. Used only to
#: confirm that Icelandic markers do *not* outweigh English ones; their absence
#: is never taken as evidence against Icelandic, because a short Icelandic
#: sentence may contain none of them.
_ICELANDIC_MARKERS = frozenset(
    """
    að og er sem ekki við um það þetta þessi því hann hún þau þeir þær var voru
    hafa hafði höfðu verið eru með fyrir frá eftir yfir þegar síðan mjög aðeins
    einnig þar hér þess þeirra okkar sinni eða en til á í úr án upp niður allt
    einn ein eitt þarf getur skal verður mun sagði kom fór eins bæði líka enn
    þó svo hins vegar meðal annars samkvæmt þannig þau þýðir gera gert
    """.split()
)

#: Openings that mark a chain of thought rather than an answer. Matched only
#: against the *start* of the response, where a model states the task back to
#: itself before doing it. Prefix-only matching matters: "ég þarf að" opening a
#: response is a model narrating; the same words inside a rewritten letter are
#: the author's own. Icelandic forms are included because a model that reasons
#: in the target language leaks just as badly as one that reasons in English.
_REASONING_OPENERS = (
    "okay,",
    "okay ",
    "ok,",
    "alright,",
    "let's ",
    "lets ",
    "let me ",
    "so, the user",
    "so the user",
    "first, i",
    "first i need",
    "i need to",
    "i should",
    "i have to",
    "i will start",
    "looking at the text",
    "hmm,",
    "wait,",
    "allt í lagi,",
    "ég þarf að",
    "fyrst þarf ég",
    "skoðum textann",
    "látum sjá",
)

#: Phrases that are about the request rather than about the document, and so
#: cannot be part of a faithful summary or rewrite of it wherever they appear.
#: Unlike the openers these are matched anywhere in the opening window, because
#: a model often reaches them a sentence or two in. Every entry has to be
#: unambiguous meta-commentary — anything a document could plausibly say itself
#: belongs in the openers above instead.
_REASONING_META = (
    "the user wants",
    "the user is asking",
    "the user asked",
    "the user provided",
    "the user gave",
    "the user has given",
    "my task is",
    "the task is to",
    "i am asked to",
    "notandinn vill",
    "notandinn biður",
    "verkefni mitt er",
)

#: How much of the response to examine for a reasoning opener. A trace states
#: the task within its first sentence or two; searching further would start
#: matching quoted material from the document.
_OPENER_WINDOW = 200

#: Below this many words there is not enough evidence to call text English.
_MIN_WORDS_FOR_LANGUAGE = 8

#: Share of words that must be English function words. Ordinary English prose is
#: well above this; the chain of thought this exists to catch runs around a
#: third.
_ENGLISH_MARKER_FLOOR = 0.12

#: Share of letters that must be Icelandic-specific before text counts as
#: written in Icelandic. Real Icelandic runs several percent; a trace that
#: quotes an Icelandic word or two stays far below.
_ICELANDIC_LETTER_FLOOR = 0.01


def _words(text: str) -> list[str]:
    return [match.group(0).lower() for match in _WORD.finditer(text)]


def icelandic_letter_ratio(text: str) -> float:
    """Share of alphabetic characters that exist only in Icelandic."""
    letters = [char for char in text.lower() if char.isalpha()]
    if not letters:
        return 0.0
    return sum(char in _ICELANDIC_LETTERS for char in letters) / len(letters)


def looks_like_english(text: str) -> bool:
    """True only when *text* is clearly English rather than Icelandic.

    Three things must hold together: English function words at a density
    ordinary Icelandic never reaches, more English markers than Icelandic ones,
    and effectively no Icelandic orthography. Icelandic that simply happens to
    contain an English word or two fails all three.
    """
    words = _words(text)
    if len(words) < _MIN_WORDS_FOR_LANGUAGE:
        return False

    english = sum(word in _ENGLISH_MARKERS for word in words) / len(words)
    icelandic = sum(word in _ICELANDIC_MARKERS for word in words) / len(words)

    return (
        english >= _ENGLISH_MARKER_FLOOR
        and english > icelandic
        and icelandic_letter_ratio(text) < _ICELANDIC_LETTER_FLOOR
    )


def looks_like_reasoning(text: str) -> bool:
    """True when *text* opens as a model talking to itself about the task.

    This catches the case tags cannot: a model whose chat template supplies the
    opening ``<think>`` and whose output is cut off before the closing tag
    arrives, leaving a chain of thought with no marker around it at all.

    Only the opening of the response is examined. A summary that quotes the
    document at length may contain almost anything further in; what no summary
    of a document *starts* with is the model restating the request.
    """
    opening = text.lstrip().lower()[:_OPENER_WINDOW]
    if any(opening.startswith(marker) for marker in _REASONING_OPENERS):
        return True
    return any(marker in opening for marker in _REASONING_META)
