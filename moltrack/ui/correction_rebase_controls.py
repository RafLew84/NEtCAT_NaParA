from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis.domain_analysis import (
    CorrectionRebaseResolution,
    DomainAnalysisWorkspaceSnapshot,
    PreparedCorrectionRebase,
)


class CorrectionRebaseControls(QWidget):
    """Render pending-rebase policy output and collect operator resolutions."""

    compare_requested = pyqtSignal(object)
    apply_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("correctionRebaseControls")
        layout = QVBoxLayout(self)
        self.pending_label = QLabel("No pending automatic candidate", self)
        self.pending_label.setWordWrap(True)
        layout.addWidget(self.pending_label)
        buttons = QHBoxLayout()
        self.compare_button = QPushButton("Compare", self)
        self.apply_button = QPushButton("Apply Rebase", self)
        buttons.addWidget(self.compare_button)
        buttons.addWidget(self.apply_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        self.issue_table = QTableWidget(self)
        self.issue_table.setColumnCount(6)
        self.issue_table.setHorizontalHeaderLabels((
            "Frame",
            "Source",
            "Issue",
            "Resolution",
            "Targets",
            "Reason",
        ))
        layout.addWidget(self.issue_table)
        self.status_label = QLabel("Run a comparison before promotion", self)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        self.compare_button.clicked.connect(self._request_comparison)
        self.apply_button.clicked.connect(self.apply_requested.emit)
        self.compare_button.setEnabled(False)
        self.apply_button.setEnabled(False)

    def render_snapshot(self, snapshot: DomainAnalysisWorkspaceSnapshot) -> None:
        state = snapshot.domain_corrections
        candidate = state.pending_automatic_candidate
        prepared = state.prepared_rebase
        if candidate is None:
            self.pending_label.setText("No pending automatic candidate")
            self.issue_table.setRowCount(0)
            self.compare_button.setEnabled(False)
            self.apply_button.setEnabled(False)
            self.status_label.setText("Run a new analysis to create a candidate")
            return
        self.pending_label.setText(
            "Pending automatic: " + candidate.automatic_fingerprint[:16]
        )
        self._render_prepared(prepared)
        if snapshot.run.status == "running":
            self.compare_button.setEnabled(False)
            self.apply_button.setEnabled(False)
        else:
            self.compare_button.setEnabled(True)

    def _render_prepared(
        self,
        prepared: PreparedCorrectionRebase | None,
    ) -> None:
        if prepared is None:
            self.issue_table.setRowCount(0)
            self.apply_button.setEnabled(False)
            self.status_label.setText("Run Compare before promotion")
            return
        resolution_by_id = {
            value.issue_id: value for value in prepared.resolutions
        }
        self.issue_table.setRowCount(len(prepared.issues))
        for row, issue in enumerate(prepared.issues):
            for column, value in enumerate((
                issue.physical_frame_id,
                issue.source_id,
                issue.kind,
            )):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, issue.issue_id)
                self.issue_table.setItem(row, column, item)
            saved = resolution_by_id.get(issue.issue_id)
            resolution = self._resolution_combo(saved, self.issue_table)
            targets = QLineEdit(self.issue_table)
            targets.setPlaceholderText("Comma-separated source IDs")
            targets.setText(
                ", ".join(
                    saved.target_source_ids
                    if saved is not None and saved.action == "remapped"
                    else issue.candidate_source_ids
                )
            )
            reason = QLineEdit(self.issue_table)
            reason.setPlaceholderText("Required reason code")
            reason.setText("" if saved is None else saved.reason_code)
            resolution.currentIndexChanged.connect(
                lambda _index, combo=resolution, edit=targets: (
                    edit.setEnabled(combo.currentData() == "remapped")
                )
            )
            targets.setEnabled(resolution.currentData() == "remapped")
            self.issue_table.setCellWidget(row, 3, resolution)
            self.issue_table.setCellWidget(row, 4, targets)
            self.issue_table.setCellWidget(row, 5, reason)
        self.apply_button.setEnabled(prepared.is_ready)
        if prepared.blocking_reasons:
            self.status_label.setText("; ".join(prepared.blocking_reasons))
        elif prepared.is_ready:
            self.status_label.setText("Ready for atomic promotion")
        else:
            missing = len(prepared.issues) - len(prepared.resolutions)
            self.status_label.setText(f"Unresolved rebase issues: {missing}")

    def _resolution_combo(
        self,
        saved: CorrectionRebaseResolution | None,
        parent: QWidget,
    ) -> QComboBox:
        combo = QComboBox(parent)
        combo.addItem("Unresolved", None)
        combo.addItem("Reapplied", "reapplied")
        combo.addItem("Remapped", "remapped")
        combo.addItem("Dropped", "dropped")
        if saved is not None:
            combo.setCurrentIndex(combo.findData(saved.action))
        return combo

    def _request_comparison(self) -> None:
        resolutions: list[CorrectionRebaseResolution] = []
        for row in range(self.issue_table.rowCount()):
            issue_item = self.issue_table.item(row, 0)
            resolution = self.issue_table.cellWidget(row, 3)
            targets = self.issue_table.cellWidget(row, 4)
            reason = self.issue_table.cellWidget(row, 5)
            if (
                issue_item is None
                or not isinstance(resolution, QComboBox)
                or not isinstance(targets, QLineEdit)
                or not isinstance(reason, QLineEdit)
            ):
                continue
            action = resolution.currentData()
            reason_code = reason.text().strip()
            if action is None or not reason_code:
                continue
            prepared = self._prepared_issue(row)
            target_source_ids = tuple(
                value.strip()
                for value in targets.text().split(",")
                if value.strip()
            )
            resolutions.append(CorrectionRebaseResolution(
                prepared,
                action,
                reason_code,
                target_source_ids if action == "remapped" else (),
            ))
        self.compare_requested.emit(tuple(resolutions))

    def _prepared_issue(self, row: int) -> str:
        source = self.issue_table.item(row, 1)
        kind = self.issue_table.item(row, 2)
        if source is None or kind is None:
            raise RuntimeError("Rendered rebase issue is incomplete.")
        snapshot_issue_id = self.issue_table.item(row, 0)
        issue_id = (
            snapshot_issue_id.data(Qt.ItemDataRole.UserRole)
            if snapshot_issue_id is not None
            else None
        )
        if not isinstance(issue_id, str):
            raise RuntimeError("Rendered rebase issue has no identity.")
        return issue_id


__all__ = ["CorrectionRebaseControls"]
