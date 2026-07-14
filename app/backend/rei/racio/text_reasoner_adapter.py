"""Adapter from the provider-neutral TextReasoner protocol to native Racio."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from ..ids import canonical_json_bytes, content_id, sha256_hex
from ..models.common import LanguageCode
from ..models.provider import ProviderCallSpec, ensure_call_contract
from ..models.racio import RacioInputPacket, RacioNativeConclusion
from ..providers.protocols import TextReasoner, TextReasoningRequest
from .contracts import RacioStructuredOutput


RACIO_STRUCTURED_INSTRUCTION = """Return exactly one JSON object with these fields:
option_id (string or null), facts_used (string array), evidence_ids_used (string
array),
unknowns (string array), causal_sequence (string array), utility_structure (string
array),
explicit_goal (string), main_objection (string), confidence (number 0..1), abstains
(boolean), uncertainty (string). Use only facts, unknowns, evidence IDs and option IDs
present in the packet. Every array must contain unique values. In facts_used, copy
only exact strings from explicit_facts or world.facts. In unknowns, copy only exact
strings from explicit_unknowns. Write causal_sequence as new descriptions of reasoning
steps: never copy a fact or unknown string verbatim into causal_sequence, and keep the
three fields mutually disjoint. Do not interpret Emocio or Instinkt, decide governance,
commit behavior, or infer character authority. Return raw JSON without markdown fences
or additional keys."""


def _unique_artifact_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


@dataclass(frozen=True, slots=True)
class TextReasonerRacioAdapter:
    """Strict structured-output adapter; provider execution remains external."""

    reasoner: TextReasoner

    @property
    def adapter_id(self) -> str:
        return f"text-reasoner-racio:{self.reasoner.identity.provider_id}"

    def build_request(
        self,
        packet: RacioInputPacket,
        *,
        language: LanguageCode | None = None,
    ) -> TextReasoningRequest:
        request_language = language or packet.language
        if request_language is None:
            raise ValueError(
                "Legacy Racio packets without language require an explicit language"
            )
        request_id = content_id(
            "racio_request",
            {
                "adapter_revision": "rei-native-racio-text-adapter-v1",
                "packet_id": packet.packet_id,
                "packet_hash": packet.content_hash(),
                "instruction_hash": sha256_hex(RACIO_STRUCTURED_INSTRUCTION),
                "language": request_language,
            },
        )
        return TextReasoningRequest(
            request_id=request_id,
            instruction=RACIO_STRUCTURED_INSTRUCTION,
            input_text=canonical_json_bytes(packet).decode("utf-8"),
            language=request_language,
            evidence_ids=packet.evidence_ids,
        )

    def required_input_artifact_ids(
        self,
        packet: RacioInputPacket,
    ) -> tuple[str, ...]:
        return _unique_artifact_ids(
            (
                packet.packet_id,
                packet.world.world_id,
                *packet.evidence_ids,
                *packet.previous_racio_projection_ids,
            )
        )

    def process(
        self,
        packet: RacioInputPacket,
        *,
        call: ProviderCallSpec,
        language: LanguageCode | None = None,
    ) -> RacioNativeConclusion:
        request = self.build_request(packet, language=language)
        ensure_call_contract(
            self.reasoner.identity,
            call,
            request_id=request.request_id,
            expected_kind="text_reasoner",
            required_input_artifact_ids=self.required_input_artifact_ids(packet),
        )
        result = self.reasoner.reason(request, call=call)
        if result.request_id != request.request_id or result.call_spec != call:
            raise ValueError("TextReasoner result does not close the adapter request")
        try:
            output = RacioStructuredOutput.model_validate_json(result.text)
        except (ValidationError, ValueError) as exc:
            raise ValueError(
                "TextReasoner returned invalid structured Racio output"
            ) from exc
        output.validate_against(
            packet,
            supporting_evidence_ids=result.supporting_evidence_ids,
        )
        return output.to_conclusion(
            packet,
            reasoning_provider_result_id=result.result_id,
            reasoning_provider_result_hash=result.content_hash(),
        )


__all__ = ["RACIO_STRUCTURED_INSTRUCTION", "TextReasonerRacioAdapter"]
