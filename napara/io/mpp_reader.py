# napara/io/mpp_reader.py
"""
Reads Omicron MPP (movie) files. Returns a list of STMImage frames.
"""

import struct
import numpy as np
import logging
import os
from typing import List, Dict, Any, Optional
from napara.core.data_models import STMImage
from .stp_reader import parse_value_unit

logger = logging.getLogger(__name__)
MAX_HEADER_LINES = 1000

def read_mpp_file(file_path: str) -> Optional[List[STMImage]]:
    """
    Read an .mpp file and return a frame list of STMImage.
    """
    logger.info(f"Reading MPP: {file_path}")
    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    images: List[STMImage] = []
    header_info: Dict[str, Any] = {}
    header_end = False
    header_end_pos = -1
    section = None

    with open(file_path, "rb") as f:
        # Header with sections: [Section]\nKey: Value
        for i in range(MAX_HEADER_LINES):
            raw = f.readline()
            if not raw:
                break
            try:
                line = raw.decode('utf-8', errors='ignore').strip()
            except Exception:
                line = raw.decode('latin-1', errors='ignore').strip()

            if not line:
                continue
            if line.strip().lower() == "[header end]":
                header_end = True
                header_end_pos = f.tell()
                break
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1]
                header_info.setdefault(section, {})
                continue
            if ":" in line and section:
                k, v = line.split(":", 1)
                header_info[section][k.strip()] = v.strip()

        if not header_end:
            raise ValueError("Missing [Header end] in MPP.")

        general = header_info.get("General Info", {})
        control = header_info.get("Control", {})
        head_settings = header_info.get("Head Settings", {})

        cols = int(general.get("Number of columns", 0))
        rows = int(general.get("Number of rows", 0))
        frames = int(general.get("Number of Frames", 0))
        if cols <= 0 or rows <= 0 or frames <= 0:
            raise ValueError("Invalid dimensions/frames in MPP header.")

        size_x_m = parse_value_unit(control.get("X Amplitude", "0"), 1.0)
        size_y_m = parse_value_unit(control.get("Y Amplitude", "0"), 1.0)
        size_nm_x = size_x_m * 1e9
        size_nm_y = size_y_m * 1e9

        off_x_m = parse_value_unit(control.get("X Offset", general.get("X-Offset", "0")), 1.0)
        off_y_m = parse_value_unit(control.get("Y Offset", general.get("Y-Offset", "0")), 1.0)
        offset_nm_x = off_x_m * 1e9
        offset_nm_y = off_y_m * 1e9

        bias_v = parse_value_unit(control.get("Gap Voltage", control.get("Topography Bias", general.get("Bias", "0"))), 1.0)
        setpoint_a = parse_value_unit(control.get("Setpoint", control.get("Set Point", general.get("Current", "0"))), 1.0)

        try:
            scan_angle_deg = float(general.get("Angle", "0.0"))
        except ValueError:
            scan_angle_deg = 0.0

        channel = general.get("Acquisition channel", "").lower()
        if "z" in channel or "topo" in channel:
            image_type = "Topography"
        elif "current" in channel or "curr" in channel:
            image_type = "Current"
        else:
            image_type = general.get("Acquisition channel", "Unknown")

        f.seek(header_end_pos)
        pts = rows * cols
        bytes_per_frame = pts * 8

        for fi in range(frames):
            payload = f.read(bytes_per_frame)
            if len(payload) != bytes_per_frame:
                raise ValueError(f"Incomplete frame {fi+1}/{frames}.")
            flat = struct.unpack(f"<{pts}d", payload)
            data = np.array(flat).reshape((rows, cols))
            # NOTE: if orientation needs to match STP exactly, apply np.rot90(data, 2) here.

            img = STMImage(
                file_name=os.path.basename(file_path),
                raw_header=header_info,
                data=data,
                pixels_x=cols,
                pixels_y=rows,
                size_nm_x=size_nm_x,
                size_nm_y=size_nm_y,
                offset_nm_x=offset_nm_x,
                offset_nm_y=offset_nm_y,
                scan_angle_deg=scan_angle_deg,
                bias_v=bias_v,
                setpoint_a=setpoint_a,
                image_type=image_type,
                frame_index=fi,
            )
            images.append(img)

    logger.info(f"MPP read OK: {file_path} ({len(images)} frames).")
    return images
