# napara/io/s94_reader.py
"""
Reads SPECS .s94 STM images. Parses fixed-size binary header and int16 payload.
Converts to physical units (nm for topography; nA for current).
"""

import struct
import numpy as np
import logging
from typing import List, Optional
from napara.core.data_models import STMImage

logger = logging.getLogger(__name__)

S94_HEADER_FORMAT = "<hhhhiffffffhhffffhh"
S94_HEADER_SIZE = struct.calcsize(S94_HEADER_FORMAT)

Z_GAIN_RANGES = {1: 5.5, 2: 22.0, 3: 88.0}

def read_s94_file(file_path: str) -> Optional[List[STMImage]]:
    """
    Read a .s94 file and return a single-frame STMImage list.
    """
    logger.info(f"Reading S94: {file_path}")
    with open(file_path, "rb") as f:
        header_bytes = f.read(S94_HEADER_SIZE)
        if len(header_bytes) != S94_HEADER_SIZE:
            raise ValueError("Incomplete S94 header.")
        (x_pts, y_pts, swapped, image_mode_raw, image_number,
         x_size_nm, y_size_nm, x_off_nm, y_off_nm, scan_speed_nm_s,
         bias_mv, z_gain_raw, section, kp, tn, tv, it,
         scan_angle_deg, z_flag) = struct.unpack(S94_HEADER_FORMAT, header_bytes)

        if x_pts <= 0 or y_pts <= 0:
            raise ValueError("Invalid dimensions in S94 header.")

        expected = x_pts * y_pts * 2
        img_raw = f.read(expected)
        if len(img_raw) != expected:
            raise ValueError("Incomplete S94 image payload.")

    data_raw = np.frombuffer(img_raw, dtype=np.int16).reshape((y_pts, x_pts))

    z_nm_per_raw = None
    if image_mode_raw == 0:
        image_type = "Topography"
        full_range_nm = Z_GAIN_RANGES.get(z_gain_raw)
        if full_range_nm is None:
            data = data_raw.astype(np.float32)
        else:
            z_nm_per_raw = full_range_nm / 65536.0
            data = data_raw.astype(np.float32) * z_nm_per_raw
    elif image_mode_raw == 1:
        image_type = "Current"
        current_nA_per_raw = 20.0 / 65536.0
        data = data_raw.astype(np.float32) * current_nA_per_raw
    else:
        image_type = f"Unknown ({image_mode_raw})"
        data = data_raw.astype(np.float32)

    if swapped == 1:
        data = data.T
        pixels_x = y_pts
        pixels_y = x_pts
        size_nm_x = y_size_nm
        size_nm_y = x_size_nm
    else:
        pixels_x = x_pts
        pixels_y = y_pts
        size_nm_x = x_size_nm
        size_nm_y = y_size_nm

    img = STMImage(
        file_name=file_path,
        raw_header={
            "x_points": x_pts, "y_points": y_pts, "Swapped": swapped,
            "image_mode": image_mode_raw, "Image_Number": image_number,
            "x_size": x_size_nm, "y_size": y_size_nm, "x_offset": x_off_nm,
            "y_offset": y_off_nm, "Scan_Speed": scan_speed_nm_s,
            "Bias_Voltage_mV": bias_mv, "z_gain": z_gain_raw, "Section": section,
            "Kp": kp, "Tn": tn, "Tv": tv, "It": it, "Scan_Angle": scan_angle_deg,
            "z_Flag": z_flag
        },
        data=data,
        pixels_x=pixels_x,
        pixels_y=pixels_y,
        size_nm_x=size_nm_x,
        size_nm_y=size_nm_y,
        offset_nm_x=x_off_nm,
        offset_nm_y=y_off_nm,
        scan_angle_deg=scan_angle_deg,
        bias_v=bias_mv / 1000.0,
        scan_speed_nm_s=scan_speed_nm_s,
        z_nm_per_raw=z_nm_per_raw,
        image_type=image_type,
    )
    return [img]
