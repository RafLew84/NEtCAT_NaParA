"""NPZ contract for subprocess-based point-tracker integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np


POINT_TRACKER_CONTRACT_VERSION = 1


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


@dataclass(frozen=True)
class PointTrackerRunInput:
    """Input payload passed from NanoTrack to a point-tracker subprocess worker."""

    frames: np.ndarray
    query_points_tyx: np.ndarray
    inference_resolution_hw: np.ndarray | None = None
    device: str = "auto"
    query_chunk_size: int | None = None
    causal: bool | None = None
    window_size: int | None = None
    window_overlap: int | None = None
    source_view: str = "preprocessed"

    def __post_init__(self) -> None:
        frames = np.asarray(self.frames, dtype=np.float32)
        if frames.ndim not in (3, 4):
            raise ValueError("frames must have shape [T, H, W] or [T, H, W, C].")
        if frames.shape[0] == 0:
            raise ValueError("frames must contain at least one frame.")
        object.__setattr__(self, "frames", frames)

        query_points = np.asarray(self.query_points_tyx, dtype=np.float32)
        if query_points.ndim != 2 or query_points.shape[1] != 3:
            raise ValueError("query_points_tyx must have shape [N, 3].")
        if query_points.shape[0] == 0:
            raise ValueError("query_points_tyx must contain at least one query point.")
        if not np.all(np.isfinite(query_points)):
            raise ValueError("query_points_tyx values must be finite.")
        query_times = query_points[:, 0]
        if np.any(query_times < 0) or np.any(query_times >= frames.shape[0]):
            raise ValueError("query_points_tyx[:, 0] must reference local frame indices inside frames.")
        object.__setattr__(self, "query_points_tyx", query_points)

        if self.inference_resolution_hw is not None:
            resolution = np.asarray(self.inference_resolution_hw, dtype=np.int32)
            if resolution.shape != (2,):
                raise ValueError("inference_resolution_hw must have shape [2].")
            if np.any(resolution <= 0):
                raise ValueError("inference_resolution_hw values must be positive.")
            object.__setattr__(self, "inference_resolution_hw", resolution)

        if self.query_chunk_size is not None:
            chunk_size = int(self.query_chunk_size)
            if chunk_size <= 0:
                raise ValueError("query_chunk_size must be positive.")
            object.__setattr__(self, "query_chunk_size", chunk_size)

        if self.causal is not None:
            object.__setattr__(self, "causal", bool(self.causal))

        if self.window_size is not None:
            window_size = int(self.window_size)
            if window_size <= 0:
                raise ValueError("window_size must be positive.")
            object.__setattr__(self, "window_size", window_size)

        if self.window_overlap is not None:
            window_overlap = int(self.window_overlap)
            if window_overlap < 0:
                raise ValueError("window_overlap must be non-negative.")
            object.__setattr__(self, "window_overlap", window_overlap)

    def to_npz_payload(self) -> dict[str, np.ndarray]:
        payload: dict[str, np.ndarray] = {
            "contract_version": np.asarray(POINT_TRACKER_CONTRACT_VERSION, dtype=np.int64),
            "frames": self.frames.astype(np.float32, copy=False),
            "query_points_tyx": self.query_points_tyx.astype(np.float32, copy=False),
            "device": np.asarray(self.device),
            "source_view": np.asarray(self.source_view),
        }
        if self.inference_resolution_hw is not None:
            payload["inference_resolution_hw"] = self.inference_resolution_hw.astype(np.int32, copy=False)
        if self.query_chunk_size is not None:
            payload["query_chunk_size"] = np.asarray(self.query_chunk_size, dtype=np.int32)
        if self.causal is not None:
            payload["causal"] = np.asarray(self.causal, dtype=np.uint8)
        if self.window_size is not None:
            payload["window_size"] = np.asarray(self.window_size, dtype=np.int32)
        if self.window_overlap is not None:
            payload["window_overlap"] = np.asarray(self.window_overlap, dtype=np.int32)
        return payload

    @classmethod
    def from_npz_payload(cls, payload: Mapping[str, Any]) -> "PointTrackerRunInput":
        version = int(np.asarray(_require_key(payload, "contract_version")).item())
        if version != POINT_TRACKER_CONTRACT_VERSION:
            raise ValueError(
                f"Unsupported point-tracker contract_version {version}; expected {POINT_TRACKER_CONTRACT_VERSION}."
            )
        query_chunk = payload.get("query_chunk_size")
        causal = payload.get("causal")
        window_size = payload.get("window_size")
        window_overlap = payload.get("window_overlap")
        return cls(
            frames=np.asarray(_require_key(payload, "frames"), dtype=np.float32),
            query_points_tyx=np.asarray(_require_key(payload, "query_points_tyx"), dtype=np.float32),
            inference_resolution_hw=_optional_array(payload, "inference_resolution_hw", dtype=np.int32),
            device=str(np.asarray(payload.get("device", "auto")).item()),
            query_chunk_size=None if query_chunk is None else int(np.asarray(query_chunk).item()),
            causal=None if causal is None else bool(np.asarray(causal).item()),
            window_size=None if window_size is None else int(np.asarray(window_size).item()),
            window_overlap=None if window_overlap is None else int(np.asarray(window_overlap).item()),
            source_view=str(np.asarray(payload.get("source_view", "preprocessed")).item()),
        )


@dataclass(frozen=True)
class PointTrackerRunOutput:
    """Output payload returned by a point-tracker subprocess worker."""

    tracks_xy: np.ndarray
    visible_mask: np.ndarray
    occlusion_scores: np.ndarray | None = None
    confidence_scores: np.ndarray | None = None
    expected_dist: np.ndarray | None = None
    model_name: str = "point_tracker"
    checkpoint_name: str | None = None

    def __post_init__(self) -> None:
        tracks = np.asarray(self.tracks_xy, dtype=np.float32)
        if tracks.ndim != 3 or tracks.shape[2] != 2:
            raise ValueError("tracks_xy must have shape [N, T, 2].")
        if tracks.shape[0] == 0 or tracks.shape[1] == 0:
            raise ValueError("tracks_xy must contain at least one point and one frame.")
        object.__setattr__(self, "tracks_xy", tracks)

        visible = np.asarray(self.visible_mask, dtype=bool)
        if visible.shape != tracks.shape[:2]:
            raise ValueError("visible_mask must have shape [N, T] matching tracks_xy.")
        object.__setattr__(self, "visible_mask", visible)

        self._normalize_optional_matrix("occlusion_scores", self.occlusion_scores, tracks.shape[:2], np.float32)
        self._normalize_optional_matrix("confidence_scores", self.confidence_scores, tracks.shape[:2], np.float32)
        self._normalize_optional_matrix("expected_dist", self.expected_dist, tracks.shape[:2], np.float32)

    def _normalize_optional_matrix(self, attr_name: str, value: np.ndarray | None, shape: tuple[int, int], dtype) -> None:
        if value is None:
            return
        array = np.asarray(value, dtype=dtype)
        if array.shape != shape:
            raise ValueError(f"{attr_name} must have shape [N, T] matching tracks_xy.")
        object.__setattr__(self, attr_name, array)

    def to_npz_payload(self) -> dict[str, np.ndarray]:
        payload: dict[str, np.ndarray] = {
            "contract_version": np.asarray(POINT_TRACKER_CONTRACT_VERSION, dtype=np.int64),
            "tracks_xy": self.tracks_xy.astype(np.float32, copy=False),
            "visible_mask": self.visible_mask.astype(np.uint8, copy=False),
            "model_name": np.asarray(self.model_name),
        }
        if self.occlusion_scores is not None:
            payload["occlusion_scores"] = self.occlusion_scores.astype(np.float32, copy=False)
        if self.confidence_scores is not None:
            payload["confidence_scores"] = self.confidence_scores.astype(np.float32, copy=False)
        if self.expected_dist is not None:
            payload["expected_dist"] = self.expected_dist.astype(np.float32, copy=False)
        if self.checkpoint_name is not None:
            payload["checkpoint_name"] = np.asarray(self.checkpoint_name)
        return payload

    @classmethod
    def from_npz_payload(cls, payload: Mapping[str, Any]) -> "PointTrackerRunOutput":
        version = int(np.asarray(_require_key(payload, "contract_version")).item())
        if version != POINT_TRACKER_CONTRACT_VERSION:
            raise ValueError(
                f"Unsupported point-tracker contract_version {version}; expected {POINT_TRACKER_CONTRACT_VERSION}."
            )
        checkpoint_value = payload.get("checkpoint_name")
        checkpoint_name = None if checkpoint_value is None else str(np.asarray(checkpoint_value).item())
        return cls(
            tracks_xy=np.asarray(_require_key(payload, "tracks_xy"), dtype=np.float32),
            visible_mask=np.asarray(_require_key(payload, "visible_mask"), dtype=bool),
            occlusion_scores=_optional_array(payload, "occlusion_scores", dtype=np.float32),
            confidence_scores=_optional_array(payload, "confidence_scores", dtype=np.float32),
            expected_dist=_optional_array(payload, "expected_dist", dtype=np.float32),
            model_name=str(np.asarray(payload.get("model_name", "point_tracker")).item()),
            checkpoint_name=checkpoint_name,
        )
