#!/usr/bin/env python3
"""Fetch the Icelandic ByT5 correction model, deliberately and once.

Ritarinn never downloads a model on your behalf. The application loads weights
with downloads disabled, so neither startup nor a proofread can reach the
network — which means the weights have to get onto the disk some other way, and
this is it. You run it, you see what it costs, and afterwards the installation
works offline.

    python scripts/install_byt5.py            # download into ./models/…
    python scripts/install_byt5.py --check    # verify what is already there
    python scripts/install_byt5.py --print-env

What it fetches (about 2.3 GB), and under what terms:

    mideind/yfirlestur-icelandic-correction-byt5
    Miðeind ehf. — https://huggingface.co/mideind/yfirlestur-icelandic-correction-byt5
    Licence: CC BY-SA 4.0 — https://creativecommons.org/licenses/by-sa/4.0/
    Fine-tuned from google/byt5-base (Apache-2.0)

The upstream repository publishes the weights twice, as `model.safetensors` and
as a pickled `pytorch_model.bin`. Only the safetensors file is downloaded:
unpickling executes whatever is inside the file, and there is no reason to take
that risk when the same weights are available in a format that cannot.

Nothing about this script is specific to this checkpoint beyond the default
`--model-id`. Point it at a different Icelandic corrector and Ritarinn will load
that one instead — no provider should become a permanent dependency.
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from ritarinn.config import DEFAULT_BYT5_MODEL_ID  # noqa: E402

#: Where the weights land by default. Inside the repository so that an
#: installation is self-contained and easy to delete; `.gitignore` keeps it out
#: of version control.
DEFAULT_TARGET = REPO_ROOT / "models" / "byt5-icelandic-correction"

#: Everything needed to load the model, and nothing else. The pickled
#: `pytorch_model.bin` is excluded on purpose — see the module docstring.
ALLOW_PATTERNS = [
    "config.json",
    "generation_config.json",
    "model.safetensors",
    "model.safetensors.index.json",
    "special_tokens_map.json",
    "tokenizer_config.json",
    "added_tokens.json",
    "README.md",
]

LICENCE_NOTICE = """\
Licence: CC BY-SA 4.0 (Miðeind ehf.), fine-tuned from google/byt5-base (Apache-2.0).
Attribution and the open question about share-alike are recorded in
THIRD_PARTY_NOTICES.md, section 1. The weights are yours to use locally; they are
not redistributed by Ritarinn and must not be bundled without checking the terms.
"""


def _fail(message: str) -> int:
    print(f"\n  ✗ {message}\n", file=sys.stderr)
    return 1


def check(target: pathlib.Path) -> int:
    """Report whether *target* holds a loadable checkpoint. Downloads nothing."""
    from ritarinn.config import Settings
    from ritarinn.services.correction.byt5 import model_files_present

    settings = Settings(byt5_enabled=True, byt5_model_path=str(target))
    if not model_files_present(settings):
        return _fail(
            f"No loadable checkpoint in {target}.\n"
            f"    Run: python scripts/install_byt5.py --target {target}"
        )

    total = sum(f.stat().st_size for f in target.rglob("*") if f.is_file())
    print(f"  ✓ Checkpoint found in {target} ({total / 1e9:.2f} GB)")
    print_env(target)
    return 0


def print_env(target: pathlib.Path) -> None:
    """Print the configuration that switches the provider on."""
    print(
        "\nTo enable it, set these and restart the backend:\n"
        f"\n    export RITARINN_BYT5_ENABLED=1"
        f"\n    export RITARINN_BYT5_MODEL_PATH={target}"
        "\n    export RITARINN_CORRECTION_ENGINES=greynir,byt5   # optional: run both by default"
        "\n\nThen check that it is actually active:\n"
        "\n    curl -s http://127.0.0.1:8756/api/models/status"
        "\n"
    )


def download(model_id: str, target: pathlib.Path, revision: str | None) -> int:
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        return _fail(
            "huggingface_hub is not installed.\n"
            "    Run: pip install -r backend/requirements-byt5.txt"
        )

    free = shutil.disk_usage(target.parent if target.parent.exists() else REPO_ROOT).free
    print(f"\nDownloading {model_id}")
    print("  about 2.3 GB, safetensors only (the pickled copy is skipped)")
    print(f"  free space here: {free / 1e9:.1f} GB")
    print(f"  destination: {target}")
    print(f"\n{LICENCE_NOTICE}")
    if free < 4e9:
        print("  ○ Less than 4 GB free. The download may not fit.\n")

    target.mkdir(parents=True, exist_ok=True)
    try:
        snapshot_download(
            repo_id=model_id,
            revision=revision,
            local_dir=str(target),
            allow_patterns=ALLOW_PATTERNS,
        )
    except Exception as exc:  # noqa: BLE001 - the message is the whole point
        return _fail(f"Download failed: {exc}")

    print("\n  ✓ Download complete.")
    return check(target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--model-id",
        default=DEFAULT_BYT5_MODEL_ID,
        help="Hugging Face model to fetch (default: %(default)s)",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="pin a specific commit of the model repository, for a reproducible install",
    )
    parser.add_argument(
        "--target",
        type=pathlib.Path,
        default=DEFAULT_TARGET,
        help="directory to install into (default: %(default)s)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify an existing installation without downloading anything",
    )
    parser.add_argument(
        "--print-env",
        action="store_true",
        help="print the configuration for an existing installation and exit",
    )
    args = parser.parse_args()

    target = args.target.resolve()
    if args.print_env:
        print_env(target)
        return 0
    if args.check:
        return check(target)
    return download(args.model_id, target, args.revision)


if __name__ == "__main__":
    raise SystemExit(main())
