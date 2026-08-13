from __future__ import annotations

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QWidget,
)

from moltrack.analysis.domain_analysis import DomainAnalysisWorkspaceSnapshot


class ManualDomainControls(QGroupBox):
    """Thin controls for preparing manual-domain lifecycle actions."""

    create_requested = pyqtSignal()
    move_requested = pyqtSignal(str)
    delete_requested = pyqtSignal(str)
    restore_requested = pyqtSignal(str)
    preview_invalidated = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("M6 domain", parent)
        layout = QGridLayout(self)
        self.domain_combo = QComboBox(self)
        self.domain_combo.currentIndexChanged.connect(
            self.preview_invalidated.emit
        )
        self.create_button = QPushButton("Create domain", self)
        self.move_button = QPushButton("Move selection", self)
        self.delete_button = QPushButton("Delete domain", self)
        self.restore_button = QPushButton("Restore domain", self)
        layout.addWidget(QLabel("Manual domain", self), 0, 0)
        layout.addWidget(self.domain_combo, 0, 1, 1, 3)
        layout.addWidget(self.create_button, 1, 0)
        layout.addWidget(self.move_button, 1, 1)
        layout.addWidget(self.delete_button, 1, 2)
        layout.addWidget(self.restore_button, 1, 3)
        self.create_button.clicked.connect(self.create_requested.emit)
        self.move_button.clicked.connect(self._request_move)
        self.delete_button.clicked.connect(self._request_delete)
        self.restore_button.clicked.connect(self._request_restore)

    def render_snapshot(self, snapshot: DomainAnalysisWorkspaceSnapshot) -> None:
        state = snapshot.domain_corrections
        projection = state.effective_projection
        domains = () if projection is None else tuple(
            value
            for value in projection.domains
            if value.physical_frame_id == snapshot.active_physical_frame_id
            and value.domain_kind == "manual"
        )
        selected_id = self.domain_combo.currentData()
        with QSignalBlocker(self.domain_combo):
            self.domain_combo.clear()
            for domain in domains:
                suffix = " (tombstone)" if domain.is_tombstone else ""
                self.domain_combo.addItem(
                    f"{domain.lattice_domain_id}{suffix}",
                    domain.lattice_domain_id,
                )
            selected_index = self.domain_combo.findData(selected_id)
            if selected_index >= 0:
                self.domain_combo.setCurrentIndex(selected_index)
        current_id = self.domain_combo.currentData()
        current = next(
            (value for value in domains if value.lattice_domain_id == current_id),
            None,
        )
        has_selection = bool(state.selected_source_ids)
        self.create_button.setEnabled(has_selection and projection is not None)
        self.move_button.setEnabled(
            has_selection and current is not None and not current.is_tombstone
        )
        self.delete_button.setEnabled(current is not None and not current.is_tombstone)
        self.restore_button.setEnabled(current is not None and current.is_tombstone)

    def _request_move(self) -> None:
        self.move_requested.emit(self._current_domain_id())

    def _request_delete(self) -> None:
        self.delete_requested.emit(self._current_domain_id())

    def _request_restore(self) -> None:
        self.restore_requested.emit(self._current_domain_id())

    def _current_domain_id(self) -> str:
        value = self.domain_combo.currentData()
        if not isinstance(value, str):
            raise ValueError("Select a manual domain first.")
        return value


__all__ = ["ManualDomainControls"]
