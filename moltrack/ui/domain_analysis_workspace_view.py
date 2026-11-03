from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PyQt6.QtCore import QObject, QSignalBlocker, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSpinBox, QWidget

from moltrack.analysis.domain_analysis import (
    CancelDomainAnalysis,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceSnapshot,
    DomainComponentKey,
    DomainHierarchyHighlight,
    ReplaceDomainAnalysisDraft,
    SelectDomainComponent,
    SetDomainHierarchyHighlight,
    StartDomainAnalysis,
)
from moltrack.analysis.m6_current_frame_results import (
    M6CurrentFrameResults,
    build_domain_analysis_current_frame_results,
)


class _CurrentFrameResultsPanel(Protocol):
    def set_results(self, results: M6CurrentFrameResults | None) -> None: ...

    def set_selected_component(
        self,
        component_key: DomainComponentKey | None,
    ) -> None: ...


class _StatusPresentation(Protocol):
    @property
    def overall_status(self) -> str: ...

    @property
    def m6_status(self) -> str: ...

    @property
    def classifier_status(self) -> str: ...

    @property
    def diagnosis(self) -> str: ...


class _ActionPresentation(Protocol):
    @property
    def request_enabled(self) -> bool: ...

    @property
    def cancel_enabled(self) -> bool: ...

    @property
    def export_enabled(self) -> bool: ...


ExportPublished = Callable[[DomainAnalysisPublication], None]
ExportAudit = Callable[[], None]


class DomainAnalysisActionRow(QHBoxLayout):
    """The shared Analyze, Cancel and Export controls for workspace adapters."""

    def __init__(self, owner: QWidget) -> None:
        super().__init__()
        self.analyze_button = QPushButton("Analyze range", owner)
        self.cancel_button = QPushButton("Cancel", owner)
        self.export_button = QPushButton("Export v10...", owner)
        self.audit_export_button = QPushButton("Export audit v10...", owner)
        self.legacy_export_button = QPushButton("Export legacy v9...", owner)
        self.addWidget(self.analyze_button)
        self.addWidget(self.cancel_button)
        self.addStretch(1)
        self.addWidget(self.legacy_export_button)
        self.addWidget(self.audit_export_button)
        self.addWidget(self.export_button)


class DomainAnalysisFrameRangeBinding:
    """Keep one-based Qt range controls aligned with a zero-based request."""

    def __init__(
        self,
        start_spin: QSpinBox,
        end_spin: QSpinBox,
        *,
        draft_changed: Callable[[], None],
    ) -> None:
        if not callable(draft_changed):
            raise TypeError("draft_changed must be callable.")
        self._start_spin = start_spin
        self._end_spin = end_spin
        self._draft_changed = draft_changed
        start_spin.valueChanged.connect(lambda: self._normalize_and_notify("start"))
        end_spin.valueChanged.connect(lambda: self._normalize_and_notify("end"))

    @property
    def frame_range(self) -> range:
        return range(self._start_spin.value() - 1, self._end_spin.value())

    def render(self, *, frame_count: int, frame_range: range) -> None:
        blockers = [QSignalBlocker(self._start_spin), QSignalBlocker(self._end_spin)]
        try:
            self._start_spin.setRange(1, frame_count)
            self._end_spin.setRange(1, frame_count)
            self._start_spin.setValue(frame_range.start + 1)
            self._end_spin.setValue(frame_range.stop)
        finally:
            del blockers

    def set_enabled(self, enabled: bool) -> None:
        self._start_spin.setEnabled(enabled)
        self._end_spin.setEnabled(enabled)

    def _normalize_and_notify(self, changed: str) -> None:
        start = self._start_spin.value()
        end = self._end_spin.value()
        if start > end:
            if changed == "start":
                with QSignalBlocker(self._end_spin):
                    self._end_spin.setValue(start)
            else:
                with QSignalBlocker(self._start_spin):
                    self._start_spin.setValue(end)
        self._draft_changed()


class DomainAnalysisWorkspaceActionBinding:
    """Share Analyze, Cancel and Export effects across workspace adapters."""

    def __init__(
        self,
        controller: DomainAnalysisWorkspaceController,
        *,
        export_published: ExportPublished,
        export_audit: ExportAudit | None,
        export_legacy_published: ExportPublished | None,
        sync_draft: Callable[[], None],
        analyze_button: QPushButton,
        cancel_button: QPushButton,
        export_button: QPushButton,
        audit_export_button: QPushButton,
        legacy_export_button: QPushButton,
        diagnosis_label: QLabel,
    ) -> None:
        if not isinstance(controller, DomainAnalysisWorkspaceController):
            raise TypeError("controller must be a DomainAnalysisWorkspaceController.")
        if not callable(export_published):
            raise TypeError("export_published must be callable.")
        if export_audit is not None and not callable(export_audit):
            raise TypeError("export_audit must be callable or None.")
        if export_legacy_published is not None and not callable(
            export_legacy_published
        ):
            raise TypeError("export_legacy_published must be callable or None.")
        if not callable(sync_draft):
            raise TypeError("sync_draft must be callable.")
        self._controller = controller
        self._export_published = export_published
        self._export_audit = export_audit
        self._export_legacy_published = export_legacy_published
        self._sync_draft = sync_draft
        self._analyze_button = analyze_button
        self._cancel_button = cancel_button
        self._export_button = export_button
        self._audit_export_button = audit_export_button
        self._legacy_export_button = legacy_export_button
        self._diagnosis_label = diagnosis_label
        analyze_button.clicked.connect(self.start_analysis)
        cancel_button.clicked.connect(self.cancel_analysis)
        export_button.clicked.connect(
            lambda _checked=False: self.export_last_publication()
        )
        audit_export_button.clicked.connect(self.export_current_audit)
        legacy_export_button.clicked.connect(
            lambda _checked=False: self.export_last_publication(
                self._export_legacy_published
            )
        )
        audit_export_button.setVisible(export_audit is not None)
        legacy_export_button.setVisible(export_legacy_published is not None)

    def replace_draft(self, draft: DomainAnalysisRequest) -> None:
        self._controller.dispatch(ReplaceDomainAnalysisDraft(draft))

    def start_analysis(self) -> None:
        self._sync_draft()
        self._controller.dispatch(StartDomainAnalysis())

    def cancel_analysis(self) -> None:
        self._controller.dispatch(CancelDomainAnalysis())

    def export_last_publication(
        self,
        callback: ExportPublished | None = None,
    ) -> None:
        export_published = self._export_published if callback is None else callback
        publication = self._controller.snapshot.published
        if publication is not None:
            self._export(lambda: export_published(publication))

    def export_current_audit(self) -> None:
        self._export(self._export_audit)

    def _export(self, callback: ExportAudit | None) -> None:
        if callback is None:
            return
        try:
            callback()
        except Exception as error:
            self._diagnosis_label.setText(
                f"Export failed: {str(error) or error.__class__.__name__}"
            )

    def render_controls(self, presentation: _ActionPresentation) -> None:
        self._analyze_button.setEnabled(presentation.request_enabled)
        self._cancel_button.setEnabled(presentation.cancel_enabled)
        self._export_button.setEnabled(presentation.export_enabled)
        self._audit_export_button.setEnabled(
            self._export_audit is not None and not presentation.cancel_enabled
        )
        self._legacy_export_button.setEnabled(
            self._export_legacy_published is not None and presentation.export_enabled
        )


class DomainAnalysisWorkspaceViewBinding(QObject):
    """Thread-safe controller binding shared by Qt workspace adapters."""

    _snapshot_received = pyqtSignal(object)

    def __init__(
        self,
        controller: DomainAnalysisWorkspaceController,
        *,
        owner: QWidget,
        render_snapshot: Callable[[object], None],
    ) -> None:
        if not isinstance(controller, DomainAnalysisWorkspaceController):
            raise TypeError("controller must be a DomainAnalysisWorkspaceController.")
        if not callable(render_snapshot):
            raise TypeError("render_snapshot must be callable.")
        super().__init__(owner)
        self._controller = controller
        self._snapshot_received.connect(render_snapshot)
        self._subscription = controller.state_changed.connect(
            self._snapshot_received.emit
        )
        owner.destroyed.connect(self._disconnect)

    def render_initial(self) -> None:
        self._snapshot_received.emit(self._controller.snapshot)

    def select_component(self, value: object) -> None:
        if value is not None and not isinstance(value, DomainComponentKey):
            raise TypeError("Domain Analysis selection must be canonical.")
        self._controller.dispatch(SelectDomainComponent(value))

    def highlight_hierarchy(self, value: object) -> None:
        if value is not None and not isinstance(value, DomainHierarchyHighlight):
            raise TypeError("Domain Analysis highlight must be canonical.")
        self._controller.dispatch(SetDomainHierarchyHighlight(value))

    @staticmethod
    def render_current_frame(
        panel: _CurrentFrameResultsPanel,
        snapshot: DomainAnalysisWorkspaceSnapshot,
    ) -> None:
        panel.set_results(
            build_domain_analysis_current_frame_results(
                snapshot.published,
                physical_frame_id=snapshot.active_physical_frame_id,
            )
        )
        panel.set_selected_component(snapshot.selected_component)

    @staticmethod
    def render_status(
        presentation: _StatusPresentation,
        *,
        overall_label: QLabel,
        m6_label: QLabel,
        classifier_label: QLabel,
        diagnosis_label: QLabel,
    ) -> None:
        overall_label.setText(presentation.overall_status)
        m6_label.setText(presentation.m6_status)
        classifier_label.setText(presentation.classifier_status)
        diagnosis_label.setText(presentation.diagnosis)

    def _disconnect(self, _object: object | None = None) -> None:
        self._subscription.disconnect()
