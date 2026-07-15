from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite
from typing import Literal

import numpy as np
from scipy.spatial.distance import pdist

from ._coordinate_fingerprint import point_coordinate_fingerprint
from ._pair_correlation_binning import pair_correlation_bin_edges
from .first_shell_graph import FirstShellGraph
from .m6_settings import MolecularM6OrientationAnalysisSettings
from ._pair_correlation_windows import (
    masked_annulus_overlap_integrals,
    rectangular_annulus_overlap_integrals,
)


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

_BIN_STATUSES = {
    "valid",
    "insufficient_exposure",
    "unsupported_window_geometry",
}
_WINDOW_STATUSES = {
    "rectangular_translation_correction",
    "irregular_mask_autocorrelation",
    "unsupported_window_geometry",
}


@dataclass(frozen=True)
class PairCorrelationResult:
    """One-frame radial pair correlation with explicit edge-corrected exposure."""

    bin_edges_nm: tuple[float, ...]
    bin_centers_nm: tuple[float, ...]
    g_r: tuple[float, ...]
    observed_unordered_pair_count: tuple[int, ...]
    expected_pair_exposure: tuple[float, ...]
    bin_status: tuple[PairCorrelationBinStatus, ...]
    contributing_frame_count: tuple[int, ...]
    point_count: int
    total_unordered_pair_count: int
    min_expected_pair_exposure: float
    window_area_nm2: float | None
    window_geometry_status: PairCorrelationWindowGeometryStatus
    frame_index: int
    representative_point_ids: tuple[str, ...]
    coordinate_frame: Literal["sample_nm"]
    spatial_calibration_fingerprint: str
    registration_fingerprint: str
    point_coordinate_fingerprint: str
    window_origin_nm: tuple[float, float]
    distance_unit: Literal["nm"] = "nm"

    def __post_init__(self) -> None:
        point_count = _as_non_negative_integer(self.point_count, "point_count")
        total_pair_count = _as_non_negative_integer(
            self.total_unordered_pair_count,
            "total_unordered_pair_count",
        )
        if total_pair_count != point_count * (point_count - 1) // 2:
            raise ValueError("total_unordered_pair_count must equal N*(N-1)/2.")
        minimum_exposure = _as_positive_float(
            self.min_expected_pair_exposure,
            "min_expected_pair_exposure",
        )
        if self.distance_unit != "nm":
            raise ValueError("distance_unit must be 'nm'.")
        frame_index = _as_non_negative_integer(self.frame_index, "frame_index")
        representative_point_ids = tuple(self.representative_point_ids)
        if len(representative_point_ids) != point_count:
            raise ValueError("representative_point_ids must contain one ID per point.")
        if any(
            not isinstance(point_id, str) or not point_id
            for point_id in representative_point_ids
        ):
            raise TypeError("representative_point_ids must contain non-empty strings.")
        if len(set(representative_point_ids)) != point_count:
            raise ValueError("representative_point_ids must be unique.")
        if self.coordinate_frame != "sample_nm":
            raise ValueError("coordinate_frame must be 'sample_nm'.")
        calibration_fingerprint = _as_non_empty_string(
            self.spatial_calibration_fingerprint,
            "spatial_calibration_fingerprint",
        )
        registration_fingerprint = _as_non_empty_string(
            self.registration_fingerprint,
            "registration_fingerprint",
        )
        coordinate_fingerprint = _as_non_empty_string(
            self.point_coordinate_fingerprint,
            "point_coordinate_fingerprint",
        )
        window_origin_nm = _normalize_finite_pair(
            self.window_origin_nm,
            "window_origin_nm",
        )
        if self.window_geometry_status not in _WINDOW_STATUSES:
            raise ValueError("Unsupported window_geometry_status.")

        edges = tuple(_as_finite_float(value, "bin_edges_nm") for value in self.bin_edges_nm)
        if len(edges) < 2 or edges[0] != 0.0:
            raise ValueError("bin_edges_nm must start at zero and contain at least one bin.")
        if any(left >= right for left, right in zip(edges, edges[1:])):
            raise ValueError("bin_edges_nm must be strictly increasing.")
        bin_count = len(edges) - 1
        centers = tuple(
            _as_finite_float(value, "bin_centers_nm") for value in self.bin_centers_nm
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
            _as_non_negative_integer(value, "observed_unordered_pair_count")
            for value in self.observed_unordered_pair_count
        )
        exposure = tuple(float(value) for value in self.expected_pair_exposure)
        g_values = tuple(float(value) for value in self.g_r)
        statuses = tuple(self.bin_status)
        contributions = tuple(
            _as_non_negative_integer(value, "contributing_frame_count")
            for value in self.contributing_frame_count
        )
        if not all(
            len(values) == bin_count
            for values in (observed, exposure, g_values, statuses, contributions)
        ):
            raise ValueError("All per-bin fields must match bin_edges_nm.")
        if sum(observed) > total_pair_count:
            raise ValueError("Observed histogram cannot exceed the total unordered pair count.")
        if any(status not in _BIN_STATUSES for status in statuses):
            raise ValueError("Unsupported pair-correlation bin status.")
        if any(value not in (0, 1) for value in contributions):
            raise ValueError("One-frame contributing_frame_count values must be zero or one.")

        unsupported = self.window_geometry_status == "unsupported_window_geometry"
        if unsupported:
            if self.window_area_nm2 is not None:
                raise ValueError("Unsupported window geometry cannot have a window area.")
            window_area_nm2 = None
        else:
            window_area_nm2 = _as_positive_float(self.window_area_nm2, "window_area_nm2")
        for index, (count, expected, g_value, status, contribution) in enumerate(
            zip(observed, exposure, g_values, statuses, contributions)
        ):
            if unsupported:
                if status != "unsupported_window_geometry":
                    raise ValueError("Unsupported geometry requires unsupported bin statuses.")
                if not np.isnan(expected) or not np.isnan(g_value) or contribution != 0:
                    raise ValueError(
                        "Unsupported geometry must expose NaN values and no contribution."
                    )
                continue
            if isfinite(expected) and expected < 0.0:
                raise ValueError(f"expected_pair_exposure[{index}] must be non-negative.")
            if not isfinite(expected):
                if status != "insufficient_exposure" or not np.isnan(g_value) or contribution != 0:
                    raise ValueError(
                        "Non-finite exposure requires insufficient_exposure, g(r)=NaN, "
                        "and no contribution."
                    )
                continue
            expected_contribution = int(expected > 0.0)
            if contribution != expected_contribution:
                raise ValueError("contributing_frame_count must indicate positive exposure.")
            if expected >= minimum_exposure:
                if status != "valid" or not isfinite(g_value):
                    raise ValueError("Sufficient exposure requires a finite valid g(r) value.")
                if not np.isclose(g_value, count / expected, rtol=1e-12, atol=1e-12):
                    raise ValueError("Valid g(r) must equal DD/E.")
            elif status != "insufficient_exposure" or not np.isnan(g_value):
                raise ValueError("Insufficient exposure requires g(r)=NaN.")

        object.__setattr__(self, "bin_edges_nm", edges)
        object.__setattr__(self, "bin_centers_nm", centers)
        object.__setattr__(self, "g_r", g_values)
        object.__setattr__(self, "observed_unordered_pair_count", observed)
        object.__setattr__(self, "expected_pair_exposure", exposure)
        object.__setattr__(self, "bin_status", statuses)
        object.__setattr__(self, "contributing_frame_count", contributions)
        object.__setattr__(self, "point_count", point_count)
        object.__setattr__(self, "total_unordered_pair_count", total_pair_count)
        object.__setattr__(self, "min_expected_pair_exposure", minimum_exposure)
        object.__setattr__(self, "window_area_nm2", window_area_nm2)
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "representative_point_ids", representative_point_ids)
        object.__setattr__(self, "spatial_calibration_fingerprint", calibration_fingerprint)
        object.__setattr__(self, "registration_fingerprint", registration_fingerprint)
        object.__setattr__(self, "point_coordinate_fingerprint", coordinate_fingerprint)
        object.__setattr__(self, "window_origin_nm", window_origin_nm)


@dataclass(frozen=True)
class _PairCorrelationFrameContext:
    frame_index: int
    representative_point_ids: tuple[str, ...]
    spatial_calibration_fingerprint: str
    registration_fingerprint: str
    point_coordinate_fingerprint: str
    window_origin_nm: tuple[float, float]


def compute_pair_correlation(
    points_xy_nm: object,
    *,
    point_ids: Sequence[str],
    point_frame_indices: Sequence[int],
    first_shell_graph: FirstShellGraph,
    frame_index: int,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
    window_geometry: Literal["rectangular", "irregular"],
    window_size_nm: tuple[float, float] | None = None,
    valid_fov_mask: object | None = None,
    valid_fov_pixel_size_nm: tuple[float, float] | None = None,
    window_origin_nm: tuple[float, float] = (0.0, 0.0),
) -> PairCorrelationResult:
    """Compute one-frame g(r) from registered, representative points in sample_nm."""

    if settings is None:
        settings = MolecularM6OrientationAnalysisSettings()
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    points = np.asarray(points_xy_nm, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 2:
        raise ValueError("points_xy_nm must have shape [N, 2].")
    if not bool(np.all(np.isfinite(points))):
        raise ValueError("points_xy_nm must contain only finite coordinates.")
    normalized_point_ids = tuple(point_ids)
    normalized_frame_index = _as_non_negative_integer(frame_index, "frame_index")
    normalized_point_frame_indices = tuple(
        _as_non_negative_integer(value, "point_frame_indices")
        for value in point_frame_indices
    )
    if not isinstance(first_shell_graph, FirstShellGraph):
        raise TypeError("first_shell_graph must be a FirstShellGraph.")
    if len(normalized_point_ids) != len(points):
        raise ValueError("point_ids must contain one ID per input point.")
    if len(normalized_point_frame_indices) != len(points):
        raise ValueError("point_frame_indices must contain one value per input point.")
    if any(value != normalized_frame_index for value in normalized_point_frame_indices):
        raise ValueError("Pair correlation input must contain points from exactly one frame.")
    if (
        normalized_point_ids != first_shell_graph.point_ids
        or len(points) != first_shell_graph.point_count
    ):
        raise ValueError("first_shell_graph must match input point IDs and order.")
    _validate_graph_settings(first_shell_graph, settings)
    _validate_graph_coordinates(points, first_shell_graph)
    representative_indices = tuple(
        index
        for index, point_id in enumerate(normalized_point_ids)
        if first_shell_graph.representative_source_ids[index] == point_id
    )
    representative_points = points[np.asarray(representative_indices, dtype=np.int64)]
    representative_point_ids = tuple(
        normalized_point_ids[index] for index in representative_indices
    )
    origin_nm = _normalize_finite_pair(window_origin_nm, "window_origin_nm")
    context = _PairCorrelationFrameContext(
        frame_index=normalized_frame_index,
        representative_point_ids=representative_point_ids,
        spatial_calibration_fingerprint=first_shell_graph.spatial_calibration_fingerprint,
        registration_fingerprint=first_shell_graph.registration_fingerprint,
        point_coordinate_fingerprint=first_shell_graph.point_coordinate_fingerprint,
        window_origin_nm=origin_nm,
    )
    geometry = str(window_geometry).strip().lower()
    if geometry not in ("rectangular", "irregular"):
        raise ValueError(f"Unsupported window_geometry: {window_geometry!r}.")
    edges = pair_correlation_bin_edges(settings.gr_bin_width_nm, settings.gr_max_nm)
    distances = (
        pdist(representative_points, metric="euclidean")
        if len(representative_points) > 1
        else np.empty(0)
    )
    observed, _edges = np.histogram(distances, bins=np.asarray(edges, dtype=np.float64))
    point_count = int(len(representative_points))

    if geometry == "irregular" and (
        valid_fov_mask is None or valid_fov_pixel_size_nm is None
    ):
        return _build_result(
            edges=edges,
            observed=tuple(int(value) for value in observed),
            exposure=(float("nan"),) * (len(edges) - 1),
            point_count=point_count,
            minimum_exposure=settings.gr_min_expected_pair_exposure,
            window_area_nm2=None,
            window_geometry_status="unsupported_window_geometry",
            context=context,
        )
    if geometry == "rectangular":
        width_nm, height_nm = _normalize_window_size(window_size_nm)
        _validate_points_in_rectangular_window(
            representative_points,
            origin_nm=origin_nm,
            window_size_nm=(width_nm, height_nm),
        )
        overlap_integrals = rectangular_annulus_overlap_integrals(
            width_nm,
            height_nm,
            edges,
        )
        area_nm2 = width_nm * height_nm
        geometry_status: PairCorrelationWindowGeometryStatus = (
            "rectangular_translation_correction"
        )
    else:
        mask = _normalize_valid_fov_mask(valid_fov_mask)
        pixel_size_nm = _normalize_pixel_size(valid_fov_pixel_size_nm)
        _validate_points_in_mask(
            representative_points,
            mask=mask,
            origin_nm=origin_nm,
            pixel_size_nm=pixel_size_nm,
        )
        area_nm2, overlap_integrals = masked_annulus_overlap_integrals(
            mask,
            pixel_size_nm=pixel_size_nm,
            edges_nm=edges,
        )
        geometry_status = "irregular_mask_autocorrelation"

    density_factor = point_count * (point_count - 1) / (2.0 * area_nm2**2)
    exposure = tuple(density_factor * integral for integral in overlap_integrals)
    return _build_result(
        edges=edges,
        observed=tuple(int(value) for value in observed),
        exposure=exposure,
        point_count=point_count,
        minimum_exposure=settings.gr_min_expected_pair_exposure,
        window_area_nm2=area_nm2,
        window_geometry_status=geometry_status,
        context=context,
    )


def _build_result(
    *,
    edges: tuple[float, ...],
    observed: tuple[int, ...],
    exposure: tuple[float, ...],
    point_count: int,
    minimum_exposure: float,
    window_area_nm2: float | None,
    window_geometry_status: PairCorrelationWindowGeometryStatus,
    context: _PairCorrelationFrameContext,
) -> PairCorrelationResult:
    unsupported = window_geometry_status == "unsupported_window_geometry"
    g_values: list[float] = []
    statuses: list[PairCorrelationBinStatus] = []
    contributions: list[int] = []
    for count, expected in zip(observed, exposure):
        if unsupported:
            g_values.append(float("nan"))
            statuses.append("unsupported_window_geometry")
            contributions.append(0)
        elif isfinite(expected) and expected >= minimum_exposure:
            g_values.append(float(count / expected))
            statuses.append("valid")
            contributions.append(int(expected > 0.0))
        else:
            g_values.append(float("nan"))
            statuses.append("insufficient_exposure")
            contributions.append(int(isfinite(expected) and expected > 0.0))
    return PairCorrelationResult(
        bin_edges_nm=edges,
        bin_centers_nm=tuple((left + right) / 2.0 for left, right in zip(edges, edges[1:])),
        g_r=tuple(g_values),
        observed_unordered_pair_count=observed,
        expected_pair_exposure=exposure,
        bin_status=tuple(statuses),
        contributing_frame_count=tuple(contributions),
        point_count=point_count,
        total_unordered_pair_count=point_count * (point_count - 1) // 2,
        min_expected_pair_exposure=minimum_exposure,
        window_area_nm2=window_area_nm2,
        window_geometry_status=window_geometry_status,
        frame_index=context.frame_index,
        representative_point_ids=context.representative_point_ids,
        coordinate_frame="sample_nm",
        spatial_calibration_fingerprint=context.spatial_calibration_fingerprint,
        registration_fingerprint=context.registration_fingerprint,
        point_coordinate_fingerprint=context.point_coordinate_fingerprint,
        window_origin_nm=context.window_origin_nm,
    )


def _normalize_window_size(
    window_size_nm: tuple[float, float] | None,
) -> tuple[float, float]:
    return _normalize_positive_pair(window_size_nm, "window_size_nm")


def _normalize_valid_fov_mask(valid_fov_mask: object) -> np.ndarray:
    mask = np.asarray(valid_fov_mask)
    if mask.ndim != 2 or 0 in mask.shape:
        raise ValueError("valid_fov_mask must be a non-empty two-dimensional mask.")
    if not bool(np.all(np.isfinite(mask))):
        raise ValueError("valid_fov_mask must contain only finite values.")
    if not bool(np.all((mask == 0) | (mask == 1))):
        raise ValueError("valid_fov_mask must be binary.")
    normalized = np.asarray(mask, dtype=bool)
    if not bool(np.any(normalized)):
        raise ValueError("valid_fov_mask must contain at least one valid pixel.")
    return normalized


def _normalize_pixel_size(
    pixel_size_nm: tuple[float, float] | None,
) -> tuple[float, float]:
    return _normalize_positive_pair(pixel_size_nm, "valid_fov_pixel_size_nm")


def _normalize_positive_pair(
    values: tuple[float, float] | None,
    field_name: str,
) -> tuple[float, float]:
    if values is None:
        raise ValueError(f"{field_name} is required.")
    try:
        normalized = tuple(float(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain two numeric values.") from exc
    if len(normalized) != 2:
        raise ValueError(f"{field_name} must contain exactly two values.")
    if any(not isfinite(value) or value <= 0.0 for value in normalized):
        raise ValueError(f"{field_name} values must be finite and positive.")
    return normalized


def _normalize_finite_pair(
    values: tuple[float, float],
    field_name: str,
) -> tuple[float, float]:
    try:
        normalized = tuple(float(value) for value in values)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain two numeric values.") from exc
    if len(normalized) != 2 or any(not isfinite(value) for value in normalized):
        raise ValueError(f"{field_name} must contain exactly two finite values.")
    return normalized


def _validate_graph_settings(
    graph: FirstShellGraph,
    settings: MolecularM6OrientationAnalysisSettings,
) -> None:
    graph_contract = (
        graph.duplicate_detection_enabled,
        graph.duplicate_max_distance_nm,
        graph.first_shell_r_min_nm,
        graph.first_shell_r_max_nm,
    )
    settings_contract = (
        settings.duplicate_detection_enabled,
        settings.duplicate_max_distance_nm,
        settings.first_shell_r_min_nm,
        settings.first_shell_r_max_nm,
    )
    if graph_contract != settings_contract:
        raise ValueError("first_shell_graph must use the supplied duplicate and shell settings.")


def _validate_graph_coordinates(points: np.ndarray, graph: FirstShellGraph) -> None:
    actual_fingerprint = point_coordinate_fingerprint(points, graph.point_ids)
    if actual_fingerprint != graph.point_coordinate_fingerprint:
        raise ValueError("first_shell_graph coordinate fingerprint must match points_xy_nm.")


def _validate_points_in_rectangular_window(
    points: np.ndarray,
    *,
    origin_nm: tuple[float, float],
    window_size_nm: tuple[float, float],
) -> None:
    if not len(points):
        return
    origin_x, origin_y = origin_nm
    width_nm, height_nm = window_size_nm
    tolerance = 1e-12 * max(1.0, width_nm, height_nm)
    outside = (
        (points[:, 0] < origin_x - tolerance)
        | (points[:, 0] > origin_x + width_nm + tolerance)
        | (points[:, 1] < origin_y - tolerance)
        | (points[:, 1] > origin_y + height_nm + tolerance)
    )
    if bool(np.any(outside)):
        raise ValueError("Representative points must not lie outside the rectangular window.")


def _validate_points_in_mask(
    points: np.ndarray,
    *,
    mask: np.ndarray,
    origin_nm: tuple[float, float],
    pixel_size_nm: tuple[float, float],
) -> None:
    if not len(points):
        return
    origin_x, origin_y = origin_nm
    pixel_size_x, pixel_size_y = pixel_size_nm
    column_coordinates = (points[:, 0] - origin_x) / pixel_size_x
    row_coordinates = (points[:, 1] - origin_y) / pixel_size_y
    inside_bounds = (
        (column_coordinates >= 0.0)
        & (column_coordinates < mask.shape[1])
        & (row_coordinates >= 0.0)
        & (row_coordinates < mask.shape[0])
    )
    if not bool(np.all(inside_bounds)):
        raise ValueError("Representative points must not lie outside valid_fov_mask.")
    columns = np.floor(column_coordinates).astype(np.int64)
    rows = np.floor(row_coordinates).astype(np.int64)
    if not bool(np.all(mask[rows, columns])):
        raise ValueError("Representative points must not lie outside valid_fov_mask.")


def _as_finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric.")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be numeric.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _as_positive_float(value: object, field_name: str) -> float:
    normalized = _as_finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _as_non_negative_integer(value: object, field_name: str) -> int:
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


def _as_non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")
    return normalized
