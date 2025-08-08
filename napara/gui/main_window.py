from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow, QFileDialog, QMessageBox, QWidget, QDockWidget, QVBoxLayout
)

from .panels.image_list_panel import ImageListPanel
from .panels.processing_panel import ProcessingPanel
from .widgets.metadata_widget import MetadataWidget
from .widgets.viewer_widget import ViewerWidget

from napara.io.factory import load_from_paths
import numpy as np  # for type hints / potential future use

class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Holds loaded STMImage objects flattened (STP/S94 -> 1 each; MPP -> many frames)
        self._images = []  # list[STMImage]
        self._active_index = None  # int | None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        self.setWindowTitle("NaParA – Nanoparticle Analyzer")
        self.resize(1200, 800)
        self._create_menu()
        self._create_central()
        self._create_docks()
        self.statusBar().showMessage("Ready")

    def _create_central(self):
        central = QWidget(self)
        v = QVBoxLayout(central)
        self.meta_widget = MetadataWidget(self)
        v.addWidget(self.meta_widget)
        self.viewer = ViewerWidget(self)
        v.addWidget(self.viewer, 1)
        self.setCentralWidget(central)

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

    # ---------------- MENU (unchanged stubs) ----------------
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

        view_menu = menubar.addMenu("&View")
        self.act_toggle_statusbar = QAction("Status Bar", self, checkable=True, checked=True)
        self.act_toggle_statusbar.triggered.connect(self.on_toggle_statusbar)
        view_menu.addAction(self.act_toggle_statusbar)

        help_menu = menubar.addMenu("&Help")
        self.act_about = QAction("About NaParA", self); self.act_about.triggered.connect(self.on_about)
        help_menu.addAction(self.act_about)

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
        Append loaded items to the QListWidget with readable labels.
        For MPP frames, include frame index in the label.
        """
        lst = self.image_list_panel.list
        for i, img in enumerate(new_items, start=0):
            # Build label
            base = img.file_name
            if getattr(img, "frame_index", None) is not None:
                label = f"{base}  [frame {img.frame_index}]  {img.pixels_x}×{img.pixels_y}px"
            else:
                label = f"{base}  {img.pixels_x}×{img.pixels_y}px"
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
