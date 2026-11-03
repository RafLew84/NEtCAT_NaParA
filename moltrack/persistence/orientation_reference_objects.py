from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from math import ceil, floor

import numpy as np

from .reference_dataset import ReferencePayloadFile


@dataclass(frozen=True)
class OrientationArrayObject:
    path: str
    sha256: str
    payload_file: ReferencePayloadFile


@dataclass(frozen=True)
class OrientationLocalMaskObject:
    array_object: OrientationArrayObject
    frame_shape: tuple[int, int]
    footprint_xyxy: tuple[int, int, int, int]
    local_shape: tuple[int, int]

    @property
    def path(self) -> str:
        return self.array_object.path

    @property
    def sha256(self) -> str:
        return self.array_object.sha256


def orientation_array_object(
    kind: str,
    array: object,
) -> OrientationArrayObject:
    """Encode a numeric array deterministically and address it by encoded bytes."""

    value = np.ascontiguousarray(np.asarray(array))
    if value.dtype.hasobject:
        raise ValueError("Orientation reference arrays must not use object dtype.")
    stream = io.BytesIO()
    np.save(stream, value, allow_pickle=False)
    content = stream.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    path = f"objects/{kind}/sha256-{digest}.npy"
    return OrientationArrayObject(
        path=path,
        sha256=digest,
        payload_file=ReferencePayloadFile(path, content, 1),
    )


def orientation_local_mask_object(
    kind: str,
    mask: object,
    *,
    frame_shape: tuple[int, int],
    detection_bbox_xyxy: tuple[float, float, float, float],
) -> OrientationLocalMaskObject:
    """Crop a working full-frame mask to its parent detection footprint."""

    value = np.asarray(mask, dtype=bool)
    if value.shape != frame_shape:
        raise ValueError("Orientation mask must match its working frame.")
    footprint = _detection_footprint(detection_bbox_xyxy, frame_shape)
    x0, y0, x1, y1 = footprint
    local_mask = np.ascontiguousarray(value[y0:y1, x0:x1])
    if not np.any(local_mask):
        raise ValueError("Orientation mask is empty inside its parent detection.")
    if int(np.count_nonzero(local_mask)) != int(np.count_nonzero(value)):
        raise ValueError("Orientation mask extends outside its parent detection.")
    return OrientationLocalMaskObject(
        array_object=orientation_array_object(kind, local_mask),
        frame_shape=frame_shape,
        footprint_xyxy=footprint,
        local_shape=(int(local_mask.shape[0]), int(local_mask.shape[1])),
    )


def _detection_footprint(
    bbox_xyxy: tuple[float, float, float, float],
    frame_shape: tuple[int, int],
) -> tuple[int, int, int, int]:
    height, width = frame_shape
    x0 = max(0, min(width, floor(bbox_xyxy[0])))
    y0 = max(0, min(height, floor(bbox_xyxy[1])))
    x1 = max(0, min(width, ceil(bbox_xyxy[2])))
    y1 = max(0, min(height, ceil(bbox_xyxy[3])))
    if x1 <= x0 or y1 <= y0:
        raise ValueError("Parent detection has no Orientation mask footprint.")
    return x0, y0, x1, y1


def deduplicated_orientation_objects(
    values: list[OrientationArrayObject],
) -> tuple[ReferencePayloadFile, ...]:
    by_path: dict[str, ReferencePayloadFile] = {}
    for value in values:
        previous = by_path.setdefault(value.path, value.payload_file)
        if previous.content != value.payload_file.content:
            raise ValueError("Content-addressed Orientation object collision.")
    return tuple(by_path[path] for path in sorted(by_path))


__all__ = [
    "OrientationArrayObject",
    "OrientationLocalMaskObject",
    "deduplicated_orientation_objects",
    "orientation_array_object",
    "orientation_local_mask_object",
]
