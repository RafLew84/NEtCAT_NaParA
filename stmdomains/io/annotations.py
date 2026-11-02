"""Read optional MolTrack annotations without loading the MolTrack application."""

from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from types import MappingProxyType
from typing import Any

import numpy as np

from stmdomains.core.annotations import BBox, Detection, FrameAnnotations, Polygon, Segmentation
from stmdomains.core.registration import Registration
from stmdomains.io.annotation_records import bbox, read_section, section_message
from stmdomains.io.mask_codec import decode_mask


class AnnotationStore:
    def __init__(
        self, payload: dict[str, Any], frame_count: int,
        registration: Registration, raw_shape: tuple[int, int],
        *, cache_frames: int = 2, cache_bytes: int = 64 * 1024**2,
    ) -> None:
        self.frame_count = frame_count
        self.registration = registration
        self.raw_shape = raw_shape
        self._detections = read_section(payload.get("molecular_detections"), "detections", frame_count)
        self._segmentations = read_section(payload.get("molecular_segmentations"), "segmentations", frame_count)
        self._cache_frames = max(0, cache_frames)
        self._cache_bytes = max(0, cache_bytes)
        self._cache: OrderedDict[tuple[int, str], tuple[FrameAnnotations, int]] = OrderedDict()
        self._lock = RLock()

    @property
    def cache_info(self) -> tuple[int, int]:
        """Number of cached frame/view entries and their decoded raster bytes."""
        with self._lock:
            return len(self._cache), sum(size for _, size in self._cache.values())

    def frame(self, index: int, view: str = "raw") -> FrameAnnotations:
        with self._lock:
            key = (index, view)
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached[0]
            result = self._prepare_frame(index, view)
            size = sum(item.mask.nbytes for item in result.segmentations if item.mask is not None)
            if self._cache_frames and size <= self._cache_bytes:
                while self._cache and (len(self._cache) >= self._cache_frames
                                      or self.cache_info[1] + size > self._cache_bytes):
                    self._cache.popitem(last=False)
                self._cache[key] = (result, size)
            return result

    def _prepare_frame(self, index: int, view: str) -> FrameAnnotations:
        if not 0 <= index < self.frame_count:
            raise IndexError("Indeks oznaczeń poza zakresem serii.")
        self.registration.field_rect(index, view)
        detections = []
        diagnostics = list(self._detections.diagnostics)
        for identifier, record in self._detections.frames.get(index, []):
            try:
                offset = self._offset(record, index, view)
                source_box = bbox(record["bbox_xyxy"])
                box = self._shift_box(source_box, offset)
                try:
                    original = bbox(record.get("original_bbox_xyxy", source_box))
                except ValueError as exc:
                    original = None
                    diagnostics.append(f"Oznaczenie {identifier}, historyczna ramka: {exc}")
                x, y, width, height = self.registration.field_rect(index, view)
                outside = box[2] <= x or box[3] <= y or box[0] >= x + width or box[1] >= y + height
                detections.append(Detection(
                    identifier, index, box, source_box, original,
                    record.get("source_view", "raw"), outside, MappingProxyType(dict(record)),
                ))
            except (TypeError, ValueError) as exc:
                diagnostics.append(f"Oznaczenie {identifier}: {exc}")
        state = "partial" if len(diagnostics) > len(self._detections.diagnostics) else self._detections.state
        segmentations = []
        segmentation_diagnostics = list(self._segmentations.diagnostics)
        valid_ids = {identifier for identifier, record in self._detections.frames.get(index, [])
                     if record.get("detection_id") == identifier}
        for identifier, record in self._segmentations.frames.get(index, []):
            try:
                item = self._segmentation(identifier, record, index, view, valid_ids)
                segmentations.append(item)
                segmentation_diagnostics.extend(item.diagnostics)
            except (TypeError, ValueError) as exc:
                segmentation_diagnostics.append(f"Segmentacja {identifier}: {exc}")
        segmentation_state = self._segmentations.state
        if len(segmentation_diagnostics) > len(self._segmentations.diagnostics):
            segmentation_state = "partial"
        detection_message = section_message(state, len(detections))
        outside_count = sum(item.outside_field for item in detections)
        if outside_count:
            detection_message += f" · poza polem pomiarowym: {outside_count}"
        return FrameAnnotations(
            tuple(detections), tuple(segmentations), tuple(diagnostics + segmentation_diagnostics),
            state, segmentation_state, detection_message,
            section_message(segmentation_state, len(segmentations), masks=True),
        )

    def _segmentation(
        self, identifier: str, record: dict[str, Any], index: int, view: str,
        valid_ids: set[str],
    ) -> Segmentation:
        offset = self._offset(record, index, view)
        source = record.get("source_view", "raw")
        links = record.get("prompt_detection_ids", [])
        if (not isinstance(links, list) or any(not isinstance(x, str) or x not in valid_ids for x in links)
                or len(set(links)) != len(links)):
            raise ValueError("Niepoprawne powiązanie z oznaczeniem tej klatki.")
        diagnostics = []
        box = None
        if record.get("bbox_xyxy") is not None:
            try:
                box = self._shift_box(bbox(record["bbox_xyxy"]), offset)
            except ValueError as exc:
                diagnostics.append(f"Segmentacja {identifier}, ramka: {exc}")
        polygon: Polygon | None = None
        if record.get("polygon_xy") is not None:
            try:
                points = np.asarray(record["polygon_xy"], dtype=float)
                if points.ndim != 2 or points.shape[1] != 2 or len(points) < 3 or not np.isfinite(points).all():
                    raise ValueError("Niepoprawne wierzchołki obrysu.")
                polygon = tuple((float(x) + offset[0], float(y) + offset[1]) for x, y in points)
            except (TypeError, ValueError) as exc:
                diagnostics.append(f"Segmentacja {identifier}, obrys: {exc}")
        mask = None
        try:
            shape = self.raw_shape if source == "raw" else self.registration.expanded_shape
            decoded = decode_mask(record.get("mask"), shape)
            if decoded is not None:
                mask = self.registration.transform_mask(decoded, index, source, view)
                mask.setflags(write=False)
        except (TypeError, ValueError) as exc:
            diagnostics.append(f"Segmentacja {identifier}, maska: {exc}")
        return Segmentation(identifier, index, box, polygon, mask, tuple(links), source,
                            MappingProxyType(dict(record)), tuple(diagnostics))

    def _offset(self, record: dict[str, Any], index: int, target: str) -> tuple[float, float]:
        source = record.get("source_view", "raw")
        origin = (0.0, 0.0)
        if source == "expanded_aligned" or target == "expanded_aligned":
            origin = self.registration.origin(index)
        metadata = record.get("metadata")
        saved = record.get("registered_frame_origin_xy")
        if isinstance(metadata, dict):
            saved = metadata.get("registered_frame_origin_xy", saved)
        if saved is not None and self.registration.available:
            values = np.asarray(saved, dtype=float)
            if values.shape != (2,) or not np.allclose(values, self.registration.origin(index), rtol=0, atol=1e-6):
                raise ValueError("Zapisany początek klatki jest niezgodny z rejestracją.")
        if source == target:
            return 0.0, 0.0
        sign = 1 if target == "expanded_aligned" else -1
        return origin[0] * sign, origin[1] * sign

    @staticmethod
    def _shift_box(box: BBox, offset: tuple[float, float]) -> BBox:
        dx, dy = offset
        return box[0] + dx, box[1] + dy, box[2] + dx, box[3] + dy
