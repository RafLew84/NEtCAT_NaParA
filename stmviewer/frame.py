"""An input frame: measurement values and source metadata, separate from display."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class FrameProvenance:
    """Historical source text; never resolved or opened on this computer."""

    source: str
    source_frame_index: int | None


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
