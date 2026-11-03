from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import isclose, isfinite
from typing import Literal

import numpy as np
from scipy.spatial.distance import pdist

from ._coordinate_fingerprint import point_coordinate_fingerprint
from ._pair_correlation_binning import pair_correlation_bin_edges
from ._oriented_rectangle import normalize_oriented_rectangle
from ._pair_correlation_validation import (
    PAIR_CORRELATION_WINDOW_STATUSES,
    PairCorrelationBinStatus,
    PairCorrelationWindowGeometryStatus,
    as_finite_float as _as_finite_float,
    as_non_empty_string as _as_non_empty_string,
    as_non_negative_integer as _as_non_negative_integer,
    as_positive_float as _as_positive_float,
    normalize_pair_correlation_bins,
)
from .first_shell_graph import FirstShellGraph
from .m6_settings import MolecularM6OrientationAnalysisSettings
from ._orientation_footprint_geometry import (
    point_in_polygon_window,
)
from ._pair_correlation_windows import (
    masked_annulus_overlap_integrals,
    rectangular_annulus_overlap_integrals,
)


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
    window_size_nm: tuple[float, float] | None = None
    window_polygon_xy_nm: tuple[tuple[float, float], ...] | None = None

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
        window_size_nm = (
            None
            if self.window_size_nm is None
            else _normalize_positive_pair(self.window_size_nm, "window_size_nm")
        )
        window_polygon_xy_nm = (
            None
            if self.window_polygon_xy_nm is None or window_size_nm is None
            else normalize_oriented_rectangle(
                self.window_polygon_xy_nm,
                side_lengths=window_size_nm,
                field_name="window_polygon_xy_nm",
            )
        )
        if self.window_polygon_xy_nm is not None and window_size_nm is None:
            raise ValueError("window_polygon_xy_nm requires window_size_nm.")
        if self.window_geometry_status not in PAIR_CORRELATION_WINDOW_STATUSES:
            raise ValueError("Unsupported window_geometry_status.")
        bins = normalize_pair_correlation_bins(
            bin_edges_nm=self.bin_edges_nm,
            bin_centers_nm=self.bin_centers_nm,
            observed_unordered_pair_count=self.observed_unordered_pair_count,
            expected_pair_exposure=self.expected_pair_exposure,
            g_r=self.g_r,
            bin_status=self.bin_status,
            contributing_frame_count=self.contributing_frame_count,
            total_unordered_pair_count=total_pair_count,
            maximum_contributing_frames=1,
            require_finite_exposure=False,
        )
        edges = bins.bin_edges_nm
        centers = bins.bin_centers_nm
        observed = bins.observed_unordered_pair_count
        exposure = bins.expected_pair_exposure
        g_values = bins.g_r
        statuses = bins.bin_status
        contributions = bins.contributing_frame_count

        unsupported = self.window_geometry_status == "unsupported_window_geometry"
        if unsupported:
            if self.window_area_nm2 is not None:
                raise ValueError("Unsupported window geometry cannot have a window area.")
            window_area_nm2 = None
        else:
            window_area_nm2 = _as_positive_float(self.window_area_nm2, "window_area_nm2")
        if (
            self.window_geometry_status == "rectangular_translation_correction"
            and window_size_nm is not None
            and not np.isclose(
                window_size_nm[0] * window_size_nm[1],
                window_area_nm2,
                rtol=1e-12,
                atol=1e-12,
            )
        ):
            raise ValueError("Rectangular window_size_nm must match window_area_nm2.")
        if (
            self.window_geometry_status != "rectangular_translation_correction"
            and window_size_nm is not None
        ):
            raise ValueError("window_size_nm is only supported for rectangular windows.")
        if window_polygon_xy_nm is not None:
            if self.window_geometry_status != "rectangular_translation_correction":
                raise ValueError(
                    "window_polygon_xy_nm is only supported for rectangular windows."
                )
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
        object.__setattr__(self, "window_size_nm", window_size_nm)
        object.__setattr__(self, "window_polygon_xy_nm", window_polygon_xy_nm)


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
    valid_fov_polygon_xy_nm: Sequence[tuple[float, float]] | None = None,
    excluded_point_ids: Sequence[str] = (),
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
    excluded_ids = tuple(excluded_point_ids)
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
    if (
        len(set(excluded_ids)) != len(excluded_ids)
        or any(point_id not in normalized_point_ids for point_id in excluded_ids)
    ):
        raise ValueError("excluded_point_ids must be unique input point IDs.")
    excluded_id_set = set(excluded_ids)
    _validate_graph_settings(first_shell_graph, settings)
    _validate_graph_coordinates(points, first_shell_graph)
    representative_indices = tuple(
        index
        for index, point_id in enumerate(normalized_point_ids)
        if (
            first_shell_graph.representative_source_ids[index] == point_id
            and point_id not in excluded_id_set
        )
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
            window_size_nm=None,
            window_polygon_xy_nm=None,
            context=context,
        )
    if geometry == "rectangular":
        width_nm, height_nm = _normalize_window_size(window_size_nm)
        window_polygon_xy_nm = (
            None
            if valid_fov_polygon_xy_nm is None
            else normalize_oriented_rectangle(
                valid_fov_polygon_xy_nm,
                side_lengths=(width_nm, height_nm),
                field_name="valid_fov_polygon_xy_nm",
            )
        )
        if window_polygon_xy_nm is None:
            _validate_points_in_rectangular_window(
                representative_points,
                origin_nm=origin_nm,
                window_size_nm=(width_nm, height_nm),
            )
        else:
            if not np.allclose(
                origin_nm,
                window_polygon_xy_nm[0],
                rtol=1e-10,
                atol=1e-10 * max(width_nm, height_nm, 1.0),
            ):
                raise ValueError(
                    "window_origin_nm must equal the first valid FOV polygon vertex."
                )
            _validate_points_in_polygon(
                representative_points,
                window_polygon_xy_nm,
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
        if valid_fov_polygon_xy_nm is not None:
            raise ValueError("valid_fov_polygon_xy_nm requires rectangular geometry.")
        window_polygon_xy_nm = None
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

    exposure = _pair_exposure(
        point_count=point_count,
        window_area_nm2=area_nm2,
        overlap_integrals=overlap_integrals,
    )
    return _build_result(
        edges=edges,
        observed=tuple(int(value) for value in observed),
        exposure=exposure,
        point_count=point_count,
        minimum_exposure=settings.gr_min_expected_pair_exposure,
        window_area_nm2=area_nm2,
        window_geometry_status=geometry_status,
        window_size_nm=(width_nm, height_nm) if geometry == "rectangular" else None,
        window_polygon_xy_nm=window_polygon_xy_nm,
        context=context,
    )


def validate_pair_correlation_result_context(
    result: PairCorrelationResult,
    *,
    first_shell_graph: FirstShellGraph,
    frame_index: int,
    settings: MolecularM6OrientationAnalysisSettings,
    window_size_nm: tuple[float, float],
    window_origin_nm: tuple[float, float],
    valid_fov_polygon_xy_nm: tuple[tuple[float, float], ...],
    excluded_point_ids: Sequence[str] = (),
) -> None:
    """Verify that a stored g(r) result belongs to one graph and FOV context."""

    excluded_ids = set(excluded_point_ids)
    representative_ids = tuple(
        point_id
        for point_id, representative_id in zip(
            first_shell_graph.point_ids,
            first_shell_graph.representative_source_ids,
        )
        if point_id == representative_id and point_id not in excluded_ids
    )
    expected_context = (
        int(frame_index),
        representative_ids,
        first_shell_graph.spatial_calibration_fingerprint,
        first_shell_graph.registration_fingerprint,
        first_shell_graph.point_coordinate_fingerprint,
        valid_fov_polygon_xy_nm,
        window_size_nm,
        window_origin_nm,
        "rectangular_translation_correction",
    )
    actual_context = (
        result.frame_index,
        result.representative_point_ids,
        result.spatial_calibration_fingerprint,
        result.registration_fingerprint,
        result.point_coordinate_fingerprint,
        result.window_polygon_xy_nm,
        result.window_size_nm,
        result.window_origin_nm,
        result.window_geometry_status,
    )
    if actual_context != expected_context:
        raise ValueError("M6 g(r) must use this frame and valid FOV graph context.")
    expected_edges = pair_correlation_bin_edges(
        settings.gr_bin_width_nm,
        settings.gr_max_nm,
    )
    width_nm, height_nm = window_size_nm
    expected_exposure = _pair_exposure(
        point_count=len(representative_ids),
        window_area_nm2=width_nm * height_nm,
        overlap_integrals=rectangular_annulus_overlap_integrals(
            width_nm,
            height_nm,
            expected_edges,
        ),
    )
    if (
        result.bin_edges_nm != expected_edges
        or not isclose(
            result.min_expected_pair_exposure,
            settings.gr_min_expected_pair_exposure,
            rel_tol=1e-12,
            abs_tol=1e-12,
        )
        or len(result.expected_pair_exposure) != len(expected_exposure)
        or any(
            not isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
            for actual, expected in zip(
                result.expected_pair_exposure,
                expected_exposure,
            )
        )
    ):
        raise ValueError("M6 g(r) must use the supplied settings and exposure.")


def _pair_exposure(
    *,
    point_count: int,
    window_area_nm2: float,
    overlap_integrals: Sequence[float],
) -> tuple[float, ...]:
    density_factor = (
        point_count * (point_count - 1)
        / (2.0 * window_area_nm2**2)
    )
    return tuple(density_factor * integral for integral in overlap_integrals)


def _build_result(
    *,
    edges: tuple[float, ...],
    observed: tuple[int, ...],
    exposure: tuple[float, ...],
    point_count: int,
    minimum_exposure: float,
    window_area_nm2: float | None,
    window_geometry_status: PairCorrelationWindowGeometryStatus,
    window_size_nm: tuple[float, float] | None,
    window_polygon_xy_nm: tuple[tuple[float, float], ...] | None,
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
        window_size_nm=window_size_nm,
        window_polygon_xy_nm=window_polygon_xy_nm,
    )


def _normalize_window_size(
    window_size_nm: tuple[float, float] | None,
) -> tuple[float, float]:
    return _normalize_positive_pair(window_size_nm, "window_size_nm")


def _validate_points_in_polygon(
    points: np.ndarray,
    polygon: tuple[tuple[float, float], ...],
) -> None:
    coordinate_scale = max(
        1.0,
        *(abs(value) for point in polygon for value in point),
    )
    tolerance = 1e-10 * coordinate_scale
    if any(
        not point_in_polygon_window(point, (polygon,), tolerance=tolerance)
        for point in points
    ):
        raise ValueError("Representative points must lie inside valid FOV W.")


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
