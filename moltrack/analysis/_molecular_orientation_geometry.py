"""Shared geometry validation for molecular-orientation estimators."""

from __future__ import annotations

import numpy as np

from ._molecular_orientation_contract import finite_float
from .molecular_orientation_models import MolecularOrientationProvenance


def orientation_context(
    provenance: MolecularOrientationProvenance,
    *,
    scan_angle_deg: float | None,
) -> tuple[str, float]:
    if scan_angle_deg is None:
        if provenance.orientation_reference != "image_x_axis_counterclockwise":
            raise ValueError(
                "Missing scan_angle_deg requires "
                "orientation_reference='image_x_axis_counterclockwise'."
            )
        return "image_xy", 0.0
    angle = finite_float(scan_angle_deg, "scan_angle_deg")
    if provenance.orientation_reference != "sample_x_axis_counterclockwise":
        raise ValueError(
            "Known scan_angle_deg requires "
            "orientation_reference='sample_x_axis_counterclockwise'."
        )
    return "sample_nm", angle


def positive_pair(value: object, field_name: str) -> tuple[float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 2:
        raise TypeError(f"{field_name} must contain x and y.")
    first = finite_float(value[0], f"{field_name}[0]")
    second = finite_float(value[1], f"{field_name}[1]")
    if first <= 0.0 or second <= 0.0:
        raise ValueError(f"{field_name} values must be positive.")
    return first, second


def binary_mask(value: object, field_name: str) -> np.ndarray:
    try:
        array = np.asarray(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"{field_name} must be a two-dimensional binary array."
        ) from exc
    if array.ndim != 2:
        raise ValueError(f"{field_name} must be a two-dimensional array.")
    if array.dtype == np.bool_:
        return np.ascontiguousarray(array, dtype=bool)
    if not (
        np.issubdtype(array.dtype, np.integer)
        or np.issubdtype(array.dtype, np.floating)
    ):
        raise TypeError(f"{field_name} must contain binary numeric values.")
    numeric = np.asarray(array, dtype=np.float64)
    if not np.all(np.isfinite(numeric)):
        raise ValueError(f"{field_name} must contain only finite values.")
    if not np.all((numeric == 0.0) | (numeric == 1.0)):
        raise ValueError(f"{field_name} must contain only binary 0/1 values.")
    return np.ascontiguousarray(numeric, dtype=bool)


def periodic_axis_distance(
    first_deg: float,
    second_deg: float,
    *,
    period_deg: float = 180.0,
) -> float:
    period = finite_float(period_deg, "period_deg")
    if period <= 0.0:
        raise ValueError("period_deg must be positive.")
    difference = abs((float(first_deg) - float(second_deg)) % period)
    return min(difference, period - difference)
