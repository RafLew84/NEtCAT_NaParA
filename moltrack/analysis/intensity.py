from __future__ import annotations

from dataclasses import dataclass
import hashlib
from math import ceil, floor
from typing import Callable

import numpy as np
from scipy.ndimage import binary_dilation

from moltrack.core import (
    MolTrackImageSeries,
    MolTrackIntensityCacheRecord,
    RegisteredFrameTransform,
)


@dataclass(frozen=True)
class MolecularIntensityMeasurement:
    """Signal statistics for one molecular measurement geometry on one frame."""

    frame_index: int
    source_id: str
    source_kind: str
    pixel_count: int
    sum: float | None
    mean: float | None
    median: float | None
    max: float | None
    unit: str = "a.u."
    local_background_median: float | None = None
    background_corrected_mean: float | None = None
    background_corrected_median: float | None = None


@dataclass(frozen=True)
class MolecularIntensityCacheStats:
    """Observable cache counters for molecular intensity measurements."""

    entry_count: int
    hit_count: int
    miss_count: int
    context_mask_build_count: int


@dataclass(frozen=True)
class _MolecularIntensityCacheEntry:
    geometry_version: tuple
    measurement: MolecularIntensityMeasurement
    annotation_fingerprint: str | None
    geometry_reference: object | None = None


@dataclass(frozen=True)
class _MolecularMeasurementGeometry:
    bounds_ltrb: tuple[int, int, int, int]
    mask: np.ndarray


@dataclass(frozen=True)
class _MolecularMeasurementSpec:
    source_id: str
    source_kind: str
    geometry_version: tuple
    geometry_reference: object | None
    mask: np.ndarray | None = None
    bbox_xyxy: tuple[float, float, float, float] | None = None
    registered_transform: RegisteredFrameTransform | None = None


@dataclass(frozen=True)
class _MolecularIntensityContextEntry:
    geometry_versions: tuple
    geometries: dict[tuple[str, str], _MolecularMeasurementGeometry]
    all_molecules_mask: np.ndarray
    geometry_references: tuple[object, ...]


class MolecularIntensityMeasurementCache:
    """Per-series cache that preserves unchanged molecular measurements."""

    def __init__(self) -> None:
        self._entries: dict[tuple, _MolecularIntensityCacheEntry] = {}
        self._pending_records: dict[tuple, MolTrackIntensityCacheRecord] = {}
        self._contexts: dict[tuple[int, str], _MolecularIntensityContextEntry] = {}
        self._hit_count = 0
        self._miss_count = 0
        self._context_mask_build_count = 0

    def get(
        self,
        key: tuple,
        *,
        geometry_version: tuple,
        geometry_reference: object | None = None,
        annotation_fingerprint_factory: Callable[[], str | None] | None = None,
    ) -> MolecularIntensityMeasurement | None:
        entry = self._entries.get(key)
        if entry is not None and entry.geometry_version == geometry_version:
            self._hit_count += 1
            return entry.measurement
        pending = self._pending_records.pop(key, None)
        if pending is not None and annotation_fingerprint_factory is not None:
            annotation_fingerprint = annotation_fingerprint_factory()
            if annotation_fingerprint == pending.annotation_fingerprint:
                measurement = _measurement_from_cache_record(pending)
                self.put(
                    key,
                    geometry_version=geometry_version,
                    measurement=measurement,
                    annotation_fingerprint=pending.annotation_fingerprint,
                    geometry_reference=geometry_reference,
                )
                self._hit_count += 1
                return measurement
        self._miss_count += 1
        return None

    def put(
        self,
        key: tuple,
        *,
        geometry_version: tuple,
        measurement: MolecularIntensityMeasurement,
        annotation_fingerprint: str | None,
        geometry_reference: object | None = None,
    ) -> None:
        self._pending_records.pop(key, None)
        self._entries[key] = _MolecularIntensityCacheEntry(
            geometry_version=geometry_version,
            measurement=measurement,
            annotation_fingerprint=annotation_fingerprint,
            geometry_reference=geometry_reference,
        )

    def retain_sources(
        self,
        *,
        frame_index: int,
        source_view: str,
        active_sources: set[tuple[str, str]],
    ) -> None:
        stale_keys = [
            key
            for key in self._entries
            if key[0] == int(frame_index)
            and key[1] == str(source_view)
            and (key[2], key[3]) not in active_sources
        ]
        for key in stale_keys:
            del self._entries[key]
        stale_pending_keys = [
            key
            for key in self._pending_records
            if key[0] == int(frame_index)
            and key[1] == str(source_view)
            and (key[2], key[3]) not in active_sources
        ]
        for key in stale_pending_keys:
            del self._pending_records[key]

    def load_records(self, records: tuple[MolTrackIntensityCacheRecord, ...]) -> None:
        self._pending_records = {
            _cache_key_from_record(record): record for record in records
        }

    def get_context(
        self,
        key: tuple[int, str],
        *,
        geometry_versions: tuple,
    ) -> _MolecularIntensityContextEntry | None:
        context = self._contexts.get(key)
        if context is None or context.geometry_versions != geometry_versions:
            return None
        return context

    def put_context(
        self,
        key: tuple[int, str],
        *,
        geometry_versions: tuple,
        geometries: dict[tuple[str, str], _MolecularMeasurementGeometry],
        all_molecules_mask: np.ndarray,
        geometry_references: tuple[object, ...],
    ) -> _MolecularIntensityContextEntry:
        context = _MolecularIntensityContextEntry(
            geometry_versions=geometry_versions,
            geometries=geometries,
            all_molecules_mask=all_molecules_mask,
            geometry_references=geometry_references,
        )
        self._contexts[key] = context
        self._context_mask_build_count += 1
        return context

    def remove_context(self, *, frame_index: int, source_view: str) -> None:
        self._contexts.pop((int(frame_index), str(source_view)), None)

    def stats(self) -> MolecularIntensityCacheStats:
        return MolecularIntensityCacheStats(
            entry_count=len(self._entries) + len(self._pending_records),
            hit_count=self._hit_count,
            miss_count=self._miss_count,
            context_mask_build_count=self._context_mask_build_count,
        )


def build_molecular_intensity_measurements(
    series: MolTrackImageSeries,
    *,
    frame_index: int | None = None,
    source_view: str = "raw",
    unit: str = "a.u.",
    background_inner_radius_px: int = 1,
    background_outer_radius_px: int = 3,
) -> list[MolecularIntensityMeasurement]:
    """Build one intensity measurement per segmented or bbox-only molecule."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    frame_index = series.active_frame_index if frame_index is None else int(frame_index)
    frame = series.get_frame(frame_index)
    source_view = str(source_view).strip()
    if source_view not in ("raw", "expanded_aligned"):
        raise ValueError(f"Unsupported source_view: {source_view!r}.")
    background_inner_radius_px, background_outer_radius_px = _normalize_background_radii(
        background_inner_radius_px,
        background_outer_radius_px,
    )
    registered_transform = (
        None
        if source_view == "raw"
        else _registered_frame_transform(series, frame_index=frame_index)
    )

    specs: list[_MolecularMeasurementSpec] = []
    linked_detection_ids: set[str] = set()
    segmentation_set = series.molecular_segmentations
    if segmentation_set is not None:
        for segmentation in segmentation_set.get_segmentations(frame_index, source_view=source_view):
            if segmentation.mask is None:
                continue
            source_mask = np.asarray(segmentation.mask, dtype=bool)
            transform_version = (
                None
                if registered_transform is None
                else (
                    registered_transform.raw_shape,
                    registered_transform.expanded_shape,
                    registered_transform.frame_origin_xy,
                )
            )
            specs.append(
                _MolecularMeasurementSpec(
                    source_id=segmentation.segmentation_id,
                    source_kind="segmentation",
                    geometry_version=(
                        "mask",
                        id(segmentation.mask),
                        tuple(source_mask.shape),
                        transform_version,
                    ),
                    geometry_reference=segmentation.mask,
                    mask=source_mask,
                    registered_transform=registered_transform,
                )
            )
            linked_detection_ids.update(segmentation.prompt_detection_ids)

    detection_set = series.molecular_detections
    if detection_set is not None:
        for detection in detection_set.get_detections(frame_index, source_view=source_view):
            if detection.detection_id in linked_detection_ids:
                continue
            bbox_xyxy = detection.bbox_xyxy
            if registered_transform is not None:
                try:
                    bbox_xyxy = registered_transform.expanded_prompt_bbox_to_raw(bbox_xyxy)
                except ValueError:
                    continue
            normalized_bbox = tuple(float(value) for value in bbox_xyxy)
            if _bbox_measurement_bounds(normalized_bbox, frame.shape) is not None:
                specs.append(
                    _MolecularMeasurementSpec(
                        source_id=detection.detection_id,
                        source_kind="bbox",
                        geometry_version=("bbox", normalized_bbox),
                        geometry_reference=detection,
                        bbox_xyxy=normalized_bbox,
                    )
                )

    cache = series.molecular_intensity_cache
    if not isinstance(cache, MolecularIntensityMeasurementCache):
        cache = MolecularIntensityMeasurementCache()
        series.molecular_intensity_cache = cache
    if not specs:
        cache.retain_sources(
            frame_index=frame_index,
            source_view=source_view,
            active_sources=set(),
        )
        cache.remove_context(frame_index=frame_index, source_view=source_view)
        return []
    context_key = (frame_index, source_view)
    geometry_versions = tuple(
        (spec.source_kind, spec.source_id, spec.geometry_version) for spec in specs
    )
    context = cache.get_context(context_key, geometry_versions=geometry_versions)
    if context is None:
        geometries, all_molecules_mask = _build_measurement_context(
            specs,
            frame_shape=frame.shape,
        )
        context = cache.put_context(
            context_key,
            geometry_versions=geometry_versions,
            geometries=geometries,
            all_molecules_mask=all_molecules_mask,
            geometry_references=tuple(
                spec.geometry_reference
                for spec in specs
                if spec.geometry_reference is not None
            ),
        )
    active_specs = [
        spec
        for spec in specs
        if (spec.source_kind, spec.source_id) in context.geometries
    ]
    cache.retain_sources(
        frame_index=frame_index,
        source_view=source_view,
        active_sources={(spec.source_kind, spec.source_id) for spec in active_specs},
    )
    measurements = []
    for spec in active_specs:
        cache_key = (
            frame_index,
            source_view,
            spec.source_kind,
            spec.source_id,
            str(unit),
            background_inner_radius_px,
            background_outer_radius_px,
        )
        measurement = cache.get(
            cache_key,
            geometry_version=spec.geometry_version,
            geometry_reference=spec.geometry_reference,
            annotation_fingerprint_factory=(
                lambda spec=spec: _annotation_fingerprint(
                    series,
                    frame_index=frame_index,
                    source_view=source_view,
                    source_kind=spec.source_kind,
                    source_id=spec.source_id,
                )
            ),
        )
        if measurement is None:
            measurement = _measure_molecular_intensity_geometry(
                frame,
                context.geometries[(spec.source_kind, spec.source_id)],
                frame_index=frame_index,
                source_id=spec.source_id,
                source_kind=spec.source_kind,
                unit=unit,
                background_inner_radius_px=background_inner_radius_px,
                background_outer_radius_px=background_outer_radius_px,
                other_molecules_mask=context.all_molecules_mask,
            )
            cache.put(
                cache_key,
                geometry_version=spec.geometry_version,
                measurement=measurement,
                annotation_fingerprint=_annotation_fingerprint(
                    series,
                    frame_index=frame_index,
                    source_view=source_view,
                    source_kind=spec.source_kind,
                    source_id=spec.source_id,
                ),
                geometry_reference=spec.geometry_reference,
            )
        measurements.append(measurement)
    return measurements


def export_molecular_intensity_cache_records(
    series: MolTrackImageSeries,
) -> tuple[MolTrackIntensityCacheRecord, ...]:
    """Export valid numeric cache entries without serializing masks or frame pixels."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    cache = series.molecular_intensity_cache
    if not isinstance(cache, MolecularIntensityMeasurementCache):
        return ()
    records_by_key: dict[tuple, MolTrackIntensityCacheRecord] = {}
    for key, pending in cache._pending_records.items():
        fingerprint = _annotation_fingerprint(
            series,
            frame_index=key[0],
            source_view=key[1],
            source_kind=key[2],
            source_id=key[3],
        )
        if fingerprint == pending.annotation_fingerprint:
            records_by_key[key] = pending
    for key, entry in cache._entries.items():
        frame_index, source_view, source_kind, source_id, unit, inner_radius, outer_radius = key
        fingerprint = _annotation_fingerprint(
            series,
            frame_index=frame_index,
            source_view=source_view,
            source_kind=source_kind,
            source_id=source_id,
        )
        if fingerprint is None or fingerprint != entry.annotation_fingerprint:
            continue
        measurement = entry.measurement
        records_by_key[key] = MolTrackIntensityCacheRecord(
            frame_index=frame_index,
            source_view=source_view,
            source_kind=source_kind,
            source_id=source_id,
            unit=unit,
            background_inner_radius_px=inner_radius,
            background_outer_radius_px=outer_radius,
            annotation_fingerprint=fingerprint,
            pixel_count=measurement.pixel_count,
            sum=measurement.sum,
            mean=measurement.mean,
            median=measurement.median,
            max=measurement.max,
            local_background_median=measurement.local_background_median,
            background_corrected_mean=measurement.background_corrected_mean,
            background_corrected_median=measurement.background_corrected_median,
        )
    return tuple(records_by_key[key] for key in sorted(records_by_key))


def restore_molecular_intensity_cache_records(
    series: MolTrackImageSeries,
    records: tuple[MolTrackIntensityCacheRecord, ...],
) -> None:
    """Attach persisted records for lazy validation against restored annotations."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    normalized_records = tuple(records)
    if not all(isinstance(record, MolTrackIntensityCacheRecord) for record in normalized_records):
        raise TypeError("records must contain MolTrackIntensityCacheRecord instances.")
    if not normalized_records:
        series.molecular_intensity_cache = None
        return
    cache = MolecularIntensityMeasurementCache()
    cache.load_records(normalized_records)
    series.molecular_intensity_cache = cache


def _cache_key_from_record(record: MolTrackIntensityCacheRecord) -> tuple:
    return (
        record.frame_index,
        record.source_view,
        record.source_kind,
        record.source_id,
        record.unit,
        record.background_inner_radius_px,
        record.background_outer_radius_px,
    )


def _measurement_from_cache_record(
    record: MolTrackIntensityCacheRecord,
) -> MolecularIntensityMeasurement:
    return MolecularIntensityMeasurement(
        frame_index=record.frame_index,
        source_id=record.source_id,
        source_kind=record.source_kind,
        pixel_count=record.pixel_count,
        sum=record.sum,
        mean=record.mean,
        median=record.median,
        max=record.max,
        unit=record.unit,
        local_background_median=record.local_background_median,
        background_corrected_mean=record.background_corrected_mean,
        background_corrected_median=record.background_corrected_median,
    )


def _annotation_fingerprint(
    series: MolTrackImageSeries,
    *,
    frame_index: int,
    source_view: str,
    source_kind: str,
    source_id: str,
) -> str | None:
    if source_kind == "bbox":
        detections = series.molecular_detections
        detection = None if detections is None else detections.get_detection(source_id)
        if (
            detection is None
            or detection.frame_index != frame_index
            or detection.source_view != source_view
        ):
            return None
        coordinates = ",".join(float(value).hex() for value in detection.bbox_xyxy)
        return f"bbox-v1:{coordinates}"
    if source_kind == "segmentation":
        segmentations = series.molecular_segmentations
        segmentation = None if segmentations is None else segmentations.get_segmentation(source_id)
        if (
            segmentation is None
            or segmentation.frame_index != frame_index
            or segmentation.source_view != source_view
            or segmentation.mask is None
        ):
            return None
        mask = np.ascontiguousarray(segmentation.mask, dtype=bool)
        digest = hashlib.blake2b(digest_size=16)
        digest.update(f"{mask.shape[0]}x{mask.shape[1]}:".encode("ascii"))
        digest.update(np.packbits(mask.reshape(-1), bitorder="little").tobytes())
        return f"mask-v1:{digest.hexdigest()}"
    return None


def measure_molecular_intensity(
    frame,
    mask,
    *,
    frame_index: int,
    source_id: str,
    source_kind: str,
    unit: str = "a.u.",
    background_inner_radius_px: int = 1,
    background_outer_radius_px: int = 3,
    other_molecules_mask=None,
) -> MolecularIntensityMeasurement:
    """Measure intensity statistics inside one molecular mask."""

    frame_array = np.asarray(frame)
    mask_array = np.asarray(mask)
    if frame_array.ndim != 2:
        raise ValueError("frame must be a 2D array.")
    if mask_array.dtype != np.dtype(bool):
        raise TypeError("mask must use bool dtype.")
    if mask_array.shape != frame_array.shape:
        raise ValueError("mask shape must match frame shape.")
    geometry = _mask_measurement_geometry(mask_array)
    if geometry is None:
        raise ValueError("mask must contain at least one active pixel.")
    if other_molecules_mask is None:
        other_molecules_mask_array = None
    else:
        other_molecules_mask_array = np.asarray(other_molecules_mask)
        if other_molecules_mask_array.dtype != np.dtype(bool):
            raise TypeError("other_molecules_mask must use bool dtype.")
        if other_molecules_mask_array.shape != frame_array.shape:
            raise ValueError("other_molecules_mask shape must match frame shape.")
    background_inner_radius_px, background_outer_radius_px = _normalize_background_radii(
        background_inner_radius_px,
        background_outer_radius_px,
    )
    return _measure_molecular_intensity_geometry(
        frame_array,
        geometry,
        frame_index=frame_index,
        source_id=source_id,
        source_kind=source_kind,
        unit=unit,
        background_inner_radius_px=background_inner_radius_px,
        background_outer_radius_px=background_outer_radius_px,
        other_molecules_mask=other_molecules_mask_array,
    )


def _measure_molecular_intensity_geometry(
    frame: np.ndarray,
    geometry: _MolecularMeasurementGeometry,
    *,
    frame_index: int,
    source_id: str,
    source_kind: str,
    unit: str,
    background_inner_radius_px: int,
    background_outer_radius_px: int,
    other_molecules_mask: np.ndarray | None,
) -> MolecularIntensityMeasurement:
    frame_array = np.asarray(frame)
    left, top, right, bottom = geometry.bounds_ltrb
    frame_height, frame_width = frame_array.shape
    roi_left = max(0, left - background_outer_radius_px)
    roi_top = max(0, top - background_outer_radius_px)
    roi_right = min(frame_width, right + background_outer_radius_px)
    roi_bottom = min(frame_height, bottom + background_outer_radius_px)
    frame_roi = frame_array[roi_top:roi_bottom, roi_left:roi_right]
    mask_roi = np.zeros(frame_roi.shape, dtype=bool)
    mask_roi[
        top - roi_top : bottom - roi_top,
        left - roi_left : right - roi_left,
    ] = geometry.mask
    other_molecules_roi = (
        None
        if other_molecules_mask is None
        else other_molecules_mask[roi_top:roi_bottom, roi_left:roi_right]
    )
    values = np.asarray(frame_roi[mask_roi], dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size == 0:
        signal_sum = signal_mean = signal_median = signal_max = None
    else:
        signal_sum = float(np.sum(values))
        signal_mean = float(np.mean(values))
        signal_median = float(np.median(values))
        signal_max = float(np.max(values))
    background_median = _local_background_median(
        frame_roi,
        mask_roi,
        inner_radius_px=background_inner_radius_px,
        outer_radius_px=background_outer_radius_px,
        other_molecules_mask=other_molecules_roi,
    )
    return MolecularIntensityMeasurement(
        frame_index=int(frame_index),
        source_id=str(source_id),
        source_kind=str(source_kind),
        pixel_count=int(values.size),
        sum=signal_sum,
        mean=signal_mean,
        median=signal_median,
        max=signal_max,
        unit=str(unit),
        local_background_median=background_median,
        background_corrected_mean=(
            None
            if signal_mean is None or background_median is None
            else signal_mean - background_median
        ),
        background_corrected_median=(
            None
            if signal_median is None or background_median is None
            else signal_median - background_median
        ),
    )


def _local_background_median(
    frame: np.ndarray,
    mask: np.ndarray,
    *,
    inner_radius_px: int,
    outer_radius_px: int,
    other_molecules_mask: np.ndarray | None,
) -> float | None:
    inner_radius_px, outer_radius_px = _normalize_background_radii(
        inner_radius_px,
        outer_radius_px,
    )
    inner = binary_dilation(mask, structure=_disk_structure(inner_radius_px))
    outer = binary_dilation(mask, structure=_disk_structure(outer_radius_px))
    ring = outer & ~inner
    if other_molecules_mask is not None:
        ring &= ~other_molecules_mask
    values = np.asarray(frame[ring], dtype=np.float64)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return None
    return float(np.median(values))


def _disk_structure(radius_px: int) -> np.ndarray:
    coordinates = np.arange(-radius_px, radius_px + 1, dtype=np.int64)
    yy, xx = np.meshgrid(coordinates, coordinates, indexing="ij")
    return xx**2 + yy**2 <= radius_px**2


def _normalize_background_radii(inner_radius_px: int, outer_radius_px: int) -> tuple[int, int]:
    inner_radius_px = int(inner_radius_px)
    outer_radius_px = int(outer_radius_px)
    if inner_radius_px < 0:
        raise ValueError("background_inner_radius_px must be non-negative.")
    if outer_radius_px <= inner_radius_px:
        raise ValueError(
            "background_outer_radius_px must be greater than background_inner_radius_px."
        )
    return inner_radius_px, outer_radius_px


def _build_measurement_context(
    specs: list[_MolecularMeasurementSpec],
    *,
    frame_shape: tuple[int, int],
) -> tuple[dict[tuple[str, str], _MolecularMeasurementGeometry], np.ndarray]:
    geometries: dict[tuple[str, str], _MolecularMeasurementGeometry] = {}
    all_molecules_mask = np.zeros(frame_shape, dtype=bool)
    for spec in specs:
        geometry = _measurement_geometry_from_spec(spec, frame_shape=frame_shape)
        if geometry is None:
            continue
        source_key = spec.source_kind, spec.source_id
        geometries[source_key] = geometry
        left, top, right, bottom = geometry.bounds_ltrb
        all_molecules_mask[top:bottom, left:right] |= geometry.mask
    return geometries, all_molecules_mask


def _measurement_geometry_from_spec(
    spec: _MolecularMeasurementSpec,
    *,
    frame_shape: tuple[int, int],
) -> _MolecularMeasurementGeometry | None:
    if spec.mask is not None:
        mask = spec.mask
        if spec.registered_transform is not None:
            mask = spec.registered_transform.expanded_mask_to_raw(mask)
        if mask.shape != tuple(frame_shape):
            raise ValueError("Molecular mask shape must match the measured raw frame.")
        return _mask_measurement_geometry(mask)
    if spec.bbox_xyxy is not None:
        return _bbox_measurement_geometry(spec.bbox_xyxy, frame_shape)
    return None


def _mask_measurement_geometry(mask: np.ndarray) -> _MolecularMeasurementGeometry | None:
    mask_array = np.asarray(mask, dtype=bool)
    active_y, active_x = np.nonzero(mask_array)
    if active_y.size == 0:
        return None
    left = int(np.min(active_x))
    top = int(np.min(active_y))
    right = int(np.max(active_x)) + 1
    bottom = int(np.max(active_y)) + 1
    return _MolecularMeasurementGeometry(
        bounds_ltrb=(left, top, right, bottom),
        mask=mask_array[top:bottom, left:right].copy(),
    )


def _bbox_measurement_bounds(
    bbox_xyxy: tuple[float, float, float, float],
    frame_shape: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    height, width = (int(value) for value in frame_shape)
    x1, y1, x2, y2 = bbox_xyxy
    left = max(0, min(width, floor(x1)))
    top = max(0, min(height, floor(y1)))
    right = max(0, min(width, ceil(x2)))
    bottom = max(0, min(height, ceil(y2)))
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def _bbox_measurement_geometry(
    bbox_xyxy: tuple[float, float, float, float],
    frame_shape: tuple[int, int],
) -> _MolecularMeasurementGeometry | None:
    bounds = _bbox_measurement_bounds(bbox_xyxy, frame_shape)
    if bounds is None:
        return None
    left, top, right, bottom = bounds
    return _MolecularMeasurementGeometry(
        bounds_ltrb=bounds,
        mask=np.ones((bottom - top, right - left), dtype=bool),
    )


def _registered_frame_transform(
    series: MolTrackImageSeries,
    *,
    frame_index: int,
) -> RegisteredFrameTransform:
    expanded_stack = series.expanded_aligned_stack
    if expanded_stack is None:
        raise ValueError("expanded_aligned source_view requires an expanded_aligned_stack.")
    frames = np.asarray(getattr(expanded_stack, "frames", None))
    if frames.ndim != 3 or frames.shape[0] != series.frame_count:
        raise ValueError("expanded_aligned_stack frames must match the working series.")
    frame_origins_xy = np.asarray(getattr(expanded_stack, "frame_origins_xy", None))
    if frame_origins_xy.shape != (series.frame_count, 2):
        raise ValueError("expanded_aligned_stack frame_origins_xy must match the working series.")
    return RegisteredFrameTransform(
        raw_shape=series.frame_shape,
        expanded_shape=(int(frames.shape[1]), int(frames.shape[2])),
        frame_origin_xy=tuple(frame_origins_xy[frame_index]),
    )
