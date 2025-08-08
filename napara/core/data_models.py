# napara/core/data_models.py
"""
Defines the core data structure for holding STM image data and metadata.
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple

@dataclass
class STMImage:
    """
    Represents STM image data and associated metadata.
    """
    file_name: str
    raw_header: Dict[str, Any] = field(repr=False)
    data: np.ndarray = field(repr=False)

    pixels_x: int = 0
    pixels_y: int = 0
    size_nm_x: float = 0.0
    size_nm_y: float = 0.0
    offset_nm_x: float = 0.0
    offset_nm_y: float = 0.0
    scan_angle_deg: float = 0.0
    bias_v: float = 0.0
    setpoint_a: Optional[float] = None
    scan_speed_nm_s: Optional[float] = None
    z_nm_per_raw: Optional[float] = None
    image_type: str = "Unknown"
    frame_index: Optional[int] = None  # <- NEW: frame index for movie formats (e.g., MPP)

    def __post_init__(self):
        """
        Ensure pixel dimensions match the data array shape when not provided.
        """
        if self.data is not None:
            if self.pixels_y == 0 and self.pixels_x == 0:
                self.pixels_y, self.pixels_x = self.data.shape
            elif self.pixels_x == 0:
                if self.data.shape[0] == self.pixels_y:
                    self.pixels_x = self.data.shape[1]
                elif self.data.shape[1] == self.pixels_y:
                    self.pixels_x = self.data.shape[0]
            elif self.pixels_y == 0:
                if self.data.shape[1] == self.pixels_x:
                    self.pixels_y = self.data.shape[0]
                elif self.data.shape[0] == self.pixels_x:
                    self.pixels_y = self.data.shape[1]

    def get_pixel_size_nm(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Returns pixel size in nanometers for x and y directions.
        """
        px_x = self.size_nm_x / self.pixels_x if self.pixels_x > 0 and self.size_nm_x > 0 else None
        px_y = self.size_nm_y / self.pixels_y if self.pixels_y > 0 and self.size_nm_y > 0 else None
        return px_x, px_y
