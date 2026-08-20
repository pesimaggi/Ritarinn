"""Helpers for scanning source files for forbidden endpoints.

The privacy tests need to answer "does this code talk to a hosted service?" —
which is a question about code, not about prose. A comment explaining that
Ritarinn deliberately avoids Google Fonts must not fail the test that checks
Ritarinn does not use Google Fonts.

So these helpers remove comments and documentation before scanning. They are
themselves covered by ``test_source_scan.py``, because a stripper that silently
removes too much would turn a security check into a no-op.
"""

from __future__ import annotations

import io
import tokenize
from urllib.parse import urlparse


def python_code(source: str) -> str:
    """Return Python source with comments and docstrings removed.

    Uses the standard tokenizer, so string contents, escapes and f-strings are
    handled correctly. Triple-quoted strings are dropped as documentation;
    anything a module actually connects to is written as an ordinary string
    literal.
    """
    kept: list[str] = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            continue
        if token.type == tokenize.STRING and _is_triple_quoted(token.string):
            continue
        kept.append(token.string)
    return "\n".join(kept)


def _is_triple_quoted(literal: str) -> bool:
    body = literal.lstrip("rbfuRBFU")
    return body.startswith('"""') or body.startswith("'''")


def javascript_code(source: str) -> str:
    """Return TypeScript/JavaScript source with comments removed.

    In valid JavaScript ``//`` and ``/*`` always begin a comment: an empty regex
    literal is not legal, and a regex cannot start with ``*``. That makes a
    small state machine sufficient, provided it also tracks string literals so
    that a URL inside a string is never mistaken for a comment.

    Unterminated single- and double-quoted strings are closed at end of line,
    since JavaScript does not allow them to span lines. That keeps an apostrophe
    inside a regex or a stray quote from swallowing the rest of the file.
    """
    out: list[str] = []
    index = 0
    length = len(source)
    quote: str | None = None

    while index < length:
        char = source[index]
        nxt = source[index + 1] if index + 1 < length else ""

        if quote is not None:
            out.append(char)
            if char == "\\" and index + 1 < length:
                out.append(nxt)
                index += 2
                continue
            if char == quote or (char == "\n" and quote in "\"'"):
                quote = None
            index += 1
            continue

        if char in "\"'`":
            quote = char
            out.append(char)
            index += 1
            continue

        if char == "/" and nxt == "/":
            while index < length and source[index] != "\n":
                index += 1
            continue

        if char == "/" and nxt == "*":
            end = source.find("*/", index + 2)
            index = length if end == -1 else end + 2
            continue

        out.append(char)
        index += 1

    return "".join(out)


def css_code(source: str) -> str:
    """Return CSS with ``/* … */`` comments removed. CSS has no line comments."""
    out: list[str] = []
    index = 0
    while index < len(source):
        start = source.find("/*", index)
        if start == -1:
            out.append(source[index:])
            break
        out.append(source[index:start])
        end = source.find("*/", start + 2)
        index = len(source) if end == -1 else end + 2
    return "".join(out)


def strip_comments(path_suffix: str, source: str) -> str:
    """Dispatch to the right stripper for a file extension."""
    if path_suffix == ".py":
        return python_code(source)
    if path_suffix in {".ts", ".tsx", ".js", ".jsx"}:
        return javascript_code(source)
    if path_suffix == ".css":
        return css_code(source)
    if path_suffix == ".html":
        return _strip_html_comments(source)
    return source


def _strip_html_comments(source: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(source):
        start = source.find("<!--", index)
        if start == -1:
            out.append(source[index:])
            break
        out.append(source[index:start])
        end = source.find("-->", start + 4)
        index = len(source) if end == -1 else end + 3
    return "".join(out)


def url_host(url: str) -> str:
    """Hostname of a URL, with IPv6 brackets handled.

    ``urlparse`` is used rather than string splitting because ``http://[::1]:5173``
    splits badly on ":" — a mistake that would report a loopback address as
    remote.
    """
    return urlparse(url).hostname or ""
