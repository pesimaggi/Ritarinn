"""The installation scripts.

The Windows script embeds a Python snippet that verifies GreynirCorrect. It is
easy for such a snippet to rot unnoticed, because nobody runs it on Linux —
so it is extracted and executed here.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

UNIX_SCRIPTS = ["setup", "start"]
WINDOWS_SCRIPTS = ["setup.ps1", "start.ps1"]


@pytest.mark.parametrize("name", UNIX_SCRIPTS + WINDOWS_SCRIPTS)
def test_script_exists(name: str) -> None:
    assert (REPO_ROOT / name).is_file(), f"{name} is missing"


@pytest.mark.parametrize("name", UNIX_SCRIPTS)
def test_unix_script_is_executable(name: str) -> None:
    assert (REPO_ROOT / name).stat().st_mode & 0o111, f"{name} is not executable"


@pytest.mark.parametrize("name", UNIX_SCRIPTS)
def test_unix_script_has_valid_syntax(name: str) -> None:
    result = subprocess.run(
        ["bash", "-n", str(REPO_ROOT / name)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("name", WINDOWS_SCRIPTS)
def test_powershell_script_is_pure_ascii(name: str) -> None:
    """Windows PowerShell 5.1 mangles non-ASCII in a BOM-less .ps1.

    Rather than depend on a BOM surviving every editor and merge, the scripts
    stay ASCII and escape the Icelandic they need.
    """
    raw = (REPO_ROOT / name).read_bytes()
    non_ascii = [(index, byte) for index, byte in enumerate(raw) if byte > 0x7F]
    assert not non_ascii, f"{name} contains non-ASCII bytes at {non_ascii[:3]}"


def _embedded_verify_script() -> str:
    text = (REPO_ROOT / "setup.ps1").read_text(encoding="ascii")
    marker = "$verifyScript = @'\n"
    assert marker in text, "setup.ps1 no longer embeds a verification script"
    return text.split(marker, 1)[1].split("\n'@", 1)[0]


def test_windows_verification_snippet_is_valid_python() -> None:
    compile(_embedded_verify_script(), "setup.ps1:$verifyScript", "exec")


def test_windows_verification_snippet_actually_passes(tmp_path: pathlib.Path) -> None:
    """Run the snippet Windows users depend on.

    Its Icelandic is written with \\u escapes, which are easy to get subtly
    wrong — an escape consumes exactly four hex digits, so a following letter
    can be swallowed. Executing it is the only way to be sure.
    """
    script = tmp_path / "verify.py"
    script.write_text(_embedded_verify_script(), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, timeout=300
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"


def test_setup_does_not_download_models() -> None:
    """Setup must never pull multi-gigabyte weights on the user's behalf."""
    for name in ["setup", "setup.ps1"]:
        text = (REPO_ROOT / name).read_text(encoding="utf-8").lower()
        for forbidden in ["ollama pull", "ollama run", "huggingface-cli download", "hf download"]:
            assert forbidden not in text, f"{name} would download a model ({forbidden})"
