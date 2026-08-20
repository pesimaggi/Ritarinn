"""Tests for the source scanners used by the privacy checks.

A stripper that removed too much would make those checks pass vacuously, so its
behaviour is pinned here.
"""

from __future__ import annotations

import pytest

from _source_scan import css_code, javascript_code, python_code, url_host


def test_python_drops_comments_and_docstrings_but_keeps_code() -> None:
    source = '''
"""Module docstring mentioning api.openai.com."""

# A comment mentioning sentry.io
ENDPOINT = "http://127.0.0.1:11434"


def f() -> str:
    """Docstring mentioning qwen."""
    return ENDPOINT
'''
    stripped = python_code(source)
    assert "api.openai.com" not in stripped
    assert "sentry.io" not in stripped
    assert "qwen" not in stripped
    assert "http://127.0.0.1:11434" in stripped
    assert "ENDPOINT" in stripped


def test_python_keeps_ordinary_string_literals() -> None:
    """A hosted endpoint written as a normal string must still be caught."""
    assert "api.openai.com" in python_code('URL = "https://api.openai.com/v1"')


def test_javascript_drops_both_comment_styles() -> None:
    source = """
// line comment about cdn.jsdelivr.net
/* block comment about fonts.googleapis.com */
const url = "http://127.0.0.1:8756/api";
"""
    stripped = javascript_code(source)
    assert "cdn.jsdelivr.net" not in stripped
    assert "fonts.googleapis.com" not in stripped
    assert "http://127.0.0.1:8756/api" in stripped


def test_javascript_does_not_treat_a_url_in_a_string_as_a_comment() -> None:
    """The scanner must not stop at the "//" in "https://"."""
    stripped = javascript_code('const u = "https://api.openai.com"; const after = 1;')
    assert "api.openai.com" in stripped
    assert "after" in stripped


def test_javascript_handles_template_literals_and_escapes() -> None:
    stripped = javascript_code('const u = `${base}/api`; const s = "a\\"b"; const t = 2;')
    assert "${base}/api" in stripped
    assert "t = 2" in stripped


def test_javascript_recovers_from_a_stray_quote() -> None:
    """An apostrophe in a regex must not swallow the rest of the file."""
    source = "const re = /[a-z']/;\nconst url = \"https://api.openai.com\";\n"
    assert "api.openai.com" in javascript_code(source)


def test_css_drops_comments_only() -> None:
    stripped = css_code("/* no @font-face here */\nbody { color: red; }")
    assert "@font-face" not in stripped
    assert "color: red" in stripped


@pytest.mark.parametrize(
    ("url", "host"),
    [
        ("http://127.0.0.1:8756", "127.0.0.1"),
        ("http://[::1]:5173", "::1"),
        ("http://localhost:5173", "localhost"),
        ("https://api.openai.com/v1", "api.openai.com"),
    ],
)
def test_url_host_handles_ipv6_brackets(url: str, host: str) -> None:
    assert url_host(url) == host
