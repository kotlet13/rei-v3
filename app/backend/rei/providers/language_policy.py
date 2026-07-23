"""Shared fail-closed language gate for active local-model dispatch."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final, Literal


LOCAL_MODEL_LANGUAGE_POLICY_ID: Final = "rei-local-model-english-only-v1"
ENGLISH_LOCAL_MODEL_LANGUAGE: Final = "en"
ENGLISH_PRESENTATION_MODE: Final = "operational_en_only"

LocalModelLanguageFailureCode = Literal[
    "language_not_declared",
    "non_english_language",
    "non_english_field",
    "non_english_presentation",
]

_FAILURE_SUMMARIES: Final[Mapping[LocalModelLanguageFailureCode, str]] = {
    "language_not_declared": (
        "Local-model execution requires an explicit English language declaration."
    ),
    "non_english_language": (
        "Local-model execution accepts only explicit English language metadata."
    ),
    "non_english_field": (
        "The provider-facing payload contains a forbidden source-language field."
    ),
    "non_english_presentation": (
        "The provider-facing payload requires the explicit English presentation mode."
    ),
}
_FORBIDDEN_PROVIDER_KEYS: Final = frozenset(
    {"canonical_sl", "notes_sl", "prompt_sl"}
)
_LANGUAGE_METADATA_KEYS: Final = frozenset(
    {
        "language",
        "input_language",
        "output_language",
        "prompt_language",
        "request_language",
        "response_language",
    }
)
_PRESENTATION_MODE_KEYS: Final = frozenset(
    {"presentation_mode", "text_presentation_mode"}
)


class LocalModelLanguagePolicyError(ValueError):
    """Content-free rejection at the local-model dispatch boundary."""

    def __init__(self, failure_code: LocalModelLanguageFailureCode) -> None:
        self.failure_code = failure_code
        self.summary = _FAILURE_SUMMARIES[failure_code]
        super().__init__(self.summary)


def _reject(failure_code: LocalModelLanguageFailureCode) -> None:
    raise LocalModelLanguagePolicyError(failure_code)


def _validate_provider_structure(value: object) -> None:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = raw_key.casefold() if isinstance(raw_key, str) else None
            if key in _FORBIDDEN_PROVIDER_KEYS:
                _reject("non_english_field")
            if key in _LANGUAGE_METADATA_KEYS and child != ENGLISH_LOCAL_MODEL_LANGUAGE:
                _reject("non_english_language")
            if key in _PRESENTATION_MODE_KEYS and child != ENGLISH_PRESENTATION_MODE:
                _reject("non_english_presentation")
            _validate_provider_structure(child)
        return
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray, memoryview)
    ):
        for child in value:
            _validate_provider_structure(child)


def require_english_local_model_payload(
    *,
    declared_language: object,
    provider_payload: object,
) -> None:
    """Reject dispatch unless metadata and provider structure are English-only."""

    if declared_language is None:
        _reject("language_not_declared")
    if declared_language != ENGLISH_LOCAL_MODEL_LANGUAGE:
        _reject("non_english_language")
    _validate_provider_structure(provider_payload)


__all__ = [
    "ENGLISH_LOCAL_MODEL_LANGUAGE",
    "ENGLISH_PRESENTATION_MODE",
    "LOCAL_MODEL_LANGUAGE_POLICY_ID",
    "LocalModelLanguageFailureCode",
    "LocalModelLanguagePolicyError",
    "require_english_local_model_payload",
]
