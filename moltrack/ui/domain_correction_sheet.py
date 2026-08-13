from __future__ import annotations

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QButtonGroup,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis.domain_analysis import (
    DomainCorrectionEffect,
    DomainAnalysisWorkspaceSnapshot,
    PreparedDomainCorrection,
)
from moltrack.ui.domain_analysis_hierarchy import DomainAnalysisHierarchySheet
from moltrack.ui.manual_domain_controls import ManualDomainControls


class DomainCorrectionSheet(QWidget):
    """Qt controls over correction intents and a rendered effective projection."""

    preview_requested = pyqtSignal(str, object)
    reset_requested = pyqtSignal()
    apply_requested = pyqtSignal(bool)
    selection_mode_changed = pyqtSignal(str)
    clear_selection_requested = pyqtSignal()
    preview_invalidated = pyqtSignal()
    create_domain_requested = pyqtSignal()
    move_domain_requested = pyqtSignal(str, object)
    delete_domain_requested = pyqtSignal(str)
    restore_domain_requested = pyqtSignal(str, object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("domainCorrectionSheet")
        layout = QHBoxLayout(self)
        self.hierarchy_sheet = DomainAnalysisHierarchySheet(self)
        layout.addWidget(self.hierarchy_sheet, 1)
        editor = self._build_editor()
        layout.addWidget(editor, 1)
        self._connect_controls()
        self._has_selection = False
        self._has_publication = False
        self._prepared: PreparedDomainCorrection | None = None
        self._rendered_prepared_fingerprint: str | None = None
        self._render_reason_requirement(self.target_combo.currentText())
        self._render_preview_availability()
        self._render_apply_availability()

    def _build_editor(self) -> QWidget:
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
        selection_buttons = QHBoxLayout()
        selection_group = QButtonGroup(self)
        selection_group.setExclusive(True)
        self.point_selection_button = QPushButton("Point / multi", editor)
        self.polygon_selection_button = QPushButton("Polygon", editor)
        self.clear_selection_button = QPushButton("Clear", editor)
        for button in (self.point_selection_button, self.polygon_selection_button):
            button.setCheckable(True)
            selection_group.addButton(button)
            selection_buttons.addWidget(button)
        self.point_selection_button.setChecked(True)
        selection_buttons.addWidget(self.clear_selection_button)
        editor_layout.addLayout(selection_buttons)
        self.manual_domain_controls = ManualDomainControls(editor)
        editor_layout.addWidget(self.manual_domain_controls)
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
        self.preview_label.setWordWrap(True)
        editor_layout.addWidget(self.preview_label)
        self.confirm_impact_checkbox = QCheckBox(
            "Confirm this prepared batch",
            editor,
        )
        self.confirm_impact_checkbox.hide()
        editor_layout.addWidget(self.confirm_impact_checkbox)
        self.table = QTableWidget(editor)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(("Molecule", "M6", "Effective", "Source"))
        editor_layout.addWidget(self.table, 1)
        return editor

    def _connect_controls(self) -> None:
        self.target_combo.currentTextChanged.connect(self._on_target_changed)
        self.reason_edit.textChanged.connect(self._on_reason_changed)
        self.preview_button.clicked.connect(self._request_preview)
        self.reset_button.clicked.connect(self.reset_requested.emit)
        self.apply_button.clicked.connect(
            lambda: self.apply_requested.emit(
                self.confirm_impact_checkbox.isChecked()
            )
        )
        self.point_selection_button.clicked.connect(
            lambda: self.selection_mode_changed.emit("point")
        )
        self.polygon_selection_button.clicked.connect(
            lambda: self.selection_mode_changed.emit("polygon")
        )
        self.clear_selection_button.clicked.connect(
            self.clear_selection_requested.emit
        )
        self.confirm_impact_checkbox.toggled.connect(
            lambda _checked: self._render_apply_availability()
        )
        self.manual_domain_controls.create_requested.connect(
            self.create_domain_requested.emit
        )
        self.manual_domain_controls.move_requested.connect(
            self.move_domain_requested.emit
        )
        self.manual_domain_controls.delete_requested.connect(
            self.delete_domain_requested.emit
        )
        self.manual_domain_controls.restore_requested.connect(
            self.restore_domain_requested.emit
        )
        self.manual_domain_controls.preview_invalidated.connect(
            self.preview_invalidated.emit
        )

    def render_snapshot(self, snapshot: DomainAnalysisWorkspaceSnapshot) -> None:
        self.hierarchy_sheet.render_snapshot(snapshot)
        self.manual_domain_controls.render_snapshot(snapshot)
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
        self._prepared = state.prepared
        self._render_prepared(state.prepared)
        projection = state.effective_projection
        molecules = () if projection is None else tuple(
            value
            for value in projection.molecules
            if value.physical_frame_id == snapshot.active_physical_frame_id
        )
        self._render_effective_label(molecules, selected)
        self._render_table(molecules)
        self._render_preview_availability()

    def _render_prepared(
        self,
        prepared: PreparedDomainCorrection | None,
    ) -> None:
        if prepared is None:
            self.preview_label.setText("No prepared correction")
            self.confirm_impact_checkbox.hide()
            self.confirm_impact_checkbox.setChecked(False)
            self._rendered_prepared_fingerprint = None
            self._render_apply_availability()
            return
        if prepared.prepared_fingerprint != self._rendered_prepared_fingerprint:
            self.confirm_impact_checkbox.setChecked(False)
        self._rendered_prepared_fingerprint = prepared.prepared_fingerprint
        self.preview_label.setText(_preview_text(prepared))
        self.confirm_impact_checkbox.setText(
            "Confirm source groups: " + ", ".join(prepared.source_groups)
        )
        self.confirm_impact_checkbox.setVisible(prepared.requires_confirmation)
        if not prepared.requires_confirmation:
            self.confirm_impact_checkbox.setChecked(False)
        self._render_apply_availability()

    def _render_apply_availability(self) -> None:
        prepared = self._prepared
        if prepared is None:
            self.apply_button.setEnabled(False)
            return
        enabled = bool(prepared.changed_source_ids)
        if enabled:
            enabled = not prepared.is_blocked and (
                not prepared.requires_confirmation
                or self.confirm_impact_checkbox.isChecked()
            )
        self.apply_button.setEnabled(enabled)

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
        self.preview_button.setEnabled(
            self._has_selection and self._has_publication
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


def _preview_text(prepared: PreparedDomainCorrection) -> str:
    operation = prepared.intent.operation
    command = {
        "assign": "Assign orientation",
        "reset": "Reset orientation",
        "create": "Create domain",
        "move": "Move to domain",
        "delete": "Delete domain",
        "restore": "Restore domain",
    }.get(operation, operation.title())
    count = len(prepared.changed_source_ids)
    conflicts = "; ".join(
        f"{value.severity}: {value.message}"
        for value in prepared.conflicts
    )
    summary = (
        f"{command}: {count}/{len(prepared.source_ids)} molecules will change; "
        f"axis {prepared.axis}; automatic {prepared.automatic_fingerprint[:12]}"
    )
    effects = "; ".join(
        f"{value.source_id}: {value.before_value or '-'} -> "
        f"{value.after_value or '-'}{_boundary_effect_text(value)}"
        for value in prepared.effects
    )
    details = ". ".join(value for value in (effects, conflicts) if value)
    return summary if not details else f"{summary}. {details}"


def _boundary_effect_text(effect: DomainCorrectionEffect) -> str:
    before = effect.before_boundary
    after = effect.after_boundary
    if before is None:
        return ""
    rendered_after = "unresolved" if after is None else str(after).lower()
    return f", boundary {str(before).lower()} -> {rendered_after}"


__all__ = ["DomainCorrectionSheet"]
