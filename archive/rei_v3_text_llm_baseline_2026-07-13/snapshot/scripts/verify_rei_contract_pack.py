from __future__ import annotations

from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "knowledge" / "canon" / "processor_contracts.json"


def main() -> int:
    data = json.loads(CONTRACTS.read_text(encoding="utf-8"))
    processors = data.get("processors", {})
    errors: list[str] = []

    expected_flags = {
        "racio": (True, False),
        "emocio": (False, True),
        "instinkt": (False, True),
    }

    for mind, (is_conscious, translated) in expected_flags.items():
        contract = processors.get(mind)
        if not contract:
            errors.append(f"missing processor {mind}")
            continue
        if contract.get("conscious_access") is not is_conscious:
            errors.append(f"{mind}: wrong conscious_access")
        if contract.get("translated_by_racio") is not translated:
            errors.append(f"{mind}: wrong translated_by_racio")
        keys = contract.get("output_contract", {}).get("required_keys", [])
        for key in ("mind", "is_conscious", "translated_by_racio", "source_refs", "confidence", "uncertainty"):
            if key not in keys:
                errors.append(f"{mind}: missing required key {key}")

    ego_keys = data.get("ego_resultant_contract", {}).get("required_keys", [])
    for key in ("perceived_world", "conscious_story", "hidden_signal_sources", "racio_after_story"):
        if key not in ego_keys:
            errors.append(f"ego: missing required key {key}")

    if errors:
        print("REI contract verification failed:")
        for error in errors:
            print(f" - {error}")
        return 1

    print("REI contract verification OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
