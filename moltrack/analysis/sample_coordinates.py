from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from math import cos, isfinite, radians, sin

import numpy as np

from moltrack.core import MolecularCentroid, MolTrackImageSeries

from ._oriented_rectangle import normalize_oriented_rectangle


SAMPLE_COORDINATE_TRANSFORM_VERSION = "moltrack-sample-nm-v1"


@dataclass(frozen=True)
class MolecularSampleCoordinates:
    """Centroids and valid FOV expressed in canonical sample coordinates."""

    frame_index: int
    source_view: str
    point_source_ids: tuple[str, ...]
    point_source_kinds: tuple[str, ...]
    source_points_xy_px: tuple[tuple[float, float], ...]
    points_xy_nm: tuple[tuple[float, float], ...]
    distance_to_valid_fov_boundary_nm: tuple[float, ...]
    valid_fov_polygon_xy_nm: tuple[tuple[float, float], ...]
    plot_canvas_polygon_xy_nm: tuple[tuple[float, float], ...]
    window_side_lengths_nm: tuple[float, float]
    coordinate_transform_fingerprint: str
    spatial_calibration_fingerprint: str
    registration_fingerprint: str
    scan_angle_deg: float
    scan_angle_missing_qc: bool
    coordinate_frame: str = "sample_nm"
    orientation_reference: str = "+x_sample_axis"

    def __post_init__(self) -> None:
        if isinstance(self.frame_index, bool) or int(self.frame_index) < 0:
            raise ValueError("frame_index must be a non-negative integer.")
        source_view = str(self.source_view).strip()
        if source_view not in {"raw", "expanded_aligned"}:
            raise ValueError("Unsupported source_view.")
        if self.coordinate_frame != "sample_nm":
            raise ValueError("coordinate_frame must be 'sample_nm'.")
        if self.orientation_reference not in {
            "+x_sample_axis",
            "scan_x_axis_assumed_sample_x",
        }:
            raise ValueError("Unsupported orientation_reference.")
        if not isinstance(self.scan_angle_missing_qc, bool):
            raise TypeError("scan_angle_missing_qc must be a boolean.")
        if self.scan_angle_missing_qc != (
            self.orientation_reference == "scan_x_axis_assumed_sample_x"
        ):
            raise ValueError("Missing scan-angle QC must determine orientation_reference.")
        point_source_ids = tuple(self.point_source_ids)
        if any(not isinstance(value, str) or not value for value in point_source_ids):
            raise TypeError("point_source_ids must contain non-empty strings.")
        if len(set(point_source_ids)) != len(point_source_ids):
            raise ValueError("point_source_ids must be unique.")
        point_source_kinds = tuple(self.point_source_kinds)
        if any(not isinstance(value, str) or not value for value in point_source_kinds):
            raise TypeError("point_source_kinds must contain non-empty strings.")
        source_points = tuple(
            _finite_pair(point, "source_points_xy_px")
            for point in self.source_points_xy_px
        )
        points = tuple(_finite_pair(point, "points_xy_nm") for point in self.points_xy_nm)
        if not len(point_source_ids) == len(point_source_kinds) == len(source_points) == len(points):
            raise ValueError("Point IDs, kinds, source pixels, and sample coordinates must align.")
        distances = tuple(
            _finite_float(value, "distance_to_valid_fov_boundary_nm")
            for value in self.distance_to_valid_fov_boundary_nm
        )
        if len(distances) != len(points):
            raise ValueError("Boundary distances must align with points_xy_nm.")
        polygon = tuple(
            _finite_pair(point, "valid_fov_polygon_xy_nm")
            for point in self.valid_fov_polygon_xy_nm
        )
        if len(polygon) != 4:
            raise ValueError("The transformed rectangular valid FOV must have four vertices.")
        plot_polygon = tuple(
            _finite_pair(point, "plot_canvas_polygon_xy_nm")
            for point in self.plot_canvas_polygon_xy_nm
        )
        if len(plot_polygon) != 4:
            raise ValueError("The transformed plot canvas must have four vertices.")
        side_lengths = tuple(
            _positive_finite(value, "window_side_lengths_nm")
            for value in self.window_side_lengths_nm
        )
        if len(side_lengths) != 2:
            raise ValueError("window_side_lengths_nm must contain two values.")
        polygon = normalize_oriented_rectangle(
            polygon,
            side_lengths=side_lengths,
            field_name="valid_fov_polygon_xy_nm",
        )
        fingerprints = (
            self.coordinate_transform_fingerprint,
            self.spatial_calibration_fingerprint,
            self.registration_fingerprint,
        )
        if any(not isinstance(value, str) or not value for value in fingerprints):
            raise TypeError("Coordinate fingerprints must be non-empty strings.")
        scan_angle = float(self.scan_angle_deg)
        if not isfinite(scan_angle):
            raise ValueError("scan_angle_deg must be finite.")
        object.__setattr__(self, "frame_index", int(self.frame_index))
        object.__setattr__(self, "source_view", source_view)
        object.__setattr__(self, "point_source_ids", point_source_ids)
        object.__setattr__(self, "point_source_kinds", point_source_kinds)
        object.__setattr__(self, "source_points_xy_px", source_points)
        object.__setattr__(self, "points_xy_nm", points)
        object.__setattr__(self, "distance_to_valid_fov_boundary_nm", distances)
        object.__setattr__(self, "valid_fov_polygon_xy_nm", polygon)
        object.__setattr__(self, "plot_canvas_polygon_xy_nm", plot_polygon)
        object.__setattr__(self, "window_side_lengths_nm", side_lengths)
        object.__setattr__(self, "scan_angle_deg", scan_angle)

    @property
    def x_range_nm(self) -> tuple[float, float]:
        values = tuple(point[0] for point in self.plot_canvas_polygon_xy_nm)
        return min(values), max(values)

    @property
    def y_range_nm(self) -> tuple[float, float]:
        values = tuple(point[1] for point in self.plot_canvas_polygon_xy_nm)
        return min(values), max(values)

    @property
    def invalid_position_point_ids(self) -> tuple[str, ...]:
        return tuple(
            point_id
            for point_id, distance in zip(
                self.point_source_ids,
                self.distance_to_valid_fov_boundary_nm,
            )
            if distance < 0.0
        )


def build_molecular_sample_coordinates(
    series: MolTrackImageSeries,
    centroids: tuple[MolecularCentroid, ...] | list[MolecularCentroid],
    *,
    frame_index: int,
    source_view: str,
) -> MolecularSampleCoordinates:
    """Transform one Position Analysis centroid set into ``sample_nm``."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    frame_index = int(frame_index)
    series.get_frame(frame_index)
    source_view = str(source_view).strip()
    centroids = tuple(centroids)
    for centroid in centroids:
        if not isinstance(centroid, MolecularCentroid):
            raise TypeError("centroids must contain MolecularCentroid instances.")
        if centroid.frame_index != frame_index or centroid.source_view != source_view:
            raise ValueError("Centroids must match the requested frame and source_view.")
    context = _source_context(
        series,
        frame_index=frame_index,
        source_view=source_view,
    )
    scale_x, scale_y = _required_pixel_size_nm(context.metadata)
    scan_angle_deg, scan_angle_missing_qc = _scan_angle(series.metadata)
    orientation_reference = (
        "scan_x_axis_assumed_sample_x"
        if scan_angle_missing_qc
        else "+x_sample_axis"
    )
    spatial_payload = {
        "pixel_size_nm": [scale_x, scale_y],
        "scan_angle_deg": scan_angle_deg,
        "scan_angle_missing_qc": scan_angle_missing_qc,
    }
    spatial_fingerprint = _fingerprint(spatial_payload)
    registration_fingerprint = (
        "unregistered"
        if source_view == "raw"
        else _fingerprint(
            {
                **context.registration_payload,
                "registration_result": _registration_provenance(
                    series,
                    frame_index=frame_index,
                ),
            }
        )
    )
    transform_fingerprint = _fingerprint(
        {
            "version": SAMPLE_COORDINATE_TRANSFORM_VERSION,
            "frame_index": frame_index,
            "source_view": source_view,
            "raw_frame_shape": list(series.frame_shape),
            "source_frame_shape": list(context.source_shape),
            "spatial_calibration_fingerprint": spatial_fingerprint,
            "registration_fingerprint": registration_fingerprint,
        }
    )

    height, width = context.source_shape
    raw_height = series.frame_shape[0]
    origin_x, origin_y = context.canvas_origin_px
    plot_x_min_nm = -origin_x * scale_x
    plot_x_max_nm = (width - origin_x) * scale_x
    plot_y_min_nm = (raw_height - (height - origin_y)) * scale_y
    plot_y_max_nm = (raw_height + origin_y) * scale_y
    local_plot_polygon = (
        (plot_x_min_nm, plot_y_min_nm),
        (plot_x_max_nm, plot_y_min_nm),
        (plot_x_max_nm, plot_y_max_nm),
        (plot_x_min_nm, plot_y_max_nm),
    )
    observed_origin_x, observed_origin_y = context.observed_origin_canvas_px
    observed_height, observed_width = context.observed_shape
    observed_x_min_ref = observed_origin_x - origin_x
    observed_x_max_ref = observed_x_min_ref + observed_width
    observed_y_top_ref = observed_origin_y - origin_y
    observed_y_bottom_ref = observed_y_top_ref + observed_height
    x_min_nm = observed_x_min_ref * scale_x
    x_max_nm = observed_x_max_ref * scale_x
    y_min_nm = (raw_height - observed_y_bottom_ref) * scale_y
    y_max_nm = (raw_height - observed_y_top_ref) * scale_y
    local_valid_fov_polygon = (
        (x_min_nm, y_min_nm),
        (x_max_nm, y_min_nm),
        (x_max_nm, y_max_nm),
        (x_min_nm, y_max_nm),
    )
    rotation = _rotation_matrix(scan_angle_deg)
    polygon = _rotate_points(local_valid_fov_polygon, rotation)
    plot_polygon = _rotate_points(local_plot_polygon, rotation)

    local_points = tuple(
        (
            (centroid.x_px - origin_x) * scale_x,
            (raw_height - (centroid.y_px - origin_y)) * scale_y,
        )
        for centroid in centroids
    )
    points = _rotate_points(local_points, rotation)
    distances = tuple(
        min(
            point[0] - x_min_nm,
            x_max_nm - point[0],
            point[1] - y_min_nm,
            y_max_nm - point[1],
        )
        for point in local_points
    )
    return MolecularSampleCoordinates(
        frame_index=frame_index,
        source_view=source_view,
        point_source_ids=tuple(centroid.source_id for centroid in centroids),
        point_source_kinds=tuple(centroid.source_kind for centroid in centroids),
        source_points_xy_px=tuple(
            (centroid.x_px, centroid.y_px) for centroid in centroids
        ),
        points_xy_nm=points,
        distance_to_valid_fov_boundary_nm=distances,
        valid_fov_polygon_xy_nm=polygon,
        plot_canvas_polygon_xy_nm=plot_polygon,
        window_side_lengths_nm=(observed_width * scale_x, observed_height * scale_y),
        coordinate_transform_fingerprint=transform_fingerprint,
        spatial_calibration_fingerprint=spatial_fingerprint,
        registration_fingerprint=registration_fingerprint,
        scan_angle_deg=scan_angle_deg,
        scan_angle_missing_qc=scan_angle_missing_qc,
        orientation_reference=orientation_reference,
    )


@dataclass(frozen=True)
class _SampleSourceContext:
    source_shape: tuple[int, int]
    canvas_origin_px: tuple[float, float]
    observed_origin_canvas_px: tuple[float, float]
    observed_shape: tuple[int, int]
    metadata: object
    registration_payload: dict[str, object]


def _source_context(
    series: MolTrackImageSeries,
    *,
    frame_index: int,
    source_view: str,
) -> _SampleSourceContext:
    if source_view == "raw":
        return _SampleSourceContext(
            source_shape=series.frame_shape,
            canvas_origin_px=(0.0, 0.0),
            observed_origin_canvas_px=(0.0, 0.0),
            observed_shape=series.frame_shape,
            metadata=series.metadata,
            registration_payload={"source_view": "raw"},
        )
    if source_view != "expanded_aligned":
        raise ValueError(f"Unsupported source_view: {source_view!r}.")
    stack = series.expanded_aligned_stack
    if stack is None:
        raise ValueError("expanded_aligned source_view requires an expanded_aligned_stack.")
    frames = np.asarray(getattr(stack, "frames", None))
    if frames.ndim != 3 or frames.shape[0] != series.frame_count:
        raise ValueError("expanded_aligned_stack frames must match the working series.")
    padding = tuple(int(value) for value in getattr(stack, "padding_ltrb", (0, 0, 0, 0)))
    canvas_offset_value = getattr(stack, "canvas_offset_xy", None)
    if canvas_offset_value is None:
        canvas_offset_value = (padding[0], padding[1])
    canvas_offset = _finite_pair(
        canvas_offset_value,
        "expanded_aligned_stack.canvas_offset_xy",
    )
    frame_origins = np.asarray(getattr(stack, "frame_origins_xy", None), dtype=np.float64)
    if frame_origins.shape != (series.frame_count, 2) or not np.all(np.isfinite(frame_origins)):
        raise ValueError("expanded_aligned_stack frame_origins_xy must match the series.")
    return _SampleSourceContext(
        source_shape=(int(frames.shape[1]), int(frames.shape[2])),
        canvas_origin_px=canvas_offset,
        observed_origin_canvas_px=tuple(float(value) for value in frame_origins[frame_index]),
        observed_shape=series.frame_shape,
        metadata=getattr(stack, "metadata", series.metadata),
        registration_payload={
            "source_view": source_view,
            "canvas_offset_xy": list(canvas_offset),
            "frame_origin_xy": [float(value) for value in frame_origins[frame_index]],
            "padding_ltrb": list(padding),
        },
    )


def _required_pixel_size_nm(metadata: object) -> tuple[float, float]:
    getter = getattr(metadata, "get_pixel_size_nm", None)
    values = None if not callable(getter) else getter()
    try:
        scale_x, scale_y = _finite_pair(values, "metadata pixel size")
    except ValueError as exc:
        raise ValueError(
            "M6 orientation analysis requires positive nm-per-pixel metadata."
        ) from exc
    if scale_x <= 0.0 or scale_y <= 0.0:
        raise ValueError("M6 orientation analysis requires positive nm-per-pixel metadata.")
    return scale_x, scale_y


def _registration_provenance(
    series: MolTrackImageSeries,
    *,
    frame_index: int,
) -> dict[str, object]:
    results = series.registration_results
    if results is None:
        return {"available": False}
    settings = getattr(results, "settings", None)
    get_result = getattr(results, "get_result", None)
    frame_result = get_result(frame_index) if callable(get_result) else None
    return {
        "available": True,
        "backend": getattr(settings, "backend", None),
        "reference_strategy": getattr(settings, "reference_strategy", None),
        "registration_view": getattr(settings, "registration_view", None),
        "backend_params": _json_compatible(getattr(settings, "backend_params", None)),
        "reference_frame_index": getattr(results, "reference_frame_index", None),
        "frame_result": None
        if frame_result is None
        else {
            "shift_xy": _json_compatible(getattr(frame_result, "shift_xy", None)),
            "method": getattr(frame_result, "method", None),
            "quality_score": _json_compatible(
                getattr(frame_result, "quality_score", None)
            ),
            "status": getattr(frame_result, "status", None),
        },
    }


def _scan_angle(metadata: object) -> tuple[float, bool]:
    value = getattr(metadata, "scan_angle_deg", None)
    if value is None:
        return 0.0, True
    try:
        angle = float(value)
    except (TypeError, ValueError):
        return 0.0, True
    if not isfinite(angle):
        return 0.0, True
    if angle != 0.0:
        return angle, False
    raw_header = getattr(metadata, "raw_header", None)
    if not isinstance(raw_header, Mapping):
        return 0.0, True
    general_info = raw_header.get("General Info")
    if not isinstance(general_info, Mapping) or "Angle" not in general_info:
        return 0.0, True
    try:
        header_angle = float(general_info["Angle"])
    except (TypeError, ValueError):
        return 0.0, True
    return (angle, False) if isfinite(header_angle) else (0.0, True)


def _rotation_matrix(angle_deg: float) -> np.ndarray:
    angle_rad = radians(angle_deg)
    return np.asarray(
        ((cos(angle_rad), -sin(angle_rad)), (sin(angle_rad), cos(angle_rad))),
        dtype=np.float64,
    )


def _rotate_points(
    points: tuple[tuple[float, float], ...],
    rotation: np.ndarray,
) -> tuple[tuple[float, float], ...]:
    if not points:
        return ()
    rotated = np.asarray(points, dtype=np.float64) @ rotation.T
    rotated[np.abs(rotated) < 1e-15] = 0.0
    return tuple((float(point[0]), float(point[1])) for point in rotated)


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _json_compatible(value: object) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if isfinite(value) else None
    if isinstance(value, np.ndarray):
        return _json_compatible(value.tolist())
    if isinstance(value, np.generic):
        return _json_compatible(value.item())
    if isinstance(value, Mapping):
        return {str(key): _json_compatible(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_compatible(item) for item in value]
    return str(value)


def _finite_pair(value: object, field_name: str) -> tuple[float, float]:
    try:
        first, second = (float(item) for item in value)  # type: ignore[union-attr]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must contain two finite values.") from exc
    if not isfinite(first) or not isfinite(second):
        raise ValueError(f"{field_name} must contain two finite values.")
    return first, second


def _non_negative_finite(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative and finite.")
    return normalized


def _finite_float(value: object, field_name: str) -> float:
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _positive_finite(value: object, field_name: str) -> float:
    normalized = _non_negative_finite(value, field_name)
    if normalized == 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized
