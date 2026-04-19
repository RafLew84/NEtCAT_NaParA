from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from nanotrack.core import ParticleTrack


class TrackListPanel(QWidget):
    """Sidebar panel listing tracked objects."""

    track_selected = pyqtSignal(object)
    run_selected_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating_selection = False
        self._processing_busy = False
        self._build()
        self.list_tracks.currentItemChanged.connect(self._on_current_item_changed)
        self.btn_run_selected.clicked.connect(self.run_selected_requested.emit)

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Tracks / Objects", self)
        group_layout = QVBoxLayout(group)

        self.lbl_summary = QLabel("0 tracks", self)
        self.list_tracks = QListWidget(self)
        self.list_tracks.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.btn_run_selected = QPushButton("Run SAM2 for Selected", self)

        group_layout.addWidget(self.lbl_summary)
        group_layout.addWidget(self.list_tracks, 1)
        group_layout.addWidget(self.btn_run_selected)

        layout.addWidget(group, 1)
        self._apply_enabled_state()

    def clear(self) -> None:
        self.list_tracks.clear()
        self.lbl_summary.setText("0 tracks")
        self._apply_enabled_state()

    def set_tracks(self, tracks: list[ParticleTrack], *, selected_track_id: int | None = None) -> None:
        self._updating_selection = True
        try:
            self.list_tracks.clear()

            for track in tracks:
                frame_start = track.seed_frame_index + 1
                frame_end = track.end_frame_index + 1
                label = track.label or f"Track {track.track_id}"
                item = QListWidgetItem(
                    f"{label} | frames {frame_start}-{frame_end} | {track.quality.value}",
                    self.list_tracks,
                )
                item.setData(Qt.ItemDataRole.UserRole, track.track_id)

            track_count = len(tracks)
            suffix = "track" if track_count == 1 else "tracks"
            self.lbl_summary.setText(f"{track_count} {suffix}")
            self.set_selected_track_id(selected_track_id)
        finally:
            self._updating_selection = False
        self._apply_enabled_state()

    def current_track_id(self) -> int | None:
        item = self.list_tracks.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def set_selected_track_id(self, track_id: int | None) -> None:
        self._updating_selection = True
        try:
            if track_id is None:
                self.list_tracks.clearSelection()
                self.list_tracks.setCurrentItem(None)
                return
            for row in range(self.list_tracks.count()):
                item = self.list_tracks.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == track_id:
                    self.list_tracks.setCurrentItem(item)
                    self._apply_enabled_state()
                    return
            self.list_tracks.setCurrentItem(None)
        finally:
            self._updating_selection = False
        self._apply_enabled_state()

    def set_processing(self, busy: bool) -> None:
        self._processing_busy = bool(busy)
        self._apply_enabled_state()

    def _apply_enabled_state(self) -> None:
        has_tracks = self.list_tracks.count() > 0
        has_selected_track = self.current_track_id() is not None
        self.list_tracks.setEnabled(has_tracks and not self._processing_busy)
        self.btn_run_selected.setEnabled(has_selected_track and not self._processing_busy)

    def _on_current_item_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        self._apply_enabled_state()
        if self._updating_selection:
            return
        track_id = None if current is None else current.data(Qt.ItemDataRole.UserRole)
        self.track_selected.emit(track_id)
