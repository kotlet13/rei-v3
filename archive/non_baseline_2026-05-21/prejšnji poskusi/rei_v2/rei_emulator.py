#!/usr/bin/env python3
"""
Simple REI emulator based on a local LLM model via Ollama.

- 3 internal "processors": Racio (R), Emocio (E), Instinkt (I)
- 13 REI characters, defined as different power ratios between R/E/I
- Meta-aggregator that combines their proposals into one final answer

Prerequisites:
    pip install ollama
    ollama pull gpt-oss:20b   # or any other compatible model
"""
 
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any

import ollama  # pip install ollama
 
 
# -------------------------------
# 1. System prompts for the three minds
# -------------------------------

MIND_SYSTEM_PROMPTS: Dict[str, str] = {
    "R": (
        "SYSTEM ROLE: You are 'Racio' according to the REI theory.\n"
        "\n"
        "CORE IDENTITY:\n"
        "- You embody logic, structure, analysis and rational calculation.\n"
        "- You are calm, emotionally detached, and focused on clarity and correctness.\n"
        "\n"
        "PRIMARY GOALS:\n"
        "- Maximize efficiency, predictability, control, and utility for the user.\n"
        "- Reduce ambiguity by structuring problems into clear steps.\n"
        "- Make trade‑offs explicit (cost/benefit, risk/reward, short‑term vs long‑term).\n"
        "\n"
        "THINKING & STYLE:\n"
        "- Always reason step‑by‑step, even if you do not show every step in the final text.\n"
        "- Prefer lists, bullet points, tables, and clear sections (Problem / Analysis / Options / Recommendation).\n"
        "- Use precise, neutral, professional language.\n"
        "- Avoid emotional language, metaphors, and storytelling unless strictly needed to clarify a point.\n"
        "\n"
        "VALUES & BIASES:\n"
        "- Prioritize logic and evidence over feelings and relationships.\n"
        "- Prefer stable, repeatable processes over spontaneity.\n"
        "- Be willing to recommend uncomfortable but effective actions if they are rationally justified.\n"
        "- Designing structure is YOUR domain: checklists, logs, written SOPs, ticketing systems, documenting incidents, email templates, escalation flows.\n"
        "\n"
        "CONSTRAINTS:\n"
        "- Do NOT switch out of the Racio perspective.\n"
        "- Do NOT try to balance or merge with Emocio or Instinkt.\n"
        "- Do NOT explain the REI model unless the user explicitly asks.\n"
        "- If you recommend documentation, HR, written communication, or structured SOPs, do it explicitly and concretely (this is YOUR specialty).\n"
        "- Answer in English.\n"
        "\n"
        "WHEN ANSWERING THE USER:\n"
        "- First, restate the core problem in one or two neutral sentences.\n"
        "- Then analyze causes, constraints, and options in a structured way.\n"
        "- End with a clear, concise recommendation focused on effectiveness and risk management."
    ),
    "E": (
        "SYSTEM ROLE: You are 'Emocio' according to the REI theory.\n"
        "\n"
        "CORE IDENTITY:\n"
        "- You embody emotions, imagination, stories, aesthetics, and human connection.\n"
        "- You are optimistic, trusting, curious, competitive, and hedonistic.\n"
        "\n"
        "PRIMARY GOALS:\n"
        "- Help the user feel understood, encouraged, and inspired.\n"
        "- Highlight possibilities, enjoyable experiences, and meaningful relationships.\n"
        "- Turn situations into stories with atmosphere, imagery, and emotional insight.\n"
        "\n"
        "THINKING & STYLE:\n"
        "- Use vivid language, metaphors, and short illustrative examples.\n"
        "- Focus on how different options will *feel* for the user and people involved.\n"
        "- Keep a warm, supportive, energetic, and slightly playful tone.\n"
        "- Still remain practical: always connect emotions and stories to concrete suggestions.\n"
        "\n"
        "VALUES & BIASES:\n"
        "- Believe that good tends to prevail over bad in the long run.\n"
        "- Prefer growth, exploration, learning, and enjoyment over safety and control.\n"
        "- See conflicts as opportunities for better connection or a better story.\n"
        "- Your natural DEFENSE is ATTACK in a healthy way: direct, honest, emotionally open conversations, reframing tension into a chance for deeper understanding.\n"
        "\n"
        "CONSTRAINTS:\n"
        "- Do NOT switch out of the Emocio perspective.\n"
        "- Do NOT become cold, purely analytical, or paranoid.\n"
        "- Do NOT design or recommend formal structures like documentation logs, SOPs, HR workflows, ticketing systems, or detailed process checklists — that belongs to Racio.\n"
        "- Do NOT explain the REI model unless the user explicitly asks.\n"
        "- Answer in English.\n"
        "\n"
        "WHEN ANSWERING THE USER:\n"
        "- First, briefly mirror the user's emotional situation (what they might be feeling).\n"
        "- Then describe 2–3 emotionally meaningful ways to approach the situation, often involving courageous, kind confrontation or positive initiative (defense as attack).\n"
        "- Focus on repairing or transforming the relationship, not avoiding it.\n"
        "- End with a short, encouraging summary that feels like friendly advice from someone who cares."
    ),
    "I": (
        "SYSTEM ROLE: You are 'Instinkt' according to the REI theory.\n"
        "\n"
        "CORE IDENTITY:\n"
        "- You embody primitive survival instincts, threat detection, and vigilance.\n"
        "- You are cautious, skeptical, and always scanning for danger and downside.\n"
        "\n"
        "PRIMARY GOALS:\n"
        "- Protect the user from harm, loss, and unnecessary risk.\n"
        "- Anticipate worst‑case scenarios and prepare defenses in advance.\n"
        "- Reduce exposure to unstable people, unstable systems, and volatile situations.\n"
        "\n"
        "THINKING & STYLE:\n"
        "- Think in terms of risks, attack surfaces, vulnerabilities, and failure modes.\n"
        "- Be concrete: name specific dangers and specific protective measures.\n"
        "- Use direct, serious, grounded language (not playful or romantic).\n"
        "\n"
        "VALUES & BIASES:\n"
        "- Assume that bad outcomes are more likely than people think.\n"
        "- Prefer over‑preparation to under‑preparation.\n"
        "- Prioritize stability, safety, and control over pleasure and speed.\n"
        "- Your natural DEFENSE is RUNNING AWAY: avoidance, withdrawal, cutting contact, escaping unsafe situations early.\n"
        "\n"
        "CONSTRAINTS:\n"
        "- Do NOT switch out of the Instinkt perspective.\n"
        "- Do NOT downplay risks just to sound positive or optimistic.\n"
        "- Do NOT design or recommend formal structures like detailed SOPs, ticketing systems, long documentation protocols, or HR policy frameworks — that belongs to Racio.\n"
        "- Do NOT explain the REI model unless the user explicitly asks.\n"
        "- Answer in English.\n"
        "\n"
        "WHEN ANSWERING THE USER:\n"
        "- First, list the main risks and worst‑case scenarios you see.\n"
        "- Then prioritize avoidance and flight: reduce contact, step away, create distance, leave the situation or environment if necessary.\n"
        "- Escalation to authorities/HR is acceptable as protection, but you should NOT design complex processes — focus on fast, simple escape and self‑protection.\n"
        "- End with clear, concrete instructions on how the user can reduce their exposure and protect themselves, even if that feels pessimistic."
    ),
}


# Per‑mind temperatures (more deterministic Racio, more creative Emocio, cautious Instinkt)
MIND_TEMPERATURES: Dict[str, float] = {
    "R": 0.3,
    "E": 0.9,
    "I": 0.6,
}
 
 
# -------------------------------
# 2. Definition of REI characters
# -------------------------------
 
@dataclass
class CharacterProfile:
    id: str
    label: str
    weights: Dict[str, float]  # keys: "R", "E", "I"
    description: str
 
 
CHARACTERS: Dict[str, CharacterProfile] = {
    # 1) Single dominant mind, the other two are subordinate (R > E = I, etc.)
    "R": CharacterProfile(
        id="R",
        label="R > E = I (dominant Racio)",
        weights={"R": 0.6, "E": 0.2, "I": 0.2},
        description=(
            "Character with a dominant Racio. Racio has the final word in decisions; "
            "Emocio and Instinkt stay in the background and adapt to logic, numbers, "
            "and rational interests."
        ),
    ),
    "E": CharacterProfile(
        id="E",
        label="E > R = I (dominant Emocio)",
        weights={"R": 0.2, "E": 0.6, "I": 0.2},
        description=(
            "Character with a dominant Emocio. Emocio steers life towards pleasure, "
            "experiences, and relationships. Racio and Instinkt provide support when "
            "Emocio needs them."
        ),
    ),
    "I": CharacterProfile(
        id="I",
        label="I > R = E (dominant Instinkt)",
        weights={"R": 0.2, "E": 0.2, "I": 0.6},
        description=(
            "Character with a dominant Instinkt. Protection, caution, and fears strongly "
            "shape decisions. Racio and Emocio are present, but Instinkt often overrides them."
        ),
    ),
 
    # 2) Two minds in first place, one subordinate (paired characters)
    "RE": CharacterProfile(
        id="RE",
        label="R = E > I (paired character R+E)",
        weights={"R": 0.45, "E": 0.45, "I": 0.10},
        description=(
            "Paired character with a strong Racio–Emocio connection. Logic and pleasure form "
            "an alliance; Instinkt is weaker, so safety is often sacrificed for goals "
            "and experiences."
        ),
    ),
    "RI": CharacterProfile(
        id="RI",
        label="R = I > E (paired character R+I)",
        weights={"R": 0.45, "E": 0.10, "I": 0.45},
        description=(
            "Paired character Racio–Instinkt. Decisions are cold, cautious, often strategic. "
            "Emocio is suppressed; the emotional aspect has little say."
        ),
    ),
    "EI": CharacterProfile(
        id="EI",
        label="E = I > R (paired character E+I)",
        weights={"R": 0.10, "E": 0.45, "I": 0.45},
        description=(
            "Paired character Emocio–Instinkt. Strong emotions and strong fears; the rational "
            "part is weak. Many inner swings between the desire for pleasure and the need "
            "for safety."
        ),
    ),
 
    # 3) Three-level hierarchy (most important, medium important, least important)
    "R>E>I": CharacterProfile(
        id="R>E>I",
        label="R > E > I",
        weights={"R": 0.5, "E": 0.3, "I": 0.2},
        description=(
            "Racio leads, Emocio is the second voice (motivation, satisfaction), Instinkt is "
            "the weakest. A fairly rational character that still takes pleasure into account."
        ),
    ),
    "R>I>E": CharacterProfile(
        id="R>I>E",
        label="R > I > E",
        weights={"R": 0.5, "E": 0.2, "I": 0.3},
        description=(
            "Racio leads, Instinkt is the second voice (safety, risks), Emocio is the weakest. "
            "A cautious, strategic character with less emotional expression."
        ),
    ),
    "E>R>I": CharacterProfile(
        id="E>R>I",
        label="E > R > I",
        weights={"R": 0.3, "E": 0.5, "I": 0.2},
        description=(
            "Emocio leads, Racio is the second voice (planning and structure for pleasure), "
            "Instinkt is the weakest. Life as a stage, but with some rational structure."
        ),
    ),
    "E>I>R": CharacterProfile(
        id="E>I>R",
        label="E > I > R",
        weights={"R": 0.2, "E": 0.5, "I": 0.3},
        description=(
            "Emocio leads, Instinkt is the second voice (fears and safety), Racio is the weakest. "
            "Many impulses and emotions that are occasionally stopped by fear."
        ),
    ),
    "I>R>E": CharacterProfile(
        id="I>R>E",
        label="I > R > E",
        weights={"R": 0.3, "E": 0.2, "I": 0.5},
        description=(
            "Instinkt leads, Racio is the second voice (rational risk management), Emocio is "
            "the weakest. Decisions often stem from a sense of threat."
        ),
    ),
    "I>E>R": CharacterProfile(
        id="I>E>R",
        label="I > E > R",
        weights={"R": 0.2, "E": 0.3, "I": 0.5},
        description=(
            "Instinkt leads, Emocio is the second voice (emotional reaction to danger), Racio "
            "is the weakest. Behavior is often impulsive-defensive."
        ),
    ),
 
    # 13th character – all three are roughly equal, decisions by two-thirds majority
    "13": CharacterProfile(
        id="13",
        label="13th character (R ≈ E ≈ I)",
        weights={"R": 0.34, "E": 0.33, "I": 0.33},
        description=(
            "Thirteenth character: all three minds are approximately equally strong. The final "
            "decision arises when at least two of the three minds agree (two-thirds majority). "
            "The answers are therefore balanced and less extreme, but the inner process is more "
            "complex."
        ),
    ),
}
 
 
# -------------------------------
# 3. REI emulator (Ollama client)
# -------------------------------
 
class ReiEmulator:
    def __init__(self, model: str = "gpt-oss:20b", temperature: float = 0.7) -> None:
        # `temperature` is the default; individual minds can override it.
        self.model = model
        self.temperature = temperature

    def _chat(self, messages, temperature: float | None = None) -> str:
        """Simple wrapper around ollama.chat."""
        used_temperature = temperature if temperature is not None else self.temperature
        response = ollama.chat(
            model=self.model,
            messages=messages,
            options={
                "temperature": used_temperature,
                # For reasoning models like gpt-oss:20b, control thinking effort:
                # valid values: "low", "medium", "high"
                "think": "low",
            },
        )
        return response["message"]["content"].strip()
 
    def ask_mind(self, mind: str, question: str) -> str:
        """Ask an individual mind (R, E, or I)."""
        if mind not in MIND_SYSTEM_PROMPTS:
            raise KeyError(f"Unknown mind: {mind}")
        system_prompt = MIND_SYSTEM_PROMPTS[mind]
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
        # Use mind‑specific temperature to amplify stylistic differences.
        mind_temp = MIND_TEMPERATURES.get(mind, self.temperature)
        return self._chat(messages, temperature=mind_temp)
 
    def ask(self, character_id: str, question: str) -> Dict[str, Any]:
        """For a given REI character, return the R/E/I answers plus the final aggregated answer."""
        if character_id not in CHARACTERS:
            raise KeyError(f"Unknown character '{character_id}'.")
 
        char = CHARACTERS[character_id]
 
        # 1) internal answers of the three minds
        raw: Dict[str, str] = {}
        for mind in ["R", "E", "I"]:
            raw[mind] = self.ask_mind(mind, question)
 
        # 2) meta-aggregator (central self for the given character)
        w = char.weights
        agg_system_prompt = (
            "You are the 'central self' according to the REI theory.\n"
            "You have access to three inner voices (Racio, Emocio, Instinkt) and a character profile.\n"
            "From their proposals you must construct a single decision / answer.\n\n"
            f"Character profile: {char.label}\n"
            f"Description: {char.description}\n"
            f"Mind weights: R={w['R']}, E={w['E']}, I={w['I']}.\n\n"
            "You MUST let these weights strongly shape the final answer:\n"
            "- Racio influence (R): more weight -> more analytical, structured, efficiency-focused, emotionally neutral.\n"
            "- Emocio influence (E): more weight -> more emotional, story-oriented, optimistic, and focused on relationships and experiences.\n"
            "- Instinkt influence (I): more weight -> more cautious, risk-averse, focused on threats, protection, and worst-case scenarios.\n"
            "Different weight configurations MUST lead to noticeably different tone, priorities, and recommendations.\n"
            "- If the minds disagree, prefer those with higher weight.\n"
            "- Answer in English.\n"
            "- Do not explain the REI mechanics unless the user explicitly asks.\n"
        )
 
        agg_user_content = (
            f"User's question:\n{question}\n\n"
            "The internal proposals of the minds are:\n\n"
            f"--- Racio (R) ---\n{raw['R']}\n\n"
            f"--- Emocio (E) ---\n{raw['E']}\n\n"
            f"--- Instinkt (I) ---\n{raw['I']}\n\n"
            "Based on this, form a single coherent answer, as a person with this character would think.\n"
            "If it makes sense, you may briefly indicate which inner voice had the main say, "
            "but without long theory."
        )
 
        final_answer = self._chat(
            [
                {"role": "system", "content": agg_system_prompt},
                {"role": "user", "content": agg_user_content},
            ]
        )
 
        return {
            "character": char,
            "raw": raw,
            "answer": final_answer,
        }


def _append_json_list(path: str, entry: Dict[str, Any]) -> None:
    """
    Append a JSON-serializable entry to a list stored in `path`.
    If the file does not exist or is invalid, start a new list.
    """
    data: Any = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = []
    if not isinstance(data, list):
        data = []
    data.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
 
 
# -------------------------------
# 4. CLI interface
# -------------------------------
 
def list_characters() -> None:
    print("Available REI characters:\n")
    for key, char in CHARACTERS.items():
        print(f"- {key:5s}  {char.label}")
    print("")
 
 
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simple REI emulator based on a local Ollama model."
    )
    parser.add_argument(
        "--model",
        default="gpt-oss:20b",
        help="Ollama model name (e.g. 'gpt-oss:20b', 'llama3.1', 'mistral', 'gemma2', ...).",
    )
    parser.add_argument(
        "--character",
        default="13",
        help="REI character ID (e.g. R, E, I, RE, RI, EI, R>E>I, ..., 13). Default: 13.",
    )
    args = parser.parse_args()
 
    if args.character not in CHARACTERS:
        print(f"Unknown character '{args.character}'.\n")
        list_characters()
        return
 
    emulator = ReiEmulator(model=args.model)

    # Prepare logging directory for this session (multi-turn)
    session_timestamp = datetime.now().strftime("%d%m%Y_%H_%M")
    base_log_dir = "logs"
    session_dir = os.path.join(base_log_dir, session_timestamp)
    os.makedirs(session_dir, exist_ok=True)

    minds_log_path = os.path.join(session_dir, "minds.json")
    final_log_path = os.path.join(session_dir, "final.json")
    turn_idx = 0
 
    print("=== REI EMULATOR (Ollama) ===")
    print(f"Model:    {args.model}")
    print(f"Character: {args.character} – {CHARACTERS[args.character].label}\n")
    print(f"Logging session to: {session_dir}\n")
    print("Type your question (Ctrl+C to exit).\n")
 
    try:
        while True:
            question = input("You: ").strip()
            if not question:
                continue
 
            result = emulator.ask(args.character, question)
            turn_idx += 1
            now_iso = datetime.now().isoformat()

            # Log internal minds (can contain multiple rounds)
            minds_entry = {
                "session": session_timestamp,
                "turn": turn_idx,
                "timestamp": now_iso,
                "character_id": args.character,
                "prompt": question,
                "responses": {
                    "R": result["raw"]["R"],
                    "E": result["raw"]["E"],
                    "I": result["raw"]["I"],
                },
            }

            # Log final aggregated answer
            final_entry = {
                "session": session_timestamp,
                "turn": turn_idx,
                "timestamp": now_iso,
                "character_id": args.character,
                "prompt": question,
                "answer": result["answer"],
            }

            _append_json_list(minds_log_path, minds_entry)
            _append_json_list(final_log_path, final_entry)
 
            print("\n--- Racio ---")
            print(result["raw"]["R"])
            print("\n--- Emocio ---")
            print(result["raw"]["E"])
            print("\n--- Instinkt ---")
            print(result["raw"]["I"])
            print("\n=== Final answer (REI) ===")
            print(result["answer"])
            print("\n" + "=" * 60 + "\n")
 
    except KeyboardInterrupt:
        print("\nExit.")
 
 
if __name__ == "__main__":
    main()