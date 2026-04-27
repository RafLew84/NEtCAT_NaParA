"""Materialized aligned registration views."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
from scipy.ndimage import affine_transform

from nanotrack.core import RegistrationResultSet, STMSequenceMetadata

from .preview import apply_translation_to_frame


@dataclass
class ExpandedAlignedStack:
    """Aligned registration stack materialized on an expanded canvas."""

    frames: np.ndarray
    canvas_offset_xy: tuple[float, float]
    padding_ltrb: tuple[int, int, int, int]
    frame_origins_xy: np.ndarray
    metadata: STMSequenceMetadata

    def __post_init__(self) -> None:
        frames = np.asarray(self.frames, dtype=np.float32)
        if frames.ndim != 3:
            raise ValueError("frames must be a 3D stack.")
        self.frames = frames

        offset = np.asarray(self.canvas_offset_xy, dtype=np.float64)
        if offset.shape != (2,) or not np.all(np.isfinite(offset)):
            raise ValueError("canvas_offset_xy must contain two finite values.")
        self.canvas_offset_xy = (float(offset[0]), float(offset[1]))

        if len(self.padding_ltrb) != 4:
            raise ValueError("padding_ltrb must contain four values: left, top, right, bottom.")
        padding = tuple(int(value) for value in self.padding_ltrb)
        if any(value < 0 for value in padding):
            raise ValueError("padding_ltrb values must be non-negative.")
        self.padding_ltrb = padding

        origins = np.asarray(self.frame_origins_xy, dtype=np.float64)
        if origins.shape != (frames.shape[0], 2):
            raise ValueError("frame_origins_xy must have shape [frame_count, 2].")
        if not np.all(np.isfinite(origins)):
            raise ValueError("frame_origins_xy values must be finite.")
        self.frame_origins_xy = origins

        if not isinstance(self.metadata, STMSequenceMetadata):
            raise TypeError("metadata must be an STMSequenceMetadata instance.")


def build_aligned_frames(
    frames: np.ndarray,
    result_set: RegistrationResultSet,
    *,
    interpolation_order: int = 1,
) -> np.ndarray:
    """Apply stored global translations to a raw frame stack."""

    source_stack = _ensure_frame_stack(frames)
    if not isinstance(result_set, RegistrationResultSet):
        raise TypeError("result_set must be a RegistrationResultSet instance.")

    frame_count = int(source_stack.shape[0])
    expected_indices = set(range(frame_count))
    result_indices = set(result_set.frame_indices)
    if result_indices != expected_indices:
        missing = sorted(expected_indices - result_indices)
        extra = sorted(result_indices - expected_indices)
        details: list[str] = []
        if missing:
            details.append(f"missing frame results: {missing}")
        if extra:
            details.append(f"out-of-range frame results: {extra}")
        raise ValueError("registration results do not match frame stack: " + "; ".join(details))

    aligned = np.empty_like(source_stack, dtype=np.float32)
    for frame_index in range(frame_count):
        result = result_set.get_result(frame_index)
        if result is None:
            raise ValueError(f"missing registration result for frame {frame_index}.")
        aligned[frame_index] = apply_translation_to_frame(
            source_stack[frame_index],
            result.shift_xy,
            interpolation_order=interpolation_order,
        )
    return aligned


def build_expanded_aligned_frames(
    frames: np.ndarray,
    result_set: RegistrationResultSet,
    *,
    metadata: STMSequenceMetadata | None = None,
    interpolation_order: int = 1,
    fill_value: float = np.nan,
) -> ExpandedAlignedStack:
    """Apply stored translations on a canvas large enough to avoid edge clipping."""

    source_stack = _ensure_frame_stack(frames)
    _validate_result_set_matches_frames(result_set, frame_count=int(source_stack.shape[0]))
    order = _normalize_interpolation_order(interpolation_order)
    cval = float(fill_value)

    padding_ltrb = _expanded_padding_from_result_set(result_set)
    left, top, right, bottom = padding_ltrb
    frame_count, height, width = source_stack.shape
    output_shape = (int(height + top + bottom), int(width + left + right))
    expanded = np.empty((frame_count, *output_shape), dtype=np.float32)
    frame_origins = np.empty((frame_count, 2), dtype=np.float64)

    for frame_index in range(frame_count):
        result = result_set.get_result(frame_index)
        if result is None:
            raise ValueError(f"missing registration result for frame {frame_index}.")
        dx, dy = result.shift_xy
        frame_origins[frame_index] = (float(left + dx), float(top + dy))
        expanded[frame_index] = _translate_frame_to_expanded_canvas(
            source_stack[frame_index],
            shift_xy=(float(dx), float(dy)),
            padding_left_top=(left, top),
            output_shape=output_shape,
            interpolation_order=order,
            fill_value=cval,
        )

    return ExpandedAlignedStack(
        frames=expanded,
        canvas_offset_xy=(float(left), float(top)),
        padding_ltrb=padding_ltrb,
        frame_origins_xy=frame_origins,
        metadata=_expanded_metadata(metadata, output_shape=output_shape, padding_ltrb=padding_ltrb),
    )


def _ensure_frame_stack(frames: np.ndarray) -> np.ndarray:
    stack = np.asarray(frames, dtype=np.float32)
    if stack.ndim != 3:
        raise ValueError("frames must be a 3D array with shape (frame, height, width).")
    if stack.shape[0] < 1:
        raise ValueError("aligned registration view requires at least one frame.")
    if stack.shape[1] < 1 or stack.shape[2] < 1:
        raise ValueError("registration frames must be non-empty.")
    if not np.all(np.isfinite(stack)):
        raise ValueError("frames must contain only finite values.")
    return stack


def _validate_result_set_matches_frames(result_set: RegistrationResultSet, *, frame_count: int) -> None:
    if not isinstance(result_set, RegistrationResultSet):
        raise TypeError("result_set must be a RegistrationResultSet instance.")

    expected_indices = set(range(frame_count))
    result_indices = set(result_set.frame_indices)
    if result_indices != expected_indices:
        missing = sorted(expected_indices - result_indices)
        extra = sorted(result_indices - expected_indices)
        details: list[str] = []
        if missing:
            details.append(f"missing frame results: {missing}")
        if extra:
            details.append(f"out-of-range frame results: {extra}")
        raise ValueError("registration results do not match frame stack: " + "; ".join(details))


def _expanded_padding_from_result_set(result_set: RegistrationResultSet) -> tuple[int, int, int, int]:
    shifts = result_set.shifts_xy_array()
    if shifts.ndim != 2 or shifts.shape[1] != 2:
        raise ValueError("registration shifts must have shape [frame_count, 2].")
    if shifts.shape[0] == 0:
        raise ValueError("expanded aligned view requires at least one registration result.")
    if not np.all(np.isfinite(shifts)):
        raise ValueError("registration shifts must contain only finite values.")

    dx = shifts[:, 0]
    dy = shifts[:, 1]
    left = int(np.ceil(max(0.0, -float(np.min(dx)))))
    right = int(np.ceil(max(0.0, float(np.max(dx)))))
    top = int(np.ceil(max(0.0, -float(np.min(dy)))))
    bottom = int(np.ceil(max(0.0, float(np.max(dy)))))
    return left, top, right, bottom


def _translate_frame_to_expanded_canvas(
    frame: np.ndarray,
    *,
    shift_xy: tuple[float, float],
    padding_left_top: tuple[int, int],
    output_shape: tuple[int, int],
    interpolation_order: int,
    fill_value: float,
) -> np.ndarray:
    left, top = padding_left_top
    dx, dy = shift_xy
    translated = affine_transform(
        np.asarray(frame, dtype=np.float32),
        matrix=np.eye(2, dtype=np.float64),
        offset=(-float(top) - float(dy), -float(left) - float(dx)),
        output_shape=output_shape,
        order=interpolation_order,
        mode="constant",
        cval=fill_value,
        prefilter=interpolation_order > 1,
    )
    return np.asarray(translated, dtype=np.float32)


def _expanded_metadata(
    metadata: STMSequenceMetadata | None,
    *,
    output_shape: tuple[int, int],
    padding_ltrb: tuple[int, int, int, int],
) -> STMSequenceMetadata:
    pixels_y, pixels_x = int(output_shape[0]), int(output_shape[1])
    if metadata is None:
        return STMSequenceMetadata(pixels_x=pixels_x, pixels_y=pixels_y)
    if not isinstance(metadata, STMSequenceMetadata):
        raise TypeError("metadata must be an STMSequenceMetadata instance.")

    left, top, _right, _bottom = padding_ltrb
    px_x, px_y = metadata.get_pixel_size_nm()
    size_nm_x = float(pixels_x * px_x) if px_x is not None else 0.0
    size_nm_y = float(pixels_y * px_y) if px_y is not None else 0.0
    offset_nm_x = float(metadata.offset_nm_x - left * px_x) if px_x is not None else metadata.offset_nm_x
    offset_nm_y = float(metadata.offset_nm_y - top * px_y) if px_y is not None else metadata.offset_nm_y
    return replace(
        metadata,
        pixels_x=pixels_x,
        pixels_y=pixels_y,
        size_nm_x=size_nm_x,
        size_nm_y=size_nm_y,
        offset_nm_x=offset_nm_x,
        offset_nm_y=offset_nm_y,
    )


def _normalize_interpolation_order(interpolation_order: int) -> int:
    order = int(interpolation_order)
    if order < 0 or order > 5:
        raise ValueError("interpolation_order must be between 0 and 5.")
    return order
