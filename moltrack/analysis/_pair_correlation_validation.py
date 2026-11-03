from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal

import numpy as np


PairCorrelationBinStatus = Literal[
    "valid",
    "insufficient_exposure",
    "unsupported_window_geometry",
]
PairCorrelationWindowGeometryStatus = Literal[
    "rectangular_translation_correction",
    "irregular_mask_autocorrelation",
    "unsupported_window_geometry",
]

PAIR_CORRELATION_BIN_STATUSES = {
    "valid",
    "insufficient_exposure",
    "unsupported_window_geometry",
}
PAIR_CORRELATION_WINDOW_STATUSES = {
    "rectangular_translation_correction",
    "irregular_mask_autocorrelation",
    "unsupported_window_geometry",
}


@dataclass(frozen=True)
class NormalizedPairCorrelationBins:
    bin_edges_nm: tuple[float, ...]
    bin_centers_nm: tuple[float, ...]
    observed_unordered_pair_count: tuple[int, ...]
    expected_pair_exposure: tuple[float, ...]
    g_r: tuple[float, ...]
    bin_status: tuple[PairCorrelationBinStatus, ...]
    contributing_frame_count: tuple[int, ...]


def normalize_pair_correlation_bins(
    *,
    bin_edges_nm: object,
    bin_centers_nm: object,
    observed_unordered_pair_count: object,
    expected_pair_exposure: object,
    g_r: object,
    bin_status: object,
    contributing_frame_count: object,
    total_unordered_pair_count: int,
    maximum_contributing_frames: int,
    require_finite_exposure: bool,
) -> NormalizedPairCorrelationBins:
    """Normalize structural invariants shared by frame and range histograms."""

    edges = tuple(as_finite_float(value, "bin_edges_nm") for value in bin_edges_nm)
    if len(edges) < 2 or edges[0] != 0.0:
        raise ValueError("bin_edges_nm must start at zero and contain at least one bin.")
    if any(left >= right for left, right in zip(edges, edges[1:])):
        raise ValueError("bin_edges_nm must be strictly increasing.")
    bin_count = len(edges) - 1
    centers = tuple(
        as_finite_float(value, "bin_centers_nm") for value in bin_centers_nm
    )
    expected_centers = tuple(
        (left + right) / 2.0 for left, right in zip(edges, edges[1:])
    )
    if len(centers) != bin_count or any(
        not np.isclose(actual, expected, rtol=1e-12, atol=1e-12)
        for actual, expected in zip(centers, expected_centers)
    ):
        raise ValueError("bin_centers_nm must contain the midpoint of every bin.")

    observed = tuple(
        as_non_negative_integer(value, "observed_unordered_pair_count")
        for value in observed_unordered_pair_count
    )
    exposure = tuple(float(value) for value in expected_pair_exposure)
    g_values = tuple(float(value) for value in g_r)
    statuses = tuple(bin_status)
    contributions = tuple(
        as_non_negative_integer(value, "contributing_frame_count")
        for value in contributing_frame_count
    )
    if not all(
        len(values) == bin_count
        for values in (observed, exposure, g_values, statuses, contributions)
    ):
        raise ValueError("All per-bin fields must match bin_edges_nm.")
    if sum(observed) > total_unordered_pair_count:
        raise ValueError("Observed histogram cannot exceed available unordered pairs.")
    if any(status not in PAIR_CORRELATION_BIN_STATUSES for status in statuses):
        raise ValueError("Unsupported pair-correlation bin status.")
    if any(value > maximum_contributing_frames for value in contributions):
        raise ValueError(
            "contributing_frame_count cannot exceed available contributing frames."
        )
    for index, expected in enumerate(exposure):
        if isfinite(expected) and expected < 0.0:
            raise ValueError(f"expected_pair_exposure[{index}] must be non-negative.")
        if require_finite_exposure and not isfinite(expected):
            raise ValueError("expected_pair_exposure must be finite for an aggregate.")

    return NormalizedPairCorrelationBins(
        bin_edges_nm=edges,
        bin_centers_nm=centers,
        observed_unordered_pair_count=observed,
        expected_pair_exposure=exposure,
        g_r=g_values,
        bin_status=statuses,
        contributing_frame_count=contributions,
    )


def as_finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric.")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be numeric.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def as_positive_float(value: object, field_name: str) -> float:
    normalized = as_finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def as_non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer.")
    try:
        normalized = int(value)
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be an integer.") from exc
    if not isfinite(numeric) or numeric != normalized or normalized < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return normalized


def as_positive_integer(value: object, field_name: str) -> int:
    normalized = as_non_negative_integer(value, field_name)
    if normalized <= 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def as_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized
