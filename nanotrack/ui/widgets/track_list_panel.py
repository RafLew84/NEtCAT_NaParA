from __future__ import annotations

from PyQt6.QtWidgets import QGroupBox, QLabel, QListWidget, QListWidgetItem, QVBoxLayout, QWidget

from nanotrack.core import ParticleTrack


class TrackListPanel(QWidget):
    """Sidebar panel listing tracked objects."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)

        group = QGroupBox("Tracks / Objects", self)
        group_layout = QVBoxLayout(group)

        self.lbl_summary = QLabel("0 tracks", self)
        self.list_tracks = QListWidget(self)
        self.list_tracks.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

        group_layout.addWidget(self.lbl_summary)
        group_layout.addWidget(self.list_tracks, 1)

        layout.addWidget(group, 1)

    def clear(self) -> None:
        self.list_tracks.clear()
        self.lbl_summary.setText("0 tracks")

    def set_tracks(self, tracks: list[ParticleTrack]) -> None:
        self.list_tracks.clear()

        for track in tracks:
            frame_start = track.seed_frame_index + 1
            frame_end = track.end_frame_index + 1
            label = track.label or f"Track {track.track_id}"
            item = QListWidgetItem(
                f"{label} | frames {frame_start}-{frame_end} | {track.quality.value}",
                self.list_tracks,
            )
            item.setData(256, track.track_id)

        track_count = len(tracks)
        suffix = "track" if track_count == 1 else "tracks"
        self.lbl_summary.setText(f"{track_count} {suffix}")
