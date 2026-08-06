from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis.domain_analysis import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ABC_ORIENTATION_CLASSIFIER_ID,
    CancelDomainAnalysis,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceSnapshot,
    ReplaceDomainAnalysisDraft,
    StartDomainAnalysis,
)


ExportPublished = Callable[[DomainAnalysisPublication], None]


@dataclass(frozen=True)
class _DialogPresentation:
    request_enabled: bool
    cancel_enabled: bool
    export_enabled: bool
    overall_status: str
    m6_status: str
    classifier_status: str
    diagnosis: str


class DomainAnalysisDialog(QDialog):
    """Thin, modeless adapter for one Domain Analysis workspace."""

    _snapshot_received = pyqtSignal(object)

    def __init__(
        self,
        controller: DomainAnalysisWorkspaceController,
        *,
        m6_preset_name: str,
        classifier_preset_name: str,
        export_published: ExportPublished,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(controller, DomainAnalysisWorkspaceController):
            raise TypeError("controller must be a DomainAnalysisWorkspaceController.")
        if not callable(export_published):
            raise TypeError("export_published must be callable.")
        self._controller = controller
        self._export_published = export_published
        self.setWindowTitle("Domain Analysis")
        self.resize(620, 470)
        self._build_ui(
            _required_name(m6_preset_name, "m6_preset_name"),
            _required_name(classifier_preset_name, "classifier_preset_name"),
        )
        self._connect_controls()
        self._snapshot_received.connect(self._render_snapshot)
        subscription = controller.state_changed.connect(
            self._snapshot_received.emit
        )
        self.destroyed.connect(lambda _object=None: subscription.disconnect())
        self._render_snapshot(controller.snapshot)

    def _build_ui(
        self,
        m6_preset_name: str,
        classifier_preset_name: str,
    ) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self._build_range_group())
        layout.addWidget(self._build_policy_group(
            m6_preset_name,
            classifier_preset_name,
        ))
        layout.addWidget(self._build_status_group())
        layout.addStretch(1)
        layout.addLayout(self._build_action_row())

    def _build_range_group(self) -> QGroupBox:
        group = QGroupBox("Frame range", self)
        grid = QGridLayout(group)
        self.range_start_spin = QSpinBox(group)
        self.range_end_spin = QSpinBox(group)
        grid.addWidget(QLabel("Start frame", group), 0, 0)
        grid.addWidget(QLabel("End frame", group), 0, 1)
        grid.addWidget(self.range_start_spin, 1, 0)
        grid.addWidget(self.range_end_spin, 1, 1)
        self.use_segmentation_centroids_checkbox = QCheckBox(
            "Use segmentation centroids when available",
            group,
        )
        grid.addWidget(self.use_segmentation_centroids_checkbox, 2, 0, 1, 2)
        self.classify_abc_checkbox = QCheckBox(
            "Run M6-Gated A/B/C Classification",
            group,
        )
        grid.addWidget(self.classify_abc_checkbox, 3, 0, 1, 2)
        return group

    def _build_policy_group(
        self,
        m6_preset_name: str,
        classifier_preset_name: str,
    ) -> QGroupBox:
        group = QGroupBox("Approved presets and policies", self)
        form = QFormLayout(group)
        self.m6_preset_edit = _read_only_edit(m6_preset_name, group)
        self.classifier_preset_edit = _read_only_edit(
            classifier_preset_name,
            group,
        )
        self.aggregation_policy_edit = _read_only_edit(
            ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1.preset_id,
            group,
        )
        form.addRow("M6 preset", self.m6_preset_edit)
        form.addRow("M6-Gated A/B/C preset", self.classifier_preset_edit)
        form.addRow("Domain-label policy", self.aggregation_policy_edit)
        return group

    def _build_status_group(self) -> QGroupBox:
        group = QGroupBox("Progress", self)
        form = QFormLayout(group)
        self.overall_status_label = QLabel(group)
        self.m6_status_label = QLabel(group)
        self.classifier_status_label = QLabel(group)
        self.diagnosis_label = QLabel(group)
        self.diagnosis_label.setWordWrap(True)
        form.addRow("Overall", self.overall_status_label)
        form.addRow("M6", self.m6_status_label)
        form.addRow("M6-Gated A/B/C", self.classifier_status_label)
        form.addRow("Diagnosis", self.diagnosis_label)
        return group

    def _build_action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.analyze_button = QPushButton("Analyze range", self)
        self.cancel_button = QPushButton("Cancel", self)
        self.export_button = QPushButton("Export results...", self)
        row.addWidget(self.analyze_button)
        row.addWidget(self.cancel_button)
        row.addStretch(1)
        row.addWidget(self.export_button)
        return row

    def _connect_controls(self) -> None:
        self.range_start_spin.valueChanged.connect(
            lambda: self._replace_draft("start")
        )
        self.range_end_spin.valueChanged.connect(
            lambda: self._replace_draft("end")
        )
        self.use_segmentation_centroids_checkbox.toggled.connect(
            lambda: self._replace_draft("geometry")
        )
        self.classify_abc_checkbox.toggled.connect(
            lambda: self._replace_draft("classifier")
        )
        self.analyze_button.clicked.connect(self._start_analysis)
        self.cancel_button.clicked.connect(
            lambda: self._controller.dispatch(CancelDomainAnalysis())
        )
        self.export_button.clicked.connect(self._export_last_publication)

    def _replace_draft(self, changed: str) -> None:
        start = self.range_start_spin.value()
        end = self.range_end_spin.value()
        if start > end:
            if changed == "start":
                end = start
                with QSignalBlocker(self.range_end_spin):
                    self.range_end_spin.setValue(end)
            else:
                start = end
                with QSignalBlocker(self.range_start_spin):
                    self.range_start_spin.setValue(start)
        draft = DomainAnalysisRequest(
            frame_range=range(start - 1, end),
            geometry_mode=(
                "segmentation_preferred"
                if self.use_segmentation_centroids_checkbox.isChecked()
                else "bbox_centers"
            ),
            classifier_ids=(
                (ABC_ORIENTATION_CLASSIFIER_ID,)
                if self.classify_abc_checkbox.isChecked()
                else ()
            ),
        )
        self._controller.dispatch(ReplaceDomainAnalysisDraft(draft))

    def _start_analysis(self) -> None:
        self._replace_draft("analyze")
        self._controller.dispatch(StartDomainAnalysis())

    def _export_last_publication(self) -> None:
        publication = self._controller.snapshot.published
        if publication is None:
            return
        try:
            self._export_published(publication)
        except Exception as error:
            self.diagnosis_label.setText(
                f"Export failed: {str(error) or error.__class__.__name__}"
            )

    def _render_snapshot(self, value: object) -> None:
        if not isinstance(value, DomainAnalysisWorkspaceSnapshot):
            raise TypeError("snapshot must be a DomainAnalysisWorkspaceSnapshot.")
        blockers = [
            QSignalBlocker(widget)
            for widget in (
                self.range_start_spin,
                self.range_end_spin,
                self.use_segmentation_centroids_checkbox,
                self.classify_abc_checkbox,
            )
        ]
        try:
            self._render_request(value)
        finally:
            del blockers
        presentation = _dialog_presentation(value)
        self._render_controls(presentation)
        self._render_status(presentation)

    def _render_request(self, snapshot: DomainAnalysisWorkspaceSnapshot) -> None:
        frame_count = snapshot.frame_count
        self.range_start_spin.setRange(1, frame_count)
        self.range_end_spin.setRange(1, frame_count)
        self.range_start_spin.setValue(snapshot.draft.frame_range.start + 1)
        self.range_end_spin.setValue(snapshot.draft.frame_range.stop)
        self.use_segmentation_centroids_checkbox.setChecked(
            snapshot.draft.geometry_mode == "segmentation_preferred"
        )
        self.classify_abc_checkbox.setChecked(
            ABC_ORIENTATION_CLASSIFIER_ID in snapshot.draft.classifier_ids
        )

    def _render_controls(self, presentation: _DialogPresentation) -> None:
        for widget in (
            self.range_start_spin,
            self.range_end_spin,
            self.use_segmentation_centroids_checkbox,
            self.classify_abc_checkbox,
        ):
            widget.setEnabled(presentation.request_enabled)
        self.analyze_button.setEnabled(presentation.request_enabled)
        self.cancel_button.setEnabled(presentation.cancel_enabled)
        self.export_button.setEnabled(presentation.export_enabled)

    def _render_status(self, presentation: _DialogPresentation) -> None:
        self.overall_status_label.setText(presentation.overall_status)
        self.m6_status_label.setText(presentation.m6_status)
        self.classifier_status_label.setText(presentation.classifier_status)
        self.diagnosis_label.setText(presentation.diagnosis)


def _required_name(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _read_only_edit(value: str, parent: QWidget) -> QLineEdit:
    edit = QLineEdit(value, parent)
    edit.setReadOnly(True)
    return edit


def _dialog_presentation(
    snapshot: DomainAnalysisWorkspaceSnapshot,
) -> _DialogPresentation:
    overall, m6, classifier = _status_texts(snapshot)
    running = snapshot.run.status == "running"
    return _DialogPresentation(
        request_enabled=not running and not snapshot.is_shutdown,
        cancel_enabled=running and not snapshot.is_shutdown,
        export_enabled=snapshot.published is not None,
        overall_status=overall,
        m6_status=m6,
        classifier_status=classifier,
        diagnosis=snapshot.run.diagnosis or "None",
    )


def _status_texts(
    snapshot: DomainAnalysisWorkspaceSnapshot,
) -> tuple[str, str, str]:
    status = snapshot.run.status
    if status == "idle":
        return "Ready", "Not run", "Not run"
    if status == "running":
        return _running_status_texts(snapshot)
    if status in {"completed", "completed_with_errors"}:
        overall = (
            "Completed" if status == "completed" else "Completed with errors"
        )
        return overall, "Completed", _completed_classifier_text(snapshot)
    if status == "canceled":
        return "Canceled", "Canceled", "Canceled"
    event = snapshot.run.event
    overall = "Failed" if event is None else f"Failed — {event.message}"
    return overall, "Failed", "Failed"


def _running_status_texts(
    snapshot: DomainAnalysisWorkspaceSnapshot,
) -> tuple[str, str, str]:
    event = snapshot.run.event
    overall = "Running" if event is None else f"Running — {event.message}"
    request = snapshot.run.request
    classifier_waiting = (
        "Waiting" if request is not None and request.classifier_ids
        else "Not requested"
    )
    if event is None or event.stage_id == "run":
        return overall, "Waiting", classifier_waiting
    event_text = _event_text(event.status, event.message)
    if event.stage_id == "m6":
        return overall, event_text, classifier_waiting
    return overall, "Completed", event_text


def _completed_classifier_text(
    snapshot: DomainAnalysisWorkspaceSnapshot,
) -> str:
    publication = snapshot.published
    if publication is None:
        return "Not run"
    result = publication.result
    label = result.classifier_status.replace("_", " ").title()
    failures = tuple(
        outcome
        for outcome in (result.classifier_outcomes or ())
        if outcome.status == "failed"
    )
    if not failures:
        return label
    details = "; ".join(
        f"{outcome.classifier_id}: {outcome.error_message} "
        f"(frame {outcome.failure_frame_index + 1})"
        for outcome in failures
        if outcome.failure_frame_index is not None
    )
    return f"{label} — {details}"


def _event_text(status: str, message: str) -> str:
    return f"{status.replace('_', ' ').title()} — {message}"
