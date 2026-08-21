"""Telling an Icelandic answer apart from a model's own thinking.

The detectors here decide whether a local model's output reaches the user's
document, so both directions matter and they are not symmetrical. Letting a
chain of thought through means pasting a model's private reasoning into someone's
letter. Rejecting a real summary means the user waited for a local model on a
CPU and got an error instead. The first is worse, but the second is the one that
happens to every user rather than to some of them, so the fixtures below are
weighted towards ordinary Icelandic that must never be rejected.
"""

from __future__ import annotations

import pytest

from ritarinn.text.language import (
    icelandic_letter_ratio,
    looks_like_english,
    looks_like_reasoning,
)

#: A real chain of thought, from a reasoning model asked for a summary of an
#: Icelandic account of a weekend trip. The model narrates the task in English
#: and is cut off by the output cap before writing anything. Nothing in it is
#: marked as reasoning: the chat template supplied the opening ``<think>``, so
#: the model never generated one, and the closing tag was never reached.
LEAKED_REASONING = """\
Okay, let's tackle this problem. The user wants me to create two sentences that \
capture the main points of the given Icelandic text. The text is about a trip \
the narrator and friends took in the summer, specifically around Borgarnes. \
They went to a small house, cooked food, had some issues with packing, and \
planned to do better next time.

First, I need to understand the key points. The main events are: they went to a \
summer house near Borgarnes, spent a day there, cooked food (lamb, potatoes, \
greens), had some issues with packing, and they plan to make a list next time \
to avoid forgetting things.

Wait, the user wants two sentences that summarize the main points without \
adding extra info. Let me check"""

ICELANDIC_SUMMARY = (
    "Hópur vina fór í sumarbústað skammt frá Borgarnesi um helgi og elduðu "
    "saman kvöldmat úr lambakjöti, kartöflum og grænmeti. Ferðin heppnaðist vel "
    "þrátt fyrir rigningu og gleymda hluti, og hópurinn ætlar að skipuleggja sig "
    "betur fyrir næstu ferð."
)


# -- text that must never be rejected -----------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        pytest.param(ICELANDIC_SUMMARY, id="ordinary summary"),
        pytest.param("Ferðin heppnaðist vel.", id="one short sentence"),
        pytest.param(
            "- Hópurinn fór í sumarbústað.\n"
            "- Þau elduðu lambakjöt og kartöflur.\n"
            "- Veðrið versnaði daginn eftir.",
            id="bullet list",
        ),
        pytest.param(
            "Í skýrslunni „Annual Report on the State of the Union“ frá 2019 "
            "kemur fram að kostnaður hafi aukist um 12 prósent milli ára.",
            id="Icelandic quoting an English title",
        ),
        pytest.param(
            "Umsækjandi skal skila gögnum fyrir 1. mars. Ég þarf að staðfesta "
            "móttöku innan viku.",
            id="first person, as a rewritten letter would be",
        ),
        pytest.param("", id="nothing at all"),
    ],
)
def test_icelandic_output_is_accepted(text: str) -> None:
    """A false positive costs the user the summary they waited for."""
    assert looks_like_english(text) is False
    assert looks_like_reasoning(text) is False


def test_a_first_person_sentence_is_not_reasoning_unless_it_opens_the_response() -> None:
    """"Ég þarf að" is a model narrating only at the very start.

    Inside a rewritten letter it is the author's own voice, and rejecting it
    would break the plain-language feature on any first-person document.
    """
    assert looks_like_reasoning("Ég þarf að lesa textann fyrst.") is True
    assert looks_like_reasoning("Umsóknin barst í tæka tíð. Ég þarf að svara henni.") is False


# -- text that must be caught -------------------------------------------------


def test_a_leaked_chain_of_thought_is_recognised() -> None:
    """The reported failure: reasoning with no tag around it, in the result."""
    assert looks_like_reasoning(LEAKED_REASONING) is True
    assert looks_like_english(LEAKED_REASONING) is True


@pytest.mark.parametrize(
    "opening",
    [
        "Okay, so I need to summarise this.",
        "Let me think about what this text says.",
        "First, I need to identify the main points of the document.",
        "Hmm, this is a long text about a trip.",
        "Wait, the instructions say two sentences.",
        "Allt í lagi, skoðum þetta skjal.",
    ],
)
def test_reasoning_openings_are_recognised(opening: str) -> None:
    assert looks_like_reasoning(opening) is True


@pytest.mark.parametrize(
    "meta",
    [
        "Þetta er löng frásögn. The user wants a two sentence summary of it.",
        "Skoðum málið. My task is to condense the following document.",
        "Fyrst um efnið. Notandinn vill fá stutta samantekt á þessum texta.",
    ],
)
def test_meta_commentary_about_the_request_is_recognised(meta: str) -> None:
    """Not a summary of the document at any length: it is about the request."""
    assert looks_like_reasoning(meta) is True


def test_a_correct_summary_in_the_wrong_language_is_recognised() -> None:
    """A model can understand the text perfectly and still answer in English."""
    english = (
        "The group of friends travelled to a summer house near Borgarnes for "
        "the weekend. They cooked dinner together and agreed to plan the next "
        "trip more carefully."
    )
    assert looks_like_english(english) is True
    # It is a real summary, so nothing marks it as reasoning — the language is
    # the only thing wrong with it, and the two detectors say so separately.
    assert looks_like_reasoning(english) is False


def test_a_few_english_words_do_not_make_icelandic_english() -> None:
    mixed = (
        "Fundurinn fjallaði um verkefnið „the Nordic Council of Ministers "
        "Working Group on Digital Inclusion“ og niðurstöður þess."
    )
    assert looks_like_english(mixed) is False


def test_a_fragment_is_too_short_to_call_english() -> None:
    """Below a handful of words there is no evidence either way."""
    assert looks_like_english("The end.") is False


# -- the orthographic signal --------------------------------------------------


def test_icelandic_letter_ratio_separates_the_two() -> None:
    assert icelandic_letter_ratio(ICELANDIC_SUMMARY) > 0.05
    assert icelandic_letter_ratio(LEAKED_REASONING) < 0.01
    assert icelandic_letter_ratio("") == 0.0
    assert icelandic_letter_ratio("12. 3. 2019") == 0.0
