"""NPZ contract shared by optional subprocess-based mask trackers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from .config import MaskTrackerKind


MASK_TRACKER_CONTRACT_VERSION = 1


def _require_key(payload: Mapping[str, Any], key: str) -> Any:
    if key not in payload:
        raise KeyError(f"Missing required NPZ field: {key}")
    return payload[key]


def _optional_array(payload: Mapping[str, Any], key: str, *, dtype=None) -> np.ndarray | None:
    if key not in payload:
        return None
    value = np.asarray(payload[key])
    if dtype is not None:
        value = value.astype(dtype, copy=False)
    return value


def _optional_string(payload: Mapping[str, Any], key: str) -> str | None:
    if key not in payload:
        return None
    return str(np.asarray(payload[key]).item())


@dataclass(frozen=True)
class MaskTrackerRunInput:
    """Input payload passed from NanoTrack to a mask-tracker subprocess worker.

    Contract assumptions:
    - one payload represents one tracking run for one seed object,
    - `frames` are cropped in time from the chosen start frame onward,
    - `frame_index_offset` maps local frame 0 back to the absolute sequence frame,
    - workers may convert `query_box_xyxy` to backend-specific formats internally.
    """

    tracker_kind: MaskTrackerKind | str
    track_id: int
    frame_index_offset: int
    frames: np.ndarray
    query_box_xyxy: np.ndarray | None = None
    query_point_tyx: np.ndarray | None = None
    initial_mask: np.ndarray | None = None
    source_view: str = "preprocessed"
    mask_probability_threshold: float = 0.5

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracker_kind", MaskTrackerKind.from_value(self.tracker_kind))

        if self.track_id < 0:
            raise ValueError("track_id must be non-negative.")
        if self.frame_index_offset < 0:
            raise ValueError("frame_index_offset must be non-negative.")

        frames = np.asarray(self.frames, dtype=np.float32)
        if frames.ndim not in (3, 4):
            raise ValueError("frames must have shape [T, H, W] or [T, H, W, C].")
        if frames.shape[0] == 0:
            raise ValueError("frames must contain at least one frame.")
        object.__setattr__(self, "frames", frames)

        query_box = None if self.query_box_xyxy is None else np.asarray(self.query_box_xyxy, dtype=np.float32)
        if query_box is not None:
            if query_box.shape != (4,):
                raise ValueError("query_box_xyxy must have shape [4].")
            if not np.all(np.isfinite(query_box)):
                raise ValueError("query_box_xyxy values must be finite.")
            object.__setattr__(self, "query_box_xyxy", query_box)

        query_point = None if self.query_point_tyx is None else np.asarray(self.query_point_tyx, dtype=np.float32)
        if query_point is not None:
            if query_point.shape != (3,):
                raise ValueError("query_point_tyx must have shape [3].")
            if not np.all(np.isfinite(query_point)):
                raise ValueError("query_point_tyx values must be finite.")
            local_t = int(query_point[0])
            if not 0 <= local_t < frames.shape[0]:
                raise ValueError("query_point_tyx[0] must reference a local frame inside frames.")
            object.__setattr__(self, "query_point_tyx", query_point)

        mask = None if self.initial_mask is None else np.asarray(self.initial_mask, dtype=bool)
        if mask is not None:
            frame_shape = frames.shape[1:3]
            if mask.shape != frame_shape:
                raise ValueError("initial_mask must match the spatial shape of frames.")
            object.__setattr__(self, "initial_mask", mask)

        if query_box is None and query_point is None and mask is None:
            raise ValueError("At least one prompt must be provided: query_box_xyxy, query_point_tyx, or initial_mask.")

        threshold = float(self.mask_probability_threshold)
        if not np.isfinite(threshold) or not 0.0 < threshold < 1.0:
            raise ValueError("mask_probability_threshold must be finite and in the open range (0, 1).")
        object.__setattr__(self, "mask_probability_threshold", threshold)

    def to_npz_payload(self) -> dict[str, np.ndarray]:
        payload: dict[str, np.ndarray] = {
            "contract_version": np.asarray(MASK_TRACKER_CONTRACT_VERSION, dtype=np.int64),
            "tracker_kind": np.asarray(self.tracker_kind.value),
            "track_id": np.asarray(self.track_id, dtype=np.int64),
            "frame_index_offset": np.asarray(self.frame_index_offset, dtype=np.int64),
            "frames": self.frames.astype(np.float32, copy=False),
            "source_view": np.asarray(self.source_view),
            "mask_probability_threshold": np.asarray(self.mask_probability_threshold, dtype=np.float32),
        }
        if self.query_box_xyxy is not None:
            payload["query_box_xyxy"] = self.query_box_xyxy.astype(np.float32, copy=False)
        if self.query_point_tyx is not None:
            payload["query_point_tyx"] = self.query_point_tyx.astype(np.float32, copy=False)
        if self.initial_mask is not None:
            payload["initial_mask"] = self.initial_mask.astype(np.uint8, copy=False)
        return payload

    @classmethod
    def from_npz_payload(cls, payload: Mapping[str, Any]) -> "MaskTrackerRunInput":
        version = int(np.asarray(_require_key(payload, "contract_version")).item())
        if version != MASK_TRACKER_CONTRACT_VERSION:
            raise ValueError(
                f"Unsupported mask-tracker contract_version {version}; "
                f"expected {MASK_TRACKER_CONTRACT_VERSION}."
            )
        return cls(
            tracker_kind=str(np.asarray(_require_key(payload, "tracker_kind")).item()),
            track_id=int(np.asarray(_require_key(payload, "track_id")).item()),
            frame_index_offset=int(np.asarray(_require_key(payload, "frame_index_offset")).item()),
            frames=np.asarray(_require_key(payload, "frames"), dtype=np.float32),
            query_box_xyxy=_optional_array(payload, "query_box_xyxy", dtype=np.float32),
            query_point_tyx=_optional_array(payload, "query_point_tyx", dtype=np.float32),
            initial_mask=_optional_array(payload, "initial_mask", dtype=bool),
            source_view=str(np.asarray(payload.get("source_view", "preprocessed")).item()),
            mask_probability_threshold=float(np.asarray(payload.get("mask_probability_threshold", 0.5)).item()),
        )


@dataclass(frozen=True)
class MaskTrackerRunOutput:
    """Output payload returned by a mask-tracker subprocess worker."""

    tracker_kind: MaskTrackerKind | str
    track_id: int
    frame_index_offset: int
    masks: np.ndarray
    visible_mask: np.ndarray
    mask_areas: np.ndarray | None = None
    mask_bboxes_xyxy: np.ndarray | None = None
    mask_scores: np.ndarray | None = None
    mask_component_counts: np.ndarray | None = None
    model_name: str = "mask_tracker"
    model_variant: str | None = None
    checkpoint_name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tracker_kind", MaskTrackerKind.from_value(self.tracker_kind))

        if self.track_id < 0:
            raise ValueError("track_id must be non-negative.")
        if self.frame_index_offset < 0:
            raise ValueError("frame_index_offset must be non-negative.")

        masks = np.asarray(self.masks, dtype=bool)
        if masks.ndim != 3:
            raise ValueError("masks must have shape [T, H, W].")
        if masks.shape[0] == 0:
            raise ValueError("masks must contain at least one frame.")
        object.__setattr__(self, "masks", masks)

        visible_mask = np.asarray(self.visible_mask, dtype=bool)
        if visible_mask.shape != (masks.shape[0],):
            raise ValueError("visible_mask must have shape [T] matching masks.")
        object.__setattr__(self, "visible_mask", visible_mask)

        self._normalize_optional_vector("mask_areas", self.mask_areas, masks.shape[0], np.float32)
        self._normalize_optional_vector("mask_scores", self.mask_scores, masks.shape[0], np.float32)
        self._normalize_optional_vector("mask_component_counts", self.mask_component_counts, masks.shape[0], np.int32)

        if self.mask_bboxes_xyxy is not None:
            mask_bboxes = np.asarray(self.mask_bboxes_xyxy, dtype=np.float32)
            if mask_bboxes.shape != (masks.shape[0], 4):
                raise ValueError("mask_bboxes_xyxy must have shape [T, 4].")
            object.__setattr__(self, "mask_bboxes_xyxy", mask_bboxes)

    def _normalize_optional_vector(self, attr_name: str, value: np.ndarray | None, length: int, dtype) -> None:
        if value is None:
            return
        array = np.asarray(value, dtype=dtype)
        if array.shape != (length,):
            raise ValueError(f"{attr_name} must have shape [T].")
        object.__setattr__(self, attr_name, array)

    def to_npz_payload(self) -> dict[str, np.ndarray]:
        payload: dict[str, np.ndarray] = {
            "contract_version": np.asarray(MASK_TRACKER_CONTRACT_VERSION, dtype=np.int64),
            "tracker_kind": np.asarray(self.tracker_kind.value),
            "track_id": np.asarray(self.track_id, dtype=np.int64),
            "frame_index_offset": np.asarray(self.frame_index_offset, dtype=np.int64),
            "masks": self.masks.astype(np.uint8, copy=False),
            "visible_mask": self.visible_mask.astype(np.uint8, copy=False),
            "model_name": np.asarray(self.model_name),
        }
        if self.mask_areas is not None:
            payload["mask_areas"] = self.mask_areas.astype(np.float32, copy=False)
        if self.mask_bboxes_xyxy is not None:
            payload["mask_bboxes_xyxy"] = self.mask_bboxes_xyxy.astype(np.float32, copy=False)
        if self.mask_scores is not None:
            payload["mask_scores"] = self.mask_scores.astype(np.float32, copy=False)
        if self.mask_component_counts is not None:
            payload["mask_component_counts"] = self.mask_component_counts.astype(np.int32, copy=False)
        if self.model_variant is not None:
            payload["model_variant"] = np.asarray(self.model_variant)
        if self.checkpoint_name is not None:
            payload["checkpoint_name"] = np.asarray(self.checkpoint_name)
        return payload

    @classmethod
    def from_npz_payload(cls, payload: Mapping[str, Any]) -> "MaskTrackerRunOutput":
        version = int(np.asarray(_require_key(payload, "contract_version")).item())
        if version != MASK_TRACKER_CONTRACT_VERSION:
            raise ValueError(
                f"Unsupported mask-tracker contract_version {version}; "
                f"expected {MASK_TRACKER_CONTRACT_VERSION}."
            )
        return cls(
            tracker_kind=str(np.asarray(_require_key(payload, "tracker_kind")).item()),
            track_id=int(np.asarray(_require_key(payload, "track_id")).item()),
            frame_index_offset=int(np.asarray(_require_key(payload, "frame_index_offset")).item()),
            masks=np.asarray(_require_key(payload, "masks"), dtype=bool),
            visible_mask=np.asarray(_require_key(payload, "visible_mask"), dtype=bool),
            mask_areas=_optional_array(payload, "mask_areas", dtype=np.float32),
            mask_bboxes_xyxy=_optional_array(payload, "mask_bboxes_xyxy", dtype=np.float32),
            mask_scores=_optional_array(payload, "mask_scores", dtype=np.float32),
            mask_component_counts=_optional_array(payload, "mask_component_counts", dtype=np.int32),
            model_name=str(np.asarray(payload.get("model_name", "mask_tracker")).item()),
            model_variant=_optional_string(payload, "model_variant"),
            checkpoint_name=_optional_string(payload, "checkpoint_name"),
        )
