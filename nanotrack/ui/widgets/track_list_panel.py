from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from nanotrack.core import ParticleTrack
from nanotrack.mask_trackers import MASK_TRACKER_KINDS, MaskTrackerKind


class TrackListPanel(QWidget):
    """Sidebar panel listing tracked objects."""

    track_selected = pyqtSignal(object)
    track_delete_requested = pyqtSignal(int)
    mask_tracker_changed = pyqtSignal(object)
    run_selected_requested = pyqtSignal()
    run_all_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating_selection = False
        self._processing_busy = False
        self._build()
        self.list_tracks.currentItemChanged.connect(self._on_current_item_changed)
        self.btn_delete_selected.clicked.connect(self._on_delete_selected_clicked)
        self.btn_run_selected.clicked.connect(self.run_selected_requested.emit)
        self.btn_run_all.clicked.connect(self.run_all_requested.emit)

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Tracks / Objects", self)
        group_layout = QVBoxLayout(group)

        self.lbl_summary = QLabel("0 tracks", self)
        self.list_tracks = QListWidget(self)
        self.list_tracks.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.lbl_mask_tracker = QLabel("Mask Tracker", self)
        self.cmb_mask_tracker = QComboBox(self)
        for tracker_kind in MASK_TRACKER_KINDS:
            self.cmb_mask_tracker.addItem(_mask_tracker_label(tracker_kind), tracker_kind.value)
        self.cmb_mask_tracker.setCurrentIndex(self.cmb_mask_tracker.findData(MaskTrackerKind.SAM2.value))
        self.lbl_run_frame_limit = QLabel("Frames", self)
        self.sp_run_frame_limit = QSpinBox(self)
        self.sp_run_frame_limit.setRange(0, 1_000_000)
        self.sp_run_frame_limit.setValue(0)
        self.sp_run_frame_limit.setSpecialValueText("All")
        self.sp_run_frame_limit.setToolTip(
            "Maximum frames to run from each seed frame, including the seed frame. Use All to run to the end."
        )
        self.btn_delete_selected = QPushButton("Delete Selected", self)
        self.btn_run_selected = QPushButton("Run for Selected", self)
        self.btn_run_all = QPushButton("Run for All Seeds", self)

        tracker_layout = QHBoxLayout()
        tracker_layout.addWidget(self.lbl_mask_tracker)
        tracker_layout.addWidget(self.cmb_mask_tracker, 1)
        frame_limit_layout = QHBoxLayout()
        frame_limit_layout.addWidget(self.lbl_run_frame_limit)
        frame_limit_layout.addWidget(self.sp_run_frame_limit, 1)

        group_layout.addWidget(self.lbl_summary)
        group_layout.addWidget(self.list_tracks, 1)
        group_layout.addWidget(self.btn_delete_selected)
        group_layout.addLayout(tracker_layout)
        group_layout.addLayout(frame_limit_layout)
        group_layout.addWidget(self.btn_run_selected)
        group_layout.addWidget(self.btn_run_all)

        layout.addWidget(group, 1)
        self.cmb_mask_tracker.currentIndexChanged.connect(self._on_mask_tracker_changed)
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

    def current_mask_tracker_kind(self) -> MaskTrackerKind:
        tracker_value = self.cmb_mask_tracker.currentData()
        return MaskTrackerKind.from_value(tracker_value)

    def set_mask_tracker_kind(self, tracker_kind: MaskTrackerKind | str) -> None:
        tracker = MaskTrackerKind.from_value(tracker_kind)
        index = self.cmb_mask_tracker.findData(tracker.value)
        if index < 0:
            raise ValueError(f"Mask tracker is not listed in the UI selector: {tracker.value!r}.")
        self.cmb_mask_tracker.setCurrentIndex(index)

    def current_run_frame_limit(self) -> int | None:
        value = int(self.sp_run_frame_limit.value())
        return None if value == 0 else value

    def set_run_frame_limit(self, frame_limit: int | None) -> None:
        if frame_limit is None:
            self.sp_run_frame_limit.setValue(0)
            return
        if frame_limit < 1:
            raise ValueError("frame_limit must be positive or None.")
        self.sp_run_frame_limit.setValue(int(frame_limit))

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
        self.cmb_mask_tracker.setEnabled(not self._processing_busy)
        self.sp_run_frame_limit.setEnabled(not self._processing_busy)
        self.btn_delete_selected.setEnabled(has_selected_track and not self._processing_busy)
        self.btn_run_selected.setEnabled(has_selected_track and not self._processing_busy)
        self.btn_run_all.setEnabled(has_tracks and not self._processing_busy)

    def _on_current_item_changed(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        self._apply_enabled_state()
        if self._updating_selection:
            return
        track_id = None if current is None else current.data(Qt.ItemDataRole.UserRole)
        self.track_selected.emit(track_id)

    def _on_mask_tracker_changed(self) -> None:
        self.mask_tracker_changed.emit(self.current_mask_tracker_kind())

    def _on_delete_selected_clicked(self) -> None:
        track_id = self.current_track_id()
        if track_id is None:
            return
        self.track_delete_requested.emit(int(track_id))


def _mask_tracker_label(tracker_kind: MaskTrackerKind) -> str:
    if tracker_kind is MaskTrackerKind.SAM2:
        return "SAM2"
    if tracker_kind is MaskTrackerKind.DAM4SAM:
        return "DAM4SAM"
    if tracker_kind is MaskTrackerKind.SAMURAI:
        return "SAMURAI"
    return tracker_kind.value
