from __future__ import annotations

from pathlib import Path
import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from moltrack.core import (
    AnalysisRegion,
    AnalysisRegionKind,
    CopiedAnalysisRegion,
    FrameScopedAnalysisRegion,
    MolTrackProject,
)
from moltrack.io import import_image_series
from moltrack.persistence import load_project, save_project
from napara.gui.widgets.viewer_widget import ViewerWidget


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
        self._analysis_regions: dict[str, AnalysisRegion] = {}
        self._analysis_region_items: dict[str, object] = {}
        self._copied_analysis_regions: dict[str, CopiedAnalysisRegion] = {}
        self._frame_scoped_analysis_regions: list[FrameScopedAnalysisRegion] = []
        self._draft_region_roi = None
        self._draft_region_roi_kind: str | None = None
        self._build_menu()

        central = QWidget(self)
        root_layout = QHBoxLayout(central)
        viewer_panel = QWidget(central)
        layout = QVBoxLayout(viewer_panel)
        self.lbl_title = QLabel("MolTrack Workspace", central)
        self.lbl_frame_index = QLabel("No project loaded", central)
        self.lbl_frame_index.setObjectName("moltrack-frame-index-label")

        self.viewer = ViewerWidget(central)

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

    def _build_regions_panel(self, parent: QWidget) -> QWidget:
        panel = QWidget(parent)
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("Regions", panel))

        self.region_list = QListWidget(panel)
        self.region_list.setObjectName("moltrack-region-list")
        layout.addWidget(self.region_list, 1)

        add_button = QPushButton("Add Rect", panel)
        add_button.clicked.connect(lambda: self.add_rect_region_action.trigger())
        layout.addWidget(add_button)

        draw_rect_button = QPushButton("Draw ROI", panel)
        draw_rect_button.clicked.connect(lambda: self.draw_rect_region_roi_action.trigger())
        layout.addWidget(draw_rect_button)

        draw_poly_button = QPushButton("Draw Polyline", panel)
        draw_poly_button.clicked.connect(lambda: self.draw_polyline_region_action.trigger())
        layout.addWidget(draw_poly_button)

        commit_button = QPushButton("Commit Drawn", panel)
        commit_button.clicked.connect(lambda: self.commit_drawn_region_action.trigger())
        layout.addWidget(commit_button)

        apply_current_button = QPushButton("Apply Current", panel)
        apply_current_button.clicked.connect(lambda: self.apply_selected_region_to_current_frame_action.trigger())
        layout.addWidget(apply_current_button)

        copy_to_end_button = QPushButton("Copy to End", panel)
        copy_to_end_button.clicked.connect(lambda: self.copy_selected_region_from_current_to_end_action.trigger())
        layout.addWidget(copy_to_end_button)

        copy_range_button = QPushButton("Copy Range", panel)
        copy_range_button.clicked.connect(lambda: self.copy_selected_region_to_frame_range_action.trigger())
        layout.addWidget(copy_range_button)

        edit_button = QPushButton("Edit", panel)
        edit_button.clicked.connect(lambda: self.edit_selected_region_action.trigger())
        layout.addWidget(edit_button)

        delete_button = QPushButton("Delete", panel)
        delete_button.clicked.connect(lambda: self.delete_selected_region_action.trigger())
        layout.addWidget(delete_button)

        copy_button = QPushButton("Copy to Series", panel)
        copy_button.clicked.connect(lambda: self.copy_selected_region_to_series_action.trigger())
        layout.addWidget(copy_button)

        return panel

    def set_project(self, project: MolTrackProject) -> None:
        self._project = project
        self.clear_drawn_region_roi()
        self._clear_analysis_region_overlays()
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
            frame = self._project.source_series.get_frame(working_frame.source_frame_index)
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
        )
        self._redraw_analysis_region_overlays()

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

    def copy_analysis_region_to_series(self, region_name: str) -> CopiedAnalysisRegion:
        if self._project is None:
            raise ValueError("No MolTrack project is loaded.")
        region_name = str(region_name)
        if region_name not in self._analysis_regions:
            raise KeyError(f"Unknown analysis region: {region_name}")
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

    def _draw_analysis_region(self, region: AnalysisRegion) -> None:
        item = self.viewer.add_polyline_nm(
            _analysis_region_polyline(region),
            name=region.name,
            color=region.color_rgb,
            width=2.0,
        )
        self._analysis_region_items[region.name] = item

    def _remove_analysis_region_overlay(self, region_name: str) -> None:
        item = self._analysis_region_items.pop(region_name, None)
        if item is not None:
            self.viewer.remove_item(item)

    def _clear_analysis_region_overlays(self) -> None:
        for item in self._analysis_region_items.values():
            self.viewer.remove_item(item)
        self._analysis_region_items = {}

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

    def _on_add_rect_region(self) -> None:
        if self._project is None:
            QMessageBox.warning(self, "Add region", "Load or import a project before adding regions.")
            return
        region = AnalysisRegionRectDialog.get_region(self)
        if region is None:
            return
        try:
            self.add_analysis_region(region)
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
                self.apply_analysis_region_to_frames(
                    region.name,
                    frame_indices,
                    region=region,
                )
            else:
                self.add_analysis_region(region)
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

    def _on_copy_selected_region_to_series(self) -> None:
        region_name = self.selected_region_name()
        if region_name is None:
            QMessageBox.warning(self, "Copy region", "Select a region to copy to the series.")
            return
        try:
            self.copy_analysis_region_to_series(region_name)
        except Exception as exc:
            QMessageBox.critical(self, "Copy region failed", str(exc))

    def _on_apply_selected_region_to_current_frame(self) -> None:
        region_name = self.selected_region_name()
        if region_name is None:
            QMessageBox.warning(self, "Apply region", "Select a region to apply to the current frame.")
            return
        try:
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
        x0, y0, x1, y1 = region.rect_xyxy
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

    vertices = np.asarray(region.polygon_xy, dtype=np.float64)
    if np.allclose(vertices[0], vertices[-1]):
        return vertices
    return np.vstack([vertices, vertices[0]])


def _sorted_rect_xyxy(rect_xyxy) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = (float(value) for value in rect_xyxy)
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


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
