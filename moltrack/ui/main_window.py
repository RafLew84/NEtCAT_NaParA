from __future__ import annotations

from PyQt6.QtCore import QObject, QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from moltrack.core import (
    MolTrackRegistrationSettings,
    SUPPORTED_REGISTRATION_BACKENDS,
    build_moltrack_expanded_aligned_stack,
    run_moltrack_registration,
)
from moltrack.io import load_moltrack_image_series
from moltrack.ui.widgets import STMSeriesViewer, SeriesMetadataPanel


class _RegistrationRunWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, registration_runner, series, settings: MolTrackRegistrationSettings):
        super().__init__()
        self._registration_runner = registration_runner
        self._series = series
        self._settings = settings

    def run(self) -> None:
        try:
            result_set = self._registration_runner(self._series, settings=self._settings)
        except Exception as exc:
            self.failed.emit(str(exc) or exc.__class__.__name__)
            return
        self.finished.emit(result_set)


class MolTrackMainWindow(QMainWindow):
    """Initial empty workspace for MolTrack."""

    def __init__(
        self,
        parent=None,
        *,
        series_loader=load_moltrack_image_series,
        registration_runner=run_moltrack_registration,
        expanded_aligned_builder=build_moltrack_expanded_aligned_stack,
    ):
        super().__init__(parent)
        self._series = None
        self._series_loader = series_loader
        self._registration_runner = registration_runner
        self._expanded_aligned_builder = expanded_aligned_builder
        self._registration_running = False
        self._registration_progress_dialog: QProgressDialog | None = None
        self._registration_thread: QThread | None = None
        self._registration_worker: _RegistrationRunWorker | None = None
        self.setWindowTitle("MolTrack")
        self.resize(1280, 860)
        self._build_actions()
        self._build_central_widget()
        self._connect_signals()
        self._update_navigation_enabled(False)
        self.statusBar().showMessage("Ready")

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        self.action_open_stm = QAction("Open STM...", self)
        self.action_open_stm.setToolTip("Load one MPP movie into MolTrack")
        self.action_open_stm_reverse = QAction("Open STM Reverse...", self)
        self.action_open_stm_reverse.setToolTip("Load one MPP movie with reversed frame order")
        file_menu.addAction(self.action_open_stm)
        file_menu.addAction(self.action_open_stm_reverse)

    def _build_central_widget(self) -> None:
        central = QSplitter(Qt.Orientation.Horizontal, self)

        viewer_container = QWidget(self)
        viewer_layout = QVBoxLayout(viewer_container)
        self.viewer = STMSeriesViewer(viewer_container)
        viewer_layout.addWidget(self.viewer, 1)

        self.lbl_frame = QLabel("Frame: - / -", viewer_container)
        self.lbl_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        viewer_layout.addWidget(self.lbl_frame)

        self.slider_frame = QSlider(Qt.Orientation.Horizontal, viewer_container)
        self.slider_frame.setTracking(True)
        viewer_layout.addWidget(self.slider_frame)

        sidebar_content = QWidget(self)
        sidebar_layout = QVBoxLayout(sidebar_content)
        self.metadata_panel = SeriesMetadataPanel(sidebar_content)
        sidebar_layout.addWidget(self.metadata_panel)
        self.btn_remove_current_frame = QPushButton("Remove current frame", sidebar_content)
        self.btn_remove_current_frame.setToolTip("Delete the current frame from the working series")
        self.btn_remove_current_frame.setEnabled(False)
        sidebar_layout.addWidget(self.btn_remove_current_frame)

        self.registration_group = QGroupBox("Registration", sidebar_content)
        registration_layout = QVBoxLayout(self.registration_group)
        self.cmb_registration_backend = QComboBox(self.registration_group)
        self.cmb_registration_backend.addItems(SUPPORTED_REGISTRATION_BACKENDS)
        self.cmb_registration_backend.setEnabled(False)
        registration_layout.addWidget(self.cmb_registration_backend)
        self.btn_run_registration = QPushButton("Run registration", self.registration_group)
        self.btn_run_registration.setEnabled(False)
        registration_layout.addWidget(self.btn_run_registration)
        self.cmb_registration_view_mode = QComboBox(self.registration_group)
        self.cmb_registration_view_mode.addItems(["Show raw", "Show expanded aligned"])
        self.cmb_registration_view_mode.setEnabled(False)
        registration_layout.addWidget(self.cmb_registration_view_mode)
        self.lbl_registration_status = QLabel("No registration results", self.registration_group)
        self.lbl_registration_status.setWordWrap(True)
        registration_layout.addWidget(self.lbl_registration_status)
        sidebar_layout.addWidget(self.registration_group)

        sidebar_layout.addStretch(1)

        sidebar = QScrollArea(self)
        sidebar.setWidgetResizable(True)
        sidebar.setFrameShape(QScrollArea.Shape.NoFrame)
        sidebar.setWidget(sidebar_content)

        central.addWidget(viewer_container)
        central.addWidget(sidebar)
        central.setStretchFactor(0, 1)
        central.setStretchFactor(1, 0)
        central.setSizes([980, 300])
        self.setCentralWidget(central)

    def _update_navigation_enabled(self, enabled: bool) -> None:
        self.slider_frame.setEnabled(enabled)

    def _connect_signals(self) -> None:
        self.action_open_stm.triggered.connect(self._on_open_stm_requested)
        self.action_open_stm_reverse.triggered.connect(self._on_open_stm_reverse_requested)
        self.slider_frame.valueChanged.connect(self._on_frame_selected)
        self.btn_remove_current_frame.clicked.connect(self._on_remove_current_frame_requested)
        self.btn_run_registration.clicked.connect(self._on_run_registration_requested)
        self.cmb_registration_view_mode.currentTextChanged.connect(self._on_registration_view_mode_changed)

    def set_image_series(self, series) -> None:
        self._series = series
        self._set_registration_view_mode("Show raw")
        self._sync_navigation_controls()
        self.viewer.set_image_series(series)
        self.metadata_panel.set_image_series(series)

    def open_stm_source(self, source_path, *, reverse_frame_order: bool = False) -> None:
        series = self._series_loader(source_path, reverse_frame_order=reverse_frame_order)
        self.set_image_series(series)
        self.statusBar().showMessage(f"Loaded {series.source_path}", 3000)

    def _sync_navigation_controls(self) -> None:
        if self._series is None:
            self.lbl_frame.setText("Frame: - / -")
            self._update_navigation_enabled(False)
            self.btn_remove_current_frame.setEnabled(False)
            self.cmb_registration_backend.setEnabled(False)
            self.btn_run_registration.setEnabled(False)
            self.cmb_registration_view_mode.setEnabled(False)
            self._set_registration_view_mode("Show raw")
            self.lbl_registration_status.setText("No registration results")
            return

        controls_enabled = not self._registration_running
        self._update_navigation_enabled(controls_enabled)
        self.btn_remove_current_frame.setEnabled(controls_enabled and self._series.frame_count > 1)
        self.cmb_registration_backend.setEnabled(controls_enabled)
        self.btn_run_registration.setEnabled(controls_enabled)
        has_registration = self._series.registration_results is not None
        self.cmb_registration_view_mode.setEnabled(controls_enabled and has_registration)
        if not has_registration:
            self._set_registration_view_mode("Show raw")
        self._sync_registration_status()
        self.slider_frame.blockSignals(True)
        try:
            self.slider_frame.setRange(0, self._series.frame_count - 1)
            self.slider_frame.setValue(self._series.active_frame_index)
        finally:
            self.slider_frame.blockSignals(False)
        self.lbl_frame.setText(f"Frame: {self._series.active_frame_index + 1} / {self._series.frame_count}")

    def _show_current_frame(self) -> None:
        if self._series is None:
            self.viewer.clear()
            return
        if self._is_expanded_aligned_view_requested():
            try:
                expanded = self._ensure_expanded_aligned_stack()
            except Exception as exc:
                self._set_registration_view_mode("Show raw")
                QMessageBox.critical(self, "Expanded aligned view failed", str(exc))
                self.statusBar().showMessage("Expanded aligned view failed.", 3000)
            else:
                self.viewer.show_expanded_aligned_frame(
                    self._series,
                    expanded,
                    self._series.active_frame_index,
                )
                self.metadata_panel.set_image_series(self._series)
                return
        self.viewer.show_frame(self._series.active_frame_index)

    def _on_frame_selected(self, frame_index: int) -> None:
        if self._series is None:
            return
        self._series.set_active_frame(int(frame_index))
        self._sync_navigation_controls()
        self._show_current_frame()
        self.metadata_panel.set_active_frame(int(frame_index))

    def _on_remove_current_frame_requested(self) -> None:
        if self._series is None:
            return
        try:
            self._series.remove_frame()
        except ValueError as exc:
            QMessageBox.critical(self, "Remove frame failed", str(exc))
            self.statusBar().showMessage("Remove frame failed.", 3000)
            return
        self._set_registration_view_mode("Show raw")
        self._sync_navigation_controls()
        self._show_current_frame()
        self.metadata_panel.set_image_series(self._series)
        self.statusBar().showMessage("Removed current frame.", 3000)

    def _on_run_registration_requested(self) -> None:
        if self._series is None or self._registration_running:
            return
        settings = MolTrackRegistrationSettings(
            backend=self.cmb_registration_backend.currentText(),
        )
        self._registration_running = True
        self._set_file_actions_enabled(False)
        self._registration_progress_dialog = self._show_registration_progress_dialog(settings)
        self._sync_navigation_controls()
        self.lbl_registration_status.setText(f"Running {settings.backend} registration...")
        self.statusBar().showMessage(f"Running {settings.backend} registration...", 0)

        self._registration_thread = QThread(self)
        self._registration_worker = _RegistrationRunWorker(self._registration_runner, self._series, settings)
        self._registration_worker.moveToThread(self._registration_thread)
        self._registration_thread.started.connect(self._registration_worker.run)
        self._registration_worker.finished.connect(self._on_registration_finished)
        self._registration_worker.failed.connect(self._on_registration_failed)
        self._registration_worker.finished.connect(self._registration_thread.quit)
        self._registration_worker.failed.connect(self._registration_thread.quit)
        self._registration_thread.finished.connect(self._cleanup_registration_worker)
        self._registration_thread.start()

    def _on_registration_finished(self, result_set) -> None:
        if self._series is not None and self._series.registration_results is None:
            self._series.registration_results = result_set
        self._registration_running = False
        self._set_file_actions_enabled(True)
        self._close_registration_progress_dialog()
        self._sync_navigation_controls()
        self.lbl_registration_status.setText(
            f"Registered {result_set.result_count} frames with {result_set.settings.backend}"
        )
        self.cmb_registration_view_mode.setEnabled(True)
        self.statusBar().showMessage(
            f"Registration finished for {result_set.result_count} frames.",
            5000,
        )

    def _on_registration_failed(self, message: str) -> None:
        self._registration_running = False
        self._set_file_actions_enabled(True)
        self._close_registration_progress_dialog()
        self._sync_navigation_controls()
        QMessageBox.critical(self, "Registration failed", message)
        self.lbl_registration_status.setText(f"Registration failed: {message}")
        self.statusBar().showMessage("Registration failed.", 3000)

    def _show_registration_progress_dialog(self, settings: MolTrackRegistrationSettings) -> QProgressDialog:
        progress_dialog = QProgressDialog(
            f"Running {settings.backend} registration...",
            None,
            0,
            0,
            self,
        )
        progress_dialog.setWindowTitle("Registration")
        progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        progress_dialog.setCancelButton(None)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(False)
        progress_dialog.setAutoReset(False)
        progress_dialog.show()
        QApplication.processEvents()
        return progress_dialog

    def _close_registration_progress_dialog(self) -> None:
        if self._registration_progress_dialog is None:
            return
        self._registration_progress_dialog.close()
        self._registration_progress_dialog = None
        QApplication.processEvents()

    def _cleanup_registration_worker(self) -> None:
        if self._registration_worker is not None:
            self._registration_worker.deleteLater()
            self._registration_worker = None
        if self._registration_thread is not None:
            self._registration_thread.deleteLater()
            self._registration_thread = None

    def _set_file_actions_enabled(self, enabled: bool) -> None:
        self.action_open_stm.setEnabled(enabled)
        self.action_open_stm_reverse.setEnabled(enabled)

    def _sync_registration_status(self) -> None:
        if self._series is None or self._series.registration_results is None:
            self.lbl_registration_status.setText("No registration results")
            return
        result_set = self._series.registration_results
        self.lbl_registration_status.setText(
            f"Registered {result_set.result_count} frames with {result_set.settings.backend}"
        )

    def _on_registration_view_mode_changed(self, _mode: str) -> None:
        if self._series is None:
            return
        self._show_current_frame()

    def _is_expanded_aligned_view_requested(self) -> bool:
        return self.cmb_registration_view_mode.currentText() == "Show expanded aligned"

    def _set_registration_view_mode(self, mode: str) -> None:
        previous = self.cmb_registration_view_mode.blockSignals(True)
        try:
            index = self.cmb_registration_view_mode.findText(mode)
            if index >= 0:
                self.cmb_registration_view_mode.setCurrentIndex(index)
        finally:
            self.cmb_registration_view_mode.blockSignals(previous)

    def _ensure_expanded_aligned_stack(self):
        if self._series is None:
            raise RuntimeError("expanded aligned view requires a loaded series.")
        if self._series.registration_results is None:
            raise RuntimeError("expanded aligned view requires registration results.")
        if self._series.expanded_aligned_stack is None:
            self._series.expanded_aligned_stack = self._expanded_aligned_builder(self._series)
        return self._series.expanded_aligned_stack

    def _on_open_stm_requested(self) -> None:
        self._choose_and_open_stm(reverse_frame_order=False)

    def _on_open_stm_reverse_requested(self) -> None:
        self._choose_and_open_stm(reverse_frame_order=True)

    def _choose_and_open_stm(self, *, reverse_frame_order: bool) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Open STM",
            "",
            "MPP files (*.mpp *.MPP)",
        )
        if not path:
            return
        try:
            self.open_stm_source(path, reverse_frame_order=reverse_frame_order)
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            self.statusBar().showMessage(f"Open STM failed: {message}", 5000)
            QMessageBox.critical(self, "Open STM failed", message)
