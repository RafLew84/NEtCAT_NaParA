from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Literal, Mapping

from .first_shell_graph import OrientationReference
from .m6_settings import MolecularM6OrientationAnalysisSettings


M6_ORIENTATION_ALGORITHM_VERSION = "m6-orientation-domains-v1"

M6ValidationSourceView = Literal["raw", "expanded_aligned"]
M6ValidationStatus = Literal["complete", "blocked_graph_fallback"]
M6ValidationWarningCode = Literal[
    "high_unassigned_fraction",
    "graph_fallback",
    "delaunay_degeneracy",
    "unreliable_valid_fov",
]


@dataclass(frozen=True)
class M6HeadlessValidationFrame:
    """One calibrated frame requested by a versioned validation manifest."""

    frame_id: str
    physical_frame_id: str
    condition: str
    source_frame_index: int
    source_view: M6ValidationSourceView
    points_xy_nm: tuple[tuple[float, float], ...]
    point_ids: tuple[str, ...]
    window_size_nm: tuple[float, float]
    window_origin_nm: tuple[float, float] = (0.0, 0.0)
    invalid_position_point_ids: tuple[str, ...] = ()
    valid_fov_reliable: bool = True
    spatial_calibration_fingerprint: str = "unspecified_calibration"
    registration_fingerprint: str = "unregistered"
    orientation_reference: OrientationReference = "+x_sample_axis"

    def __post_init__(self) -> None:
        for field_name in (
            "frame_id",
            "physical_frame_id",
            "condition",
            "spatial_calibration_fingerprint",
            "registration_fingerprint",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_empty_string(getattr(self, field_name), field_name),
            )
        source_frame_index = _non_negative_int(
            self.source_frame_index,
            "source_frame_index",
        )
        if self.source_view not in {"raw", "expanded_aligned"}:
            raise ValueError(f"Unsupported source_view: {self.source_view!r}.")
        if self.orientation_reference not in {
            "+x_sample_axis",
            "scan_x_axis_assumed_sample_x",
        }:
            raise ValueError(
                f"Unsupported orientation_reference: {self.orientation_reference!r}."
            )
        if not isinstance(self.valid_fov_reliable, bool):
            raise TypeError("valid_fov_reliable must be a boolean.")

        points = _points_tuple(self.points_xy_nm)
        point_ids = tuple(self.point_ids)
        if len(point_ids) != len(points):
            raise ValueError("point_ids must contain one ID per point.")
        if any(not isinstance(point_id, str) or not point_id for point_id in point_ids):
            raise TypeError("point_ids must contain non-empty strings.")
        if len(set(point_ids)) != len(point_ids):
            raise ValueError("point_ids must be unique within a validation frame.")
        invalid_position_ids = tuple(self.invalid_position_point_ids)
        if (
            len(set(invalid_position_ids)) != len(invalid_position_ids)
            or any(
                not isinstance(point_id, str) or not point_id
                for point_id in invalid_position_ids
            )
        ):
            raise ValueError(
                "invalid_position_point_ids must contain unique non-empty IDs."
            )
        unknown_invalid_ids = sorted(set(invalid_position_ids) - set(point_ids))
        if unknown_invalid_ids:
            raise ValueError(
                "invalid_position_point_ids must refer to frame point_ids."
            )

        window_size = _positive_pair(self.window_size_nm, "window_size_nm")
        window_origin = _finite_pair(self.window_origin_nm, "window_origin_nm")
        origin_x, origin_y = window_origin
        width, height = window_size
        tolerance = max(width, height, 1.0) * 1e-12
        if any(
            not (
                origin_x - tolerance <= x <= origin_x + width + tolerance
                and origin_y - tolerance <= y <= origin_y + height + tolerance
            )
            for x, y in points
        ):
            raise ValueError("Validation points must lie inside rectangular valid FOV W.")

        object.__setattr__(self, "source_frame_index", source_frame_index)
        object.__setattr__(self, "points_xy_nm", points)
        object.__setattr__(self, "point_ids", point_ids)
        object.__setattr__(self, "invalid_position_point_ids", invalid_position_ids)
        object.__setattr__(self, "window_size_nm", window_size)
        object.__setattr__(self, "window_origin_nm", window_origin)

    @property
    def distance_to_valid_fov_boundary_nm(self) -> tuple[float | None, ...]:
        origin_x, origin_y = self.window_origin_nm
        width, height = self.window_size_nm
        invalid_ids = set(self.invalid_position_point_ids)
        return tuple(
            None
            if point_id in invalid_ids
            else min(
                x - origin_x,
                origin_x + width - x,
                y - origin_y,
                origin_y + height - y,
            )
            for point_id, (x, y) in zip(self.point_ids, self.points_xy_nm)
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "frame_id": self.frame_id,
            "physical_frame_id": self.physical_frame_id,
            "condition": self.condition,
            "source_frame_index": self.source_frame_index,
            "source_view": self.source_view,
            "points_xy_nm": [list(point) for point in self.points_xy_nm],
            "point_ids": list(self.point_ids),
            "window_size_nm": list(self.window_size_nm),
            "window_origin_nm": list(self.window_origin_nm),
            "invalid_position_point_ids": list(self.invalid_position_point_ids),
            "valid_fov_reliable": self.valid_fov_reliable,
            "spatial_calibration_fingerprint": self.spatial_calibration_fingerprint,
            "registration_fingerprint": self.registration_fingerprint,
            "orientation_reference": self.orientation_reference,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "M6HeadlessValidationFrame":
        if not isinstance(payload, Mapping):
            raise TypeError("Validation frame payload must be a mapping.")
        required = {
            "frame_id",
            "physical_frame_id",
            "condition",
            "source_frame_index",
            "source_view",
            "points_xy_nm",
            "window_size_nm",
            "valid_fov_reliable",
            "spatial_calibration_fingerprint",
            "registration_fingerprint",
        }
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"Missing validation frame fields: {', '.join(missing)}")
        frame_id = payload["frame_id"]
        raw_points = payload["points_xy_nm"]
        try:
            points = tuple(tuple(point) for point in raw_points)  # type: ignore[union-attr]
        except TypeError as exc:
            raise TypeError("points_xy_nm must be a sequence of coordinate pairs.") from exc
        raw_point_ids = payload.get("point_ids")
        if raw_point_ids is None:
            point_ids = tuple(
                f"{frame_id}:point:{index:04d}" for index in range(len(points))
            )
        else:
            try:
                point_ids = tuple(raw_point_ids)  # type: ignore[arg-type]
            except TypeError as exc:
                raise TypeError("point_ids must be a sequence.") from exc
        return cls(
            frame_id=frame_id,  # type: ignore[arg-type]
            physical_frame_id=payload["physical_frame_id"],  # type: ignore[arg-type]
            condition=payload["condition"],  # type: ignore[arg-type]
            source_frame_index=payload["source_frame_index"],  # type: ignore[arg-type]
            source_view=payload["source_view"],  # type: ignore[arg-type]
            points_xy_nm=points,  # type: ignore[arg-type]
            point_ids=point_ids,  # type: ignore[arg-type]
            window_size_nm=payload["window_size_nm"],  # type: ignore[arg-type]
            window_origin_nm=payload.get("window_origin_nm", (0.0, 0.0)),  # type: ignore[arg-type]
            invalid_position_point_ids=tuple(
                payload.get("invalid_position_point_ids", ())  # type: ignore[arg-type]
            ),
            valid_fov_reliable=payload["valid_fov_reliable"],  # type: ignore[arg-type]
            spatial_calibration_fingerprint=payload[
                "spatial_calibration_fingerprint"
            ],  # type: ignore[arg-type]
            registration_fingerprint=payload[
                "registration_fingerprint"
            ],  # type: ignore[arg-type]
            orientation_reference=payload.get(
                "orientation_reference",
                "+x_sample_axis",
            ),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class M6HeadlessValidationProvenance:
    """Dataset and coordinate provenance retained with a validation manifest."""

    source_session: str
    source_frame_indices: tuple[int, ...]
    raw_frame_size_px: tuple[int, int]
    expanded_frame_size_px: tuple[int, int]
    pixel_size_nm: tuple[float, float]
    scan_angle_deg: float
    coordinate_frame: Literal["sample_nm"] = "sample_nm"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "source_session",
            _non_empty_string(self.source_session, "source_session"),
        )
        source_indices = tuple(
            _non_negative_int(value, "source_frame_indices")
            for value in self.source_frame_indices
        )
        if not source_indices or len(set(source_indices)) != len(source_indices):
            raise ValueError("source_frame_indices must be non-empty and unique.")
        object.__setattr__(self, "source_frame_indices", source_indices)
        object.__setattr__(
            self,
            "raw_frame_size_px",
            _positive_int_pair(self.raw_frame_size_px, "raw_frame_size_px"),
        )
        object.__setattr__(
            self,
            "expanded_frame_size_px",
            _positive_int_pair(
                self.expanded_frame_size_px,
                "expanded_frame_size_px",
            ),
        )
        object.__setattr__(
            self,
            "pixel_size_nm",
            _positive_pair(self.pixel_size_nm, "pixel_size_nm"),
        )
        object.__setattr__(
            self,
            "scan_angle_deg",
            _finite_float(self.scan_angle_deg, "scan_angle_deg"),
        )
        if self.coordinate_frame != "sample_nm":
            raise ValueError("coordinate_frame must be 'sample_nm'.")

    def to_dict(self) -> dict[str, object]:
        return {
            "source_session": self.source_session,
            "source_frame_indices": list(self.source_frame_indices),
            "raw_frame_size_px": list(self.raw_frame_size_px),
            "expanded_frame_size_px": list(self.expanded_frame_size_px),
            "pixel_size_nm": list(self.pixel_size_nm),
            "scan_angle_deg": self.scan_angle_deg,
            "coordinate_frame": self.coordinate_frame,
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "M6HeadlessValidationProvenance":
        if not isinstance(payload, Mapping):
            raise TypeError("Validation provenance payload must be a mapping.")
        required = {
            "source_session",
            "source_frame_indices",
            "raw_frame_size_px",
            "expanded_frame_size_px",
            "pixel_size_nm",
            "scan_angle_deg",
            "coordinate_frame",
        }
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"Missing validation provenance fields: {', '.join(missing)}")
        return cls(
            source_session=payload["source_session"],  # type: ignore[arg-type]
            source_frame_indices=tuple(payload["source_frame_indices"]),  # type: ignore[arg-type]
            raw_frame_size_px=payload["raw_frame_size_px"],  # type: ignore[arg-type]
            expanded_frame_size_px=payload["expanded_frame_size_px"],  # type: ignore[arg-type]
            pixel_size_nm=payload["pixel_size_nm"],  # type: ignore[arg-type]
            scan_angle_deg=payload["scan_angle_deg"],  # type: ignore[arg-type]
            coordinate_frame=payload["coordinate_frame"],  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class M6HeadlessValidationManifest:
    """Versioned accepted settings and representative frame inputs."""

    manifest_version: int
    manifest_id: str
    algorithm_version: str
    accepted_settings: MolecularM6OrientationAnalysisSettings
    high_unassigned_fraction_warning_threshold: float
    frames: tuple[M6HeadlessValidationFrame, ...]
    provenance: M6HeadlessValidationProvenance | None = None

    def __post_init__(self) -> None:
        manifest_version = _positive_int(self.manifest_version, "manifest_version")
        if manifest_version != 1:
            raise ValueError("manifest_version must be 1.")
        manifest_id = _non_empty_string(self.manifest_id, "manifest_id")
        algorithm_version = _non_empty_string(
            self.algorithm_version,
            "algorithm_version",
        )
        if algorithm_version != M6_ORIENTATION_ALGORITHM_VERSION:
            raise ValueError(
                "algorithm_version must match the supported M6 orientation algorithm."
            )
        if not isinstance(
            self.accepted_settings,
            MolecularM6OrientationAnalysisSettings,
        ):
            raise TypeError(
                "accepted_settings must be MolecularM6OrientationAnalysisSettings."
            )
        threshold = _unit_float(
            self.high_unassigned_fraction_warning_threshold,
            "high_unassigned_fraction_warning_threshold",
        )
        frames = tuple(self.frames)
        if not frames:
            raise ValueError("Validation manifest must contain at least one frame.")
        if any(not isinstance(frame, M6HeadlessValidationFrame) for frame in frames):
            raise TypeError("frames must contain M6HeadlessValidationFrame values.")
        frame_ids = tuple(frame.frame_id for frame in frames)
        if len(set(frame_ids)) != len(frame_ids):
            raise ValueError("frame_id values must be unique within a manifest.")
        view_keys = tuple(
            (frame.physical_frame_id, frame.source_view) for frame in frames
        )
        if len(set(view_keys)) != len(view_keys):
            raise ValueError(
                "Each physical frame may occur once for each source_view."
            )
        if self.provenance is not None and not isinstance(
            self.provenance,
            M6HeadlessValidationProvenance,
        ):
            raise TypeError(
                "provenance must be M6HeadlessValidationProvenance or None."
            )
        if self.provenance is not None:
            unknown_source_indices = sorted(
                {frame.source_frame_index for frame in frames}
                - set(self.provenance.source_frame_indices)
            )
            if unknown_source_indices:
                raise ValueError(
                    "Frame source indices must be declared by manifest provenance."
                )

        object.__setattr__(self, "manifest_version", manifest_version)
        object.__setattr__(self, "manifest_id", manifest_id)
        object.__setattr__(self, "algorithm_version", algorithm_version)
        object.__setattr__(
            self,
            "high_unassigned_fraction_warning_threshold",
            threshold,
        )
        object.__setattr__(self, "frames", frames)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "manifest_version": self.manifest_version,
            "manifest_id": self.manifest_id,
            "algorithm_version": self.algorithm_version,
            "accepted_settings": self.accepted_settings.to_dict(),
            "high_unassigned_fraction_warning_threshold": (
                self.high_unassigned_fraction_warning_threshold
            ),
            "frames": [frame.to_dict() for frame in self.frames],
        }
        if self.provenance is not None:
            payload["provenance"] = self.provenance.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "M6HeadlessValidationManifest":
        if not isinstance(payload, Mapping):
            raise TypeError("Validation manifest payload must be a mapping.")
        required = {
            "manifest_version",
            "manifest_id",
            "algorithm_version",
            "accepted_settings",
            "high_unassigned_fraction_warning_threshold",
            "frames",
        }
        missing = sorted(required - set(payload))
        if missing:
            raise ValueError(f"Missing validation manifest fields: {', '.join(missing)}")
        settings_payload = payload["accepted_settings"]
        if not isinstance(settings_payload, Mapping):
            raise TypeError("accepted_settings must be a mapping.")
        raw_frames = payload["frames"]
        try:
            frames = tuple(
                M6HeadlessValidationFrame.from_dict(frame)
                for frame in raw_frames  # type: ignore[union-attr]
            )
        except TypeError as exc:
            raise TypeError("frames must be a sequence of mappings.") from exc
        provenance_payload = payload.get("provenance")
        if provenance_payload is not None and not isinstance(
            provenance_payload,
            Mapping,
        ):
            raise TypeError("provenance must be a mapping or null.")
        return cls(
            manifest_version=payload["manifest_version"],  # type: ignore[arg-type]
            manifest_id=payload["manifest_id"],  # type: ignore[arg-type]
            algorithm_version=payload["algorithm_version"],  # type: ignore[arg-type]
            accepted_settings=MolecularM6OrientationAnalysisSettings.from_dict(
                settings_payload
            ),
            high_unassigned_fraction_warning_threshold=payload[
                "high_unassigned_fraction_warning_threshold"
            ],  # type: ignore[arg-type]
            frames=frames,
            provenance=(
                None
                if provenance_payload is None
                else M6HeadlessValidationProvenance.from_dict(provenance_payload)
            ),
        )



def _points_tuple(value: object) -> tuple[tuple[float, float], ...]:
    try:
        raw_points = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError("points_xy_nm must be a sequence of coordinate pairs.") from exc
    points: list[tuple[float, float]] = []
    for index, raw_point in enumerate(raw_points):
        try:
            point = tuple(raw_point)
        except TypeError as exc:
            raise TypeError(f"points_xy_nm[{index}] must contain x and y.") from exc
        if len(point) != 2:
            raise ValueError(f"points_xy_nm[{index}] must contain x and y.")
        x = _finite_float(point[0], f"points_xy_nm[{index}][0]")
        y = _finite_float(point[1], f"points_xy_nm[{index}][1]")
        points.append((x, y))
    return tuple(points)



def _finite_pair(value: object, field_name: str) -> tuple[float, float]:
    try:
        pair = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{field_name} must contain two values.") from exc
    if len(pair) != 2:
        raise ValueError(f"{field_name} must contain two values.")
    return (
        _finite_float(pair[0], f"{field_name}[0]"),
        _finite_float(pair[1], f"{field_name}[1]"),
    )


def _positive_pair(value: object, field_name: str) -> tuple[float, float]:
    pair = _finite_pair(value, field_name)
    if pair[0] <= 0.0 or pair[1] <= 0.0:
        raise ValueError(f"{field_name} values must be positive.")
    return pair


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a finite number.")
    try:
        normalized = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be a finite number.") from exc
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _unit_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie between 0 and 1.")
    return normalized



def _non_negative_int(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise TypeError(f"{field_name} must be a non-negative integer.")
    return value


def _positive_int(value: object, field_name: str) -> int:
    normalized = _non_negative_int(value, field_name)
    if normalized == 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _positive_int_pair(value: object, field_name: str) -> tuple[int, int]:
    try:
        pair = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise TypeError(f"{field_name} must contain two integers.") from exc
    if len(pair) != 2:
        raise ValueError(f"{field_name} must contain two integers.")
    return (
        _positive_int(pair[0], f"{field_name}[0]"),
        _positive_int(pair[1], f"{field_name}[1]"),
    )


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field_name} must be a non-empty string.")
    return value.strip()
