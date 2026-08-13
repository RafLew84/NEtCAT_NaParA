from __future__ import annotations

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis.domain_analysis import DomainAnalysisWorkspaceSnapshot
from moltrack.ui.domain_analysis_hierarchy import DomainAnalysisHierarchySheet


class DomainCorrectionSheet(QWidget):
    """Qt controls over correction intents and a rendered effective projection."""

    preview_requested = pyqtSignal(str, object)
    reset_requested = pyqtSignal()
    apply_requested = pyqtSignal()
    preview_invalidated = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("domainCorrectionSheet")
        layout = QHBoxLayout(self)
        self.hierarchy_sheet = DomainAnalysisHierarchySheet(self)
        layout.addWidget(self.hierarchy_sheet, 1)
        editor = QWidget(self)
        editor_layout = QVBoxLayout(editor)
        form = QFormLayout()
        self.selection_label = QLabel("No molecule selected", editor)
        self.target_combo = QComboBox(editor)
        self.target_combo.addItems([chr(value) for value in range(ord("A"), ord("Z") + 1)])
        self.target_combo.addItem("Unresolvable")
        self.reason_edit = QLineEdit(editor)
        self.reason_edit.setPlaceholderText("Reason code")
        self.effective_label = QLabel("Effective: -", editor)
        form.addRow("Selection", self.selection_label)
        form.addRow("Orientation", self.target_combo)
        form.addRow("Reason", self.reason_edit)
        form.addRow("Current", self.effective_label)
        editor_layout.addLayout(form)
        buttons = QHBoxLayout()
        self.preview_button = QPushButton("Preview", editor)
        self.reset_button = QPushButton("Reset", editor)
        self.apply_button = QPushButton("Apply", editor)
        buttons.addWidget(self.preview_button)
        buttons.addWidget(self.reset_button)
        buttons.addStretch(1)
        buttons.addWidget(self.apply_button)
        editor_layout.addLayout(buttons)
        self.preview_label = QLabel("No prepared correction", editor)
        editor_layout.addWidget(self.preview_label)
        self.table = QTableWidget(editor)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(("Molecule", "M6", "Effective", "Source"))
        editor_layout.addWidget(self.table, 1)
        layout.addWidget(editor, 1)
        self.target_combo.currentTextChanged.connect(self._on_target_changed)
        self.reason_edit.textChanged.connect(self._on_reason_changed)
        self.preview_button.clicked.connect(self._request_preview)
        self.reset_button.clicked.connect(self.reset_requested.emit)
        self.apply_button.clicked.connect(self.apply_requested.emit)
        self._has_selection = False
        self._has_publication = False
        self._render_reason_requirement(self.target_combo.currentText())
        self._render_preview_availability()

    def render_snapshot(self, snapshot: DomainAnalysisWorkspaceSnapshot) -> None:
        self.hierarchy_sheet.render_snapshot(snapshot)
        state = snapshot.domain_corrections
        selected = state.selected_source_ids
        self._has_selection = bool(selected)
        self._has_publication = snapshot.published is not None
        self.selection_label.setText(
            "No molecule selected"
            if not selected
            else ", ".join(selected)
        )
        self.reset_button.setEnabled(self._has_selection and self._has_publication)
        self.apply_button.setEnabled(
            state.prepared is not None and bool(state.prepared.changed_source_ids)
        )
        self.preview_label.setText(
            "No prepared correction"
            if state.prepared is None
            else _preview_text(state.prepared.intent.operation, state.prepared.changed_source_ids)
        )
        projection = state.effective_projection
        molecules = () if projection is None else tuple(
            value
            for value in projection.molecules
            if value.physical_frame_id == snapshot.active_physical_frame_id
        )
        self._render_effective_label(molecules, selected)
        self._render_table(molecules)
        self._render_preview_availability()

    def _request_preview(self) -> None:
        reason = self.reason_edit.text().strip() or None
        self.preview_requested.emit(self.target_combo.currentText(), reason)

    def _on_target_changed(self, label: str) -> None:
        self._render_reason_requirement(label)
        self.preview_invalidated.emit()

    def _on_reason_changed(self, _value: str) -> None:
        self._render_preview_availability()
        self.preview_invalidated.emit()

    def _render_reason_requirement(self, label: str) -> None:
        required = label == "Unresolvable"
        self.reason_edit.setEnabled(required)
        if not required:
            with QSignalBlocker(self.reason_edit):
                self.reason_edit.clear()
        self._render_preview_availability()

    def _render_preview_availability(self) -> None:
        reason_ready = (
            self.target_combo.currentText() != "Unresolvable"
            or bool(self.reason_edit.text().strip())
        )
        self.preview_button.setEnabled(
            self._has_selection and self._has_publication and reason_ready
        )

    def _render_effective_label(self, molecules: tuple, selected: tuple[str, ...]) -> None:
        if len(selected) != 1:
            self.effective_label.setText("Effective: -")
            return
        molecule = next(
            (value for value in molecules if value.source_id == selected[0]),
            None,
        )
        if molecule is None or molecule.effective_orientation is None:
            self.effective_label.setText("Effective: none")
            return
        self.effective_label.setText(
            f"Effective: {molecule.effective_orientation} "
            f"({molecule.effective_orientation_source})"
        )

    def _render_table(self, molecules: tuple) -> None:
        self.table.setRowCount(len(molecules))
        for row, molecule in enumerate(molecules):
            values = (
                molecule.source_id,
                molecule.m6_partition,
                molecule.effective_orientation or "-",
                molecule.effective_orientation_source,
            )
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))


def _preview_text(operation: str, changed_source_ids: tuple[str, ...]) -> str:
    command = "Reset" if operation == "reset" else "Assign"
    count = len(changed_source_ids)
    return f"{command}: {count} molecule{'s' if count != 1 else ''} will change"


__all__ = ["DomainCorrectionSheet"]
