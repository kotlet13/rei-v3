"""One fail-closed tensor-shape boundary shared by control and target evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from math import prod
from typing import Any, Mapping


class ShapeContractError(ValueError):
    """An LPWM output is missing, ambiguous, or incompatible with B and T."""


@dataclass(frozen=True)
class _Spec:
    flat_rank: int
    shaped_rank: int
    tail: tuple[int | None, ...]


_SPECS = {
    "rec_rgb": _Spec(4, 5, (3, None, None)),
    "bg_rgb": _Spec(4, 5, (3, None, None)),
    "dec_objects": _Spec(4, 5, (3, None, None)),
    "alpha_masks": _Spec(5, 6, (None, 1, None, None)),
    "obj_on": _Spec(3, 4, (None, 1)),
    "mu_tot": _Spec(3, 4, (None, 2)),
}


def _shape(value: Any) -> tuple[int, ...]:
    try:
        shape = tuple(int(x) for x in value.shape)
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise ShapeContractError("tensor has no usable shape") from exc
    if any(x <= 0 for x in shape):
        raise ShapeContractError(f"tensor has non-positive dimension: {shape}")
    return shape


def _numel(value: Any) -> int:
    size = getattr(value, "numel", None)
    if callable(size):
        return int(size())
    size = getattr(value, "size", None)
    if isinstance(size, int):
        return size
    return prod(_shape(value))


def _validate_tail(name: str, tail: tuple[int, ...], spec: _Spec) -> None:
    if len(tail) != len(spec.tail):
        raise ShapeContractError(f"{name}: trailing rank {len(tail)} != {len(spec.tail)}")
    for index, (actual, expected) in enumerate(zip(tail, spec.tail)):
        if expected is not None and actual != expected:
            raise ShapeContractError(
                f"{name}: trailing dimension {index} is {actual}, expected {expected}"
            )


def _normalize(name: str, value: Any, batch_size: int, timesteps: int) -> tuple[Any, dict]:
    spec = _SPECS[name]
    raw = _shape(value)
    reported = _numel(value)
    geometric = prod(raw)
    if reported != geometric:
        raise ShapeContractError(
            f"{name}: reported element count {reported} != shape product {geometric}"
        )
    if len(raw) == spec.shaped_rank:
        if raw[:2] != (batch_size, timesteps):
            raise ShapeContractError(
                f"{name}: shaped prefix {raw[:2]} != expected {(batch_size, timesteps)}"
            )
        _validate_tail(name, raw[2:], spec)
        normalized = value
    elif len(raw) == spec.flat_rank:
        if raw[0] != batch_size * timesteps:
            raise ShapeContractError(
                f"{name}: flattened leading dimension {raw[0]} != B*T {batch_size * timesteps}"
            )
        _validate_tail(name, raw[1:], spec)
        expected = batch_size * timesteps * prod(raw[1:])
        if reported != expected:
            raise ShapeContractError(f"{name}: {reported} elements != expected {expected}")
        normalized = value.reshape((batch_size, timesteps, *raw[1:]))
    else:
        raise ShapeContractError(
            f"{name}: rank {len(raw)} is neither flattened {spec.flat_rank} nor shaped {spec.shaped_rank}"
        )
    return normalized, {
        "raw_shape": list(raw),
        "normalized_shape": list(_shape(normalized)),
        "elements": reported,
    }


def normalize_lpwm_output_shapes(
    output: Mapping[str, Any], batch_size: int, timesteps: int
) -> tuple[dict[str, Any], dict]:
    """Normalize all public LPWM output tensors and record both shape views."""
    if batch_size <= 0 or timesteps <= 0:
        raise ShapeContractError("batch_size and timesteps must be positive")
    if "bg_rgb" not in output:
        if "bg_rec" in output:
            raise ShapeContractError("public bg_rgb is missing; legacy background output is forbidden")
        raise ShapeContractError("required LPWM output bg_rgb is missing")
    missing = sorted(set(_SPECS) - set(output))
    if missing:
        raise ShapeContractError(f"required LPWM outputs missing: {', '.join(missing)}")

    normalized: dict[str, Any] = {}
    tensors: dict[str, dict] = {}
    for name in _SPECS:
        normalized[name], tensors[name] = _normalize(
            name, output[name], batch_size, timesteps
        )

    spatial = tuple(normalized["rec_rgb"].shape[-2:])
    for name in ("bg_rgb", "dec_objects", "alpha_masks"):
        if tuple(normalized[name].shape[-2:]) != spatial:
            raise ShapeContractError(f"{name}: spatial dimensions do not match rec_rgb")
    k_enc_obj = int(normalized["obj_on"].shape[2])
    k_enc_mu = int(normalized["mu_tot"].shape[2])
    if k_enc_obj != k_enc_mu:
        raise ShapeContractError(f"K_enc mismatch: obj_on={k_enc_obj}, mu_tot={k_enc_mu}")
    k_dec = int(normalized["alpha_masks"].shape[2])
    manifest = {
        "schema_version": "rei-emocio-vwm-e3r-shape-manifest-v1",
        "batch_size": batch_size,
        "timesteps": timesteps,
        "tensors": tensors,
        "particle_axes": {
            "K_enc": k_enc_obj,
            "K_dec": k_dec,
            "equality_required": False,
            "active_particle_metrics_axis": "K_enc",
            "mask_coverage_metrics_axis": "K_dec",
        },
    }
    return normalized, manifest
