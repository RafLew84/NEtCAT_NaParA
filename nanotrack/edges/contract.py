"""NPZ contract for subprocess-based DexiNed integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np


DEXINED_CONTRACT_VERSION = 1


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
class DexiNedRunInput:
    """Input payload passed from NanoTrack to the DexiNed subprocess worker."""

    frames: np.ndarray
    polygon_mask: np.ndarray
    frame_indices: np.ndarray | None = None
    inference_resolution_hw: np.ndarray | None = None
    device: str = "auto"
    threshold: float | None = None
    source_view: str = "preprocessed"

    def __post_init__(self) -> None:
        frames = np.asarray(self.frames, dtype=np.float32)
        if frames.ndim not in (3, 4):
            raise ValueError("frames must have shape [T, H, W] or [T, H, W, C].")
        if frames.shape[0] == 0:
            raise ValueError("frames must contain at least one frame.")
        object.__setattr__(self, "frames", frames)

        polygon_mask = np.asarray(self.polygon_mask, dtype=bool)
        if polygon_mask.ndim != 2:
            raise ValueError("polygon_mask must have shape [H, W].")
        if polygon_mask.shape != frames.shape[1:3]:
            raise ValueError("polygon_mask must match the spatial shape of frames.")
        if not np.any(polygon_mask):
            raise ValueError("polygon_mask must contain at least one True pixel.")
        object.__setattr__(self, "polygon_mask", polygon_mask)

        if self.frame_indices is not None:
            frame_indices = np.asarray(self.frame_indices, dtype=np.int32)
            if frame_indices.shape != (frames.shape[0],):
                raise ValueError("frame_indices must have shape [T].")
            if np.any(frame_indices < 0):
                raise ValueError("frame_indices must be non-negative.")
            object.__setattr__(self, "frame_indices", frame_indices)

        if self.inference_resolution_hw is not None:
            resolution = np.asarray(self.inference_resolution_hw, dtype=np.int32)
            if resolution.shape != (2,):
                raise ValueError("inference_resolution_hw must have shape [2].")
            if np.any(resolution <= 0):
                raise ValueError("inference_resolution_hw values must be positive.")
            object.__setattr__(self, "inference_resolution_hw", resolution)

        if self.threshold is not None:
            threshold = float(self.threshold)
            if not 0.0 <= threshold <= 1.0:
                raise ValueError("threshold must be within [0, 1].")
            object.__setattr__(self, "threshold", threshold)

    def to_npz_payload(self) -> dict[str, np.ndarray]:
        payload: dict[str, np.ndarray] = {
            "contract_version": np.asarray(DEXINED_CONTRACT_VERSION, dtype=np.int64),
            "frames": self.frames.astype(np.float32, copy=False),
            "polygon_mask": self.polygon_mask.astype(np.uint8, copy=False),
            "device": np.asarray(self.device),
            "source_view": np.asarray(self.source_view),
        }
        if self.frame_indices is not None:
            payload["frame_indices"] = self.frame_indices.astype(np.int32, copy=False)
        if self.inference_resolution_hw is not None:
            payload["inference_resolution_hw"] = self.inference_resolution_hw.astype(np.int32, copy=False)
        if self.threshold is not None:
            payload["threshold"] = np.asarray(self.threshold, dtype=np.float32)
        return payload

    @classmethod
    def from_npz_payload(cls, payload: Mapping[str, Any]) -> "DexiNedRunInput":
        version = int(np.asarray(_require_key(payload, "contract_version")).item())
        if version != DEXINED_CONTRACT_VERSION:
            raise ValueError(
                f"Unsupported DexiNed contract_version {version}; expected {DEXINED_CONTRACT_VERSION}."
            )
        threshold = payload.get("threshold")
        threshold_value = None if threshold is None else float(np.asarray(threshold).item())
        return cls(
            frames=np.asarray(_require_key(payload, "frames"), dtype=np.float32),
            polygon_mask=np.asarray(_require_key(payload, "polygon_mask"), dtype=bool),
            frame_indices=_optional_array(payload, "frame_indices", dtype=np.int32),
            inference_resolution_hw=_optional_array(payload, "inference_resolution_hw", dtype=np.int32),
            device=str(np.asarray(payload.get("device", "auto")).item()),
            threshold=threshold_value,
            source_view=str(np.asarray(payload.get("source_view", "preprocessed")).item()),
        )


@dataclass(frozen=True)
class DexiNedRunOutput:
    """Output payload returned by the DexiNed subprocess worker."""

    edge_prob: np.ndarray
    edge_binary: np.ndarray | None = None
    model_name: str = "dexined"
    checkpoint_name: str | None = None

    def __post_init__(self) -> None:
        edge_prob = np.asarray(self.edge_prob, dtype=np.float32)
        if edge_prob.ndim != 3:
            raise ValueError("edge_prob must have shape [T, H, W].")
        if edge_prob.shape[0] == 0:
            raise ValueError("edge_prob must contain at least one frame.")
        object.__setattr__(self, "edge_prob", edge_prob)

        if self.edge_binary is not None:
            edge_binary = np.asarray(self.edge_binary, dtype=bool)
            if edge_binary.shape != edge_prob.shape:
                raise ValueError("edge_binary must match the shape of edge_prob.")
            object.__setattr__(self, "edge_binary", edge_binary)

    def to_npz_payload(self) -> dict[str, np.ndarray]:
        payload: dict[str, np.ndarray] = {
            "contract_version": np.asarray(DEXINED_CONTRACT_VERSION, dtype=np.int64),
            "edge_prob": self.edge_prob.astype(np.float32, copy=False),
            "model_name": np.asarray(self.model_name),
        }
        if self.edge_binary is not None:
            payload["edge_binary"] = self.edge_binary.astype(np.uint8, copy=False)
        if self.checkpoint_name is not None:
            payload["checkpoint_name"] = np.asarray(self.checkpoint_name)
        return payload

    @classmethod
    def from_npz_payload(cls, payload: Mapping[str, Any]) -> "DexiNedRunOutput":
        version = int(np.asarray(_require_key(payload, "contract_version")).item())
        if version != DEXINED_CONTRACT_VERSION:
            raise ValueError(
                f"Unsupported DexiNed contract_version {version}; expected {DEXINED_CONTRACT_VERSION}."
            )
        checkpoint_value = payload.get("checkpoint_name")
        checkpoint_name = None if checkpoint_value is None else str(np.asarray(checkpoint_value).item())
        return cls(
            edge_prob=np.asarray(_require_key(payload, "edge_prob"), dtype=np.float32),
            edge_binary=_optional_array(payload, "edge_binary", dtype=bool),
            model_name=str(np.asarray(payload.get("model_name", "dexined")).item()),
            checkpoint_name=checkpoint_name,
        )
