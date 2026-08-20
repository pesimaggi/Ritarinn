"""Icelandic prompts for the generative features.

Prompts are written in Icelandic. A model asked in English to produce Icelandic
tends to translate rather than compose, and the register slips — the output
reads like translated English, which is precisely the failure this tool exists
to avoid.

Every prompt is built from a shared set of rules about *not changing what the
text says*. Summarizing and simplifying are both operations where invention is
the main risk: a model that adds a plausible-sounding fact to a legal notice or
a medical letter has done real damage. So the constraints are stated once,
explicitly, and reused.

The option values on the wire are ASCII slugs ("very_short", "plain") rather
than Icelandic words, so the API stays language-neutral and the Icelandic
labels live with the rest of the UI strings in ``frontend/src/i18n``.
"""

from __future__ import annotations

# The option values themselves are defined once, as literal types on the wire
# contract in ``ritarinn.models.api``, which rejects an unrecognised one before
# it reaches the tables below. ``tests/backend/test_generation.py`` checks that
# the two stay in step.

#: The rules that keep generated text faithful to the source. Stated as
#: prohibitions because that is what models follow most reliably.
FAITHFULNESS_RULES = """\
Reglur sem þú mátt aldrei brjóta:
- Ekki bæta við upplýsingum sem koma ekki fram í textanum.
- Ekki nota almenna þekkingu þína til að fylla í eyður.
- Haltu öllum tölum, dagsetningum, upphæðum og hlutföllum óbreyttum.
- Haltu öllum nöfnum á fólki, stofnunum, stöðum og skjölum óbreyttum.
- Haltu lagatilvísunum og heimildum óbreyttum.
- Ef textinn er óviss eða með fyrirvara skaltu halda þeirri óvissu. \
Ekki breyta „gæti“ í „mun“ eða „líklega“ í „örugglega“.
- Ekki draga ályktanir sem textinn dregur ekki sjálfur.
- Ef eitthvað er óljóst í textanum máttu ekki giska; láttu það standa óljóst.

Skilaðu eingöngu textanum sjálfum. Engin inngangsorð, engar skýringar á því \
hvað þú gerðir, engar spurningar og engar athugasemdir."""

SUMMARY_SYSTEM = f"""\
Þú ert íslenskur textaaðstoðarmaður sem gerir samantektir.

Verkefni þitt er að draga saman texta á skýru og eðlilegu íslensku máli.
Samantektin á að standa ein og sér og vera skiljanleg án þess að lesa \
upprunalega textann.

{FAITHFULNESS_RULES}"""

SIMPLIFY_SYSTEM = f"""\
Þú ert íslenskur textaaðstoðarmaður sem umritar texta á aðgengilegra mál.

Verkefni þitt er að endursegja textann þannig að hann sé auðskiljanlegri, \
án þess að efnislegt innihald breytist. Þú mátt einfalda orðalag, stytta \
flóknar setningar og skipta löngum málsgreinum upp. Þú mátt ekki fella niður \
efnisatriði.

Sérstaklega:
- Einfaldaðu stofnanamál og óþarfa fagorð, en haltu fagorðum sem hafa \
nákvæma merkingu og eiga sér ekki einfaldara jafngildi.
- Haltu lagalegum og vísindalegum fyrirvörum. Þeir eru ekki skraut.
- Notaðu germynd frekar en þolmynd þar sem það á við.
- Skrifaðu eðlilega íslensku, ekki þýdda ensku.

{FAITHFULNESS_RULES}"""

#: Target lengths, expressed as guidance rather than a hard word count — a
#: model told "exactly 50 words" pads or truncates to hit the number, which
#: costs accuracy for no benefit.
_LENGTH_GUIDANCE: dict[str, str] = {
    "very_short": "Skrifaðu eina til tvær setningar sem fanga meginatriðið.",
    "short": "Skrifaðu stutta samantekt, um það bil þrjár til fimm setningar.",
    "medium": "Skrifaðu samantekt í einni til tveimur málsgreinum sem nær helstu atriðum.",
    "detailed": (
        "Skrifaðu ítarlega samantekt sem nær öllum helstu atriðum, "
        "í nokkrum málsgreinum."
    ),
}

#: Roughly how many tokens each length may use. Local generation must always be
#: capped: an uncapped reasoning model on a CPU runs until it hits a timeout,
#: and the user sees a hang instead of a result. Set generously so output ends
#: at a sentence rather than being cut off.
LENGTH_TOKEN_BUDGET: dict[str, int] = {
    "very_short": 160,
    "short": 400,
    "medium": 800,
    "detailed": 1600,
}

_FORM_GUIDANCE: dict[str, str] = {
    "prose": (
        "Skrifaðu samfelldan texta í málsgreinum. Ekki nota punktalista. "
        "Ekki skrifa fyrirsögn."
    ),
    "bullets": (
        "Skrifaðu eingöngu punktalista og ekkert annað. Hver punktur byrjar á "
        "„- “ og stendur á eigin línu. Ekki skrifa fyrirsögn, inngang né "
        "samfelldan texta á undan eða eftir listanum."
    ),
}

_AUDIENCE_GUIDANCE: dict[str, str] = {
    "general": (
        "Lesandinn er almennur borgari án sérþekkingar á efninu. "
        "Útskýrðu fagorð í stuttu máli þegar þau eru nauðsynleg."
    ),
    "experts": (
        "Lesandinn er sérfræðingur á sviðinu. Þú mátt nota viðtekin fagorð "
        "án útskýringa, en haltu framsetningunni skýrri."
    ),
    "managers": (
        "Lesandinn er stjórnandi sem þarf að taka ákvörðun. Dragðu fram það "
        "sem skiptir máli fyrir ákvörðun, svo sem kostnað, tímalínu, áhættu "
        "og skyldur."
    ),
    "customers": (
        "Lesandinn er viðskiptavinur. Vertu skýr um hvað þetta þýðir fyrir "
        "hann, hvað hann þarf að gera og hvenær."
    ),
    "youth": (
        "Lesandinn er ungmenni. Notaðu einfalt og hversdagslegt orðalag og "
        "stuttar setningar, en ekki tala niður til lesandans."
    ),
}

_STYLE_GUIDANCE: dict[str, str] = {
    "plain": (
        "Notaðu einfalt mál: stuttar setningar, algeng orð og skýra röð "
        "hugsana. Ein hugsun í hverri setningu."
    ),
    "concise": "Vertu hnitmiðaður. Slepptu endurtekningum og orðalengingum.",
    "formal": "Notaðu formlegt málsnið sem hæfir opinberu erindi.",
    "neutral": "Notaðu hlutlaust málsnið án gildishlaðinna orða.",
    "friendly": "Notaðu vinalegt og aðgengilegt málsnið, án þess að verða óformlegur um of.",
}


def summary_user_prompt(text: str, length: str, form: str) -> str:
    """Prompt for summarizing a document, or a single chunk of one."""
    return (
        f"{_LENGTH_GUIDANCE[length]}\n"
        f"{_FORM_GUIDANCE[form]}\n\n"
        "Textinn sem á að draga saman er á milli merkjanna hér að neðan.\n\n"
        "<<<TEXTI\n"
        f"{text}\n"
        "TEXTI>>>"
    )


def chunk_summary_user_prompt(text: str, part: int, total: int) -> str:
    """Prompt for summarizing one part of a document that was split up.

    The model is told this is a fragment so that it does not write a conclusion
    for a document it has only seen part of.
    """
    return (
        f"Þetta er hluti {part} af {total} úr lengri texta. "
        "Dragðu saman efnisatriði þessa hluta á hlutlausan hátt. "
        "Ekki reyna að draga ályktun um textann í heild, því þú sérð hann ekki allan. "
        "Haltu öllum tölum, nöfnum og dagsetningum sem koma fyrir.\n\n"
        "<<<TEXTI\n"
        f"{text}\n"
        "TEXTI>>>"
    )


def combine_summaries_user_prompt(summaries: list[str], length: str, form: str) -> str:
    """Prompt for merging per-chunk summaries into the final summary."""
    joined = "\n\n".join(
        f"Hluti {index}:\n{summary}" for index, summary in enumerate(summaries, start=1)
    )
    return (
        "Hér að neðan eru samantektir á hlutum úr einum og sama textanum, í réttri röð.\n"
        "Sameinaðu þær í eina heildstæða samantekt á textanum öllum.\n"
        "Fjarlægðu endurtekningar en ekki fella niður efnisatriði, tölur, nöfn eða dagsetningar.\n"
        "Ekki vísa í „hluta 1“ eða „hluta 2“ í svarinu; samantektin á að lesast sem ein heild.\n"
        "Ekki skrifa fyrirsögn á borð við „Samantekt:“ — skilaðu samantektinni sjálfri.\n\n"
        f"{_LENGTH_GUIDANCE[length]}\n"
        f"{_FORM_GUIDANCE[form]}\n\n"
        "<<<SAMANTEKTIR\n"
        f"{joined}\n"
        "SAMANTEKTIR>>>"
    )


def simplify_user_prompt(text: str, audience: str, style: str) -> str:
    """Prompt for rewriting a document, or a single chunk of one."""
    return (
        f"{_AUDIENCE_GUIDANCE[audience]}\n"
        f"{_STYLE_GUIDANCE[style]}\n\n"
        "Umritaðu textann á milli merkjanna hér að neðan. "
        "Haltu sömu röð efnisatriða og í upprunalega textanum.\n\n"
        "<<<TEXTI\n"
        f"{text}\n"
        "TEXTI>>>"
    )
