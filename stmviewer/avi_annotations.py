"""Deterministic movie labels, rendered after measurement contrast and gamma."""
from dataclasses import dataclass
import math

import numpy as np
from numpy.typing import NDArray

from stmviewer.avi_raster import MovieGeometry
from stmviewer.frame import ImageFrame


@dataclass(frozen=True)
class AnnotationOptions:
    scale_bar: bool = False
    frame_number: bool = False
    measurement_time: bool = False


@dataclass(frozen=True)
class MovieAnnotations:
    labels: tuple[tuple[str, ...], ...]
    font_scale: float
    text_height: int
    line_height: int
    scale_label: str | None
    scale_pixels: int
    scale_height: int
    image_height: int

    def draw(self, raster: NDArray[np.uint8], index: int) -> None:
        import cv2
        def draw_text(text: str, origin: tuple[int, int]) -> None:
            cv2.putText(raster, text, origin, cv2.FONT_HERSHEY_SIMPLEX, self.font_scale,
                        (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(raster, text, origin, cv2.FONT_HERSHEY_SIMPLEX, self.font_scale,
                        (255, 255, 255), 1, cv2.LINE_AA)

        for row, text in enumerate(self.labels[index]):
            draw_text(text, (16, 16 + self.text_height + row * self.line_height))
        if self.scale_label is not None:
            top = self.image_height - 8 - self.scale_height
            draw_text(self.scale_label, (16, top + 8 + self.text_height))
            # Only the marks have a dark contour; the surrounding image stays visible.
            raster[self.image_height - 20:self.image_height - 15, 15:17 + self.scale_pixels] = 0
            raster[self.image_height - 19:self.image_height - 16, 16:16 + self.scale_pixels] = 255



def prepare_annotations(frames: tuple[ImageFrame, ...], geometry: MovieGeometry,
                        options: AnnotationOptions, *, start: int, total: int) -> MovieAnnotations | None:
    if not (options.scale_bar or options.frame_number or options.measurement_time):
        return None
    try:
        import cv2
    except ImportError as error:
        raise ValueError('Opisy AVI wymagają OpenCV (stmviewer/requirements-avi.txt).') from error
    labels = []
    for position, frame in enumerate(frames, start):
        lines = []
        if options.frame_number:
            lines.append(f'Klatka {position}/{total}')
        if options.measurement_time:
            value = frame.measurement_time_s
            time = f'{value:.12g} s' if value is not None and math.isfinite(value) else 'brak'
            lines.append(f'Czas: {time}')
        labels.append(tuple(lines))
    scale = max(0.5, min(2.0, min(geometry.image_size) / 512))
    (_, height), baseline = cv2.getTextSize('Ag', cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    width = max((cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)[0][0]
                 for lines in labels for line in lines), default=0)
    scale_label = None
    scale_pixels = scale_width = scale_height = 0
    if options.scale_bar:
        image_width = geometry.image_size[0]
        extent = frames[0].size_x_nm if geometry.physical else float(geometry.source_shape[1])
        assert extent is not None
        units_per_pixel = extent / image_width
        target = extent / 4
        power = 10.0 ** math.floor(math.log10(target))
        length = max(value * power for value in (1, 2, 5) if value * power <= target)
        scale_pixels = round(length / units_per_pixel)
        scale_label = f'{length:g} {"nm" if geometry.physical else "px"}'
        scale_width = max(scale_pixels, cv2.getTextSize(scale_label, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)[0][0])
        scale_height = height + baseline + 27
    text_height = 16 + len(labels[0]) * (height + baseline + 8) if labels[0] else 0
    minimum_width = max(width, scale_width) + 32
    minimum_height = text_height + scale_height + (24 if text_height and scale_height else 16)
    if geometry.image_size[0] < minimum_width or geometry.image_size[1] < minimum_height:
        raise ValueError('Obraz jest za mały na czytelne opisy '
                         f'(potrzeba co najmniej {minimum_width} × {minimum_height} px). '
                         'Wyłącz część opisów lub wybierz większy obraz.')
    return MovieAnnotations(tuple(labels), scale, height, height + baseline + 8,
                            scale_label, scale_pixels, scale_height, geometry.image_size[1])
