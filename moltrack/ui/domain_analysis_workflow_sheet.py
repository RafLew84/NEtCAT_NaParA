from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from moltrack.analysis.domain_analysis import (
    DomainAnalysisWorkspaceSnapshot,
    ReferenceReadiness,
    ReferenceReadinessMeasurement,
    ReferenceReadinessPolicy,
)


WorkflowOperation = Callable[[], object]
ReferenceMeasurements = Callable[[], tuple[ReferenceReadinessMeasurement, ...]]


@dataclass(frozen=True)
class DomainAnalysisWorkflowActions:
    """Operator-owned persistence, reference, and campaign entry points."""

    save_session: WorkflowOperation | None = None
    open_session: WorkflowOperation | None = None
    publish_m6_reference: WorkflowOperation | None = None
    publish_orientation_reference: WorkflowOperation | None = None
    m6_reference_measurements: ReferenceMeasurements | None = None
    orientation_reference_measurements: ReferenceMeasurements | None = None
    run_calibration: WorkflowOperation | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "save_session",
            "open_session",
            "publish_m6_reference",
            "publish_orientation_reference",
            "m6_reference_measurements",
            "orientation_reference_measurements",
            "run_calibration",
        ):
            value = getattr(self, field_name)
            if value is not None and not callable(value):
                raise TypeError(f"{field_name} must be callable or None.")


class ReferenceDatasetWorkflowSheet(QWidget):
    """Qt adapter for session checkpoints and target-specific publication."""

    def __init__(
        self,
        actions: DomainAnalysisWorkflowActions,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("domainAnalysisSheet_datasets")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Save/Open checkpoint", self))
        self.save_session_button = self._button(
            "Save session", actions.save_session, layout
        )
        self.open_session_button = self._button(
            "Open session", actions.open_session, layout
        )
        layout.addWidget(QLabel("Publish reviewed references", self))
        self.publish_m6_button = self._button(
            "Publish M6 Reference Dataset v2",
            actions.publish_m6_reference,
            layout,
        )
        self.publish_orientation_button = self._button(
            "Publish Orientation Reference Dataset v2",
            actions.publish_orientation_reference,
            layout,
        )
        self._publish_m6_available = actions.publish_m6_reference is not None
        self._publish_orientation_available = (
            actions.publish_orientation_reference is not None
        )
        self._m6_measurements = actions.m6_reference_measurements or (lambda: ())
        self._orientation_measurements = (
            actions.orientation_reference_measurements or (lambda: ())
        )
        self._snapshot: DomainAnalysisWorkspaceSnapshot | None = None
        self.status_label = QLabel(self)
        self.status_label.setObjectName("domainAnalysisReferenceWorkflowStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

    def render_snapshot(self, snapshot: DomainAnalysisWorkspaceSnapshot) -> None:
        if not isinstance(snapshot, DomainAnalysisWorkspaceSnapshot):
            raise TypeError("snapshot must be a DomainAnalysisWorkspaceSnapshot.")
        self._snapshot = snapshot
        policy = ReferenceReadinessPolicy()
        m6_snapshot = policy.evaluate_snapshot(snapshot, "m6")
        orientation_snapshot = policy.evaluate_snapshot(snapshot, "orientation")
        m6 = policy.evaluate_dataset(
            self._m6_measurements(),
            "m6",
            candidate_snapshot=snapshot,
        )
        orientation = policy.evaluate_dataset(
            self._orientation_measurements(),
            "orientation",
            candidate_snapshot=snapshot,
        )
        _render_reference_action(
            self.publish_m6_button,
            "M6",
            self._publish_m6_available,
            m6_snapshot,
            m6,
        )
        _render_reference_action(
            self.publish_orientation_button,
            "Orientation",
            self._publish_orientation_available,
            orientation_snapshot,
            orientation,
        )
        self.status_label.setText(
            f"M6 {_readiness_summary(m6)} | "
            f"Orientation {_readiness_summary(orientation)}"
        )

    def _button(
        self,
        label: str,
        operation: WorkflowOperation | None,
        layout: QVBoxLayout,
    ) -> QPushButton:
        button = QPushButton(label, self)
        button.setEnabled(operation is not None)
        if operation is not None:
            button.clicked.connect(
                lambda _checked=False, callback=operation, name=label: self._run(
                    name, callback
                )
            )
        layout.addWidget(button)
        return button

    def _run(self, label: str, operation: WorkflowOperation) -> None:
        try:
            result = operation()
        except Exception as error:
            self.status_label.setText(
                f"{label} failed: {str(error) or error.__class__.__name__}"
            )
            return
        detail = _result_detail(result)
        completion = f"{label} completed.{detail}"
        if self._snapshot is not None:
            self.render_snapshot(self._snapshot)
            completion = f"{completion} {self.status_label.text()}"
        self.status_label.setText(completion)


class M6CalibrationWorkflowSheet(QWidget):
    """Qt adapter for the bounded campaign and one-shot Validation report."""

    def __init__(
        self,
        actions: DomainAnalysisWorkflowActions,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("domainAnalysisSheet_calibrate")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("M6 calibration campaign", self))
        self.run_campaign_button = QPushButton(
            "Run, freeze shortlist, open Validation and publish report v2",
            self,
        )
        self.run_campaign_button.setEnabled(actions.run_calibration is not None)
        if actions.run_calibration is not None:
            self.run_campaign_button.clicked.connect(self._run)
        layout.addWidget(self.run_campaign_button)
        self.status_label = QLabel(self)
        self.status_label.setObjectName("domainAnalysisCalibrationWorkflowStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch(1)
        self._operation = actions.run_calibration

    def _run(self) -> None:
        operation = self._operation
        if operation is None:
            return
        try:
            result = operation()
        except Exception as error:
            self.status_label.setText(
                "Calibration failed: "
                f"{str(error) or error.__class__.__name__}"
            )
            return
        detail = _result_detail(result)
        self.status_label.setText(f"Calibration report published.{detail}")


def _result_detail(result: object) -> str:
    if result is None:
        return ""
    value = result.name if isinstance(result, Path) else result
    return f" {value}"


def _readiness_summary(readiness: ReferenceReadiness) -> str:
    if readiness.ready:
        return "Ready"
    return "Not ready: " + "; ".join(
        f"{value.code}: {value.message}" for value in readiness.blockers
    )


def _render_reference_action(
    button: QPushButton,
    target_label: str,
    operation_available: bool,
    snapshot: ReferenceReadiness,
    dataset: ReferenceReadiness,
) -> None:
    if dataset.ready:
        button.setText(f"Publish {target_label} Reference Dataset v2")
        button.setEnabled(operation_available)
        return
    missing_split = any(
        value.code in {"calibration_split_missing", "validation_split_missing"}
        for value in dataset.blockers
    )
    if missing_split:
        button.setText(f"Stage current {target_label} reference split")
        button.setEnabled(operation_available and snapshot.ready)
        return
    button.setText(f"{target_label} Reference Dataset blocked")
    button.setEnabled(False)


__all__ = [
    "DomainAnalysisWorkflowActions",
    "M6CalibrationWorkflowSheet",
    "ReferenceDatasetWorkflowSheet",
]
