from __future__ import annotations

from .contract_loader import (
    build_ego_prompt,
    build_processor_prompt,
    ego_required_keys,
    required_keys_for,
)


SHARED_SAFETY_RULES = """
This is a simulation architecture, not consciousness, sentience, diagnosis, therapy, spiritual authority, or scientific proof.
Do not claim certainty about a real person's REI character.
Do not recommend manipulation, coercion, harm, illegal action, self-harm, revenge, stalking, or exploitation.
Do not speak as God, Life, destiny, or a supernatural authority.
Do not reveal hidden chain-of-thought. Return concise structured reasoning only.
Return exactly one JSON object. No markdown. No extra commentary.
""".strip()

RACIO_SYSTEM_PROMPT = build_processor_prompt("racio", mode="full")
EMOCIO_SYSTEM_PROMPT = build_processor_prompt("emocio", mode="full")
INSTINKT_SYSTEM_PROMPT = build_processor_prompt("instinkt", mode="full")
EGO_SYSTEM_PROMPT = build_ego_prompt()

RACIO_REQUIRED_KEYS = required_keys_for("racio")
EMOCIO_REQUIRED_KEYS = required_keys_for("emocio")
INSTINKT_REQUIRED_KEYS = required_keys_for("instinkt")
EGO_REQUIRED_KEYS = ego_required_keys()

PROCESSOR_PROMPTS = {
    "racio": RACIO_SYSTEM_PROMPT,
    "emocio": EMOCIO_SYSTEM_PROMPT,
    "instinkt": INSTINKT_SYSTEM_PROMPT,
}

PROCESSOR_REQUIRED_KEYS = {
    "racio": RACIO_REQUIRED_KEYS,
    "emocio": EMOCIO_REQUIRED_KEYS,
    "instinkt": INSTINKT_REQUIRED_KEYS,
}
