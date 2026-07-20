"""Run one sealed English-primary Gemma text-shadow integration smoke.

The runner performs one model-free control cycle and one identical native
cycle with the explicitly injected Gemma text-shadow adapter. The shadow cycle
may dispatch exactly two ``/api/chat`` requests, strictly E then I, with no
retry or fallback. Shadow output remains terminal and non-authoritative.
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
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "app" / "backend"
for import_root in (ROOT, BACKEND_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))


from rei.communication.epistemic_interpreter_en import (  # noqa: E402
    RacioEpistemicInterpretationEnV3,
    RacioEpistemicPacketEnV3,
)
from rei.communication.epistemic_interpreter_v3 import (  # noqa: E402
    RacioEpistemicDraftV3,
)
from rei.communication.text_shadow import (  # noqa: E402
    ShadowProviderAttempt,
    build_racio_epistemic_shadow_packet_en_v3,
)
from rei.engine import ReiNativeCycleRequest, ReiNativeCycleResult  # noqa: E402
from rei.ids import canonical_json_bytes, content_id, sha256_hex  # noqa: E402
from rei.models.longitudinal import LongitudinalPersonState  # noqa: E402
from rei.persistence import FileArtifactStore  # noqa: E402
from rei.providers.native import ExecutionClock  # noqa: E402
from rei.providers.ollama_gemma4_epistemic_v3 import (  # noqa: E402
    GEMMA4_EPISTEMIC_V3_INSTRUCTION_SHA256,
    GEMMA4_EPISTEMIC_V3_SCHEMA_SHA256,
)
from scripts.run_gemma4_racio_text_shadow_smoke import (  # noqa: E402
    _authority_hashes,
    _create_bytes,
    _create_json,
    _evidence_root_snapshot,
    _run_cycle,
    _verify_private_content_absent,
    _verify_shadow_no_authority_ledger,
)


IMPLEMENTATION_COMMIT = "e607993baafa2ebe743251d3baaee38e2e9c190d"
BRANCH = "codex/rei-english-runtime-smoke"
BASE_FIXTURE = (
    ROOT / "tests" / "fixtures" / "native_cycles" / "deterministic_e2e.json"
)
SEAL_PATH = (
    ROOT
    / "Docs"
    / "evals"
    / "research_reset_2026-07"
    / "gemma4_english_runtime_shadow_smoke_seal.json"
)
OUTPUT_ROOT = (
    ROOT
    / "Docs"
    / "evals"
    / "semantic_lab_v1"
    / "en1-gemma4-text-shadow-2026-07-20"
)
RECEIPT_PATH = (
    ROOT
    / "Docs"
    / "evals"
    / "research_reset_2026-07"
    / "gemma4_english_runtime_shadow_smoke_receipt.json"
)
EXPECTED_OUTPUT_ROOT = (
    "Docs/evals/semantic_lab_v1/en1-gemma4-text-shadow-2026-07-20"
)
MODEL = "gemma4:31b"
MODEL_DIGEST = (
    "6316f0629137b426c9d9b853ffc4c8209589f30ee39aebede6285096c0ff47e7"
)
PROVIDER_REVISION = "rei-racio-gemma4-epistemic-v3-en-chat-v1"
EXPECTED_CALLS = 2
MANIFEST_NAME = "smoke_evidence_manifest.json"
WINDOWS_ABSOLUTE_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/](?![\\/])")


def _git_text(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json_file_sha256(path: Path) -> str:
    return sha256_hex(json.loads(path.read_text(encoding="utf-8")))


def _build_request() -> ReiNativeCycleRequest:
    """Build the exact English equivalent of the reviewed S1R cycle."""

    request = ReiNativeCycleRequest.model_validate_json(BASE_FIXTURE.read_bytes())
    evidence_text = {
        "b11_text_fact": (
            "The shared workshop can be restored with the available materials."
        ),
        "b11_current_image": "a dim workshop with a closed passage",
    }
    evidence = tuple(
        item.model_copy(update={"content": evidence_text[item.evidence_id]})
        for item in request.scene.evidence
    )
    options = tuple(
        item.model_copy(
            update={
                "label": (
                    "restore the workshop"
                    if item.option_id == "option_restore"
                    else "leave it closed"
                ),
                "description": (
                    "Open and restore the shared workshop."
                    if item.option_id == "option_restore"
                    else "Keep the shared workshop closed."
                ),
            }
        )
        for item in request.scene.options
    )
    scene = request.scene.model_copy(
        update={
            "event_id": "en1_gemma4_text_shadow_event",
            "raw_input": (
                "Decide whether to restore the shared workshop or leave it closed."
            ),
            "language": "en",
            "evidence": evidence,
            "options": options,
            "actors": ("self", "neighbor"),
            "constraints": ("Use only the available materials.",),
            "unknowns": ("The neighbor's response is unknown.",),
        }
    )
    return ReiNativeCycleRequest.model_validate(
        request.model_copy(
            update={
                "run_id": "en1-gemma4-text-shadow-cycle",
                "ego_id": "en1-gemma4-text-shadow-ego",
                "source_commit": IMPLEMENTATION_COMMIT,
                "scene": scene,
            }
        ).model_dump(mode="python", round_trip=True)
    )


def _packet_pair(
    control: ReiNativeCycleResult,
) -> tuple[RacioEpistemicPacketEnV3, RacioEpistemicPacketEnV3]:
    option_descriptions = {
        option.option_id: option.description for option in control.request.scene.options
    }
    packets = tuple(
        build_racio_epistemic_shadow_packet_en_v3(
            communication.request,
            language="en",
            option_descriptions=option_descriptions,
        ).packet
        for communication in (
            control.emocio_communication,
            control.instinkt_communication,
        )
    )
    if tuple(packet.source_mind for packet in packets) != ("E", "I"):
        raise ValueError("English smoke packet order must remain E then I")
    return packets  # type: ignore[return-value]


class _CountingOllamaClient:
    """Count and cap only chat dispatches while delegating discovery calls."""

    def __init__(self, base: object) -> None:
        self.base = base
        self.chat_dispatch_count = 0

    def __getattr__(self, name: str) -> object:
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
                raise RuntimeError("English smoke refuses more than two chat calls")
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
        raise ValueError("Provider discovery dispatched an unauthorized chat call")
    return interpreter, client


def _seal_candidate(
    *,
    control: ReiNativeCycleResult,
    packets: tuple[RacioEpistemicPacketEnV3, RacioEpistemicPacketEnV3],
    interpreter: object,
    branch_head_before_seal: str,
) -> dict[str, object]:
    provider = interpreter.provider
    if provider is None:
        failure = interpreter.preflight_failure
        code = None if failure is None else failure.failure_code
        raise ValueError(f"English provider discovery failed closed: {code}")
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
        "schema_version": "rei-gemma4-english-shadow-smoke-seal-v1",
        "phase": "EN1",
        "implementation_commit": IMPLEMENTATION_COMMIT,
        "branch_head_before_seal": branch_head_before_seal,
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
        "runner_sha256": _sha256_file(Path(__file__).resolve()),
        "language": "en",
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
        "canonical_interpretation_schema_sha256": sha256_hex(
            RacioEpistemicInterpretationEnV3.model_json_schema()
        ),
        "packet_schema_sha256": sha256_hex(
            RacioEpistemicPacketEnV3.model_json_schema()
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
        "no_authority": True,
    }


class _SealedShadowInterpreter:
    def __init__(self, inner: object, seal: Mapping[str, object]) -> None:
        self.inner = inner
        self.expected_packet_hashes = tuple(seal["packet_hashes"])
        self.expected_call_spec_hashes = tuple(seal["call_spec_hashes"])
        self.index = 0

    def interpret_shadow(
        self,
        packet: RacioEpistemicPacketEnV3,
        *,
        clock: ExecutionClock,
    ) -> ShadowProviderAttempt:
        if self.index >= EXPECTED_CALLS:
            raise ValueError("English smoke received more than two shadow lanes")
        if packet.packet_hash != self.expected_packet_hashes[self.index]:
            raise ValueError("Runtime packet differs from the English pre-call seal")
        provider = self.inner.provider
        if provider is not None:
            spec = provider.build_call_spec(packet)
            if spec.content_hash() != self.expected_call_spec_hashes[self.index]:
                raise ValueError("Runtime call spec differs from the pre-call seal")
        elif self.inner.preflight_failure is None:
            raise ValueError("Shadow dependency has no provider or bounded failure")
        self.index += 1
        return self.inner.interpret_shadow(packet, clock=clock)


def _inventory(output_root: Path) -> list[dict[str, object]]:
    artifacts: list[dict[str, object]] = []
    for path in sorted(output_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(output_root).as_posix()
        if relative == MANIFEST_NAME:
            continue
        artifacts.append(
            {
                "relative_path": relative,
                "content_sha256": _sha256_file(path),
                "size_bytes": path.stat().st_size,
                "no_authority": not relative.startswith("control/"),
            }
        )
    return artifacts


def _manifest_value(output_root: Path, *, execution_head: str) -> dict[str, object]:
    base = {
        "schema_version": "rei-gemma4-english-shadow-smoke-manifest-v1",
        "phase": "EN1",
        "execution_head": execution_head,
        "seal_sha256": _canonical_json_file_sha256(SEAL_PATH),
        "artifacts": _inventory(output_root),
        "development_smoke_only": True,
        "model_promoted": False,
        "no_authority": True,
    }
    manifest_id = content_id("gemma4_english_shadow_smoke_manifest", base)
    payload = {"manifest_id": manifest_id, **base}
    return {**payload, "manifest_sha256": sha256_hex(payload)}


def _verify_root(output_root: Path) -> dict[str, object]:
    manifest_path = output_root / MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("English smoke manifest must be one JSON object")
    execution_head = manifest.get("execution_head")
    if not isinstance(execution_head, str) or not re.fullmatch(
        r"[0-9a-f]{40}", execution_head
    ):
        raise ValueError("English smoke manifest has an invalid execution head")
    if manifest != _manifest_value(output_root, execution_head=execution_head):
        raise ValueError("English smoke evidence differs from its closed inventory")
    seal_bytes = subprocess.run(
        [
            "git",
            "show",
            f"{execution_head}:{SEAL_PATH.relative_to(ROOT).as_posix()}",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    if sha256_hex(json.loads(seal_bytes)) != manifest["seal_sha256"]:
        raise ValueError("Execution commit does not contain the sealed bytes")
    _verify_private_content_absent(output_root)
    return manifest


def _receipt_value(
    output_root: Path,
    *,
    manifest: Mapping[str, object],
) -> dict[str, object]:
    summary = json.loads((output_root / "summary.json").read_text(encoding="utf-8"))
    base = {
        "schema_version": "rei-gemma4-english-shadow-smoke-receipt-v1",
        "phase": "EN1",
        "execution_head": manifest["execution_head"],
        "manifest_id": manifest["manifest_id"],
        "manifest_sha256": manifest["manifest_sha256"],
        "evidence_root_integrity_status": "succeeded",
        "shadow_statuses": summary["shadow_statuses"],
        "calls": summary["api_chat_dispatches"],
        "retries": summary["retries"],
        "fallbacks": summary["fallbacks"],
        "authoritative_cycle_unchanged": summary[
            "authoritative_cycle_unchanged"
        ],
        "thinking_content_persisted": False,
        "evidence_root_mutated_during_verification": False,
        "model_promoted": False,
        "holdout": False,
        "no_authority": True,
        "receipt_status": "succeeded",
    }
    receipt_id = content_id("gemma4_english_shadow_receipt", base)
    payload = {"receipt_id": receipt_id, **base}
    return {**payload, "receipt_sha256": sha256_hex(payload)}


def derive_seal(work_root: Path) -> int:
    if work_root.exists():
        raise ValueError("Seal-derivation root must not already exist")
    if _git_text("branch", "--show-current") != BRANCH:
        raise ValueError("Seal derivation requires the dedicated smoke branch")
    request = _build_request()
    control = _run_cycle(work_root, request)
    packets = _packet_pair(control)
    interpreter, client = _discover_shadow_interpreter()
    candidate = _seal_candidate(
        control=control,
        packets=packets,
        interpreter=interpreter,
        branch_head_before_seal=_git_text("rev-parse", "HEAD"),
    )
    if client.chat_dispatch_count != 0:
        raise ValueError("Seal derivation dispatched an unauthorized chat call")
    sys.stdout.buffer.write(canonical_json_bytes(candidate))
    sys.stdout.buffer.flush()
    return 0


def _load_seal() -> dict[str, object]:
    seal = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
    if not isinstance(seal, dict):
        raise ValueError("English smoke seal must be one JSON object")
    return seal


def _require_sealed_clean_source(seal: Mapping[str, object]) -> str:
    if _git_text("branch", "--show-current") != BRANCH:
        raise ValueError("Execution requires the dedicated smoke branch")
    if _git_text("status", "--porcelain=v1", "--untracked-files=all"):
        raise ValueError("Execution requires a clean committed worktree")
    head = _git_text("rev-parse", "HEAD")
    pre_seal_head = str(seal["branch_head_before_seal"])
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", pre_seal_head, head],
        cwd=ROOT,
        check=True,
    )
    runtime_delta = _git_text(
        "diff",
        "--name-only",
        pre_seal_head,
        head,
        "--",
        "app/backend/rei",
        "scripts/run_gemma4_racio_english_shadow_smoke.py",
        "tests/rei/test_english_runtime_shadow_smoke.py",
    )
    if runtime_delta:
        raise ValueError("Runtime, runner, or focused tests changed after sealing")
    return head


def execute_smoke(output_root: Path) -> int:
    seal = _load_seal()
    head = _require_sealed_clean_source(seal)
    if output_root.resolve() != OUTPUT_ROOT.resolve():
        raise ValueError("Execution output root differs from the seal")
    if output_root.exists() or RECEIPT_PATH.exists():
        raise ValueError("English smoke evidence and receipt are create-only")
    output_root.mkdir(parents=True)
    _create_json(
        output_root / "planned_ledger.json",
        {
            "schema_version": "rei-gemma4-english-shadow-planned-ledger-v1",
            "phase": "EN1",
            "execution_head": head,
            "language": "en",
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
        _create_json(output_root / "preflight" / f"{label}_packet_en_v3.json", packet)

    interpreter, client = _discover_shadow_interpreter()
    if interpreter.provider is None:
        failure = interpreter.preflight_failure
        code = None if failure is None else failure.failure_code
        raise ValueError(f"English provider preflight failed: {code}")
    candidate = _seal_candidate(
        control=control,
        packets=packets,
        interpreter=interpreter,
        branch_head_before_seal=str(seal["branch_head_before_seal"]),
    )
    if candidate != seal:
        raise ValueError("Live preflight differs from the committed English seal")
    specs = tuple(interpreter.provider.build_call_spec(packet) for packet in packets)
    for label, spec in zip(("emocio", "instinkt"), specs, strict=True):
        _create_json(output_root / "preflight" / f"{label}_call_spec.json", spec)
    _create_json(
        output_root / "preflight" / "seal_receipt.json",
        {
            "schema_version": "rei-gemma4-english-shadow-seal-receipt-v1",
            "phase": "EN1",
            "execution_head": head,
            "seal_sha256": _canonical_json_file_sha256(SEAL_PATH),
            "chat_dispatch_count_before_execution": client.chat_dispatch_count,
            "packets_match": True,
            "call_specs_match": True,
            "provider_preflight_status": "succeeded",
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
        raise ValueError("English smoke did not attempt both precommitted lanes")

    control_authority = _authority_hashes(control)
    shadow_authority = _authority_hashes(shadow)
    authority_unchanged = control_authority == shadow_authority
    if not authority_unchanged:
        raise ValueError("English shadow execution changed authoritative artifacts")
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
        "schema_version": "rei-gemma4-english-shadow-smoke-summary-v1",
        "phase": "EN1",
        "execution_head": head,
        "language": "en",
        "control_run_id": control.request.run_id,
        "shadow_run_id": shadow.request.run_id,
        "packet_order": [item.source_mind for item in shadow.shadow_communications],
        "shadow_statuses": statuses,
        "provider_call_records": len(call_records),
        "api_chat_dispatches": client.chat_dispatch_count,
        "retries": retries,
        "fallbacks": fallbacks,
        "authoritative_hashes": control_authority,
        "authoritative_cycle_unchanged": authority_unchanged,
        "control_manifest_sha256": control.manifest.content_hash(),
        "shadow_manifest_sha256": shadow.manifest.content_hash(),
        "cold_verification_required": True,
        "evidence_root_closed": True,
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
            "# Gemma 4 English runtime text-shadow smoke",
            "",
            "Technical development smoke only; not a holdout, promotion, or authority grant.",
            "",
            f"- execution head: `{head}`",
            f"- E/I shadow statuses: `{statuses}`",
            f"- `/api/chat` dispatches: `{client.chat_dispatch_count}`",
            f"- retries/fallbacks: `{retries}/{fallbacks}`",
            f"- authoritative cycle unchanged: `{authority_unchanged}`",
            "- deterministic interpreter remains authoritative",
            "- governance/decision/behavior/MindWorld/Ego authority: `false`",
            "- thinking content persisted: `false`",
            f"- technical smoke succeeded: `{summary['technical_smoke_succeeded']}`",
            "",
        )
    )
    _create_bytes(output_root / "report.md", report.encode("utf-8"))
    _create_json(output_root / MANIFEST_NAME, _manifest_value(output_root, execution_head=head))

    snapshot_before = _evidence_root_snapshot(output_root)
    manifest = _verify_root(output_root)
    if snapshot_before != _evidence_root_snapshot(output_root):
        raise ValueError("Evidence root changed during cold verification")
    receipt = _receipt_value(output_root, manifest=manifest)
    _create_json(RECEIPT_PATH, receipt)
    if receipt != _receipt_value(output_root, manifest=manifest):
        raise ValueError("External receipt is not reproducible")
    sys.stdout.buffer.write(canonical_json_bytes(summary))
    sys.stdout.buffer.flush()
    return 0 if summary["technical_smoke_succeeded"] else 2


def cold_verify(output_root: Path) -> int:
    snapshot_before = _evidence_root_snapshot(output_root)
    manifest = _verify_root(output_root)
    receipt = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    if receipt != _receipt_value(output_root, manifest=manifest):
        raise ValueError("English smoke receipt differs from verified evidence")
    if snapshot_before != _evidence_root_snapshot(output_root):
        raise ValueError("Evidence root changed during cold verification")
    print("English Gemma shadow smoke cold verification succeeded")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--derive-seal", action="store_true")
    mode.add_argument("--execute", action="store_true")
    mode.add_argument("--cold-verify", action="store_true")
    parser.add_argument("--work-root", type=Path)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
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
