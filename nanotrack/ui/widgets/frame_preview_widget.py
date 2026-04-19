from __future__ import annotations

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

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
        self.viewer.clear()

    def set_frame(
        self,
        frame,
        *,
        title: str,
        meta: str,
        scale_nm_per_px: tuple[float | None, float | None] = (None, None),
        preserve_zoom: bool = True,
    ) -> None:
        self.viewer.set_image(
            frame,
            scale_nm_per_px=scale_nm_per_px,
            preserve_zoom=preserve_zoom,
            auto_levels=True,
        )
        self.lbl_title.setText(title)
        self.lbl_meta.setText(meta)
