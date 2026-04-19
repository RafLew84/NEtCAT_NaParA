from __future__ import annotations

import os

import pyqtgraph as pg
from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

import numpy as np

from nanotrack.core import BBoxXYXY, ParticleTrack, STMSequence
from napara.gui.widgets.viewer_widget import ViewerWidget


class SequenceViewerWidget(QWidget):
    """Main frame viewer for NanoTrack sequences."""

    bbox_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence: STMSequence | None = None
        self._bbox_roi: pg.RectROI | None = None
        self._bbox_draw_mode = False
        self._bbox_default_size_px = (48.0, 48.0)
        self._current_bbox: BBoxXYXY | None = None
        self._suppress_bbox_signal = False
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        self.lbl_title = QLabel("No sequence loaded", self)
        self.lbl_meta = QLabel("-", self)
        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_meta)

        self.viewer = ViewerWidget(self)
        layout.addWidget(self.viewer, 1)
        self.viewer.glw.scene().sigMouseClicked.connect(self._on_scene_mouse_clicked)

    def clear(self) -> None:
        self._sequence = None
        self.clear_bbox()
        self.clear_track_seed_overlays()
        self.set_bbox_draw_mode(False)
        self.lbl_title.setText("No sequence loaded")
        self.lbl_meta.setText("-")
        self.viewer.clear()

    def set_sequence(self, sequence: STMSequence) -> None:
        self._sequence = sequence
        self.clear_bbox()
        self.show_frame(sequence.active_frame_index, preserve_zoom=False)

    def show_frame(
        self,
        frame_index: int,
        preserve_zoom: bool = True,
        *,
        frame_override=None,
        view_label: str = "Raw",
    ) -> None:
        if self._sequence is None:
            self.clear()
            return

        self._sequence.set_active_frame(frame_index)
        frame = self._sequence.active_frame if frame_override is None else frame_override
        px_x, px_y = self._sequence.metadata.get_pixel_size_nm()
        self.viewer.set_image(
            frame,
            scale_nm_per_px=(px_x, px_y),
            preserve_zoom=preserve_zoom,
            auto_levels=True,
        )

        file_name = os.path.basename(self._sequence.source_path)
        current = self._sequence.active_frame_index + 1
        total = self._sequence.frame_count
        self.lbl_title.setText(f"{file_name} | Frame {current}/{total}")

        time_s = self._sequence.active_frame_time_s
        if time_s is None:
            time_txt = "n/a"
        else:
            time_txt = f"{time_s:.4g} s"

        self.lbl_meta.setText(
            f"Shape: {frame.shape[1]}x{frame.shape[0]} px | "
            f"Channel: {self._sequence.metadata.image_type} | "
            f"Time: {time_txt} | "
            f"View: {view_label}"
        )

    def current_bbox(self) -> BBoxXYXY | None:
        return self._current_bbox

    def clear_track_seed_overlays(self) -> None:
        self.viewer.clear_overlay()

    def set_seed_tracks(self, tracks: list[ParticleTrack], *, selected_track_id: int | None = None) -> None:
        self.clear_track_seed_overlays()
        if self._sequence is None:
            return

        current_frame = self._sequence.active_frame_index
        for track in tracks:
            annotation = track.get_annotation(current_frame)
            if annotation is None or annotation.bbox is None:
                continue

            points_nm = self._bbox_polyline_nm(annotation.bbox)
            polyline = self.viewer.add_polyline_nm(points_nm, color=(0, 255, 0), width=2.0)
            label_txt = track.label or f"T{track.track_id}"
            text = self.viewer.add_text_nm(label_txt, self._bbox_center_nm(annotation.bbox), color=(0, 255, 0))
            highlight = track.track_id == selected_track_id
            self.viewer.set_item_highlight(polyline, highlight)
            self.viewer.set_item_highlight(text, highlight)

    def set_bbox_draw_mode(self, enabled: bool) -> None:
        self._bbox_draw_mode = bool(enabled)

    def set_default_bbox_size_px(self, width_px: float, height_px: float) -> None:
        self._bbox_default_size_px = (max(1.0, float(width_px)), max(1.0, float(height_px)))

    def clear_bbox(self) -> None:
        self._current_bbox = None
        if self._bbox_roi is None:
            return
        try:
            self.viewer.plot_item.removeItem(self._bbox_roi)
        except Exception:
            pass
        self._bbox_roi = None

    def set_bbox(self, bbox: BBoxXYXY | None) -> None:
        self._suppress_bbox_signal = True
        try:
            self._current_bbox = bbox
            if bbox is None:
                self.clear_bbox()
                return
            self._ensure_bbox_roi(bbox)
            self._update_bbox_roi(bbox)
        finally:
            self._suppress_bbox_signal = False

    def place_bbox_at_pixel(self, center_x_px: float, center_y_px: float) -> BBoxXYXY | None:
        if self._sequence is None:
            return None

        frame_h, frame_w = self._sequence.frame_shape
        width_px = min(self._bbox_default_size_px[0], float(frame_w))
        height_px = min(self._bbox_default_size_px[1], float(frame_h))
        center_x_px = float(min(max(center_x_px, 0.0), frame_w))
        center_y_px = float(min(max(center_y_px, 0.0), frame_h))

        x0 = max(0.0, center_x_px - width_px / 2.0)
        y0 = max(0.0, center_y_px - height_px / 2.0)
        x1 = min(float(frame_w), x0 + width_px)
        y1 = min(float(frame_h), y0 + height_px)
        x0 = max(0.0, x1 - width_px)
        y0 = max(0.0, y1 - height_px)

        bbox = BBoxXYXY(x0, y0, x1, y1)
        self._commit_bbox(bbox)
        return bbox

    def _on_scene_mouse_clicked(self, event) -> None:
        if not self._bbox_draw_mode or self._sequence is None:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if not self.viewer.plot_item.sceneBoundingRect().contains(event.scenePos()):
            return

        view_pos = self.viewer.plot_item.getViewBox().mapSceneToView(event.scenePos())
        center_x_px, center_y_px = self._view_to_pixel_coords(view_pos.x(), view_pos.y())
        if self.place_bbox_at_pixel(center_x_px, center_y_px) is not None:
            event.accept()

    def _commit_bbox(self, bbox: BBoxXYXY | None) -> None:
        self.set_bbox(bbox)
        self.bbox_changed.emit(bbox)

    def _ensure_bbox_roi(self, bbox: BBoxXYXY) -> None:
        if self._bbox_roi is not None:
            self._bbox_roi.maxBounds = self._frame_rect_nm()
            return

        pos_nm, size_nm = self._bbox_to_nm(bbox)
        self._bbox_roi = pg.RectROI(
            pos_nm,
            size_nm,
            pen=pg.mkPen(255, 200, 0, width=2),
            movable=True,
            resizable=True,
            rotatable=False,
            maxBounds=self._frame_rect_nm(),
        )
        self._bbox_roi.addScaleHandle((0, 0), (1, 1))
        self._bbox_roi.addScaleHandle((1, 1), (0, 0))
        self._bbox_roi.addScaleHandle((1, 0), (0, 1))
        self._bbox_roi.addScaleHandle((0, 1), (1, 0))
        self._bbox_roi.sigRegionChanged.connect(self._on_bbox_roi_changed)
        self.viewer.plot_item.addItem(self._bbox_roi)

    def _update_bbox_roi(self, bbox: BBoxXYXY) -> None:
        if self._bbox_roi is None:
            return
        pos_nm, size_nm = self._bbox_to_nm(bbox)
        self._bbox_roi.maxBounds = self._frame_rect_nm()
        self._bbox_roi.setPos(pos_nm)
        self._bbox_roi.setSize(size_nm)

    def _on_bbox_roi_changed(self) -> None:
        if self._bbox_roi is None or self._sequence is None or self._suppress_bbox_signal:
            return
        bbox = self._bbox_from_roi()
        self._current_bbox = bbox
        self.bbox_changed.emit(bbox)

    def _bbox_from_roi(self) -> BBoxXYXY:
        if self._bbox_roi is None or self._sequence is None:
            raise RuntimeError("BBox ROI is not available.")

        pos = self._bbox_roi.pos()
        size = self._bbox_roi.size()
        x0_px, y0_px = self._view_to_pixel_coords(pos.x(), pos.y())
        x1_px, y1_px = self._view_to_pixel_coords(pos.x() + size.x(), pos.y() + size.y())

        frame_h, frame_w = self._sequence.frame_shape
        x0_px = min(max(x0_px, 0.0), float(frame_w))
        x1_px = min(max(x1_px, 0.0), float(frame_w))
        y0_px = min(max(y0_px, 0.0), float(frame_h))
        y1_px = min(max(y1_px, 0.0), float(frame_h))

        return BBoxXYXY(min(x0_px, x1_px), min(y0_px, y1_px), max(x0_px, x1_px), max(y0_px, y1_px))

    def _bbox_to_nm(self, bbox: BBoxXYXY) -> tuple[tuple[float, float], tuple[float, float]]:
        sx, sy = self._pixel_scale()
        return (bbox.x0 * sx, bbox.y0 * sy), (bbox.width * sx, bbox.height * sy)

    def _bbox_polyline_nm(self, bbox: BBoxXYXY) -> np.ndarray:
        sx, sy = self._pixel_scale()
        return np.asarray(
            [
                [bbox.x0 * sx, bbox.y0 * sy],
                [bbox.x1 * sx, bbox.y0 * sy],
                [bbox.x1 * sx, bbox.y1 * sy],
                [bbox.x0 * sx, bbox.y1 * sy],
                [bbox.x0 * sx, bbox.y0 * sy],
            ],
            dtype=np.float64,
        )

    def _bbox_center_nm(self, bbox: BBoxXYXY) -> tuple[float, float]:
        sx, sy = self._pixel_scale()
        cx, cy = bbox.center_xy
        return cx * sx, cy * sy

    def _frame_rect_nm(self) -> QRectF:
        if self._sequence is None:
            return QRectF()
        frame_h, frame_w = self._sequence.frame_shape
        sx, sy = self._pixel_scale()
        return QRectF(0.0, 0.0, frame_w * sx, frame_h * sy)

    def _pixel_scale(self) -> tuple[float, float]:
        if self._sequence is None:
            return 1.0, 1.0
        px_x, px_y = self._sequence.metadata.get_pixel_size_nm()
        return float(px_x or 1.0), float(px_y or 1.0)

    def _view_to_pixel_coords(self, x_view: float, y_view: float) -> tuple[float, float]:
        sx, sy = self._pixel_scale()
        return float(x_view) / sx, float(y_view) / sy
