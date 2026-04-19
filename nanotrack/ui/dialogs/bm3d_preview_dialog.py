from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QHBoxLayout

from nanotrack.ui.widgets import FramePreviewWidget


class Bm3dPreviewDialog(QDialog):
    """Side-by-side comparison window for single-frame BM3D previews."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._preview_frame_index: int | None = None
        self._build()

    def _build(self) -> None:
        self.setWindowTitle("BM3D Preview")
        self.resize(1220, 680)

        layout = QHBoxLayout(self)
        self.raw_view = FramePreviewWidget("Original", self)
        self.denoised_view = FramePreviewWidget("BM3D", self)
        layout.addWidget(self.raw_view, 1)
        layout.addWidget(self.denoised_view, 1)

    def set_preview(
        self,
        raw_frame,
        denoised_frame,
        *,
        frame_index: int,
        frame_count: int,
        sigma_factor: float,
        scale_nm_per_px: tuple[float | None, float | None] = (None, None),
    ) -> None:
        preserve_zoom = self._preview_frame_index == frame_index
        frame_label = f"Frame {frame_index + 1}/{frame_count}"

        self.raw_view.set_frame(
            raw_frame,
            title=f"Original | {frame_label}",
            meta="Raw frame",
            scale_nm_per_px=scale_nm_per_px,
            preserve_zoom=preserve_zoom,
        )
        self.denoised_view.set_frame(
            denoised_frame,
            title=f"BM3D | {frame_label}",
            meta=f"Sigma factor: {sigma_factor:.2f}",
            scale_nm_per_px=scale_nm_per_px,
            preserve_zoom=preserve_zoom,
        )
        self._preview_frame_index = frame_index

    def clear_preview(self) -> None:
        self._preview_frame_index = None
        self.raw_view.clear()
        self.denoised_view.clear()
