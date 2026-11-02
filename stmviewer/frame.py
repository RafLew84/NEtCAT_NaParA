"""An input frame: measurement values and source metadata, separate from display."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from stmviewer.manual_movie_types import MovieHistory
from stmviewer.correspondence_types import CorrespondenceDiagnostics


@dataclass(frozen=True)
class FrameProvenance:
    """Historical source text; never resolved or opened on this computer."""

    source: str
    source_frame_index: int | None


@dataclass(frozen=True)
class AlignmentHistory:
    """Geometry of saved pixels; never a recovered pre-interpolation image."""

    canvas_shape: tuple[int, int]
    padding_ltrb: tuple[int, int, int, int]
    pixel_size_nm: tuple[float, float] | None
    reference: FrameProvenance
    method: str
    device: str
    original_shape: tuple[int, int]
    original_size_nm: tuple[float | None, float | None]
    original_offset_nm: tuple[float | None, float | None]
    shift_xy: tuple[float, float]
    origin_xy: tuple[float, float]
    status: str
    quality_score: float | None
    inherited_uncertainty: bool
    previous: 'AlignmentHistory | None' = None
    manual_movie: MovieHistory | None = None
    manual_frame_index: int | None = None
    correspondence: CorrespondenceDiagnostics | None = None

    @property
    def original_rect(self) -> tuple[float, float, int, int]:
        height, width = self.original_shape
        return (*self.origin_xy, width, height)


@dataclass(frozen=True)
class ImageFrame:
    source: Path
    data: NDArray[np.float64] = field(repr=False)
    raw_header: Mapping[str, str | Mapping[str, str]] = field(repr=False)
    channel: str | None
    signal_unit: str | None
    size_x_nm: float | None
    size_y_nm: float | None
    offset_x_nm: float | None
    offset_y_nm: float | None
    bias_v: float | None
    setpoint_a: float | None
    scan_angle_deg: float | None
    calibration_note: str | None = None
    # Zero-based index in the source MPP, independent of current series position.
    source_frame_index: int | None = None
    measurement_time_s: float | None = None
    measurement_time_raw: str | None = None
    # The opened file/index remain in source/source_frame_index.
    provenance: FrameProvenance | None = None
    metadata_note: str | None = None
    alignment: AlignmentHistory | None = None
