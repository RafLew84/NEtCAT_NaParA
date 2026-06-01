from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QRectF, QSignalBlocker
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QApplication,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from moltrack.core import (
    AnalysisRegion,
    AnalysisRegionKind,
    CopiedAnalysisRegion,
    DetectionReviewStatus,
    FrameScopedAnalysisRegion,
    MolTrackProject,
    MolecularDetection,
)
from moltrack.io import import_image_series
from moltrack.persistence import load_project, save_project
from moltrack.registration import expanded_registered_working_stack, run_project_registration
from moltrack.yolo import MolTrackYoloDetectionConfig, MolTrackYoloModelInfo, discover_moltrack_yolo_models
from nanotrack.yolo import YoloRuntime
from napara.gui.widgets.viewer_widget import ViewerWidget


EXPANDED_REGION_MODE_FIXED_CANVAS = "fixed_canvas"
EXPANDED_REGION_MODE_MOVE_WITH_IMAGE = "move_with_image"


class MolTrackWorkspace(QMainWindow):
    """Top-level MolTrack workspace window."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("moltrack-workspace")
        self.setWindowTitle("MolTrack Workspace")
        self._project: MolTrackProject | None = None
        self._project_path: Path | None = None
        self._active_working_frame_index = 0
        self._displayed_frame: np.ndarray | None = None
        self._show_expanded_aligned_view = False
        self._expanded_aligned_stack = None
        self._expanded_aligned_cache_key: tuple[int, int] | None = None
        self._analysis_regions: dict[str, AnalysisRegion] = {}
        self._analysis_region_items: dict[str, object] = {}
        self._molecular_detection_items: list[object] = []
        self._selected_molecular_detection_id: str | None = None
        self._yolo_models: list[MolTrackYoloModelInfo] = []
        self._selected_yolo_model_path: Path | None = None
        self._yolo_detection_config = MolTrackYoloDetectionConfig()
        self._copied_analysis_regions: dict[str, CopiedAnalysisRegion] = {}
        self._frame_scoped_analysis_regions: list[FrameScopedAnalysisRegion] = []
        self._draft_region_roi = None
        self._draft_region_roi_kind: str | None = None
        self._draft_detection_bbox_roi = None
        self._editing_detection_id: str | None = None
        self._build_menu()
        self._build_registration_toolbar()

        central = QWidget(self)
        root_layout = QHBoxLayout(central)
        viewer_panel = QWidget(central)
        layout = QVBoxLayout(viewer_panel)
        self.lbl_title = QLabel("MolTrack Workspace", central)
        self.lbl_frame_index = QLabel("No project loaded", central)
        self.lbl_frame_index.setObjectName("moltrack-frame-index-label")

        self.viewer = ViewerWidget(central)
        self.viewer.glw.scene().sigMouseClicked.connect(self._on_viewer_scene_mouse_clicked)

        self.frame_slider = QSlider(Qt.Orientation.Horizontal, central)
        self.frame_slider.setObjectName("moltrack-frame-slider")
        self.frame_slider.setEnabled(False)
        self.frame_slider.valueChanged.connect(self.set_active_working_frame_index)

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_frame_index)
        layout.addWidget(self.viewer, 1)
        layout.addWidget(self.frame_slider)
        root_layout.addWidget(viewer_panel, 1)
        root_layout.addWidget(self._build_regions_panel(central))
        self.setCentralWidget(central)

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("File")

        self.import_image_series_action = QAction("Import Image Series...", self)
        self.import_image_series_action.triggered.connect(self._on_import_image_series)
        file_menu.addAction(self.import_image_series_action)

        self.import_reversed_order_action = QAction("Import Reversed Order", self)
        self.import_reversed_order_action.setCheckable(True)
        file_menu.addAction(self.import_reversed_order_action)

        self.open_project_action = QAction("Open Project...", self)
        self.open_project_action.triggered.connect(self._on_open_project)
        file_menu.addAction(self.open_project_action)

        self.save_project_action = QAction("Save Project", self)
        self.save_project_action.triggered.connect(self._on_save_project)
        file_menu.addAction(self.save_project_action)

        self.save_project_as_action = QAction("Save Project As...", self)
        self.save_project_as_action.triggered.connect(self._on_save_project_as)
        file_menu.addAction(self.save_project_as_action)

        registration_menu = self.menuBar().addMenu("Registration")

        self.run_registration_action = QAction("Run Registration", self)
        self.run_registration_action.triggered.connect(self._on_run_registration)
        registration_menu.addAction(self.run_registration_action)

        self.show_expanded_aligned_action = QAction("Show Expanded Aligned", self)
        self.show_expanded_aligned_action.setCheckable(True)
        self.show_expanded_aligned_action.toggled.connect(self._on_show_expanded_aligned_toggled)
        registration_menu.addAction(self.show_expanded_aligned_action)

        regions_menu = self.menuBar().addMenu("Regions")

        self.add_rect_region_action = QAction("Add Rect Region...", self)
        self.add_rect_region_action.triggered.connect(self._on_add_rect_region)
        regions_menu.addAction(self.add_rect_region_action)

        self.draw_rect_region_roi_action = QAction("Draw Rect ROI", self)
        self.draw_rect_region_roi_action.triggered.connect(self._on_draw_rect_region_roi)
        regions_menu.addAction(self.draw_rect_region_roi_action)

        self.draw_polyline_region_action = QAction("Draw Polyline Region", self)
        self.draw_polyline_region_action.triggered.connect(self._on_draw_polyline_region)
        regions_menu.addAction(self.draw_polyline_region_action)

        self.commit_drawn_region_action = QAction("Commit Drawn Region...", self)
        self.commit_drawn_region_action.triggered.connect(self._on_commit_drawn_region)
        regions_menu.addAction(self.commit_drawn_region_action)

        self.clear_drawn_region_action = QAction("Clear Drawn Region", self)
        self.clear_drawn_region_action.triggered.connect(self.clear_drawn_region_roi)
        regions_menu.addAction(self.clear_drawn_region_action)

        self.apply_selected_region_to_current_frame_action = QAction("Apply Selected to Current Frame", self)
        self.apply_selected_region_to_current_frame_action.triggered.connect(
            self._on_apply_selected_region_to_current_frame
        )
        regions_menu.addAction(self.apply_selected_region_to_current_frame_action)

        self.copy_selected_region_from_current_to_end_action = QAction("Copy Selected from Current to End", self)
        self.copy_selected_region_from_current_to_end_action.triggered.connect(
            self._on_copy_selected_region_from_current_to_end
        )
        regions_menu.addAction(self.copy_selected_region_from_current_to_end_action)

        self.copy_selected_region_to_frame_range_action = QAction("Copy Selected to Frame Range...", self)
        self.copy_selected_region_to_frame_range_action.triggered.connect(
            self._on_copy_selected_region_to_frame_range
        )
        regions_menu.addAction(self.copy_selected_region_to_frame_range_action)

        self.edit_selected_region_action = QAction("Edit Selected Region...", self)
        self.edit_selected_region_action.triggered.connect(self._on_edit_selected_region)
        regions_menu.addAction(self.edit_selected_region_action)

        self.delete_selected_region_action = QAction("Delete Selected Region", self)
        self.delete_selected_region_action.triggered.connect(self._on_delete_selected_region)
        regions_menu.addAction(self.delete_selected_region_action)

        self.copy_selected_region_to_series_action = QAction("Copy Selected to Series", self)
        self.copy_selected_region_to_series_action.triggered.connect(self._on_copy_selected_region_to_series)
        regions_menu.addAction(self.copy_selected_region_to_series_action)

        yolo_menu = self.menuBar().addMenu("YOLO")
        self.detect_yolo_current_frame_action = QAction("Detect Current Frame", self)
        self.detect_yolo_current_frame_action.triggered.connect(self._on_detect_yolo_current_frame)
        yolo_menu.addAction(self.detect_yolo_current_frame_action)

        self.detect_yolo_current_frame_in_selected_roi_action = QAction(
            "Detect Current Frame in Selected ROI",
            self,
        )
        self.detect_yolo_current_frame_in_selected_roi_action.triggered.connect(
            self._on_detect_yolo_current_frame_in_selected_roi
        )
        yolo_menu.addAction(self.detect_yolo_current_frame_in_selected_roi_action)

        self.detect_yolo_all_working_frames_action = QAction("Detect All Working Frames", self)
        self.detect_yolo_all_working_frames_action.triggered.connect(self._on_detect_yolo_all_working_frames)
        yolo_menu.addAction(self.detect_yolo_all_working_frames_action)

        self.detect_yolo_selected_roi_frame_range_action = QAction(
            "Detect Selected ROI on Frame Range...",
            self,
        )
        self.detect_yolo_selected_roi_frame_range_action.triggered.connect(
            self._on_detect_yolo_selected_roi_frame_range
        )
        yolo_menu.addAction(self.detect_yolo_selected_roi_frame_range_action)

    def _build_registration_toolbar(self) -> None:
        toolbar = QToolBar("Registration", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        toolbar.addWidget(QLabel("Registration:", self))
        self.registration_backend_combo = QComboBox(self)
        self.registration_backend_combo.addItem("Phase", "phase_correlation")
        self.registration_backend_combo.addItem("Optical Flow", "optical_flow_median")
        self.registration_backend_combo.setToolTip("Registration algorithm used for adjacent registration.")
        toolbar.addWidget(self.registration_backend_combo)
        toolbar.addAction(self.run_registration_action)
        toolbar.addAction(self.show_expanded_aligned_action)

    def _build_regions_panel(self, parent: QWidget) -> QWidget:
        scroll = QScrollArea(parent)
        scroll.setObjectName("moltrack-side-panel-scroll")
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(320)
        scroll.setToolTip("Side panel with region and detection lists plus frame-wide actions.")

        panel = QWidget(scroll)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        def group(title: str, tooltip: str) -> tuple[QGroupBox, QVBoxLayout]:
            box = QGroupBox(title, panel)
            box.setToolTip(tooltip)
            box_layout = QVBoxLayout(box)
            box_layout.setSpacing(6)
            return box, box_layout

        def button(text: str, tooltip: str, callback) -> QPushButton:
            btn = QPushButton(text, panel)
            btn.setToolTip(tooltip)
            btn.clicked.connect(callback)
            return btn

        def button_row(*buttons: QPushButton) -> QWidget:
            row = QWidget(panel)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            for btn in buttons:
                row_layout.addWidget(btn)
            return row

        regions_group, regions_layout = group(
            "Regions",
            "Define and manage analysis regions on the active working frame.",
        )

        self.expanded_region_mode_combo = QComboBox(panel)
        self.expanded_region_mode_combo.addItem("Fixed expanded canvas", EXPANDED_REGION_MODE_FIXED_CANVAS)
        self.expanded_region_mode_combo.addItem("Move with image", EXPANDED_REGION_MODE_MOVE_WITH_IMAGE)
        self.expanded_region_mode_combo.setToolTip(
            "Controls how region copy/apply behaves while Show Expanded Aligned is enabled."
        )
        regions_layout.addWidget(QLabel("Expanded region mode", panel))
        regions_layout.addWidget(self.expanded_region_mode_combo)

        self.region_list = QListWidget(panel)
        self.region_list.setObjectName("moltrack-region-list")
        self.region_list.setToolTip("Analysis regions available on the active working frame.")
        regions_layout.addWidget(self.region_list, 1)
        layout.addWidget(regions_group)

        region_actions_group, region_actions_layout = group(
            "Region Actions",
            "Create, edit, delete, and copy analysis regions.",
        )
        add_button = button("Add Rect", "Open a coordinate dialog for a rectangular region.", lambda: self.add_rect_region_action.trigger())
        draw_rect_button = button("Draw ROI", "Draw a rectangular ROI directly on the viewer.", lambda: self.draw_rect_region_roi_action.trigger())
        draw_poly_button = button("Draw Polyline", "Draw a polygon/polyline region directly on the viewer.", lambda: self.draw_polyline_region_action.trigger())
        commit_button = button("Commit Drawn", "Save the currently drawn ROI/polyline as a region.", lambda: self.commit_drawn_region_action.trigger())
        apply_current_button = button("Apply Current", "Apply the selected region geometry to the active working frame.", lambda: self.apply_selected_region_to_current_frame_action.trigger())
        copy_to_end_button = button("Copy to End", "Copy the selected region from the active frame to the end of the series.", lambda: self.copy_selected_region_from_current_to_end_action.trigger())
        copy_range_button = button("Copy Range", "Copy the selected region to a chosen working-frame range.", lambda: self.copy_selected_region_to_frame_range_action.trigger())
        edit_button = button("Edit", "Edit metadata or rectangle coordinates for the selected region.", lambda: self.edit_selected_region_action.trigger())
        delete_button = button("Delete", "Delete the selected region.", lambda: self.delete_selected_region_action.trigger())
        copy_button = button("Copy to Series", "Copy the selected region to the whole working series.", lambda: self.copy_selected_region_to_series_action.trigger())
        region_actions_layout.addWidget(button_row(add_button, draw_rect_button))
        region_actions_layout.addWidget(button_row(draw_poly_button, commit_button))
        region_actions_layout.addWidget(button_row(apply_current_button, copy_to_end_button))
        region_actions_layout.addWidget(button_row(copy_range_button, copy_button))
        region_actions_layout.addWidget(button_row(edit_button, delete_button))
        layout.addWidget(region_actions_group)

        detections_group, detections_layout = group(
            "Detections",
            "Detections on the active working frame. Right-click a bbox on the viewer for single-bbox actions.",
        )
        self.detection_list = QListWidget(panel)
        self.detection_list.setObjectName("moltrack-detection-list")
        self.detection_list.setToolTip(
            "Detection list for the active frame. Select an item to highlight it; right-click the bbox on the image for single-bbox actions."
        )
        self.detection_list.currentItemChanged.connect(self._on_detection_list_current_item_changed)
        detections_layout.addWidget(self.detection_list, 1)
        layout.addWidget(detections_group)

        self.draw_manual_detection_button = QPushButton("Draw BBox", panel)
        self.draw_manual_detection_button.setObjectName("moltrack-draw-manual-detection-button")
        self.draw_manual_detection_button.setToolTip("Start drawing a manual molecular bbox on the active frame.")
        self.draw_manual_detection_button.clicked.connect(self._on_draw_manual_detection_bbox)

        self.commit_manual_detection_button = QPushButton("Commit Manual", panel)
        self.commit_manual_detection_button.setObjectName("moltrack-commit-manual-detection-button")
        self.commit_manual_detection_button.setToolTip("Save the drawn bbox as a manual detection on the active frame.")
        self.commit_manual_detection_button.clicked.connect(self._on_commit_manual_detection_bbox)
        manual_group, manual_layout = group(
            "Manual Detection",
            "Create one manual bbox on the active working frame.",
        )
        manual_layout.addWidget(button_row(self.draw_manual_detection_button, self.commit_manual_detection_button))
        layout.addWidget(manual_group)

        review_group, review_layout = group(
            "Review Current Frame",
            "Bulk review operations for detections on the active working frame.",
        )
        self.accept_all_current_frame_button = QPushButton("Accept Current", panel)
        self.accept_all_current_frame_button.setObjectName("moltrack-accept-all-current-frame-button")
        self.accept_all_current_frame_button.setToolTip("Mark every detection on the active frame as accepted.")
        self.accept_all_current_frame_button.clicked.connect(self._on_accept_all_current_frame)

        self.accept_confidence_threshold_spin = QDoubleSpinBox(panel)
        self.accept_confidence_threshold_spin.setObjectName("moltrack-accept-confidence-threshold-spin")
        self.accept_confidence_threshold_spin.setRange(0.0, 1.0)
        self.accept_confidence_threshold_spin.setSingleStep(0.05)
        self.accept_confidence_threshold_spin.setDecimals(2)
        self.accept_confidence_threshold_spin.setValue(0.80)
        self.accept_confidence_threshold_spin.setPrefix("Conf >= ")
        self.accept_confidence_threshold_spin.setToolTip("Confidence threshold used by Accept Above Conf.")

        self.accept_above_confidence_button = QPushButton("Accept Above Conf", panel)
        self.accept_above_confidence_button.setObjectName("moltrack-accept-above-confidence-button")
        self.accept_above_confidence_button.setToolTip("Mark active-frame detections above the confidence threshold as accepted.")
        self.accept_above_confidence_button.clicked.connect(self._on_accept_above_confidence)
        review_layout.addWidget(self.accept_all_current_frame_button)
        review_layout.addWidget(self.accept_confidence_threshold_spin)
        review_layout.addWidget(self.accept_above_confidence_button)
        layout.addWidget(review_group)

        delete_group, delete_layout = group(
            "Delete Current Frame",
            "Bulk deletion operations. Single bbox deletion is in the right-click bbox menu.",
        )
        self.delete_status_combo = QComboBox(panel)
        self.delete_status_combo.setObjectName("moltrack-delete-status-combo")
        for status in DetectionReviewStatus:
            self.delete_status_combo.addItem(status.value, status.value)
        self.delete_status_combo.setToolTip("Status removed by Delete Status on the active frame.")
        delete_layout.addWidget(self.delete_status_combo)

        self.delete_current_status_button = QPushButton("Delete Status", panel)
        self.delete_current_status_button.setObjectName("moltrack-delete-current-status-button")
        self.delete_current_status_button.setToolTip("Delete active-frame detections whose status matches the selected status.")
        self.delete_current_status_button.clicked.connect(self._on_delete_current_status)

        self.delete_inside_selected_region_button = QPushButton("Delete in Region", panel)
        self.delete_inside_selected_region_button.setObjectName("moltrack-delete-inside-selected-region-button")
        self.delete_inside_selected_region_button.setToolTip("Delete active-frame detections whose bbox centroid lies inside the selected region.")
        self.delete_inside_selected_region_button.clicked.connect(self._on_delete_inside_selected_region)
        delete_layout.addWidget(button_row(self.delete_current_status_button, self.delete_inside_selected_region_button))
        layout.addWidget(delete_group)

        scale_group, scale_layout = group(
            "Scale BBoxes",
            "Bulk bbox scaling. Single bbox scaling is in the right-click bbox menu.",
        )
        self.scale_bbox_factor_spin = QDoubleSpinBox(panel)
        self.scale_bbox_factor_spin.setObjectName("moltrack-scale-bbox-factor-spin")
        self.scale_bbox_factor_spin.setRange(0.05, 10.0)
        self.scale_bbox_factor_spin.setSingleStep(0.05)
        self.scale_bbox_factor_spin.setDecimals(3)
        self.scale_bbox_factor_spin.setValue(1.0)
        self.scale_bbox_factor_spin.setPrefix("Scale x ")
        self.scale_bbox_factor_spin.setToolTip("Scale factor for current-frame and all-frame bbox scaling.")
        scale_layout.addWidget(self.scale_bbox_factor_spin)

        self.scale_current_frame_bboxes_button = QPushButton("Scale Current", panel)
        self.scale_current_frame_bboxes_button.setObjectName("moltrack-scale-current-frame-bboxes-button")
        self.scale_current_frame_bboxes_button.setToolTip("Scale every bbox on the active working frame around its own center.")
        self.scale_current_frame_bboxes_button.clicked.connect(self._on_scale_current_frame_bboxes)

        self.scale_all_bboxes_button = QPushButton("Scale All", panel)
        self.scale_all_bboxes_button.setObjectName("moltrack-scale-all-bboxes-button")
        self.scale_all_bboxes_button.setToolTip("Scale every bbox in the whole working series around its own center.")
        self.scale_all_bboxes_button.clicked.connect(self._on_scale_all_bboxes)
        scale_layout.addWidget(button_row(self.scale_current_frame_bboxes_button, self.scale_all_bboxes_button))
        layout.addWidget(scale_group)

        layout.addStretch(1)
        scroll.setWidget(panel)
        return scroll

    def set_project(self, project: MolTrackProject) -> None:
        self._project = project
        self._clear_expanded_aligned_cache()
        self._set_show_expanded_aligned(False)
        self.clear_drawn_region_roi()
        self.clear_manual_detection_bbox()
        self._clear_analysis_region_overlays()
        self._clear_molecular_detection_overlays()
        self._selected_molecular_detection_id = None
        self._analysis_regions = {region.name: region for region in project.analysis_regions}
        self._copied_analysis_regions = {
            copied_region.region.name: copied_region
            for copied_region in project.copied_analysis_regions
        }
        self._frame_scoped_analysis_regions = list(project.frame_scoped_analysis_regions)
        for scoped_region in self._frame_scoped_analysis_regions:
            self._analysis_regions.setdefault(scoped_region.region.name, scoped_region.region)
        frame_count = project.working_series.frame_count
        self.frame_slider.setEnabled(frame_count > 1)
        self.frame_slider.setRange(0, frame_count - 1)
        self.set_active_working_frame_index(0)
        self._refresh_region_list()

    def set_active_working_frame_index(self, working_frame_index: int) -> None:
        if self._project is None:
            return
        working_frame_index = int(working_frame_index)
        working_frame = self._project.working_series.get_working_frame(working_frame_index)

        self._active_working_frame_index = working_frame_index
        if self.frame_slider.value() != working_frame_index:
            self.frame_slider.setValue(working_frame_index)

        if self._project.source_series.raw_frames is None:
            self._displayed_frame = None
            self.viewer.clear()
            suffix = " | Images not loaded"
        else:
            frame = self._display_frame_for_working_frame(working_frame_index)
            self._displayed_frame = np.asarray(frame)
            self.viewer.set_image(
                self._displayed_frame,
                scale_nm_per_px=(None, None),
                preserve_zoom=True,
                auto_levels=True,
            )
            suffix = ""
        self.lbl_frame_index.setText(
            f"Working {working_frame_index + 1}/{self._project.working_series.frame_count} | "
            f"Source {working_frame.source_frame_index + 1}/{self._project.source_series.frame_count}"
            f"{suffix}"
            f"{self._registration_shift_label_suffix(working_frame_index)}"
            f"{self._registered_view_label_suffix()}"
        )
        self._redraw_analysis_region_overlays()
        self._refresh_detection_list()
        self._redraw_molecular_detection_overlays()

    def active_working_frame_index(self) -> int:
        return self._active_working_frame_index

    def active_source_frame_index(self) -> int:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        return self._project.working_series.get_source_frame_index(self._active_working_frame_index)

    def displayed_frame(self) -> np.ndarray:
        if self._displayed_frame is None:
            raise ValueError("No frame is displayed.")
        return self._displayed_frame

    def frame_index_text(self) -> str:
        return self.lbl_frame_index.text()

    def add_analysis_region(self, region: AnalysisRegion) -> None:
        if region.name in self._analysis_regions:
            raise ValueError(f"Analysis region already exists: {region.name}")
        self._analysis_regions[region.name] = region
        self._draw_analysis_region(region)
        self._sync_project_analysis_regions()
        self._refresh_region_list(region.name)

    def update_analysis_region(self, region_name: str, region: AnalysisRegion) -> None:
        region_name = str(region_name)
        if region_name not in self._analysis_regions:
            raise KeyError(f"Unknown analysis region: {region_name}")
        if region.name != region_name and region.name in self._analysis_regions:
            raise ValueError(f"Analysis region already exists: {region.name}")
        self._remove_analysis_region_overlay(region_name)
        del self._analysis_regions[region_name]
        self._analysis_regions[region.name] = region
        copied_region = self._copied_analysis_regions.pop(region_name, None)
        if copied_region is not None:
            self._copied_analysis_regions[region.name] = CopiedAnalysisRegion(
                region=region,
                working_frame_indices=copied_region.working_frame_indices,
            )
        self._frame_scoped_analysis_regions = [
            FrameScopedAnalysisRegion(
                region=(
                    AnalysisRegion(
                        kind=region.kind,
                        name=region.name,
                        color_rgb=region.color_rgb,
                        rect_xyxy=scoped_region.region.rect_xyxy,
                        polygon_xy=scoped_region.region.polygon_xy,
                        coordinate_system=scoped_region.region.coordinate_system,
                    )
                    if scoped_region.region.name == region_name
                    else scoped_region.region
                ),
                working_frame_indices=scoped_region.working_frame_indices,
            )
            for scoped_region in self._frame_scoped_analysis_regions
        ]
        self._draw_analysis_region(region)
        self._sync_project_analysis_regions()
        self._refresh_region_list(region.name)

    def remove_analysis_region(self, region_name: str) -> AnalysisRegion:
        region_name = str(region_name)
        if region_name not in self._analysis_regions:
            raise KeyError(f"Unknown analysis region: {region_name}")
        self._remove_analysis_region_overlay(region_name)
        self._copied_analysis_regions.pop(region_name, None)
        self._frame_scoped_analysis_regions = [
            scoped_region
            for scoped_region in self._frame_scoped_analysis_regions
            if scoped_region.region.name != region_name
        ]
        removed = self._analysis_regions.pop(region_name)
        self._sync_project_analysis_regions()
        self._refresh_region_list()
        return removed

    def analysis_regions(self) -> list[AnalysisRegion]:
        return list(self._analysis_regions.values())

    def copy_analysis_region_to_series(self, region_name: str) -> CopiedAnalysisRegion | None:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        region_name = str(region_name)
        if region_name not in self._analysis_regions:
            raise KeyError(f"Unknown analysis region: {region_name}")
        if self._expanded_region_mode_is_fixed_canvas():
            frame_indices = tuple(frame.working_frame_index for frame in self._project.working_series.frames)
            self._copy_active_expanded_canvas_region_to_frames(region_name, frame_indices)
            return None
        copied_region = CopiedAnalysisRegion.from_working_series(
            self._analysis_regions[region_name],
            self._project.working_series,
        )
        self._copied_analysis_regions[region_name] = copied_region
        self._sync_project_analysis_regions()
        return copied_region

    def copied_analysis_regions(self) -> list[CopiedAnalysisRegion]:
        return list(self._copied_analysis_regions.values())

    def frame_scoped_analysis_regions(self) -> list[FrameScopedAnalysisRegion]:
        return list(self._frame_scoped_analysis_regions)

    def molecular_detections(self) -> list[MolecularDetection]:
        if self._project is None:
            return []
        return list(self._project.molecular_detections)

    def set_molecular_detection_status(
        self,
        detection_ids,
        status: DetectionReviewStatus | str,
    ) -> tuple[MolecularDetection, ...]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        target_ids = {str(detection_id) for detection_id in detection_ids}
        if not target_ids:
            return tuple()
        review_status = (
            status
            if isinstance(status, DetectionReviewStatus)
            else DetectionReviewStatus(str(status).strip())
        )
        updated_detections = []
        changed_detections = []
        for detection in self._project.molecular_detections:
            if detection.detection_id in target_ids:
                updated_detection = replace(detection, review_status=review_status)
                updated_detections.append(updated_detection)
                changed_detections.append(updated_detection)
            else:
                updated_detections.append(detection)
        changed_ids = {detection.detection_id for detection in changed_detections}
        missing_ids = target_ids - changed_ids
        if missing_ids:
            raise KeyError(f"Unknown molecular detection id: {sorted(missing_ids)[0]}")
        self._project = self._project.with_molecular_detections(tuple(updated_detections))
        self._refresh_detection_list(self._selected_molecular_detection_id)
        self._redraw_molecular_detection_overlays()
        return tuple(changed_detections)

    def set_selected_molecular_detection_status(
        self,
        status: DetectionReviewStatus | str,
    ) -> MolecularDetection:
        if self._selected_molecular_detection_id is None:
            raise ValueError("Select a molecular detection first.")
        return self.set_molecular_detection_status((self._selected_molecular_detection_id,), status)[0]

    def set_current_frame_molecular_detection_status(
        self,
        status: DetectionReviewStatus | str,
    ) -> tuple[MolecularDetection, ...]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        detection_ids = [
            detection.detection_id
            for detection in self._project.molecular_detections_for_working_frame(self._active_working_frame_index)
        ]
        return self.set_molecular_detection_status(detection_ids, status)

    def set_current_frame_molecular_detection_status_above_confidence(
        self,
        threshold: float,
        status: DetectionReviewStatus | str,
    ) -> tuple[MolecularDetection, ...]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        threshold = float(threshold)
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("threshold must be in [0, 1].")
        detection_ids = [
            detection.detection_id
            for detection in self._project.molecular_detections_for_working_frame(self._active_working_frame_index)
            if detection.confidence >= threshold
        ]
        return self.set_molecular_detection_status(detection_ids, status)

    def add_manual_detection_bbox(
        self,
        bbox_xyxy,
        *,
        select: bool = True,
    ) -> MolecularDetection:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        working_frame = self._project.working_series.get_working_frame(self._active_working_frame_index)
        bbox_xyxy = _sorted_rect_xyxy(bbox_xyxy)
        used_detection_ids = {detection.detection_id for detection in self._project.molecular_detections}
        detection_id = _unique_detection_id(
            f"manual-w{working_frame.working_frame_index:04d}-0000",
            used_detection_ids,
        )
        detection = MolecularDetection(
            detection_id=detection_id,
            working_frame_index=working_frame.working_frame_index,
            source_frame_index=working_frame.source_frame_index,
            bbox_xyxy=bbox_xyxy,
            confidence=1.0,
            model_name="manual",
            review_status=DetectionReviewStatus.MANUAL,
            backend_name="manual",
            run_mode="full_frame",
        )
        self._project = self._project.with_molecular_detections(
            tuple(self._project.molecular_detections + (detection,))
        )
        if select:
            self._selected_molecular_detection_id = detection.detection_id
        self._refresh_detection_list(detection.detection_id if select else None)
        self._redraw_molecular_detection_overlays()
        return detection

    def edit_molecular_detection_bbox(
        self,
        detection_id: str,
        bbox_xyxy,
    ) -> MolecularDetection:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        target_id = str(detection_id)
        bbox_xyxy = _sorted_rect_xyxy(bbox_xyxy)
        updated_detections = []
        updated_detection = None
        for detection in self._project.molecular_detections:
            if detection.detection_id == target_id:
                updated_status = _review_status_after_bbox_edit(detection.review_status)
                updated_detection = replace(
                    detection,
                    bbox_xyxy=bbox_xyxy,
                    review_status=updated_status,
                )
                updated_detections.append(updated_detection)
            else:
                updated_detections.append(detection)
        if updated_detection is None:
            raise KeyError(f"Unknown molecular detection id: {target_id}")
        self._project = self._project.with_molecular_detections(tuple(updated_detections))
        self._selected_molecular_detection_id = updated_detection.detection_id
        self._refresh_detection_list(updated_detection.detection_id)
        self._redraw_molecular_detection_overlays()
        return updated_detection

    def remove_molecular_detections(self, detection_ids) -> tuple[MolecularDetection, ...]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        target_ids = {str(detection_id) for detection_id in detection_ids}
        if not target_ids:
            return tuple()
        removed_detections = tuple(
            detection
            for detection in self._project.molecular_detections
            if detection.detection_id in target_ids
        )
        removed_ids = {detection.detection_id for detection in removed_detections}
        missing_ids = target_ids - removed_ids
        if missing_ids:
            raise KeyError(f"Unknown molecular detection id: {sorted(missing_ids)[0]}")
        remaining_detections = tuple(
            detection
            for detection in self._project.molecular_detections
            if detection.detection_id not in target_ids
        )
        self._project = self._project.with_molecular_detections(remaining_detections)
        if self._selected_molecular_detection_id in target_ids:
            self._selected_molecular_detection_id = None
        self._refresh_detection_list()
        self._redraw_molecular_detection_overlays()
        return removed_detections

    def remove_selected_molecular_detection(self) -> MolecularDetection:
        if self._selected_molecular_detection_id is None:
            raise ValueError("Select a molecular detection first.")
        return self.remove_molecular_detections((self._selected_molecular_detection_id,))[0]

    def remove_current_frame_molecular_detections_by_status(
        self,
        status: DetectionReviewStatus | str,
    ) -> tuple[MolecularDetection, ...]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        review_status = (
            status
            if isinstance(status, DetectionReviewStatus)
            else DetectionReviewStatus(str(status).strip())
        )
        detection_ids = [
            detection.detection_id
            for detection in self._project.molecular_detections_for_working_frame(self._active_working_frame_index)
            if detection.review_status == review_status
        ]
        return self.remove_molecular_detections(detection_ids)

    def remove_current_frame_molecular_detections_inside_region(
        self,
        region_name: str,
    ) -> tuple[MolecularDetection, ...]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        active_region = self._project.region_for_working_frame(
            str(region_name),
            self._active_working_frame_index,
        )
        detection_ids = [
            detection.detection_id
            for detection in self._project.molecular_detections_for_working_frame(self._active_working_frame_index)
            if _point_inside_analysis_region(active_region, detection.centroid_xy)
        ]
        return self.remove_molecular_detections(detection_ids)

    def scale_molecular_detection_bboxes(
        self,
        detection_ids,
        scale_factor: float,
    ) -> tuple[MolecularDetection, ...]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        target_ids = {str(detection_id) for detection_id in detection_ids}
        if not target_ids:
            return tuple()
        scale_factor = _valid_bbox_scale_factor(scale_factor)
        updated_detections = []
        changed_detections = []
        for detection in self._project.molecular_detections:
            if detection.detection_id in target_ids:
                updated_detection = replace(
                    detection,
                    bbox_xyxy=_scale_bbox_xyxy(detection.bbox_xyxy, scale_factor),
                    review_status=_review_status_after_bbox_edit(detection.review_status),
                )
                updated_detections.append(updated_detection)
                changed_detections.append(updated_detection)
            else:
                updated_detections.append(detection)
        changed_ids = {detection.detection_id for detection in changed_detections}
        missing_ids = target_ids - changed_ids
        if missing_ids:
            raise KeyError(f"Unknown molecular detection id: {sorted(missing_ids)[0]}")
        self._project = self._project.with_molecular_detections(tuple(updated_detections))
        self._refresh_detection_list(self._selected_molecular_detection_id)
        self._redraw_molecular_detection_overlays()
        return tuple(changed_detections)

    def scale_selected_molecular_detection_bbox(self, scale_factor: float) -> MolecularDetection:
        if self._selected_molecular_detection_id is None:
            raise ValueError("Select a molecular detection first.")
        return self.scale_molecular_detection_bboxes((self._selected_molecular_detection_id,), scale_factor)[0]

    def scale_current_frame_molecular_detection_bboxes(
        self,
        scale_factor: float,
    ) -> tuple[MolecularDetection, ...]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        detection_ids = [
            detection.detection_id
            for detection in self._project.molecular_detections_for_working_frame(self._active_working_frame_index)
        ]
        return self.scale_molecular_detection_bboxes(detection_ids, scale_factor)

    def scale_all_molecular_detection_bboxes(
        self,
        scale_factor: float,
    ) -> tuple[MolecularDetection, ...]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        detection_ids = [detection.detection_id for detection in self._project.molecular_detections]
        return self.scale_molecular_detection_bboxes(detection_ids, scale_factor)

    def refresh_yolo_models(self, models: list[MolTrackYoloModelInfo] | None = None) -> None:
        current_path = self._selected_yolo_model_path
        self._yolo_models = list(discover_moltrack_yolo_models() if models is None else models)
        if current_path is not None and any(model.path == current_path for model in self._yolo_models):
            self._selected_yolo_model_path = current_path
        elif self._yolo_models:
            self._selected_yolo_model_path = self._yolo_models[0].path
        else:
            self._selected_yolo_model_path = None

    def selected_yolo_model(self) -> MolTrackYoloModelInfo | None:
        if self._selected_yolo_model_path is not None:
            for model in self._yolo_models:
                if model.path == self._selected_yolo_model_path:
                    return model
        return self._yolo_models[0] if self._yolo_models else None

    def selected_yolo_detection_config(self) -> MolTrackYoloDetectionConfig:
        return self._yolo_detection_config

    def _request_yolo_detection_options(
        self,
        *,
        title: str = "YOLO Detection Options",
    ) -> tuple[MolTrackYoloModelInfo, MolTrackYoloDetectionConfig] | None:
        if not self._yolo_models:
            self.refresh_yolo_models()
        options = YoloDetectionOptionsDialog.get_options(
            self,
            title=title,
            models=self._yolo_models,
            selected_model_path=self._selected_yolo_model_path,
            config=self._yolo_detection_config,
        )
        if options is None:
            return None
        model, config = options
        self._selected_yolo_model_path = model.path
        self._yolo_detection_config = config
        if all(existing.path != model.path for existing in self._yolo_models):
            self._yolo_models.append(model)
        return model, config

    def detect_yolo_on_current_frame(
        self,
        model: MolTrackYoloModelInfo,
        *,
        config: MolTrackYoloDetectionConfig | None = None,
        runtime=None,
    ) -> tuple[MolecularDetection, ...]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        if self._project.source_series.raw_frames is None:
            raise ValueError("YOLO detection requires loaded source image frames.")
        config = config or MolTrackYoloDetectionConfig()
        runtime = runtime or YoloRuntime(config.to_nanotrack_runtime_config())
        working_frame = self._project.working_series.get_working_frame(self._active_working_frame_index)
        frame = self._project.source_series.get_frame(working_frame.source_frame_index)
        runtime_detections = runtime.predict_frame(
            frame,
            model_path=model.path,
            conf_threshold=config.confidence_threshold,
            iou_threshold=config.iou_threshold,
            device=config.device,
        )
        preserved_detections = [
            detection
            for detection in self._project.molecular_detections
            if not (
                detection.working_frame_index == working_frame.working_frame_index
                and detection.backend_name == "yolo"
                and detection.review_status == DetectionReviewStatus.CANDIDATE
            )
        ]
        used_detection_ids = {detection.detection_id for detection in preserved_detections}
        new_detections = []
        for detection_index, runtime_detection in enumerate(runtime_detections):
            detection_id = _unique_detection_id(
                f"yolo-w{working_frame.working_frame_index:04d}-{detection_index:04d}",
                used_detection_ids,
            )
            used_detection_ids.add(detection_id)
            model_name = str(getattr(runtime_detection, "model_name", model.name)).strip() or model.name
            new_detections.append(
                MolecularDetection(
                    detection_id=detection_id,
                    working_frame_index=working_frame.working_frame_index,
                    source_frame_index=working_frame.source_frame_index,
                    bbox_xyxy=_runtime_bbox_xyxy(runtime_detection.bbox),
                    confidence=float(runtime_detection.confidence),
                    model_name=model_name,
                    review_status=DetectionReviewStatus.default_for_yolo(),
                    backend_name="yolo",
                    run_mode="full_frame",
                )
            )
        self._project = self._project.with_molecular_detections(
            tuple(preserved_detections + new_detections)
        )
        self._refresh_detection_list()
        self._redraw_molecular_detection_overlays()
        return tuple(new_detections)

    def detect_yolo_on_current_frame_in_region(
        self,
        region_name: str,
        model: MolTrackYoloModelInfo,
        *,
        config: MolTrackYoloDetectionConfig | None = None,
        runtime=None,
    ) -> tuple[MolecularDetection, ...]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        if self._project.source_series.raw_frames is None:
            raise ValueError("YOLO detection requires loaded source image frames.")
        config = config or MolTrackYoloDetectionConfig()
        runtime = runtime or YoloRuntime(config.to_nanotrack_runtime_config())
        working_frame = self._project.working_series.get_working_frame(self._active_working_frame_index)
        active_region = self._project.region_for_working_frame(
            str(region_name),
            working_frame.working_frame_index,
        )
        frame = self._project.source_series.get_frame(working_frame.source_frame_index)
        runtime_detections = runtime.predict_frame(
            frame,
            model_path=model.path,
            conf_threshold=config.confidence_threshold,
            iou_threshold=config.iou_threshold,
            device=config.device,
        )
        preserved_detections = [
            detection
            for detection in self._project.molecular_detections
            if not (
                detection.working_frame_index == working_frame.working_frame_index
                and _point_inside_analysis_region(active_region, detection.centroid_xy)
            )
        ]
        used_detection_ids = {detection.detection_id for detection in preserved_detections}
        new_detections = []
        for detection_index, runtime_detection in enumerate(runtime_detections):
            bbox_xyxy = _runtime_bbox_xyxy(runtime_detection.bbox)
            if not _point_inside_analysis_region(active_region, _bbox_centroid_xy(bbox_xyxy)):
                continue
            detection_id = _unique_detection_id(
                f"yolo-roi-w{working_frame.working_frame_index:04d}-{detection_index:04d}",
                used_detection_ids,
            )
            used_detection_ids.add(detection_id)
            model_name = str(getattr(runtime_detection, "model_name", model.name)).strip() or model.name
            new_detections.append(
                MolecularDetection(
                    detection_id=detection_id,
                    working_frame_index=working_frame.working_frame_index,
                    source_frame_index=working_frame.source_frame_index,
                    bbox_xyxy=bbox_xyxy,
                    confidence=float(runtime_detection.confidence),
                    model_name=model_name,
                    review_status=DetectionReviewStatus.default_for_yolo(),
                    backend_name="yolo",
                    run_mode="roi_replace",
                    region_name=active_region.name,
                )
            )
        self._project = self._project.with_molecular_detections(
            tuple(preserved_detections + new_detections)
        )
        self._refresh_detection_list()
        self._redraw_molecular_detection_overlays()
        return tuple(new_detections)

    def detect_yolo_on_all_working_frames(
        self,
        model: MolTrackYoloModelInfo,
        *,
        config: MolTrackYoloDetectionConfig | None = None,
        runtime=None,
        progress_callback=None,
        cancel_check=None,
    ) -> dict[int, tuple[MolecularDetection, ...]]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        if self._project.source_series.raw_frames is None:
            raise ValueError("YOLO detection requires loaded source image frames.")
        config = config or MolTrackYoloDetectionConfig()
        runtime = runtime or YoloRuntime(config.to_nanotrack_runtime_config())
        working_frames = tuple(self._project.working_series.frames)
        total = len(working_frames)
        detections_by_frame: dict[int, tuple[MolecularDetection, ...]] = {}
        new_detections: list[MolecularDetection] = []
        used_detection_ids = {detection.detection_id for detection in self._project.molecular_detections}

        for completed, working_frame in enumerate(working_frames):
            if cancel_check is not None and cancel_check():
                break
            frame = self._project.source_series.get_frame(working_frame.source_frame_index)
            runtime_detections = runtime.predict_frame(
                frame,
                model_path=model.path,
                conf_threshold=config.confidence_threshold,
                iou_threshold=config.iou_threshold,
                device=config.device,
            )
            frame_detections = []
            for detection_index, runtime_detection in enumerate(runtime_detections):
                detection_id = _unique_detection_id(
                    f"yolo-w{working_frame.working_frame_index:04d}-{detection_index:04d}",
                    used_detection_ids,
                )
                used_detection_ids.add(detection_id)
                model_name = str(getattr(runtime_detection, "model_name", model.name)).strip() or model.name
                frame_detections.append(
                    MolecularDetection(
                        detection_id=detection_id,
                        working_frame_index=working_frame.working_frame_index,
                        source_frame_index=working_frame.source_frame_index,
                        bbox_xyxy=_runtime_bbox_xyxy(runtime_detection.bbox),
                        confidence=float(runtime_detection.confidence),
                        model_name=model_name,
                        review_status=DetectionReviewStatus.default_for_yolo(),
                        backend_name="yolo",
                        run_mode="full_frame",
                    )
                )
            detections_by_frame[working_frame.working_frame_index] = tuple(frame_detections)
            new_detections.extend(frame_detections)
            if progress_callback is not None:
                progress_callback(completed + 1, total, working_frame.working_frame_index)

        processed_frame_indices = set(detections_by_frame)
        preserved_detections = [
            detection
            for detection in self._project.molecular_detections
            if not (
                detection.working_frame_index in processed_frame_indices
                and detection.backend_name == "yolo"
                and detection.review_status == DetectionReviewStatus.CANDIDATE
            )
        ]
        self._project = self._project.with_molecular_detections(
            tuple(preserved_detections + new_detections)
        )
        self._refresh_detection_list()
        self._redraw_molecular_detection_overlays()
        return detections_by_frame

    def detect_yolo_in_region_on_working_frames(
        self,
        region_name: str,
        model: MolTrackYoloModelInfo,
        *,
        working_frame_indices=None,
        config: MolTrackYoloDetectionConfig | None = None,
        runtime=None,
        progress_callback=None,
        cancel_check=None,
    ) -> dict[int, tuple[MolecularDetection, ...]]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        if self._project.source_series.raw_frames is None:
            raise ValueError("YOLO detection requires loaded source image frames.")
        config = config or MolTrackYoloDetectionConfig()
        runtime = runtime or YoloRuntime(config.to_nanotrack_runtime_config())
        region_name = str(region_name)
        if working_frame_indices is None:
            working_frames = tuple(self._project.working_series.frames)
        else:
            unique_indices = tuple(dict.fromkeys(int(index) for index in working_frame_indices))
            working_frames = tuple(
                self._project.working_series.get_working_frame(index)
                for index in unique_indices
            )
        total = len(working_frames)
        detections_by_frame: dict[int, tuple[MolecularDetection, ...]] = {}
        regions_by_frame: dict[int, AnalysisRegion] = {}
        new_detections: list[MolecularDetection] = []
        used_detection_ids = {detection.detection_id for detection in self._project.molecular_detections}

        for completed, working_frame in enumerate(working_frames):
            if cancel_check is not None and cancel_check():
                break
            active_region = self._project.region_for_working_frame(
                region_name,
                working_frame.working_frame_index,
            )
            regions_by_frame[working_frame.working_frame_index] = active_region
            frame = self._project.source_series.get_frame(working_frame.source_frame_index)
            runtime_detections = runtime.predict_frame(
                frame,
                model_path=model.path,
                conf_threshold=config.confidence_threshold,
                iou_threshold=config.iou_threshold,
                device=config.device,
            )
            frame_detections = []
            for detection_index, runtime_detection in enumerate(runtime_detections):
                bbox_xyxy = _runtime_bbox_xyxy(runtime_detection.bbox)
                if not _point_inside_analysis_region(active_region, _bbox_centroid_xy(bbox_xyxy)):
                    continue
                detection_id = _unique_detection_id(
                    f"yolo-roi-w{working_frame.working_frame_index:04d}-{detection_index:04d}",
                    used_detection_ids,
                )
                used_detection_ids.add(detection_id)
                model_name = str(getattr(runtime_detection, "model_name", model.name)).strip() or model.name
                frame_detections.append(
                    MolecularDetection(
                        detection_id=detection_id,
                        working_frame_index=working_frame.working_frame_index,
                        source_frame_index=working_frame.source_frame_index,
                        bbox_xyxy=bbox_xyxy,
                        confidence=float(runtime_detection.confidence),
                        model_name=model_name,
                        review_status=DetectionReviewStatus.default_for_yolo(),
                        backend_name="yolo",
                        run_mode="roi_replace",
                        region_name=active_region.name,
                    )
                )
            detections_by_frame[working_frame.working_frame_index] = tuple(frame_detections)
            new_detections.extend(frame_detections)
            if progress_callback is not None:
                progress_callback(completed + 1, total, working_frame.working_frame_index)

        processed_frame_indices = set(detections_by_frame)
        preserved_detections = [
            detection
            for detection in self._project.molecular_detections
            if not (
                detection.working_frame_index in processed_frame_indices
                and _point_inside_analysis_region(
                    regions_by_frame[detection.working_frame_index],
                    detection.centroid_xy,
                )
            )
        ]
        self._project = self._project.with_molecular_detections(
            tuple(preserved_detections + new_detections)
        )
        self._refresh_detection_list()
        self._redraw_molecular_detection_overlays()
        return detections_by_frame

    def apply_analysis_region_to_frames(
        self,
        region_name: str,
        working_frame_indices,
        *,
        region: AnalysisRegion | None = None,
    ) -> FrameScopedAnalysisRegion:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        region_name = str(region_name)
        if region is None:
            if region_name not in self._analysis_regions:
                raise KeyError(f"Unknown analysis region: {region_name}")
            region = self._analysis_regions[region_name]
        elif region.name != region_name:
            raise ValueError("Frame-scoped region name must match the logical region name.")
        elif region_name not in self._analysis_regions:
            self._analysis_regions[region_name] = region

        scoped_region = FrameScopedAnalysisRegion(
            region=region,
            working_frame_indices=tuple(int(index) for index in working_frame_indices),
        )
        new_indices = set(scoped_region.working_frame_indices)
        self._frame_scoped_analysis_regions = [
            existing
            for existing in self._frame_scoped_analysis_regions
            if existing.region.name != region_name or set(existing.working_frame_indices).isdisjoint(new_indices)
        ]
        self._frame_scoped_analysis_regions.append(scoped_region)
        self._frame_scoped_analysis_regions.sort(
            key=lambda item: (item.region.name, item.working_frame_indices[0])
        )
        self._sync_project_analysis_regions()
        self._refresh_region_list(region_name)
        self._redraw_analysis_region_overlays()
        self._warn_if_terrace_regions_overlap()
        return scoped_region

    def _copy_active_expanded_canvas_region_to_frames(
        self,
        region_name: str,
        working_frame_indices,
    ) -> tuple[FrameScopedAnalysisRegion, ...]:
        active_region = self._active_analysis_region_by_name(region_name)
        display_region = self._region_to_expanded_canvas(active_region, self._active_working_frame_index)
        return self._apply_expanded_canvas_region_to_frames(display_region, working_frame_indices)

    def _apply_expanded_canvas_region_to_frames(
        self,
        expanded_canvas_region: AnalysisRegion,
        working_frame_indices,
    ) -> tuple[FrameScopedAnalysisRegion, ...]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        frame_indices = tuple(int(index) for index in working_frame_indices)
        if not frame_indices:
            raise ValueError("working_frame_indices must contain at least one frame.")
        for frame_index in frame_indices:
            self._project.working_series.get_working_frame(frame_index)
        region_name = expanded_canvas_region.name
        if region_name not in self._analysis_regions:
            active_native_region = self._region_from_expanded_canvas(
                expanded_canvas_region,
                self._active_working_frame_index,
            )
            self._analysis_regions[region_name] = active_native_region

        new_index_set = set(frame_indices)
        self._copied_analysis_regions.pop(region_name, None)
        self._frame_scoped_analysis_regions = [
            existing
            for existing in self._frame_scoped_analysis_regions
            if existing.region.name != region_name or set(existing.working_frame_indices).isdisjoint(new_index_set)
        ]
        scoped_regions = tuple(
            FrameScopedAnalysisRegion(
                region=self._region_from_expanded_canvas(expanded_canvas_region, frame_index),
                working_frame_indices=(frame_index,),
            )
            for frame_index in frame_indices
        )
        self._frame_scoped_analysis_regions.extend(scoped_regions)
        self._frame_scoped_analysis_regions.sort(
            key=lambda item: (item.region.name, item.working_frame_indices[0])
        )
        self._sync_project_analysis_regions()
        self._refresh_region_list(region_name)
        self._redraw_analysis_region_overlays()
        self._warn_if_terrace_regions_overlap()
        return scoped_regions

    def region_overlay_count(self) -> int:
        return len(self._analysis_region_items)

    def selected_region_name(self) -> str | None:
        item = self.region_list.currentItem()
        return item.text() if item is not None else None

    def active_region_roi_kind(self) -> str | None:
        return self._draft_region_roi_kind

    def start_rect_region_roi(self, rect_xyxy: tuple[float, float, float, float] | None = None) -> None:
        self.clear_drawn_region_roi()
        if rect_xyxy is None:
            rect_xyxy = self._default_rect_roi_xyxy()
        x0, y0, x1, y1 = _sorted_rect_xyxy(rect_xyxy)
        roi = pg.RectROI(
            [x0, y0],
            [x1 - x0, y1 - y0],
            pen=pg.mkPen((255, 200, 0), width=2),
            movable=True,
            resizable=True,
            rotatable=False,
        )
        roi.addScaleHandle((0, 0), (1, 1))
        roi.addScaleHandle((1, 1), (0, 0))
        roi.addScaleHandle((1, 0), (0, 1))
        roi.addScaleHandle((0, 1), (1, 0))
        self.viewer.get_plot_item().addItem(roi)
        self._draft_region_roi = roi
        self._draft_region_roi_kind = "rect"

    def start_manual_detection_bbox(self, rect_xyxy: tuple[float, float, float, float] | None = None) -> None:
        self.clear_manual_detection_bbox()
        self._editing_detection_id = None
        if rect_xyxy is None:
            rect_xyxy = self._default_rect_roi_xyxy()
        self._start_detection_bbox_roi(rect_xyxy)

    def start_selected_detection_bbox_edit(self) -> None:
        detection = self._selected_molecular_detection()
        self.clear_manual_detection_bbox()
        self._editing_detection_id = detection.detection_id
        self._start_detection_bbox_roi(self._bbox_from_native_to_current_view(detection.bbox_xyxy))

    def _start_detection_bbox_roi(self, rect_xyxy) -> None:
        x0, y0, x1, y1 = _sorted_rect_xyxy(rect_xyxy)
        roi = pg.RectROI(
            [x0, y0],
            [x1 - x0, y1 - y0],
            pen=pg.mkPen((0, 220, 255), width=2),
            movable=True,
            resizable=True,
            rotatable=False,
        )
        roi.addScaleHandle((0, 0), (1, 1))
        roi.addScaleHandle((1, 1), (0, 0))
        roi.addScaleHandle((1, 0), (0, 1))
        roi.addScaleHandle((0, 1), (1, 0))
        self.viewer.get_plot_item().addItem(roi)
        self._draft_detection_bbox_roi = roi

    def start_polyline_region_roi(self, vertices_xy=None) -> None:
        self.clear_drawn_region_roi()
        if vertices_xy is None:
            vertices_xy = self._default_polyline_vertices_xy()
        vertices = np.asarray(vertices_xy, dtype=np.float64)
        if vertices.ndim != 2 or vertices.shape[1] != 2 or len(vertices) < 3:
            raise ValueError("Polyline region requires at least three vertices.")
        roi = pg.PolyLineROI(
            [tuple(point) for point in vertices],
            closed=True,
            movable=True,
            pen=pg.mkPen((0, 220, 255), width=2),
        )
        self.viewer.get_plot_item().addItem(roi)
        self._draft_region_roi = roi
        self._draft_region_roi_kind = "polygon"

    def clear_drawn_region_roi(self) -> None:
        if self._draft_region_roi is not None:
            try:
                self.viewer.get_plot_item().removeItem(self._draft_region_roi)
            except Exception:
                pass
        self._draft_region_roi = None
        self._draft_region_roi_kind = None

    def clear_manual_detection_bbox(self) -> None:
        if self._draft_detection_bbox_roi is not None:
            try:
                self.viewer.get_plot_item().removeItem(self._draft_detection_bbox_roi)
            except Exception:
                pass
        self._draft_detection_bbox_roi = None
        self._editing_detection_id = None

    def select_analysis_region(self, region_name: str) -> None:
        matching_items = self.region_list.findItems(str(region_name), Qt.MatchFlag.MatchExactly)
        if not matching_items:
            raise KeyError(f"Unknown analysis region: {region_name}")
        self.region_list.setCurrentItem(matching_items[0])

    def _refresh_region_list(self, selected_region_name: str | None = None) -> None:
        current_name = selected_region_name or self.selected_region_name()
        self.region_list.clear()
        for region in self._analysis_regions.values():
            self.region_list.addItem(region.name)
        if current_name and current_name in self._analysis_regions:
            self.select_analysis_region(current_name)

    def _refresh_detection_list(self, selected_detection_id: str | None = None) -> None:
        if self._project is None:
            self._selected_molecular_detection_id = None
            self.detection_list.clear()
            return
        current_detection_id = selected_detection_id or self._selected_molecular_detection_id
        detections = self._project.molecular_detections_for_working_frame(self._active_working_frame_index)
        active_detection_ids = {detection.detection_id for detection in detections}
        if current_detection_id not in active_detection_ids:
            current_detection_id = None
        self._selected_molecular_detection_id = current_detection_id

        with QSignalBlocker(self.detection_list):
            self.detection_list.clear()
            selected_item = None
            for detection in detections:
                item = QListWidgetItem(_detection_list_label(detection))
                item.setData(Qt.ItemDataRole.UserRole, detection.detection_id)
                self.detection_list.addItem(item)
                if detection.detection_id == current_detection_id:
                    selected_item = item
            if selected_item is not None:
                self.detection_list.setCurrentItem(selected_item)

    def _on_detection_list_current_item_changed(self, current_item, _previous_item) -> None:
        self._selected_molecular_detection_id = (
            None
            if current_item is None
            else str(current_item.data(Qt.ItemDataRole.UserRole))
        )
        self._redraw_molecular_detection_overlays()

    def _on_viewer_scene_mouse_clicked(self, event) -> None:
        if self._project is None or event.button() != Qt.MouseButton.RightButton:
            return
        plot_item = self.viewer.get_plot_item()
        if not plot_item.sceneBoundingRect().contains(event.scenePos()):
            return
        view_pos = plot_item.getViewBox().mapSceneToView(event.scenePos())
        detection_id = self.detection_id_at_view_point(view_pos.x(), view_pos.y())
        if detection_id is None:
            return
        global_pos = (
            event.screenPos().toPoint()
            if hasattr(event, "screenPos")
            else self.viewer.mapToGlobal(self.viewer.rect().center())
        )
        self.show_detection_context_menu(detection_id, global_pos)
        event.accept()

    def _draw_analysis_region(self, region: AnalysisRegion) -> None:
        item = self.viewer.add_polyline_nm(
            self._analysis_region_display_polyline(region),
            name=region.name,
            color=region.color_rgb,
            width=2.0,
        )
        self._analysis_region_items[region.name] = item

    def _analysis_region_display_polyline(self, region: AnalysisRegion) -> np.ndarray:
        polyline = _analysis_region_polyline(region)
        if self._project is None or not self._show_expanded_aligned_view:
            return polyline
        expanded = self._ensure_expanded_aligned_stack()
        if not 0 <= self._active_working_frame_index < expanded.frame_origins_xy.shape[0]:
            return polyline
        origin_xy = expanded.frame_origins_xy[self._active_working_frame_index]
        return polyline + np.asarray(origin_xy, dtype=np.float64)

    def _active_analysis_region_by_name(self, region_name: str) -> AnalysisRegion:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        return self._project.region_for_working_frame(str(region_name), self._active_working_frame_index)

    def _region_from_current_view_to_native(self, region: AnalysisRegion) -> AnalysisRegion:
        if not self._show_expanded_aligned_view:
            return region
        return self._region_from_expanded_canvas(region, self._active_working_frame_index)

    def _region_from_expanded_canvas(
        self,
        region: AnalysisRegion,
        working_frame_index: int,
    ) -> AnalysisRegion:
        origin = self._expanded_frame_origin_xy(working_frame_index)
        return _translated_analysis_region(region, -origin)

    def _region_to_expanded_canvas(
        self,
        region: AnalysisRegion,
        working_frame_index: int,
    ) -> AnalysisRegion:
        origin = self._expanded_frame_origin_xy(working_frame_index)
        return _translated_analysis_region(region, origin)

    def _expanded_frame_origin_xy(self, working_frame_index: int) -> np.ndarray:
        expanded = self._ensure_expanded_aligned_stack()
        frame_index = int(working_frame_index)
        if not 0 <= frame_index < expanded.frame_origins_xy.shape[0]:
            raise IndexError("working_frame_index is out of range for expanded aligned stack.")
        return np.asarray(expanded.frame_origins_xy[frame_index], dtype=np.float64)

    def _remove_analysis_region_overlay(self, region_name: str) -> None:
        item = self._analysis_region_items.pop(region_name, None)
        if item is not None:
            self.viewer.remove_item(item)

    def _clear_analysis_region_overlays(self) -> None:
        for item in self._analysis_region_items.values():
            self.viewer.remove_item(item)
        self._analysis_region_items = {}

    def _draw_molecular_detection(self, detection: MolecularDetection) -> None:
        is_selected = detection.detection_id == self._selected_molecular_detection_id
        item = self.viewer.add_polyline_nm(
            _bbox_polyline(self._bbox_from_native_to_current_view(detection.bbox_xyxy)),
            name=detection.detection_id,
            color=(0, 220, 255) if is_selected else (255, 180, 0),
            width=3.0 if is_selected else 1.5,
        )
        self._molecular_detection_items.append(item)

    def _clear_molecular_detection_overlays(self) -> None:
        for item in self._molecular_detection_items:
            self.viewer.remove_item(item)
        self._molecular_detection_items = []

    def _redraw_molecular_detection_overlays(self) -> None:
        self._clear_molecular_detection_overlays()
        if self._project is None:
            return
        detections = self._project.molecular_detections_for_working_frame(self._active_working_frame_index)
        for detection in detections:
            if detection.detection_id != self._selected_molecular_detection_id:
                self._draw_molecular_detection(detection)
        for detection in detections:
            if detection.detection_id == self._selected_molecular_detection_id:
                self._draw_molecular_detection(detection)

    def selected_molecular_detection_id(self) -> str | None:
        return self._selected_molecular_detection_id

    def select_molecular_detection(self, detection_id: str) -> None:
        target_id = str(detection_id)
        matches = [
            self.detection_list.item(row)
            for row in range(self.detection_list.count())
            if self.detection_list.item(row).data(Qt.ItemDataRole.UserRole) == target_id
        ]
        if not matches:
            raise KeyError(f"Unknown active-frame molecular detection: {target_id}")
        self.detection_list.setCurrentItem(matches[0])

    def detection_id_at_view_point(self, x: float, y: float) -> str | None:
        if self._project is None:
            return None
        native_point = self._point_from_current_view_to_native((float(x), float(y)))
        detections = self._project.molecular_detections_for_working_frame(self._active_working_frame_index)
        for detection in reversed(detections):
            if _point_inside_bbox_xyxy(detection.bbox_xyxy, native_point):
                return detection.detection_id
        return None

    def build_detection_context_menu(self, detection_id: str) -> QMenu:
        detection = self._active_molecular_detection_by_id(detection_id)
        self.select_molecular_detection(detection.detection_id)
        menu = QMenu(self)
        accept_action = menu.addAction("Accept")
        accept_action.triggered.connect(
            lambda _checked=False, target_id=detection.detection_id: self.set_molecular_detection_status(
                (target_id,),
                DetectionReviewStatus.ACCEPTED,
            )
        )
        reject_action = menu.addAction("Reject")
        reject_action.triggered.connect(
            lambda _checked=False, target_id=detection.detection_id: self.set_molecular_detection_status(
                (target_id,),
                DetectionReviewStatus.REJECTED,
            )
        )
        uncertain_action = menu.addAction("Uncertain")
        uncertain_action.triggered.connect(
            lambda _checked=False, target_id=detection.detection_id: self.set_molecular_detection_status(
                (target_id,),
                DetectionReviewStatus.UNCERTAIN,
            )
        )
        menu.addSeparator()
        edit_action = menu.addAction("Edit BBox...")
        edit_action.triggered.connect(
            lambda _checked=False, target_id=detection.detection_id: self.edit_detection_bbox_via_dialog(target_id)
        )
        scale_action = menu.addAction("Scale BBox...")
        scale_action.triggered.connect(
            lambda _checked=False, target_id=detection.detection_id: self.scale_detection_bbox_via_dialog(target_id)
        )
        menu.addSeparator()
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(
            lambda _checked=False, target_id=detection.detection_id: self.remove_molecular_detections((target_id,))
        )
        return menu

    def show_detection_context_menu(self, detection_id: str, global_pos) -> None:
        menu = self.build_detection_context_menu(detection_id)
        menu.exec(global_pos)
        menu.deleteLater()

    def edit_detection_bbox_via_dialog(self, detection_id: str) -> MolecularDetection | None:
        detection = self._active_molecular_detection_by_id(detection_id)
        bbox_xyxy = DetectionBBoxDialog.get_bbox(self, detection.bbox_xyxy)
        if bbox_xyxy is None:
            return None
        return self.edit_molecular_detection_bbox(detection.detection_id, bbox_xyxy)

    def scale_detection_bbox_via_dialog(self, detection_id: str) -> MolecularDetection | None:
        detection = self._active_molecular_detection_by_id(detection_id)
        scale_factor = DetectionScaleDialog.get_scale_factor(self, self.scale_bbox_factor_spin.value())
        if scale_factor is None:
            return None
        return self.scale_molecular_detection_bboxes((detection.detection_id,), scale_factor)[0]

    def _active_molecular_detection_by_id(self, detection_id: str) -> MolecularDetection:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        target_id = str(detection_id)
        for detection in self._project.molecular_detections_for_working_frame(self._active_working_frame_index):
            if detection.detection_id == target_id:
                return detection
        raise KeyError(f"Unknown active-frame molecular detection: {target_id}")

    def _selected_molecular_detection(self) -> MolecularDetection:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        if self._selected_molecular_detection_id is None:
            raise ValueError("Select a molecular detection first.")
        for detection in self._project.molecular_detections_for_working_frame(self._active_working_frame_index):
            if detection.detection_id == self._selected_molecular_detection_id:
                return detection
        raise KeyError(f"Unknown active-frame molecular detection: {self._selected_molecular_detection_id}")

    def _active_analysis_regions(self) -> list[AnalysisRegion]:
        if self._project is None:
            return list(self._analysis_regions.values())
        return list(self._project.analysis_regions_for_working_frame(self._active_working_frame_index))

    def _redraw_analysis_region_overlays(self) -> None:
        self._clear_analysis_region_overlays()
        for region in self._active_analysis_regions():
            self._draw_analysis_region(region)

    def _sync_project_analysis_regions(self) -> None:
        if self._project is None:
            return
        self._project = self._project.with_analysis_regions(
            tuple(self._analysis_regions.values()),
            copied_analysis_regions=tuple(self._copied_analysis_regions.values()),
            frame_scoped_analysis_regions=tuple(self._frame_scoped_analysis_regions),
        )

    def _warn_if_terrace_regions_overlap(self) -> None:
        if self._project is None:
            return
        warnings = _terrace_overlap_warnings(self._project)
        if warnings:
            QMessageBox.warning(self, "Region overlap", "\n".join(warnings))

    def _default_rect_roi_xyxy(self) -> tuple[float, float, float, float]:
        rect = self._visible_image_rect()
        width = max(rect.width() * 0.35, 1.0)
        height = max(rect.height() * 0.35, 1.0)
        cx = rect.left() + rect.width() * 0.5
        cy = rect.top() + rect.height() * 0.5
        return cx - width / 2.0, cy - height / 2.0, cx + width / 2.0, cy + height / 2.0

    def _default_polyline_vertices_xy(self) -> np.ndarray:
        x0, y0, x1, y1 = self._default_rect_roi_xyxy()
        return np.asarray(
            [
                [x0, y0],
                [x1, y0],
                [x1, y1],
                [x0, y1],
            ],
            dtype=np.float64,
        )

    def _visible_image_rect(self) -> QRectF:
        if self._displayed_frame is not None:
            height, width = self._displayed_frame.shape[:2]
            return QRectF(0.0, 0.0, float(width), float(height))
        (x0, x1), (y0, y1) = self.viewer.get_plot_item().getViewBox().viewRange()
        width = max(float(x1 - x0), 1.0)
        height = max(float(y1 - y0), 1.0)
        return QRectF(float(x0), float(y0), width, height)

    def _drawn_region_geometry(self):
        if self._draft_region_roi is None or self._draft_region_roi_kind is None:
            raise ValueError("No drawn ROI or polyline is available.")
        if self._draft_region_roi_kind == "rect":
            pos = self._draft_region_roi.pos()
            size = self._draft_region_roi.size()
            return "rect", _sorted_rect_xyxy(
                (
                    float(pos.x()),
                    float(pos.y()),
                    float(pos.x() + size.x()),
                    float(pos.y() + size.y()),
                )
            )
        state = self._draft_region_roi.saveState()
        pos = self._draft_region_roi.pos()
        vertices = np.asarray(
            [
                [
                    float(point[0] if isinstance(point, (tuple, list)) else point.x()) + float(pos.x()),
                    float(point[1] if isinstance(point, (tuple, list)) else point.y()) + float(pos.y()),
                ]
                for point in state.get("points", [])
            ],
            dtype=np.float64,
        )
        if vertices.ndim != 2 or vertices.shape[1] != 2 or len(vertices) < 3:
            raise ValueError("Drawn polyline region requires at least three vertices.")
        return "polygon", vertices

    def _manual_detection_bbox_geometry(self) -> tuple[float, float, float, float]:
        if self._draft_detection_bbox_roi is None:
            raise ValueError("No drawn detection bbox is available.")
        pos = self._draft_detection_bbox_roi.pos()
        size = self._draft_detection_bbox_roi.size()
        return _sorted_rect_xyxy(
            (
                float(pos.x()),
                float(pos.y()),
                float(pos.x() + size.x()),
                float(pos.y() + size.y()),
            )
        )

    def _bbox_from_current_view_to_native(self, bbox_xyxy) -> tuple[float, float, float, float]:
        region = AnalysisRegion.rectangle(
            kind=AnalysisRegionKind.CUSTOM,
            name="manual_detection_bbox",
            color_rgb=(0, 220, 255),
            rect_xyxy=_sorted_rect_xyxy(bbox_xyxy),
        )
        native_region = self._region_from_current_view_to_native(region)
        return native_region.rect_xyxy

    def _bbox_from_native_to_current_view(self, bbox_xyxy) -> tuple[float, float, float, float]:
        region = AnalysisRegion.rectangle(
            kind=AnalysisRegionKind.CUSTOM,
            name="detection_bbox",
            color_rgb=(0, 220, 255),
            rect_xyxy=_sorted_rect_xyxy(bbox_xyxy),
        )
        if self._show_expanded_aligned_view:
            region = self._region_to_expanded_canvas(region, self._active_working_frame_index)
        return region.rect_xyxy

    def _point_from_current_view_to_native(self, point_xy) -> tuple[float, float]:
        x, y = (float(value) for value in point_xy)
        if not self._show_expanded_aligned_view:
            return x, y
        origin = self._expanded_frame_origin_xy(self._active_working_frame_index)
        return x - float(origin[0]), y - float(origin[1])

    def commit_selected_detection_bbox_edit(self, bbox_xyxy=None) -> MolecularDetection:
        detection_id = self._editing_detection_id or self._selected_molecular_detection_id
        if detection_id is None:
            raise ValueError("Select a molecular detection first.")
        if bbox_xyxy is None:
            bbox_xyxy = self._manual_detection_bbox_geometry()
        native_bbox = self._bbox_from_current_view_to_native(bbox_xyxy)
        updated_detection = self.edit_molecular_detection_bbox(detection_id, native_bbox)
        self.clear_manual_detection_bbox()
        return updated_detection

    def _on_add_rect_region(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "Add region", "Load or import a project before adding regions.")
            return
        region = AnalysisRegionRectDialog.get_region(self)
        if region is None:
            return
        try:
            if self._expanded_region_mode_is_fixed_canvas():
                self._apply_expanded_canvas_region_to_frames(region, self._all_working_frame_indices())
            else:
                self.add_analysis_region(self._region_from_current_view_to_native(region))
        except Exception as exc:
            QMessageBox.critical(self, "Add region failed", str(exc))

    def _on_draw_rect_region_roi(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "Draw region", "Load or import a project before drawing regions.")
            return
        try:
            self.start_rect_region_roi()
        except Exception as exc:
            QMessageBox.critical(self, "Draw region failed", str(exc))

    def _on_draw_polyline_region(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "Draw region", "Load or import a project before drawing regions.")
            return
        try:
            self.start_polyline_region_roi()
        except Exception as exc:
            QMessageBox.critical(self, "Draw region failed", str(exc))

    def _on_draw_manual_detection_bbox(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "Draw detection", "Load or import a project before drawing detections.")
            return
        try:
            self.start_manual_detection_bbox()
        except Exception as exc:
            QMessageBox.critical(self, "Draw detection failed", str(exc))

    def _on_commit_manual_detection_bbox(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "Manual detection", "Load or import a project before adding detections.")
            return
        try:
            bbox_xyxy = self._bbox_from_current_view_to_native(self._manual_detection_bbox_geometry())
            self.add_manual_detection_bbox(bbox_xyxy)
            self.clear_manual_detection_bbox()
        except ValueError as exc:
            QMessageBox.warning(self, "Manual detection", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Manual detection failed", str(exc))

    def _on_edit_selected_detection_bbox(self) -> None:
        try:
            self.start_selected_detection_bbox_edit()
        except ValueError as exc:
            QMessageBox.warning(self, "Edit detection", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Edit detection failed", str(exc))

    def _on_commit_detection_bbox_edit(self) -> None:
        try:
            self.commit_selected_detection_bbox_edit()
        except ValueError as exc:
            QMessageBox.warning(self, "Edit detection", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Edit detection failed", str(exc))

    def _on_delete_selected_detection(self) -> None:
        try:
            self.remove_selected_molecular_detection()
        except ValueError as exc:
            QMessageBox.warning(self, "Delete detection", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Delete detection failed", str(exc))

    def _on_delete_current_status(self) -> None:
        try:
            self.remove_current_frame_molecular_detections_by_status(
                str(self.delete_status_combo.currentData() or DetectionReviewStatus.CANDIDATE.value)
            )
        except Exception as exc:
            QMessageBox.critical(self, "Delete detection failed", str(exc))

    def _on_delete_inside_selected_region(self) -> None:
        region_name = self.selected_region_name()
        if region_name is None:
            QMessageBox.warning(self, "Delete detection", "Select a region before deleting detections inside it.")
            return
        try:
            self.remove_current_frame_molecular_detections_inside_region(region_name)
        except Exception as exc:
            QMessageBox.critical(self, "Delete detection failed", str(exc))

    def _on_scale_selected_bbox(self) -> None:
        try:
            self.scale_selected_molecular_detection_bbox(self.scale_bbox_factor_spin.value())
        except ValueError as exc:
            QMessageBox.warning(self, "Scale detection", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Scale detection failed", str(exc))

    def _on_scale_current_frame_bboxes(self) -> None:
        try:
            self.scale_current_frame_molecular_detection_bboxes(self.scale_bbox_factor_spin.value())
        except Exception as exc:
            QMessageBox.critical(self, "Scale detection failed", str(exc))

    def _on_scale_all_bboxes(self) -> None:
        try:
            self.scale_all_molecular_detection_bboxes(self.scale_bbox_factor_spin.value())
        except Exception as exc:
            QMessageBox.critical(self, "Scale detection failed", str(exc))

    def _on_commit_drawn_region(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "Commit region", "Load or import a project before adding regions.")
            return
        try:
            geometry_type, geometry = self._drawn_region_geometry()
            metadata = AnalysisRegionMetadataDialog.get_metadata(self)
            if metadata is None:
                return
            kind, name, color_rgb = metadata
            if geometry_type == "rect":
                region = AnalysisRegion.rectangle(
                    kind=kind,
                    name=name,
                    color_rgb=color_rgb,
                    rect_xyxy=geometry,
                )
            else:
                region = AnalysisRegion.polygon(
                    kind=kind,
                    name=name,
                    color_rgb=color_rgb,
                    vertices_xy=geometry,
                )
            if region.name in self._analysis_regions:
                frame_indices = AnalysisRegionFrameRangeDialog.get_working_frame_indices(
                    self,
                    self._project.working_series.frame_count,
                    self._active_working_frame_index,
                )
                if frame_indices is None:
                    return
                if self._expanded_region_mode_is_fixed_canvas():
                    self._apply_expanded_canvas_region_to_frames(region, frame_indices)
                else:
                    self.apply_analysis_region_to_frames(
                        region.name,
                        frame_indices,
                        region=self._region_from_current_view_to_native(region),
                    )
            else:
                if self._expanded_region_mode_is_fixed_canvas():
                    self._apply_expanded_canvas_region_to_frames(region, self._all_working_frame_indices())
                else:
                    self.add_analysis_region(self._region_from_current_view_to_native(region))
            self.clear_drawn_region_roi()
        except Exception as exc:
            QMessageBox.critical(self, "Commit region failed", str(exc))

    def _on_edit_selected_region(self) -> None:
        region_name = self.selected_region_name()
        if region_name is None:
            QMessageBox.warning(self, "Edit region", "Select a region to edit.")
            return
        active_scoped_region = self._active_frame_scoped_region(region_name)
        region = active_scoped_region.region if active_scoped_region is not None else self._analysis_regions[region_name]
        if region.rect_xyxy is None:
            QMessageBox.warning(self, "Edit region", "Only rectangular regions can be edited in this dialog.")
            return
        updated_region = AnalysisRegionRectDialog.get_region(self, region)
        if updated_region is None:
            return
        try:
            if active_scoped_region is not None:
                scope = AnalysisRegionEditScopeDialog.get_scope(self)
                if scope is None:
                    return
                if scope == "current_scope":
                    self._replace_frame_scoped_region(active_scoped_region, updated_region)
                else:
                    self.update_analysis_region(region_name, updated_region)
            else:
                self.update_analysis_region(region_name, updated_region)
        except Exception as exc:
            QMessageBox.critical(self, "Edit region failed", str(exc))

    def _on_delete_selected_region(self) -> None:
        region_name = self.selected_region_name()
        if region_name is None:
            QMessageBox.warning(self, "Delete region", "Select a region to delete.")
            return
        try:
            self.remove_analysis_region(region_name)
        except Exception as exc:
            QMessageBox.critical(self, "Delete region failed", str(exc))

    def _on_set_selected_detection_status(self, status: DetectionReviewStatus) -> None:
        try:
            self.set_selected_molecular_detection_status(status)
        except ValueError as exc:
            QMessageBox.warning(self, "Detection review", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Detection review failed", str(exc))

    def _on_accept_all_current_frame(self) -> None:
        try:
            self.set_current_frame_molecular_detection_status(DetectionReviewStatus.ACCEPTED)
        except Exception as exc:
            QMessageBox.critical(self, "Detection review failed", str(exc))

    def _on_accept_above_confidence(self) -> None:
        try:
            self.set_current_frame_molecular_detection_status_above_confidence(
                self.accept_confidence_threshold_spin.value(),
                DetectionReviewStatus.ACCEPTED,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Detection review failed", str(exc))

    def _on_copy_selected_region_to_series(self) -> None:
        region_name = self.selected_region_name()
        if region_name is None:
            QMessageBox.warning(self, "Copy region", "Select a region to copy to the series.")
            return
        try:
            self.copy_analysis_region_to_series(region_name)
        except Exception as exc:
            QMessageBox.critical(self, "Copy region failed", str(exc))

    def _on_run_registration(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "Run registration", "Load or import a project before running registration.")
            return
        active_index = self._active_working_frame_index
        frame_count = self._project.working_series.frame_count
        backend_label = self._selected_registration_backend_label()
        progress = QProgressDialog(f"Running {backend_label} registration...", "", 0, frame_count, self)
        progress.setWindowTitle("Registration")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setAutoClose(True)
        progress.setAutoReset(True)
        progress.setValue(0)

        def on_progress(completed: int, total: int, _shift) -> None:
            progress.setMaximum(int(total))
            progress.setLabelText(f"Running {backend_label} registration... {int(completed)}/{int(total)}")
            progress.setValue(int(completed))
            QApplication.processEvents()

        try:
            backend = self._selected_registration_backend_key()
            registered_project = run_project_registration(
                self._project,
                backend=backend,
                progress_callback=on_progress,
            )
            self.set_project(registered_project)
            self._set_show_expanded_aligned(True)
            self.set_active_working_frame_index(
                min(active_index, registered_project.working_series.frame_count - 1)
            )
            progress.setValue(frame_count)
        except Exception as exc:
            QMessageBox.critical(self, "Run registration failed", str(exc))
        finally:
            progress.close()

    def _on_detect_yolo_current_frame(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "YOLO detection", "Load or import a project before running YOLO detection.")
            return
        options = self._request_yolo_detection_options(title="YOLO Detect Current Frame")
        if options is None:
            return
        model, config = options
        try:
            detections = self.detect_yolo_on_current_frame(
                model,
                config=config,
            )
        except Exception as exc:
            QMessageBox.critical(self, "YOLO detection failed", str(exc))
            return
        self.statusBar().showMessage(
            f"YOLO detected {len(detections)} molecules on current frame.",
            2500,
        )

    def _on_detect_yolo_current_frame_in_selected_roi(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "YOLO ROI detection", "Load or import a project before running YOLO detection.")
            return
        region_name = self.selected_region_name()
        if region_name is None:
            QMessageBox.warning(self, "YOLO ROI detection", "Select a region before running ROI detection.")
            return
        options = self._request_yolo_detection_options(title="YOLO Detect Current Frame in Selected ROI")
        if options is None:
            return
        model, config = options
        try:
            detections = self.detect_yolo_on_current_frame_in_region(
                region_name,
                model,
                config=config,
            )
        except Exception as exc:
            QMessageBox.critical(self, "YOLO ROI detection failed", str(exc))
            return
        self.statusBar().showMessage(
            f"YOLO replaced {len(detections)} molecules inside {region_name}.",
            2500,
        )

    def _on_detect_yolo_all_working_frames(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "YOLO detection", "Load or import a project before running YOLO detection.")
            return
        options = self._request_yolo_detection_options(title="YOLO Detect All Working Frames")
        if options is None:
            return
        model, config = options
        total_frames = self._project.working_series.frame_count
        progress = QProgressDialog("Running YOLO detection...", "Cancel", 0, total_frames, self)
        progress.setWindowTitle("YOLO detection")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(True)
        progress.setAutoReset(True)
        progress.setValue(0)

        def on_progress(completed: int, total: int, frame_index: int) -> None:
            progress.setMaximum(int(total))
            progress.setLabelText(
                f"Running YOLO detection... {int(completed)}/{int(total)} "
                f"(working frame {int(frame_index) + 1})"
            )
            progress.setValue(int(completed))
            QApplication.processEvents()

        def is_canceled() -> bool:
            QApplication.processEvents()
            return progress.wasCanceled()

        try:
            detections_by_frame = self.detect_yolo_on_all_working_frames(
                model,
                config=config,
                progress_callback=on_progress,
                cancel_check=is_canceled,
            )
        except Exception as exc:
            QMessageBox.critical(self, "YOLO detection failed", str(exc))
            return
        finally:
            progress.close()

        detection_count = sum(len(detections) for detections in detections_by_frame.values())
        if len(detections_by_frame) < total_frames:
            self.statusBar().showMessage(
                f"YOLO detection canceled after {len(detections_by_frame)}/{total_frames} frames; "
                f"{detection_count} molecules detected.",
                3500,
            )
        else:
            self.statusBar().showMessage(
                f"YOLO detected {detection_count} molecules across {total_frames} working frames.",
                3500,
            )

    def _on_detect_yolo_selected_roi_frame_range(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "YOLO ROI detection", "Load or import a project before running YOLO detection.")
            return
        region_name = self.selected_region_name()
        if region_name is None:
            QMessageBox.warning(self, "YOLO ROI detection", "Select a region before running ROI detection.")
            return
        frame_indices = AnalysisRegionFrameRangeDialog.get_working_frame_indices(
            self,
            self._project.working_series.frame_count,
            self._active_working_frame_index,
        )
        if frame_indices is None:
            return
        options = self._request_yolo_detection_options(title="YOLO Detect Selected ROI on Frame Range")
        if options is None:
            return
        model, config = options

        progress = QProgressDialog("Running YOLO ROI detection...", "Cancel", 0, len(frame_indices), self)
        progress.setWindowTitle("YOLO ROI detection")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setAutoClose(True)
        progress.setAutoReset(True)
        progress.setValue(0)

        def on_progress(completed: int, total: int, frame_index: int) -> None:
            progress.setMaximum(int(total))
            progress.setLabelText(
                f"Running YOLO ROI detection... {int(completed)}/{int(total)} "
                f"(working frame {int(frame_index) + 1})"
            )
            progress.setValue(int(completed))
            QApplication.processEvents()

        def is_canceled() -> bool:
            QApplication.processEvents()
            return progress.wasCanceled()

        try:
            detections_by_frame = self.detect_yolo_in_region_on_working_frames(
                region_name,
                model,
                working_frame_indices=frame_indices,
                config=config,
                progress_callback=on_progress,
                cancel_check=is_canceled,
            )
        except Exception as exc:
            QMessageBox.critical(self, "YOLO ROI detection failed", str(exc))
            return
        finally:
            progress.close()

        detection_count = sum(len(detections) for detections in detections_by_frame.values())
        if len(detections_by_frame) < len(frame_indices):
            self.statusBar().showMessage(
                f"YOLO ROI detection canceled after {len(detections_by_frame)}/{len(frame_indices)} frames; "
                f"{detection_count} molecules detected inside {region_name}.",
                3500,
            )
        else:
            self.statusBar().showMessage(
                f"YOLO detected {detection_count} molecules inside {region_name} "
                f"across {len(frame_indices)} working frames.",
                3500,
            )

    def _on_show_expanded_aligned_toggled(self, checked: bool) -> None:
        self._show_expanded_aligned_view = bool(checked)
        if self._project is None:
            return
        try:
            self.set_active_working_frame_index(self._active_working_frame_index)
        except Exception as exc:
            self._set_show_expanded_aligned(False)
            QMessageBox.critical(self, "Expanded aligned view failed", str(exc))

    def _on_apply_selected_region_to_current_frame(self) -> None:
        region_name = self.selected_region_name()
        if region_name is None:
            QMessageBox.warning(self, "Apply region", "Select a region to apply to the current frame.")
            return
        try:
            if self._expanded_region_mode_is_fixed_canvas():
                self._copy_active_expanded_canvas_region_to_frames(region_name, (self._active_working_frame_index,))
            else:
                self.apply_analysis_region_to_frames(region_name, (self._active_working_frame_index,))
        except Exception as exc:
            QMessageBox.critical(self, "Apply region failed", str(exc))

    def _on_copy_selected_region_from_current_to_end(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "Copy region", "Load or import a project before copying regions.")
            return
        region_name = self.selected_region_name()
        if region_name is None:
            QMessageBox.warning(self, "Copy region", "Select a region to copy to the frame range.")
            return
        try:
            frame_indices = tuple(
                range(self._active_working_frame_index, self._project.working_series.frame_count)
            )
            if self._expanded_region_mode_is_fixed_canvas():
                self._copy_active_expanded_canvas_region_to_frames(region_name, frame_indices)
            else:
                self.apply_analysis_region_to_frames(region_name, frame_indices)
        except Exception as exc:
            QMessageBox.critical(self, "Copy region failed", str(exc))

    def _on_copy_selected_region_to_frame_range(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "Copy region", "Load or import a project before copying regions.")
            return
        region_name = self.selected_region_name()
        if region_name is None:
            QMessageBox.warning(self, "Copy region", "Select a region to copy to the frame range.")
            return
        try:
            frame_indices = AnalysisRegionFrameRangeDialog.get_working_frame_indices(
                self,
                self._project.working_series.frame_count,
                self._active_working_frame_index,
            )
            if frame_indices is None:
                return
            if self._expanded_region_mode_is_fixed_canvas():
                self._copy_active_expanded_canvas_region_to_frames(region_name, frame_indices)
            else:
                self.apply_analysis_region_to_frames(region_name, frame_indices)
        except Exception as exc:
            QMessageBox.critical(self, "Copy region failed", str(exc))

    def _active_frame_scoped_region(self, region_name: str) -> FrameScopedAnalysisRegion | None:
        for scoped_region in self._frame_scoped_analysis_regions:
            if (
                scoped_region.region.name == region_name
                and scoped_region.applies_to_working_frame(self._active_working_frame_index)
            ):
                return scoped_region
        return None

    def _replace_frame_scoped_region(
        self,
        scoped_region: FrameScopedAnalysisRegion,
        updated_region: AnalysisRegion,
    ) -> None:
        self._frame_scoped_analysis_regions = [
            existing
            for existing in self._frame_scoped_analysis_regions
            if existing is not scoped_region
        ]
        self._frame_scoped_analysis_regions.append(
            FrameScopedAnalysisRegion(
                region=updated_region,
                working_frame_indices=scoped_region.working_frame_indices,
            )
        )
        self._sync_project_analysis_regions()
        self._refresh_region_list(updated_region.name)
        self._redraw_analysis_region_overlays()

    def _registration_shift_label_suffix(self, working_frame_index: int) -> str:
        if self._project is None:
            return ""
        shift = self._project.registration_shift_for_working_frame(working_frame_index)
        if shift is None:
            return ""
        return f" | Registration dx={shift.dx:.3f}px dy={shift.dy:.3f}px"

    def _registered_view_label_suffix(self) -> str:
        return " | Expanded aligned view" if self._show_expanded_aligned_view else ""

    def _display_frame_for_working_frame(self, working_frame_index: int) -> np.ndarray:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        working_frame = self._project.working_series.get_working_frame(working_frame_index)
        if self._show_expanded_aligned_view:
            return self._ensure_expanded_aligned_stack().frames[working_frame.working_frame_index]
        return self._project.source_series.get_frame(working_frame.source_frame_index)

    def _selected_registration_backend_key(self) -> str:
        current_data = self.registration_backend_combo.currentData()
        return str(current_data or "phase_correlation")

    def _selected_registration_backend_label(self) -> str:
        current_text = self.registration_backend_combo.currentText().strip()
        return current_text or "Phase"

    def _selected_expanded_region_mode(self) -> str:
        combo = getattr(self, "expanded_region_mode_combo", None)
        if combo is None:
            return EXPANDED_REGION_MODE_FIXED_CANVAS
        current_data = combo.currentData()
        if current_data in {EXPANDED_REGION_MODE_FIXED_CANVAS, EXPANDED_REGION_MODE_MOVE_WITH_IMAGE}:
            return str(current_data)
        return EXPANDED_REGION_MODE_FIXED_CANVAS

    def _expanded_region_mode_is_fixed_canvas(self) -> bool:
        return (
            self._show_expanded_aligned_view
            and self._selected_expanded_region_mode() == EXPANDED_REGION_MODE_FIXED_CANVAS
        )

    def _all_working_frame_indices(self) -> tuple[int, ...]:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        return tuple(frame.working_frame_index for frame in self._project.working_series.frames)

    def _clear_expanded_aligned_cache(self) -> None:
        self._expanded_aligned_stack = None
        self._expanded_aligned_cache_key = None

    def _set_show_expanded_aligned(self, checked: bool) -> None:
        self._show_expanded_aligned_view = bool(checked)
        if hasattr(self, "show_expanded_aligned_action"):
            with QSignalBlocker(self.show_expanded_aligned_action):
                self.show_expanded_aligned_action.setChecked(bool(checked))

    def _ensure_expanded_aligned_stack(self):
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        if self._project.source_series.raw_frames is None:
            raise ValueError("Expanded aligned view requires loaded source image frames.")
        cache_key = (id(self._project), id(self._project.source_series.raw_frames))
        if self._expanded_aligned_stack is None or self._expanded_aligned_cache_key != cache_key:
            self._expanded_aligned_stack = expanded_registered_working_stack(self._project)
            self._expanded_aligned_cache_key = cache_key
        return self._expanded_aligned_stack

    def current_expanded_aligned_stack(self):
        return self._ensure_expanded_aligned_stack()

    def current_expanded_aligned_frame(self) -> np.ndarray:
        return self._ensure_expanded_aligned_stack().frames[self._active_working_frame_index]

    def current_project(self) -> MolTrackProject | None:
        return self._project

    def current_project_path(self):
        return self._project_path

    def save_project_to(self, path) -> None:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        self._sync_project_analysis_regions()
        save_project(path, self._project)
        self._project_path = Path(path)

    def save_project(self) -> None:
        if self._project_path is None:
            self._on_save_project_as()
            return
        self.save_project_to(self._project_path)

    def open_project_file(self, path) -> None:
        project = load_project(path)
        self._project_path = Path(path)
        self.set_project(project)

    def import_image_series_from(self, source_paths, *, reverse_frame_order: bool = False) -> None:
        project = import_image_series(source_paths, reverse_frame_order=reverse_frame_order)
        self._project_path = None
        self.set_project(project)

    def _on_import_image_series(self) -> None:
        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "Import Image Series",
            "",
            "STM Image Series (*.mpp *.stp *.s94);;MPP Movies (*.mpp);;Frame Series (*.stp *.s94);;All Files (*)",
        )
        if not paths:
            return
        source_paths = paths[0] if len(paths) == 1 else paths
        try:
            self.import_image_series_from(
                source_paths,
                reverse_frame_order=self.import_reversed_order_action.isChecked(),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Import image series failed", str(exc))

    def _on_open_project(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open MolTrack Project",
            "",
            "MolTrack Projects (*.moltrack);;All Files (*)",
        )
        if path:
            try:
                self.open_project_file(path)
            except Exception as exc:
                QMessageBox.critical(self, "Open project failed", str(exc))

    def _on_save_project(self) -> None:
        try:
            self.save_project()
        except Exception as exc:
            QMessageBox.critical(self, "Save project failed", str(exc))

    def _on_save_project_as(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save MolTrack Project",
            "",
            "MolTrack Projects (*.moltrack);;All Files (*)",
        )
        if path:
            try:
                self.save_project_to(path)
            except Exception as exc:
                QMessageBox.critical(self, "Save project failed", str(exc))


def _analysis_region_polyline(region: AnalysisRegion) -> np.ndarray:
    if region.rect_xyxy is not None:
        return _bbox_polyline(region.rect_xyxy)

    vertices = np.asarray(region.polygon_xy, dtype=np.float64)
    if np.allclose(vertices[0], vertices[-1]):
        return vertices
    return np.vstack([vertices, vertices[0]])


def _bbox_polyline(bbox_xyxy) -> np.ndarray:
    x0, y0, x1, y1 = (float(value) for value in bbox_xyxy)
    return np.asarray(
        [
            [x0, y0],
            [x1, y0],
            [x1, y1],
            [x0, y1],
            [x0, y0],
        ],
        dtype=np.float64,
    )


def _runtime_bbox_xyxy(bbox) -> tuple[float, float, float, float]:
    if hasattr(bbox, "as_tuple"):
        values = bbox.as_tuple()
    elif all(hasattr(bbox, attr) for attr in ("x0", "y0", "x1", "y1")):
        values = (bbox.x0, bbox.y0, bbox.x1, bbox.y1)
    else:
        values = tuple(bbox)
    return tuple(float(value) for value in values)


def _bbox_centroid_xy(bbox_xyxy) -> tuple[float, float]:
    x0, y0, x1, y1 = (float(value) for value in bbox_xyxy)
    return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def _detection_list_label(detection: MolecularDetection) -> str:
    region = detection.region_name or "-"
    return (
        f"{detection.detection_id} | {detection.review_status.value} | "
        f"conf={detection.confidence:.3f} | region={region}"
    )


def _review_status_after_bbox_edit(status: DetectionReviewStatus) -> DetectionReviewStatus:
    if status in {DetectionReviewStatus.CANDIDATE, DetectionReviewStatus.ACCEPTED}:
        return DetectionReviewStatus.EDITED
    return status


def _valid_bbox_scale_factor(scale_factor: float) -> float:
    scale_factor = float(scale_factor)
    if not np.isfinite(scale_factor) or scale_factor <= 0.0:
        raise ValueError("scale_factor must be a positive finite value.")
    return scale_factor


def _scale_bbox_xyxy(bbox_xyxy, scale_factor: float) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = _sorted_rect_xyxy(bbox_xyxy)
    scale_factor = _valid_bbox_scale_factor(scale_factor)
    cx = (x0 + x1) / 2.0
    cy = (y0 + y1) / 2.0
    half_width = (x1 - x0) * scale_factor / 2.0
    half_height = (y1 - y0) * scale_factor / 2.0
    return (
        cx - half_width,
        cy - half_height,
        cx + half_width,
        cy + half_height,
    )


def _point_inside_analysis_region(region: AnalysisRegion, point_xy) -> bool:
    x, y = (float(value) for value in point_xy)
    if region.rect_xyxy is not None:
        x0, y0, x1, y1 = region.rect_xyxy
        return x0 <= x <= x1 and y0 <= y <= y1
    return _point_inside_polygon_xy((x, y), np.asarray(region.polygon_xy, dtype=np.float64))


def _point_inside_bbox_xyxy(bbox_xyxy, point_xy) -> bool:
    x, y = (float(value) for value in point_xy)
    x0, y0, x1, y1 = _sorted_rect_xyxy(bbox_xyxy)
    return x0 <= x <= x1 and y0 <= y <= y1


def _point_inside_polygon_xy(point_xy: tuple[float, float], polygon_xy: np.ndarray) -> bool:
    x, y = point_xy
    inside = False
    previous_x, previous_y = polygon_xy[-1]
    for current_x, current_y in polygon_xy:
        if _point_on_segment_xy((x, y), (previous_x, previous_y), (current_x, current_y)):
            return True
        crosses_y = (current_y > y) != (previous_y > y)
        if crosses_y:
            boundary_x = (previous_x - current_x) * (y - current_y) / (previous_y - current_y) + current_x
            if x < boundary_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def _point_on_segment_xy(point_xy, start_xy, end_xy, *, eps: float = 1e-9) -> bool:
    px, py = (float(value) for value in point_xy)
    x0, y0 = (float(value) for value in start_xy)
    x1, y1 = (float(value) for value in end_xy)
    cross = (px - x0) * (y1 - y0) - (py - y0) * (x1 - x0)
    if abs(cross) > eps:
        return False
    return min(x0, x1) - eps <= px <= max(x0, x1) + eps and min(y0, y1) - eps <= py <= max(y0, y1) + eps


def _unique_detection_id(base_id: str, existing_ids: set[str]) -> str:
    if base_id not in existing_ids:
        return base_id
    suffix = 1
    while f"{base_id}-{suffix}" in existing_ids:
        suffix += 1
    return f"{base_id}-{suffix}"


def _translated_analysis_region(region: AnalysisRegion, offset_xy) -> AnalysisRegion:
    offset = np.asarray(offset_xy, dtype=np.float64)
    if offset.shape != (2,) or not np.all(np.isfinite(offset)):
        raise ValueError("offset_xy must contain two finite values.")
    dx, dy = float(offset[0]), float(offset[1])
    if region.rect_xyxy is not None:
        x0, y0, x1, y1 = region.rect_xyxy
        return AnalysisRegion.rectangle(
            kind=region.kind,
            name=region.name,
            color_rgb=region.color_rgb,
            rect_xyxy=(x0 + dx, y0 + dy, x1 + dx, y1 + dy),
        )
    vertices = np.asarray(region.polygon_xy, dtype=np.float64) + offset
    return AnalysisRegion.polygon(
        kind=region.kind,
        name=region.name,
        color_rgb=region.color_rgb,
        vertices_xy=vertices,
    )


def _sorted_rect_xyxy(rect_xyxy) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = (float(value) for value in rect_xyxy)
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _yolo_device_combo_index(device: str) -> int:
    normalized = str(device).strip().lower()
    if normalized == "cpu":
        return 1
    if normalized in {"gpu", "cuda", "cuda:0", "0"}:
        return 2
    return 0


class YoloDetectionOptionsDialog(QDialog):
    """Dialog for choosing the YOLO checkpoint and detection thresholds."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str = "YOLO Detection Options",
        models: list[MolTrackYoloModelInfo] | None = None,
        selected_model_path: Path | None = None,
        config: MolTrackYoloDetectionConfig | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._models: list[MolTrackYoloModelInfo] = []
        self._selected_model_path = Path(selected_model_path).resolve() if selected_model_path is not None else None

        config = config or MolTrackYoloDetectionConfig()
        layout = QFormLayout(self)

        self.model_combo = QComboBox(self)
        self.model_combo.setObjectName("moltrack-yolo-model-combo")
        self.model_combo.setToolTip("Choose a YOLO checkpoint discovered in nanotrack/yolo_models.")
        layout.addRow("Model", self.model_combo)

        self.confidence_spin = QDoubleSpinBox(self)
        self.confidence_spin.setObjectName("moltrack-yolo-confidence-spin")
        self.confidence_spin.setRange(0.0, 1.0)
        self.confidence_spin.setSingleStep(0.05)
        self.confidence_spin.setDecimals(2)
        self.confidence_spin.setValue(config.confidence_threshold)
        self.confidence_spin.setToolTip("Confidence threshold passed to YOLO detection.")
        layout.addRow("Confidence", self.confidence_spin)

        self.iou_spin = QDoubleSpinBox(self)
        self.iou_spin.setObjectName("moltrack-yolo-iou-spin")
        self.iou_spin.setRange(0.0, 1.0)
        self.iou_spin.setSingleStep(0.05)
        self.iou_spin.setDecimals(2)
        self.iou_spin.setValue(config.iou_threshold)
        self.iou_spin.setToolTip("NMS IoU threshold passed to YOLO detection.")
        layout.addRow("IoU", self.iou_spin)

        self.device_combo = QComboBox(self)
        self.device_combo.setObjectName("moltrack-yolo-device-combo")
        self.device_combo.setToolTip("Choose where YOLO inference runs.")
        self.device_combo.addItem("Auto", "auto")
        self.device_combo.addItem("CPU", "cpu")
        self.device_combo.addItem("GPU", "cuda:0")
        self.device_combo.setCurrentIndex(_yolo_device_combo_index(config.device))
        layout.addRow("Device", self.device_combo)

        self.models_label = QLabel("", self)
        self.models_label.setWordWrap(True)
        layout.addRow(self.models_label)

        self.refresh_models_button = QPushButton("Refresh Models", self)
        self.refresh_models_button.clicked.connect(lambda: self.refresh_models())
        layout.addRow(self.refresh_models_button)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addRow(self.button_box)

        self.refresh_models(models)

    def refresh_models(self, models: list[MolTrackYoloModelInfo] | None = None) -> None:
        current_model = self.selected_model()
        current_path = None if current_model is None else current_model.path
        selected_path = current_path or self._selected_model_path
        self._models = list(discover_moltrack_yolo_models() if models is None else models)
        self.model_combo.clear()

        selected_index = -1
        for index, model in enumerate(self._models):
            self.model_combo.addItem(model.display_name, model)
            if selected_path is not None and model.path == selected_path:
                selected_index = index

        if selected_index >= 0:
            self.model_combo.setCurrentIndex(selected_index)
        elif self._models:
            self.model_combo.setCurrentIndex(0)

        self.model_combo.setEnabled(bool(self._models))
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setEnabled(bool(self._models))
        if self._models:
            self.models_label.setText(f"YOLO models available: {len(self._models)}")
        else:
            self.models_label.setText("No YOLO models found in nanotrack/yolo_models.")

    def selected_model(self) -> MolTrackYoloModelInfo | None:
        data = self.model_combo.currentData()
        return data if isinstance(data, MolTrackYoloModelInfo) else None

    def to_options(self) -> tuple[MolTrackYoloModelInfo, MolTrackYoloDetectionConfig]:
        model = self.selected_model()
        if model is None:
            raise ValueError("Select a YOLO model before running detection.")
        device = str(self.device_combo.currentData() or "auto")
        return (
            model,
            MolTrackYoloDetectionConfig(
                confidence_threshold=self.confidence_spin.value(),
                iou_threshold=self.iou_spin.value(),
                device=device,
            ),
        )

    @classmethod
    def get_options(
        cls,
        parent: QWidget | None = None,
        *,
        title: str = "YOLO Detection Options",
        models: list[MolTrackYoloModelInfo] | None = None,
        selected_model_path: Path | None = None,
        config: MolTrackYoloDetectionConfig | None = None,
    ) -> tuple[MolTrackYoloModelInfo, MolTrackYoloDetectionConfig] | None:
        dialog = cls(
            parent,
            title=title,
            models=models,
            selected_model_path=selected_model_path,
            config=config,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.to_options()


class DetectionBBoxDialog(QDialog):
    """Dialog for editing one molecular detection bbox in native coordinates."""

    def __init__(self, parent: QWidget | None = None, bbox_xyxy=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit BBox")

        layout = QFormLayout(self)
        self.x0_spin = _coordinate_spinbox(self)
        self.y0_spin = _coordinate_spinbox(self)
        self.x1_spin = _coordinate_spinbox(self)
        self.y1_spin = _coordinate_spinbox(self)
        layout.addRow("x0", self.x0_spin)
        layout.addRow("y0", self.y0_spin)
        layout.addRow("x1", self.x1_spin)
        layout.addRow("y1", self.y1_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        x0, y0, x1, y1 = _sorted_rect_xyxy((0.0, 0.0, 1.0, 1.0) if bbox_xyxy is None else bbox_xyxy)
        self.x0_spin.setValue(x0)
        self.y0_spin.setValue(y0)
        self.x1_spin.setValue(x1)
        self.y1_spin.setValue(y1)

    @classmethod
    def get_bbox(
        cls,
        parent: QWidget | None,
        bbox_xyxy=None,
    ) -> tuple[float, float, float, float] | None:
        dialog = cls(parent, bbox_xyxy)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.to_bbox()

    def to_bbox(self) -> tuple[float, float, float, float]:
        x0, y0, x1, y1 = _sorted_rect_xyxy(
            (
                self.x0_spin.value(),
                self.y0_spin.value(),
                self.x1_spin.value(),
                self.y1_spin.value(),
            )
        )
        if x0 == x1 or y0 == y1:
            raise ValueError("bbox must have positive width and height.")
        return x0, y0, x1, y1

    def accept(self) -> None:
        try:
            self.to_bbox()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid bbox", str(exc))
            return
        super().accept()


class DetectionScaleDialog(QDialog):
    """Dialog for scaling one molecular detection bbox."""

    def __init__(self, parent: QWidget | None = None, scale_factor: float = 1.0) -> None:
        super().__init__(parent)
        self.setWindowTitle("Scale BBox")

        layout = QFormLayout(self)
        self.scale_spin = QDoubleSpinBox(self)
        self.scale_spin.setRange(0.05, 10.0)
        self.scale_spin.setSingleStep(0.05)
        self.scale_spin.setDecimals(3)
        self.scale_spin.setValue(_valid_bbox_scale_factor(scale_factor))
        self.scale_spin.setPrefix("Scale x ")
        layout.addRow("Factor", self.scale_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @classmethod
    def get_scale_factor(
        cls,
        parent: QWidget | None,
        scale_factor: float = 1.0,
    ) -> float | None:
        dialog = cls(parent, scale_factor)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.to_scale_factor()

    def to_scale_factor(self) -> float:
        return _valid_bbox_scale_factor(self.scale_spin.value())


class AnalysisRegionRectDialog(QDialog):
    """Dialog for creating or editing a rectangular analysis region."""

    def __init__(self, parent: QWidget | None = None, region: AnalysisRegion | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rect Region")

        layout = QFormLayout(self)
        self.kind_combo = QComboBox(self)
        self.kind_combo.addItem("Terrace", AnalysisRegionKind.TERRACE.value)
        self.kind_combo.addItem("Step edge", AnalysisRegionKind.STEP_EDGE.value)
        self.kind_combo.addItem("Ignore", AnalysisRegionKind.IGNORE.value)
        self.kind_combo.addItem("Custom", AnalysisRegionKind.CUSTOM.value)
        layout.addRow("Type", self.kind_combo)

        self.name_edit = QLineEdit(self)
        layout.addRow("Name", self.name_edit)

        self.red_spin = _rgb_spinbox(self)
        self.green_spin = _rgb_spinbox(self)
        self.blue_spin = _rgb_spinbox(self)
        color_widget = QWidget(self)
        color_layout = QHBoxLayout(color_widget)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.red_spin)
        color_layout.addWidget(self.green_spin)
        color_layout.addWidget(self.blue_spin)
        layout.addRow("RGB", color_widget)

        self.x0_spin = _coordinate_spinbox(self)
        self.y0_spin = _coordinate_spinbox(self)
        self.x1_spin = _coordinate_spinbox(self)
        self.y1_spin = _coordinate_spinbox(self)
        layout.addRow("x0", self.x0_spin)
        layout.addRow("y0", self.y0_spin)
        layout.addRow("x1", self.x1_spin)
        layout.addRow("y1", self.y1_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

        self._set_defaults(region)

    @classmethod
    def get_region(
        cls,
        parent: QWidget | None,
        region: AnalysisRegion | None = None,
    ) -> AnalysisRegion | None:
        dialog = cls(parent, region)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.to_region()

    def to_region(self) -> AnalysisRegion:
        return AnalysisRegion.rectangle(
            kind=self.kind_combo.currentData(),
            name=self.name_edit.text(),
            color_rgb=(self.red_spin.value(), self.green_spin.value(), self.blue_spin.value()),
            rect_xyxy=(
                self.x0_spin.value(),
                self.y0_spin.value(),
                self.x1_spin.value(),
                self.y1_spin.value(),
            ),
        )

    def accept(self) -> None:
        try:
            self.to_region()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid region", str(exc))
            return
        super().accept()

    def _set_defaults(self, region: AnalysisRegion | None) -> None:
        if region is None:
            self.kind_combo.setCurrentIndex(0)
            self.name_edit.setText("Region")
            self.red_spin.setValue(20)
            self.green_spin.setValue(120)
            self.blue_spin.setValue(240)
            self.x0_spin.setValue(0.0)
            self.y0_spin.setValue(0.0)
            self.x1_spin.setValue(1.0)
            self.y1_spin.setValue(1.0)
            return
        if region.rect_xyxy is None:
            raise ValueError("AnalysisRegionRectDialog only supports rectangular regions.")
        kind_index = self.kind_combo.findData(region.kind.value)
        self.kind_combo.setCurrentIndex(max(kind_index, 0))
        self.name_edit.setText(region.name)
        self.red_spin.setValue(region.color_rgb[0])
        self.green_spin.setValue(region.color_rgb[1])
        self.blue_spin.setValue(region.color_rgb[2])
        x0, y0, x1, y1 = region.rect_xyxy
        self.x0_spin.setValue(x0)
        self.y0_spin.setValue(y0)
        self.x1_spin.setValue(x1)
        self.y1_spin.setValue(y1)


def _rgb_spinbox(parent: QWidget) -> QSpinBox:
    spin = QSpinBox(parent)
    spin.setRange(0, 255)
    return spin


def _coordinate_spinbox(parent: QWidget) -> QDoubleSpinBox:
    spin = QDoubleSpinBox(parent)
    spin.setRange(-1_000_000.0, 1_000_000.0)
    spin.setDecimals(6)
    return spin


class AnalysisRegionFrameRangeDialog(QDialog):
    """Dialog for selecting the working-frame range where a region geometry is active."""

    def __init__(
        self,
        parent: QWidget | None,
        frame_count: int,
        current_working_frame_index: int = 0,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Region Frame Range")
        frame_count = int(frame_count)
        if frame_count <= 0:
            raise ValueError("frame_count must be positive.")
        current_working_frame_index = min(max(int(current_working_frame_index), 0), frame_count - 1)

        layout = QFormLayout(self)
        self.start_spin = QSpinBox(self)
        self.start_spin.setRange(0, frame_count - 1)
        self.start_spin.setValue(current_working_frame_index)
        layout.addRow("Start frame", self.start_spin)

        self.end_spin = QSpinBox(self)
        self.end_spin.setRange(0, frame_count - 1)
        self.end_spin.setValue(frame_count - 1)
        layout.addRow("End frame", self.end_spin)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @classmethod
    def get_working_frame_indices(
        cls,
        parent: QWidget | None,
        frame_count: int,
        current_working_frame_index: int = 0,
    ) -> tuple[int, ...] | None:
        dialog = cls(parent, frame_count, current_working_frame_index)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.working_frame_indices()

    def working_frame_indices(self) -> tuple[int, ...]:
        start = int(self.start_spin.value())
        end = int(self.end_spin.value())
        if end < start:
            raise ValueError("End frame must be greater than or equal to start frame.")
        return tuple(range(start, end + 1))

    def accept(self) -> None:
        try:
            self.working_frame_indices()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid frame range", str(exc))
            return
        super().accept()


class AnalysisRegionEditScopeDialog(QDialog):
    """Dialog asking whether an edit changes one active frame scope or the logical region."""

    CURRENT_SCOPE = "current_scope"
    LOGICAL_REGION = "logical_region"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Region Scope")

        layout = QFormLayout(self)
        self.scope_combo = QComboBox(self)
        self.scope_combo.addItem("Current frame range", self.CURRENT_SCOPE)
        self.scope_combo.addItem("Logical region", self.LOGICAL_REGION)
        layout.addRow("Apply edit to", self.scope_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @classmethod
    def get_scope(cls, parent: QWidget | None = None) -> str | None:
        dialog = cls(parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return str(dialog.scope_combo.currentData())


class AnalysisRegionMetadataDialog(QDialog):
    """Dialog for naming a drawn analysis region."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Drawn Region")

        layout = QFormLayout(self)
        self.kind_combo = QComboBox(self)
        self.kind_combo.addItem("Terrace", AnalysisRegionKind.TERRACE.value)
        self.kind_combo.addItem("Step edge", AnalysisRegionKind.STEP_EDGE.value)
        self.kind_combo.addItem("Ignore", AnalysisRegionKind.IGNORE.value)
        self.kind_combo.addItem("Custom", AnalysisRegionKind.CUSTOM.value)
        layout.addRow("Type", self.kind_combo)

        self.name_edit = QLineEdit(self)
        self.name_edit.setText("Region")
        layout.addRow("Name", self.name_edit)

        self.red_spin = _rgb_spinbox(self)
        self.green_spin = _rgb_spinbox(self)
        self.blue_spin = _rgb_spinbox(self)
        self.red_spin.setValue(20)
        self.green_spin.setValue(120)
        self.blue_spin.setValue(240)
        color_widget = QWidget(self)
        color_layout = QHBoxLayout(color_widget)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.addWidget(self.red_spin)
        color_layout.addWidget(self.green_spin)
        color_layout.addWidget(self.blue_spin)
        layout.addRow("RGB", color_widget)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    @classmethod
    def get_metadata(cls, parent: QWidget | None):
        dialog = cls(parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.metadata()

    def metadata(self) -> tuple[str, str, tuple[int, int, int]]:
        name = self.name_edit.text().strip()
        if not name:
            raise ValueError("Analysis region name must be a non-empty string.")
        return (
            self.kind_combo.currentData(),
            name,
            (self.red_spin.value(), self.green_spin.value(), self.blue_spin.value()),
        )

    def accept(self) -> None:
        try:
            self.metadata()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid region", str(exc))
            return
        super().accept()


def _terrace_overlap_warnings(project: MolTrackProject) -> list[str]:
    warnings = []
    for working_frame_index in range(project.working_series.frame_count):
        terraces = [
            region
            for region in project.analysis_regions_for_working_frame(working_frame_index)
            if region.kind == AnalysisRegionKind.TERRACE
        ]
        for left_index, left_region in enumerate(terraces):
            for right_region in terraces[left_index + 1:]:
                if _regions_overlap(left_region, right_region):
                    warnings.append(
                        "Terrace regions overlap on working frame "
                        f"{working_frame_index}: {left_region.name!r} and {right_region.name!r}."
                    )
    return warnings


def _regions_overlap(left_region: AnalysisRegion, right_region: AnalysisRegion) -> bool:
    left_x0, left_y0, left_x1, left_y1 = left_region.bounds_xyxy
    right_x0, right_y0, right_x1, right_y1 = right_region.bounds_xyxy
    return left_x0 < right_x1 and right_x0 < left_x1 and left_y0 < right_y1 and right_y0 < left_y1
