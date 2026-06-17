from __future__ import annotations

import os

import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from napara.gui.widgets.viewer_widget import ViewerWidget


class STMSeriesViewer(QWidget):
    """Minimal STM image-series viewer for MolTrack."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._series = None
        self._visible_molecular_detection_count = 0
        self._visible_molecular_detection_colors: list[tuple[int, int, int]] = []
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        self.lbl_title = QLabel("No STM series loaded", self)
        self.lbl_meta = QLabel("-", self)
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_meta)

        self.viewer = ViewerWidget(self)
        layout.addWidget(self.viewer, 1)

    def clear(self) -> None:
        self._series = None
        self.clear_molecular_detection_overlays()
        self.lbl_title.setText("No STM series loaded")
        self.lbl_meta.setText("-")
        self.viewer.clear()

    def set_image_series(self, series) -> None:
        self._series = series
        self.show_frame(series.active_frame_index, preserve_zoom=False)

    def show_frame(self, frame_index: int, *, preserve_zoom: bool = True) -> None:
        if self._series is None:
            self.clear()
            return

        self._series.set_active_frame(frame_index)
        px_x, px_y = self._series.pixel_size_nm
        frame = self._series.active_frame
        file_name = os.path.basename(self._series.source_path)
        current = self._series.active_frame_index + 1
        total = self._series.frame_count
        image_type = getattr(self._series.metadata, "image_type", "") or "n/a"
        self.show_image(
            frame,
            title=f"{file_name} | Frame {current}/{total}",
            meta=f"Shape: {frame.shape[1]}x{frame.shape[0]} px | Channel: {image_type}",
            scale_nm_per_px=(px_x, px_y),
            preserve_zoom=preserve_zoom,
        )
        self.show_molecular_detections(source_view="raw", scale_nm_per_px=(px_x, px_y))

    def show_expanded_aligned_frame(self, series, expanded_stack, frame_index: int, *, preserve_zoom: bool = True) -> None:
        self._series = series
        self._series.set_active_frame(frame_index)
        metadata = getattr(expanded_stack, "metadata", self._series.metadata)
        get_pixel_size = getattr(metadata, "get_pixel_size_nm", None)
        px_x, px_y = get_pixel_size() if callable(get_pixel_size) else self._series.pixel_size_nm
        frame = expanded_stack.frames[self._series.active_frame_index]
        file_name = os.path.basename(self._series.source_path)
        current = self._series.active_frame_index + 1
        total = self._series.frame_count
        left, top, right, bottom = expanded_stack.padding_ltrb
        self.show_image(
            frame,
            title=f"{file_name} | Expanded aligned frame {current}/{total}",
            meta=(
                f"Shape: {frame.shape[1]}x{frame.shape[0]} px | "
                f"Padding: {left},{top},{right},{bottom} px"
            ),
            scale_nm_per_px=(px_x, px_y),
            preserve_zoom=preserve_zoom,
        )
        self.show_molecular_detections(source_view="expanded_aligned", scale_nm_per_px=(px_x, px_y))

    def show_image(
        self,
        frame,
        *,
        title: str,
        meta: str,
        scale_nm_per_px: tuple[float | None, float | None],
        preserve_zoom: bool = True,
    ) -> None:
        self.viewer.set_image(
            frame,
            scale_nm_per_px=scale_nm_per_px,
            preserve_zoom=preserve_zoom,
            auto_levels=True,
        )
        self.lbl_title.setText(str(title))
        self.lbl_meta.setText(str(meta))

    def clear_molecular_detection_overlays(self) -> None:
        self.viewer.clear_overlay()
        self._visible_molecular_detection_count = 0
        self._visible_molecular_detection_colors = []

    def visible_molecular_detection_count(self) -> int:
        return int(self._visible_molecular_detection_count)

    def visible_molecular_detection_colors(self) -> list[tuple[int, int, int]]:
        return list(self._visible_molecular_detection_colors)

    def show_molecular_detections(
        self,
        *,
        source_view: str,
        scale_nm_per_px: tuple[float | None, float | None],
    ) -> None:
        self.clear_molecular_detection_overlays()
        if self._series is None:
            return
        detection_set = getattr(self._series, "molecular_detections", None)
        if detection_set is None:
            return
        detections = detection_set.get_detections(
            self._series.active_frame_index,
            source_view=source_view,
        )
        sx, sy = self._effective_scale_nm_per_px(scale_nm_per_px)
        count = 0
        colors: list[tuple[int, int, int]] = []
        for detection in detections:
            color = (255, 0, 255) if detection.selected else (255, 140, 0)
            polyline = self.viewer.add_polyline_nm(
                self._bbox_polyline_nm(detection.bbox_xyxy, scale_nm_per_px=(sx, sy)),
                color=color,
                width=1.8,
            )
            if polyline is None:
                continue
            colors.append(color)
            x0, y0, x1, y1 = detection.bbox_xyxy
            self.viewer.add_text_nm(
                f"{detection.confidence:.2f}",
                (((x0 + x1) / 2.0) * sx, ((y0 + y1) / 2.0) * sy),
                color=color,
            )
            count += 1
        self._visible_molecular_detection_count = count
        self._visible_molecular_detection_colors = colors

    def _effective_scale_nm_per_px(self, scale_nm_per_px: tuple[float | None, float | None]) -> tuple[float, float]:
        sx, sy = scale_nm_per_px
        try:
            sx = float(sx) if sx else 1.0
        except (TypeError, ValueError):
            sx = 1.0
        try:
            sy = float(sy) if sy else 1.0
        except (TypeError, ValueError):
            sy = 1.0
        return sx, sy

    def _bbox_polyline_nm(
        self,
        bbox_xyxy: tuple[float, float, float, float],
        *,
        scale_nm_per_px: tuple[float, float],
    ) -> np.ndarray:
        x0, y0, x1, y1 = (float(value) for value in bbox_xyxy)
        sx, sy = scale_nm_per_px
        return np.asarray(
            [
                [x0 * sx, y0 * sy],
                [x1 * sx, y0 * sy],
                [x1 * sx, y1 * sy],
                [x0 * sx, y1 * sy],
                [x0 * sx, y0 * sy],
            ],
            dtype=np.float64,
        )
