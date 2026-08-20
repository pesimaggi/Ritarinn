"""Logging that cannot leak the user's document.

Ritarinn logs what happened, never what was written. Request handlers log
counts, durations and error codes; they do not log text, prompts or model
output. The filter below is a backstop, not the primary defence — the primary
defence is that no call site passes document text to the logger.
"""

from __future__ import annotations

import logging
import sys

#: Attribute name a log record can carry to assert it holds no user text.
_SAFE_MARKER = "ritarinn_safe"


class NoDocumentTextFilter(logging.Filter):
    """Drops overlong log messages as a defence against accidental text logging.

    A legitimate Ritarinn log line is short — "proofread completed, 8 issues,
    146 ms". A line long enough to be a paragraph of someone's document is
    treated as a bug and replaced rather than written out.
    """

    def __init__(self, max_message_chars: int = 500) -> None:
        super().__init__()
        self._max = max_message_chars

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, _SAFE_MARKER, False):
            return True
        try:
            message = record.getMessage()
        except Exception:
            return True
        if len(message) > self._max:
            record.msg = (
                "[log line suppressed: %d characters, which may contain document text]"
                % len(message)
            )
            record.args = ()
        return True


def configure_logging(level: str = "INFO") -> None:
    """Install Ritarinn's logging configuration on the root logger."""
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    handler.addFilter(NoDocumentTextFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # Uvicorn's access log records URLs only, which carry no document text
    # because every text-bearing endpoint takes a POST body.
    logging.getLogger("uvicorn.access").setLevel("WARNING")

    # httpx logs every request line at INFO. Ritarinn only uses it to probe a
    # loopback Ollama, so the noise buys nothing and the lines look alarming in
    # an application that advertises making no network calls.
    logging.getLogger("httpx").setLevel("WARNING")
    logging.getLogger("httpcore").setLevel("WARNING")
