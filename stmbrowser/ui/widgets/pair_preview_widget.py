from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QHBoxLayout

from napara.core.data_models import STMImage

from .image_preview_widget import ImagePreviewWidget


class PairPreviewWidget(QWidget):
    """Side-by-side image preview with synchronized zoom/pan."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._syncing = False
        self._build()
        self._connect_sync()

    def _build(self) -> None:
        layout = QHBoxLayout(self)
        self.left = ImagePreviewWidget(panel_title="Image A (selected)", parent=self)
        self.right = ImagePreviewWidget(panel_title="Image B (next)", parent=self)
        layout.addWidget(self.left, 1)
        layout.addWidget(self.right, 1)

    def _connect_sync(self) -> None:
        self.left.view_box().sigRangeChanged.connect(self._on_left_range_changed)
        self.right.view_box().sigRangeChanged.connect(self._on_right_range_changed)

    def _sync_range(self, source_vb, target_vb) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            x_rng, y_rng = source_vb.viewRange()
            target_vb.setRange(xRange=x_rng, yRange=y_rng, padding=0.0)
        finally:
            self._syncing = False

    def _on_left_range_changed(self, *_args) -> None:
        self._sync_range(self.left.view_box(), self.right.view_box())

    def _on_right_range_changed(self, *_args) -> None:
        self._sync_range(self.right.view_box(), self.left.view_box())

    def clear(self) -> None:
        self.left.clear()
        self.right.clear()

    def set_pair(self, left_image: STMImage, right_image: STMImage) -> None:
        self.left.set_image(left_image)
        self.right.set_image(right_image)
        # Force identical initial range after auto-fit.
        self._sync_range(self.left.view_box(), self.right.view_box())
