from __future__ import annotations

from dataclasses import replace

from PyQt6.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from moltrack.analysis.domain_analysis import (
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceSnapshot,
)
from moltrack.ui.domain_analysis_workspace_view import (
    DomainAnalysisActionRow,
    DomainAnalysisFrameRangeBinding,
    DomainAnalysisWorkspaceActionBinding,
    DomainAnalysisWorkspaceViewBinding,
    ExportPublished,
)
from moltrack.ui.position_analysis_workspace_presentation import (
    position_analysis_advanced_tab_text,
)

from .domain_analysis_dialog import (
    DomainAnalysisDialogPresentation,
    domain_analysis_dialog_presentation,
)
from .m6_current_frame_results_panel import M6CurrentFrameResultsPanel


_POSITION_ANALYSIS_TABS = (
    "Current frame",
    "Range trends",
    "Sixfold Bond Order",
    "Domain Types",
    "M6-Gated A/B/C",
    "Order Hierarchy",
)


class PositionAnalysisWorkspaceDialog(QDialog):
    """Unrouted read adapter for the shared Domain Analysis workspace."""

    def __init__(
        self,
        controller: DomainAnalysisWorkspaceController,
        *,
        export_published: ExportPublished,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        if not isinstance(controller, DomainAnalysisWorkspaceController):
            raise TypeError("controller must be a DomainAnalysisWorkspaceController.")
        self._controller = controller
        self.setWindowTitle("Position Analysis")
        self.resize(760, 560)
        self._build_ui()
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
        self.current_frame_results_panel.domain_selection_changed.connect(
            self._workspace_view.select_component
        )
        self._workspace_view.render_initial()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self._build_range_group())
        layout.addWidget(self._build_status_group())
        self.analysis_tabs = QTabWidget(self)
        self.current_frame_results_panel = M6CurrentFrameResultsPanel(
            self.analysis_tabs
        )
        self.analysis_tabs.addTab(
            self.current_frame_results_panel,
            _POSITION_ANALYSIS_TABS[0],
        )
        self.range_trends_view = self._add_read_only_tab(_POSITION_ANALYSIS_TABS[1])
        self.sixfold_bond_order_view = self._add_read_only_tab(
            _POSITION_ANALYSIS_TABS[2]
        )
        self.domain_types_view = self._add_read_only_tab(_POSITION_ANALYSIS_TABS[3])
        self.classifier_view = self._add_read_only_tab(_POSITION_ANALYSIS_TABS[4])
        self.order_hierarchy_view = self._add_read_only_tab(_POSITION_ANALYSIS_TABS[5])
        layout.addWidget(self.analysis_tabs)
        layout.addLayout(self._build_action_row())

    def _add_read_only_tab(self, label: str) -> QPlainTextEdit:
        view = QPlainTextEdit(self.analysis_tabs)
        view.setReadOnly(True)
        self.analysis_tabs.addTab(view, label)
        return view

    def _build_range_group(self) -> QGroupBox:
        group = QGroupBox("Frame range", self)
        form = QFormLayout(group)
        self.range_start_spin = QSpinBox(group)
        self.range_end_spin = QSpinBox(group)
        form.addRow("Start frame", self.range_start_spin)
        form.addRow("End frame", self.range_end_spin)
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

    def _replace_draft(self) -> None:
        current = self._controller.snapshot.draft
        self._workspace_actions.replace_draft(
            replace(current, frame_range=self._range_binding.frame_range)
        )

    def frame_range(self) -> tuple[int, int]:
        return self.range_start_spin.value(), self.range_end_spin.value()

    def analysis_tab_labels(self) -> tuple[str, ...]:
        return tuple(
            self.analysis_tabs.tabText(index)
            for index in range(self.analysis_tabs.count())
        )

    def _render_snapshot(self, value: object) -> None:
        if not isinstance(value, DomainAnalysisWorkspaceSnapshot):
            raise TypeError("snapshot must be a DomainAnalysisWorkspaceSnapshot.")
        self._range_binding.render(
            frame_count=value.frame_count,
            frame_range=value.draft.frame_range,
        )
        self._workspace_view.render_current_frame(
            self.current_frame_results_panel,
            value,
        )
        self._render_advanced_tabs(value)
        presentation = domain_analysis_dialog_presentation(value)
        self._workspace_view.render_status(
            presentation,
            overall_label=self.overall_status_label,
            m6_label=self.m6_status_label,
            classifier_label=self.classifier_status_label,
            diagnosis_label=self.diagnosis_label,
        )
        self._render_controls(presentation)

    def _render_controls(
        self,
        presentation: DomainAnalysisDialogPresentation,
    ) -> None:
        self._range_binding.set_enabled(presentation.request_enabled)
        self._workspace_actions.render_controls(presentation)

    def _render_advanced_tabs(
        self,
        snapshot: DomainAnalysisWorkspaceSnapshot,
    ) -> None:
        text = position_analysis_advanced_tab_text(snapshot)
        self.range_trends_view.setPlainText(text.range_trends)
        self.sixfold_bond_order_view.setPlainText(text.sixfold_bond_order)
        self.domain_types_view.setPlainText(text.domain_types)
        self.classifier_view.setPlainText(text.classifier)
        self.order_hierarchy_view.setPlainText(text.order_hierarchy)
