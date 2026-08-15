from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis.domain_analysis import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ABC_ORIENTATION_CLASSIFIER_ID,
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    DomainAnalysisRequest,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceSnapshot,
    M6Preset,
    M6PresetLibrary,
    M6RunConfiguration,
)
from moltrack.ui.domain_analysis_workspace_view import (
    DomainAnalysisActionRow,
    DomainAnalysisFrameRangeBinding,
    DomainAnalysisWorkspaceActionBinding,
    DomainAnalysisWorkspaceViewBinding,
    ExportPublished,
)
from moltrack.ui.domain_correction_sheet import DomainCorrectionSheet
from moltrack.ui.domain_correction_view import DomainCorrectionActionBinding
from moltrack.ui.domain_analysis_workflow_sheet import (
    DomainAnalysisWorkflowActions,
    M6CalibrationWorkflowSheet,
    ReferenceDatasetWorkflowSheet,
)
from moltrack.ui.reference_review_sheet import ReferenceReviewSheet
from moltrack.ui.reference_review_view import ReferenceReviewActionBinding

from .domain_analysis_command_center import (
    DomainAnalysisCanvasTargetViewFor,
    DomainAnalysisCommandCenter,
    DomainAnalysisImageCanvas,
)
from .m6_current_frame_results_panel import M6CurrentFrameResultsPanel
from .m6_preset_sheet import M6PresetSheet


@dataclass(frozen=True)
class DomainAnalysisDialogPresentation:
    request_enabled: bool
    cancel_enabled: bool
    export_enabled: bool
    overall_status: str
    m6_status: str
    classifier_status: str
    diagnosis: str


class DomainAnalysisDialog(QDialog):
    """Thin, modeless adapter for one Domain Analysis workspace."""

    def __init__(
        self,
        controller: DomainAnalysisWorkspaceController,
        *,
        m6_preset_name: str,
        classifier_preset_name: str,
        export_published: ExportPublished,
        m6_preset_library: M6PresetLibrary | None = None,
        workflow_actions: DomainAnalysisWorkflowActions | None = None,
        canvas_frame_for: Callable[[int], object] | None = None,
        canvas_scale_nm_per_px: tuple[float | None, float | None] = (None, None),
        canvas_target_view_for: DomainAnalysisCanvasTargetViewFor | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(controller, DomainAnalysisWorkspaceController):
            raise TypeError("controller must be a DomainAnalysisWorkspaceController.")
        self._controller = controller
        if m6_preset_library is not None and not isinstance(
            m6_preset_library,
            M6PresetLibrary,
        ):
            raise TypeError("m6_preset_library must be an M6PresetLibrary.")
        self._m6_preset_library = m6_preset_library
        self._workflow_actions = workflow_actions or DomainAnalysisWorkflowActions()
        self.setWindowTitle("Domain Analysis")
        self.resize(1100, 760)
        self._build_ui(
            (
                _required_name(m6_preset_name, "m6_preset_name")
                if m6_preset_library is None
                else m6_preset_library.snapshot.active_preset.name
            ),
            _required_name(classifier_preset_name, "classifier_preset_name"),
            canvas_frame_for,
            canvas_scale_nm_per_px,
            canvas_target_view_for,
        )
        self._workspace_view = DomainAnalysisWorkspaceViewBinding(
            controller,
            owner=self,
            render_snapshot=self._render_snapshot,
        )
        self._range_binding = DomainAnalysisFrameRangeBinding(
            self.range_start_spin,
            self.range_end_spin,
            draft_changed=self._replace_draft,
        )
        self._workspace_actions = DomainAnalysisWorkspaceActionBinding(
            controller,
            export_published=export_published,
            sync_draft=self._replace_draft,
            analyze_button=self.analyze_button,
            cancel_button=self.cancel_button,
            export_button=self.export_button,
            diagnosis_label=self.diagnosis_label,
        )
        self._correction_actions = DomainCorrectionActionBinding(controller)
        self._review_actions = ReferenceReviewActionBinding(controller)
        self._connect_controls()
        self._workspace_view.render_initial()

    def _build_ui(
        self,
        m6_preset_name: str,
        classifier_preset_name: str,
        canvas_frame_for: Callable[[int], object] | None,
        canvas_scale_nm_per_px: tuple[float | None, float | None],
        canvas_target_view_for: DomainAnalysisCanvasTargetViewFor | None,
    ) -> None:
        layout = QVBoxLayout(self)
        analyze_sheet = QWidget(self)
        analyze_layout = QGridLayout(analyze_sheet)
        settings = QWidget(analyze_sheet)
        settings_layout = QVBoxLayout(settings)
        settings_layout.setContentsMargins(0, 0, 0, 0)
        settings_layout.addWidget(self._build_range_group())
        settings_layout.addWidget(
            self._build_policy_group(m6_preset_name, classifier_preset_name)
        )
        settings_layout.addLayout(self._build_action_row())
        settings_layout.addStretch(1)
        analyze_layout.addWidget(settings, 0, 0)
        diagnostics = self._build_status_group()
        self.current_frame_results_panel = M6CurrentFrameResultsPanel(analyze_sheet)
        analyze_layout.addWidget(self.current_frame_results_panel, 0, 1)
        analyze_layout.setColumnStretch(1, 1)
        canvas = DomainAnalysisImageCanvas(
            canvas_frame_for,
            scale_nm_per_px=canvas_scale_nm_per_px,
            target_view_for=canvas_target_view_for,
            parent=self,
        )
        self.domain_correction_sheet = DomainCorrectionSheet(self)
        self.reference_review_sheet = ReferenceReviewSheet(self)
        self.domain_hierarchy_sheet = self.domain_correction_sheet.hierarchy_sheet
        self.orientation_target_combo = self.domain_correction_sheet.target_combo
        self.orientation_reason_edit = self.domain_correction_sheet.reason_edit
        self.orientation_preview_button = self.domain_correction_sheet.preview_button
        self.orientation_reset_button = self.domain_correction_sheet.reset_button
        self.orientation_apply_button = self.domain_correction_sheet.apply_button
        self.orientation_effective_label = self.domain_correction_sheet.effective_label
        self.correction_point_selection_button = (
            self.domain_correction_sheet.point_selection_button
        )
        self.correction_polygon_selection_button = (
            self.domain_correction_sheet.polygon_selection_button
        )
        self.correction_clear_selection_button = (
            self.domain_correction_sheet.clear_selection_button
        )
        self.correction_confirm_impact_checkbox = (
            self.domain_correction_sheet.confirm_impact_checkbox
        )
        self.correction_undo_button = self.domain_correction_sheet.undo_button
        self.correction_redo_button = self.domain_correction_sheet.redo_button
        domain_controls = self.domain_correction_sheet.manual_domain_controls
        self.manual_domain_combo = domain_controls.domain_combo
        self.manual_domain_create_button = domain_controls.create_button
        self.manual_domain_move_button = domain_controls.move_button
        self.manual_domain_delete_button = domain_controls.delete_button
        self.manual_domain_restore_button = domain_controls.restore_button
        self.m6_preset_sheet = (
            M6PresetSheet(self._m6_preset_library, self)
            if self._m6_preset_library is not None
            else _unconfigured_preset_sheet(self)
        )
        self._build_release_sheets()
        self.command_center = DomainAnalysisCommandCenter(
            canvas=canvas,
            analyze_sheet=analyze_sheet,
            correct_sheet=self.domain_correction_sheet,
            review_sheet=self.reference_review_sheet,
            datasets_sheet=self.reference_dataset_sheet,
            presets_sheet=self.m6_preset_sheet,
            calibrate_sheet=self.calibration_sheet,
            diagnostics=diagnostics,
            parent=self,
        )
        layout.addWidget(self.command_center)

    def _build_release_sheets(self) -> None:
        self.reference_dataset_sheet = ReferenceDatasetWorkflowSheet(
            self._workflow_actions,
            self,
        )
        self.calibration_sheet = M6CalibrationWorkflowSheet(
            self._workflow_actions,
            self,
        )

    def _build_range_group(self) -> QGroupBox:
        group = QGroupBox("Frame range", self)
        grid = QGridLayout(group)
        self.range_start_spin = QSpinBox(group)
        self.range_end_spin = QSpinBox(group)
        grid.addWidget(QLabel("Start frame", group), 0, 0)
        grid.addWidget(QLabel("End frame", group), 0, 1)
        grid.addWidget(self.range_start_spin, 1, 0)
        grid.addWidget(self.range_end_spin, 1, 1)
        self.domain_backend_combo = QComboBox(group)
        for backend_id in (
            M6_ORIENTATION_COMPONENTS_BACKEND_ID,
            M3_M6_LATTICE_NETWORK_BACKEND_ID,
        ):
            self.domain_backend_combo.addItem(backend_id, backend_id)
        grid.addWidget(QLabel("Domain backend", group), 2, 0)
        grid.addWidget(self.domain_backend_combo, 2, 1)
        self.use_segmentation_centroids_checkbox = QCheckBox(
            "Use segmentation centroids when available",
            group,
        )
        grid.addWidget(self.use_segmentation_centroids_checkbox, 3, 0, 1, 2)
        self.classify_abc_checkbox = QCheckBox(
            "Run M6-Gated A/B/C Classification",
            group,
        )
        grid.addWidget(self.classify_abc_checkbox, 4, 0, 1, 2)
        return group

    def _build_policy_group(
        self,
        m6_preset_name: str,
        classifier_preset_name: str,
    ) -> QGroupBox:
        group = QGroupBox("Analysis presets and policies", self)
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

    def _build_action_row(self) -> DomainAnalysisActionRow:
        row = DomainAnalysisActionRow(self)
        self.analyze_button = row.analyze_button
        self.cancel_button = row.cancel_button
        self.export_button = row.export_button
        return row

    def _connect_controls(self) -> None:
        self.domain_backend_combo.currentIndexChanged.connect(self._replace_draft)
        self.use_segmentation_centroids_checkbox.toggled.connect(self._replace_draft)
        self.classify_abc_checkbox.toggled.connect(self._replace_draft)
        self.current_frame_results_panel.domain_selection_changed.connect(
            self._workspace_view.select_component
        )
        self.domain_hierarchy_sheet.highlight_requested.connect(
            self._workspace_view.highlight_hierarchy
        )
        self.command_center.canvas.molecule_selected.connect(
            self._correction_actions.select_molecule
        )
        self.command_center.canvas.polygons_selected.connect(
            self._correction_actions.select_polygons
        )
        self.domain_correction_sheet.selection_mode_changed.connect(
            self.command_center.canvas.set_selection_mode
        )
        self.domain_correction_sheet.clear_selection_requested.connect(
            self._correction_actions.clear_selection
        )
        self.domain_correction_sheet.preview_requested.connect(
            self._correction_actions.preview_manual_orientation
        )
        self.domain_correction_sheet.reset_requested.connect(
            self._correction_actions.preview_orientation_reset
        )
        self.domain_correction_sheet.apply_requested.connect(
            self._correction_actions.apply_prepared_correction
        )
        self.domain_correction_sheet.undo_requested.connect(
            self._correction_actions.undo
        )
        self.domain_correction_sheet.redo_requested.connect(
            self._correction_actions.redo
        )
        self.domain_correction_sheet.compare_rebase_requested.connect(
            self._correction_actions.compare_rebase
        )
        self.domain_correction_sheet.apply_rebase_requested.connect(
            self._correction_actions.apply_rebase
        )
        self.domain_correction_sheet.preview_invalidated.connect(
            self._correction_actions.discard_prepared_correction
        )
        self.domain_correction_sheet.create_domain_requested.connect(
            self._correction_actions.preview_create_manual_domain
        )
        self.domain_correction_sheet.move_domain_requested.connect(
            self._correction_actions.preview_move_to_manual_domain
        )
        self.domain_correction_sheet.delete_domain_requested.connect(
            self._correction_actions.preview_delete_manual_domain
        )
        self.domain_correction_sheet.restore_domain_requested.connect(
            self._correction_actions.preview_restore_manual_domain
        )
        self.reference_review_sheet.decision_requested.connect(
            self._review_actions.record_decision
        )
        self.reference_review_sheet.sign_off_requested.connect(
            self._review_actions.sign_off
        )
        if isinstance(self.m6_preset_sheet, M6PresetSheet):
            self.m6_preset_sheet.active_preset_changed.connect(
                self._activate_m6_preset
            )

    def _replace_draft(self) -> None:
        selected_backend = self.domain_backend_combo.currentData()
        configuration: M6RunConfiguration | None = None
        if self._m6_preset_library is not None:
            configuration = self._m6_preset_library.active_run_configuration()
            selected_backend = configuration.backend_id
            blocker = QSignalBlocker(self.domain_backend_combo)
            self.domain_backend_combo.setCurrentIndex(
                self.domain_backend_combo.findData(selected_backend)
            )
            del blocker
        if not isinstance(selected_backend, str):
            raise RuntimeError("Domain Analysis backend selection is unavailable.")
        draft = DomainAnalysisRequest(
            frame_range=self._range_binding.frame_range,
            backend_id=selected_backend,
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
            m6_configuration=configuration,
        )
        self._workspace_actions.replace_draft(draft)

    def _activate_m6_preset(self, value: object) -> None:
        if not isinstance(value, M6Preset):
            raise TypeError("active preset must be an M6Preset.")
        self.m6_preset_edit.setText(value.name)
        blocker = QSignalBlocker(self.domain_backend_combo)
        self.domain_backend_combo.setCurrentIndex(
            self.domain_backend_combo.findData(value.configuration.backend_id)
        )
        del blocker
        if self._controller.snapshot.run.status != "running":
            self._replace_draft()

    def _render_snapshot(self, value: object) -> None:
        if not isinstance(value, DomainAnalysisWorkspaceSnapshot):
            raise TypeError("snapshot must be a DomainAnalysisWorkspaceSnapshot.")
        self.command_center.render_snapshot(value)
        self.domain_correction_sheet.render_snapshot(value)
        self.reference_review_sheet.render_snapshot(value)
        blockers = [
            QSignalBlocker(widget)
            for widget in (
                self.domain_backend_combo,
                self.use_segmentation_centroids_checkbox,
                self.classify_abc_checkbox,
            )
        ]
        try:
            self._render_request(value)
        finally:
            del blockers
        presentation = domain_analysis_dialog_presentation(value)
        self._workspace_view.render_current_frame(
            self.current_frame_results_panel,
            value,
        )
        self._render_controls(presentation)
        self._render_status(presentation)

    def _render_request(self, snapshot: DomainAnalysisWorkspaceSnapshot) -> None:
        self._range_binding.render(
            frame_count=snapshot.frame_count,
            frame_range=snapshot.draft.frame_range,
        )
        backend_index = self.domain_backend_combo.findData(
            snapshot.draft.backend_id
        )
        self.domain_backend_combo.setCurrentIndex(backend_index)
        self.use_segmentation_centroids_checkbox.setChecked(
            snapshot.draft.geometry_mode == "segmentation_preferred"
        )
        self.classify_abc_checkbox.setChecked(
            ABC_ORIENTATION_CLASSIFIER_ID in snapshot.draft.classifier_ids
        )

    def _render_controls(
        self,
        presentation: DomainAnalysisDialogPresentation,
    ) -> None:
        self._range_binding.set_enabled(presentation.request_enabled)
        for widget in (
            self.domain_backend_combo,
            self.use_segmentation_centroids_checkbox,
            self.classify_abc_checkbox,
        ):
            widget.setEnabled(presentation.request_enabled)
        self._workspace_actions.render_controls(presentation)

    def _render_status(
        self,
        presentation: DomainAnalysisDialogPresentation,
    ) -> None:
        self._workspace_view.render_status(
            presentation,
            overall_label=self.overall_status_label,
            m6_label=self.m6_status_label,
            classifier_label=self.classifier_status_label,
            diagnosis_label=self.diagnosis_label,
        )


def _required_name(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _read_only_edit(value: str, parent: QWidget) -> QLineEdit:
    edit = QLineEdit(value, parent)
    edit.setReadOnly(True)
    return edit


def _unconfigured_preset_sheet(parent: QWidget) -> QWidget:
    page = QWidget(parent)
    page.setObjectName("domainAnalysisSheet_presets")
    layout = QVBoxLayout(page)
    layout.addWidget(QLabel("Presets", page))
    layout.addStretch(1)
    return page


def domain_analysis_dialog_presentation(
    snapshot: DomainAnalysisWorkspaceSnapshot,
) -> DomainAnalysisDialogPresentation:
    overall, m6, classifier = _status_texts(snapshot)
    running = snapshot.run.status == "running"
    return DomainAnalysisDialogPresentation(
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
        overall = "Completed" if status == "completed" else "Completed with errors"
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
        "Waiting" if request is not None and request.classifier_ids else "Not requested"
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
