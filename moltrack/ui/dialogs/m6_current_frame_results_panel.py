from __future__ import annotations

from dataclasses import fields

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis import M6CurrentFrameResults, M6CurrentFrameSummary


_DOMAIN_COLUMNS = (
    ("ordered_component_id", "Component ID"),
    ("m6_orientation_domain_id", "Domain ID"),
    ("component_type", "Type"),
    ("molecule_count", "Count"),
    ("molecule_fraction_of_valid_representatives", "Molecule fraction of V"),
    ("footprint_fraction_of_valid_fov", "Footprint fraction of valid FOV"),
    ("footprint_area_nm2", "Area [nm2]"),
    ("orientation_deg", "M6 orientation [deg]"),
    ("domain_mean_local_q6", "Mean local q6"),
    ("domain_coherent_q6", "Coherent q6"),
    ("domain_median_bond_length_nm", "Bond median [nm]"),
    ("domain_bond_length_mad_nm", "Bond MAD [nm]"),
    ("domain_bond_length_iqr_nm", "Bond IQR [nm]"),
    ("domain_bond_length_robust_cv", "Bond robust CV"),
    ("qc_statuses", "QC"),
)

_SUMMARY_LABELS = {
    "mean_local_q6_interior": "Mean local q6 (interior)",
    "mean_local_q6_all_valid": "Mean local q6 (all valid)",
    "global_q6_interior": "Global q6 (interior)",
    "edge_truncated_fraction_of_valid_representatives": "Edge-truncated fraction of V",
    "full_domain_count": "Full domains",
    "small_ordered_island_count": "Small ordered islands",
    "full_domain_molecule_fraction": "Molecules in full domains",
    "small_island_molecule_fraction": "Molecules in small islands",
    "unassigned_molecule_fraction": "Unassigned molecules",
    "full_domain_footprint_fraction": "Valid FOV: full domains",
    "small_island_footprint_fraction": "Valid FOV: small islands",
    "unassigned_supported_footprint_fraction": "Valid FOV: unassigned support",
    "unsupported_background_fraction": "Valid FOV: unsupported background",
    "duplicate_excluded_fraction_of_original": "Excluded duplicates",
    "invalid_position_fraction_of_original": "Excluded invalid positions",
    "full_domain_molecule_weighted_coherent_q6": "Coherent q6 (molecule weighted)",
    "full_domain_footprint_weighted_coherent_q6": "Coherent q6 (footprint weighted)",
    "domain_molecule_entropy": "Domain molecule entropy",
    "domain_footprint_entropy": "Domain footprint entropy",
}


class M6CurrentFrameResultsPanel(QWidget):
    """Current-frame domain table and quantitative M6 summary."""

    domain_selection_changed = pyqtSignal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._results: M6CurrentFrameResults | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        table_group = QGroupBox("Current-frame M6 domains", self)
        table_layout = QVBoxLayout(table_group)
        self.empty_label = QLabel("No current-frame M6 result.", table_group)
        self.empty_label.setWordWrap(True)
        table_layout.addWidget(self.empty_label)
        self.domain_table = QTableWidget(0, len(_DOMAIN_COLUMNS), table_group)
        self.domain_table.setHorizontalHeaderLabels(
            [label for _field_name, label in _DOMAIN_COLUMNS]
        )
        self.domain_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.domain_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.domain_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.domain_table.verticalHeader().setVisible(False)
        self.domain_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.domain_table.setMinimumHeight(180)
        self.domain_table.hide()
        table_layout.addWidget(self.domain_table)
        layout.addWidget(table_group)

        summary_group = QGroupBox("Current-frame M6 summary", self)
        summary_form = QFormLayout(summary_group)
        self.summary_value_labels: dict[str, QLabel] = {}
        for field in fields(M6CurrentFrameSummary):
            value_label = QLabel("n/a", summary_group)
            value_label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self.summary_value_labels[field.name] = value_label
            summary_form.addRow(_SUMMARY_LABELS[field.name], value_label)
        summary_group.hide()
        self.summary_group = summary_group
        layout.addWidget(summary_group)

        self.domain_table.currentCellChanged.connect(self._on_current_cell_changed)

    def set_results(self, results: M6CurrentFrameResults | None) -> None:
        if results is not None and not isinstance(results, M6CurrentFrameResults):
            raise TypeError("results must be M6CurrentFrameResults or None.")
        self._results = results
        blocker = QSignalBlocker(self.domain_table)
        try:
            self.domain_table.clearContents()
            self.domain_table.setRowCount(0 if results is None else len(results.domains))
            if results is not None:
                for row_index, row in enumerate(results.domains):
                    for column_index, (field_name, _label) in enumerate(_DOMAIN_COLUMNS):
                        item = QTableWidgetItem(_format_value(getattr(row, field_name)))
                        if isinstance(getattr(row, field_name), (int, float)):
                            item.setTextAlignment(
                                Qt.AlignmentFlag.AlignRight
                                | Qt.AlignmentFlag.AlignVCenter
                            )
                        self.domain_table.setItem(row_index, column_index, item)
        finally:
            del blocker
        has_domains = results is not None and bool(results.domains)
        self.domain_table.setVisible(has_domains)
        self.empty_label.setVisible(not has_domains)
        self.empty_label.setText(
            "No current-frame M6 result."
            if results is None
            else (results.empty_message or "")
        )
        self.summary_group.setVisible(results is not None)
        if results is not None:
            for field_name, label in self.summary_value_labels.items():
                label.setText(_format_value(getattr(results.summary, field_name)))
        self.domain_selection_changed.emit(None)

    def current_results(self) -> M6CurrentFrameResults | None:
        return self._results

    def domain_row_count(self) -> int:
        return self.domain_table.rowCount()

    def _on_current_cell_changed(
        self,
        current_row: int,
        _current_column: int,
        _previous_row: int,
        _previous_column: int,
    ) -> None:
        if self._results is None or not 0 <= current_row < len(self._results.domains):
            self.domain_selection_changed.emit(None)
            return
        self.domain_selection_changed.emit(
            self._results.domains[current_row].ordered_component_id
        )


def _format_value(value: object) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, tuple):
        return ", ".join(str(item) for item in value) if value else "OK"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)
