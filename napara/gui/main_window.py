from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow, QFileDialog, QMessageBox, QWidget, QDockWidget, QVBoxLayout
)
from .panels.image_list_panel import ImageListPanel
from .panels.processing_panel import ProcessingPanel
from .widgets.metadata_widget import MetadataWidget
from .widgets.viewer_widget import ViewerWidget

class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

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
        # Metadata na górze
        self.meta_widget = MetadataWidget(self)
        v.addWidget(self.meta_widget)
        # Viewer pod spodem
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

    # --- Slots (stub) ---
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
