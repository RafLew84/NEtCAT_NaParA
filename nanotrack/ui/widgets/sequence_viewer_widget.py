from __future__ import annotations

import os

import pyqtgraph as pg
from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

import numpy as np
from skimage import measure

from nanotrack.core import BBoxXYXY, EdgeTrack, FrameVisibility, ParticleTrack, PolygonROI, STMSequence, YoloDetection
from napara.gui.widgets.viewer_widget import ViewerWidget


class SequenceViewerWidget(QWidget):
    """Main frame viewer for NanoTrack sequences."""

    bbox_changed = pyqtSignal(object)
    polygon_changed = pyqtSignal(object)
    edge_polyline_changed = pyqtSignal(object)
    yolo_detection_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence: STMSequence | None = None
        self._bbox_roi: pg.RectROI | None = None
        self._bbox_draw_mode = False
        self._bbox_default_size_px = (48.0, 48.0)
        self._current_bbox: BBoxXYXY | None = None
        self._suppress_bbox_signal = False
        self._polygon_roi: pg.PolyLineROI | None = None
        self._polygon_draw_mode = False
        self._polygon_draft_vertices_px: list[tuple[float, float]] = []
        self._polygon_draft_curve: pg.PlotCurveItem | None = None
        self._polygon_draft_scatter: pg.ScatterPlotItem | None = None
        self._current_polygon: PolygonROI | None = None
        self._suppress_polygon_signal = False
        self._edge_polyline_roi: pg.PolyLineROI | None = None
        self._current_edge_polyline: np.ndarray | None = None
        self._suppress_edge_polyline_signal = False
        self._current_yolo_detections: list[YoloDetection] = []
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
        self.clear_polygon()
        self.clear_edge_polyline()
        self.clear_track_seed_overlays()
        self.set_bbox_draw_mode(False)
        self.set_polygon_draw_mode(False)
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

    def current_polygon_roi(self) -> PolygonROI | None:
        return self._current_polygon

    def current_edge_polyline(self) -> np.ndarray | None:
        return None if self._current_edge_polyline is None else np.asarray(self._current_edge_polyline, dtype=np.float64)

    def clear_track_seed_overlays(self) -> None:
        self._current_yolo_detections = []
        self.viewer.clear_overlay()

    def set_tracks_and_edges(
        self,
        tracks: list[ParticleTrack],
        *,
        selected_track_id: int | None = None,
        edge_tracks: list[EdgeTrack] | None = None,
        selected_edge_track_id: int | None = None,
        yolo_detections: list[YoloDetection] | None = None,
    ) -> None:
        self.clear_track_seed_overlays()
        if self._sequence is None:
            return
        self._current_yolo_detections = list(yolo_detections or [])

        current_frame = self._sequence.active_frame_index
        for track in tracks:
            annotation = track.get_annotation(current_frame)
            if (
                annotation is None
                or annotation.visibility != FrameVisibility.VISIBLE
                or not annotation.has_geometry
            ):
                continue

            overlay_items = []
            if annotation.mask is not None and np.any(annotation.mask):
                for contour_nm in self._mask_contours_nm(annotation.mask):
                    polyline = self.viewer.add_polyline_nm(contour_nm, color=(0, 255, 0), width=2.0)
                    if polyline is not None:
                        overlay_items.append(polyline)
            elif annotation.bbox is not None:
                polyline = self.viewer.add_polyline_nm(
                    self._bbox_polyline_nm(annotation.bbox),
                    color=(0, 255, 0),
                    width=2.0,
                )
                if polyline is not None:
                    overlay_items.append(polyline)

            label_txt = track.label or f"T{track.track_id}"
            text = self.viewer.add_text_nm(
                label_txt,
                self._annotation_label_position_nm(annotation),
                color=(0, 255, 0),
            )
            highlight = track.track_id == selected_track_id
            for item in overlay_items:
                self.viewer.set_item_highlight(item, highlight)
            self.viewer.set_item_highlight(text, highlight)

        for edge_track in edge_tracks or []:
            annotation = edge_track.get_annotation(current_frame)
            if (
                annotation is None
                or annotation.visibility != FrameVisibility.VISIBLE
                or annotation.polyline is None
            ):
                continue

            polyline_item = self.viewer.add_polyline_nm(
                self._polyline_nm(annotation.polyline),
                color=(0, 220, 255),
                width=2.4,
            )
            label_txt = edge_track.label or f"E{edge_track.edge_track_id}"
            text = self.viewer.add_text_nm(
                label_txt,
                self._polyline_label_position_nm(annotation.polyline),
                color=(0, 220, 255),
            )
            highlight = edge_track.edge_track_id == selected_edge_track_id
            self.viewer.set_item_highlight(polyline_item, highlight)
            self.viewer.set_item_highlight(text, highlight)

        for detection in self._current_yolo_detections:
            color = (255, 0, 255) if detection.selected else (255, 140, 0)
            polyline_item = self.viewer.add_polyline_nm(
                self._bbox_polyline_nm(detection.bbox),
                color=color,
                width=1.8,
            )
            confidence_text = self.viewer.add_text_nm(
                f"{detection.confidence:.2f}",
                self._bbox_center_nm(detection.bbox),
                color=color,
            )
            if polyline_item is None:
                self.viewer.remove_item(confidence_text)

    def set_bbox_draw_mode(self, enabled: bool) -> None:
        self._bbox_draw_mode = bool(enabled)

    def set_polygon_draw_mode(self, enabled: bool) -> None:
        self._polygon_draw_mode = bool(enabled)

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

    def clear_polygon(self) -> None:
        self._clear_polygon_internal()
        if self._suppress_polygon_signal:
            return
        self.polygon_changed.emit(None)

    def clear_edge_polyline(self) -> None:
        self._clear_edge_polyline_internal()
        if self._suppress_edge_polyline_signal:
            return
        self.edge_polyline_changed.emit(None)

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

    def set_polygon_roi(self, polygon: PolygonROI | None) -> None:
        self._suppress_polygon_signal = True
        try:
            self._set_polygon_roi_internal(polygon)
        finally:
            self._suppress_polygon_signal = False

    def set_edge_polyline(self, polyline: np.ndarray | None) -> None:
        self._suppress_edge_polyline_signal = True
        try:
            self._set_edge_polyline_internal(polyline)
        finally:
            self._suppress_edge_polyline_signal = False

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

    def place_polygon_vertex_at_pixel(self, x_px: float, y_px: float) -> tuple[float, float] | None:
        if self._sequence is None:
            return None

        frame_h, frame_w = self._sequence.frame_shape
        x_px = float(min(max(x_px, 0.0), float(frame_w)))
        y_px = float(min(max(y_px, 0.0), float(frame_h)))
        if not self._polygon_draft_vertices_px and self._current_polygon is not None:
            self._commit_polygon(None)

        self._polygon_draft_vertices_px.append((x_px, y_px))
        self._update_polygon_draft_items()
        return x_px, y_px

    def finish_polygon_drawing(self) -> PolygonROI | None:
        if len(self._polygon_draft_vertices_px) < 3:
            return None
        polygon = PolygonROI(np.asarray(self._polygon_draft_vertices_px, dtype=np.float64))
        self._commit_polygon(polygon)
        return polygon

    def _on_scene_mouse_clicked(self, event) -> None:
        if self._sequence is None:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if not self.viewer.plot_item.sceneBoundingRect().contains(event.scenePos()):
            return

        view_pos = self.viewer.plot_item.getViewBox().mapSceneToView(event.scenePos())
        center_x_px, center_y_px = self._view_to_pixel_coords(view_pos.x(), view_pos.y())
        if self._polygon_draw_mode:
            if self.place_polygon_vertex_at_pixel(center_x_px, center_y_px) is not None:
                event.accept()
            return
        if self._bbox_draw_mode and self.place_bbox_at_pixel(center_x_px, center_y_px) is not None:
            event.accept()
            return
        clicked_detection_index = self._find_yolo_detection_at_pixel(center_x_px, center_y_px)
        if clicked_detection_index is not None:
            self.yolo_detection_clicked.emit(clicked_detection_index)
            event.accept()

    def _commit_bbox(self, bbox: BBoxXYXY | None) -> None:
        self.set_bbox(bbox)
        self.bbox_changed.emit(bbox)

    def _commit_polygon(self, polygon: PolygonROI | None) -> None:
        self.set_polygon_roi(polygon)
        self.polygon_changed.emit(polygon)

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

    def _set_polygon_roi_internal(self, polygon: PolygonROI | None) -> None:
        self._clear_polygon_internal()
        self._current_polygon = polygon
        if polygon is None:
            return
        self._ensure_polygon_roi(polygon)

    def _clear_polygon_internal(self) -> None:
        self._current_polygon = None
        self._polygon_draft_vertices_px = []
        self._clear_polygon_draft_items()
        if self._polygon_roi is not None:
            try:
                self.viewer.plot_item.removeItem(self._polygon_roi)
            except Exception:
                pass
            self._polygon_roi = None

    def _clear_edge_polyline_internal(self) -> None:
        self._current_edge_polyline = None
        if self._edge_polyline_roi is not None:
            try:
                self.viewer.plot_item.removeItem(self._edge_polyline_roi)
            except Exception:
                pass
            self._edge_polyline_roi = None

    def _clear_polygon_draft_items(self) -> None:
        for item_name in ("_polygon_draft_curve", "_polygon_draft_scatter"):
            item = getattr(self, item_name)
            if item is None:
                continue
            try:
                self.viewer.plot_item.removeItem(item)
            except Exception:
                pass
            setattr(self, item_name, None)

    def _update_polygon_draft_items(self) -> None:
        self._clear_polygon_draft_items()
        if not self._polygon_draft_vertices_px:
            return
        vertices_nm = self._polygon_vertices_px_to_nm(self._polygon_draft_vertices_px)
        self._polygon_draft_curve = pg.PlotCurveItem(
            vertices_nm[:, 0],
            vertices_nm[:, 1],
            pen=pg.mkPen(255, 120, 0, width=2),
        )
        self._polygon_draft_scatter = pg.ScatterPlotItem(
            vertices_nm[:, 0],
            vertices_nm[:, 1],
            pen=pg.mkPen(255, 160, 0, width=1),
            brush=pg.mkBrush(255, 200, 0, 180),
            size=8,
        )
        self.viewer.plot_item.addItem(self._polygon_draft_curve)
        self.viewer.plot_item.addItem(self._polygon_draft_scatter)

    def _ensure_polygon_roi(self, polygon: PolygonROI) -> None:
        points_nm = [tuple(point) for point in self._polygon_vertices_px_to_nm(polygon.vertices_xy)]
        self._polygon_roi = pg.PolyLineROI(
            points_nm,
            closed=True,
            movable=False,
            rotatable=False,
            resizable=False,
            pen=pg.mkPen(255, 120, 0, width=2),
            maxBounds=self._frame_rect_nm(),
        )
        self._polygon_roi.sigRegionChanged.connect(self._on_polygon_roi_changed)
        self.viewer.plot_item.addItem(self._polygon_roi)

    def _on_polygon_roi_changed(self) -> None:
        if self._polygon_roi is None or self._sequence is None or self._suppress_polygon_signal:
            return
        polygon = self._polygon_from_roi()
        self._current_polygon = polygon
        self.polygon_changed.emit(polygon)

    def _set_edge_polyline_internal(self, polyline: np.ndarray | None) -> None:
        self._clear_edge_polyline_internal()
        if polyline is None:
            return
        polyline_arr = np.asarray(polyline, dtype=np.float64)
        if polyline_arr.ndim != 2 or polyline_arr.shape[1] != 2 or len(polyline_arr) < 2:
            raise ValueError("edge polyline must have shape [N, 2] with at least two points.")
        self._current_edge_polyline = polyline_arr
        self._ensure_edge_polyline_roi(polyline_arr)

    def _ensure_edge_polyline_roi(self, polyline: np.ndarray) -> None:
        points_nm = [tuple(point) for point in self._polygon_vertices_px_to_nm(polyline)]
        self._edge_polyline_roi = pg.PolyLineROI(
            points_nm,
            closed=False,
            movable=False,
            rotatable=False,
            resizable=False,
            pen=pg.mkPen(255, 230, 0, width=2),
            maxBounds=self._frame_rect_nm(),
        )
        self._edge_polyline_roi.sigRegionChanged.connect(self._on_edge_polyline_roi_changed)
        self.viewer.plot_item.addItem(self._edge_polyline_roi)

    def _on_edge_polyline_roi_changed(self) -> None:
        if self._edge_polyline_roi is None or self._sequence is None or self._suppress_edge_polyline_signal:
            return
        polyline = self._edge_polyline_from_roi()
        self._current_edge_polyline = polyline
        self.edge_polyline_changed.emit(polyline)

    def _edge_polyline_from_roi(self) -> np.ndarray:
        if self._edge_polyline_roi is None or self._sequence is None:
            raise RuntimeError("Edge polyline ROI is not available.")
        state = self._edge_polyline_roi.saveState()
        points_nm = np.asarray(
            [
                (
                    float(point[0] if isinstance(point, (tuple, list)) else point.x()),
                    float(point[1] if isinstance(point, (tuple, list)) else point.y()),
                )
                for point in state["points"]
            ],
            dtype=np.float64,
        )
        return self._polygon_vertices_nm_to_px(points_nm)

    def _polygon_from_roi(self) -> PolygonROI:
        if self._polygon_roi is None or self._sequence is None:
            raise RuntimeError("Polygon ROI is not available.")
        state = self._polygon_roi.saveState()
        points_nm = np.asarray(
            [
                (
                    float(point[0] if isinstance(point, (tuple, list)) else point.x()),
                    float(point[1] if isinstance(point, (tuple, list)) else point.y()),
                )
                for point in state["points"]
            ],
            dtype=np.float64,
        )
        return PolygonROI(self._polygon_vertices_nm_to_px(points_nm))

    def _polygon_vertices_px_to_nm(self, vertices_px) -> np.ndarray:
        sx, sy = self._pixel_scale()
        vertices_px = np.asarray(vertices_px, dtype=np.float64)
        return np.column_stack((vertices_px[:, 0] * sx, vertices_px[:, 1] * sy)).astype(np.float64, copy=False)

    def _polygon_vertices_nm_to_px(self, vertices_nm) -> np.ndarray:
        sx, sy = self._pixel_scale()
        vertices_nm = np.asarray(vertices_nm, dtype=np.float64)
        return np.column_stack((vertices_nm[:, 0] / sx, vertices_nm[:, 1] / sy)).astype(np.float64, copy=False)

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

    def _polyline_nm(self, polyline_px: np.ndarray) -> np.ndarray:
        sx, sy = self._pixel_scale()
        polyline_px = np.asarray(polyline_px, dtype=np.float64)
        return np.column_stack((polyline_px[:, 0] * sx, polyline_px[:, 1] * sy)).astype(np.float64, copy=False)

    def _bbox_center_nm(self, bbox: BBoxXYXY) -> tuple[float, float]:
        sx, sy = self._pixel_scale()
        cx, cy = bbox.center_xy
        return cx * sx, cy * sy

    def _find_yolo_detection_at_pixel(self, x_px: float, y_px: float) -> int | None:
        best_index: int | None = None
        best_area: float | None = None
        for index, detection in enumerate(self._current_yolo_detections):
            bbox = detection.bbox
            if not (bbox.x0 <= x_px <= bbox.x1 and bbox.y0 <= y_px <= bbox.y1):
                continue
            area = float(bbox.width * bbox.height)
            if best_area is None or area < best_area:
                best_index = index
                best_area = area
        return best_index

    def _annotation_label_position_nm(self, annotation) -> tuple[float, float]:
        if annotation.bbox is not None:
            return self._bbox_center_nm(annotation.bbox)
        assert annotation.mask is not None
        ys, xs = np.nonzero(annotation.mask)
        sx, sy = self._pixel_scale()
        return float(xs.mean()) * sx, float(ys.mean()) * sy

    def _polyline_label_position_nm(self, polyline_px: np.ndarray) -> tuple[float, float]:
        polyline_px = np.asarray(polyline_px, dtype=np.float64)
        sx, sy = self._pixel_scale()
        center = np.mean(polyline_px, axis=0)
        return float(center[0]) * sx, float(center[1]) * sy

    def _mask_contours_nm(self, mask: np.ndarray) -> list[np.ndarray]:
        sx, sy = self._pixel_scale()
        contours_nm: list[np.ndarray] = []
        for contour in measure.find_contours(mask.astype(np.uint8), level=0.5):
            if contour.shape[0] < 2:
                continue
            contour_xy = np.column_stack((contour[:, 1] * sx, contour[:, 0] * sy)).astype(np.float64, copy=False)
            contours_nm.append(contour_xy)
        return contours_nm

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
