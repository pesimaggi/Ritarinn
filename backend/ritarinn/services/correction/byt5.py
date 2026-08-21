"""Optional neural correction provider: an Icelandic ByT5 sequence-to-sequence model.

`mideind/yfirlestur-icelandic-correction-byt5` (Miðeind ehf., CC BY-SA 4.0,
fine-tuned from `google/byt5-base`) rewrites an Icelandic sentence into a
corrected one. It sees the sentence in context, so it catches things a
rule-based engine cannot — and it also has opinions, invents nothing it is asked
about, and reports no error codes. See `THIRD_PARTY_NOTICES.md` section 1 for
the licence and its unresolved question, and `docs/roadmap.md` for what still
has to be evaluated before it can be recommended.

Three decisions shape this module.

**Everything model-shaped stays inside it.** The rest of Ritarinn talks to a
`CorrectionEngine` and receives `WritingIssue` objects. Tokenizers, tensors,
devices and checkpoint identifiers do not appear in routes, schemas or the
editor, so replacing this model — or this whole family of models — is a change
to one file. The seam is the `SentenceCorrector` protocol below: an object that
turns sentences into corrected sentences and nothing else.

**A rewrite is not a correction until it is broken into reviewable pieces.**
The model answers with a whole sentence. Substituting it for the user's would be
exactly the blind replacement Ritarinn refuses to do anywhere else, so the pair
is diffed and each differing region becomes one issue the user accepts or
rejects on its own (`diffing.py`).

**Nothing is downloaded, ever, by the application.** Weights are loaded with
downloads disabled, so neither startup nor a correction request can reach the
network — a missing model is reported as a missing model. Fetching it is
`scripts/install_byt5.py`, run deliberately by the user. Ritarinn works fully
without this provider; it is an addition to proofreading, not a prerequisite.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import threading
import time
from typing import Callable, Optional, Protocol, Sequence

from ritarinn.config import Settings
from ritarinn.models.issue import WritingIssue
from ritarinn.services.correction.base import (
    CorrectionEngine,
    CorrectionOutcome,
    CorrectionRequest,
    EngineStatus,
    EngineUnavailableError,
)
from ritarinn.services.correction.categories import SPAN_SCOPE, UNKNOWN
from ritarinn.services.correction.diffing import (
    TextEdit,
    anchor_insertions,
    diff_words,
    similarity,
)
from ritarinn.text.chunking import split_sentences
from ritarinn.text.offsets import Utf16OffsetMap

logger = logging.getLogger(__name__)

ENGINE_NAME = "byt5"
LABEL = "ByT5 tauganetsleiðrétting"
PROVENANCE = "yfirlestur-icelandic-correction-byt5 eftir Miðeind ehf. (CC BY-SA 4.0)"

#: Icelandic label for every issue this provider emits. It reports no error
#: codes, so there is nothing to classify and nothing is guessed at — see
#: ``_to_issue``.
FAMILY = "Tauganetsleiðrétting"

#: Python packages the provider needs. Deliberately absent from
#: ``backend/requirements.txt``: installing PyTorch is a decision with its own
#: size and licence consequences, and proofreading does not depend on it.
REQUIRED_PACKAGES = ("torch", "transformers")

#: Sentences per forward pass. Small on purpose — a byte-level model's memory
#: use scales with the longest sentence in the batch, and the machines Ritarinn
#: targets are ordinary laptops.
BATCH_SIZE = 4

#: How much of a sentence has to survive for the model's answer to be treated as
#: a correction of it. A seq2seq model that runs out of output budget, loses the
#: thread, or answers something else entirely returns a sentence with little to
#: do with the input; diffing that produces one enormous "replace this whole
#: sentence" suggestion, which is precisely the blind replacement Ritarinn
#: exists to avoid offering. Below this floor the answer is dropped and counted,
#: not shown. A safety floor rather than a tuning knob, so it is a constant.
MIN_SENTENCE_SIMILARITY = 0.5

#: The largest share of a sentence a single *deletion* may propose to remove.
#: Generation that stops early leaves the tail of the sentence missing, which
#: diffs into one edit deleting everything after the cut — never a correction,
#: and something a hurried user could accept. Replacements are not capped this
#: way: reworking most of a short sentence is a real correction.
MAX_DELETION_FRACTION = 0.5

# -- Icelandic status text ----------------------------------------------------

DISABLED_DETAIL = (
    "Tauganetsleiðrétting er ekki virk. Hún er valfrjáls viðbót við yfirlestur; "
    "kveiktu á henni með RITARINN_BYT5_ENABLED=1 þegar líkanið hefur verið sótt."
)
MISSING_PACKAGES_DETAIL = (
    "Tauganetsleiðréttingu vantar Python-pakka ({packages}). "
    "Settu þá upp með: pip install -r backend/requirements-byt5.txt"
)
MISSING_MODEL_DETAIL = (
    "Líkanaskrár fundust ekki ({source}). Sæktu líkanið með: "
    "python scripts/install_byt5.py"
)
LOAD_FAILED_DETAIL = "Ekki tókst að hlaða tauganetslíkaninu. Sjá annál bakendans."


class SentenceCorrector(Protocol):
    """The only thing this module needs a model to be able to do.

    Narrow on purpose: it is the boundary that keeps Transformers and PyTorch
    objects out of the rest of the application, and it is what a test double
    implements in place of a two-gigabyte checkpoint.
    """

    #: Torch device the model was placed on, for the status panel.
    device: str

    def correct(self, sentences: Sequence[str]) -> list[str]:
        """Return one corrected sentence per input sentence, in the same order."""


#: Builds a corrector from settings. Injectable so that tests — and any future
#: runtime that is not Transformers — can supply their own without this module
#: knowing about them.
CorrectorFactory = Callable[[Settings], SentenceCorrector]


class ByT5CorrectionEngine(CorrectionEngine):
    """Context-sensitive Icelandic correction, off unless installed and enabled."""

    name = ENGINE_NAME

    def __init__(
        self, settings: Settings, corrector_factory: Optional[CorrectorFactory] = None
    ) -> None:
        self._settings = settings
        self._factory: CorrectorFactory = corrector_factory or load_transformers_corrector
        self._corrector: Optional[SentenceCorrector] = None
        self._load_error: Optional[str] = None
        #: True once loading has been attempted, successfully or not. A failed
        #: load is not retried: this model takes seconds to load and gigabytes
        #: of memory, and retrying it on every keystroke-triggered proofread
        #: would turn one clear failure into a stalled application.
        self._load_attempted = False
        self._lock = threading.Lock()

    # -- lifecycle ------------------------------------------------------------

    def warm_up(self) -> None:
        """Load the model once, at startup, when the user has enabled it.

        Enabling the provider in configuration *is* the intentional
        initialization step. Loading here rather than on the first request keeps
        a multi-second load off the path of someone waiting for a proofread —
        and when it fails, it fails at startup where the message is visible,
        without preventing the application from starting.
        """
        if not self._settings.byt5_enabled:
            return
        try:
            self._ensure_loaded()
        except EngineUnavailableError as exc:
            logger.warning("ByT5 correction is unavailable: %s", exc.detail)

    def _ensure_loaded(self) -> SentenceCorrector:
        """Return the loaded model, loading it at most once per instance."""
        if self._corrector is not None:
            return self._corrector
        with self._lock:
            if self._corrector is not None:
                return self._corrector
            if self._load_attempted:
                raise EngineUnavailableError(ENGINE_NAME, self._load_error or LOAD_FAILED_DETAIL)
            self._load_attempted = True

            unavailable = self._why_unavailable()
            if unavailable is not None:
                self._load_error = unavailable
                raise EngineUnavailableError(ENGINE_NAME, unavailable)

            started = time.perf_counter()
            try:
                self._corrector = self._factory(self._settings)
            except Exception as exc:  # pragma: no cover - depends on install state
                self._load_error = LOAD_FAILED_DETAIL
                logger.exception("Loading the ByT5 correction model failed")
                raise EngineUnavailableError(ENGINE_NAME, LOAD_FAILED_DETAIL) from exc
            logger.info(
                "ByT5 correction model loaded on %s in %.0f ms",
                self._corrector.device,
                (time.perf_counter() - started) * 1000,
            )
        return self._corrector

    # -- readiness ------------------------------------------------------------

    def status(self) -> EngineStatus:
        if self._corrector is not None:
            detail, available = None, True
        else:
            # Before a load is attempted this reports installability rather
            # than paying the load cost; afterwards it reports what went wrong,
            # since a failed load is not retried.
            detail = self._load_error if self._load_attempted else self._why_unavailable()
            available = detail is None
        return EngineStatus(
            name=ENGINE_NAME,
            label=LABEL,
            available=available,
            # The identity of what is (or would be) loaded, so a user can check
            # which checkpoint is actually answering rather than assuming.
            version=self.model_source if available else None,
            detail=detail,
            local_only=True,
            provenance=PROVENANCE,
        )

    @property
    def model_source(self) -> str:
        """The local directory or model identifier the weights come from."""
        return self._settings.byt5_model_path or self._settings.byt5_model_id

    def _why_unavailable(self) -> Optional[str]:
        """Icelandic explanation of what is missing, or None when ready.

        Cheap by contract — ``status()`` is called on every status poll, so this
        checks for files and importable packages and never loads anything.
        """
        if not self._settings.byt5_enabled:
            return DISABLED_DETAIL
        missing = [name for name in REQUIRED_PACKAGES if importlib.util.find_spec(name) is None]
        if missing:
            return MISSING_PACKAGES_DETAIL.format(packages=", ".join(missing))
        if not model_files_present(self._settings):
            return MISSING_MODEL_DETAIL.format(source=self.model_source)
        return None

    # -- analysis -------------------------------------------------------------

    def analyze(self, request: CorrectionRequest) -> CorrectionOutcome:
        corrector = self._ensure_loaded()
        text = request.text
        if not text.strip():
            return CorrectionOutcome(issues=[], stats={"sentences": 0})

        started = time.perf_counter()
        spans = self._sentence_spans(text)
        limit = self._settings.byt5_max_sentence_chars
        # A byte-level model costs time in proportion to characters, so one
        # pathological line is left alone rather than allowed to stall the rest.
        analysable = [(start, end) for start, end in spans if end - start <= limit]
        skipped = len(spans) - len(analysable)

        corrected = corrector.correct([text[start:end] for start, end in analysable])
        if len(corrected) != len(analysable):
            raise EngineUnavailableError(
                ENGINE_NAME,
                "Tauganetslíkanið skilaði óvæntum fjölda setninga.",
            )

        offsets = Utf16OffsetMap(text)
        issues: list[WritingIssue] = []
        rejected = 0
        for (start, end), suggestion in zip(analysable, corrected):
            sentence = text[start:end]
            if similarity(sentence, suggestion) < MIN_SENTENCE_SIMILARITY:
                rejected += 1
                continue
            for edit in anchor_insertions(sentence, diff_words(sentence, suggestion)):
                if edit.is_deletion and (edit.end - edit.start) >= (
                    len(sentence) * MAX_DELETION_FRACTION
                ):
                    rejected += 1
                    continue
                issues.append(self._to_issue(edit, start, offsets, len(issues)))

        stats: dict[str, float | int | str] = {
            "sentences": len(spans),
            "analysed_sentences": len(analysable),
            "issues": len(issues),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "device": corrector.device,
        }
        if skipped:
            stats["skipped_long_sentences"] = skipped
        if rejected:
            # Reported rather than hidden: a model rejecting many sentences is
            # a sign that something is wrong with the installation, and the
            # counts here are the only place that would show.
            stats["rejected_suggestions"] = rejected
        return CorrectionOutcome(issues=issues, stats=stats)

    def _sentence_spans(self, text: str) -> list[tuple[int, int]]:
        """Character spans of each sentence, trimmed to its non-whitespace core.

        The model was trained on one sentence at a time. ``split_sentences``
        loses no characters, so walking its output accumulates exact document
        offsets; the surrounding whitespace is then excluded so that neither the
        model nor the diff has to reason about paragraph breaks.
        """
        spans: list[tuple[int, int]] = []
        cursor = 0
        for piece in split_sentences(text):
            start = cursor
            cursor += len(piece)
            leading = len(piece) - len(piece.lstrip())
            trailing = len(piece) - len(piece.rstrip())
            core_start, core_end = start + leading, cursor - trailing
            if core_start < core_end:
                spans.append((core_start, core_end))
        return spans

    def _to_issue(
        self, edit: TextEdit, sentence_start: int, offsets: Utf16OffsetMap, index: int
    ) -> WritingIssue:
        start = sentence_start + edit.start
        end = sentence_start + edit.end
        return WritingIssue(
            id=f"{ENGINE_NAME}-{index}-{start}-{end}",
            # Provenance travels with the issue: the sidebar can attribute this
            # to the neural provider without inspecting anything else.
            source="byt5",
            # The model reports no error code and no category. Ritarinn does not
            # invent either, so these land in "unknown" — the same treatment an
            # unrecognised GreynirCorrect code gets — rather than being guessed
            # into "spelling" or "grammar". Miðeind publishes a companion
            # classification model; using it is noted in the roadmap.
            category=UNKNOWN,
            code=None,
            family=FAMILY,
            start_char=offsets.to_utf16(start),
            end_char=offsets.to_utf16(end),
            # Always a word-level span: a whole-sentence rewrite was broken into
            # word-level edits precisely so it would never be one.
            scope=SPAN_SCOPE,
            original=edit.original,
            replacement=edit.replacement,
            alternatives=[],
            title=_title(edit),
            explanation=(
                "Tillaga frá tauganetslíkani sem les setninguna í samhengi. "
                "Líkanið gefur enga skýringu og engan vissustuðul — "
                "metið tillöguna sjálf."
            ),
            # Advisory rather than an error: unlike GreynirCorrect's "/w" marker
            # this model publishes no severity distinction, and a neural rewrite
            # is a suggestion about the sentence, not a rule that was broken.
            severity="warning",
            references=[],
            # No score is reported by the model, so none is reported here. A
            # fabricated percentage would be worse than no number at all.
            confidence=None,
        )


def _title(edit: TextEdit) -> str:
    """Icelandic one-line heading describing the edit."""
    if edit.is_deletion:
        return f"Tauganet leggur til að fella brott „{edit.original}“"
    return f"Tauganet leggur til „{edit.replacement}“ í stað „{edit.original}“"


# -- model files --------------------------------------------------------------

#: Files a usable checkpoint directory has to contain. Safetensors only: loading
#: a pickled ``pytorch_model.bin`` executes whatever is inside it, and the
#: upstream repository publishes both formats, so the safe one is required.
REQUIRED_MODEL_FILES = ("config.json",)
WEIGHT_FILES = ("model.safetensors", "model.safetensors.index.json")


def model_files_present(settings: Settings) -> bool:
    """True when the configured checkpoint can be loaded without a download.

    A configured directory is checked directly. Without one, the model
    identifier is resolved against the local Hugging Face cache — a filesystem
    lookup, not a request.
    """
    path = settings.byt5_model_path.strip()
    if path:
        return _directory_has_model(path)
    return _cache_has_model(settings.byt5_model_id)


def _directory_has_model(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    if not all(os.path.isfile(os.path.join(path, name)) for name in REQUIRED_MODEL_FILES):
        return False
    return any(os.path.isfile(os.path.join(path, name)) for name in WEIGHT_FILES)


def _cache_has_model(model_id: str) -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:  # pragma: no cover - ships with transformers
        return False
    try:
        cached = try_to_load_from_cache(model_id, "config.json")
    except Exception:  # pragma: no cover - a malformed cache is not a crash
        return False
    return isinstance(cached, str)


# -- the Transformers implementation ------------------------------------------


def load_transformers_corrector(settings: Settings) -> SentenceCorrector:
    """Load the checkpoint with PyTorch and Transformers.

    Imports happen here rather than at module scope so that importing Ritarinn
    never costs a PyTorch import, and so an installation without these packages
    reports an unavailable provider instead of failing to start.
    """
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    source = settings.byt5_model_path or settings.byt5_model_id
    # local_files_only is not configurable: the application must not be able to
    # start a multi-gigabyte download, whether at startup or mid-request.
    tokenizer = AutoTokenizer.from_pretrained(source, local_files_only=True)
    model = AutoModelForSeq2SeqLM.from_pretrained(
        source, local_files_only=True, use_safetensors=True
    )
    device = resolve_device(settings.byt5_device, torch)
    model.to(device)
    model.eval()
    return _TransformersCorrector(
        tokenizer=tokenizer,
        model=model,
        torch_module=torch,
        device=device,
        max_output_ratio=settings.byt5_max_output_ratio,
    )


def resolve_device(spec: str, torch_module: object) -> str:
    """Pick a torch device, honouring an explicit choice.

    "auto" prefers an accelerator when one is present and falls back to CPU,
    which every machine has and which this model is small enough to run on. Any
    other value is passed through: on a multi-GPU machine the right answer is
    the user's to give.
    """
    if spec and spec != "auto":
        return spec
    cuda = getattr(torch_module, "cuda", None)
    if cuda is not None and cuda.is_available():
        return "cuda"
    backends = getattr(torch_module, "backends", None)
    mps = getattr(backends, "mps", None) if backends is not None else None
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


class _TransformersCorrector:
    """Runs the checkpoint. The only object in Ritarinn that holds a tensor."""

    def __init__(
        self,
        tokenizer: object,
        model: object,
        torch_module: object,
        device: str,
        max_output_ratio: float,
    ) -> None:
        self._tokenizer = tokenizer
        self._model = model
        self._torch = torch_module
        self.device = device
        self._max_output_ratio = max_output_ratio

    def correct(self, sentences: Sequence[str]) -> list[str]:
        results: list[str] = []
        for index in range(0, len(sentences), BATCH_SIZE):
            results.extend(self._correct_batch(list(sentences[index : index + BATCH_SIZE])))
        return results

    def _correct_batch(self, batch: list[str]) -> list[str]:
        if not batch:
            return []
        encoded = self._tokenizer(batch, return_tensors="pt", padding=True).to(self.device)
        # ByT5 emits bytes, so the output budget is measured in bytes of input.
        # The margin covers a correction that is legitimately longer than what
        # it replaces; without it a fix at the end of a sentence is cut off.
        longest = max(len(sentence.encode("utf-8")) for sentence in batch)
        budget = int(longest * self._max_output_ratio) + 16

        with self._torch.inference_mode():
            generated = self._model.generate(
                **encoded,
                max_new_tokens=budget,
                # Greedy and unsampled: proofreading the same paragraph twice
                # has to produce the same suggestions, or accepting one becomes
                # a gamble on what the sidebar happens to show.
                do_sample=False,
                num_beams=1,
            )
        return list(self._tokenizer.batch_decode(generated, skip_special_tokens=True))
