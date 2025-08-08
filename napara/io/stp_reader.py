# napara/io/stp_reader.py
"""
Reads Omicron STP STM image files. Text header ends with '[Header end]' then binary doubles.
Parses units and rotates data by 180 degrees to match expected orientation.
"""

import struct
import numpy as np
import logging
import re
from typing import List, Optional
from napara.core.data_models import STMImage

logger = logging.getLogger(__name__)
MAX_HEADER_LINES = 1000

def parse_value_unit(value_str: str, default_unit_factor: float = 1.0) -> float:
    """
    Parse a number with an optional unit and return value in base units (m, V, A).
    """
    value_str = (value_str or "").strip()
    if not value_str:
        return 0.0
    m = re.match(r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s*([a-zA-ZμÅµ]*)", value_str)
    if not m:
        return 0.0
    val = float(m.group(1))
    unit = m.group(2).lower()

    factor = default_unit_factor
    # length
    if unit == 'nm': factor = 1e-9
    elif unit == 'pm': factor = 1e-12
    elif unit in ('å','a','angstrom'): factor = 1e-10
    elif unit in ('μm','um'): factor = 1e-6
    elif unit == 'mm': factor = 1e-3
    # voltage
    elif unit == 'v': factor = 1.0
    elif unit == 'mv': factor = 1e-3
    elif unit in ('uv','μv'): factor = 1e-6
    # current
    elif unit == 'a': factor = 1.0
    elif unit == 'na': factor = 1e-9
    elif unit == 'pa': factor = 1e-12
    elif unit in ('ua','μa'): factor = 1e-6

    return val * factor

def read_stp_file(file_path: str) -> Optional[List[STMImage]]:
    """
    Read an Omicron .stp file and return a single-frame STMImage list.
    """
    logger.info(f"Reading STP: {file_path}")
    header = {}
    header_end_found = False

    with open(file_path, "rb") as f:
        for i in range(MAX_HEADER_LINES):
            pos = f.tell()
            raw = f.readline()
            if not raw:
                break
            line = raw.decode('utf-8', errors='ignore').strip()
            if not line:
                continue
            if line == "[Header end]":
                header_end_found = True
                break
            if ":" in line:
                k, v = line.split(":", 1)
                header[k.strip()] = v.strip()

        if not header_end_found:
            raise ValueError("Missing '[Header end]' in STP header.")

        num_columns = int(header.get("Number of columns", 0))
        num_rows = int(header.get("Number of rows", 0))
        if num_columns <= 0 or num_rows <= 0:
            raise ValueError("Invalid image size in STP header.")

        expected_bytes = num_rows * num_columns * 8
        data_bytes = f.read(expected_bytes)
        if len(data_bytes) != expected_bytes:
            raise ValueError("Incomplete STP binary payload.")

    flat = struct.unpack(f"<{num_rows*num_columns}d", data_bytes)
    data = np.array(flat).reshape((num_rows, num_columns))
    data = np.rot90(data, 2)  # 180 degrees

    size_x_m = parse_value_unit(header.get("X Amplitude", "0"), 1.0)
    size_y_m = parse_value_unit(header.get("Y Amplitude", "0"), 1.0)
    size_nm_x = size_x_m * 1e9
    size_nm_y = size_y_m * 1e9

    off_x_m = parse_value_unit(header.get("X Offset", "0"), 1.0)
    off_y_m = parse_value_unit(header.get("Y Offset", "0"), 1.0)
    offset_nm_x = off_x_m * 1e9
    offset_nm_y = off_y_m * 1e9

    bias_v = parse_value_unit(header.get("Gap Voltage", header.get("Bias", "0")), 1.0)
    setpoint_a = parse_value_unit(header.get("Setpoint", header.get("Current", "0")), 1.0)

    try:
        scan_angle_deg = float(header.get("Angle", "0.0"))
    except ValueError:
        scan_angle_deg = 0.0

    channel = header.get("Channel", "").lower()
    if "z" in channel or "topo" in channel:
        image_type = "Topography"
    elif "current" in channel or "iset" in channel:
        image_type = "Current"
    else:
        image_type = header.get("Channel", "Unknown")

    img = STMImage(
        file_name=file_path,
        raw_header=header,
        data=data,
        pixels_x=num_columns,
        pixels_y=num_rows,
        size_nm_x=size_nm_x,
        size_nm_y=size_nm_y,
        offset_nm_x=offset_nm_x,
        offset_nm_y=offset_nm_y,
        scan_angle_deg=scan_angle_deg,
        bias_v=bias_v,
        setpoint_a=setpoint_a,
        image_type=image_type,
    )
    return [img]
