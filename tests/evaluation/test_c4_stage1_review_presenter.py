from __future__ import annotations

import hashlib
import json
import shutil
import struct
import threading
from pathlib import Path
from types import SimpleNamespace
from typing import Any
import zlib

import pytest

from rei.evaluation.c4_blind_review import C4BlindOutputReference
from rei.evaluation.c4_stage1_review import (
    C4Stage1DisplayContext,
    C4Stage1VisibleOutput,
)
from rei.evaluation.c4_stage1_review_presenter import (
    C4_STAGE1_PLAYWRIGHT_CHROMIUM_REVISION,
    C4_STAGE1_PLAYWRIGHT_CHROMIUM_VERSION,
    C4_STAGE1_PLAYWRIGHT_PYTHON_VERSION,
    C4Stage1OfflineReviewPresenter,
    C4Stage1ReviewPresenterError,
    _parse_png_pixel_identity,
)
from rei.evaluation.c4_stage1_review_runtime import (
    C4_STAGE1_REVIEW_IPC_PROTOCOL,
    C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
    C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID,
    C4_STAGE1_REVIEW_PRESENTER_REVISION,
    C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
    capture_c4_stage1_review_runtime_manifest,
)
from rei.ids import canonical_json_bytes, content_id


ROOT = Path(__file__).resolve().parents[2]
UI_RELATIVE = Path("app/backend/rei/evaluation/c4_stage1_review_ui")
INDEX_URL = "https://rei-c4-stage1.invalid/index.html"
OUTPUT_FIELDS = (
    "source_subject_present",
    "identity_preserved",
    "unchanged_composition_preserved",
    "option_action_correct",
    "no_extra_actor",
    "no_generated_external_evidence_claim",
    "reviewer_uncertain",
)
PAIR_FIELDS = (
    "actions_visibly_distinct",
    "same_source_bytes_confirmed",
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _digest(label: str) -> str:
    return _sha256(label.encode("utf-8"))


def _chunk(kind: bytes, value: bytes) -> bytes:
    return (
        struct.pack(">I", len(value))
        + kind
        + value
        + struct.pack(">I", zlib.crc32(kind + value) & 0xFFFFFFFF)
    )


def _png(red: int, green: int, blue: int) -> bytes:
    width = height = 8
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    scanlines = b"".join(
        bytes((0,))
        + b"".join(
            bytes(
                (
                    (red + row + column) & 0xFF,
                    (green + (2 * row) + column) & 0xFF,
                    (blue + row + (2 * column)) & 0xFF,
                )
            )
            for column in range(width)
        )
        for row in range(height)
    )
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"tEXt", b"fixture\x00original-metadata")
        + _chunk(b"IDAT", zlib.compress(scanlines, level=9))
        + _chunk(b"IEND", b"")
    )


def _png_pixel_identity(
    value: bytes,
) -> tuple[bytes, bytes | None, bytes | None, bytes]:
    identity = _parse_png_pixel_identity(value)
    return identity.ihdr, None, None, identity.decoded_pixels


def _concatenated_idat(value: bytes) -> bytes:
    offset = 8
    result = bytearray()
    while offset < len(value):
        length = struct.unpack(">I", value[offset : offset + 4])[0]
        kind = value[offset + 4 : offset + 8]
        chunk_value = value[offset + 8 : offset + 8 + length]
        if kind == b"IDAT":
            result.extend(chunk_value)
        offset += 12 + length
        if kind == b"IEND":
            break
    return bytes(result)


def _material(manifest):
    source = _png(1, 2, 3)
    raw = (
        ("blind-alpha", "The figure enters the circle.", _png(4, 5, 6)),
        ("blind-beta", "The figure remains at the edge.", _png(7, 8, 9)),
    )
    references = sorted(
        [
            (
                C4BlindOutputReference(
                    blind_code=blind_code,
                    blind_order_sha256=_sha256(blind_code.encode("utf-8")),
                    option_id=f"option-{index}",
                    instruction=instruction,
                    instruction_sha256=_sha256(instruction.encode("utf-8")),
                    output_sha256=_sha256(png_bytes),
                ),
                png_bytes,
            )
            for index, (blind_code, instruction, png_bytes) in enumerate(raw)
        ],
        key=lambda item: item[0].blind_order_sha256,
    )
    outputs = tuple(
        C4Stage1VisibleOutput(
            blind_code=reference.blind_code,
            blind_order_sha256=reference.blind_order_sha256,
            instruction=reference.instruction,
            instruction_sha256=reference.instruction_sha256,
            output_sha256=reference.output_sha256,
            png_bytes=png_bytes,
        )
        for reference, png_bytes in references
    )
    base = {
        "schema_version": "rei-c4-stage1-display-context-v1",
        "screen_contract_id": "screen-contract-fixture",
        "screen_contract_sha256": _digest("screen-contract"),
        "display_policy_id": "display-policy-fixture",
        "display_policy_sha256": _digest("display-policy"),
        "display_policy_artifact_sha256": _digest("display-policy-artifact"),
        "ui_bundle_sha256": manifest.ui_bundle_sha256,
        "content_security_policy_sha256": manifest.content_security_policy_sha256,
        "display_attester_id": "display-attester-fixture",
        "review_schema_id": "review-schema-fixture",
        "review_schema_sha256": _digest("review-schema"),
        "rubric_version": "c4-visual-remediation-human-review-v1",
        "operator_policy_id": "operator-policy-fixture",
        "operator_policy_sha256": _digest("operator-policy"),
        "packet_id": "blind-packet-fixture",
        "packet_sha256": _digest("blind-packet"),
        "presentation_manifest_id": "presentation-fixture",
        "presentation_manifest_sha256": _digest("presentation"),
        "material_commitment_id": "material-fixture",
        "material_commitment_sha256": _digest("material"),
        "source_image_sha256": _sha256(source),
        "outputs": tuple(reference for reference, _ in references),
        "pair_order_policy": "ascending_sha256_of_blind_code",
        "ui_implementation_id": C4_STAGE1_REVIEW_PRESENTER_IMPLEMENTATION_ID,
        "ui_revision": C4_STAGE1_REVIEW_PRESENTER_REVISION,
        "ui_session_id": "fresh-review-session-fixture",
        "renderer_identity_structured_field_present": False,
        "model_identity_structured_field_present": False,
        "provider_or_model_labels_passed_to_display_port": False,
        "other_provider_output_references_present": False,
        "external_text_identifiers_trusted_caller_boundary": True,
        "absence_of_covert_secret_encoding_proven": False,
    }
    context = C4Stage1DisplayContext(
        context_id=content_id("c4_stage1_display_context", base),
        context_sha256=_sha256(canonical_json_bytes(base)),
        **base,
    )
    return context, source, outputs


def _submission(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
        "sessionToken": packet["sessionToken"],
        "reviewerPseudonym": "reviewer-one",
        "slotJudgments": [
            {
                "slot": output["slot"],
                "judgments": {
                    field: (field_index + output_index) % 2 == 0
                    for field_index, field in enumerate(OUTPUT_FIELDS)
                },
            }
            for output_index, output in enumerate(packet["candidateSlots"])
        ],
        "pairJudgments": {
            "actions_visibly_distinct": True,
            "same_source_bytes_confirmed": False,
        },
    }


class _FakeRoute:
    def __init__(self, url: str) -> None:
        self.request = SimpleNamespace(url=url)
        self.fulfilled: dict[str, Any] | None = None
        self.aborted: str | None = None

    def fulfill(self, **kwargs: Any) -> None:
        self.fulfilled = kwargs

    def abort(self, reason: str) -> None:
        self.aborted = reason


class _FakeLocator:
    def __init__(self, page: _FakePage, selector: str) -> None:
        self._page = page
        self._selector = selector

    def fill(self, value: str) -> None:
        self._page.reviewer = value

    def check(self) -> None:
        self._page.checked.append(self._selector)

    def click(self) -> None:
        assert self._selector == "#submit-review"
        assert self._page.packet is not None
        submission = _submission(self._page.packet)
        submission["reviewerPseudonym"] = self._page.reviewer
        for item in submission["slotJudgments"]:
            item["judgments"] = dict.fromkeys(OUTPUT_FIELDS, False)
        submission["pairJudgments"] = dict.fromkeys(PAIR_FIELDS, False)
        self._page._context.binding("SubmitReview")(self._page._source(), submission)
        self._page.submitted = True


class _FakePage:
    def __init__(self, browser_context: _FakeBrowserContext) -> None:
        self._context = browser_context
        self.url = "about:blank"
        self.frame = SimpleNamespace(url="about:blank")
        self.packet: dict[str, Any] | None = None
        self.wait_count = 0
        self.reviewer = ""
        self.checked: list[str] = []
        self.submitted = False

    def _source(self) -> dict[str, Any]:
        return {"page": self, "frame": self.frame}

    def goto(self, url: str, **kwargs: Any) -> None:
        self._context.goto = {"url": url, **kwargs}
        self._context.advance_clock()
        self.url = url
        self.frame.url = url
        for asset_url in (
            INDEX_URL,
            "https://rei-c4-stage1.invalid/review.css",
            "https://rei-c4-stage1.invalid/review.js",
        ):
            self._context.issue_request(asset_url)
        if self._context.scenario == "network" and self._context.mode == "display":
            self._context.issue_request("https://example.invalid/escape")
        self.packet = self._context.binding("GetReviewPacket")(
            self._source(),
            {
                "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
                "serviceSchemaRevision": C4_STAGE1_REVIEW_SERVICE_SCHEMA_REVISION,
                "ledgerSchemaRevision": C4_STAGE1_REVIEW_LEDGER_SCHEMA_REVISION,
            },
        )
        self._context.binding("MarkReviewReady")(
            self._source(),
            {
                "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
                "sessionToken": self.packet["sessionToken"],
            },
        )

    def wait_for_function(self, expression: str, **kwargs: Any) -> None:
        self.wait_count += 1
        self._context.advance_clock()
        self._context.waits.append({"expression": expression, **kwargs})
        self._context.hang_if_requested("action")
        if self._context.mode == "probe" or self.wait_count == 1:
            return
        if self._context.scenario == "close":
            raise RuntimeError("page closed")
        if self._context.scenario == "premature-terminal":
            return
        if self._context.scenario == "block":
            self._context.terminal_wait_entered.set()
            if self._context.closed_event.wait(
                timeout=min(0.05, kwargs.get("timeout", 250) / 1_000)
            ):
                raise RuntimeError("page closed by cancellation")
            raise TimeoutError("bounded poll timeout")
        assert self.packet is not None
        if self._context.scenario == "cancel":
            self._context.binding("CancelReview")(
                self._source(),
                {
                    "ipcProtocol": C4_STAGE1_REVIEW_IPC_PROTOCOL,
                    "sessionToken": self.packet["sessionToken"],
                },
            )
            return
        submission = _submission(self.packet)
        if self._context.scenario == "missing-field":
            del submission["slotJudgments"][0]["judgments"][OUTPUT_FIELDS[0]]
        if self._context.scenario == "unknown-slot":
            submission["slotJudgments"][1]["slot"] = "slot-" + ("0" * 64)
        self._context.binding("SubmitReview")(self._source(), submission)

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self, selector)


class _FakeBrowserContext:
    def __init__(
        self,
        scenario: str,
        *,
        mode: str,
        clock_step: Any | None = None,
        owner: _FakePlaywrightFactory,
    ) -> None:
        self.scenario = scenario
        self.mode = mode
        self._clock_step = clock_step
        self._owner = owner
        self.pages = [_FakePage(self)]
        self._bindings: dict[str, Any] = {}
        self._route = None
        self.routes: list[_FakeRoute] = []
        self.waits: list[dict[str, Any]] = []
        self.goto: dict[str, Any] | None = None
        self.init_scripts: list[str] = []
        self.timeout: int | None = None
        self.offline_values: list[bool] = []
        self.closed = False
        self.closed_event = threading.Event()
        self.terminal_wait_entered = threading.Event()

    def advance_clock(self) -> None:
        if self._clock_step is not None:
            self._clock_step()

    def hang_if_requested(self, stage: str) -> None:
        self._owner.hang_if_requested(stage)

    def set_default_timeout(self, value: int) -> None:
        self.timeout = value

    def set_offline(self, value: bool) -> None:
        self.offline_values.append(value)

    def route(self, pattern: str, callback: Any) -> None:
        assert pattern == "**/*"
        self._route = callback

    def issue_request(self, url: str) -> _FakeRoute:
        assert self._route is not None
        route = _FakeRoute(url)
        self.routes.append(route)
        self._route(route)
        return route

    def expose_binding(self, name: str, callback: Any) -> None:
        self._bindings[name] = callback

    def binding(self, fragment: str):
        matches = [value for name, value in self._bindings.items() if fragment in name]
        assert len(matches) == 1
        return matches[0]

    def add_init_script(self, script: str) -> None:
        self.init_scripts.append(script)

    def new_page(self):
        page = _FakePage(self)
        self.pages.append(page)
        return page

    def close(self) -> None:
        self.hang_if_requested("close")
        if self._owner.close_failure:
            raise RuntimeError("fake close failure")
        self.closed = True
        self.closed_event.set()
        if self.mode == "display" and self._owner.on_display_close is not None:
            self._owner.on_display_close()


class _FakeChromium:
    def __init__(self, owner: _FakePlaywrightFactory) -> None:
        self._owner = owner
        self.launches: list[dict[str, Any]] = []
        self.executable_path = ""

    def launch_persistent_context(self, user_data_dir: str, **kwargs: Any):
        assert Path(user_data_dir).is_dir()
        self._owner.hang_if_requested("launch")
        if self._owner.broken_launch:
            raise RuntimeError("browser launch failed")
        mode = "probe" if not self.launches else "display"
        self.launches.append({"user_data_dir": user_data_dir, **kwargs})
        context = _FakeBrowserContext(
            self._owner.scenario,
            mode=mode,
            clock_step=self._owner.clock_step,
            owner=self._owner,
        )
        self._owner.contexts.append(context)
        self._owner.browser_context = context
        return context


class _FakePlaywrightManager:
    def __init__(self, owner: _FakePlaywrightFactory) -> None:
        self._owner = owner
        chromium = owner.chromium
        self._playwright = SimpleNamespace(chromium=chromium)

    def __enter__(self):
        return self._playwright

    def __exit__(self, *_args: object) -> None:
        self._owner.hang_if_requested("disconnect")
        return None


class _FakePlaywrightFactory:
    def __init__(
        self,
        scenario: str = "submit",
        *,
        clock_step: Any | None = None,
        broken_launch: bool = False,
        hang_stage: str | None = None,
        on_hang: Any | None = None,
        on_display_close: Any | None = None,
        close_failure: bool = False,
    ) -> None:
        self.scenario = scenario
        self.clock_step = clock_step
        self.broken_launch = broken_launch
        self.hang_stage = hang_stage
        self.on_hang = on_hang
        self.on_display_close = on_display_close
        self.close_failure = close_failure
        self.containment: _FakeContainment | None = None
        self.contexts: list[_FakeBrowserContext] = []
        self.browser_context: _FakeBrowserContext | None = None
        self.chromium = _FakeChromium(self)

    def __call__(self):
        return _FakePlaywrightManager(self)

    def hang_if_requested(self, stage: str) -> None:
        if self.hang_stage != stage:
            return
        if self.on_hang is not None:
            self.on_hang()
        if self.containment is None or not self.containment.terminated.wait(timeout=2):
            raise RuntimeError(f"fake {stage} hang was not terminated")
        raise RuntimeError(f"fake {stage} terminated")


class _FakeRuntimeVerifier:
    def __init__(self) -> None:
        self.epoch = 0
        self.calls: list[tuple[Path, Path, Path]] = []

    def mutate(self) -> None:
        self.epoch += 1

    def __call__(
        self,
        provenance_root: Path,
        runtime_root: Path,
        browser_root: Path,
        *,
        checkpoint: Any,
    ) -> dict[str, object]:
        checkpoint()
        roots = tuple(
            path.resolve(strict=True)
            for path in (provenance_root, runtime_root, browser_root)
        )
        self.calls.append(roots)
        chromium = browser_root / "chromium-1228/chrome-win64/chrome.exe"
        chromium_bytes = chromium.read_bytes()

        def tree(role: str, root: Path, *, files: int) -> dict[str, object]:
            identity = f"{role}:{root.resolve()}:{self.epoch}"
            return {
                "manifest_id": f"manifest-{_digest(identity)[:32]}",
                "canonical_sha256": _digest(identity + ":manifest"),
                "canonical_size_bytes": 100 + self.epoch,
                "tree_content_id": f"tree-{_digest(identity + ':tree')[:32]}",
                "tree_content_sha256": _digest(identity + ":tree"),
                "file_count": files,
                "directory_count": 4,
                "executable_count": 1,
                "total_size_bytes": 1_000 + self.epoch,
                "regular_files_only": True,
                "links_reparse_points_and_hardlinks_allowed": False,
                "python_bytecode_and_cache_directories_allowed": False,
            }

        body = {
            "schema_version": "rei-c4-stage1-review-runtime-verification-v1",
            "provenance": {
                "provenance_id": f"provenance-{_digest(str(roots[0]) + str(self.epoch))[:32]}",
                "canonical_sha256": _digest(f"provenance:{roots[0]}:{self.epoch}"),
                "canonical_size_bytes": 211 + self.epoch,
                "create_only_inventory_verified": True,
            },
            "runtime_manifest": tree("runtime", roots[1], files=10),
            "browser_manifest": tree("browser", roots[2], files=8),
            "runtime_base_python": {
                "relative_path": "base-python/python.exe",
                "sha256": _digest("base-python"),
                "size_bytes": 31,
            },
            "runtime_python": {
                "relative_path": "venv/Scripts/python.exe",
                "sha256": _digest("runtime-python"),
                "size_bytes": 32,
            },
            "venv_configuration": {
                "relative_path": "venv/pyvenv.cfg",
                "sha256": _digest("pyvenv-config"),
                "size_bytes": 34,
            },
            "installed_browsers_json": {
                "relative_path": "venv/Lib/site-packages/playwright/driver/package/browsers.json",
                "sha256": _digest("browsers-json"),
                "size_bytes": 33,
            },
            "installed_distributions": [
                {
                    "name": "playwright",
                    "version": "1.61.0",
                    "record_sha256": _digest("playwright-record"),
                }
            ],
            "chromium_executable": {
                "relative_path": "chromium-1228/chrome-win64/chrome.exe",
                "sha256": _sha256(chromium_bytes),
                "size_bytes": len(chromium_bytes),
            },
            "checkpoint_applied_during_all_file_and_tree_hashing": True,
            "paths_stored": False,
            "browser_process_launch_performed": False,
            "headed_full_ui_smoke_performed": False,
            "model_calls": 0,
        }
        checkpoint()
        return {
            "verification_id": content_id("c4_review_runtime_verification", body),
            **body,
        }


class _HangingRuntimeVerifier(_FakeRuntimeVerifier):
    def __init__(
        self,
        containment: _FakeContainment,
        on_hang: Any,
    ) -> None:
        super().__init__()
        self._containment = containment
        self._on_hang = on_hang

    def __call__(self, *args: object, checkpoint: Any, **kwargs: object):
        checkpoint()
        self._on_hang()
        if not self._containment.terminated.wait(timeout=2):
            raise RuntimeError("fake runtime verification hang was not terminated")
        raise RuntimeError("fake runtime verification terminated")


class _ManualDeadlineClock:
    def __init__(self) -> None:
        self._value = 0
        self._lock = threading.Lock()

    def __call__(self) -> int:
        with self._lock:
            return self._value

    def expire(self) -> None:
        with self._lock:
            self._value = 2_000_000_000


class _FakeContainment:
    def __init__(self) -> None:
        self.reasons: list[str] = []
        self.terminated = threading.Event()

    def terminate(self, reason: str) -> None:
        self.reasons.append(reason)
        self.terminated.set()


def _fake_runtime_arguments(
    tmp_path: Path,
    factory: _FakePlaywrightFactory,
    *,
    verifier: _FakeRuntimeVerifier | None = None,
) -> dict[str, object]:
    provenance_root = tmp_path / "sealed-provenance"
    runtime_root = tmp_path / "sealed-runtime"
    browser_root = tmp_path / "sealed-browser"
    provenance_root.mkdir(exist_ok=True)
    (runtime_root / "venv/Scripts").mkdir(parents=True, exist_ok=True)
    (runtime_root / "venv/Scripts/python.exe").write_bytes(b"sealed python")
    executable = browser_root / "chromium-1228/chrome-win64/chrome.exe"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"fake pinned browser executable")
    factory.chromium.executable_path = str(executable.resolve())
    return {
        "runtime_provenance_root": provenance_root.resolve(),
        "external_runtime_root": runtime_root.resolve(),
        "external_browser_root": browser_root.resolve(),
        "runtime_verifier": verifier or _FakeRuntimeVerifier(),
    }


def _presenter(
    tmp_path: Path,
    factory: _FakePlaywrightFactory,
    *,
    verify: bool = True,
    monotonic_ns: Any | None = None,
    containment: _FakeContainment | None = None,
    runtime_verifier: _FakeRuntimeVerifier | None = None,
    cancellation_grace_ms: int = 2_000,
):
    runtime_arguments = _fake_runtime_arguments(
        tmp_path, factory, verifier=runtime_verifier
    )
    manifest = capture_c4_stage1_review_runtime_manifest(ROOT.resolve())
    containment = containment or _FakeContainment()
    factory.containment = containment
    presenter = C4Stage1OfflineReviewPresenter(
        repository_root=ROOT.resolve(),
        runtime_manifest=manifest,
        user_data_dir=(tmp_path / "external-session").resolve(),
        timeout_ms=1_000,
        playwright_factory=factory,
        runtime_identity_resolver=lambda: (
            C4_STAGE1_PLAYWRIGHT_PYTHON_VERSION,
            C4_STAGE1_PLAYWRIGHT_CHROMIUM_REVISION,
            C4_STAGE1_PLAYWRIGHT_CHROMIUM_VERSION,
        ),
        process_tree_containment=containment,
        cancellation_grace_ms=cancellation_grace_ms,
        **runtime_arguments,
        **({"monotonic_ns": monotonic_ns} if monotonic_ns is not None else {}),
    )
    if verify:
        presenter.verify_operational()
    return manifest, presenter


def test_presenter_operational_probe_hashes_installed_browser(tmp_path: Path) -> None:
    factory = _FakePlaywrightFactory()
    _, presenter = _presenter(tmp_path, factory)

    assert presenter.browser_runtime_pin.playwright_python_version == "1.61.0"
    assert (
        presenter.browser_executable_path
        == Path(factory.chromium.executable_path).resolve()
    )
    assert presenter.browser_user_data_parent == tmp_path.resolve()
    assert (
        presenter.runtime_provenance_root == (tmp_path / "sealed-provenance").resolve()
    )
    assert presenter.external_runtime_root == (tmp_path / "sealed-runtime").resolve()
    assert presenter.external_browser_root == (tmp_path / "sealed-browser").resolve()
    external = presenter.browser_runtime_pin.external_runtime
    assert external.create_only_inventory_verified is True
    assert external.runtime_manifest.regular_files_only is True
    assert external.runtime_manifest.links_reparse_points_and_hardlinks_allowed is False
    assert (
        external.runtime_manifest.python_bytecode_and_cache_directories_allowed is False
    )
    assert external.browser_manifest.tree_content_sha256
    assert external.verification_sha256
    assert len(factory.contexts) == 1
    probe = factory.contexts[0]
    assert probe.mode == "probe"
    assert probe.pages[0].submitted is True
    assert len(probe.pages[0].checked) == 16
    assert "addEventListener('load'" in probe.init_scripts[0]
    assert not (tmp_path / "external-session").exists()


@pytest.mark.parametrize(
    ("attribute", "argument"),
    [
        ("_runtime_provenance_root", "runtime_provenance_root"),
        ("_external_runtime_root", "external_runtime_root"),
        ("_external_browser_root", "external_browser_root"),
    ],
)
def test_sealed_runtime_root_substitution_is_rejected(
    tmp_path: Path,
    attribute: str,
    argument: str,
) -> None:
    verifier = _FakeRuntimeVerifier()
    factory = _FakePlaywrightFactory()
    _, presenter = _presenter(tmp_path, factory, runtime_verifier=verifier)
    stored_pin = presenter.browser_runtime_pin
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    replacement_factory = _FakePlaywrightFactory()
    replacement_arguments = _fake_runtime_arguments(
        replacement, replacement_factory, verifier=verifier
    )
    setattr(presenter, attribute, replacement_arguments[argument])

    with pytest.raises(C4Stage1ReviewPresenterError, match="runtime changed"):
        presenter.verify_runtime_pin(stored_pin)


def test_post_session_runtime_tree_mutation_fails_before_submission_sealing(
    tmp_path: Path,
) -> None:
    verifier = _FakeRuntimeVerifier()
    factory = _FakePlaywrightFactory(on_display_close=verifier.mutate)
    manifest, presenter = _presenter(tmp_path, factory, runtime_verifier=verifier)
    context, source, outputs = _material(manifest)

    with pytest.raises(C4Stage1ReviewPresenterError, match="runtime changed"):
        presenter(context, source, outputs)
    with pytest.raises(C4Stage1ReviewPresenterError, match="No unretrieved"):
        presenter.take_submission(context.context_id)


@pytest.mark.parametrize("hang_stage", ["launch", "action", "close", "disconnect"])
def test_absolute_deadline_terminates_hanging_browser_stage_once(
    tmp_path: Path,
    hang_stage: str,
) -> None:
    clock = _ManualDeadlineClock()
    containment = _FakeContainment()
    factory = _FakePlaywrightFactory(
        hang_stage=hang_stage,
        on_hang=clock.expire,
    )
    _, presenter = _presenter(
        tmp_path,
        factory,
        verify=False,
        monotonic_ns=clock,
        containment=containment,
    )

    with pytest.raises(C4Stage1ReviewPresenterError, match="absolute.*deadline"):
        presenter.verify_operational()
    assert containment.reasons == ["absolute-deadline"]


def test_absolute_deadline_terminates_hanging_runtime_verification_once(
    tmp_path: Path,
) -> None:
    clock = _ManualDeadlineClock()
    containment = _FakeContainment()
    verifier = _HangingRuntimeVerifier(containment, clock.expire)
    factory = _FakePlaywrightFactory()
    _, presenter = _presenter(
        tmp_path,
        factory,
        verify=False,
        monotonic_ns=clock,
        containment=containment,
        runtime_verifier=verifier,
    )

    with pytest.raises(C4Stage1ReviewPresenterError, match="absolute.*deadline"):
        presenter.verify_operational()
    assert containment.reasons == ["absolute-deadline"]


def test_close_failure_terminates_job_once(tmp_path: Path) -> None:
    containment = _FakeContainment()
    factory = _FakePlaywrightFactory(close_failure=True)
    _, presenter = _presenter(
        tmp_path,
        factory,
        verify=False,
        containment=containment,
    )

    with pytest.raises(C4Stage1ReviewPresenterError, match="not operational"):
        presenter.verify_operational()
    assert len(containment.reasons) == 1
    assert "close-failed" in containment.reasons[0]


def test_cancel_grace_terminates_hanging_action_once(tmp_path: Path) -> None:
    containment = _FakeContainment()
    factory = _FakePlaywrightFactory()
    manifest, presenter = _presenter(
        tmp_path,
        factory,
        containment=containment,
        cancellation_grace_ms=10,
    )
    context, source, outputs = _material(manifest)
    entered = threading.Event()
    factory.hang_stage = "action"
    factory.on_hang = entered.set
    failures: list[BaseException] = []

    def run() -> None:
        try:
            presenter(context, source, outputs)
        except BaseException as exc:  # noqa: BLE001 - thread handoff for assertion
            failures.append(exc)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    assert entered.wait(timeout=1)
    assert presenter.cancel_active() is True
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert failures and isinstance(failures[0], C4Stage1ReviewPresenterError)
    assert containment.reasons == ["cancel-grace-expired"]


def test_request_cancellation_during_input_validation_never_launches_browser(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _FakePlaywrightFactory()
    manifest, presenter = _presenter(tmp_path, factory)
    context, source, outputs = _material(manifest)
    validation_started = threading.Event()
    request_cancelled = threading.Event()
    original_validate_inputs = presenter._validate_inputs
    failures: list[BaseException] = []

    def blocked_validate_inputs(*args: object):
        validation_started.set()
        assert request_cancelled.wait(timeout=1)
        return original_validate_inputs(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(presenter, "_validate_inputs", blocked_validate_inputs)

    def run() -> None:
        try:
            presenter.present(
                context,
                source,
                outputs,
                cancellation_event=request_cancelled,
            )
        except BaseException as exc:  # noqa: BLE001 - thread handoff for assertion
            failures.append(exc)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    assert validation_started.wait(timeout=1)
    assert presenter.cancel_active() is False
    request_cancelled.set()
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert failures and isinstance(failures[0], C4Stage1ReviewPresenterError)
    assert "cancelled during display input validation completion" in str(failures[0])
    assert len(factory.contexts) == 1


def test_presenter_operational_probe_rejects_stale_user_data_dir(
    tmp_path: Path,
) -> None:
    factory = _FakePlaywrightFactory()
    _, presenter = _presenter(tmp_path, factory, verify=False)
    (tmp_path / "external-session").mkdir()

    with pytest.raises(C4Stage1ReviewPresenterError, match="not operational"):
        presenter.verify_operational()


def test_browser_profile_cannot_overlap_a_sealed_runtime_root(
    tmp_path: Path,
) -> None:
    factory = _FakePlaywrightFactory()
    runtime_arguments = _fake_runtime_arguments(tmp_path, factory)
    manifest = capture_c4_stage1_review_runtime_manifest(ROOT.resolve())
    presenter = C4Stage1OfflineReviewPresenter(
        repository_root=ROOT.resolve(),
        runtime_manifest=manifest,
        user_data_dir=(tmp_path / "sealed-runtime/browser-session").resolve(),
        timeout_ms=1_000,
        playwright_factory=factory,
        runtime_identity_resolver=lambda: (
            C4_STAGE1_PLAYWRIGHT_PYTHON_VERSION,
            C4_STAGE1_PLAYWRIGHT_CHROMIUM_REVISION,
            C4_STAGE1_PLAYWRIGHT_CHROMIUM_VERSION,
        ),
        process_tree_containment=_FakeContainment(),
        **runtime_arguments,
    )

    with pytest.raises(C4Stage1ReviewPresenterError, match="not operational"):
        presenter.verify_operational()
    assert factory.chromium.launches == []


def test_headed_offline_presenter_binds_exact_bytes_and_one_time_submission(
    tmp_path: Path,
) -> None:
    factory = _FakePlaywrightFactory()
    manifest, presenter = _presenter(tmp_path, factory)
    context, source, outputs = _material(manifest)

    assert presenter(context, source, outputs) is True
    submission, submitted_at = presenter.peek_submission(context.context_id)
    assert presenter.peek_submission(context.context_id) == (
        submission,
        submitted_at,
    )
    with pytest.raises(C4Stage1ReviewPresenterError, match="changed before discard"):
        presenter.discard_submission(
            context.context_id,
            expected_submission=submission + b" ",
            expected_submitted_at=submitted_at,
        )
    assert presenter.peek_submission(context.context_id) == (
        submission,
        submitted_at,
    )
    assert presenter.discard_submission(
        context.context_id,
        expected_submission=submission,
        expected_submitted_at=submitted_at,
    )
    assert (
        presenter.discard_submission(
            context.context_id,
            expected_submission=submission,
            expected_submitted_at=submitted_at,
        )
        is False
    )
    decoded = json.loads(submission)

    assert canonical_json_bytes(decoded) == submission
    assert submitted_at.tzinfo is not None
    assert decoded["packetId"] == context.packet_id
    assert (
        sum(
            type(value) is bool
            for output in decoded["outputs"]
            for value in output["judgments"].values()
        )
        + sum(type(value) is bool for value in decoded["pairJudgments"].values())
        == 16
    )
    displayed_index = {
        item["instruction"]: index
        for index, item in enumerate(
            factory.browser_context.pages[0].packet["candidateSlots"]
        )
    }
    for context_index, output in enumerate(outputs):
        judgments = decoded["outputs"][context_index]["judgments"]
        assert judgments == {
            field: (field_index + displayed_index[output.instruction]) % 2 == 0
            for field_index, field in enumerate(OUTPUT_FIELDS)
        }
    with pytest.raises(C4Stage1ReviewPresenterError, match="No unretrieved"):
        presenter.take_submission(context.context_id)

    assert len(factory.chromium.launches) == 2
    launch = factory.chromium.launches[-1]
    assert launch["user_data_dir"] == str((tmp_path / "external-session").resolve())
    assert launch["headless"] is False
    assert launch["offline"] is True
    assert launch["accept_downloads"] is False
    assert launch["service_workers"] == "block"
    assert launch["args"] == [
        "--disable-application-cache",
        "--disable-background-networking",
        "--disk-cache-size=1",
        "--media-cache-size=1",
    ]
    browser = factory.browser_context
    assert browser is not None
    assert browser.offline_values == [True]
    assert browser.closed is True
    assert not (tmp_path / "external-session").exists()
    assert len(browser.init_scripts) == 1
    assert "window.reiReviewHost" not in browser.init_scripts[0]
    assert "'reiReviewHost'" in browser.init_scripts[0]

    packet = browser.pages[0].packet
    assert packet is not None
    assert set(packet) == {
        "ipcProtocol",
        "serviceSchemaRevision",
        "ledgerSchemaRevision",
        "sessionToken",
        "referenceSlot",
        "candidateSlots",
    }
    visible_source = bytes(packet["referenceSlot"]["pngBytes"])
    assert visible_source != source
    assert source not in visible_source
    assert _sha256(visible_source) != context.source_image_sha256
    assert _png_pixel_identity(visible_source) == _png_pixel_identity(source)
    visible_by_instruction = {
        item["instruction"]: bytes(item["pngBytes"])
        for item in packet["candidateSlots"]
    }
    for output in outputs:
        visible = visible_by_instruction[output.instruction]
        assert visible != output.png_bytes
        assert output.png_bytes not in visible
        assert _sha256(visible) != output.output_sha256
        assert _png_pixel_identity(visible) == _png_pixel_identity(output.png_bytes)
    serialized = json.dumps(packet, sort_keys=True)
    forbidden = {
        context.packet_id,
        context.packet_sha256,
        context.material_commitment_id,
        context.material_commitment_sha256,
        context.source_image_sha256,
        *(item.blind_code for item in outputs),
        *(item.blind_order_sha256 for item in outputs),
        *(item.instruction_sha256 for item in outputs),
        *(item.output_sha256 for item in outputs),
    }
    assert all(value not in serialized for value in forbidden)
    assert b"original-metadata" not in visible_source
    assert all(
        b"original-metadata" not in bytes(item["pngBytes"])
        for item in packet["candidateSlots"]
    )
    assert "packetId" not in browser.init_scripts[0]
    assert "packetSha256" not in browser.init_scripts[0]
    html = (ROOT / UI_RELATIVE / "index.html").read_text(encoding="utf-8")
    assert '<span id="source-digest" hidden aria-hidden="true"></span>' in html
    assert '<span id="output-digest-0" hidden aria-hidden="true"></span>' in html
    assert '<span id="output-digest-1" hidden aria-hidden="true"></span>' in html

    fulfilled = {route.request.url: route for route in browser.routes}
    for asset in manifest.assets:
        route = fulfilled[
            f"https://rei-c4-stage1.invalid/{Path(asset.relative_path).name}"
        ]
        assert route.aborted is None
        assert route.fulfilled is not None
        assert route.fulfilled["body"] == (ROOT / asset.relative_path).read_bytes()


def test_cancel_returns_false_and_stores_no_submission(tmp_path: Path) -> None:
    factory = _FakePlaywrightFactory("cancel")
    manifest, presenter = _presenter(tmp_path, factory)
    context, source, outputs = _material(manifest)

    assert presenter(context, source, outputs) is False
    with pytest.raises(C4Stage1ReviewPresenterError, match="No unretrieved"):
        presenter.take_submission(context.context_id)


def test_present_service_port_delegates_to_callable_presenter(tmp_path: Path) -> None:
    factory = _FakePlaywrightFactory()
    manifest, presenter = _presenter(tmp_path, factory)
    context, source, outputs = _material(manifest)

    assert presenter.present(context, source, outputs) is True
    submission, _ = presenter.take_submission(context.context_id)
    assert json.loads(submission)["packetId"] == context.packet_id


@pytest.mark.parametrize("scenario", ["missing-field", "unknown-slot"])
def test_incomplete_or_tampered_submission_fails_closed(
    tmp_path: Path, scenario: str
) -> None:
    factory = _FakePlaywrightFactory(scenario)
    manifest, presenter = _presenter(tmp_path, factory)
    context, source, outputs = _material(manifest)

    with pytest.raises(C4Stage1ReviewPresenterError):
        presenter(context, source, outputs)
    with pytest.raises(C4Stage1ReviewPresenterError, match="No unretrieved"):
        presenter.take_submission(context.context_id)
    assert not (tmp_path / "external-session").exists()


def test_unpinned_network_request_is_aborted_and_fails_closed(tmp_path: Path) -> None:
    factory = _FakePlaywrightFactory("network")
    manifest, presenter = _presenter(tmp_path, factory)
    context, source, outputs = _material(manifest)

    with pytest.raises(C4Stage1ReviewPresenterError, match="non-pinned resource"):
        presenter(context, source, outputs)
    assert factory.browser_context is not None
    escaped = factory.browser_context.routes[-1]
    assert escaped.request.url == "https://example.invalid/escape"
    assert escaped.aborted == "blockedbyclient"
    assert escaped.fulfilled is None


def test_runtime_or_display_byte_tamper_fails_before_browser_launch(
    tmp_path: Path,
) -> None:
    repository = (tmp_path / "repository").resolve()
    target = repository / UI_RELATIVE
    target.parent.mkdir(parents=True)
    shutil.copytree(ROOT / UI_RELATIVE, target)
    manifest = capture_c4_stage1_review_runtime_manifest(repository)
    factory = _FakePlaywrightFactory()
    presenter = C4Stage1OfflineReviewPresenter(
        repository_root=repository,
        runtime_manifest=manifest,
        user_data_dir=(tmp_path / "session-one").resolve(),
        timeout_ms=1_000,
        playwright_factory=factory,
        process_tree_containment=_FakeContainment(),
        **_fake_runtime_arguments(tmp_path, factory),
    )
    context, source, outputs = _material(manifest)
    (target / "review.css").write_bytes((target / "review.css").read_bytes() + b"\n")

    with pytest.raises(C4Stage1ReviewPresenterError):
        presenter(context, source, outputs)
    assert factory.chromium.launches == []

    clean_factory = _FakePlaywrightFactory()
    clean_manifest = capture_c4_stage1_review_runtime_manifest(ROOT.resolve())
    clean_presenter = C4Stage1OfflineReviewPresenter(
        repository_root=ROOT.resolve(),
        runtime_manifest=clean_manifest,
        user_data_dir=(tmp_path / "session-two").resolve(),
        timeout_ms=1_000,
        playwright_factory=clean_factory,
        process_tree_containment=_FakeContainment(),
        **_fake_runtime_arguments(tmp_path, clean_factory),
    )
    clean_context, clean_source, clean_outputs = _material(clean_manifest)
    tampered_outputs = (
        clean_outputs[0],
        C4Stage1VisibleOutput(
            blind_code=clean_outputs[1].blind_code,
            blind_order_sha256=clean_outputs[1].blind_order_sha256,
            instruction=clean_outputs[1].instruction,
            instruction_sha256=clean_outputs[1].instruction_sha256,
            output_sha256=clean_outputs[1].output_sha256,
            png_bytes=clean_outputs[1].png_bytes + b"tampered",
        ),
    )
    with pytest.raises(C4Stage1ReviewPresenterError, match="display context"):
        clean_presenter(clean_context, clean_source, tampered_outputs)
    assert clean_factory.chromium.launches == []


def test_closed_page_fails_without_leaving_submission_or_session(
    tmp_path: Path,
) -> None:
    factory = _FakePlaywrightFactory("close")
    manifest, presenter = _presenter(tmp_path, factory)
    context, source, outputs = _material(manifest)

    with pytest.raises(C4Stage1ReviewPresenterError, match="closed or timed out"):
        presenter(context, source, outputs)
    assert not (tmp_path / "external-session").exists()
    with pytest.raises(C4Stage1ReviewPresenterError, match="No unretrieved"):
        presenter.take_submission(context.context_id)


def test_browser_runtime_drift_and_broken_launch_fail_closed(tmp_path: Path) -> None:
    drift_factory = _FakePlaywrightFactory()
    manifest, presenter = _presenter(tmp_path, drift_factory)
    context, source, outputs = _material(manifest)
    Path(drift_factory.chromium.executable_path).write_bytes(b"changed executable")

    with pytest.raises(C4Stage1ReviewPresenterError, match="runtime changed"):
        presenter(context, source, outputs)
    assert len(drift_factory.chromium.launches) == 1

    broken_root = tmp_path / "broken"
    broken_root.mkdir()
    broken_factory = _FakePlaywrightFactory(broken_launch=True)
    _, broken = _presenter(broken_root, broken_factory, verify=False)
    with pytest.raises(C4Stage1ReviewPresenterError, match="not operational"):
        broken.verify_operational()
    assert not (broken_root / "external-session").exists()


def test_one_absolute_deadline_covers_navigation_readiness_and_terminal(
    tmp_path: Path,
) -> None:
    now = 0

    def clock() -> int:
        return now

    def advance() -> None:
        nonlocal now
        now += 400_000_000

    factory = _FakePlaywrightFactory()
    manifest, presenter = _presenter(tmp_path, factory, monotonic_ns=clock)
    factory.clock_step = advance
    context, source, outputs = _material(manifest)

    with pytest.raises(C4Stage1ReviewPresenterError, match="absolute.*deadline"):
        presenter(context, source, outputs)
    assert not (tmp_path / "external-session").exists()


def test_unconfirmed_js_terminal_cannot_race_delayed_submit_binding(
    tmp_path: Path,
) -> None:
    factory = _FakePlaywrightFactory("premature-terminal")
    manifest, presenter = _presenter(tmp_path, factory)
    context, source, outputs = _material(manifest)

    with pytest.raises(C4Stage1ReviewPresenterError, match="confirmed host binding"):
        presenter(context, source, outputs)
    script = factory.contexts[-1].init_scripts[0]
    submit_block = script.split("async submitReview", 1)[1].split(
        "async cancelReview", 1
    )[0]
    assert submit_block.index("await globalThis.__reiC4Stage1SubmitReviewV1") < (
        submit_block.index("state.terminal = true")
    )


def test_cancel_active_closes_the_live_browser_context(tmp_path: Path) -> None:
    factory = _FakePlaywrightFactory("block")
    manifest, presenter = _presenter(tmp_path, factory)
    context, source, outputs = _material(manifest)
    failures: list[BaseException] = []

    def run() -> None:
        try:
            presenter(context, source, outputs)
        except BaseException as exc:  # noqa: BLE001 - thread handoff for assertion
            failures.append(exc)

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    while len(factory.contexts) < 2:
        worker.join(timeout=0.01)
    live = factory.contexts[-1]
    assert live.terminal_wait_entered.wait(timeout=1)
    assert presenter.cancel_active() is True
    worker.join(timeout=2)

    assert not worker.is_alive()
    assert live.closed is True
    assert failures and isinstance(failures[0], C4Stage1ReviewPresenterError)
    with pytest.raises(C4Stage1ReviewPresenterError, match="No unretrieved"):
        presenter.take_submission(context.context_id)


def test_blinded_payload_is_fresh_across_sessions_and_never_persisted(
    tmp_path: Path,
) -> None:
    packets: list[dict[str, Any]] = []
    for name in ("one", "two"):
        root = tmp_path / name
        root.mkdir()
        factory = _FakePlaywrightFactory()
        manifest, presenter = _presenter(root, factory)
        context, source, outputs = _material(manifest)
        assert presenter(context, source, outputs) is True
        assert factory.browser_context is not None
        packet = factory.browser_context.pages[0].packet
        assert packet is not None
        packets.append(packet)
        presenter.take_submission(context.context_id)
        assert not (root / "external-session").exists()

    assert packets[0]["sessionToken"] != packets[1]["sessionToken"]
    assert packets[0]["referenceSlot"]["slot"] != packets[1]["referenceSlot"]["slot"]
    assert bytes(packets[0]["referenceSlot"]["pngBytes"]) != bytes(
        packets[1]["referenceSlot"]["pngBytes"]
    )
    assert {item["slot"] for item in packets[0]["candidateSlots"]}.isdisjoint(
        {item["slot"] for item in packets[1]["candidateSlots"]}
    )
    first_png = bytes(packets[0]["referenceSlot"]["pngBytes"])
    second_png = bytes(packets[1]["referenceSlot"]["pngBytes"])
    first_idat = _concatenated_idat(first_png)
    second_idat = _concatenated_idat(second_png)
    assert _sha256(first_idat) != _sha256(second_idat)
    assert zlib.decompress(first_idat) != zlib.decompress(second_idat)
    assert _parse_png_pixel_identity(first_png).decoded_pixels == (
        _parse_png_pixel_identity(second_png).decoded_pixels
    )
