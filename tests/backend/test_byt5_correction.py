"""The ByT5 correction provider.

The provider is optional, and these tests are written so that they say the same
thing whether or not PyTorch is installed on the machine running them: a suite
whose result depends on what happens to be in the developer's virtualenv is not
a check on anything. Package availability is therefore substituted explicitly,
and no test loads, downloads or needs the real 2.3 GB checkpoint — a small test
double stands in for it everywhere.

What is being protected here:

* the model is loaded at most once, and never per request;
* an absent model degrades the application rather than breaking it;
* Transformers and PyTorch objects stay inside the adapter;
* a mocked model's output turns into the same reviewable issues every time;
* an ordinary correction request opens no socket.
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import threading

import pytest
from fastapi.testclient import TestClient

from ritarinn.config import ConfigurationError, Settings, load_settings
from ritarinn.main import create_app
from ritarinn.services.correction import byt5 as byt5_module
from ritarinn.services.correction.base import CorrectionRequest, EngineUnavailableError
from ritarinn.services.correction.byt5 import ByT5CorrectionEngine
from ritarinn.services.correction.registry import EngineRegistry

from _source_scan import python_code

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


# -- test doubles -------------------------------------------------------------


class FakeCorrector:
    """Stands in for the checkpoint. Answers from a table, and counts its calls."""

    def __init__(self, corrections: dict[str, str] | None = None, device: str = "cpu") -> None:
        self.device = device
        self._corrections = corrections or {}
        self.calls: list[list[str]] = []

    def correct(self, sentences):
        self.calls.append(list(sentences))
        return [self._corrections.get(sentence, sentence) for sentence in sentences]


class CountingFactory:
    """A corrector factory that records how often it was asked to load."""

    def __init__(self, corrector: FakeCorrector | None = None) -> None:
        self.corrector = corrector or FakeCorrector()
        self.loads = 0

    def __call__(self, settings: Settings) -> FakeCorrector:
        self.loads += 1
        return self.corrector


def installed_settings(tmp_path: pathlib.Path, **overrides) -> Settings:
    """Settings describing a complete, enabled ByT5 installation."""
    model_dir = tmp_path / "byt5"
    model_dir.mkdir(exist_ok=True)
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "model.safetensors").write_bytes(b"")
    return Settings(byt5_enabled=True, byt5_model_path=str(model_dir), **overrides)


@pytest.fixture
def packages_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend torch and transformers are importable, whatever the machine has."""
    monkeypatch.setattr(byt5_module, "REQUIRED_PACKAGES", ())


@pytest.fixture
def packages_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pretend they are not, whatever the machine has."""
    monkeypatch.setattr(byt5_module, "REQUIRED_PACKAGES", ("ritarinn_no_such_package",))


# -- provider selection through configuration ---------------------------------


def test_the_default_selection_is_greynir_only() -> None:
    assert load_settings({}).correction_engines == ["greynir"]


def test_configuration_chooses_which_providers_run() -> None:
    """Switching ByT5 on is a configuration change, not a code change."""
    settings = load_settings({"RITARINN_CORRECTION_ENGINES": "greynir,byt5"})
    assert settings.correction_engines == ["greynir", "byt5"]
    registry = EngineRegistry(settings)
    assert [engine.name for engine in registry.resolve(None)] == ["greynir", "byt5"]


def test_configuration_can_select_byt5_alone() -> None:
    registry = EngineRegistry(load_settings({"RITARINN_CORRECTION_ENGINES": "byt5"}))
    assert [engine.name for engine in registry.resolve(None)] == ["byt5"]


def test_a_request_still_overrides_the_configured_default() -> None:
    registry = EngineRegistry(load_settings({"RITARINN_CORRECTION_ENGINES": "greynir,byt5"}))
    assert [engine.name for engine in registry.resolve(["greynir"])] == ["greynir"]


def test_a_misspelled_provider_name_fails_at_startup() -> None:
    """A typo must not become a puzzling error on the user's first proofread."""
    with pytest.raises(ConfigurationError) as excinfo:
        EngineRegistry(load_settings({"RITARINN_CORRECTION_ENGINES": "greynir,byt-5"}))
    assert "byt-5" in str(excinfo.value)


def test_the_configured_checkpoint_is_replaceable() -> None:
    """No checkpoint is wired in: the identifier is a setting like any other."""
    settings = load_settings({"RITARINN_BYT5_MODEL_ID": "eitthvad/annad-likan"})
    assert ByT5CorrectionEngine(settings).model_source == "eitthvad/annad-likan"


def test_a_local_path_wins_over_the_model_identifier(tmp_path: pathlib.Path) -> None:
    """Local paths are what make an installation reproducible and offline."""
    settings = installed_settings(tmp_path)
    assert ByT5CorrectionEngine(settings).model_source == settings.byt5_model_path


# -- unavailable: disabled, missing packages, missing weights -----------------


def test_disabled_by_default() -> None:
    status = ByT5CorrectionEngine(Settings()).status()
    assert status.available is False
    assert "RITARINN_BYT5_ENABLED" in (status.detail or "")


def test_missing_packages_are_named_with_the_command_that_installs_them(
    packages_absent: None,
) -> None:
    status = ByT5CorrectionEngine(Settings(byt5_enabled=True)).status()
    assert status.available is False
    assert "requirements-byt5.txt" in (status.detail or "")


def test_missing_weights_point_at_the_provisioning_command(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    settings = Settings(byt5_enabled=True, byt5_model_path=str(tmp_path / "nothing-here"))
    status = ByT5CorrectionEngine(settings).status()
    assert status.available is False
    assert "install_byt5.py" in (status.detail or "")


def test_a_directory_without_safetensors_is_not_a_checkpoint(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    """A pickled pytorch_model.bin alone is not accepted: it is never loaded."""
    model_dir = tmp_path / "pickled-only"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")
    (model_dir / "pytorch_model.bin").write_bytes(b"")
    settings = Settings(byt5_enabled=True, byt5_model_path=str(model_dir))
    assert ByT5CorrectionEngine(settings).status().available is False


def test_analyzing_without_an_installation_raises_a_clean_error(packages_absent: None) -> None:
    engine = ByT5CorrectionEngine(Settings(byt5_enabled=True))
    with pytest.raises(EngineUnavailableError) as excinfo:
        engine.analyze(CorrectionRequest(text="Halló."))
    assert excinfo.value.engine == "byt5"
    assert excinfo.value.detail


def test_warm_up_never_raises_when_the_model_is_missing(packages_absent: None) -> None:
    """A missing optional model must not stop the application from starting."""
    ByT5CorrectionEngine(Settings(byt5_enabled=True)).warm_up()


def test_warm_up_does_not_load_anything_when_disabled() -> None:
    factory = CountingFactory()
    ByT5CorrectionEngine(Settings(byt5_enabled=False), corrector_factory=factory).warm_up()
    assert factory.loads == 0


def test_a_status_check_never_loads_the_model(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    """The status panel is polled; it must not pay for a model load to answer."""
    factory = CountingFactory()
    engine = ByT5CorrectionEngine(installed_settings(tmp_path), corrector_factory=factory)
    for _ in range(5):
        assert engine.status().available is True
    assert factory.loads == 0


# -- the model is loaded once, and reused -------------------------------------


def test_the_model_is_loaded_at_most_once_per_instance(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    factory = CountingFactory()
    engine = ByT5CorrectionEngine(installed_settings(tmp_path), corrector_factory=factory)

    engine.warm_up()
    for _ in range(10):
        engine.analyze(CorrectionRequest(text="Fyrsta setningin. Önnur setningin."))

    assert factory.loads == 1


def test_concurrent_first_requests_still_load_once(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    """Two requests arriving together must not start two model loads."""
    factory = CountingFactory()
    engine = ByT5CorrectionEngine(installed_settings(tmp_path), corrector_factory=factory)

    barrier = threading.Barrier(4)

    def analyze() -> None:
        barrier.wait()
        engine.analyze(CorrectionRequest(text="Setning til að lesa yfir."))

    threads = [threading.Thread(target=analyze) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert factory.loads == 1


def test_a_failed_load_is_not_retried_on_every_request(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    """Retrying a multi-gigabyte load per keystroke would stall the application."""
    attempts = {"count": 0}

    def failing_factory(settings: Settings):
        attempts["count"] += 1
        raise RuntimeError("no weights here")

    engine = ByT5CorrectionEngine(installed_settings(tmp_path), corrector_factory=failing_factory)
    for _ in range(5):
        with pytest.raises(EngineUnavailableError):
            engine.analyze(CorrectionRequest(text="Halló."))

    assert attempts["count"] == 1
    assert engine.status().available is False


# -- mocked output becomes reviewable issues ----------------------------------


SENTENCE = "Þinngið samþikkti tilöguna."
CORRECTED = "Þingið samþykkti tillöguna."


def analyzing(tmp_path: pathlib.Path, text: str, corrections: dict[str, str]):
    corrector = FakeCorrector(corrections)
    engine = ByT5CorrectionEngine(
        installed_settings(tmp_path), corrector_factory=CountingFactory(corrector)
    )
    return engine.analyze(CorrectionRequest(text=text)), corrector


def test_mocked_output_becomes_individual_reviewable_issues(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    outcome, _ = analyzing(tmp_path, SENTENCE, {SENTENCE: CORRECTED})
    corrections = [(issue.original, issue.replacement) for issue in outcome.issues]
    assert corrections == [
        ("Þinngið", "Þingið"),
        ("samþikkti", "samþykkti"),
        ("tilöguna.", "tillöguna."),
    ]


def test_the_conversion_is_deterministic(packages_present: None, tmp_path: pathlib.Path) -> None:
    first = [
        issue.model_dump()
        for issue in analyzing(tmp_path, SENTENCE, {SENTENCE: CORRECTED})[0].issues
    ]
    for _ in range(3):
        again = [
            issue.model_dump()
            for issue in analyzing(tmp_path, SENTENCE, {SENTENCE: CORRECTED})[0].issues
        ]
        assert again == first


def test_issues_carry_their_provenance(packages_present: None, tmp_path: pathlib.Path) -> None:
    """`source` and `scope` are how a finding is attributed and rendered."""
    outcome, _ = analyzing(tmp_path, SENTENCE, {SENTENCE: CORRECTED})
    assert outcome.issues
    for issue in outcome.issues:
        assert issue.source == "byt5"
        assert issue.scope == "span"


def test_no_confidence_is_invented(packages_present: None, tmp_path: pathlib.Path) -> None:
    """The model reports no score, so no number appears in its place."""
    outcome, _ = analyzing(tmp_path, SENTENCE, {SENTENCE: CORRECTED})
    assert all(issue.confidence is None for issue in outcome.issues)


def test_no_error_code_is_invented(packages_present: None, tmp_path: pathlib.Path) -> None:
    """The model publishes no code vocabulary, so the category is not guessed."""
    outcome, _ = analyzing(tmp_path, SENTENCE, {SENTENCE: CORRECTED})
    assert all(issue.code is None for issue in outcome.issues)
    assert all(issue.category == "unknown" for issue in outcome.issues)


def test_spans_index_the_submitted_document(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    """Offsets are document-wide, not sentence-relative."""
    text = f"Fyrsta málsgrein er í lagi.\n\n{SENTENCE}"
    outcome, _ = analyzing(tmp_path, text, {SENTENCE: CORRECTED})
    assert outcome.issues
    for issue in outcome.issues:
        assert text[issue.start_char : issue.end_char] == issue.original


def test_offsets_are_utf16_code_units(packages_present: None, tmp_path: pathlib.Path) -> None:
    """An emoji counts as two units in the editor, and must not shift a span."""
    from conftest import js_slice

    text = f"Halló 🎉 heimur. {SENTENCE}"
    outcome, _ = analyzing(tmp_path, text, {SENTENCE: CORRECTED})
    assert outcome.issues
    for issue in outcome.issues:
        assert js_slice(text, issue.start_char, issue.end_char) == issue.original


def test_an_agreeing_model_produces_no_issues(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    outcome, _ = analyzing(tmp_path, "Þingið samþykkti tillöguna.", {})
    assert list(outcome.issues) == []


def test_the_document_is_never_returned_rewritten(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    """The outcome carries findings, not a replacement document."""
    outcome, _ = analyzing(tmp_path, SENTENCE, {SENTENCE: CORRECTED})
    assert not hasattr(outcome, "text")
    assert all(len(issue.original) < len(SENTENCE) for issue in outcome.issues)


def test_an_unrelated_answer_is_discarded(packages_present: None, tmp_path: pathlib.Path) -> None:
    """A model that answers something else has not corrected the sentence."""
    outcome, _ = analyzing(
        tmp_path, SENTENCE, {SENTENCE: "Ég veit ekki hvað þú átt við með þessu."}
    )
    assert list(outcome.issues) == []
    assert outcome.stats["rejected_suggestions"] == 1


def test_an_empty_answer_is_discarded(packages_present: None, tmp_path: pathlib.Path) -> None:
    """Generation that produced nothing must not become "delete this sentence"."""
    outcome, _ = analyzing(tmp_path, SENTENCE, {SENTENCE: ""})
    assert list(outcome.issues) == []


def test_a_truncated_answer_does_not_propose_deleting_the_rest(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    long_sentence = (
        "Þingið samþykkti tillöguna á fundi sínum í gær eftir langar umræður."
    )
    truncated = "Þingið samþykkti tillöguna á fundi"
    outcome, _ = analyzing(tmp_path, long_sentence, {long_sentence: truncated})
    assert all(issue.replacement for issue in outcome.issues)


def test_the_model_sees_one_sentence_at_a_time(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    """The checkpoint is trained per sentence, so it is given sentences."""
    _, corrector = analyzing(tmp_path, f"{SENTENCE} Önnur setning hér.", {SENTENCE: CORRECTED})
    assert corrector.calls == [[SENTENCE, "Önnur setning hér."]]


def test_one_call_per_request_not_one_per_sentence(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    """Batching is the adapter's job; the rest of the application never sees it."""
    text = " ".join(f"Setning númer {index}." for index in range(10))
    _, corrector = analyzing(tmp_path, text, {})
    assert len(corrector.calls) == 1


def test_a_pathological_sentence_is_left_alone(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    """One very long line must not stall the whole document."""
    settings = installed_settings(tmp_path, byt5_max_sentence_chars=20)
    corrector = FakeCorrector()
    engine = ByT5CorrectionEngine(settings, corrector_factory=CountingFactory(corrector))
    outcome = engine.analyze(CorrectionRequest(text="Stutt. " + "x" * 100 + "."))
    assert outcome.stats["skipped_long_sentences"] == 1
    assert corrector.calls == [["Stutt."]]


def test_empty_text_is_not_sent_to_the_model(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    corrector = FakeCorrector()
    engine = ByT5CorrectionEngine(
        installed_settings(tmp_path), corrector_factory=CountingFactory(corrector)
    )
    assert list(engine.analyze(CorrectionRequest(text="   \n\n ")).issues) == []
    assert corrector.calls == []


# -- the adapter boundary -----------------------------------------------------

#: Names that belong to the model runtime and nowhere else in the application.
MODEL_RUNTIME_NAMES = [
    "transformers",
    "torch",
    "AutoTokenizer",
    "AutoModelForSeq2SeqLM",
    "from_pretrained",
    "safetensors",
    "huggingface_hub",
]

#: The one module allowed to know about them.
ADAPTER = REPO_ROOT / "backend" / "ritarinn" / "services" / "correction" / "byt5.py"


def test_model_runtime_names_appear_only_in_the_adapter() -> None:
    """Comments and documentation may discuss them; executable code may not.

    If this fails, something outside the adapter has started depending on how
    the model happens to be run — which is exactly what makes a model
    replaceable or not.
    """
    offenders: list[str] = []
    for path in (REPO_ROOT / "backend" / "ritarinn").rglob("*.py"):
        if path == ADAPTER:
            continue
        code = python_code(path.read_text(encoding="utf-8"))
        for name in MODEL_RUNTIME_NAMES:
            if name in code:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {name}")
    assert not offenders, "model runtime leaked out of the adapter: " + ", ".join(offenders)


def test_importing_the_application_does_not_import_pytorch() -> None:
    """Starting Ritarinn must not cost a PyTorch import, installed or not.

    Run in a fresh interpreter, because by this point in a test session almost
    anything could already be in ``sys.modules``.
    """
    script = (
        "import sys;"
        "sys.path.insert(0, %r);"
        "import ritarinn.main;"
        "import ritarinn.services.correction.byt5;"
        "leaked = [m for m in ('torch', 'transformers') if m in sys.modules];"
        "print(','.join(leaked))" % str(REPO_ROOT / "backend")
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=300
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "", f"imported at module scope: {result.stdout.strip()}"


def test_issues_are_plain_data(packages_present: None, tmp_path: pathlib.Path) -> None:
    """Whatever the model is, what leaves the adapter is JSON."""
    outcome, _ = analyzing(tmp_path, SENTENCE, {SENTENCE: CORRECTED})
    assert outcome.issues
    for issue in outcome.issues:
        json.dumps(issue.model_dump(by_alias=True))


def test_stats_are_counts_and_never_user_text(
    packages_present: None, tmp_path: pathlib.Path
) -> None:
    """Stats are logged, so a document must not be able to reach them."""
    outcome, _ = analyzing(tmp_path, SENTENCE, {SENTENCE: CORRECTED})
    for key, value in outcome.stats.items():
        assert isinstance(value, (int, float, str)), key
        if isinstance(value, str):
            assert value not in SENTENCE


# -- the Transformers loading path --------------------------------------------


class _FakeAuto:
    """Records the keyword arguments the adapter loads a checkpoint with."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def from_pretrained(self, source, **kwargs):
        self.calls.append((source, kwargs))
        return _FakeModel()


class _FakeModel:
    def to(self, device):
        return self

    def eval(self):
        return self


def test_the_loader_never_permits_a_download(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """The application must not be able to start a 2.3 GB download.

    The real Transformers entry points are substituted, so this asserts how the
    adapter asks for a checkpoint without loading one.
    """
    import types

    tokenizer_auto, model_auto = _FakeAuto(), _FakeAuto()
    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoTokenizer = tokenizer_auto
    fake_transformers.AutoModelForSeq2SeqLM = model_auto
    fake_torch = types.ModuleType("torch")

    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    settings = installed_settings(tmp_path, byt5_device="cpu")
    corrector = byt5_module.load_transformers_corrector(settings)

    assert corrector.device == "cpu"
    for _source, kwargs in tokenizer_auto.calls + model_auto.calls:
        assert kwargs["local_files_only"] is True
    # Safetensors only: loading a pickled checkpoint executes its contents.
    assert model_auto.calls[0][1]["use_safetensors"] is True


def test_device_selection_falls_back_to_cpu() -> None:
    """Every machine has a CPU, and this model is small enough to run on one."""
    import types

    torch_without_accelerators = types.ModuleType("torch")
    assert byt5_module.resolve_device("auto", torch_without_accelerators) == "cpu"


def test_an_explicit_device_is_honoured() -> None:
    """On a multi-GPU machine the right answer is the user's to give."""
    import types

    fake_torch = types.ModuleType("torch")
    assert byt5_module.resolve_device("cuda:1", fake_torch) == "cuda:1"


# -- the application with ByT5 configured on ----------------------------------


@pytest.fixture
def byt5_app(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> TestClient:
    """A full application with both providers on and a test double behind ByT5."""
    monkeypatch.setattr(byt5_module, "REQUIRED_PACKAGES", ())
    monkeypatch.setattr(
        byt5_module,
        "load_transformers_corrector",
        lambda settings: FakeCorrector({SENTENCE: CORRECTED}),
    )
    settings = installed_settings(tmp_path, correction_engines=["greynir", "byt5"])
    with TestClient(create_app(settings)) as client:
        yield client


def test_both_providers_report_ready(byt5_app: TestClient) -> None:
    """How a user verifies locally that the provider they configured is active."""
    engines = byt5_app.get("/api/models/status").json()["correctionEngines"]
    by_name = {engine["name"]: engine for engine in engines}
    assert by_name["greynir"]["available"] is True
    assert by_name["byt5"]["available"] is True
    # The status names the checkpoint that is answering, not just that one is.
    assert by_name["byt5"]["version"]
    assert by_name["byt5"]["localOnly"] is True


def test_both_providers_contribute_issues(byt5_app: TestClient) -> None:
    body = byt5_app.post("/api/proofread", json={"text": SENTENCE}).json()
    assert set(body["engines"]) == {"greynir", "byt5"}
    assert {issue["source"] for issue in body["issues"]} == {"greynir", "byt5"}


def test_issues_from_both_providers_stay_ordered_by_position(byt5_app: TestClient) -> None:
    body = byt5_app.post("/api/proofread", json={"text": SENTENCE}).json()
    positions = [(issue["startChar"], issue["endChar"]) for issue in body["issues"]]
    assert positions == sorted(positions)


def test_greynir_alone_is_unchanged_by_byt5_being_on(byt5_app: TestClient) -> None:
    """Enabling the neural provider must not alter what the rule-based one says."""
    body = byt5_app.post("/api/proofread", json={"text": SENTENCE, "engines": ["greynir"]}).json()
    assert body["engines"] == ["greynir"]
    corrections = {issue["original"]: issue["replacement"] for issue in body["issues"]}
    assert corrections == {
        "Þinngið": "Þingið",
        "samþikkti": "samþykkti",
        "tilöguna": "tillöguna",
    }


def test_an_ordinary_correction_request_opens_no_socket(
    byt5_app: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Proofreading is local. Not "local by policy" — there is nothing to call.

    Every way of opening a connection is made to fail loudly, and a full
    proofread with both providers still succeeds.
    """
    import socket

    def refuse(*args, **kwargs):
        raise AssertionError("proofreading attempted a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)

    response = byt5_app.post("/api/proofread", json={"text": SENTENCE})
    assert response.status_code == 200
    assert response.json()["issues"]


# -- graceful degradation in the application ----------------------------------


@pytest.fixture
def byt5_configured_but_missing(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """ByT5 in the default selection, with nothing installed behind it."""
    monkeypatch.setattr(byt5_module, "REQUIRED_PACKAGES", ("ritarinn_no_such_package",))
    settings = Settings(byt5_enabled=True, correction_engines=["greynir", "byt5"])
    with TestClient(create_app(settings)) as client:
        yield client


def test_a_missing_provider_does_not_take_proofreading_down(
    byt5_configured_but_missing: TestClient,
) -> None:
    body = byt5_configured_but_missing.post("/api/proofread", json={"text": SENTENCE}).json()
    assert body["issues"], "GreynirCorrect should still have found the misspellings"
    assert {issue["source"] for issue in body["issues"]} == {"greynir"}


def test_the_response_reports_which_providers_actually_ran(
    byt5_configured_but_missing: TestClient,
) -> None:
    """Skipping is reported, not hidden: `engines` lists what really answered."""
    body = byt5_configured_but_missing.post("/api/proofread", json={"text": SENTENCE}).json()
    assert body["engines"] == ["greynir"]
    assert "byt5.skipped" in body["stats"]


def test_asking_for_a_missing_provider_by_name_still_fails(
    byt5_configured_but_missing: TestClient,
) -> None:
    """An explicit request gets an explicit answer rather than a silent skip."""
    response = byt5_configured_but_missing.post(
        "/api/proofread", json={"text": SENTENCE, "engines": ["byt5"]}
    )
    assert response.status_code == 503
