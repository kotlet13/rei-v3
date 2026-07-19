"""Run the sealed S1 Gemma 4 text-shadow integration smoke.

The runner performs one provider-free control cycle and one identical native
cycle with the explicitly injected text-shadow adapter.  The latter may issue
at most two ``/api/chat`` requests, strictly E then I.  It never promotes the
model or feeds shadow output into governance, decision, behavior, Ego
composition, or world updates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from rei.communication.epistemic_interpreter_v3 import (  # noqa: E402
    RacioEpistemicInterpretationV3,
    RacioEpistemicPacketV3,
)
from rei.communication.text_shadow import (  # noqa: E402
    ShadowNoAuthorityLedger,
    ShadowProviderAttempt,
    build_racio_epistemic_shadow_packet_v3,
)
from rei.engine import (  # noqa: E402
    ReiNativeCycleRequest,
    ReiNativeCycleResult,
    ReiNativeEngine,
)
from rei.ids import canonical_json_bytes, content_id, sha256_hex  # noqa: E402
from rei.persistence import FileArtifactStore  # noqa: E402
from rei.providers.native import DeterministicExecutionClock, ExecutionClock  # noqa: E402


CYCLE_SOURCE_COMMIT = "1511d871a92dd15217899c5b43e1acdcea4c972b"
IMPLEMENTATION_COMMIT = "6130942c7726240773d7298d6583a77d38a82650"
BRANCH = "codex/racio-gemma4-text-shadow"
BASE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"
)
ORIGINAL_SEAL_PATH = (
    ROOT
    / "Docs"
    / "evals"
    / "research_reset_2026-07"
    / "gemma4_text_shadow_s1_seal.json"
)
SEAL_PATH = (
    ROOT
    / "Docs"
    / "evals"
    / "research_reset_2026-07"
    / "gemma4_text_shadow_s1r_seal.json"
)
ORIGINAL_OUTPUT_ROOT = (
    ROOT
    / "Docs"
    / "evals"
    / "semantic_lab_v1"
    / "s1-gemma4-text-shadow-2026-07-19"
)
DEFAULT_OUTPUT_ROOT = (
    ROOT
    / "Docs"
    / "evals"
    / "semantic_lab_v1"
    / "s1r-gemma4-text-shadow-2026-07-19"
)
EXPECTED_OUTPUT_ROOT = (
    "Docs/evals/semantic_lab_v1/s1r-gemma4-text-shadow-2026-07-19"
)
S1R_COLD_VERIFICATION_RECEIPT = (
    ROOT
    / "Docs"
    / "evals"
    / "research_reset_2026-07"
    / "gemma4_text_shadow_s1r_cold_verification_receipt.json"
)
MODEL = "gemma4:31b"
MODEL_DIGEST = (
    "6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7"
)
PROVIDER_REVISION = "rei-racio-gemma4-epistemic-v3-chat-v1"
EXPECTED_CALLS = 2
SMOKE_MANIFEST_NAME = "smoke_evidence_manifest.json"
COLD_VERIFIER_REVISION = "rei-gemma4-text-shadow-cold-verifier-v2"
WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])"
)


def _phase_config(output_root: Path) -> dict[str, object]:
    resolved = output_root.resolve()
    if resolved == ORIGINAL_OUTPUT_ROOT.resolve():
        return {
            "phase": "S1",
            "seal_path": ORIGINAL_SEAL_PATH,
            "manifest_schema": "rei-gemma4-text-shadow-s1-evidence-manifest-v1",
            "manifest_namespace": "gemma4_text_shadow_s1_evidence",
            "receipt_path": None,
        }
    if resolved == DEFAULT_OUTPUT_ROOT.resolve():
        return {
            "phase": "S1R",
            "seal_path": SEAL_PATH,
            "manifest_schema": "rei-gemma4-text-shadow-s1r-evidence-manifest-v1",
            "manifest_namespace": "gemma4_text_shadow_s1r_evidence",
            "receipt_path": S1R_COLD_VERIFICATION_RECEIPT,
        }
    raise ValueError("Unrecognized Gemma text-shadow evidence root")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json_file_sha256(path: Path) -> str:
    return sha256_hex(json.loads(path.read_text(encoding="utf-8")))


def _create_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)


def _create_json(path: Path, value: object) -> None:
    _create_bytes(path, canonical_json_bytes(value))


def _smoke_inventory(output_root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(output_root.rglob("*")):
        if not path.is_file():
            continue
        relative_path = path.relative_to(output_root).as_posix()
        if relative_path == SMOKE_MANIFEST_NAME:
            continue
        entries.append(
            {
                "relative_path": relative_path,
                "content_sha256": _sha256_file(path),
                "size_bytes": path.stat().st_size,
                "no_authority": not relative_path.startswith("control/"),
            }
        )
    return entries


def _smoke_manifest_value(
    output_root: Path,
    *,
    execution_head: str,
) -> dict[str, object]:
    config = _phase_config(output_root)
    seal_path = config["seal_path"]
    assert isinstance(seal_path, Path)
    base = {
        "schema_version": config["manifest_schema"],
        "phase": config["phase"],
        "execution_head": execution_head,
        "seal_sha256": _canonical_json_file_sha256(seal_path),
        "artifacts": _smoke_inventory(output_root),
        "development_smoke_only": True,
        "model_promoted": False,
        "no_authority": True,
    }
    manifest_id = content_id(str(config["manifest_namespace"]), base)
    payload = {"manifest_id": manifest_id, **base}
    return {**payload, "manifest_sha256": sha256_hex(payload)}


def _walk_json(value: object):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _contains_windows_absolute_path(value: str) -> bool:
    return WINDOWS_ABSOLUTE_PATH.search(value) is not None


def _verify_private_content_absent(output_root: Path) -> None:
    forbidden_keys = {
        "thinking",
        "raw_traceback",
        "raw_response",
        "raw_response_envelope",
        "native_truth",
        "evaluator_gold",
    }
    allowed_thinking_keys = {
        "thinking_present",
        "thinking_sha256",
        "thinking_byte_count",
        "thinking_token_count",
        "thinking_channel",
        "thinking_content_persisted",
    }
    for path in sorted(output_root.rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for value in _walk_json(payload):
            if isinstance(value, dict):
                keys = {str(key) for key in value}
                if keys.intersection(forbidden_keys):
                    raise ValueError("S1 evidence contains a forbidden private key")
                unexpected_thinking = {
                    key
                    for key in keys
                    if "thinking" in key.casefold()
                    and key not in allowed_thinking_keys
                }
                if unexpected_thinking:
                    raise ValueError("S1 evidence contains an unreviewed thinking field")
            elif isinstance(value, str):
                if _contains_windows_absolute_path(value):
                    raise ValueError("Shadow evidence contains a local absolute path")
                if "Traceback (most recent call last)" in value:
                    raise ValueError("S1 evidence contains a raw traceback")


def _verify_smoke_evidence_root(output_root: Path) -> dict[str, object]:
    config = _phase_config(output_root)
    phase = str(config["phase"])
    seal_path = config["seal_path"]
    assert isinstance(seal_path, Path)
    manifest_path = output_root / SMOKE_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError(f"{phase} evidence manifest must be one JSON object")
    execution_head = manifest.get("execution_head")
    if not isinstance(execution_head, str) or not re.fullmatch(
        r"[0-9a-f]{40}", execution_head
    ):
        raise ValueError(f"{phase} evidence manifest has an invalid execution head")
    expected = _smoke_manifest_value(output_root, execution_head=execution_head)
    if manifest != expected:
        raise ValueError(f"{phase} evidence root differs from its closed inventory")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", execution_head, "HEAD"],
        cwd=ROOT,
        check=True,
    )
    seal_at_execution = subprocess.run(
        [
            "git",
            "show",
            f"{execution_head}:{seal_path.relative_to(ROOT).as_posix()}",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    if sha256_hex(json.loads(seal_at_execution)) != manifest["seal_sha256"]:
        raise ValueError(f"{phase} execution commit lacks the sealed bytes")
    _verify_private_content_absent(output_root)
    return manifest


def _pending_cold_verification_state() -> dict[str, bool]:
    return {
        "cold_verification_required": True,
        "evidence_root_closed": True,
    }


def _cold_receipt_value(
    output_root: Path,
    *,
    manifest: Mapping[str, object],
    verifier_head: str,
) -> dict[str, object]:
    manifest_path = output_root / SMOKE_MANIFEST_NAME
    base = {
        "schema_version": (
            "rei-gemma4-text-shadow-cold-verification-receipt-v1"
        ),
        "phase": manifest["phase"],
        "evidence_root": output_root.relative_to(ROOT).as_posix(),
        "evidence_manifest_id": manifest["manifest_id"],
        "evidence_manifest_sha256": manifest["manifest_sha256"],
        "evidence_manifest_file_sha256": _sha256_file(manifest_path),
        "artifact_count": len(manifest["artifacts"]),
        "verifier_revision": COLD_VERIFIER_REVISION,
        "verifier_head": verifier_head,
        "native_run_manifests_verified": 2,
        "shadow_no_authority_ledger_verified": True,
        "private_content_scan_passed": True,
        "cold_verification": "succeeded",
        "no_authority": True,
    }
    receipt_id = content_id("gemma4_text_shadow_cold_verification", base)
    payload = {"receipt_id": receipt_id, **base}
    return {**payload, "receipt_sha256": sha256_hex(payload)}


def _verify_shadow_no_authority_ledger(
    output_root: Path,
    *,
    run_id: str,
) -> ShadowNoAuthorityLedger:
    run_root = output_root / "shadow" / "runs" / run_id
    ledger_path = run_root / "communication_shadow" / "no_authority_ledger.json"
    ledger = ShadowNoAuthorityLedger.model_validate_json(ledger_path.read_bytes())
    actual_paths = {
        path.relative_to(run_root).as_posix()
        for path in (run_root / "communication_shadow").glob("*.json")
        if path.name != ledger_path.name
    }
    if {item.relative_path for item in ledger.artifacts} != actual_paths:
        raise ValueError("S1 shadow roles differ from the no-authority ledger")
    for item in ledger.artifacts:
        artifact = run_root / item.relative_path
        if _sha256_file(artifact) != item.artifact_sha256:
            raise ValueError("S1 shadow role differs from its no-authority hash")
    return ledger


def _git_text(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _build_request() -> ReiNativeCycleRequest:
    """Build the exact reviewed-Slovene S1 request from one frozen fixture."""

    request = ReiNativeCycleRequest.model_validate_json(BASE_FIXTURE.read_bytes())
    evidence_text = {
        "b11_text_fact": "Delavnico je mogoče obnoviti z razpoložljivim materialom.",
        "b11_current_image": "zatemnjena delavnica z zaprtim prehodom",
    }
    evidence = tuple(
        item.model_copy(update={"content": evidence_text[item.evidence_id]})
        for item in request.scene.evidence
    )
    options = tuple(
        item.model_copy(
            update={
                "label": (
                    "obnovi delavnico"
                    if item.option_id == "option_restore"
                    else "pusti zaprto"
                ),
                "description": (
                    "Odpri in obnovi skupno delavnico."
                    if item.option_id == "option_restore"
                    else "Skupna delavnica naj ostane zaprta."
                ),
            }
        )
        for item in request.scene.options
    )
    scene = request.scene.model_copy(
        update={
            "event_id": "s1_gemma4_text_shadow_event",
            "raw_input": "Odloči se, ali obnoviti skupno delavnico ali jo pustiti zaprto.",
            "language": "sl",
            "evidence": evidence,
            "options": options,
            "actors": ("jaz", "sosed"),
            "constraints": ("Uporabi samo razpoložljivi material.",),
            "unknowns": ("Odziv soseda ni znan.",),
        }
    )
    return ReiNativeCycleRequest.model_validate(
        request.model_copy(
            update={
                "run_id": "s1-gemma4-text-shadow-cycle",
                "ego_id": "s1-gemma4-text-shadow-ego",
                "source_commit": CYCLE_SOURCE_COMMIT,
                "scene": scene,
            }
        ).model_dump(mode="python", round_trip=True)
    )


def _run_cycle(
    root: Path,
    request: ReiNativeCycleRequest,
    *,
    shadow_interpreter: object | None = None,
) -> ReiNativeCycleResult:
    return ReiNativeEngine.with_file_stores(
        runs_root=root / "runs",
        ego_traces_root=root / "ego_traces",
        clock=DeterministicExecutionClock(request.started_at),
        racio_interpreter_mode=(
            "deterministic"
            if shadow_interpreter is None
            else "gemma4_text_shadow"
        ),
        shadow_racio_interpreter=shadow_interpreter,
    ).run_cycle(request)


def _packet_pair(
    control: ReiNativeCycleResult,
) -> tuple[RacioEpistemicPacketV3, RacioEpistemicPacketV3]:
    option_descriptions = {
        option.option_id: option.description for option in control.request.scene.options
    }
    packets = tuple(
        build_racio_epistemic_shadow_packet_v3(
            communication.request,
            language="sl",
            option_descriptions=option_descriptions,
        ).packet
        for communication in (
            control.emocio_communication,
            control.instinkt_communication,
        )
    )
    if tuple(packet.source_mind for packet in packets) != ("E", "I"):
        raise ValueError("S1 packet order must remain E then I")
    return packets


def _authority_hashes(result: ReiNativeCycleResult) -> dict[str, str]:
    communication_values = {
        "emocio_request": result.emocio_communication.request,
        "emocio_interpretation": result.emocio_communication.interpretation,
        "emocio_translation_gap": result.emocio_communication.translation_gap,
        "emocio_acceptance_fidelity": (
            result.emocio_communication.acceptance_fidelity
        ),
        "instinkt_request": result.instinkt_communication.request,
        "instinkt_interpretation": result.instinkt_communication.interpretation,
        "instinkt_translation_gap": result.instinkt_communication.translation_gap,
        "instinkt_acceptance_fidelity": (
            result.instinkt_communication.acceptance_fidelity
        ),
    }
    values = {
        "character_authority": result.request.character,
        "acceptance_state": result.request.acceptance_state,
        "racio_world_input": result.racio_world_input,
        "emocio_world_input": result.emocio_world_input,
        "instinkt_world_input": result.instinkt_world_input,
        "racio_native_conclusion": result.racio_execution.conclusion,
        "emocio_native_conclusion": result.emocio_execution.conclusion,
        "instinkt_native_conclusion": result.instinkt_execution.conclusion,
        "native_bundle": result.native_bundle,
        "effective_authority": result.effective_authority,
        "governance": result.governance,
        "emocio_manifestation": result.emocio_manifestation,
        "instinkt_manifestation": result.instinkt_manifestation,
        **communication_values,
        "mandate_view": result.mandate_view,
        "interpretation_inputs": result.interpretation_inputs,
        "conscious_decision": result.conscious_decision,
        "behavior_resultant": result.behavior_resultant,
        "racio_self_narrative": result.narrative,
        "ego_measure": result.ego_measure,
        "ego_trace": result.ego_trace,
        "ego_composition_snapshot": result.composition_snapshot,
        "ego_projections": result.projections,
    }
    return {name: sha256_hex(value) for name, value in values.items()}


class _CountingOllamaClient:
    """Duck-typed client that counts and caps only ``/api/chat`` dispatches."""

    def __init__(self, base: object) -> None:
        self.base = base
        self.chat_dispatch_count = 0

    def __getattr__(self, name: str) -> object:
        """Delegate non-counting client properties to the frozen client."""

        return getattr(self.base, name)

    def get(self, path: str, *, timeout_seconds: float = 10.0):
        return self.base.get(path, timeout_seconds=timeout_seconds)

    def post(
        self,
        path: str,
        payload: Mapping[str, Any],
        *,
        timeout_seconds: float,
    ):
        if path == "/api/chat":
            if self.chat_dispatch_count >= EXPECTED_CALLS:
                raise RuntimeError("S1 refuses more than two /api/chat dispatches")
            self.chat_dispatch_count += 1
        return self.base.post(path, payload, timeout_seconds=timeout_seconds)

    def version(self):
        return self.base.version()

    def model_entry(self, model: str):
        return self.base.model_entry(model)

    def show(self, model: str):
        return self.base.show(model)

    def ps(self):
        return self.base.ps()


def _discover_shadow_interpreter():
    from rei.providers.gemma4_text_shadow import Gemma4TextShadowInterpreter
    from rei.providers.ollama import OllamaApiClient

    environment = dict(os.environ)
    environment.update(
        {
            "REI_OLLAMA_MODEL": MODEL,
            "REI_OLLAMA_NUM_CTX": "65536",
            "REI_OLLAMA_NUM_GPU": "999",
        }
    )
    client = _CountingOllamaClient(OllamaApiClient())
    interpreter = Gemma4TextShadowInterpreter.discover(
        client=client,
        environ=environment,
    )
    if client.chat_dispatch_count != 0:
        raise ValueError("Provider discovery must not dispatch /api/chat")
    return interpreter, client


def _seal_candidate(
    *,
    control: ReiNativeCycleResult,
    packets: tuple[RacioEpistemicPacketV3, RacioEpistemicPacketV3],
    interpreter: object,
) -> dict[str, object]:
    from rei.communication.epistemic_interpreter_v3 import RacioEpistemicDraftV3
    from rei.models.longitudinal import LongitudinalPersonState
    from rei.providers.ollama_gemma4_epistemic_v3 import (
        GEMMA4_EPISTEMIC_V3_INSTRUCTION_SHA256,
        GEMMA4_EPISTEMIC_V3_SCHEMA_SHA256,
    )

    provider = interpreter.provider
    if provider is None:
        failure = interpreter.preflight_failure
        code = None if failure is None else failure.failure_code
        raise ValueError(f"S1 provider discovery failed closed: {code}")
    specs = tuple(provider.build_call_spec(packet) for packet in packets)
    payloads = tuple(provider.request_payload(packet) for packet in packets)
    request = control.request
    person_state = LongitudinalPersonState.create(
        ego_id=request.ego_id,
        structural_character=request.character,
        acceptance_state=request.acceptance_state,
        racio_world=request.racio_world,
        emocio_world=request.emocio_world,
        instinkt_world=request.instinkt_world,
        body_state=request.body_state,
    )
    return {
        "schema_version": "rei-gemma4-text-shadow-s1r-seal-v1",
        "phase": "S1R",
        "main_base_sha": "2da951c4b840dcadd69683b7235616fe4f025f43",
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "branch_head_before_seal": IMPLEMENTATION_COMMIT,
        "branch": BRANCH,
        "cycle_request_sha256": request.content_hash(),
        "person_state_id": person_state.state_id,
        "person_state_sha256": person_state.state_hash,
        "body_state_sha256": request.body_state.content_hash(),
        "character_authority_sha256": request.character.content_hash(),
        "acceptance_state_sha256": request.acceptance_state.content_hash(),
        "racio_world_sha256": request.racio_world.content_hash(),
        "emocio_world_sha256": request.emocio_world.content_hash(),
        "instinkt_world_sha256": request.instinkt_world.content_hash(),
        "base_fixture": BASE_FIXTURE.relative_to(ROOT).as_posix(),
        "base_fixture_sha256": _sha256_file(BASE_FIXTURE),
        "request_builder_sha256": _sha256_file(Path(__file__).resolve()),
        "presentation_mode": "canonical_sl_only",
        "packet_order": ["E", "I"],
        "packet_ids": [packet.packet_id for packet in packets],
        "packet_hashes": [packet.packet_hash for packet in packets],
        "provider_payload_hashes": [sha256_hex(payload) for payload in payloads],
        "call_spec_ids": [spec.call_id for spec in specs],
        "call_spec_hashes": [spec.content_hash() for spec in specs],
        "provider_identity": provider.identity.model_dump(mode="json"),
        "provider_revision": PROVIDER_REVISION,
        "instruction_sha256": GEMMA4_EPISTEMIC_V3_INSTRUCTION_SHA256,
        "draft_v3_schema_sha256": GEMMA4_EPISTEMIC_V3_SCHEMA_SHA256,
        "canonical_interpretation_v3_schema_sha256": sha256_hex(
            RacioEpistemicInterpretationV3.model_json_schema()
        ),
        "packet_v3_schema_sha256": sha256_hex(
            RacioEpistemicPacketV3.model_json_schema()
        ),
        "draft_model_schema_sha256": sha256_hex(
            RacioEpistemicDraftV3.model_json_schema()
        ),
        "model": MODEL,
        "model_digest": MODEL_DIGEST,
        "endpoint": "/api/chat",
        "context": 65536,
        "num_gpu": 999,
        "num_predict": 16384,
        "seed": 314159,
        "temperature": 0.0,
        "top_p": 0.95,
        "top_k": 64,
        "retry_count": 0,
        "fallback_count": 0,
        "require_full_gpu": True,
        "thinking_channel": "separate_private_not_persisted",
        "expected_model_calls": EXPECTED_CALLS,
        "output_root": EXPECTED_OUTPUT_ROOT,
        "development_smoke_only": True,
        "holdout": False,
        "model_promoted": False,
        "governance_authority": False,
        "decision_authority": False,
        "behavior_authority": False,
        "mind_world_authority": False,
    }


def _load_seal() -> dict[str, object]:
    seal = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
    if not isinstance(seal, dict):
        raise ValueError("S1R seal must be one JSON object")
    return seal


def _require_sealed_clean_source() -> str:
    if _git_text("branch", "--show-current") != BRANCH:
        raise ValueError("S1R execution requires the dedicated shadow branch")
    head = _git_text("rev-parse", "HEAD")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", IMPLEMENTATION_COMMIT, head],
        cwd=ROOT,
        check=True,
    )
    if _git_text("status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("S1R execution requires a clean committed worktree")
    runtime_delta = _git_text(
        "diff",
        "--name-only",
        IMPLEMENTATION_COMMIT,
        head,
        "--",
        "app/backend/rei",
        "tests/rei/test_racio_text_shadow.py",
    )
    if runtime_delta:
        raise ValueError("S1R runtime or focused tests changed after implementation seal")
    return head


class _SealedShadowInterpreter:
    def __init__(self, inner: object, seal: Mapping[str, object]) -> None:
        self.inner = inner
        self.expected_packet_hashes = tuple(seal["packet_hashes"])
        self.expected_call_spec_hashes = tuple(seal["call_spec_hashes"])
        self.index = 0

    def interpret_shadow(
        self,
        packet: RacioEpistemicPacketV3,
        *,
        clock: ExecutionClock,
    ) -> ShadowProviderAttempt:
        if self.index >= EXPECTED_CALLS:
            raise ValueError("S1R received more than two shadow lanes")
        if packet.packet_hash != self.expected_packet_hashes[self.index]:
            raise ValueError("S1R runtime packet differs from its pre-call seal")
        provider = self.inner.provider
        if provider is not None:
            canonical_spec = provider.build_call_spec(packet)
            if (
                canonical_spec.content_hash()
                != self.expected_call_spec_hashes[self.index]
            ):
                raise ValueError("S1R runtime call spec differs from its pre-call seal")
        elif self.inner.preflight_failure is None:
            raise ValueError("S1R shadow dependency has no provider or bounded failure")
        self.index += 1
        return self.inner.interpret_shadow(packet, clock=clock)


def derive_seal(work_root: Path) -> int:
    if work_root.exists():
        raise ValueError("Seal-derivation root must not already exist")
    request = _build_request()
    control = _run_cycle(work_root, request)
    packets = _packet_pair(control)
    interpreter, client = _discover_shadow_interpreter()
    candidate = _seal_candidate(
        control=control,
        packets=packets,
        interpreter=interpreter,
    )
    if client.chat_dispatch_count != 0:
        raise ValueError("Seal derivation dispatched an unauthorized chat call")
    sys.stdout.buffer.write(canonical_json_bytes(candidate))
    sys.stdout.buffer.flush()
    return 0


def execute_smoke(output_root: Path) -> int:
    head = _require_sealed_clean_source()
    seal = _load_seal()
    if output_root.resolve() != DEFAULT_OUTPUT_ROOT.resolve():
        raise ValueError("S1R execution output root differs from the seal")
    if output_root.exists():
        raise ValueError("S1R output root is create-only and already exists")
    if S1R_COLD_VERIFICATION_RECEIPT.exists():
        raise ValueError("S1R cold-verification receipt is create-only")
    output_root.mkdir(parents=True)
    _create_json(
        output_root / "planned_ledger.json",
        {
            "schema_version": "rei-gemma4-text-shadow-s1r-planned-ledger-v1",
            "phase": "S1R",
            "execution_head": head,
            "packet_order": ["E", "I"],
            "maximum_model_calls": EXPECTED_CALLS,
            "retry_count": 0,
            "fallback_count": 0,
            "no_authority": True,
        },
    )

    request = _build_request()
    control = _run_cycle(output_root / "control", request)
    packets = _packet_pair(control)
    for label, packet in zip(("emocio", "instinkt"), packets, strict=True):
        _create_json(output_root / "preflight" / f"{label}_packet_v3.json", packet)

    interpreter, client = _discover_shadow_interpreter()
    provider_preflight_status = "succeeded"
    provider_preflight_failure_code = None
    call_specs_match = False
    if interpreter.provider is None:
        failure = interpreter.preflight_failure
        if failure is None:
            raise ValueError("S1R provider discovery returned no bounded outcome")
        provider_preflight_status = "failed"
        provider_preflight_failure_code = failure.failure_code
        if [packet.packet_hash for packet in packets] != seal["packet_hashes"]:
            raise ValueError("Live S1R packets differ from the committed seal")
    else:
        candidate = _seal_candidate(
            control=control,
            packets=packets,
            interpreter=interpreter,
        )
        if candidate != seal:
            raise ValueError("Live S1R preflight differs from the committed seal")
        specs = tuple(
            interpreter.provider.build_call_spec(packet) for packet in packets
        )
        for label, spec in zip(("emocio", "instinkt"), specs, strict=True):
            _create_json(output_root / "preflight" / f"{label}_call_spec.json", spec)
        call_specs_match = True
    _create_json(
        output_root / "preflight" / "seal_receipt.json",
        {
            "schema_version": "rei-gemma4-text-shadow-s1r-seal-receipt-v1",
            "phase": "S1R",
            "execution_head": head,
            "seal_sha256": _canonical_json_file_sha256(SEAL_PATH),
            "chat_dispatch_count_before_execution": client.chat_dispatch_count,
            "packets_match": True,
            "call_specs_match": call_specs_match,
            "provider_preflight_status": provider_preflight_status,
            "provider_preflight_failure_code": provider_preflight_failure_code,
            "no_authority": True,
        },
    )
    sealed_interpreter = _SealedShadowInterpreter(interpreter, seal)
    shadow = _run_cycle(
        output_root / "shadow",
        request,
        shadow_interpreter=sealed_interpreter,
    )
    if sealed_interpreter.index != EXPECTED_CALLS:
        raise ValueError("S1R did not attempt both precommitted E/I lanes")

    control_authority = _authority_hashes(control)
    shadow_authority = _authority_hashes(shadow)
    authority_unchanged = control_authority == shadow_authority
    if not authority_unchanged:
        raise ValueError("Shadow execution changed authoritative cycle artifacts")
    FileArtifactStore(output_root / "control" / "runs").verify_run(request.run_id)
    FileArtifactStore(output_root / "shadow" / "runs").verify_run(request.run_id)
    _verify_shadow_no_authority_ledger(output_root, run_id=request.run_id)

    statuses = [item.result.status for item in shadow.shadow_communications]
    call_records = [
        item.call_record
        for item in shadow.shadow_communications
        if item.call_record is not None
    ]
    retries = 0
    fallbacks = sum(1 for record in call_records if record.fallback is not None)
    successful = statuses == ["succeeded", "succeeded"]
    summary = {
        "schema_version": "rei-gemma4-text-shadow-s1r-summary-v1",
        "phase": "S1R",
        "execution_head": head,
        "control_run_id": control.request.run_id,
        "shadow_run_id": shadow.request.run_id,
        "packet_order": [item.source_mind for item in shadow.shadow_communications],
        "shadow_statuses": statuses,
        "provider_call_records": len(call_records),
        "api_chat_dispatches": client.chat_dispatch_count,
        "provider_preflight_status": provider_preflight_status,
        "provider_preflight_failure_code": provider_preflight_failure_code,
        "retries": retries,
        "fallbacks": fallbacks,
        "authoritative_hashes": control_authority,
        "authoritative_cycle_unchanged": authority_unchanged,
        "world_update_inputs_and_ego_projections_unchanged": authority_unchanged,
        "standalone_mindworld_updaters_exercised": False,
        "control_manifest_sha256": control.manifest.content_hash(),
        "shadow_manifest_sha256": shadow.manifest.content_hash(),
        **_pending_cold_verification_state(),
        "thinking_content_persisted": False,
        "development_smoke_only": True,
        "holdout": False,
        "model_promoted": False,
        "no_authority": True,
        "technical_smoke_succeeded": (
            successful
            and len(call_records) == EXPECTED_CALLS
            and client.chat_dispatch_count == EXPECTED_CALLS
            and retries == 0
            and fallbacks == 0
        ),
    }
    _create_json(output_root / "summary.json", summary)
    report = "\n".join(
        (
            "# Gemma 4 text shadow S1R smoke",
            "",
            "Technical backend integration smoke only; not a holdout, promotion, or authority grant.",
            "",
            f"- execution head: `{head}`",
            f"- E/I shadow statuses: `{statuses}`",
            f"- `/api/chat` dispatches: `{client.chat_dispatch_count}`",
            f"- retries/fallbacks: `{retries}/{fallbacks}`",
            f"- authoritative cycle unchanged: `{authority_unchanged}`",
            "- deterministic interpreter remains authoritative",
            "- governance/decision/behavior/MindWorld authority: `false`",
            "- cycle inputs and Ego projections for deterministic MindWorld updates are unchanged",
            "- standalone post-cycle MindWorld updaters were not exercised by this S1R smoke",
            "- thinking content persisted: `false`",
            f"- technical smoke succeeded: `{summary['technical_smoke_succeeded']}`",
            "",
        )
    )
    _create_bytes(output_root / "report.md", report.encode("utf-8"))
    _create_json(
        output_root / SMOKE_MANIFEST_NAME,
        _smoke_manifest_value(output_root, execution_head=head),
    )
    _verify_and_issue_cold_receipt(
        output_root,
        receipt_path=S1R_COLD_VERIFICATION_RECEIPT,
    )
    sys.stdout.buffer.write(canonical_json_bytes(summary))
    sys.stdout.buffer.flush()
    return 0 if summary["technical_smoke_succeeded"] else 2


def _cold_verification_checks(output_root: Path) -> dict[str, object]:
    config = _phase_config(output_root)
    phase = str(config["phase"])
    summary = json.loads((output_root / "summary.json").read_text(encoding="utf-8"))
    request = _build_request()
    for lane in ("control", "shadow"):
        FileArtifactStore(output_root / lane / "runs").verify_run(request.run_id)
    _verify_shadow_no_authority_ledger(output_root, run_id=request.run_id)
    manifest = _verify_smoke_evidence_root(output_root)
    if summary.get("no_authority") is not True:
        raise ValueError(f"{phase} summary lost its no-authority marker")
    if summary.get("thinking_content_persisted") is not False:
        raise ValueError(f"{phase} summary claims persisted thinking content")
    if phase == "S1R":
        if summary.get("cold_verification_required") is not True:
            raise ValueError("S1R summary lost its verification requirement")
        if summary.get("evidence_root_closed") is not True:
            raise ValueError("S1R summary does not claim a closed evidence root")
        if "cold_verification" in summary:
            raise ValueError("S1R summary prematurely claims cold-verification success")
    return manifest


def _verify_and_issue_cold_receipt(
    output_root: Path,
    *,
    receipt_path: Path,
    verifier: Callable[[Path], dict[str, object]] = _cold_verification_checks,
) -> dict[str, object]:
    if receipt_path.exists():
        raise FileExistsError(receipt_path)
    manifest = verifier(output_root)
    receipt = _cold_receipt_value(
        output_root,
        manifest=manifest,
        verifier_head=_git_text("rev-parse", "HEAD"),
    )
    _create_json(receipt_path, receipt)
    return receipt


def _verify_cold_receipt(
    output_root: Path,
    *,
    manifest: Mapping[str, object],
    receipt_path: Path,
) -> dict[str, object]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise ValueError("S1R cold-verification receipt must be one JSON object")
    verifier_head = receipt.get("verifier_head")
    if not isinstance(verifier_head, str) or not re.fullmatch(
        r"[0-9a-f]{40}", verifier_head
    ):
        raise ValueError("S1R cold-verification receipt has an invalid head")
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", verifier_head, "HEAD"],
        cwd=ROOT,
        check=True,
    )
    expected = _cold_receipt_value(
        output_root,
        manifest=manifest,
        verifier_head=verifier_head,
    )
    if receipt != expected:
        raise ValueError("S1R cold-verification receipt differs from its evidence")
    return receipt


def cold_verify(output_root: Path) -> int:
    config = _phase_config(output_root)
    manifest = _cold_verification_checks(output_root)
    receipt_path = config["receipt_path"]
    if isinstance(receipt_path, Path):
        _verify_cold_receipt(
            output_root,
            manifest=manifest,
            receipt_path=receipt_path,
        )
    print(f"{config['phase']} cold verification succeeded")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--derive-seal", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--cold-verify", action="store_true")
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.derive_seal:
        if args.work_root is None:
            raise ValueError("--derive-seal requires --work-root")
        return derive_seal(args.work_root.resolve())
    if args.execute:
        return execute_smoke(args.output_root.resolve())
    return cold_verify(args.output_root.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
