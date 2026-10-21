"""Display-only grayscale conversion shared by previews and thumbnails."""

import numpy as np
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QImage

from stmviewer.frame import ImageFrame


def frame_aspect(frame: ImageFrame) -> float:
    if frame.size_x_nm is not None and frame.size_y_nm is not None:
        return frame.size_x_nm / frame.size_y_nm
    height, width = frame.data.shape
    return width / height


def frame_image(frame: ImageFrame) -> QImage:
    data = frame.data
    finite = np.isfinite(data)
    raster = np.zeros(data.shape, dtype=np.uint8)
    if finite.any():
        values = data[finite]
        low, high = float(values.min()), float(values.max())
        if low == high:
            raster[finite] = 127
        else:
            # Scaling first also handles opposite finite float64 extremes.
            scale = max(abs(low), abs(high))
            values = (values / scale - low / scale) / (high / scale - low / scale)
            raster[finite] = np.clip(values * 255, 0, 255).astype(np.uint8)
    height, width = raster.shape
    return QImage(raster.tobytes(), width, height, raster.strides[0],
                  QImage.Format.Format_Grayscale8).copy()


def frame_thumbnail(frame: ImageFrame) -> QImage:
    aspect = frame_aspect(frame)
    width = min(96.0, 72 * aspect)
    size = QSize(max(1, round(width)), max(1, round(width / aspect)))
    return frame_image(frame).scaled(size, Qt.AspectRatioMode.IgnoreAspectRatio,
                                     Qt.TransformationMode.FastTransformation)
