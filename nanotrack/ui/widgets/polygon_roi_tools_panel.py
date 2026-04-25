from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from nanotrack.core import PolygonROI


class PolygonRoiToolsPanel(QWidget):
    """Sidebar tools for drawing and editing a polygon ROI per frame."""

    draw_mode_toggled = pyqtSignal(bool)
    finish_requested = pyqtSignal()
    clear_requested = pyqtSignal()
    preview_requested = pyqtSignal()
    run_sequence_requested = pyqtSignal()
    load_edge_requested = pyqtSignal()
    save_edge_correction_requested = pyqtSignal()
    resume_edge_requested = pyqtSignal()
    redetect_edge_requested = pyqtSignal()
    redetect_edge_range_requested = pyqtSignal()
    hybrid_stabilize_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence_loaded = False
        self._processing_busy = False
        self._draw_mode_active = False
        self._has_polygon = False
        self._has_active_edge = False
        self._has_edge_polyline_on_frame = False
        self._has_editable_edge = False
        self._frame_count = 0
        self._build()
        self._connect_signals()
        self._update_enabled_state()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Polygon ROI Tools", self)
        group_layout = QVBoxLayout(group)

        self.lbl_hint = QLabel(
            "Click successive vertices on the image, then use Finish Polygon to close the ROI. "
            "After finishing, drag the vertex handles to edit the polygon.",
            group,
        )
        self.lbl_hint.setWordWrap(True)
        group_layout.addWidget(self.lbl_hint)

        button_row = QHBoxLayout()
        self.btn_draw = QPushButton("Draw Polygon ROI", group)
        self.btn_draw.setCheckable(True)
        self.btn_finish = QPushButton("Finish Polygon", group)
        self.btn_clear = QPushButton("Clear Current", group)
        self.btn_preview = QPushButton("Preview Edge Detection", group)
        button_row.addWidget(self.btn_draw)
        button_row.addWidget(self.btn_finish)
        button_row.addWidget(self.btn_clear)
        button_row.addWidget(self.btn_preview)
        group_layout.addLayout(button_row)

        run_row = QHBoxLayout()
        self.btn_run_sequence = QPushButton("Run Edge Detection on Range", group)
        self.sp_run_end_frame = QSpinBox(group)
        self.sp_run_end_frame.setPrefix("End ")
        self.sp_run_end_frame.setMinimum(1)
        self.sp_run_end_frame.setMaximum(1)
        self.sp_run_end_frame.setValue(1)
        self.sp_run_end_frame.setToolTip(
            "Current frame is the start; choose the last frame included in this edge-detector run."
        )
        self.chk_stitch_active = QCheckBox("Stitch Active Edge", group)
        self.chk_stitch_active.setToolTip(
            "Append or replace only the selected frame range in the currently active edge track instead of creating a new edge."
        )
        run_row.addWidget(self.btn_run_sequence)
        run_row.addWidget(self.sp_run_end_frame)
        run_row.addWidget(self.chk_stitch_active)
        group_layout.addLayout(run_row)

        edge_row = QHBoxLayout()
        self.btn_load_edge = QPushButton("Load Current Edge", group)
        self.btn_save_edge = QPushButton("Save Edge Correction", group)
        self.btn_resume_edge = QPushButton("Resume Edge Tracking", group)
        self.btn_redetect_edge = QPushButton("Re-detect Edge", group)
        self.btn_redetect_edge_range = QPushButton("Re-detect Range", group)
        edge_row.addWidget(self.btn_load_edge)
        edge_row.addWidget(self.btn_save_edge)
        edge_row.addWidget(self.btn_resume_edge)
        edge_row.addWidget(self.btn_redetect_edge)
        edge_row.addWidget(self.btn_redetect_edge_range)
        group_layout.addLayout(edge_row)

        hybrid_row = QHBoxLayout()
        self.cmb_tracker = QComboBox(group)
        self.cmb_tracker.addItem("TAPIR", "tapir")
        self.cmb_tracker.addItem("LocoTrack", "locotrack")
        self.cmb_tracker.addItem("Track-On-R", "trackonr")
        self.cmb_tracker.setToolTip("Point-tracker backend used to stabilize the edge polyline over time.")
        self.sp_tracker_points = QSpinBox(group)
        self.sp_tracker_points.setRange(4, 64)
        self.sp_tracker_points.setValue(16)
        self.sp_tracker_points.setPrefix("Pts ")
        self.sp_tracker_points.setToolTip("Number of control points sampled from the anchor polyline.")
        self.btn_hybrid = QPushButton("Hybrid Stabilize", group)
        hybrid_row.addWidget(self.cmb_tracker)
        hybrid_row.addWidget(self.sp_tracker_points)
        hybrid_row.addWidget(self.btn_hybrid)
        group_layout.addLayout(hybrid_row)

        dexined_row = QHBoxLayout()
        self.cmb_edge_backend = QComboBox(group)
        self.cmb_edge_backend.addItem("DexiNed", "dexined")
        self.cmb_edge_backend.addItem("TEED", "teed")
        self.cmb_edge_backend.addItem("NBED", "nbed")
        self.cmb_edge_backend.setToolTip(
            "Coarse edge-detector backend used before component selection, polyline extraction, and refinement."
        )
        self.sp_dexined_threshold = QDoubleSpinBox(group)
        self.sp_dexined_threshold.setRange(0.05, 0.95)
        self.sp_dexined_threshold.setSingleStep(0.05)
        self.sp_dexined_threshold.setDecimals(2)
        self.sp_dexined_threshold.setValue(0.35)
        self.sp_dexined_threshold.setPrefix("Thr ")
        self.sp_dexined_threshold.setToolTip(
            "Probability threshold used to binarize the coarse edge-detector response."
        )
        self.sp_edge_components = QSpinBox(group)
        self.sp_edge_components.setRange(1, 8)
        self.sp_edge_components.setValue(1)
        self.sp_edge_components.setPrefix("k ")
        self.sp_edge_components.setToolTip("Number of strongest edge components inside the ROI used to build one polyline.")
        self.cmb_inference_resolution = QComboBox(group)
        self.cmb_inference_resolution.addItem("Auto", None)
        self.cmb_inference_resolution.addItem("512 px", (512, 512))
        self.cmb_inference_resolution.addItem("768 px", (768, 768))
        self.cmb_inference_resolution.addItem("1024 px", (1024, 1024))
        self.cmb_inference_resolution.setToolTip("Square inference resolution used for the edge-detector crop.")
        dexined_row.addWidget(self.cmb_edge_backend)
        dexined_row.addWidget(self.sp_dexined_threshold)
        dexined_row.addWidget(self.sp_edge_components)
        dexined_row.addWidget(self.cmb_inference_resolution)
        group_layout.addLayout(dexined_row)

        refine_row = QHBoxLayout()
        self.cmb_refine_score_mode = QComboBox(group)
        self.cmb_refine_score_mode.addItem("Ref combined", "combined")
        self.cmb_refine_score_mode.addItem("Ref edge_prob", "edge_prob")
        self.cmb_refine_score_mode.addItem("Ref gradient", "gradient")
        self.cmb_refine_score_mode.setToolTip(
            "Score used during normal-direction refinement of the final edge geometry."
        )
        self.sp_refine_radius = QSpinBox(group)
        self.sp_refine_radius.setRange(1, 24)
        self.sp_refine_radius.setValue(4)
        self.sp_refine_radius.setPrefix("R ")
        self.sp_refine_radius.setSuffix(" px")
        self.sp_refine_radius.setToolTip("Half-width of the search window used to localize the final edge.")
        refine_row.addWidget(self.cmb_refine_score_mode)
        refine_row.addWidget(self.sp_refine_radius)
        group_layout.addLayout(refine_row)

        self.lbl_frame = QLabel("Frame: -", group)
        self.lbl_polygon = QLabel("No polygon ROI on current frame", group)
        self.lbl_edge = QLabel("Active edge track: -", group)
        self.lbl_polygon.setWordWrap(True)
        group_layout.addWidget(self.lbl_frame)
        group_layout.addWidget(self.lbl_polygon)
        group_layout.addWidget(self.lbl_edge)

        layout.addWidget(group)
        layout.addStretch(0)

    def _connect_signals(self) -> None:
        self.btn_draw.toggled.connect(self.draw_mode_toggled)
        self.btn_finish.clicked.connect(self.finish_requested)
        self.btn_clear.clicked.connect(self.clear_requested)
        self.btn_preview.clicked.connect(self.preview_requested)
        self.btn_run_sequence.clicked.connect(self.run_sequence_requested)
        self.btn_load_edge.clicked.connect(self.load_edge_requested)
        self.btn_save_edge.clicked.connect(self.save_edge_correction_requested)
        self.btn_resume_edge.clicked.connect(self.resume_edge_requested)
        self.btn_redetect_edge.clicked.connect(self.redetect_edge_requested)
        self.btn_redetect_edge_range.clicked.connect(self.redetect_edge_range_requested)
        self.btn_hybrid.clicked.connect(self.hybrid_stabilize_requested)

    def _update_enabled_state(self) -> None:
        enabled = self._sequence_loaded and not self._processing_busy
        self.btn_draw.setEnabled(enabled)
        self.btn_finish.setEnabled(enabled and self._draw_mode_active)
        self.btn_clear.setEnabled(enabled and (self._draw_mode_active or self._has_polygon))
        self.btn_preview.setEnabled(enabled and self._has_polygon and not self._draw_mode_active)
        self.btn_run_sequence.setEnabled(enabled and self._has_polygon and not self._draw_mode_active)
        self.sp_run_end_frame.setEnabled(enabled)
        self.cmb_edge_backend.setEnabled(enabled)
        self.chk_stitch_active.setEnabled(enabled and self._has_active_edge)
        if not (enabled and self._has_active_edge):
            blocked = self.chk_stitch_active.blockSignals(True)
            self.chk_stitch_active.setChecked(False)
            self.chk_stitch_active.blockSignals(blocked)
        self.btn_load_edge.setEnabled(enabled and self._has_active_edge and self._has_edge_polyline_on_frame)
        self.btn_save_edge.setEnabled(enabled and self._has_active_edge and self._has_polygon and self._has_editable_edge)
        self.btn_resume_edge.setEnabled(
            enabled
            and self._has_active_edge
            and self._has_polygon
            and (self._has_editable_edge or self._has_edge_polyline_on_frame)
        )
        self.btn_redetect_edge.setEnabled(enabled and self._has_active_edge and not self._draw_mode_active)
        self.btn_redetect_edge_range.setEnabled(enabled and self._has_active_edge and not self._draw_mode_active)
        self.sp_dexined_threshold.setEnabled(enabled)
        self.sp_edge_components.setEnabled(enabled)
        self.cmb_inference_resolution.setEnabled(enabled)
        self.cmb_refine_score_mode.setEnabled(enabled)
        self.sp_refine_radius.setEnabled(enabled)
        self.cmb_tracker.setEnabled(enabled)
        self.sp_tracker_points.setEnabled(enabled)
        self.btn_hybrid.setEnabled(
            enabled and self._has_active_edge and (self._has_editable_edge or self._has_edge_polyline_on_frame)
        )

    def set_draw_mode_active(self, active: bool) -> None:
        self._draw_mode_active = bool(active)
        blocked = self.btn_draw.blockSignals(True)
        self.btn_draw.setChecked(self._draw_mode_active)
        self.btn_draw.blockSignals(blocked)
        self._update_enabled_state()

    def set_current_polygon(self, frame_index: int | None, polygon: PolygonROI | None) -> None:
        if frame_index is None:
            self.lbl_frame.setText("Frame: -")
            self.lbl_polygon.setText("No sequence loaded")
            self._has_polygon = False
            self._update_enabled_state()
            return

        self.lbl_frame.setText(f"Frame: {frame_index + 1}")
        if polygon is None:
            self.lbl_polygon.setText("No polygon ROI on current frame")
            self._has_polygon = False
            self._update_enabled_state()
            return

        x0, y0, x1, y1 = polygon.bounds_xyxy
        self.lbl_polygon.setText(
            "Vertices: {} | bounds x=[{:.1f}, {:.1f}], y=[{:.1f}, {:.1f}]".format(
                polygon.vertex_count,
                x0,
                x1,
                y0,
                y1,
            )
        )
        self._has_polygon = True
        self._update_enabled_state()

    def set_frame_context(self, frame_index: int | None, frame_count: int | None) -> None:
        if frame_index is None or frame_count is None or frame_count <= 0:
            self._frame_count = 0
            self.sp_run_end_frame.setRange(1, 1)
            self.sp_run_end_frame.setValue(1)
            self._update_enabled_state()
            return

        self._frame_count = int(frame_count)
        start_frame_number = int(frame_index) + 1
        previous_minimum = int(self.sp_run_end_frame.minimum())
        previous_value = int(self.sp_run_end_frame.value())
        self.sp_run_end_frame.setRange(start_frame_number, self._frame_count)
        if start_frame_number <= previous_value <= self._frame_count and previous_value != previous_minimum:
            target_value = previous_value
        else:
            target_value = self._frame_count
        self.sp_run_end_frame.setValue(target_value)
        self._update_enabled_state()

    def clear(self) -> None:
        self.set_draw_mode_active(False)
        self.lbl_frame.setText("Frame: -")
        self.lbl_polygon.setText("No sequence loaded")
        self.lbl_edge.setText("Active edge track: -")
        self._has_polygon = False
        self._has_active_edge = False
        self._has_edge_polyline_on_frame = False
        self._has_editable_edge = False
        self._frame_count = 0
        self._update_enabled_state()

    def set_sequence_loaded(self, loaded: bool) -> None:
        was_loaded = self._sequence_loaded
        self._sequence_loaded = bool(loaded)
        if not self._sequence_loaded:
            self.clear()
        elif not was_loaded:
            self.lbl_polygon.setText("No polygon ROI on current frame")
            self.lbl_edge.setText("Active edge track: -")
            self._has_polygon = False
            self._has_active_edge = False
            self._has_edge_polyline_on_frame = False
            self._has_editable_edge = False
            self._frame_count = 0
        self._update_enabled_state()

    def set_processing(self, busy: bool) -> None:
        self._processing_busy = bool(busy)
        self._update_enabled_state()

    def hybrid_tracker_model(self) -> str:
        current_data = self.cmb_tracker.currentData()
        return "tapir" if current_data is None else str(current_data)

    def hybrid_control_point_count(self) -> int:
        return int(self.sp_tracker_points.value())

    def edge_backend(self) -> str:
        current_data = self.cmb_edge_backend.currentData()
        return "dexined" if current_data is None else str(current_data)

    def dexined_threshold(self) -> float:
        return float(self.sp_dexined_threshold.value())

    def dexined_top_k_components(self) -> int:
        return int(self.sp_edge_components.value())

    def dexined_inference_resolution_hw(self) -> tuple[int, int] | None:
        value = self.cmb_inference_resolution.currentData()
        if value is None:
            return None
        height, width = value
        return int(height), int(width)

    def edge_refine_score_mode(self) -> str:
        current_data = self.cmb_refine_score_mode.currentData()
        return "combined" if current_data is None else str(current_data)

    def edge_refine_search_radius_px(self) -> int:
        return int(self.sp_refine_radius.value())

    def edge_run_end_frame_index(self) -> int:
        return max(0, int(self.sp_run_end_frame.value()) - 1)

    def stitch_to_active_edge(self) -> bool:
        return self.chk_stitch_active.isEnabled() and self.chk_stitch_active.isChecked()

    def set_edge_track_context(
        self,
        edge_label: str | None,
        *,
        has_polyline_on_current_frame: bool,
        has_editable_polyline: bool,
    ) -> None:
        if edge_label is None:
            self.lbl_edge.setText("Active edge track: -")
            self._has_active_edge = False
            self._has_edge_polyline_on_frame = False
            self._has_editable_edge = False
            self._update_enabled_state()
            return

        self.lbl_edge.setText(f"Active edge track: {edge_label}")
        self._has_active_edge = True
        self._has_edge_polyline_on_frame = bool(has_polyline_on_current_frame)
        self._has_editable_edge = bool(has_editable_polyline)
        self._update_enabled_state()
