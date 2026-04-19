from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QSignalBlocker, Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from nanotrack.core import ParticleTrack, STMSequence
from nanotrack.io import load_mpp_sequence
from nanotrack.ui.widgets import (
    PreprocessingActionsPanel,
    SequenceMetadataPanel,
    SequenceViewerWidget,
    TrackListPanel,
)


class NanoTrackMainWindow(QMainWindow):
    """Main window for MPP sequence browsing and navigation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence: STMSequence | None = None
        self._tracks: list[ParticleTrack] = []
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        self.setWindowTitle("NanoTrack")
        self.resize(1280, 860)

        self._build_actions()
        self._build_central_widget()
        self._update_navigation_enabled(False)
        self.statusBar().showMessage("Ready")

    def _build_actions(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        self.action_open_mpp = toolbar.addAction("Open MPP...")
        self.action_open_mpp.setToolTip("Load an MPP sequence into NanoTrack")

    def _build_central_widget(self) -> None:
        central = QSplitter(Qt.Orientation.Horizontal, self)

        viewer_container = QWidget(self)
        layout = QVBoxLayout(viewer_container)

        self.viewer = SequenceViewerWidget(self)
        layout.addWidget(self.viewer, 1)

        self.lbl_frame = QLabel("Frame: - / -", self)
        self.lbl_frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_frame)

        self.slider_frame = QSlider(Qt.Orientation.Horizontal, self)
        self.slider_frame.setTracking(True)
        layout.addWidget(self.slider_frame)

        nav_row = QWidget(self)
        nav_layout = QHBoxLayout(nav_row)
        nav_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_prev = QPushButton("Previous Frame", self)
        self.spin_frame = QSpinBox(self)
        self.spin_frame.setPrefix("Frame ")
        self.btn_next = QPushButton("Next Frame", self)

        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.spin_frame)
        nav_layout.addWidget(self.btn_next)

        layout.addWidget(nav_row)

        sidebar = QWidget(self)
        sidebar_layout = QVBoxLayout(sidebar)
        self.metadata_panel = SequenceMetadataPanel(self)
        self.track_list_panel = TrackListPanel(self)
        self.preprocessing_panel = PreprocessingActionsPanel(self)
        sidebar_layout.addWidget(self.metadata_panel, 0)
        sidebar_layout.addWidget(self.track_list_panel, 1)
        sidebar_layout.addWidget(self.preprocessing_panel, 0)

        central.addWidget(viewer_container)
        central.addWidget(sidebar)
        central.setStretchFactor(0, 1)
        central.setStretchFactor(1, 0)
        central.setSizes([980, 300])
        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.action_open_mpp.triggered.connect(self._on_open_mpp)
        self.slider_frame.valueChanged.connect(self._on_frame_selected)
        self.spin_frame.valueChanged.connect(self._on_spin_frame_selected)
        self.btn_prev.clicked.connect(self._on_prev_frame)
        self.btn_next.clicked.connect(self._on_next_frame)
        self.preprocessing_panel.preview_requested.connect(self._on_preprocessing_preview_requested)
        self.preprocessing_panel.apply_all_requested.connect(self._on_preprocessing_apply_all_requested)

    def _update_navigation_enabled(self, enabled: bool) -> None:
        self.slider_frame.setEnabled(enabled)
        self.spin_frame.setEnabled(enabled)
        self.btn_prev.setEnabled(enabled)
        self.btn_next.setEnabled(enabled)
        self.preprocessing_panel.set_sequence_loaded(enabled)

    def _sync_navigation_controls(self) -> None:
        if self._sequence is None:
            self.lbl_frame.setText("Frame: - / -")
            self._update_navigation_enabled(False)
            self.metadata_panel.clear()
            return

        current = self._sequence.active_frame_index
        total = self._sequence.frame_count
        self._update_navigation_enabled(True)

        with QSignalBlocker(self.slider_frame):
            self.slider_frame.setRange(0, total - 1)
            self.slider_frame.setValue(current)

        with QSignalBlocker(self.spin_frame):
            self.spin_frame.setRange(1, total)
            self.spin_frame.setValue(current + 1)

        self.btn_prev.setEnabled(current > 0)
        self.btn_next.setEnabled(current < total - 1)
        self.lbl_frame.setText(f"Frame: {current + 1} / {total}")
        self.metadata_panel.set_sequence(self._sequence)

    def _show_current_frame(self, preserve_zoom: bool = True) -> None:
        if self._sequence is None:
            self.viewer.clear()
            self._sync_navigation_controls()
            return

        self.viewer.show_frame(self._sequence.active_frame_index, preserve_zoom=preserve_zoom)
        self._sync_navigation_controls()
        self.statusBar().showMessage(
            f"{Path(self._sequence.source_path).name} | frame {self._sequence.active_frame_index + 1}/{self._sequence.frame_count}",
            3000,
        )

    def set_sequence(self, sequence: STMSequence) -> None:
        self._sequence = sequence
        self.viewer.set_sequence(sequence)
        self._sync_navigation_controls()
        self.statusBar().showMessage(
            f"{Path(sequence.source_path).name} | frame {sequence.active_frame_index + 1}/{sequence.frame_count}",
            3000,
        )
        self.set_tracks([])

    def load_sequence_from_path(self, file_path: str) -> None:
        sequence = load_mpp_sequence(file_path)
        self.set_sequence(sequence)

    def current_sequence(self) -> STMSequence | None:
        return self._sequence

    def set_tracks(self, tracks: list[ParticleTrack]) -> None:
        self._tracks = list(tracks)
        self.track_list_panel.set_tracks(self._tracks)

    def current_tracks(self) -> list[ParticleTrack]:
        return list(self._tracks)

    def _set_active_frame(self, frame_index: int) -> None:
        if self._sequence is None:
            return
        if frame_index == self._sequence.active_frame_index:
            return
        self._sequence.set_active_frame(frame_index)
        self._show_current_frame(preserve_zoom=True)

    def _on_open_mpp(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open MPP sequence",
            "",
            "MPP files (*.mpp *.MPP);;All files (*.*)",
        )
        if not path:
            return

        try:
            self.load_sequence_from_path(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", f"Cannot load MPP sequence:\n{path}\n\n{exc}")
            return

    def _on_frame_selected(self, frame_index: int) -> None:
        self._set_active_frame(frame_index)

    def _on_spin_frame_selected(self, spin_value: int) -> None:
        self._set_active_frame(spin_value - 1)

    def _on_prev_frame(self) -> None:
        if self._sequence is None:
            return
        self._set_active_frame(max(0, self._sequence.active_frame_index - 1))

    def _on_next_frame(self) -> None:
        if self._sequence is None:
            return
        self._set_active_frame(min(self._sequence.frame_count - 1, self._sequence.active_frame_index + 1))

    def _on_preprocessing_preview_requested(self) -> None:
        if self._sequence is None:
            return
        self.statusBar().showMessage(
            "BM3D preview will be implemented in step 9.",
            3000,
        )

    def _on_preprocessing_apply_all_requested(self) -> None:
        if self._sequence is None:
            return
        self.statusBar().showMessage(
            "Apply-to-all BM3D will be implemented in step 10.",
            3000,
        )
