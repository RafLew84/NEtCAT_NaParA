from __future__ import annotations

from dataclasses import dataclass
from math import fsum, isfinite
from typing import Literal

import numpy as np
from scipy.signal import convolve, find_peaks

from ._pair_correlation_binning import pair_correlation_bin_edges
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .pair_correlation import PairCorrelationResult
from .pair_correlation_aggregation import AggregatedPairCorrelationResult


FirstShellSuggestionQualityStatus = Literal[
    "valid_suggestion",
    "insufficient_pair_count",
    "insufficient_valid_range",
    "no_reliable_peak",
    "no_minimum_after_peak",
    "unsupported_smoothing_method",
    "unsupported_window_geometry",
]


@dataclass(frozen=True)
class FirstShellSuggestionResult:
    """Non-binding first-shell radius proposal derived from a pair correlation."""

    bin_centers_nm: tuple[float, ...]
    raw_g_r: tuple[float, ...]
    smoothed_g_r: tuple[float, ...]
    valid_bin_mask: tuple[bool, ...]
    smoothing_support: tuple[float, ...]
    search_min_radius_nm: float
    peak_bin_index: int | None
    peak_radius_nm: float | None
    peak_value: float | None
    peak_prominence: float | None
    minimum_bin_index: int | None
    minimum_radius_nm: float | None
    minimum_value: float | None
    suggested_first_shell_r_max_nm: float | None
    quality_status: FirstShellSuggestionQualityStatus
    smoothing_method: str
    smoothing_width_bins: float
    minimum_expected_pair_exposure: float
    minimum_contributing_frames: int
    required_peak_prominence: float
    distance_unit: Literal["nm"] = "nm"


@dataclass(frozen=True)
class _PooledPairCorrelationSuggestionInput:
    bin_edges_nm: tuple[float, ...]
    bin_centers_nm: tuple[float, ...]
    g_r: tuple[float, ...]
    expected_pair_exposure: tuple[float, ...]
    bin_status: tuple[str, ...]
    contributing_frame_count: tuple[int, ...]
    total_unordered_pair_count: int
    min_expected_pair_exposure: float
    window_geometry_status: str


def suggest_first_shell_r_max(
    pair_correlation: PairCorrelationResult | AggregatedPairCorrelationResult,
    *,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
) -> FirstShellSuggestionResult:
    """Suggest the first local minimum after the first reliable g(r) peak."""

    if not isinstance(
        pair_correlation,
        (PairCorrelationResult, AggregatedPairCorrelationResult),
    ):
        raise TypeError(
            "pair_correlation must be a one-frame or aggregated pair-correlation result."
        )
    if settings is None:
        settings = MolecularM6OrientationAnalysisSettings()
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    return _suggest_first_shell_r_max(pair_correlation, settings=settings)


def _suggest_first_shell_r_max(
    pair_correlation: (
        PairCorrelationResult
        | AggregatedPairCorrelationResult
        | _PooledPairCorrelationSuggestionInput
    ),
    *,
    settings: MolecularM6OrientationAnalysisSettings,
) -> FirstShellSuggestionResult:
    _validate_pair_correlation_settings(pair_correlation, settings)

    centers = np.asarray(pair_correlation.bin_centers_nm, dtype=np.float64)
    raw_g = np.asarray(pair_correlation.g_r, dtype=np.float64)
    exposure = np.asarray(pair_correlation.expected_pair_exposure, dtype=np.float64)
    contributing_frames = np.asarray(
        pair_correlation.contributing_frame_count,
        dtype=np.int64,
    )
    valid = (
        (np.asarray(pair_correlation.bin_status, dtype=object) == "valid")
        & np.isfinite(raw_g)
        & np.isfinite(exposure)
        & (exposure >= settings.gr_min_expected_pair_exposure)
        & (contributing_frames >= settings.gr_min_contributing_frames)
    )

    empty_values = np.full(raw_g.shape, np.nan, dtype=np.float64)
    empty_support = np.zeros(raw_g.shape, dtype=np.float64)
    common = dict(
        bin_centers_nm=tuple(float(value) for value in centers),
        raw_g_r=tuple(float(value) for value in raw_g),
        valid_bin_mask=tuple(bool(value) for value in valid),
        search_min_radius_nm=settings.first_shell_r_min_nm,
        smoothing_method=settings.gr_smoothing_method,
        smoothing_width_bins=settings.gr_smoothing_width,
        minimum_expected_pair_exposure=settings.gr_min_expected_pair_exposure,
        minimum_contributing_frames=settings.gr_min_contributing_frames,
        required_peak_prominence=settings.gr_peak_prominence,
    )

    if settings.gr_smoothing_method != "gaussian_bins":
        return _empty_result(
            common,
            smoothed=empty_values,
            support=empty_support,
            quality_status="unsupported_smoothing_method",
        )
    if pair_correlation.window_geometry_status == "unsupported_window_geometry":
        return _empty_result(
            common,
            smoothed=empty_values,
            support=empty_support,
            quality_status="unsupported_window_geometry",
        )
    if pair_correlation.total_unordered_pair_count == 0:
        return _empty_result(
            common,
            smoothed=empty_values,
            support=empty_support,
            quality_status="insufficient_pair_count",
        )

    smoothed, support = _normalized_gaussian_convolution(
        raw_g,
        valid,
        sigma_bins=settings.gr_smoothing_width,
    )
    reliable = valid & np.isfinite(smoothed)
    searchable = reliable & (centers >= settings.first_shell_r_min_nm)
    searchable_ranges = _contiguous_true_ranges(searchable)
    if not any(stop - start >= 3 for start, stop in searchable_ranges):
        return _empty_result(
            common,
            smoothed=smoothed,
            support=support,
            quality_status="insufficient_valid_range",
        )

    peak = _first_peak(
        smoothed,
        searchable,
        reliable,
        minimum_prominence=settings.gr_peak_prominence,
    )
    if peak is None:
        return _empty_result(
            common,
            smoothed=smoothed,
            support=support,
            quality_status="no_reliable_peak",
        )
    peak_index, peak_prominence = peak
    range_stop = peak_index + 1
    while range_stop < len(searchable) and searchable[range_stop]:
        range_stop += 1
    if range_stop - peak_index < 3:
        return _peak_only_result(
            common,
            centers=centers,
            smoothed=smoothed,
            support=support,
            peak_index=peak_index,
            peak_prominence=peak_prominence,
            quality_status="insufficient_valid_range",
        )
    minimum_index = _first_minimum_after_peak(smoothed, searchable, peak_index)
    if minimum_index is None:
        return _peak_only_result(
            common,
            centers=centers,
            smoothed=smoothed,
            support=support,
            peak_index=peak_index,
            peak_prominence=peak_prominence,
            quality_status="no_minimum_after_peak",
        )

    minimum_radius = float(centers[minimum_index])
    return FirstShellSuggestionResult(
        **common,
        smoothed_g_r=tuple(float(value) for value in smoothed),
        smoothing_support=tuple(float(value) for value in support),
        peak_bin_index=peak_index,
        peak_radius_nm=float(centers[peak_index]),
        peak_value=float(smoothed[peak_index]),
        peak_prominence=peak_prominence,
        minimum_bin_index=minimum_index,
        minimum_radius_nm=minimum_radius,
        minimum_value=float(smoothed[minimum_index]),
        suggested_first_shell_r_max_nm=minimum_radius,
        quality_status="valid_suggestion",
    )


def suggest_shared_first_shell_r_max(
    first_range: AggregatedPairCorrelationResult,
    second_range: AggregatedPairCorrelationResult,
    *,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
) -> FirstShellSuggestionResult:
    """Suggest one shell radius from pooled histograms of two compared ranges."""

    if not isinstance(first_range, AggregatedPairCorrelationResult) or not isinstance(
        second_range,
        AggregatedPairCorrelationResult,
    ):
        raise TypeError("Compared ranges must be aggregated pair-correlation results.")
    if settings is None:
        settings = MolecularM6OrientationAnalysisSettings()
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    _validate_pair_correlation_settings(first_range, settings)
    _validate_pair_correlation_settings(second_range, settings)
    if set(first_range.frame_indices) & set(second_range.frame_indices):
        raise ValueError("Compared frame ranges must not overlap for a shared suggestion.")
    if (
        first_range.spatial_calibration_fingerprint
        != second_range.spatial_calibration_fingerprint
    ):
        raise ValueError("Compared ranges must share one spatial calibration fingerprint.")
    if first_range.registration_fingerprint != second_range.registration_fingerprint:
        raise ValueError("Compared ranges must share one registration fingerprint.")

    observed = tuple(
        first + second
        for first, second in zip(
            first_range.observed_unordered_pair_count,
            second_range.observed_unordered_pair_count,
        )
    )
    try:
        exposure = tuple(
            fsum((first, second))
            for first, second in zip(
                first_range.expected_pair_exposure,
                second_range.expected_pair_exposure,
            )
        )
    except OverflowError as exc:
        raise ValueError("Compared ranges produce a non-finite pooled exposure.") from exc
    if any(not isfinite(value) for value in exposure):
        raise ValueError("Compared ranges produce a non-finite pooled exposure.")
    contributions = tuple(
        first + second
        for first, second in zip(
            first_range.contributing_frame_count,
            second_range.contributing_frame_count,
        )
    )
    shared_geometry_unsupported = (
        first_range.window_geometry_status == "unsupported_window_geometry"
        or second_range.window_geometry_status == "unsupported_window_geometry"
    )
    if shared_geometry_unsupported:
        statuses = ("unsupported_window_geometry",) * len(observed)
        g_values = (float("nan"),) * len(observed)
        geometry_status = "unsupported_window_geometry"
    else:
        valid = tuple(
            expected >= settings.gr_min_expected_pair_exposure
            and contribution >= settings.gr_min_contributing_frames
            and first_expected > 0.0
            and second_expected > 0.0
            for expected, contribution, first_expected, second_expected in zip(
                exposure,
                contributions,
                first_range.expected_pair_exposure,
                second_range.expected_pair_exposure,
            )
        )
        statuses = tuple(
            "valid" if is_valid else "insufficient_exposure"
            for is_valid in valid
        )
        g_values_list: list[float] = []
        for count, expected, is_valid in zip(observed, exposure, valid):
            if not is_valid:
                g_values_list.append(float("nan"))
                continue
            try:
                value = count / expected
            except OverflowError as exc:
                raise ValueError("Pooled g(r) is not finite.") from exc
            if not isfinite(value):
                raise ValueError("Pooled g(r) is not finite.")
            g_values_list.append(float(value))
        g_values = tuple(g_values_list)
        geometry_status = (
            "partially_unsupported_frame_windows"
            if (
                first_range.window_geometry_status != "supported_frame_windows"
                or second_range.window_geometry_status != "supported_frame_windows"
            )
            else "supported_frame_windows"
        )
    pooled = _PooledPairCorrelationSuggestionInput(
        bin_edges_nm=first_range.bin_edges_nm,
        bin_centers_nm=first_range.bin_centers_nm,
        g_r=g_values,
        expected_pair_exposure=exposure,
        bin_status=statuses,
        contributing_frame_count=contributions,
        total_unordered_pair_count=(
            first_range.total_unordered_pair_count
            + second_range.total_unordered_pair_count
        ),
        min_expected_pair_exposure=settings.gr_min_expected_pair_exposure,
        window_geometry_status=geometry_status,
    )
    return _suggest_first_shell_r_max(pooled, settings=settings)


def _normalized_gaussian_convolution(
    values: np.ndarray,
    valid: np.ndarray,
    *,
    sigma_bins: float,
) -> tuple[np.ndarray, np.ndarray]:
    radius = max(1, int(np.ceil(4.0 * sigma_bins)))
    offsets = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * np.square(offsets / sigma_bins))
    kernel /= float(np.sum(kernel))
    weights = valid.astype(np.float64)
    numerator = convolve(np.where(valid, values, 0.0), kernel, mode="same")
    support = convolve(weights, kernel, mode="same")
    smoothed = np.full(values.shape, np.nan, dtype=np.float64)
    positive_support = support > 0.0
    smoothed[positive_support] = numerator[positive_support] / support[positive_support]
    return smoothed, support


def _first_peak(
    values: np.ndarray,
    searchable: np.ndarray,
    reliable: np.ndarray,
    *,
    minimum_prominence: float,
) -> tuple[int, float] | None:
    for start, stop in _contiguous_true_ranges(searchable):
        context_start = start - 1 if start > 0 and reliable[start - 1] else start
        peak_indices, properties = find_peaks(
            values[context_start:stop],
            prominence=minimum_prominence,
        )
        allowed_peak_offsets = np.flatnonzero(peak_indices + context_start >= start)
        if len(allowed_peak_offsets):
            first_allowed_offset = int(allowed_peak_offsets[0])
            return (
                context_start + int(peak_indices[first_allowed_offset]),
                float(properties["prominences"][first_allowed_offset]),
            )
    return None


def _first_minimum_after_peak(
    values: np.ndarray,
    searchable: np.ndarray,
    peak_index: int,
) -> int | None:
    stop = peak_index + 1
    while stop < len(searchable) and searchable[stop]:
        stop += 1
    minimum_indices, _properties = find_peaks(-values[peak_index:stop])
    if not len(minimum_indices):
        return None
    return peak_index + int(minimum_indices[0])


def _contiguous_true_ranges(mask: np.ndarray) -> tuple[tuple[int, int], ...]:
    padded = np.concatenate(([False], mask, [False])).astype(np.int8)
    transitions = np.diff(padded)
    starts = np.flatnonzero(transitions == 1)
    stops = np.flatnonzero(transitions == -1)
    return tuple((int(start), int(stop)) for start, stop in zip(starts, stops))


def _empty_result(
    common: dict[str, object],
    *,
    smoothed: np.ndarray,
    support: np.ndarray,
    quality_status: FirstShellSuggestionQualityStatus,
) -> FirstShellSuggestionResult:
    return FirstShellSuggestionResult(
        **common,
        smoothed_g_r=tuple(float(value) for value in smoothed),
        smoothing_support=tuple(float(value) for value in support),
        peak_bin_index=None,
        peak_radius_nm=None,
        peak_value=None,
        peak_prominence=None,
        minimum_bin_index=None,
        minimum_radius_nm=None,
        minimum_value=None,
        suggested_first_shell_r_max_nm=None,
        quality_status=quality_status,
    )


def _peak_only_result(
    common: dict[str, object],
    *,
    centers: np.ndarray,
    smoothed: np.ndarray,
    support: np.ndarray,
    peak_index: int,
    peak_prominence: float,
    quality_status: FirstShellSuggestionQualityStatus,
) -> FirstShellSuggestionResult:
    return FirstShellSuggestionResult(
        **common,
        smoothed_g_r=tuple(float(value) for value in smoothed),
        smoothing_support=tuple(float(value) for value in support),
        peak_bin_index=peak_index,
        peak_radius_nm=float(centers[peak_index]),
        peak_value=float(smoothed[peak_index]),
        peak_prominence=peak_prominence,
        minimum_bin_index=None,
        minimum_radius_nm=None,
        minimum_value=None,
        suggested_first_shell_r_max_nm=None,
        quality_status=quality_status,
    )


def _validate_pair_correlation_settings(
    pair_correlation: (
        PairCorrelationResult
        | AggregatedPairCorrelationResult
        | _PooledPairCorrelationSuggestionInput
    ),
    settings: MolecularM6OrientationAnalysisSettings,
) -> None:
    expected_edges = pair_correlation_bin_edges(
        settings.gr_bin_width_nm,
        settings.gr_max_nm,
    )
    if len(expected_edges) != len(pair_correlation.bin_edges_nm) or not np.allclose(
        expected_edges,
        pair_correlation.bin_edges_nm,
        rtol=1e-12,
        atol=1e-12,
    ):
        raise ValueError("pair_correlation binning must match the supplied g(r) settings.")
    if settings.gr_min_expected_pair_exposure < pair_correlation.min_expected_pair_exposure:
        raise ValueError(
            "settings minimum exposure cannot be lower than the threshold used "
            "to compute pair_correlation."
        )
    if (
        isinstance(pair_correlation, AggregatedPairCorrelationResult)
        and settings.gr_min_contributing_frames
        < pair_correlation.min_contributing_frames
    ):
        raise ValueError(
            "settings contributing-frame minimum cannot be lower than the threshold "
            "used to compute the aggregated pair correlation."
        )
