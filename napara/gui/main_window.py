from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow, QFileDialog, QMessageBox, QWidget, QDockWidget, QVBoxLayout, QDialog
)

from .panels.image_list_panel import ImageListPanel
from .panels.processing_panel import ProcessingPanel
from .widgets.metadata_widget import MetadataWidget
from .widgets.viewer_widget import ViewerWidget
from napara.logic.roi_manager import ROIManager
from napara.processing.pipeline_spec import PipelineSpec
from .dialogs.preprocessing_dialog import PreprocessingDialog

import os
import numpy as np
from collections import defaultdict

from napara.io.factory import load_from_paths
from napara.processing.pipeline import run_pipeline

class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Holds loaded STMImage objects flattened (STP/S94 -> 1 each; MPP -> many frames)
        self._images = []  # list[STMImage]
        self._contours_by_image = {}  # dict[int, list[np.ndarray]]  # per-image detected contours
        self._overlay_items = {}      # dict[int, list[pg.PlotDataItem]]  # drawn items per image
        self._spec = PipelineSpec()   # default pipeline
        self._active_index = None  # int | None
        self.detections = defaultdict(list)
        self._setup_ui()
        self._connect_signals()

        self.roi_manager = ROIManager(self.viewer.get_plot_item(), self)
        self.roi_manager.roiAdded.connect(self.on_roi_added)
        self.roi_manager.roiChanged.connect(self.on_roi_changed)
        # self.roi_manager.roiRemoved.connect(self.on_roi_removed)
        self.roi_manager.roiSelected.connect(self.on_roi_selected)

    def _setup_ui(self):
        self.setWindowTitle("NaParA – Nanoparticle Analyzer")
        self.resize(1200, 800)
        self._create_menu()
        self._create_central()
        self._create_docks()
        self.statusBar().showMessage("Ready")

    def _create_central(self):
        from PyQt6.QtWidgets import QSplitter
        from PyQt6.QtCore import Qt

        # widgets
        self.meta_widget = MetadataWidget(self)
        from .widgets.roi_preview_widget import ROIPreviewWidget
        self.roi_preview = ROIPreviewWidget(self)
        self.viewer = ViewerWidget(self)

        self.viewer.lutChanged.connect(self._update_roi_preview)

        # top: meta | preview
        top_split = QSplitter(Qt.Orientation.Horizontal, self)
        top_split.addWidget(self.meta_widget)
        top_split.addWidget(self.roi_preview)
        top_split.setStretchFactor(0, 10)
        top_split.setStretchFactor(1, 1)

        # main: (top) / (viewer)
        main_split = QSplitter(Qt.Orientation.Vertical, self)
        main_split.addWidget(top_split)
        main_split.addWidget(self.viewer)
        main_split.setStretchFactor(0, 0)
        main_split.setStretchFactor(10, 1)

        self.setCentralWidget(main_split)

    def _update_roi_preview(self):
        """
        Run a lightweight version of the pipeline on the ROI
        and show the result in the preview widget.
        """
        if self._active_index is None or not self._images:
            self.roi_preview.clear()
            return

        img = self._images[self._active_index]
        roi_rect_nm = self._get_active_roi_rect_nm()
        if not roi_rect_nm:
            self.roi_preview.clear()
            return
        
        if img.preprocessed_data is not None:
            source_data = img.preprocessed_data
            self.roi_preview.title.setText("ROI Preview (Processed)")
        else:
            source_data = img.data
            self.roi_preview.title.setText("ROI Preview (Original)")
        
        # Get physical scaling and current viewer visual settings
        px_x, px_y = img.get_pixel_size_nm()
        levels = self.viewer.image_item.getLevels()
        lut = self.viewer.image_item.lut

        try:
            result = run_pipeline(
                source_data,
                roi_rect_nm=roi_rect_nm,
                nm_per_px=(px_x, px_y),
                spec=self._spec
            )
            processed_roi_img = result["debug"]["roi_preview"]
        except Exception as e:
            print(f"Error during preview update: {e}")
            self.roi_preview.clear()
            return

        self.roi_preview.set_preview(
            processed_roi_img,
            (px_x, px_y),
            levels=levels,
            lut=lut
        )

    def _create_docks(self):
        self.image_list_panel = ImageListPanel(self)
        dock_left = QDockWidget("Images", self)
        dock_left.setWidget(self.image_list_panel)
        dock_left.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock_left)

        self.proc_panel = ProcessingPanel(self)
        dock_right = QDockWidget("Processing", self)
        dock_right.setWidget(self.proc_panel)
        dock_right.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock_right)

    def _connect_signals(self):
        """Connect UI signals to handlers."""
        # Image list: add/remove and selection change
        self.image_list_panel.btn_add.clicked.connect(self.on_add_images_clicked)
        self.image_list_panel.btn_remove.clicked.connect(self.on_remove_selected_clicked)
        self.image_list_panel.list.currentRowChanged.connect(self.on_image_selected)

        self.proc_panel.cb_gauss.stateChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_sigma.valueChanged.connect(self._on_spec_changed)

        self.proc_panel.cb_median.stateChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_med.valueChanged.connect(self._on_spec_changed)

        self.proc_panel.cb_tophat.stateChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_tophat.valueChanged.connect(self._on_spec_changed)

        self.proc_panel.cb_thresh.stateChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_min_area.valueChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_otsu_bias.valueChanged.connect(self._on_spec_changed)
        self.proc_panel.cmb_thresh_mode.currentIndexChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_sauvola_win.valueChanged.connect(self._on_spec_changed)
        self.proc_panel.sp_sauvola_k.valueChanged.connect(self._on_spec_changed)

        self.proc_panel.cb_detect.stateChanged.connect(self._on_spec_changed)

        self.proc_panel.btn_detect.clicked.connect(self.on_detect_roi)

    def _on_spec_changed(self):
        """
        Update the spec object from UI controls and refresh the ROI preview.
        This acts as a live preview handler.
        """
        if self._active_index is None:
            return

        self._spec.gaussian_blur  = self.proc_panel.cb_gauss.isChecked()
        self._spec.gaussian_sigma = float(self.proc_panel.sp_sigma.value())

        self._spec.median_filter  = self.proc_panel.cb_median.isChecked()
        self._spec.median_size    = int(self.proc_panel.sp_med.value())

        self._spec.white_top_hat  = self.proc_panel.cb_tophat.isChecked()
        self._spec.wth_radius_px  = int(self.proc_panel.sp_tophat.value())

        self._spec.threshold_enable = self.proc_panel.cb_thresh.isChecked()
        self._spec.threshold_mode   = "sauvola" if self.proc_panel.cmb_thresh_mode.currentIndex()==1 else "otsu"
        self._spec.min_area_px      = int(self.proc_panel.sp_min_area.value())
        self._spec.threshold_bias   = float(self.proc_panel.sp_otsu_bias.value())
        self._spec.sauvola_window   = int(self.proc_panel.sp_sauvola_win.value())
        self._spec.sauvola_k        = float(self.proc_panel.sp_sauvola_k.value())

        self._spec.detect_enable    = self.proc_panel.cb_detect.isChecked()

        self._update_roi_preview()

    def _create_menu(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        self.act_open_project = QAction("Open Project…", self)
        self.act_open_project.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open_project.triggered.connect(self.on_open_project)
        file_menu.addAction(self.act_open_project)

        self.act_quickload = QAction("Quick Load", self)
        self.act_quickload.setShortcut("Ctrl+L")
        self.act_quickload.triggered.connect(self.on_quick_load)
        file_menu.addAction(self.act_quickload)

        file_menu.addSeparator()

        self.act_save = QAction("Save", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.triggered.connect(self.on_save)
        file_menu.addAction(self.act_save)

        self.act_save_as = QAction("Save As…", self)
        self.act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_save_as.triggered.connect(self.on_save_as)
        file_menu.addAction(self.act_save_as)

        self.act_quicksave = QAction("Quick Save", self)
        self.act_quicksave.setShortcut("Ctrl+S")
        self.act_quicksave.triggered.connect(self.on_quick_save)
        file_menu.addAction(self.act_quicksave)

        file_menu.addSeparator()

        self.act_exit = QAction("Exit", self)
        self.act_exit.setShortcut(QKeySequence.StandardKey.Quit)
        self.act_exit.triggered.connect(self.close)
        file_menu.addAction(self.act_exit)

        edit_menu = menubar.addMenu("&Edit")
        self.act_undo = QAction("Undo", self); self.act_undo.setShortcut(QKeySequence.StandardKey.Undo); self.act_undo.setEnabled(False)
        self.act_redo = QAction("Redo", self); self.act_redo.setShortcut(QKeySequence.StandardKey.Redo); self.act_redo.setEnabled(False)
        edit_menu.addAction(self.act_undo); edit_menu.addAction(self.act_redo)

        an_menu = menubar.addMenu("&Analyze")
        self.act_detect_roi = QAction("Detect (ROI)", self)
        self.act_detect_roi.setShortcut("D")
        self.act_detect_roi.triggered.connect(self.on_detect_roi)
        an_menu.addAction(self.act_detect_roi)
        self.act_preprocess = QAction("Full Image Preprocessing...", self)
        self.act_preprocess.triggered.connect(self.on_preprocess_image)
        an_menu.addAction(self.act_preprocess)

        view_menu = menubar.addMenu("&View")
        self.act_toggle_statusbar = QAction("Status Bar", self, checkable=True, checked=True)
        self.act_toggle_statusbar.triggered.connect(self.on_toggle_statusbar)
        view_menu.addAction(self.act_toggle_statusbar)

        self.act_reset_roi = QAction("Reset ROI", self)
        self.act_reset_roi.triggered.connect(self.on_add_rect_roi)
        view_menu.addAction(self.act_reset_roi)

        help_menu = menubar.addMenu("&Help")
        self.act_about = QAction("About NaParA", self); self.act_about.triggered.connect(self.on_about)
        help_menu.addAction(self.act_about)

    def _get_active_roi_rect_nm(self):
        """Return (x,y,w,h) in nm for current image ROI; None if missing.
        If polygon ROI exists, use its bounding rect (warn once)."""
        idx = self._active_index
        if idx is None:
            return None
        # Rect ROI
        rect = self.roi_manager.get_rect(idx)
        if rect is not None:
            return (rect.x(), rect.y(), rect.width(), rect.height())
        # Poly ROI -> fallback to bounding rect
        poly = self.roi_manager.get_polygon(idx)
        if poly:
            xs = [p.x() for p in poly]; ys = [p.y() for p in poly]
            x, y = min(xs), min(ys); w, h = max(xs)-x, max(ys)-y
            # Optional: QMessageBox.information(self, "...", "Polygon ROI treated as bounding box.")
            return (x, y, w, h)
        return None

    @staticmethod
    def _centroid(contour_xy: np.ndarray) -> tuple[float, float]:
        """Return (cx, cy) in pixel coords for Nx2 contour array."""
        if contour_xy.size == 0:
            return (0.0, 0.0)
        cx = float(np.mean(contour_xy[:, 0]))
        cy = float(np.mean(contour_xy[:, 1]))
        return (cx, cy)

    @staticmethod
    def _point_in_rect_px(pt: tuple[float, float], rect_nm: tuple[float, float, float, float], nm_per_px: tuple[float | None, float | None]) -> bool:
        """Check if pixel point is inside nm-rect (convert rect to px)."""
        sx, sy = nm_per_px
        x_nm, y_nm, w_nm, h_nm = rect_nm
        if not sx or not sy or sx <= 0 or sy <= 0:
            return False
        x0 = x_nm / sx; y0 = y_nm / sy
        x1 = (x_nm + w_nm) / sx; y1 = (y_nm + h_nm) / sy
        px, py = pt
        return (x0 <= px <= x1) and (y0 <= py <= y1)

    def _clear_overlays(self, image_index: int):
        """Remove existing contour items for given image."""
        items = self._overlay_items.get(image_index, [])
        for it in items:
            try:
                self.viewer.get_plot_item().removeItem(it)
            except Exception:
                pass
        self._overlay_items[image_index] = []

    def _draw_contours(self, image_index: int, contours: list[np.ndarray]):
        """Draw contours as polyline overlays in NM coordinates (viewer axes are in nm)."""
        from pyqtgraph import PlotDataItem, mkPen
        self._clear_overlays(image_index)

        # Get nm/px scaling for this image
        img = self._images[image_index]
        sx, sy = img.get_pixel_size_nm()  # returns (nm_x_per_px, nm_y_per_px)

        items = []
        for c in contours:
            if c.shape[0] < 2:
                continue
            # Convert pixel coords -> nm to match PlotItem axes
            x_nm = c[:, 0] * (sx or 1.0)
            y_nm = c[:, 1] * (sy or 1.0)
            item = PlotDataItem(x_nm, y_nm, pen=mkPen((0, 255, 0), width=2))
            self.viewer.get_plot_item().addItem(item)
            items.append(item)

        self._overlay_items[image_index] = items

    def on_preprocess_image(self):
        if self._active_index is None:
            QMessageBox.warning(self, "No Image", "Please select an image to preprocess.")
            return

        active_image_obj = self._images[self._active_index]

        dialog = PreprocessingDialog(active_image_obj.data, self)
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            processed_data = dialog.get_processed_image()
            if processed_data is not None:
                active_image_obj.preprocessed_data = processed_data
                self.statusBar().showMessage("Image preprocessed successfully.", 4000)
                self._update_roi_preview()
            else:
                self.statusBar().showMessage("Preprocessing was accepted, but no data was returned.", 4000)

    def on_detect_roi(self):
        if self._active_index is None:
            return
        if not self.proc_panel.cb_detect.isChecked():
            self._clear_overlays(self._active_index)
            self.statusBar().showMessage("Detection disabled.", 2000)
            return

        img = self._images[self._active_index]
        roi_rect_nm = self._get_active_roi_rect_nm()
        if roi_rect_nm is None:
            QMessageBox.information(self, "ROI required", "Please create a ROI (View → Add/Reset Rect ROI) and try again.")
            return

        px_x, px_y = img.get_pixel_size_nm()

        res = run_pipeline(
            img.preprocessed_data if img.preprocessed_data is not None else img.data,
            roi_rect_nm=roi_rect_nm,
            nm_per_px=(px_x, px_y),
            spec=self._spec,
        )
        new_contours = res["contours"]  # w px

        # Overwrite policy: drop existing contours whose centroid ∈ ROI, then add new
        existing = self._contours_by_image.get(self._active_index, [])
        kept = []
        for c in existing:
            if not self._point_in_rect_px(self._centroid(c), roi_rect_nm, (px_x, px_y)):
                kept.append(c)
        merged = kept + new_contours
        self._contours_by_image[self._active_index] = merged

        # Draw overlays for current image
        self._draw_contours(self._active_index, merged)

        # Optional: status
        self.statusBar().showMessage(f"Detected {len(new_contours)} objects (total: {len(merged)}).", 5000)

    def on_add_images_clicked(self):
        """
        Open a file dialog to load multiple STP/S94 files or a single MPP file.
        STP/S94: multiple selection allowed; each path -> 1 STMImage.
        MPP: only one file at a time (UI allows multi, but we'll expand frames).
        """
        # Build filter: multiple extensions
        filt = "STM files (*.stp *.STP *.s94 *.S94 *.mpp *.MPP);;All files (*.*)"
        paths, _ = QFileDialog.getOpenFileNames(self, "Add STM files", "", filt)
        if not paths:
            return

        try:
            new_images = load_from_paths(paths)  # flattens frames for MPP
        except Exception as e:
            QMessageBox.critical(self, "Load error", f"Failed to load files:\n{e}")
            return

        if not new_images:
            QMessageBox.information(self, "No data", "No images were loaded from the selected files.")
            return

        # Extend internal list and refresh UI
        start_index = len(self._images)
        self._images.extend(new_images)
        self._update_image_list(new_items=new_images, start_index=start_index)

        # Select first newly added item to display it immediately
        if start_index < len(self._images):
            self.image_list_panel.list.setCurrentRow(start_index)

        self.statusBar().showMessage(f"Loaded {len(new_images)} image(s).", 4000)

    def _update_image_list(self, new_items, start_index: int):
        """
        Append loaded items to the QListWidget using short labels:
        - STP/S94: show only 'filename.ext'
        - MPP frames: show 'filename.ext  [frame N]'
        """
        lst = self.image_list_panel.list
        for img in new_items:
            base = os.path.basename(str(img.file_name))  # strip directories
            if getattr(img, "frame_index", None) is not None:
                label = f"{base}  [frame {img.frame_index}]"
            else:
                label = base
            lst.addItem(label)

    def on_remove_selected_clicked(self):
        """
        Remove the currently selected image entry from the list and memory.
        """
        row = self.image_list_panel.list.currentRow()
        if row < 0 or row >= len(self._images):
            return
        # Remove from data and UI
        del self._images[row]
        self.image_list_panel.list.takeItem(row)
        # Clear viewer if nothing selected
        if not self._images:
            self._active_index = None
            self.viewer.clear()
            self.meta_widget.set_metadata(filename="", shape=None, scale_nm_per_px=None, channel=None)
            return
        # Adjust selection to a valid index
        new_row = max(0, min(row, len(self._images) - 1))
        self.image_list_panel.list.setCurrentRow(new_row)

    def on_image_selected(self, row: int):
        """
        Update central viewer and metadata when a list entry is selected.
        """
        if row < 0 or row >= len(self._images):
            return
        self._active_index = row
        img = self._images[row]

        # Physical pixel sizes (nm/px)
        px_x, px_y = img.get_pixel_size_nm()

        # Pass image and physical scaling; preserve zoom between images
        self.viewer.set_image(
            img.data,
            scale_nm_per_px=(px_x, px_y),     # maps px grid to nm
            preserve_zoom=True,               # keep current zoom/pan
            auto_levels=True
        )

        # Metadata: include physical size in nm
        self.meta_widget.set_metadata(
            filename=str(img.file_name),
            shape=(img.pixels_y, img.pixels_x),
            size_nm=(img.size_nm_x, img.size_nm_y), 
            scale_nm_per_px=px_x if px_x else None,
            channel=img.image_type
        )

        self.roi_manager.set_active_image(self._active_index)
        if not self.roi_manager.has_roi(self._active_index):
            self.roi_manager.add_centered_rect(self._active_index, size_nm=20.0)
        conts = self._contours_by_image.get(self._active_index, [])
        self._draw_contours(self._active_index, conts)
        self._update_roi_preview()

    def on_open_project(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Project", "", "NaParA Project (*.json *.napara)")
        if path:
            self.statusBar().showMessage(f"Opened project: {path}", 4000)

    def on_quick_load(self):
        self.statusBar().showMessage("Quick Load… (stub)", 3000)

    def on_save(self):
        self.statusBar().showMessage("Save… (stub)", 3000)

    def on_save_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Project As", "", "NaParA Project (*.json)")
        if path:
            self.statusBar().showMessage(f"Saved project as: {path}", 4000)

    def on_quick_save(self):
        self.statusBar().showMessage("Quick Save… (stub)", 3000)

    def on_toggle_statusbar(self, checked: bool):
        self.statusBar().setVisible(checked)

    def on_about(self):
        QMessageBox.about(
            self,
            "About NaParA",
            "<b>NaParA – Nanoparticle Analyzer</b><br>"
            "PyQt6 application for ROI‑driven nanoparticle detection on STM images."
        )
    
    # ROI actions:
    def on_add_rect_roi(self):
        if self._active_index is None:
            return
        # Create centered 20 nm square in current view
        self.roi_manager.add_centered_rect(self._active_index, size_nm=20.0)

    # ROI signals (stubs for now)
    def on_roi_added(self, image_index: int):
        if image_index == self._active_index:
            self._update_roi_preview()

    def on_roi_changed(self, image_index: int):
        if image_index == self._active_index:
            self._update_roi_preview()

    def on_roi_removed(self, image_index: int):
        if image_index == self._active_index:
            self.roi_preview.clear()

    def on_roi_selected(self, image_index: int):
        if image_index == self._active_index:
            self._update_roi_preview()