from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QHBoxLayout

from nanotrack.registration import RegistrationPairPreview
from nanotrack.ui.widgets import FramePreviewWidget


class RegistrationPreviewDialog(QDialog):
    """Three-panel preview for one translation-only registration estimate."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._preview_pair: tuple[int, int] | None = None
        self._build()

    def _build(self) -> None:
        self.setWindowTitle("Registration Preview")
        self.resize(1440, 680)

        layout = QHBoxLayout(self)
        self.reference_view = FramePreviewWidget("Reference", self)
        self.moving_view = FramePreviewWidget("Moving", self)
        self.aligned_view = FramePreviewWidget("Aligned Moving", self)
        layout.addWidget(self.reference_view, 1)
        layout.addWidget(self.moving_view, 1)
        layout.addWidget(self.aligned_view, 1)

    def set_preview(
        self,
        preview: RegistrationPairPreview,
        *,
        frame_count: int,
        scale_nm_per_px: tuple[float | None, float | None] = (None, None),
    ) -> None:
        pair = (preview.reference_index, preview.moving_index)
        preserve_zoom = self._preview_pair == pair
        self.setWindowTitle("Registration Preview")

        reference_label = f"Frame {preview.reference_index + 1}/{frame_count}"
        moving_label = f"Frame {preview.moving_index + 1}/{frame_count}"
        result = preview.result
        peak = result.phase_peak_ratio
        peak_text = "n/a" if peak is None else f"{peak:.2f}"

        self.reference_view.set_frame(
            preview.reference_frame,
            title=f"Reference | {reference_label}",
            meta=f"Registration view: {preview.registration_view.view_name}",
            scale_nm_per_px=scale_nm_per_px,
            preserve_zoom=preserve_zoom,
        )
        self.moving_view.set_frame(
            preview.moving_frame,
            title=f"Moving | {moving_label}",
            meta="Before alignment",
            scale_nm_per_px=scale_nm_per_px,
            preserve_zoom=preserve_zoom,
        )
        self.aligned_view.set_frame(
            preview.aligned_moving_frame,
            title=f"Aligned Moving | {moving_label}",
            meta=(
                f"dx {result.dx:.3f}px | dy {result.dy:.3f}px | "
                f"status {result.status} | quality {result.quality_score:.3f} | peak {peak_text}"
            ),
            scale_nm_per_px=scale_nm_per_px,
            preserve_zoom=preserve_zoom,
        )
        self._preview_pair = pair

    def clear_preview(self) -> None:
        self._preview_pair = None
        self.reference_view.clear()
        self.moving_view.clear()
        self.aligned_view.clear()
