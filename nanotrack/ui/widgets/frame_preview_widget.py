from __future__ import annotations

import numpy as np
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget
from skimage import measure

from napara.gui.widgets.viewer_widget import ViewerWidget


class FramePreviewWidget(QWidget):
    """Generic image viewer for single-frame previews."""

    def __init__(self, panel_title: str = "Preview", parent=None):
        super().__init__(parent)
        self._panel_title = panel_title
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        self.lbl_title = QLabel(self._panel_title, self)
        self.lbl_meta = QLabel("-", self)
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_meta)

        self.viewer = ViewerWidget(self)
        layout.addWidget(self.viewer, 1)

    def clear(self) -> None:
        self.lbl_title.setText(self._panel_title)
        self.lbl_meta.setText("-")
        self.viewer.clear_overlay()
        self.viewer.clear()

    def _add_mask_overlay(
        self,
        overlay_mask,
        *,
        scale_nm_per_px: tuple[float | None, float | None],
        color=(255, 80, 80),
        width: float = 2.0,
    ) -> None:
        mask = np.asarray(overlay_mask, dtype=bool)
        if mask.ndim != 2 or not np.any(mask):
            return

        sx, sy = scale_nm_per_px
        for contour in measure.find_contours(mask.astype(np.uint8), 0.5):
            if contour.shape[0] < 2:
                continue
            pts = np.column_stack([contour[:, 1], contour[:, 0]]).astype(np.float64, copy=False)
            if sx is not None and sy is not None:
                pts[:, 0] *= float(sx)
                pts[:, 1] *= float(sy)
            self.viewer.add_polyline_nm(pts, color=color, width=width)

    def set_frame(
        self,
        frame,
        *,
        title: str,
        meta: str,
        scale_nm_per_px: tuple[float | None, float | None] = (None, None),
        preserve_zoom: bool = True,
        overlay_mask=None,
    ) -> None:
        self.viewer.clear_overlay()
        self.viewer.set_image(
            frame,
            scale_nm_per_px=scale_nm_per_px,
            preserve_zoom=preserve_zoom,
            auto_levels=True,
        )
        if overlay_mask is not None:
            self._add_mask_overlay(overlay_mask, scale_nm_per_px=scale_nm_per_px)
        self.lbl_title.setText(title)
        self.lbl_meta.setText(meta)
