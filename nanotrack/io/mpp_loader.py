"""Load MPP movies into NanoTrack sequence data models."""

from __future__ import annotations

import os
import re
from typing import Iterable, Optional

import numpy as np

from nanotrack.core import STMSequence, STMSequenceMetadata
from napara.core.data_models import STMImage
from napara.io.mpp_reader import read_mpp_file


def _parse_time_seconds(value: object) -> Optional[float]:
    text = str(value).strip()
    if not text:
        return None
    match = re.match(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", text)
    if not match:
        return None
    return float(match.group(1))


def _extract_frame_times_s(raw_header: dict, frame_count: int) -> Optional[np.ndarray]:
    section = raw_header.get("Frames Synchronization", {})
    if not isinstance(section, dict) or not section:
        return None

    indexed_times: dict[int, float] = {}
    for key, raw_value in section.items():
        match = re.search(r"Frame\s+(\d+)", str(key))
        if not match:
            continue
        frame_index = int(match.group(1))
        time_s = _parse_time_seconds(raw_value)
        if time_s is None:
            continue
        indexed_times[frame_index] = time_s

    if len(indexed_times) < frame_count:
        return None

    frame_times = np.array([indexed_times[idx] for idx in range(frame_count)], dtype=np.float64)
    return frame_times


def _infer_frame_interval_s(frame_times_s: Optional[np.ndarray]) -> Optional[float]:
    if frame_times_s is None or len(frame_times_s) < 2:
        return None
    diffs = np.diff(frame_times_s)
    if np.allclose(diffs, diffs[0]):
        return float(diffs[0])
    return None


def _build_sequence_metadata(frames: list[STMImage], *, reverse_frame_order: bool = False) -> STMSequenceMetadata:
    first = frames[0]
    frame_times_s = _extract_frame_times_s(first.raw_header, len(frames))
    frame_interval_s = _infer_frame_interval_s(frame_times_s)
    if frame_times_s is not None and reverse_frame_order:
        frame_times_s = frame_times_s[::-1].copy()
    return STMSequenceMetadata(
        raw_header=first.raw_header,
        pixels_x=first.pixels_x,
        pixels_y=first.pixels_y,
        size_nm_x=first.size_nm_x,
        size_nm_y=first.size_nm_y,
        offset_nm_x=first.offset_nm_x,
        offset_nm_y=first.offset_nm_y,
        scan_angle_deg=first.scan_angle_deg,
        bias_v=first.bias_v,
        setpoint_a=first.setpoint_a,
        image_type=first.image_type,
        frame_times_s=frame_times_s,
        frame_interval_s=frame_interval_s,
    )


def _normalize_frames(frames: Iterable[STMImage]) -> list[STMImage]:
    ordered = list(frames)
    if not ordered:
        raise ValueError("MPP file did not contain any frames.")
    ordered.sort(key=lambda image: image.frame_index if image.frame_index is not None else -1)
    return ordered


def _orient_frame_for_nanotrack(frame: STMImage) -> np.ndarray:
    """
    Normalize MPP frame orientation for NanoTrack.

    After aligning pyqtgraph to row-major rendering, the current required
    correction against the native MPP viewer is a 180-degree rotation.
    """
    return np.rot90(np.asarray(frame.data), 2)


def load_mpp_sequence(file_path: str, *, reverse_frame_order: bool = False) -> STMSequence:
    """Load a `.mpp` file and convert it into an `STMSequence`."""
    if os.path.splitext(file_path)[1].lower() != ".mpp":
        raise ValueError(f"Unsupported extension for NanoTrack sequence loader: {file_path}")

    frames = _normalize_frames(read_mpp_file(file_path) or [])
    if reverse_frame_order:
        frames = list(reversed(frames))
    try:
        raw_frames = np.stack([_orient_frame_for_nanotrack(frame) for frame in frames], axis=0)
    except ValueError as exc:
        raise ValueError("MPP frames must all share the same shape.") from exc

    return STMSequence(
        source_path=file_path,
        raw_frames=raw_frames,
        metadata=_build_sequence_metadata(frames, reverse_frame_order=reverse_frame_order),
        reverse_frame_order=reverse_frame_order,
    )
