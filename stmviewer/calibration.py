"""Common physical pixel scale for registration, movie preview and export."""
import math

from stmviewer.frame import ImageFrame


def common_pixel_size(frames: tuple[ImageFrame, ...]) -> tuple[float, float] | None:
    common = None
    for frame in frames:
        x, y = frame.size_x_nm, frame.size_y_nm
        if x is None or y is None or not (math.isfinite(x) and math.isfinite(y) and x > 0 and y > 0):
            return None
        size = (x / frame.data.shape[1], y / frame.data.shape[0])
        if common is not None and not all(math.isclose(a, b, rel_tol=1e-9) for a, b in zip(size, common)):
            return None
        if common is None:
            common = size
    return common
