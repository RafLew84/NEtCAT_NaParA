"""S94 adapter with explicit byte order, calibrated values and source metadata.

The header layout and calibration ranges follow the shared SPECS reader.
Decoding locally avoids its native-endian int16 and implicit signal units.
"""

import math
import os
from pathlib import Path
import struct

import numpy as np

from napara.io.s94_reader import S94_HEADER_FORMAT, S94_HEADER_SIZE, Z_GAIN_RANGES
from stmviewer.frame import ImageFrame

_FIELDS = (
    "x_points", "y_points", "Swapped", "image_mode", "Image_Number",
    "x_size", "y_size", "x_offset", "y_offset", "Scan_Speed", "Bias_Voltage_mV",
    "z_gain", "Section", "Kp", "Tn", "Tv", "It", "Scan_Angle", "z_Flag",
)


def _finite(value: float, *, positive: bool = False) -> float | None:
    return value if math.isfinite(value) and (not positive or value > 0) else None


def open_s94(path: str | Path) -> ImageFrame:
    """Read one little-endian S94, keeping its own calibration and provenance."""
    source = Path(path).resolve()
    try:
        with source.open("rb") as stream:
            raw_header = stream.read(S94_HEADER_SIZE)
            if len(raw_header) != S94_HEADER_SIZE:
                raise ValueError("Niepełny nagłówek S94.")
            header = dict(zip(_FIELDS, struct.unpack(S94_HEADER_FORMAT, raw_header), strict=True))
            width, height = int(header["x_points"]), int(header["y_points"])
            if width <= 0 or height <= 0:
                raise ValueError("Nieprawidłowe wymiary S94.")
            if header["Swapped"] not in (0, 1):
                raise ValueError(f"Nieprawidłowa flaga Swapped: {header['Swapped']}.")
            if os.fstat(stream.fileno()).st_size < S94_HEADER_SIZE + width * height * 2:
                raise ValueError("Niepełne dane obrazu S94.")
            payload = stream.read(width * height * 2)
            if len(payload) != width * height * 2:
                raise ValueError("Niepełne dane obrazu S94.")
        data = np.frombuffer(payload, dtype="<i2").astype(np.float64).reshape(height, width)
        mode, gain = int(header["image_mode"]), int(header["z_gain"])
        channel = {0: "Topography", 1: "Current"}.get(mode, f"Unknown ({mode})")
        unit = None
        note = None
        if mode == 0 and gain in Z_GAIN_RANGES:
            data *= Z_GAIN_RANGES[gain] / 65536.0
            unit = "nm"
        elif mode == 1:
            data *= 20.0 / 65536.0
            unit = "nA"
        elif mode == 0:
            note = f"Wartości surowe S94: nieznane wzmocnienie Z ({gain})."
        else:
            note = f"Wartości surowe S94: nieznany tryb ({mode})."
    except (OSError, ValueError, OverflowError, struct.error) as error:
        raise ValueError(f"{source}: {error}") from error
    x_size, y_size = float(header["x_size"]), float(header["y_size"])
    x_offset, y_offset = float(header["x_offset"]), float(header["y_offset"])
    if header["Swapped"] == 1:
        data = data.T
        x_size, y_size = y_size, x_size
        x_offset, y_offset = y_offset, x_offset
    return ImageFrame(
        source=source, data=data,
        raw_header={key: str(value) for key, value in header.items()},
        channel=channel, signal_unit=unit, calibration_note=note,
        size_x_nm=_finite(x_size, positive=True), size_y_nm=_finite(y_size, positive=True),
        offset_x_nm=_finite(x_offset), offset_y_nm=_finite(y_offset),
        bias_v=_finite(float(header["Bias_Voltage_mV"]) / 1000.0),
        setpoint_a=None, scan_angle_deg=float(header["Scan_Angle"]),
    )
