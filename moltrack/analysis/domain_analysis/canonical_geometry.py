from math import ceil, cos, floor, radians, sin
from typing import Any

import numpy as np
from scipy.ndimage import affine_transform

from .fingerprints import canonical_sha256
from .geometry import (
    CoordinateView,
    DomainAnalysisSeries,
    GeometryMode,
    M6AnalyzedMolecule,
    M6CanonicalFrame,
    M6FrameGeometry,
    M6PresentationProvenance,
    M6SourceAnnotation,
)


_ADAPTER_VERSION = "domain-analysis-raw-registered-v1"


def canonicalize_frame(
    series: DomainAnalysisSeries,
    *,
    frame_index: int,
    geometry_mode: GeometryMode,
) -> M6CanonicalFrame:
    """Map raw or registered annotations into one canonical raw/sample frame."""

    if not isinstance(series, DomainAnalysisSeries):
        raise TypeError("series must be a DomainAnalysisSeries.")
    frame = series.frame(frame_index)
    canonical = tuple(
        _canonical_annotation(annotation, frame.geometry, geometry_mode)
        for annotation in frame.annotations
    )
    molecules = tuple(value[0] for value in canonical)
    analyzed_pixels = tuple(sorted({
        pixel
        for molecule in molecules
        for pixel in molecule.footprint_pixels_xy
    }))
    geometry_payloads = tuple(value[1] for value in canonical)
    geometry = frame.geometry
    transform_fingerprint = canonical_sha256({
        "adapter_version": _ADAPTER_VERSION,
        "physical_frame_id": geometry.physical_frame_id,
        "geometry_mode": geometry_mode,
        "canonical_annotations": geometry_payloads,
        "raw_shape": geometry.raw_shape,
        "pixel_size_nm": geometry.pixel_size_nm,
        "scan_angle_deg": _q(geometry.scan_angle_deg),
    })
    provenance = M6PresentationProvenance(
        raw_shape=geometry.raw_shape,
        expanded_shape=geometry.expanded_shape,
        source_view=frame.source_view,
        frame_origin_xy=geometry.frame_origin_xy,
        canvas_offset_xy=geometry.canvas_offset_xy,
        registration_fingerprint=geometry.registration_fingerprint,
    )
    return M6CanonicalFrame(
        frame_index=frame.frame_index,
        physical_frame_id=geometry.physical_frame_id,
        molecules=molecules,
        analyzed_pixels_xy=analyzed_pixels,
        pixel_area_nm2=geometry.pixel_size_nm[0] * geometry.pixel_size_nm[1],
        coordinate_frame="series_physical_nm",
        coordinate_transform_fingerprint=transform_fingerprint,
        presentation_provenance=provenance,
    )


def _canonical_annotation(
    annotation: M6SourceAnnotation,
    geometry: M6FrameGeometry,
    geometry_mode: GeometryMode,
) -> tuple[M6AnalyzedMolecule, dict[str, object]]:
    expected_shape = (
        geometry.raw_shape
        if annotation.source_view == "raw"
        else geometry.expanded_shape
    )
    if annotation.mask_shape is not None and annotation.mask_shape != expected_shape:
        raise ValueError("mask_shape must match its source_view.")
    raw_bbox = _raw_bbox(annotation.bbox_xyxy, annotation.source_view, geometry)
    raw_mask = _raw_mask(annotation, geometry)
    has_raw_foreground = bool(np.any(raw_mask))
    if (
        geometry_mode == "segmentation_preferred"
        and annotation.mask_pixels_xy
        and not has_raw_foreground
    ):
        raise ValueError(
            "annotation mask does not overlap the observed raw footprint."
        )
    if geometry_mode == "segmentation_preferred" and has_raw_foreground:
        y_indices, x_indices = np.nonzero(raw_mask)
        footprint = tuple(
            sorted((int(x), int(y)) for y, x in zip(y_indices, x_indices))
        )
        centroid_px = (
            _q(float(np.mean(x_indices, dtype=np.float64) + 0.5)),
            _q(float(np.mean(y_indices, dtype=np.float64) + 0.5)),
        )
        source_kind = "segmentation"
        annotation_geometry: object = footprint
    else:
        footprint = _bbox_pixels(raw_bbox, geometry.raw_shape)
        centroid_px = (
            _q((raw_bbox[0] + raw_bbox[2]) / 2.0),
            _q((raw_bbox[1] + raw_bbox[3]) / 2.0),
        )
        source_kind = "bbox_center"
        annotation_geometry = raw_bbox
    centroid_nm = _raw_point_to_sample(centroid_px, geometry)
    molecule = M6AnalyzedMolecule(
        source_id=annotation.source_id,
        raw_centroid_xy=centroid_px,
        centroid_xy_nm=centroid_nm,
        footprint_pixels_xy=footprint,
    )
    payload = {
        "source_id": annotation.source_id,
        "source_kind": source_kind,
        "geometry": annotation_geometry,
        "raw_centroid_xy": centroid_px,
        "centroid_xy_nm": centroid_nm,
    }
    return molecule, payload


def _raw_bbox(
    bbox: tuple[float, float, float, float],
    source_view: CoordinateView,
    geometry: M6FrameGeometry,
) -> tuple[float, float, float, float]:
    x1, y1, x2, y2 = bbox
    if source_view == "expanded_aligned":
        origin_x, origin_y = geometry.frame_origin_xy
        x1, y1, x2, y2 = (
            x1 - origin_x,
            y1 - origin_y,
            x2 - origin_x,
            y2 - origin_y,
        )
    height, width = geometry.raw_shape
    clipped = (
        _q(min(max(x1, 0.0), float(width))),
        _q(min(max(y1, 0.0), float(height))),
        _q(min(max(x2, 0.0), float(width))),
        _q(min(max(y2, 0.0), float(height))),
    )
    if clipped[2] <= clipped[0] or clipped[3] <= clipped[1]:
        raise ValueError("annotation does not overlap the observed raw footprint.")
    return clipped


def _raw_mask(
    annotation: M6SourceAnnotation,
    geometry: M6FrameGeometry,
) -> Any:
    if annotation.mask_shape is None:
        return np.zeros(geometry.raw_shape, dtype=bool)
    mask = np.zeros(annotation.mask_shape, dtype=np.uint8)
    for x, y in annotation.mask_pixels_xy:
        mask[y, x] = 1
    if annotation.source_view == "raw":
        return np.asarray(mask, dtype=bool)
    origin_x, origin_y = geometry.frame_origin_xy
    mapped = affine_transform(
        mask,
        matrix=np.eye(2, dtype=np.float64),
        offset=(origin_y, origin_x),
        output_shape=geometry.raw_shape,
        order=0,
        mode="constant",
        cval=0,
        prefilter=False,
    )
    return np.asarray(mapped, dtype=bool)


def _bbox_pixels(
    bbox: tuple[float, float, float, float],
    raw_shape: tuple[int, int],
) -> tuple[tuple[int, int], ...]:
    height, width = raw_shape
    x1, y1, x2, y2 = bbox
    pixels = tuple(
        (x, y)
        for y in range(max(0, floor(y1)), min(height, ceil(y2)))
        for x in range(max(0, floor(x1)), min(width, ceil(x2)))
    )
    if not pixels:
        raise ValueError("canonical bbox must cover at least one raw pixel.")
    return pixels


def _raw_point_to_sample(
    point_xy: tuple[float, float],
    geometry: M6FrameGeometry,
) -> tuple[float, float]:
    raw_height, _ = geometry.raw_shape
    scale_x, scale_y = geometry.pixel_size_nm
    local_x = point_xy[0] * scale_x
    local_y = (raw_height - point_xy[1]) * scale_y
    angle = radians(geometry.scan_angle_deg)
    return (
        _q(cos(angle) * local_x - sin(angle) * local_y),
        _q(sin(angle) * local_x + cos(angle) * local_y),
    )


def _q(value: float) -> float:
    normalized = round(float(value), 12)
    return 0.0 if normalized == 0.0 else normalized
