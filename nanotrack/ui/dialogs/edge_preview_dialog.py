from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QHBoxLayout

from nanotrack.ui.widgets import FramePreviewWidget


class EdgePreviewDialog(QDialog):
    """Side-by-side comparison window for single-frame DexiNed previews."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._preview_frame_index: int | None = None
        self._build()

    def _build(self) -> None:
        self.setWindowTitle("DexiNed Preview")
        self.resize(1220, 680)

        layout = QHBoxLayout(self)
        self.input_view = FramePreviewWidget("Input", self)
        self.edge_view = FramePreviewWidget("DexiNed", self)
        layout.addWidget(self.input_view, 1)
        layout.addWidget(self.edge_view, 1)

    def set_preview(
        self,
        input_frame,
        edge_frame,
        *,
        frame_index: int,
        frame_count: int,
        scale_nm_per_px: tuple[float | None, float | None] = (None, None),
        window_title: str = "DexiNed Preview",
        input_title: str = "Input",
        input_meta: str = "-",
        input_overlay_mask=None,
        edge_title: str = "DexiNed",
        edge_meta: str = "-",
    ) -> None:
        preserve_zoom = self._preview_frame_index == frame_index
        frame_label = f"Frame {frame_index + 1}/{frame_count}"
        self.setWindowTitle(window_title)

        self.input_view.set_frame(
            input_frame,
            title=f"{input_title} | {frame_label}",
            meta=input_meta,
            scale_nm_per_px=scale_nm_per_px,
            preserve_zoom=preserve_zoom,
            overlay_mask=input_overlay_mask,
        )
        self.edge_view.set_frame(
            edge_frame,
            title=f"{edge_title} | {frame_label}",
            meta=edge_meta,
            scale_nm_per_px=scale_nm_per_px,
            preserve_zoom=preserve_zoom,
        )
        self._preview_frame_index = frame_index

    def clear_preview(self) -> None:
        self._preview_frame_index = None
        self.input_view.clear()
        self.edge_view.clear()
