"""Sanitize E/I manifestations before any Racio interpretation step."""

from __future__ import annotations

from ..models.communication import (
    AcceptanceState,
    EmocioManifestation,
    InstinktManifestation,
    ObservableManifestationView,
    RacioInterpreterRequest,
)
from ..models.common import NonEmptyId


def build_observable_manifestation_view(
    manifestation: EmocioManifestation | InstinktManifestation,
) -> ObservableManifestationView:
    """Project only allowlisted manifestation fields; native objects are not accepted."""

    return ObservableManifestationView.create(manifestation)


def build_racio_interpreter_request(
    *,
    manifestations: tuple[EmocioManifestation | InstinktManifestation, ...],
    allowed_option_ids: tuple[NonEmptyId, ...],
    acceptance_state: AcceptanceState,
) -> RacioInterpreterRequest:
    """Select only the relevant explicit R→E or R→I relation."""

    if not manifestations:
        raise ValueError("Racio interpreter request requires manifestations")
    canonical_manifestations = tuple(
        sorted(manifestations, key=lambda item: item.manifestation_id)
    )
    request = RacioInterpreterRequest.create(
        views=tuple(
            build_observable_manifestation_view(manifestation)
            for manifestation in canonical_manifestations
        ),
        allowed_option_ids=allowed_option_ids,
        acceptance_state=acceptance_state,
    )
    return request.validate_against(
        manifestations=canonical_manifestations,
        acceptance_state=acceptance_state,
    )


__all__ = [
    "build_observable_manifestation_view",
    "build_racio_interpreter_request",
]
