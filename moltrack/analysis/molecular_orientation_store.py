"""Frame-indexed molecular orientations and series-level estimation."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from math import cos, isfinite, radians, sin
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from moltrack.core.data_models import MolTrackImageSeries

from .molecular_orientation_estimator import (
    MolecularOrientationEstimationResult,
    estimate_molecular_orientation,
)
from .molecular_orientation_models import (
    MolecularOrientationMeasurement,
    MolecularOrientationProvenance,
)
from .molecular_orientation_topography import MolecularTopographyOrientationSettings


@dataclass(frozen=True)
class MolecularOrientationEstimationProgress:
    """Progress after one segmentation has been processed."""

    completed_count: int
    total_count: int
    frame_index: int | None
    source_id: str | None


@dataclass(frozen=True)
class MolecularOrientationEstimationFailure:
    """One segmentation that could not be estimated."""

    frame_index: int
    source_id: str
    message: str


@dataclass(frozen=True)
class MolecularOrientationBatchResult:
    """Measurements and recoverable per-segmentation failures from one run."""

    measurements: tuple[MolecularOrientationMeasurement, ...]
    failures: tuple[MolecularOrientationEstimationFailure, ...]
    completed_count: int
    total_count: int

    @property
    def failure_count(self) -> int:
        return len(self.failures)


@dataclass(frozen=True)
class MolecularOrientationAxis:
    """One image-space line representing a stored molecular axis."""

    source_id: str
    center_xy_px: tuple[float, float]
    endpoints_xy_px: tuple[tuple[float, float], tuple[float, float]]
    angle_deg: float
    confidence: float
    method: str
    selected: bool = False


class MolecularOrientationEstimationCancelled(RuntimeError):
    """Raised when a range estimation is canceled between molecules."""


class MolecularOrientationStore:
    """Mutable result collection keyed by annotation identity."""

    def __init__(
        self,
        *,
        frame_count: int,
        measurements: Iterable[MolecularOrientationMeasurement] = (),
    ) -> None:
        frame_count = int(frame_count)
        if frame_count <= 0:
            raise ValueError("frame_count must be positive.")
        self.frame_count = frame_count
        self._measurements: dict[
            tuple[str, str],
            MolecularOrientationMeasurement,
        ] = {}
        for measurement in measurements:
            self.put(measurement)

    @property
    def measurements(self) -> tuple[MolecularOrientationMeasurement, ...]:
        return tuple(
            sorted(
                self._measurements.values(),
                key=lambda item: (
                    item.provenance.frame_index,
                    item.provenance.source_view,
                    item.provenance.source_kind,
                    item.provenance.source_id,
                ),
            )
        )

    @property
    def measurement_count(self) -> int:
        return len(self._measurements)

    def put(
        self,
        measurement: MolecularOrientationMeasurement,
    ) -> MolecularOrientationMeasurement:
        if not isinstance(measurement, MolecularOrientationMeasurement):
            raise TypeError(
                "measurement must be a MolecularOrientationMeasurement."
            )
        provenance = measurement.provenance
        if provenance.frame_index >= self.frame_count:
            raise IndexError("Orientation frame_index is out of range.")
        key = (provenance.source_kind, provenance.source_id)
        self._measurements[key] = measurement
        return measurement

    def put_many(
        self,
        measurements: Iterable[MolecularOrientationMeasurement],
    ) -> int:
        count = 0
        for measurement in measurements:
            self.put(measurement)
            count += 1
        return count

    def put_automatic_measurements_preserving_manual(
        self,
        measurements: Iterable[MolecularOrientationMeasurement],
    ) -> int:
        """Refresh automatic baselines without discarding audited angles."""

        count = 0
        for measurement in measurements:
            provenance = measurement.provenance
            existing = self.get(
                provenance.source_kind,
                provenance.source_id,
            )
            if existing is not None and (
                existing.manual_correction is not None
                or existing.method == "manual"
            ):
                correction = existing.manual_correction
                measurement = measurement.with_manual_correction(
                    status=existing.status,
                    angle_deg=existing.angle_deg,
                    confidence=existing.confidence,
                    reviewer=(
                        "MolTrack user"
                        if correction is None
                        else correction.reviewer
                    ),
                    note="" if correction is None else correction.note,
                )
            self.put(measurement)
            count += 1
        return count

    def get(
        self,
        source_kind: str,
        source_id: str,
    ) -> MolecularOrientationMeasurement | None:
        return self._measurements.get((str(source_kind), str(source_id)))

    def remove(self, source_kind: str, source_id: str) -> bool:
        return self._measurements.pop(
            (str(source_kind), str(source_id)),
            None,
        ) is not None

    def measurements_for_frame(
        self,
        frame_index: int,
        *,
        source_view: str | None = None,
    ) -> tuple[MolecularOrientationMeasurement, ...]:
        frame_index = self._validate_frame_index(frame_index)
        return tuple(
            measurement
            for measurement in self.measurements
            if measurement.provenance.frame_index == frame_index
            and (
                source_view is None
                or measurement.provenance.source_view == str(source_view)
            )
        )

    def set_manual_angle(
        self,
        source_kind: str,
        source_id: str,
        *,
        angle_deg: float,
        reviewer: str,
        note: str = "",
    ) -> MolecularOrientationMeasurement:
        measurement = self._required(source_kind, source_id)
        corrected = measurement.with_manual_correction(
            status="available",
            angle_deg=float(angle_deg),
            confidence=1.0,
            reviewer=reviewer,
            note=note,
        )
        return self.put(corrected)

    def rotate_manual_angle(
        self,
        source_kind: str,
        source_id: str,
        *,
        delta_deg: float,
        reviewer: str,
        note: str = "",
    ) -> MolecularOrientationMeasurement:
        measurement = self._required(source_kind, source_id)
        if measurement.angle_deg is None:
            raise ValueError(
                "Cannot rotate an unavailable molecular orientation."
            )
        return self.set_manual_angle(
            source_kind,
            source_id,
            angle_deg=measurement.angle_deg + float(delta_deg),
            reviewer=reviewer,
            note=note,
        )

    def reset_manual_angle(
        self,
        source_kind: str,
        source_id: str,
    ) -> MolecularOrientationMeasurement:
        measurement = self._required(source_kind, source_id)
        return self.put(measurement.reset_manual_correction())

    def _required(
        self,
        source_kind: str,
        source_id: str,
    ) -> MolecularOrientationMeasurement:
        measurement = self.get(source_kind, source_id)
        if measurement is None:
            raise KeyError(
                f"Unknown molecular orientation: {source_kind}:{source_id}."
            )
        return measurement

    def _validate_frame_index(self, frame_index: int) -> int:
        frame_index = int(frame_index)
        if not 0 <= frame_index < self.frame_count:
            raise IndexError("frame_index is out of range.")
        return frame_index


def estimate_series_molecular_orientations(
    series: MolTrackImageSeries,
    *,
    frame_indices: Iterable[int],
    source_view: str,
    source_file_sha256: str | None = None,
    progress_callback: (
        Callable[[MolecularOrientationEstimationProgress], None] | None
    ) = None,
    should_cancel: Callable[[], bool] | None = None,
    estimator: Callable[..., MolecularOrientationEstimationResult] = (
        estimate_molecular_orientation
    ),
) -> MolecularOrientationBatchResult:
    """Estimate all segmentation masks in the requested frames."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries.")
    source_view = str(source_view)
    if source_view not in ("raw", "expanded_aligned"):
        raise ValueError("source_view must be 'raw' or 'expanded_aligned'.")
    indices = tuple(int(index) for index in frame_indices)
    for frame_index in indices:
        series.get_frame(frame_index)
    if series.molecular_segmentations is None:
        segmentations = ()
    else:
        segmentations = tuple(
            segmentation
            for frame_index in indices
            for segmentation in series.molecular_segmentations.get_segmentations(
                frame_index,
                source_view=source_view,
            )
        )

    total_count = len(segmentations)
    _report_progress(
        progress_callback,
        completed_count=0,
        total_count=total_count,
        frame_index=None,
        source_id=None,
    )
    if source_file_sha256 is None:
        source_file_sha256 = _source_file_sha256(series)
    frames = _frames_for_source_view(series, source_view)
    pixel_size_nm_xy = _pixel_size_nm_xy(series)
    scan_angle_deg = _scan_angle_deg(series)
    orientation_reference = (
        "image_x_axis_counterclockwise"
        if scan_angle_deg is None
        else "sample_x_axis_counterclockwise"
    )
    topography_settings = MolecularTopographyOrientationSettings()
    margin_px = (
        topography_settings.context_radius_px
        + topography_settings.gradient_erosion_px
        + 2
    )
    measurements: list[MolecularOrientationMeasurement] = []
    failures: list[MolecularOrientationEstimationFailure] = []
    for completed_count, segmentation in enumerate(segmentations, start=1):
        if should_cancel is not None and should_cancel():
            raise MolecularOrientationEstimationCancelled(
                "Molecular orientation estimation was canceled."
            )
        try:
            frame = np.asarray(frames[segmentation.frame_index])
            full_mask = _full_frame_segmentation_mask(
                segmentation,
                frame_shape=frame.shape[:2],
            )
            patch, mask_patch, valid_fov_patch, patch_bbox = _orientation_patch(
                frame,
                full_mask,
                margin_px=margin_px,
            )
            provenance = MolecularOrientationProvenance(
                source_file_name=Path(series.source_path).name,
                source_file_sha256=source_file_sha256,
                source_session_file_name=None,
                source_session_sha256=None,
                frame_index=segmentation.frame_index,
                source_view=source_view,
                source_kind="segmentation",
                source_id=segmentation.segmentation_id,
                patch_bbox_xyxy=patch_bbox,
                orientation_reference=orientation_reference,
            )
            result = estimator(
                patch,
                mask_patch,
                measurement_id=(
                    "orientation:segmentation:"
                    f"{segmentation.segmentation_id}"
                ),
                provenance=provenance,
                pixel_size_nm_xy=pixel_size_nm_xy,
                scan_angle_deg=scan_angle_deg,
                valid_fov_mask=valid_fov_patch,
                topography_settings=topography_settings,
            )
            measurements.append(result.measurement)
        except Exception as exc:
            failures.append(
                MolecularOrientationEstimationFailure(
                    frame_index=segmentation.frame_index,
                    source_id=segmentation.segmentation_id,
                    message=str(exc) or exc.__class__.__name__,
                )
            )
        _report_progress(
            progress_callback,
            completed_count=completed_count,
            total_count=total_count,
            frame_index=segmentation.frame_index,
            source_id=segmentation.segmentation_id,
        )
    return MolecularOrientationBatchResult(
        measurements=tuple(measurements),
        failures=tuple(failures),
        completed_count=total_count,
        total_count=total_count,
    )


def build_manual_molecular_orientation_measurement(
    series: MolTrackImageSeries,
    segmentation: object,
    *,
    source_view: str,
    angle_deg: float,
    source_file_sha256: str | None = None,
) -> MolecularOrientationMeasurement:
    """Create the first auditable orientation for a selected mask."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries.")
    frame_index = int(getattr(segmentation, "frame_index"))
    source_id = str(getattr(segmentation, "segmentation_id"))
    frame = np.asarray(
        _frames_for_source_view(series, source_view)[frame_index]
    )
    full_mask = _full_frame_segmentation_mask(
        segmentation,
        frame_shape=frame.shape[:2],
    )
    patch, _mask, _valid_fov, patch_bbox = _orientation_patch(
        frame,
        full_mask,
        margin_px=0,
    )
    scan_angle_deg = _scan_angle_deg(series)
    return MolecularOrientationMeasurement(
        measurement_id=f"orientation:segmentation:{source_id}",
        status="available",
        angle_deg=float(angle_deg),
        periodicity_deg=180.0,
        confidence=1.0,
        method="manual",
        patch_shape_px=tuple(int(value) for value in patch.shape),
        provenance=MolecularOrientationProvenance(
            source_file_name=Path(series.source_path).name,
            source_file_sha256=(
                _source_file_sha256(series)
                if source_file_sha256 is None
                else source_file_sha256
            ),
            source_session_file_name=None,
            source_session_sha256=None,
            frame_index=frame_index,
            source_view=str(source_view),
            source_kind="segmentation",
            source_id=source_id,
            patch_bbox_xyxy=patch_bbox,
            orientation_reference=(
                "image_x_axis_counterclockwise"
                if scan_angle_deg is None
                else "sample_x_axis_counterclockwise"
            ),
        ),
    )


def build_molecular_orientation_axes(
    series: MolTrackImageSeries,
    *,
    frame_index: int,
    source_view: str,
    selected_source_id: str | None = None,
) -> tuple[MolecularOrientationAxis, ...]:
    """Build image-space axis lines without rerunning orientation estimation."""

    store = getattr(series, "molecular_orientations", None)
    segmentations = getattr(series, "molecular_segmentations", None)
    if not isinstance(store, MolecularOrientationStore) or segmentations is None:
        return ()
    frame = _frames_for_source_view(series, source_view)[int(frame_index)]
    scan_angle_deg = _scan_angle_deg(series)
    axes: list[MolecularOrientationAxis] = []
    for measurement in store.measurements_for_frame(
        frame_index,
        source_view=source_view,
    ):
        if measurement.status == "unavailable" or measurement.angle_deg is None:
            continue
        segmentation = segmentations.get_segmentation(
            measurement.provenance.source_id
        )
        if segmentation is None or segmentation.mask is None:
            continue
        try:
            mask = _full_frame_segmentation_mask(
                segmentation,
                frame_shape=np.asarray(frame).shape[:2],
            )
        except (TypeError, ValueError):
            continue
        rows, columns = np.nonzero(mask)
        if rows.size == 0:
            continue
        center_x = float(np.mean(columns))
        center_y = float(np.mean(rows))
        width = float(np.max(columns) - np.min(columns) + 1)
        height = float(np.max(rows) - np.min(rows) + 1)
        try:
            pixel_size_x, pixel_size_y = _pixel_size_nm_xy(series)
        except ValueError:
            pixel_size_x, pixel_size_y = 1.0, 1.0
        half_length_nm = max(
            3.0 * max(pixel_size_x, pixel_size_y),
            0.6
            * max(
                width * pixel_size_x,
                height * pixel_size_y,
            ),
        )
        image_angle_deg = measurement.angle_deg - (scan_angle_deg or 0.0)
        angle_rad = radians(image_angle_deg)
        dx = cos(angle_rad) * half_length_nm / pixel_size_x
        dy = -sin(angle_rad) * half_length_nm / pixel_size_y
        axes.append(
            MolecularOrientationAxis(
                source_id=measurement.provenance.source_id,
                center_xy_px=(center_x, center_y),
                endpoints_xy_px=(
                    (center_x - dx, center_y - dy),
                    (center_x + dx, center_y + dy),
                ),
                angle_deg=measurement.angle_deg,
                confidence=float(measurement.confidence or 0.0),
                method=measurement.method,
                selected=(
                    measurement.provenance.source_id
                    == selected_source_id
                ),
            )
        )
    return tuple(axes)


def _frames_for_source_view(
    series: MolTrackImageSeries,
    source_view: str,
) -> np.ndarray:
    if source_view == "raw":
        return np.asarray(series.raw_frames)
    expanded = series.expanded_aligned_stack
    if expanded is None:
        raise ValueError(
            "expanded_aligned orientation requires an expanded aligned stack."
        )
    frames = np.asarray(expanded.frames)
    if frames.shape[0] != series.frame_count:
        raise ValueError("Expanded aligned stack does not match the series.")
    return frames


def _full_frame_segmentation_mask(
    segmentation: object,
    *,
    frame_shape: tuple[int, int],
) -> np.ndarray:
    mask_value = getattr(segmentation, "mask", None)
    if mask_value is None:
        raise ValueError("Molecular orientation requires a segmentation mask.")
    mask = np.asarray(mask_value, dtype=bool)
    height, width = (int(value) for value in frame_shape)
    if mask.shape == (height, width):
        return mask
    bbox = getattr(segmentation, "bbox_xyxy", None)
    if bbox is None:
        raise ValueError("A local segmentation mask requires bbox_xyxy.")
    x0, y0, x1, y1 = (int(round(float(value))) for value in bbox)
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise ValueError("Segmentation bbox lies outside its source frame.")
    if mask.shape != (y1 - y0, x1 - x0):
        raise ValueError("Local segmentation mask does not match bbox_xyxy.")
    full_mask = np.zeros((height, width), dtype=bool)
    full_mask[y0:y1, x0:x1] = mask
    return full_mask


def _orientation_patch(
    frame: np.ndarray,
    full_mask: np.ndarray,
    *,
    margin_px: int,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    tuple[float, float, float, float],
]:
    rows, columns = np.nonzero(full_mask)
    if rows.size == 0:
        raise ValueError("Molecular orientation requires a non-empty mask.")
    height, width = full_mask.shape
    x0 = max(0, int(np.min(columns)) - int(margin_px))
    x1 = min(width, int(np.max(columns)) + int(margin_px) + 1)
    y0 = max(0, int(np.min(rows)) - int(margin_px))
    y1 = min(height, int(np.max(rows)) + int(margin_px) + 1)
    patch = np.asarray(frame[y0:y1, x0:x1], dtype=np.float64)
    mask_patch = np.asarray(full_mask[y0:y1, x0:x1], dtype=bool)
    valid_fov_patch = np.isfinite(patch)
    if np.any(mask_patch & ~valid_fov_patch):
        raise ValueError("Segmentation mask contains invalid STM pixels.")
    return (
        patch,
        mask_patch,
        valid_fov_patch,
        (float(x0), float(y0), float(x1), float(y1)),
    )


def _pixel_size_nm_xy(
    series: MolTrackImageSeries,
) -> tuple[float, float]:
    pixel_size_x, pixel_size_y = series.pixel_size_nm
    if pixel_size_x is None or pixel_size_y is None:
        raise ValueError(
            "Molecular orientation requires STM pixel-size calibration."
        )
    normalized = (float(pixel_size_x), float(pixel_size_y))
    if not all(isfinite(value) and value > 0.0 for value in normalized):
        raise ValueError(
            "Molecular orientation requires positive pixel-size calibration."
        )
    return normalized


def _scan_angle_deg(series: MolTrackImageSeries) -> float | None:
    value = getattr(series.metadata, "scan_angle_deg", None)
    if value is None:
        return None
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return None
    return normalized if isfinite(normalized) else None


def _source_file_sha256(series: MolTrackImageSeries) -> str:
    path = Path(series.source_path).expanduser().resolve()
    stat = path.stat()
    cache_key = (str(path), int(stat.st_size), int(stat.st_mtime_ns))
    cached = getattr(series, "_molecular_orientation_source_hash", None)
    if (
        isinstance(cached, tuple)
        and len(cached) == 2
        and cached[0] == cache_key
    ):
        return str(cached[1])
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    value = digest.hexdigest()
    setattr(series, "_molecular_orientation_source_hash", (cache_key, value))
    return value


def _report_progress(
    callback: Callable[[MolecularOrientationEstimationProgress], None] | None,
    *,
    completed_count: int,
    total_count: int,
    frame_index: int | None,
    source_id: str | None,
) -> None:
    if callback is not None:
        callback(
            MolecularOrientationEstimationProgress(
                completed_count=int(completed_count),
                total_count=int(total_count),
                frame_index=frame_index,
                source_id=source_id,
            )
        )
