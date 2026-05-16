from __future__ import annotations

from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QCheckBox

from napara.core.data_models import STMImage

from .image_preview_widget import ImagePreviewWidget


class PairPreviewWidget(QWidget):
    """Side-by-side image preview with synchronized zoom/pan."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._syncing = False
        self._img_a: STMImage | None = None
        self._img_b: STMImage | None = None
        self._build()
        self._connect_sync()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        self.chk_show_b_in_a = QCheckBox("Alignment check: show image B in panel A", self)
        self.chk_show_b_in_a.setChecked(False)
        self.chk_show_b_in_a.setEnabled(False)
        root.addWidget(self.chk_show_b_in_a)

        layout = QHBoxLayout()
        self.left = ImagePreviewWidget(panel_title="Image A (selected)", parent=self)
        self.right = ImagePreviewWidget(panel_title="Image B (next)", parent=self)
        layout.addWidget(self.left, 1)
        layout.addWidget(self.right, 1)
        root.addLayout(layout, 1)

    def _connect_sync(self) -> None:
        self.left.view_box().sigRangeChanged.connect(self._on_left_range_changed)
        self.right.view_box().sigRangeChanged.connect(self._on_right_range_changed)
        self.chk_show_b_in_a.toggled.connect(self._on_alignment_toggle)

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
        self._img_a = None
        self._img_b = None
        self.chk_show_b_in_a.blockSignals(True)
        self.chk_show_b_in_a.setChecked(False)
        self.chk_show_b_in_a.setEnabled(False)
        self.chk_show_b_in_a.blockSignals(False)
        self.left.set_panel_title("Image A (selected)")
        self.right.set_panel_title("Image B (next)")
        self.left.clear()
        self.right.clear()

    def _render_pair(self, *, keep_view: bool) -> None:
        if self._img_a is None or self._img_b is None:
            self.clear()
            return

        left_vb = self.left.view_box()
        right_vb = self.right.view_box()
        left_rng = left_vb.viewRange()
        right_rng = right_vb.viewRange()

        show_b_on_left = self.chk_show_b_in_a.isChecked()
        if show_b_on_left:
            self.left.set_panel_title("Image A panel (showing B)")
            left_image = self._img_b
        else:
            self.left.set_panel_title("Image A (selected)")
            left_image = self._img_a

        self.right.set_panel_title("Image B (next)")
        self.left.set_image(left_image)
        self.right.set_image(self._img_b)

        if keep_view:
            self._syncing = True
            try:
                left_vb.setRange(xRange=left_rng[0], yRange=left_rng[1], padding=0.0)
                right_vb.setRange(xRange=right_rng[0], yRange=right_rng[1], padding=0.0)
            finally:
                self._syncing = False
        else:
            # Force identical initial range after auto-fit.
            self._sync_range(left_vb, right_vb)

    def _on_alignment_toggle(self, _checked: bool) -> None:
        if self._img_a is None or self._img_b is None:
            return
        self._render_pair(keep_view=True)

    def set_pair(self, left_image: STMImage, right_image: STMImage) -> None:
        self._img_a = left_image
        self._img_b = right_image
        self.chk_show_b_in_a.setEnabled(True)
        self._render_pair(keep_view=False)

    def current_pair(self) -> tuple[STMImage, STMImage] | None:
        if self._img_a is None or self._img_b is None:
            return None
        return (self._img_a, self._img_b)

    def is_alignment_check_active(self) -> bool:
        return bool(self.chk_show_b_in_a.isChecked())
