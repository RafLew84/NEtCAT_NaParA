from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


WorkflowOperation = Callable[[], object]


@dataclass(frozen=True)
class DomainAnalysisWorkflowActions:
    """Operator-owned persistence, reference, and campaign entry points."""

    save_session: WorkflowOperation | None = None
    open_session: WorkflowOperation | None = None
    publish_m6_reference: WorkflowOperation | None = None
    publish_orientation_reference: WorkflowOperation | None = None
    run_calibration: WorkflowOperation | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "save_session",
            "open_session",
            "publish_m6_reference",
            "publish_orientation_reference",
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
        self.status_label = QLabel(self)
        self.status_label.setObjectName("domainAnalysisReferenceWorkflowStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

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
        detail = "" if result is None else f" {result}"
        self.status_label.setText(f"{label} completed.{detail}")


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
        detail = "" if result is None else f" {result}"
        self.status_label.setText(f"Calibration report published.{detail}")


__all__ = [
    "DomainAnalysisWorkflowActions",
    "M6CalibrationWorkflowSheet",
    "ReferenceDatasetWorkflowSheet",
]
