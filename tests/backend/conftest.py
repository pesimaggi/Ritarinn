"""Shared fixtures.

The GreynirCorrect engine is expensive to load, so the application is built once
per test session and shared. Tests that need a different configuration build
their own app.
"""

from __future__ import annotations

import json
import pathlib
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from ritarinn.config import Settings, load_settings
from ritarinn.main import create_app

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CORPUS_PATH = REPO_ROOT / "corpus" / "cases.json"


@pytest.fixture(scope="session")
def settings() -> Settings:
    # An explicit empty environment, so a developer's own RITARINN_* variables
    # cannot change what the tests assert.
    return load_settings({})


@pytest.fixture(scope="session")
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def corpus() -> list[dict]:
    with CORPUS_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)["cases"]


def js_slice(text: str, start: int, end: int) -> str:
    """Slice *text* the way JavaScript would, by UTF-16 code unit.

    Python slices by code point, so it cannot verify UTF-16 offsets on its own.
    Encoding to UTF-16 and slicing the bytes reproduces exactly what
    ``String.prototype.slice`` does in the browser.
    """
    units = text.encode("utf-16-le")
    return units[start * 2 : end * 2].decode("utf-16-le")
