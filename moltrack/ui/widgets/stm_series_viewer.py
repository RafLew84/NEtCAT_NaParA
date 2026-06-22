from __future__ import annotations

import os

import numpy as np

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from napara.gui.widgets.viewer_widget import ViewerWidget


class STMSeriesViewer(QWidget):
    """Minimal STM image-series viewer for MolTrack."""

    molecular_detection_selection_changed = pyqtSignal(object)
    manual_molecular_bbox_drawn = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._series = None
        self._visible_molecular_detection_count = 0
        self._visible_molecular_detection_colors: list[tuple[int, int, int]] = []
        self._visible_molecular_segmentation_count = 0
        self._visible_molecular_segmentation_ids: list[str] = []
        self._highlighted_molecular_segmentation_ids: list[str] = []
        self._visible_sam3_preview_count = 0
        self._visible_sam3_preview_ids: list[str] = []
        self._selected_molecular_detection_id: str | None = None
        self._molecular_detection_overlay_items_by_id: dict[str, list[object]] = {}
        self._molecular_segmentation_overlay_items_by_id: dict[str, list[object]] = {}
        self._molecular_segmentation_prompt_ids_by_id: dict[str, tuple[str, ...]] = {}
        self._sam3_preview_overlay_items_by_id: dict[str, list[object]] = {}
        self._current_molecular_detection_source_view = "raw"
        self._current_scale_nm_per_px = (1.0, 1.0)
        self._current_image_shape_px: tuple[int, int] | None = None
        self._molecular_bbox_add_mode_enabled = False
        self._manual_bbox_drag_start_px: tuple[float, float] | None = None
        self._manual_bbox_drag_current_px: tuple[float, float] | None = None
        self._manual_bbox_preview_item = None
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
        self.viewer.glw.scene().sigMouseClicked.connect(self._on_scene_mouse_clicked)
        self.viewer.glw.viewport().installEventFilter(self)
        self.viewer.glw.viewport().setMouseTracking(True)

    def clear(self) -> None:
        self._series = None
        self.set_molecular_bbox_add_mode_enabled(False)
        self.clear_molecular_detection_overlays()
        self._set_selected_molecular_detection_id(None)
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
        frame_array = np.asarray(frame)
        self._current_image_shape_px = tuple(int(value) for value in frame_array.shape[:2])
        self.lbl_title.setText(str(title))
        self.lbl_meta.setText(str(meta))

    def clear_molecular_detection_overlays(self) -> None:
        self.viewer.clear_overlay()
        self._visible_molecular_detection_count = 0
        self._visible_molecular_detection_colors = []
        self._visible_molecular_segmentation_count = 0
        self._visible_molecular_segmentation_ids = []
        self._highlighted_molecular_segmentation_ids = []
        self._visible_sam3_preview_count = 0
        self._visible_sam3_preview_ids = []
        self._molecular_detection_overlay_items_by_id = {}
        self._molecular_segmentation_overlay_items_by_id = {}
        self._molecular_segmentation_prompt_ids_by_id = {}
        self._sam3_preview_overlay_items_by_id = {}
        self._manual_bbox_preview_item = None

    def visible_molecular_detection_count(self) -> int:
        return int(self._visible_molecular_detection_count)

    def visible_molecular_detection_colors(self) -> list[tuple[int, int, int]]:
        return list(self._visible_molecular_detection_colors)

    def selected_molecular_detection_id(self) -> str | None:
        return self._selected_molecular_detection_id

    def visible_molecular_segmentation_count(self) -> int:
        return int(self._visible_molecular_segmentation_count)

    def visible_molecular_segmentation_ids(self) -> list[str]:
        return list(self._visible_molecular_segmentation_ids)

    def highlighted_molecular_detection_ids(self) -> list[str]:
        selected_id = self._selected_molecular_detection_id
        if selected_id is None or selected_id not in self._molecular_detection_overlay_items_by_id:
            return []
        return [selected_id]

    def highlighted_molecular_segmentation_ids(self) -> list[str]:
        return list(self._highlighted_molecular_segmentation_ids)

    def visible_sam3_preview_count(self) -> int:
        return int(self._visible_sam3_preview_count)

    def visible_sam3_preview_ids(self) -> list[str]:
        return list(self._visible_sam3_preview_ids)

    def molecular_bbox_add_mode_enabled(self) -> bool:
        return bool(self._molecular_bbox_add_mode_enabled)

    def set_molecular_bbox_add_mode_enabled(self, enabled: bool) -> None:
        self._molecular_bbox_add_mode_enabled = bool(enabled)
        if not self._molecular_bbox_add_mode_enabled:
            self._manual_bbox_drag_start_px = None
            self._manual_bbox_drag_current_px = None
            self._set_manual_bbox_preview(None)

    def select_molecular_detection_by_id(self, detection_id: str | None) -> str | None:
        detection_id = str(detection_id) if detection_id is not None else None
        if detection_id is None or detection_id not in self._molecular_detection_overlay_items_by_id:
            self._set_selected_molecular_detection_id(None)
            return None
        self._set_selected_molecular_detection_id(detection_id)
        return detection_id

    def select_molecular_detection_at_pixel(
        self,
        x_px: float,
        y_px: float,
        *,
        source_view: str | None = None,
    ) -> str | None:
        detection_id = self._find_molecular_detection_at_pixel(
            float(x_px),
            float(y_px),
            source_view=source_view or self._current_molecular_detection_source_view,
        )
        self._set_selected_molecular_detection_id(detection_id)
        return detection_id

    def finish_manual_bbox_drag_from_pixels(
        self,
        start_xy_px: tuple[float, float],
        end_xy_px: tuple[float, float],
    ) -> tuple[float, float, float, float] | None:
        bbox_xyxy = self._bbox_from_pixel_drag(start_xy_px, end_xy_px)
        self._manual_bbox_drag_start_px = None
        self._manual_bbox_drag_current_px = None
        self._set_manual_bbox_preview(None)
        if bbox_xyxy is None:
            return None
        self.manual_molecular_bbox_drawn.emit(bbox_xyxy)
        return bbox_xyxy

    def show_molecular_detections(
        self,
        *,
        source_view: str,
        scale_nm_per_px: tuple[float | None, float | None],
    ) -> None:
        self.clear_molecular_detection_overlays()
        self._current_molecular_detection_source_view = str(source_view)
        if self._series is None:
            self._set_selected_molecular_detection_id(None)
            return
        detection_set = getattr(self._series, "molecular_detections", None)
        sx, sy = self._effective_scale_nm_per_px(scale_nm_per_px)
        self._current_scale_nm_per_px = (sx, sy)
        count = 0
        colors: list[tuple[int, int, int]] = []
        visible_ids: set[str] = set()
        if detection_set is not None:
            detections = detection_set.get_detections(
                self._series.active_frame_index,
                source_view=source_view,
            )
            for detection in detections:
                color = (255, 0, 255) if detection.selected else (255, 140, 0)
                polyline = self.viewer.add_polyline_nm(
                    self._bbox_polyline_nm(detection.bbox_xyxy, scale_nm_per_px=(sx, sy)),
                    color=color,
                    width=1.8,
                )
                if polyline is None:
                    continue
                visible_ids.add(detection.detection_id)
                self._molecular_detection_overlay_items_by_id[detection.detection_id] = [polyline]
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
        self._show_molecular_segmentations(source_view=source_view, scale_nm_per_px=(sx, sy))
        self._show_sam3_preview(source_view=source_view, scale_nm_per_px=(sx, sy))
        if self._selected_molecular_detection_id not in visible_ids:
            self._set_selected_molecular_detection_id(None)
        else:
            self._apply_molecular_detection_highlight()

    def _show_molecular_segmentations(
        self,
        *,
        source_view: str,
        scale_nm_per_px: tuple[float, float],
    ) -> None:
        self._visible_molecular_segmentation_count = 0
        self._visible_molecular_segmentation_ids = []
        self._molecular_segmentation_overlay_items_by_id = {}
        self._molecular_segmentation_prompt_ids_by_id = {}
        self._highlighted_molecular_segmentation_ids = []
        if self._series is None:
            return
        segmentation_set = getattr(self._series, "molecular_segmentations", None)
        if segmentation_set is None:
            return
        segmentations = segmentation_set.get_segmentations(
            self._series.active_frame_index,
            source_view=source_view,
        )
        count = 0
        visible_ids: list[str] = []
        sx, sy = scale_nm_per_px
        for segmentation in segmentations:
            items = []
            mask = self._full_frame_mask_for_segmentation(segmentation)
            if mask is not None:
                mask_item = self.viewer.add_mask_overlay_px(
                    mask,
                    color=(0, 200, 255),
                    alpha=80,
                    scale_nm_per_px=(sx, sy),
                )
                if mask_item is not None:
                    items.append(mask_item)
            if segmentation.polygon_xy is not None:
                polyline = self.viewer.add_polyline_nm(
                    self._polygon_polyline_nm(segmentation.polygon_xy, scale_nm_per_px=(sx, sy)),
                    color=(0, 220, 255),
                    width=2.0,
                )
                if polyline is not None:
                    items.append(polyline)
            if not items:
                continue
            self._molecular_segmentation_overlay_items_by_id[segmentation.segmentation_id] = items
            self._molecular_segmentation_prompt_ids_by_id[segmentation.segmentation_id] = tuple(
                segmentation.prompt_detection_ids
            )
            visible_ids.append(segmentation.segmentation_id)
            count += 1
        self._visible_molecular_segmentation_count = count
        self._visible_molecular_segmentation_ids = visible_ids

    def _show_sam3_preview(
        self,
        *,
        source_view: str,
        scale_nm_per_px: tuple[float, float],
    ) -> None:
        self._visible_sam3_preview_count = 0
        self._visible_sam3_preview_ids = []
        self._sam3_preview_overlay_items_by_id = {}
        if self._series is None:
            return
        clear_if_context_changed = getattr(self._series, "clear_sam3_preview_if_context_changed", None)
        if callable(clear_if_context_changed):
            clear_if_context_changed(source_view=source_view)
        preview = getattr(self._series, "sam3_preview", None)
        if preview is None:
            return
        matches_context = getattr(preview, "matches_context", None)
        if callable(matches_context) and not matches_context(
            frame_index=self._series.active_frame_index,
            source_view=source_view,
        ):
            self._series.sam3_preview = None
            return
        sx, sy = scale_nm_per_px
        visible_ids: list[str] = []
        count = 0
        for proposal in preview.proposals:
            items = []
            mask = self._full_frame_mask_for_sam3_preview_proposal(proposal)
            if mask is not None:
                mask_item = self.viewer.add_mask_overlay_px(
                    mask,
                    color=(0, 255, 120),
                    alpha=70,
                    scale_nm_per_px=(sx, sy),
                )
                if mask_item is not None:
                    items.append(mask_item)
            if proposal.polygon_xy:
                polyline = self.viewer.add_polyline_nm(
                    self._polygon_polyline_nm(proposal.polygon_xy, scale_nm_per_px=(sx, sy)),
                    color=(0, 255, 120),
                    width=2.0,
                )
                if polyline is not None:
                    items.append(polyline)
            bbox_item = self.viewer.add_polyline_nm(
                self._bbox_polyline_nm(proposal.bbox_xyxy, scale_nm_per_px=(sx, sy)),
                color=(0, 255, 120),
                width=1.8,
            )
            if bbox_item is not None:
                items.append(bbox_item)
            x0, y0, x1, y1 = proposal.bbox_xyxy
            self.viewer.add_text_nm(
                f"SAM3 {proposal.score:.2f}",
                (((x0 + x1) / 2.0) * sx, ((y0 + y1) / 2.0) * sy),
                color=(0, 255, 120),
            )
            if not items:
                continue
            self._sam3_preview_overlay_items_by_id[proposal.proposal_id] = items
            visible_ids.append(proposal.proposal_id)
            count += 1
        self._visible_sam3_preview_count = count
        self._visible_sam3_preview_ids = visible_ids

    def _on_scene_mouse_clicked(self, event) -> None:
        if self._series is None:
            return
        if self._molecular_bbox_add_mode_enabled:
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if not self.viewer.plot_item.sceneBoundingRect().contains(event.scenePos()):
            return

        view_pos = self.viewer.plot_item.getViewBox().mapSceneToView(event.scenePos())
        x_px, y_px = self._view_to_pixel_coords(view_pos.x(), view_pos.y())
        self.select_molecular_detection_at_pixel(x_px, y_px)
        event.accept()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.viewer.glw.viewport() and self._molecular_bbox_add_mode_enabled:
            event_type = event.type()
            if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                start_px = self._pixel_coords_from_viewport_pos(event.position())
                if start_px is None:
                    return False
                self._manual_bbox_drag_start_px = start_px
                self._manual_bbox_drag_current_px = start_px
                self._set_manual_bbox_preview(None)
                event.accept()
                return True

            if event_type == QEvent.Type.MouseMove and self._manual_bbox_drag_start_px is not None:
                current_px = self._pixel_coords_from_viewport_pos(event.position(), require_inside=False)
                if current_px is not None:
                    self._manual_bbox_drag_current_px = current_px
                    self._set_manual_bbox_preview(
                        self._bbox_from_pixel_drag(self._manual_bbox_drag_start_px, current_px)
                    )
                event.accept()
                return True

            if event_type == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                if self._manual_bbox_drag_start_px is None:
                    return False
                end_px = self._pixel_coords_from_viewport_pos(event.position(), require_inside=False)
                if end_px is None:
                    end_px = self._manual_bbox_drag_current_px or self._manual_bbox_drag_start_px
                self.finish_manual_bbox_drag_from_pixels(self._manual_bbox_drag_start_px, end_px)
                event.accept()
                return True

        return super().eventFilter(watched, event)

    def _find_molecular_detection_at_pixel(
        self,
        x_px: float,
        y_px: float,
        *,
        source_view: str,
    ) -> str | None:
        if self._series is None:
            return None
        detection_set = getattr(self._series, "molecular_detections", None)
        if detection_set is None:
            return None
        detections = detection_set.get_detections(
            self._series.active_frame_index,
            source_view=source_view,
        )
        matches = []
        for detection in detections:
            x0, y0, x1, y1 = detection.bbox_xyxy
            if float(x0) <= x_px <= float(x1) and float(y0) <= y_px <= float(y1):
                area = (float(x1) - float(x0)) * (float(y1) - float(y0))
                matches.append((area, detection.detection_id))
        if not matches:
            return None
        matches.sort(key=lambda item: item[0])
        return matches[0][1]

    def _view_to_pixel_coords(self, x_view: float, y_view: float) -> tuple[float, float]:
        sx, sy = self._current_scale_nm_per_px
        return float(x_view) / sx, float(y_view) / sy

    def _pixel_coords_from_viewport_pos(self, pos, *, require_inside: bool = True) -> tuple[float, float] | None:
        scene_pos = self.viewer.glw.mapToScene(pos.toPoint())
        if require_inside and not self.viewer.plot_item.sceneBoundingRect().contains(scene_pos):
            return None
        view_pos = self.viewer.plot_item.getViewBox().mapSceneToView(scene_pos)
        return self._view_to_pixel_coords(view_pos.x(), view_pos.y())

    def _bbox_from_pixel_drag(
        self,
        start_xy_px: tuple[float, float],
        end_xy_px: tuple[float, float],
    ) -> tuple[float, float, float, float] | None:
        x0 = min(float(start_xy_px[0]), float(end_xy_px[0]))
        y0 = min(float(start_xy_px[1]), float(end_xy_px[1]))
        x1 = max(float(start_xy_px[0]), float(end_xy_px[0]))
        y1 = max(float(start_xy_px[1]), float(end_xy_px[1]))
        if self._current_image_shape_px is not None:
            height, width = self._current_image_shape_px
            x0 = min(max(x0, 0.0), float(width))
            x1 = min(max(x1, 0.0), float(width))
            y0 = min(max(y0, 0.0), float(height))
            y1 = min(max(y1, 0.0), float(height))
        if x1 <= x0 or y1 <= y0:
            return None
        return x0, y0, x1, y1

    def _set_manual_bbox_preview(self, bbox_xyxy: tuple[float, float, float, float] | None) -> None:
        if self._manual_bbox_preview_item is not None:
            self.viewer.remove_item(self._manual_bbox_preview_item)
            self._manual_bbox_preview_item = None
        if bbox_xyxy is None:
            return
        self._manual_bbox_preview_item = self.viewer.add_polyline_nm(
            self._bbox_polyline_nm(bbox_xyxy, scale_nm_per_px=self._current_scale_nm_per_px),
            color=(255, 220, 0),
            width=1.5,
        )

    def _set_selected_molecular_detection_id(self, detection_id: str | None) -> None:
        detection_id = str(detection_id) if detection_id is not None else None
        if detection_id == self._selected_molecular_detection_id:
            self._apply_molecular_detection_highlight()
            return
        self._selected_molecular_detection_id = detection_id
        self._apply_molecular_detection_highlight()
        self.molecular_detection_selection_changed.emit(detection_id)

    def _apply_molecular_detection_highlight(self) -> None:
        selected_id = self._selected_molecular_detection_id
        for detection_id, items in self._molecular_detection_overlay_items_by_id.items():
            for item in items:
                self.viewer.set_item_highlight(item, detection_id == selected_id)
        highlighted_segmentations: list[str] = []
        for segmentation_id, items in self._molecular_segmentation_overlay_items_by_id.items():
            prompt_ids = self._molecular_segmentation_prompt_ids_by_id.get(segmentation_id, ())
            highlighted = selected_id is not None and selected_id in prompt_ids
            if highlighted:
                highlighted_segmentations.append(segmentation_id)
            for item in items:
                self.viewer.set_item_highlight(item, highlighted)
        self._highlighted_molecular_segmentation_ids = highlighted_segmentations

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

    def _polygon_polyline_nm(
        self,
        polygon_xy,
        *,
        scale_nm_per_px: tuple[float, float],
    ) -> np.ndarray:
        sx, sy = scale_nm_per_px
        pts = np.asarray(polygon_xy, dtype=np.float64)
        if pts.ndim != 2 or pts.shape[1] != 2:
            return np.empty((0, 2), dtype=np.float64)
        if len(pts) >= 2 and not np.allclose(pts[0], pts[-1]):
            pts = np.vstack([pts, pts[0]])
        pts = pts.copy()
        pts[:, 0] *= sx
        pts[:, 1] *= sy
        return pts

    def _full_frame_mask_for_segmentation(self, segmentation) -> np.ndarray | None:
        if segmentation.mask is None:
            return None
        mask = np.asarray(segmentation.mask, dtype=bool)
        if self._current_image_shape_px is None:
            return mask
        image_height, image_width = self._current_image_shape_px
        if mask.shape == (image_height, image_width):
            return mask
        if segmentation.bbox_xyxy is None:
            return None

        x0, y0, x1, y1 = (int(round(float(value))) for value in segmentation.bbox_xyxy)
        x0 = min(max(x0, 0), image_width)
        x1 = min(max(x1, 0), image_width)
        y0 = min(max(y0, 0), image_height)
        y1 = min(max(y1, 0), image_height)
        if x1 <= x0 or y1 <= y0:
            return None
        target_shape = (y1 - y0, x1 - x0)
        if mask.shape != target_shape:
            return None
        full_mask = np.zeros((image_height, image_width), dtype=bool)
        full_mask[y0:y1, x0:x1] = mask
        return full_mask

    def _full_frame_mask_for_sam3_preview_proposal(self, proposal) -> np.ndarray | None:
        if proposal.mask is None:
            return None
        mask = np.asarray(proposal.mask, dtype=bool)
        if self._current_image_shape_px is None:
            return mask
        image_height, image_width = self._current_image_shape_px
        if mask.shape == (image_height, image_width):
            return mask
        return None
