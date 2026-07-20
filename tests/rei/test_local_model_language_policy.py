from __future__ import annotations

import pytest

from app.backend.rei.providers.language_policy import (
    ENGLISH_LOCAL_MODEL_LANGUAGE,
    ENGLISH_PRESENTATION_MODE,
    LOCAL_MODEL_LANGUAGE_POLICY_ID,
    LocalModelLanguagePolicyError,
    require_english_local_model_payload,
)


def test_policy_identity_and_explicit_english_constants_are_stable() -> None:
    assert LOCAL_MODEL_LANGUAGE_POLICY_ID == "rei-local-model-english-only-v1"
    assert ENGLISH_LOCAL_MODEL_LANGUAGE == "en"
    assert ENGLISH_PRESENTATION_MODE == "operational_en_only"


@pytest.mark.parametrize(
    "provider_payload",
    (
        {
            "language": "en",
            "prompt": (
                "Explain the reviewed source faithfully; a quoted term such as "
                "Sloven\u0161\u010dina or \u017ealost is opaque content, not language metadata."
            ),
        },
        {
            "messages": [
                {"role": "system", "content": "Return one bounded JSON object."},
                {"role": "user", "content": "Analyse the visible evidence."},
            ],
            "metadata": {
                "request_language": "en",
                "response_language": "en",
                "presentation_mode": "operational_en_only",
            },
        },
        {
            "prompt": "Preserve the reference image and edit only the requested action.",
            "negative_prompt": "Do not add people or text.",
            "render": {"prompt_language": "en", "width": 1024, "height": 1024},
        },
    ),
)
def test_explicit_english_text_chat_and_image_payloads_are_accepted(
    provider_payload: object,
) -> None:
    assert (
        require_english_local_model_payload(
            declared_language="en",
            provider_payload=provider_payload,
        )
        is None
    )


@pytest.mark.parametrize(
    ("declared_language", "expected_code"),
    (
        (None, "language_not_declared"),
        ("sl", "non_english_language"),
        ("EN", "non_english_language"),
        ("english", "non_english_language"),
    ),
)
def test_language_declaration_is_required_and_exact(
    declared_language: object,
    expected_code: str,
) -> None:
    with pytest.raises(LocalModelLanguagePolicyError) as caught:
        require_english_local_model_payload(
            declared_language=declared_language,
            provider_payload={"prompt": "Opaque provider text."},
        )

    assert caught.value.failure_code == expected_code


@pytest.mark.parametrize("forbidden_key", ("canonical_sl", "notes_sl", "prompt_sl"))
def test_non_english_provider_fields_are_rejected_recursively(
    forbidden_key: str,
) -> None:
    payload = {
        "messages": [
            {
                "role": "user",
                "content": {
                    "safe": "English declaration remains explicit.",
                    forbidden_key: "PRIVATE_SENTINEL_DO_NOT_ECHO",
                },
            }
        ]
    }

    with pytest.raises(LocalModelLanguagePolicyError) as caught:
        require_english_local_model_payload(
            declared_language="en",
            provider_payload=payload,
        )

    assert caught.value.failure_code == "non_english_field"
    assert caught.value.summary == str(caught.value)
    assert "PRIVATE_SENTINEL_DO_NOT_ECHO" not in str(caught.value)


@pytest.mark.parametrize(
    "payload",
    (
        {"prompt_language": "sl", "prompt": "Text"},
        {"metadata": {"output_language": None}},
        {"metadata": {"language": "en", "response_language": "sl"}},
    ),
)
def test_mixed_or_missing_nested_language_metadata_fails_closed(
    payload: object,
) -> None:
    with pytest.raises(
        LocalModelLanguagePolicyError,
        match="only explicit English language metadata",
    ) as caught:
        require_english_local_model_payload(
            declared_language="en",
            provider_payload=payload,
        )

    assert caught.value.failure_code == "non_english_language"


@pytest.mark.parametrize(
    "presentation_mode",
    (
        "canonical_sl_only",
        "canonical_sl_plus_operational_en",
        "en",
        None,
    ),
)
def test_non_english_or_implicit_presentation_mode_fails_closed(
    presentation_mode: object,
) -> None:
    with pytest.raises(LocalModelLanguagePolicyError) as caught:
        require_english_local_model_payload(
            declared_language="en",
            provider_payload={
                "metadata": {"presentation_mode": presentation_mode},
                "prompt": "Opaque provider text.",
            },
        )

    assert caught.value.failure_code == "non_english_presentation"


def test_policy_does_not_guess_language_from_text_or_string_values() -> None:
    payload = {
        "prompt": "Sloven\u0161\u010dina, \u010dustvo, Racio, canonical_sl, prompt_sl.",
        "messages": ["Arbitrary UTF-8 remains opaque: \u017e\u0161\u010d\u0107\u0111."],
        "unrelated_mode": "canonical_sl_plus_operational_en",
    }

    assert (
        require_english_local_model_payload(
            declared_language="en",
            provider_payload=payload,
        )
        is None
    )


def test_active_provider_surface_does_not_advertise_frozen_ollama_wrappers() -> None:
    from app.backend.rei import providers

    assert "OllamaRacioNativeEnProvider" in providers.__all__
    assert "OllamaStructuredRacioInterpreterEnProvider" in providers.__all__
    assert "build_ollama_racio_native_en_providers" in providers.__all__
    assert "OllamaRacioNativeProvider" not in providers.__all__
    assert "OllamaStructuredRacioInterpreterProvider" not in providers.__all__
    assert "build_ollama_racio_native_providers" not in providers.__all__
