from __future__ import annotations

from typing import cast

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis.domain_analysis import (
    DomainAnalysisWorkspaceSnapshot,
    ReferenceReadiness,
    ReferenceReadinessPolicy,
    ReferenceReviewAbstention,
    ReferenceReviewDecision,
    ReferenceReviewDisposition,
    ReferenceReviewFrame,
    ReferenceReviewTarget,
)


_M6_DECISIONS = (
    ("Accept automatic", "accepted_automatic"),
    ("Corrected", "corrected"),
    ("Created", "created"),
    ("Rejected", "rejected"),
    ("Uncertain", "uncertain"),
    ("Not eligible", "not_eligible"),
)
_ORIENTATION_DECISIONS = (
    ("Accept automatic", "accepted_automatic"),
    ("Corrected", "corrected"),
    ("Created", "created"),
    ("Rejected", "rejected"),
    ("Unresolvable", "unresolvable"),
    ("Not eligible", "not_eligible"),
)


class ReferenceReviewSheet(QWidget):
    """Thin Qt projection of target-specific Reference Review state."""

    decision_requested = pyqtSignal(str, str, object)
    sign_off_requested = pyqtSignal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("referenceReviewSheet")
        self._snapshot: DomainAnalysisWorkspaceSnapshot | None = None
        self._build_ui()
        self._connect_controls()
        self._render_decision_options()
        self._render_empty()

    @property
    def target(self) -> ReferenceReviewTarget:
        value = self.target_combo.currentData()
        if value not in {"m6", "orientation"}:
            raise ValueError("Review target control has an invalid value.")
        return value

    def render_snapshot(self, snapshot: DomainAnalysisWorkspaceSnapshot) -> None:
        if not isinstance(snapshot, DomainAnalysisWorkspaceSnapshot):
            raise TypeError("snapshot must be a DomainAnalysisWorkspaceSnapshot.")
        self._snapshot = snapshot
        readiness = ReferenceReadinessPolicy().evaluate_snapshot(
            snapshot,
            self.target,
        )
        if snapshot.published is None or not snapshot.reference_reviews.frames:
            self._render_empty(readiness=readiness)
            return
        try:
            m6_review = snapshot.reference_reviews.review_for(
                snapshot.active_physical_frame_id,
                "m6",
            )
            orientation_review = snapshot.reference_reviews.review_for(
                snapshot.active_physical_frame_id,
                "orientation",
            )
        except ValueError:
            self._render_empty(
                "No Review Scope for the active frame",
                readiness=readiness,
            )
            return
        self.m6_status_label.setText(_status_text(m6_review))
        self.orientation_status_label.setText(_status_text(orientation_review))
        selected_review = (
            m6_review if self.target == "m6" else orientation_review
        )
        self.scope_label.setText(
            f"Frozen scope · {len(selected_review.scope.source_ids)} molecules · "
            f"annotation revision {selected_review.scope.annotation_revision}"
        )
        self._render_table(selected_review)
        self.readiness_label.setText(_readiness_text(readiness))
        self.sign_off_button.setEnabled(
            selected_review.is_complete and selected_review.status == "draft"
        )
        self._render_record_availability()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        status_row = QHBoxLayout()
        self.m6_status_label = QLabel(self)
        self.orientation_status_label = QLabel(self)
        self.readiness_label = QLabel(self)
        self.readiness_label.setWordWrap(True)
        status_row.addWidget(QLabel("M6 review:", self))
        status_row.addWidget(self.m6_status_label)
        status_row.addWidget(QLabel("Orientation review:", self))
        status_row.addWidget(self.orientation_status_label)
        status_row.addStretch(1)
        status_row.addWidget(self.readiness_label)
        layout.addLayout(status_row)

        target_row = QHBoxLayout()
        self.target_combo = QComboBox(self)
        self.target_combo.addItem("M6", "m6")
        self.target_combo.addItem("Orientation", "orientation")
        self.scope_label = QLabel(self)
        target_row.addWidget(QLabel("Review target", self))
        target_row.addWidget(self.target_combo)
        target_row.addWidget(self.scope_label)
        target_row.addStretch(1)
        layout.addLayout(target_row)

        self.review_table = QTableWidget(0, 5, self)
        self.review_table.setObjectName("referenceReviewLedger")
        self.review_table.setHorizontalHeaderLabels((
            "Source ID",
            "Eligibility",
            "Disposition",
            "Abstention",
            "Reason",
        ))
        self.review_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.review_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.review_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        header = self.review_table.horizontalHeader()
        assert header is not None
        header.setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.review_table)

        form = QFormLayout()
        self.decision_combo = QComboBox(self)
        self.reason_edit = QLineEdit(self)
        self.reason_edit.setPlaceholderText(
            "Required for rejection, abstention and exclusion"
        )
        form.addRow("Decision", self.decision_combo)
        form.addRow("Reason code", self.reason_edit)
        layout.addLayout(form)

        actions = QHBoxLayout()
        self.record_button = QPushButton("Record decision", self)
        self.sign_off_button = QPushButton("Sign off target", self)
        actions.addWidget(self.record_button)
        actions.addStretch(1)
        actions.addWidget(self.sign_off_button)
        layout.addLayout(actions)

    def _connect_controls(self) -> None:
        self.target_combo.currentIndexChanged.connect(self._on_target_changed)
        self.decision_combo.currentIndexChanged.connect(
            self._render_record_availability
        )
        self.reason_edit.textChanged.connect(self._render_record_availability)
        self.review_table.itemSelectionChanged.connect(
            self._render_record_availability
        )
        self.record_button.clicked.connect(self._record_decision)
        self.sign_off_button.clicked.connect(self._sign_off)

    def _on_target_changed(self) -> None:
        self._render_decision_options()
        if self._snapshot is not None:
            self.render_snapshot(self._snapshot)

    def _render_decision_options(self) -> None:
        options = (
            _M6_DECISIONS if self.target == "m6" else _ORIENTATION_DECISIONS
        )
        with QSignalBlocker(self.decision_combo):
            self.decision_combo.clear()
            for label, value in options:
                self.decision_combo.addItem(label, value)
        self._render_record_availability()

    def _render_table(self, review: ReferenceReviewFrame) -> None:
        decisions = {value.source_id: value for value in review.decisions}
        self.review_table.setRowCount(len(review.scope.source_ids))
        for row, source_id in enumerate(review.scope.source_ids):
            decision = decisions.get(source_id)
            values = (
                source_id,
                "Unreviewed" if decision is None else decision.eligibility,
                "" if decision is None or decision.disposition is None else decision.disposition,
                "" if decision is None or decision.abstention is None else decision.abstention,
                "" if decision is None or decision.reason_code is None else decision.reason_code,
            )
            for column, value in enumerate(values):
                self.review_table.setItem(row, column, QTableWidgetItem(value))

    def _render_empty(
        self,
        scope_text: str = "No published scope",
        *,
        readiness: ReferenceReadiness | None = None,
    ) -> None:
        self.m6_status_label.setText("Draft")
        self.orientation_status_label.setText("Draft")
        self.readiness_label.setText(
            "Not ready" if readiness is None else _readiness_text(readiness)
        )
        self.scope_label.setText(scope_text)
        self.review_table.setRowCount(0)
        self.sign_off_button.setEnabled(False)
        self.record_button.setEnabled(False)

    def _selected_source_id(self) -> str | None:
        row = self.review_table.currentRow()
        if row < 0:
            return None
        item = self.review_table.item(row, 0)
        return None if item is None else item.text()

    def _candidate_decision(self) -> ReferenceReviewDecision | None:
        source_id = self._selected_source_id()
        kind = self.decision_combo.currentData()
        if source_id is None or not isinstance(kind, str):
            return None
        reason = self.reason_edit.text().strip() or None
        try:
            if kind == "not_eligible":
                if reason is None:
                    return None
                return ReferenceReviewDecision.not_eligible(
                    source_id,
                    reason_code=reason,
                )
            if kind in {"uncertain", "unresolvable"}:
                if reason is None:
                    return None
                return ReferenceReviewDecision.abstain(
                    source_id,
                    cast(ReferenceReviewAbstention, kind),
                    reason_code=reason,
                )
            return ReferenceReviewDecision.eligible(
                source_id,
                disposition=cast(ReferenceReviewDisposition, kind),
                reason_code=reason,
            )
        except (TypeError, ValueError):
            return None

    def _render_record_availability(self) -> None:
        self.record_button.setEnabled(
            self._snapshot is not None and self._candidate_decision() is not None
        )

    def _record_decision(self) -> None:
        snapshot = self._snapshot
        decision = self._candidate_decision()
        if snapshot is None or decision is None:
            return
        self.decision_requested.emit(
            self.target,
            snapshot.active_physical_frame_id,
            decision,
        )

    def _sign_off(self) -> None:
        snapshot = self._snapshot
        if snapshot is None:
            return
        self.sign_off_requested.emit(
            self.target,
            snapshot.active_physical_frame_id,
        )


def _status_text(review: ReferenceReviewFrame) -> str:
    return "Reviewed" if review.status == "reviewed" else "Draft"


def _readiness_text(readiness: ReferenceReadiness) -> str:
    if readiness.ready:
        return "Ready"
    return "Not ready · " + " · ".join(
        f"{value.code}: {value.message}" for value in readiness.blockers
    )


__all__ = ["ReferenceReviewSheet"]
