"""An input frame: measurement values and source metadata, separate from display."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class ImageFrame:
    source: Path
    data: NDArray[np.float64] = field(repr=False)
    raw_header: Mapping[str, str] = field(repr=False)
    channel: str | None
    signal_unit: str | None
    size_x_nm: float | None
    size_y_nm: float | None
    offset_x_nm: float | None
    offset_y_nm: float | None
    bias_v: float | None
    setpoint_a: float | None
    scan_angle_deg: float | None
