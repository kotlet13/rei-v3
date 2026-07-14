from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
from typing import Any, Literal, Mapping, cast

ProcessorMind = Literal["racio", "emocio", "instinkt"]
PromptMode = Literal["compact", "full"]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONTRACT_PATH = _REPO_ROOT / "knowledge" / "canon" / "processor_contracts.json"

_MIND_FLAGS: dict[ProcessorMind, tuple[bool, bool]] = {
    "racio": (True, False),
    "emocio": (False, True),
    "instinkt": (False, True),
}

_PROCESSING_MODES: dict[ProcessorMind, str] = {
    "racio": "conscious verbal-analytical interpretation",
    "emocio": "Racio-translated approximation of unconscious image/social/desire signal",
    "instinkt": "Racio-translated approximation of unconscious protective/fear/attachment signal",
}

_CANONICAL_ATTACHED_KEYS = {
    "native_language",
    "world_filter",
    "primary_motive",
    "truth_model",
    "defense_mode",
    "justice_model",
    "accepting_expression",
    "accepted_expression",
    "non_accepting_distortion",
    "non_accepted_expression",
    "resistance_to_other_minds",
    "what_this_mind_needs",
    "risk_if_ignored",
    "risk_if_dominant",
    "blind_spot",
    "source_refs",
    "safety_flags",
}


class ContractError(RuntimeError):
    """Raised when the canonical processor contract file is missing or invalid."""


@lru_cache(maxsize=4)
def load_contract_pack(path: str | None = None) -> dict[str, Any]:
    contract_path = Path(path) if path else _DEFAULT_CONTRACT_PATH
    if not contract_path.exists():
        raise ContractError(f"Missing REI contract pack: {contract_path}")
    try:
        data = json.loads(contract_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(f"Invalid REI contract pack JSON: {contract_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ContractError("REI contract pack root must be an object.")
    if "processors" not in data or not isinstance(data["processors"], dict):
        raise ContractError("REI contract pack must contain processors object.")
    for mind in ("racio", "emocio", "instinkt"):
        if mind not in data["processors"]:
            raise ContractError(f"REI contract pack missing processor: {mind}")
    return data


def get_processor_contract(mind: ProcessorMind, path: str | None = None) -> dict[str, Any]:
    pack = load_contract_pack(path)
    contract = pack["processors"].get(mind)
    if not isinstance(contract, dict):
        raise ContractError(f"Invalid contract for mind: {mind}")
    expected_conscious, expected_translated = _MIND_FLAGS[mind]
    if contract.get("conscious_access") is not expected_conscious:
        raise ContractError(f"{mind} contract has wrong conscious_access flag.")
    if contract.get("translated_by_racio") is not expected_translated:
        raise ContractError(f"{mind} contract has wrong translated_by_racio flag.")
    return cast(dict[str, Any], contract)


def required_keys_for(mind: ProcessorMind, path: str | None = None) -> list[str]:
    contract = get_processor_contract(mind, path)
    output_contract = contract.get("output_contract")
    if not isinstance(output_contract, dict):
        raise ContractError(f"{mind} contract missing output_contract.")
    keys = output_contract.get("required_keys")
    if not isinstance(keys, list) or not all(isinstance(item, str) for item in keys):
        raise ContractError(f"{mind} contract output_contract.required_keys must be list[str].")
    return list(keys)


def canonical_keys_for(mind: ProcessorMind, path: str | None = None) -> list[str]:
    return [key for key in required_keys_for(mind, path) if key in _CANONICAL_ATTACHED_KEYS]


def runtime_required_keys_for(mind: ProcessorMind, path: str | None = None) -> list[str]:
    return [key for key in required_keys_for(mind, path) if key not in _CANONICAL_ATTACHED_KEYS]


def canonical_defaults_for(mind: ProcessorMind, path: str | None = None) -> dict[str, Any]:
    contract = get_processor_contract(mind, path)
    is_conscious, translated_by_racio = _MIND_FLAGS[mind]
    accepting_expression = str(contract.get("accepting_expression", ""))
    non_accepting_distortion = str(contract.get("non_accepting_distortion", ""))
    return {
        "mind": mind,
        "is_conscious": is_conscious,
        "translated_by_racio": translated_by_racio,
        "processing_mode": _PROCESSING_MODES[mind],
        "native_language": list(contract.get("native_language", [])),
        "world_filter": str(contract.get("world_filter", "")),
        "primary_motive": str(contract.get("primary_motive", "")),
        "truth_model": str(contract.get("truth_model", "")),
        "defense_mode": str(contract.get("defense_mode", "")),
        "justice_model": str(contract.get("justice_model", "")),
        "accepting_expression": accepting_expression,
        "accepted_expression": accepting_expression,
        "non_accepting_distortion": non_accepting_distortion,
        "non_accepted_expression": non_accepting_distortion,
        "resistance_to_other_minds": str(contract.get("resistance_to_other_minds", "")),
        "what_this_mind_needs": str(contract.get("what_this_mind_needs", "")),
        "risk_if_ignored": str(contract.get("risk_if_ignored", "")),
        "risk_if_dominant": str(contract.get("risk_if_dominant", "")),
        "blind_spot": str(contract.get("blind_spot", "")),
        "source_refs": list(contract.get("source_refs", [])),
        "safety_flags": [],
    }


def ego_required_keys(path: str | None = None) -> list[str]:
    pack = load_contract_pack(path)
    ego = pack.get("ego_resultant_contract")
    if not isinstance(ego, dict):
        raise ContractError("REI contract pack missing ego_resultant_contract.")
    keys = ego.get("required_keys")
    if not isinstance(keys, list) or not all(isinstance(item, str) for item in keys):
        raise ContractError("ego_resultant_contract.required_keys must be list[str].")
    return list(keys)


def _default_shape_value(key: str) -> Any:
    if key in {
        "native_language",
        "known_facts",
        "unknowns",
        "logical_options",
        "source_refs",
        "safety_flags",
        "profile_leader_minds",
    }:
        return []
    if key in {"hidden_signal_sources", "influence_weights", "task_delegation"}:
        return {}
    if key in {"is_conscious", "translated_by_racio"}:
        return False
    if key == "confidence":
        return 0.0
    return ""


def _json_shape(keys: list[str]) -> str:
    return json.dumps({key: _default_shape_value(key) for key in keys}, ensure_ascii=False, indent=2)


def _processor_json_shape(mind: ProcessorMind, keys: list[str]) -> str:
    shape = {key: _default_shape_value(key) for key in keys}
    is_conscious, translated_by_racio = _MIND_FLAGS[mind]
    shape.update(
        {
            "mind": mind,
            "is_conscious": is_conscious,
            "translated_by_racio": translated_by_racio,
            "processing_mode": _PROCESSING_MODES[mind],
        }
    )
    return json.dumps(shape, ensure_ascii=False, indent=2)


def build_processor_prompt(mind: ProcessorMind, mode: PromptMode = "compact", path: str | None = None) -> str:
    contract = get_processor_contract(mind, path)
    keys = required_keys_for(mind, path) if mode == "full" else runtime_required_keys_for(mind, path)
    is_conscious, translated_by_racio = _MIND_FLAGS[mind]

    global_rules = load_contract_pack(path).get("global_rules", [])
    global_rules_text = "\n".join(f"- {rule}" for rule in global_rules)

    if mind == "racio":
        hard_flags = "Use mind='racio', is_conscious=true, translated_by_racio=false."
        translation_rule = "Racio may speak in explicit words, but it must not claim objective truth."
    elif mind == "emocio":
        hard_flags = "Use mind='emocio', is_conscious=false, translated_by_racio=true."
        translation_rule = "Do not write as a literal conscious inner speaker; write Racio's concise translation of an image/social/desire signal."
    else:
        hard_flags = "Use mind='instinkt', is_conscious=false, translated_by_racio=true."
        translation_rule = "Do not write as a literal conscious inner speaker; write Racio's concise translation of a protective/body/fear/loss signal."

    body = [
        "Return exactly one JSON object. No markdown. No commentary. No hidden chain-of-thought.",
        "",
        "Global rules:",
        global_rules_text,
        "",
        f"You simulate only {contract['display_name']} in a REI-inspired architecture.",
        contract["canonical_summary"],
        "",
        f"Conscious access: {str(is_conscious).lower()}",
        f"Translated by Racio: {str(translated_by_racio).lower()}",
        translation_rule,
        hard_flags,
        "",
        "Input gate - accept:",
        ", ".join(contract["input_gate"]["accept"]),
        "Input gate - reject or translate:",
        ", ".join(contract["input_gate"]["reject_or_translate"]),
        "",
        "Processing loop:",
        "\n".join(f"- {item}" for item in contract["processing_loop"]),
        "",
        "Processor isolation rules:",
        "\n".join(f"- {item}" for item in contract.get("processor_isolation_rules", [])),
        "",
        "Style rules:",
        "\n".join(f"- {item}" for item in contract["style_rules"]),
        "",
        "Prohibited modes:",
        "\n".join(f"- {item}" for item in contract["prohibited_modes"]),
        "",
        "Required JSON keys, all must be present:",
        ", ".join(keys),
        "",
        "Required JSON shape, fill every key:",
        _processor_json_shape(mind, keys),
    ]
    output_constraints = contract.get("processor_output_constraints", [])
    if output_constraints:
        body.extend(
            [
                "",
                "Final output constraints:",
                "\n".join(f"- {item}" for item in output_constraints),
            ]
        )

    if mode == "full":
        body.extend(
            [
                "",
                "Canonical metadata:",
                f"- Native language: {', '.join(contract['native_language'])}",
                f"- World filter: {contract['world_filter']}",
                f"- Primary motive: {contract['primary_motive']}",
                f"- Truth model: {contract['truth_model']}",
                f"- Defense mode: {contract['defense_mode']}",
                f"- Justice model: {contract['justice_model']}",
            ]
        )
        body.extend(
            [
                "",
                "Canonical acceptance/non-acceptance:",
                f"- Accepting expression: {contract['accepting_expression']}",
                f"- Non-accepting distortion: {contract['non_accepting_distortion']}",
                f"- Resistance to other minds: {contract['resistance_to_other_minds']}",
                f"- Blind spot: {contract['blind_spot']}",
                "",
                "Source reference IDs to include in source_refs:",
                ", ".join(contract.get("source_refs", [])),
            ]
        )

    return "\n".join(body)


def build_ego_prompt(path: str | None = None) -> str:
    pack = load_contract_pack(path)
    ego = pack["ego_resultant_contract"]
    global_rules_text = "\n".join(f"- {rule}" for rule in pack.get("global_rules", []))
    forbidden_text = "\n".join(f"- {item}" for item in ego.get("forbidden_claims", []))
    keys = ", ".join(ego_required_keys(path))

    return "\n".join(
        [
            "Return exactly one JSON object. No markdown. No commentary. No hidden chain-of-thought.",
            "",
            "Global rules:",
            global_rules_text,
            "",
            "You are EgoResultant in a REI-inspired architecture.",
            ego["definition"],
            "",
            "Forbidden claims:",
            forbidden_text,
            "",
            "Task:",
            "- Build the perceived world/story/action-pressure from Racio, Emocio, and Instinkt signals.",
            "- Do not average mechanically.",
            "- Separate profile leader, situational driver, and resultant leader under pressure.",
            "- For R=E=I, never default to Racio merely because Racio is verbal; use two-of-three arbitration or mark mixed/unknown.",
            "- Name conscious_story and racio_after_story separately from hidden_signal_sources.",
            "",
            "Required JSON keys, all must be present:",
            keys,
            "",
            "Required JSON shape, fill every key:",
            _json_shape(ego_required_keys(path)),
        ]
    )
