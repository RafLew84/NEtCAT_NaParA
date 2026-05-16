"""Load supported STM sources into NanoTrack sequence data models."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

import numpy as np

from nanotrack.core import STMSequence, STMSequenceMetadata
from napara.core.data_models import STMImage
from napara.io.factory import load_stm_path

from .mpp_loader import load_mpp_sequence


FRAME_SERIES_EXTENSIONS = {".stp", ".s94"}
SUPPORTED_SEQUENCE_EXTENSIONS = {".mpp", *FRAME_SERIES_EXTENSIONS}


def load_stm_sequence(
    source_paths: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
    *,
    reverse_frame_order: bool = False,
) -> STMSequence:
    """Load `.mpp` movies or `.stp`/`.s94` frame series into an `STMSequence`.

    `.mpp` remains a single-file movie loader. `.stp` and `.s94` are treated as
    one-frame files and loaded strictly in the order provided by the caller.
    """

    paths = _coerce_source_paths(source_paths)
    if len(paths) == 1 and Path(paths[0]).suffix.lower() == ".mpp":
        return load_mpp_sequence(paths[0], reverse_frame_order=reverse_frame_order)

    _validate_frame_series_paths(paths)
    frames = _load_frame_series_strict(paths)
    if reverse_frame_order:
        frames = list(reversed(frames))
        paths = list(reversed(paths))

    raw_frames = _stack_stm_frames(frames)
    return STMSequence(
        source_path=_sequence_source_path(paths),
        raw_frames=raw_frames,
        metadata=_build_frame_series_metadata(frames, paths),
        reverse_frame_order=reverse_frame_order,
    )


def _coerce_source_paths(
    source_paths: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
) -> list[str]:
    if isinstance(source_paths, (str, os.PathLike)):
        paths = [os.fspath(source_paths)]
    else:
        paths = [os.fspath(path) for path in source_paths]
    if not paths:
        raise ValueError("At least one STM source path is required.")
    return paths


def _validate_frame_series_paths(paths: Sequence[str]) -> None:
    for path in paths:
        ext = Path(path).suffix.lower()
        if ext == ".mpp":
            raise ValueError("MPP loading accepts a single .mpp path; frame series loading supports .stp/.s94 only.")
        if ext not in FRAME_SERIES_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_SEQUENCE_EXTENSIONS))
            raise ValueError(f"Unsupported STM source extension for {path!r}. Supported extensions: {supported}.")


def _load_frame_series_strict(paths: Sequence[str]) -> list[STMImage]:
    frames: list[STMImage] = []
    for path in paths:
        try:
            loaded = load_stm_path(path)
        except Exception as exc:
            raise ValueError(f"Cannot load STM source: {path}") from exc
        if not loaded:
            raise ValueError(f"STM source did not contain any frames: {path}")
        frames.extend(loaded)
    return frames


def _stack_stm_frames(frames: Sequence[STMImage]) -> np.ndarray:
    if not frames:
        raise ValueError("STM source did not contain any frames.")

    arrays = [np.asarray(frame.data) for frame in frames]
    for index, frame_data in enumerate(arrays):
        if frame_data.ndim != 2:
            raise ValueError(f"STM frame {index} must be a 2D image.")

    first_shape = arrays[0].shape
    for index, frame_data in enumerate(arrays[1:], start=1):
        if frame_data.shape != first_shape:
            raise ValueError(
                f"STM frame shapes must match for NanoTrack sequences: frame 0 has {first_shape}, "
                f"frame {index} has {frame_data.shape}."
            )
    return np.stack(arrays, axis=0)


def _build_frame_series_metadata(frames: Sequence[STMImage], source_paths: Sequence[str]) -> STMSequenceMetadata:
    first = frames[0]
    raw_header = dict(first.raw_header)
    raw_header["NanoTrack Source"] = {
        "loader": "napara.io.factory.load_stm_path",
        "source_files": list(source_paths),
        "frame_count": len(frames),
        "source_extensions": [Path(path).suffix.lower() for path in source_paths],
    }
    raw_header["NanoTrack Frame Headers"] = [
        {
            "frame_index": index,
            "source_file": frame.file_name,
            "raw_header": frame.raw_header,
        }
        for index, frame in enumerate(frames)
    ]

    return STMSequenceMetadata(
        raw_header=raw_header,
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
        frame_times_s=None,
        frame_interval_s=None,
    )


def _sequence_source_path(paths: Sequence[str]) -> str:
    if len(paths) == 1:
        return paths[0]
    first = Path(paths[0])
    return str(first.with_name(f"{first.stem}_series_{len(paths)}_frames"))
