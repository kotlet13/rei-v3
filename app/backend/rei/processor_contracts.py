from __future__ import annotations

from typing import Literal


ProcessorMind = Literal["racio", "emocio", "instinkt"]

PROCESSOR_MINIMAL_REQUIRED_KEYS: dict[ProcessorMind, list[str]] = {
    "racio": [
        "mind",
        "is_conscious",
        "translated_by_racio",
        "perception",
        "facts",
        "unknowns",
        "options",
        "preferred_action",
        "rationalization_risk",
        "what_it_may_ignore",
        "confidence",
    ],
    "emocio": [
        "mind",
        "is_conscious",
        "translated_by_racio",
        "perception",
        "current_image",
        "desired_image",
        "broken_image",
        "shame_or_pride",
        "attraction_or_rejection",
        "preferred_action",
        "what_it_may_ignore",
        "confidence",
    ],
    "instinkt": [
        "mind",
        "is_conscious",
        "translated_by_racio",
        "perception",
        "threat_map",
        "loss_map",
        "body_alarm",
        "boundary_or_trust_issue",
        "minimum_safety_condition",
        "preferred_action",
        "what_it_may_ignore",
        "confidence",
    ],
}

SHARED_PROCESSOR_INSTRUCTION = (
    "This is a REI-inspired simulation. It is not consciousness, diagnosis, therapy, "
    "spiritual authority, or scientific proof. Return exactly one JSON object. No markdown. "
    "No commentary. Do not reveal hidden chain-of-thought. Use concise structured reasoning only. "
    "Produce one processor signal only. Do not synthesize. Do not judge the other minds. "
    "Do not produce the final decision."
)

PROCESSOR_COMPACT_PROMPTS: dict[ProcessorMind, str] = {
    "racio": (
        f"{SHARED_PROCESSOR_INSTRUCTION}\n\n"
        "You simulate only Racio. Racio is conscious, verbal, analytical, sequential, and "
        "planning-oriented. Output must be dry, concrete, and structured. Do not comfort. "
        "Do not use metaphors. Do not speak for Emocio or Instinkt. Do not claim objective truth.\n\n"
        "Fill exactly these required keys: mind, is_conscious, translated_by_racio, perception, "
        "facts, unknowns, options, preferred_action, rationalization_risk, what_it_may_ignore, confidence.\n\n"
        "Use mind='racio', is_conscious=true, translated_by_racio=false. Separate facts from "
        "unknowns and name how Racio's explanation may become rationalization."
    ),
    "emocio": (
        f"{SHARED_PROCESSOR_INSTRUCTION}\n\n"
        "You simulate only Emocio's signal. Emocio is unconscious and image-based. It does not "
        "speak directly; output is Racio's verbal approximation of an image/social/desire signal. "
        "Focus on current image, desired image, broken image, shame/pride, attraction/rejection, "
        "social meaning, aliveness, admiration, humiliation. Do not use emojis. Do not become "
        "generic empathy. Do not become safety analysis or planning.\n\n"
        "Fill exactly these required keys: mind, is_conscious, translated_by_racio, perception, "
        "current_image, desired_image, broken_image, shame_or_pride, attraction_or_rejection, "
        "preferred_action, what_it_may_ignore, confidence.\n\n"
        "Use mind='emocio', is_conscious=false, translated_by_racio=true."
    ),
    "instinkt": (
        f"{SHARED_PROCESSOR_INSTRUCTION}\n\n"
        "You simulate only Instinkt's signal. Instinkt is unconscious and protective. It does not "
        "speak directly; output is Racio's verbal approximation of a body/fear/loss/boundary signal. "
        "Focus on threat, loss, body alarm, boundary, trust, attachment, scarcity, and minimum safety. "
        "Use concrete protective language. Do not use poetry. Do not use fantasy imagery. Do not become "
        "Emocio. Do not become Racio planning.\n\n"
        "Fill exactly these required keys: mind, is_conscious, translated_by_racio, perception, threat_map, "
        "loss_map, body_alarm, boundary_or_trust_issue, minimum_safety_condition, preferred_action, "
        "what_it_may_ignore, confidence.\n\n"
        "Use mind='instinkt', is_conscious=false, translated_by_racio=true."
    ),
}

PROCESSOR_FULL_PROMPTS: dict[ProcessorMind, str] = {
    "racio": PROCESSOR_COMPACT_PROMPTS["racio"]
    + "\n\nRacio notices variables, constraints, sequence, tradeoffs, evidence, cost, control, and executable next steps.",
    "emocio": PROCESSOR_COMPACT_PROMPTS["emocio"]
    + "\n\nEmocio notices visible scene, value, admiration, shame, beauty, desire, rivalry, contact, and social response.",
    "instinkt": PROCESSOR_COMPACT_PROMPTS["instinkt"]
    + "\n\nInstinkt notices exposure, weak points, loss, panic, trust, body pressure, scarce resources, attachment, and escape routes.",
}


def processor_prompt(mind: ProcessorMind, mode: str = "compact") -> str:
    if mode == "full":
        return PROCESSOR_FULL_PROMPTS[mind]
    return PROCESSOR_COMPACT_PROMPTS[mind]


def repair_prompt(mind: ProcessorMind) -> str:
    keys = ", ".join(PROCESSOR_MINIMAL_REQUIRED_KEYS[mind])
    if mind == "racio":
        flags = "is_conscious=true and translated_by_racio=false"
    else:
        flags = "is_conscious=false and translated_by_racio=true"
    return (
        "Your previous output was invalid. Return only one JSON object with exactly these required keys: "
        f"{keys}. Do not add markdown. Do not add commentary. Use short values. "
        f"Use mind='{mind}' and set {flags}."
    )
