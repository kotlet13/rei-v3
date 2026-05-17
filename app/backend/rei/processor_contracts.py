from __future__ import annotations

from typing import Literal

from .contract_loader import build_processor_prompt, required_keys_for


ProcessorMind = Literal["racio", "emocio", "instinkt"]

PROCESSOR_MINIMAL_REQUIRED_KEYS: dict[ProcessorMind, list[str]] = {
    "racio": required_keys_for("racio"),
    "emocio": required_keys_for("emocio"),
    "instinkt": required_keys_for("instinkt"),
}


def processor_prompt(mind: ProcessorMind, mode: str = "compact") -> str:
    return build_processor_prompt(mind, mode="full" if mode == "full" else "compact")


def repair_prompt(mind: ProcessorMind) -> str:
    keys = ", ".join(PROCESSOR_MINIMAL_REQUIRED_KEYS[mind])
    if mind == "racio":
        flags = "is_conscious=true and translated_by_racio=false"
    else:
        flags = "is_conscious=false and translated_by_racio=true"
    return (
        "Your previous output was invalid. Return only one JSON object with every required key present: "
        f"{keys}. Do not add markdown. Do not add commentary. Use short values. "
        f"Use mind='{mind}' and set {flags}."
    )
