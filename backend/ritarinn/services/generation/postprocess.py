"""Proofreading generated Icelandic with GreynirCorrect.

A local model's Icelandic is not reliably correct, and the specialised tools
Ritarinn already has can say so. Running generated text back through
GreynirCorrect combines the model's semantic ability with real Icelandic
linguistic analysis.

What this must *not* do is apply the corrections. A summary is a claim about
meaning; silently rewriting it on the strength of a grammar rule could change
that claim. The issues are shown to the user, who decides — the same contract
as the proofreading tab.
"""

from __future__ import annotations

import logging
from typing import Sequence

from ritarinn.models.issue import WritingIssue
from ritarinn.services.correction.base import CorrectionRequest
from ritarinn.services.correction.registry import EngineRegistry

logger = logging.getLogger(__name__)


def proofread_generated_text(
    registry: EngineRegistry, text: str, engine_name: str = "greynir"
) -> Sequence[WritingIssue]:
    """Return issues found in generated text, or nothing if unavailable.

    Failure here must never fail the generation that produced the text: the
    user asked for a summary, and getting one without an advisory grammar check
    is better than getting an error.
    """
    if not text.strip():
        return ()
    try:
        engine = registry.get(engine_name)
        if not engine.status().available:
            return ()
        outcome = engine.analyze(CorrectionRequest(text=text))
    except Exception:
        logger.exception("Proofreading generated text failed; continuing without it")
        return ()

    issues = list(outcome.issues)
    logger.info("post-processed generated text | issues=%d", len(issues))
    return issues
