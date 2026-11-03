from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import fsum, isfinite
from typing import Literal

import numpy as np

from ._pair_correlation_binning import pair_correlation_bin_edges
from ._pair_correlation_validation import (
    PAIR_CORRELATION_WINDOW_STATUSES,
    PairCorrelationBinStatus,
    PairCorrelationWindowGeometryStatus,
    as_non_empty_string as _as_non_empty_string,
    as_non_negative_integer as _as_non_negative_integer,
    as_positive_float as _as_positive_float,
    as_positive_integer as _as_positive_integer,
    normalize_pair_correlation_bins,
)
from .frame_ranges import MolecularFrameRange
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .pair_correlation import PairCorrelationResult


AggregatedPairCorrelationWindowGeometryStatus = Literal[
    "supported_frame_windows",
    "partially_unsupported_frame_windows",
    "unsupported_window_geometry",
]

_AGGREGATE_WINDOW_STATUSES = {
    "supported_frame_windows",
    "partially_unsupported_frame_windows",
    "unsupported_window_geometry",
}
@dataclass(frozen=True)
class AggregatedPairCorrelationResult:
    """Pair correlation aggregated from independent per-frame histograms."""

    bin_edges_nm: tuple[float, ...]
    bin_centers_nm: tuple[float, ...]
    g_r: tuple[float, ...]
    observed_unordered_pair_count: tuple[int, ...]
    expected_pair_exposure: tuple[float, ...]
    bin_status: tuple[PairCorrelationBinStatus, ...]
    contributing_frame_count: tuple[int, ...]
    frame_range: MolecularFrameRange
    frame_indices: tuple[int, ...]
    frame_count: int
    frame_point_counts: tuple[int, ...]
    total_point_count: int
    frame_unordered_pair_counts: tuple[int, ...]
    total_unordered_pair_count: int
    min_expected_pair_exposure: float
    min_contributing_frames: int
    window_geometry_status: AggregatedPairCorrelationWindowGeometryStatus
    frame_window_geometry_statuses: tuple[PairCorrelationWindowGeometryStatus, ...]
    unsupported_frame_indices: tuple[int, ...]
    coordinate_frame: Literal["sample_nm"]
    spatial_calibration_fingerprint: str
    registration_fingerprint: str
    frame_point_coordinate_fingerprints: tuple[str, ...]
    distance_unit: Literal["nm"] = "nm"

    def __post_init__(self) -> None:
        if not isinstance(self.frame_range, MolecularFrameRange):
            raise TypeError("frame_range must be a MolecularFrameRange.")
        frame_indices = tuple(
            _as_non_negative_integer(value, "frame_indices")
            for value in self.frame_indices
        )
        if frame_indices != self.frame_range.frame_indices:
            raise ValueError("frame_indices must match the inclusive frame_range.")
        frame_count = _as_positive_integer(self.frame_count, "frame_count")
        if frame_count != len(frame_indices):
            raise ValueError("frame_count must match frame_indices.")

        frame_point_counts = tuple(
            _as_non_negative_integer(value, "frame_point_counts")
            for value in self.frame_point_counts
        )
        frame_pair_counts = tuple(
            _as_non_negative_integer(value, "frame_unordered_pair_counts")
            for value in self.frame_unordered_pair_counts
        )
        if len(frame_point_counts) != frame_count or len(frame_pair_counts) != frame_count:
            raise ValueError("Per-frame counts must contain one value per frame.")
        if any(
            pair_count != point_count * (point_count - 1) // 2
            for point_count, pair_count in zip(frame_point_counts, frame_pair_counts)
        ):
            raise ValueError("Each frame pair count must equal N*(N-1)/2.")
        total_point_count = _as_non_negative_integer(
            self.total_point_count,
            "total_point_count",
        )
        total_pair_count = _as_non_negative_integer(
            self.total_unordered_pair_count,
            "total_unordered_pair_count",
        )
        if total_point_count != sum(frame_point_counts):
            raise ValueError("total_point_count must equal the sum of frame_point_counts.")
        if total_pair_count != sum(frame_pair_counts):
            raise ValueError(
                "total_unordered_pair_count must equal the sum of per-frame pair counts."
            )

        bins = normalize_pair_correlation_bins(
            bin_edges_nm=self.bin_edges_nm,
            bin_centers_nm=self.bin_centers_nm,
            observed_unordered_pair_count=self.observed_unordered_pair_count,
            expected_pair_exposure=self.expected_pair_exposure,
            g_r=self.g_r,
            bin_status=self.bin_status,
            contributing_frame_count=self.contributing_frame_count,
            total_unordered_pair_count=total_pair_count,
            maximum_contributing_frames=frame_count,
            require_finite_exposure=True,
        )
        edges = bins.bin_edges_nm
        centers = bins.bin_centers_nm
        observed = bins.observed_unordered_pair_count
        exposure = bins.expected_pair_exposure
        g_values = bins.g_r
        statuses = bins.bin_status
        contributions = bins.contributing_frame_count

        minimum_exposure = _as_positive_float(
            self.min_expected_pair_exposure,
            "min_expected_pair_exposure",
        )
        minimum_frames = _as_positive_integer(
            self.min_contributing_frames,
            "min_contributing_frames",
        )
        if self.window_geometry_status not in _AGGREGATE_WINDOW_STATUSES:
            raise ValueError("Unsupported aggregate window_geometry_status.")
        frame_geometry_statuses = tuple(self.frame_window_geometry_statuses)
        if len(frame_geometry_statuses) != frame_count:
            raise ValueError(
                "frame_window_geometry_statuses must contain one status per frame."
            )
        if any(
            status not in PAIR_CORRELATION_WINDOW_STATUSES
            for status in frame_geometry_statuses
        ):
            raise ValueError("Unsupported per-frame window geometry status.")
        unsupported_indices = tuple(
            frame_index
            for frame_index, status in zip(frame_indices, frame_geometry_statuses)
            if status == "unsupported_window_geometry"
        )
        if tuple(self.unsupported_frame_indices) != unsupported_indices:
            raise ValueError(
                "unsupported_frame_indices must match frame window geometry statuses."
            )
        expected_geometry_status: AggregatedPairCorrelationWindowGeometryStatus
        if len(unsupported_indices) == frame_count:
            expected_geometry_status = "unsupported_window_geometry"
        elif unsupported_indices:
            expected_geometry_status = "partially_unsupported_frame_windows"
        else:
            expected_geometry_status = "supported_frame_windows"
        if self.window_geometry_status != expected_geometry_status:
            raise ValueError("Aggregate window geometry status does not match its frames.")

        all_windows_unsupported = (
            self.window_geometry_status == "unsupported_window_geometry"
        )
        for count, expected, g_value, status, contribution in zip(
            observed,
            exposure,
            g_values,
            statuses,
            contributions,
        ):
            if all_windows_unsupported:
                if (
                    status != "unsupported_window_geometry"
                    or count != 0
                    or expected != 0.0
                    or not np.isnan(g_value)
                    or contribution != 0
                ):
                    raise ValueError(
                        "Fully unsupported aggregation requires zero exposure, NaN g(r), "
                        "and unsupported bin statuses."
                    )
                continue
            if (expected == 0.0) != (contribution == 0):
                raise ValueError(
                    "Positive aggregate exposure must have a contributing frame."
                )
            is_valid = expected >= minimum_exposure and contribution >= minimum_frames
            if is_valid:
                if status != "valid" or not isfinite(g_value):
                    raise ValueError("Sufficient aggregate support requires finite valid g(r).")
                if not np.isclose(g_value, count / expected, rtol=1e-12, atol=1e-12):
                    raise ValueError("Valid aggregate g(r) must equal sum(DD)/sum(E).")
            elif status != "insufficient_exposure" or not np.isnan(g_value):
                raise ValueError("Insufficient aggregate support requires g(r)=NaN.")

        if self.coordinate_frame != "sample_nm":
            raise ValueError("coordinate_frame must be 'sample_nm'.")
        if self.distance_unit != "nm":
            raise ValueError("distance_unit must be 'nm'.")
        calibration_fingerprint = _as_non_empty_string(
            self.spatial_calibration_fingerprint,
            "spatial_calibration_fingerprint",
        )
        registration_fingerprint = _as_non_empty_string(
            self.registration_fingerprint,
            "registration_fingerprint",
        )
        coordinate_fingerprints = tuple(
            _as_non_empty_string(value, "frame_point_coordinate_fingerprints")
            for value in self.frame_point_coordinate_fingerprints
        )
        if len(coordinate_fingerprints) != frame_count:
            raise ValueError(
                "frame_point_coordinate_fingerprints must contain one value per frame."
            )

        object.__setattr__(self, "bin_edges_nm", edges)
        object.__setattr__(self, "bin_centers_nm", centers)
        object.__setattr__(self, "g_r", g_values)
        object.__setattr__(self, "observed_unordered_pair_count", observed)
        object.__setattr__(self, "expected_pair_exposure", exposure)
        object.__setattr__(self, "bin_status", statuses)
        object.__setattr__(self, "contributing_frame_count", contributions)
        object.__setattr__(self, "frame_indices", frame_indices)
        object.__setattr__(self, "frame_count", frame_count)
        object.__setattr__(self, "frame_point_counts", frame_point_counts)
        object.__setattr__(self, "total_point_count", total_point_count)
        object.__setattr__(self, "frame_unordered_pair_counts", frame_pair_counts)
        object.__setattr__(self, "total_unordered_pair_count", total_pair_count)
        object.__setattr__(self, "min_expected_pair_exposure", minimum_exposure)
        object.__setattr__(self, "min_contributing_frames", minimum_frames)
        object.__setattr__(self, "frame_window_geometry_statuses", frame_geometry_statuses)
        object.__setattr__(self, "unsupported_frame_indices", unsupported_indices)
        object.__setattr__(self, "spatial_calibration_fingerprint", calibration_fingerprint)
        object.__setattr__(self, "registration_fingerprint", registration_fingerprint)
        object.__setattr__(
            self,
            "frame_point_coordinate_fingerprints",
            coordinate_fingerprints,
        )


def aggregate_pair_correlation_results(
    frame_results: Sequence[PairCorrelationResult],
    *,
    frame_range: MolecularFrameRange,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
) -> AggregatedPairCorrelationResult:
    """Aggregate independent frame histograms without introducing cross-frame pairs."""

    if not isinstance(frame_range, MolecularFrameRange):
        raise TypeError("frame_range must be a MolecularFrameRange.")
    if settings is None:
        settings = MolecularM6OrientationAnalysisSettings()
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    normalized_results = tuple(frame_results)
    if any(not isinstance(result, PairCorrelationResult) for result in normalized_results):
        raise TypeError("frame_results must contain PairCorrelationResult values.")
    if len(normalized_results) != len(frame_range.frame_indices):
        raise ValueError("frame_results must contain exactly one result per selected frame.")
    ordered_results = tuple(sorted(normalized_results, key=lambda result: result.frame_index))
    frame_indices = tuple(result.frame_index for result in ordered_results)
    if frame_indices != frame_range.frame_indices:
        raise ValueError("frame result frame indices must match the inclusive frame_range.")
    _validate_frame_result_contract(ordered_results, settings)

    bin_count = len(ordered_results[0].bin_centers_nm)
    observed_sum = [0] * bin_count
    exposure_terms: list[list[float]] = [[] for _index in range(bin_count)]
    contributing_frames = [0] * bin_count
    for result in ordered_results:
        for bin_index, (count, expected) in enumerate(
            zip(
                result.observed_unordered_pair_count,
                result.expected_pair_exposure,
            )
        ):
            contributes = isfinite(expected) and expected > 0.0
            if (
                count > 0
                and not contributes
                and result.window_geometry_status != "unsupported_window_geometry"
            ):
                raise ValueError(
                    "A positive observed count requires positive finite exposure "
                    "for aggregation."
                )
            if contributes:
                observed_sum[bin_index] += count
                exposure_terms[bin_index].append(expected)
                contributing_frames[bin_index] += 1
    try:
        exposure_sum = tuple(fsum(terms) for terms in exposure_terms)
    except OverflowError as exc:
        raise ValueError("Per-frame values produce a non-finite aggregate exposure.") from exc
    if any(not isfinite(value) for value in exposure_sum):
        raise ValueError("Per-frame values produce a non-finite aggregate exposure.")

    unsupported_frame_indices = tuple(
        result.frame_index
        for result in ordered_results
        if result.window_geometry_status == "unsupported_window_geometry"
    )
    if len(unsupported_frame_indices) == len(ordered_results):
        geometry_status: AggregatedPairCorrelationWindowGeometryStatus = (
            "unsupported_window_geometry"
        )
        statuses: tuple[PairCorrelationBinStatus, ...] = (
            "unsupported_window_geometry",
        ) * bin_count
        g_values = (float("nan"),) * bin_count
    else:
        geometry_status = (
            "partially_unsupported_frame_windows"
            if unsupported_frame_indices
            else "supported_frame_windows"
        )
        valid = (
            (np.asarray(exposure_sum) >= settings.gr_min_expected_pair_exposure)
            & (
                np.asarray(contributing_frames)
                >= settings.gr_min_contributing_frames
            )
        )
        statuses = tuple(
            "valid" if is_valid else "insufficient_exposure"
            for is_valid in valid
        )
        g_values_list: list[float] = []
        for count, expected, is_valid in zip(observed_sum, exposure_sum, valid):
            if not is_valid:
                g_values_list.append(float("nan"))
                continue
            try:
                value = count / expected
            except OverflowError as exc:
                raise ValueError("Aggregate g(r) is not finite.") from exc
            if not isfinite(value):
                raise ValueError("Aggregate g(r) is not finite.")
            g_values_list.append(float(value))
        g_values = tuple(g_values_list)

    return AggregatedPairCorrelationResult(
        bin_edges_nm=ordered_results[0].bin_edges_nm,
        bin_centers_nm=ordered_results[0].bin_centers_nm,
        g_r=g_values,
        observed_unordered_pair_count=tuple(observed_sum),
        expected_pair_exposure=exposure_sum,
        bin_status=statuses,
        contributing_frame_count=tuple(contributing_frames),
        frame_range=frame_range,
        frame_indices=frame_indices,
        frame_count=len(ordered_results),
        frame_point_counts=tuple(result.point_count for result in ordered_results),
        total_point_count=sum(result.point_count for result in ordered_results),
        frame_unordered_pair_counts=tuple(
            result.total_unordered_pair_count for result in ordered_results
        ),
        total_unordered_pair_count=sum(
            result.total_unordered_pair_count for result in ordered_results
        ),
        min_expected_pair_exposure=settings.gr_min_expected_pair_exposure,
        min_contributing_frames=settings.gr_min_contributing_frames,
        window_geometry_status=geometry_status,
        frame_window_geometry_statuses=tuple(
            result.window_geometry_status for result in ordered_results
        ),
        unsupported_frame_indices=unsupported_frame_indices,
        coordinate_frame="sample_nm",
        spatial_calibration_fingerprint=ordered_results[0].spatial_calibration_fingerprint,
        registration_fingerprint=ordered_results[0].registration_fingerprint,
        frame_point_coordinate_fingerprints=tuple(
            result.point_coordinate_fingerprint for result in ordered_results
        ),
    )


def _validate_frame_result_contract(
    results: tuple[PairCorrelationResult, ...],
    settings: MolecularM6OrientationAnalysisSettings,
) -> None:
    expected_edges = pair_correlation_bin_edges(
        settings.gr_bin_width_nm,
        settings.gr_max_nm,
    )
    for result in results:
        if len(result.bin_edges_nm) != len(expected_edges) or not np.allclose(
            result.bin_edges_nm,
            expected_edges,
            rtol=1e-12,
            atol=1e-12,
        ):
            raise ValueError("Every frame result binning must match the supplied settings.")
    calibration_fingerprints = {
        result.spatial_calibration_fingerprint for result in results
    }
    if len(calibration_fingerprints) != 1:
        raise ValueError("Frame results must share one spatial calibration fingerprint.")
    registration_fingerprints = {result.registration_fingerprint for result in results}
    if len(registration_fingerprints) != 1:
        raise ValueError("Frame results must share one registration fingerprint.")
