"""Display-only grayscale conversion shared by previews and thumbnails."""

import math

import numpy as np
from PyQt6.QtCore import QRectF, QSize
from PyQt6.QtGui import QBrush, QColor, QImage, QPainter

from stmviewer.frame import ImageFrame


def frame_aspect(frame: ImageFrame, *, pixel_proportions: bool = False) -> float:
    if (not pixel_proportions and frame.size_x_nm is not None
            and frame.size_y_nm is not None and frame.size_y_nm > 0):
        aspect = frame.size_x_nm / frame.size_y_nm
        if math.isfinite(aspect) and aspect > 0:
            return aspect
    height, width = frame.data.shape
    return width / height


def frame_image(frame: ImageFrame, *, gamma: float = 1.0) -> QImage:
    data = frame.data
    finite = np.isfinite(data)
    raster = np.zeros(data.shape, dtype=np.uint8)
    if finite.any():
        values = data[finite]
        low, high = float(values.min()), float(values.max())
        if low == high:
            raster[finite] = int(255 * 0.5 ** (1 / gamma))
        else:
            # Scaling first also handles opposite finite float64 extremes.
            scale = max(abs(low), abs(high))
            values = (values / scale - low / scale) / (high / scale - low / scale)
            raster[finite] = (np.clip(values, 0, 1) ** (1 / gamma) * 255).astype(np.uint8)
    height, width = raster.shape
    if finite.all():
        return QImage(raster.tobytes(), width, height, raster.strides[0],
                      QImage.Format.Format_Grayscale8).copy()
    rgba = np.empty((height, width, 4), dtype=np.uint8)
    rgba[:, :, :3] = raster[:, :, None]
    rgba[:, :, 3] = finite * 255
    return QImage(rgba.tobytes(), width, height, rgba.strides[0],
                  QImage.Format.Format_RGBA8888).copy()


def draw_frame(painter: QPainter, target: QRectF, image: QImage) -> None:
    """Composite missing samples over a screen-sized checker, after gamma."""
    tile = QImage(16, 16, QImage.Format.Format_RGB32)
    tile.fill(QColor(96, 96, 96))
    tile_painter = QPainter(tile)
    tile_painter.fillRect(0, 0, 8, 8, QColor(144, 144, 144))
    tile_painter.fillRect(8, 8, 8, 8, QColor(144, 144, 144))
    tile_painter.end()
    painter.fillRect(target, QBrush(tile))
    painter.drawImage(target, image)


def frame_thumbnail(frame: ImageFrame, *, pixel_proportions: bool = False) -> QImage:
    aspect = frame_aspect(frame, pixel_proportions=pixel_proportions)
    width = min(96.0, 72 * aspect)
    size = QSize(max(1, round(width)), max(1, round(width / aspect)))
    thumbnail = QImage(size, QImage.Format.Format_RGB32)
    painter = QPainter(thumbnail)
    draw_frame(painter, QRectF(0, 0, size.width(), size.height()), frame_image(frame))
    painter.end()
    return thumbnail
