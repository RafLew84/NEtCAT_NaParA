from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QLabel, QWidget

from moltrack.analysis.domain_analysis import (
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceSnapshot,
    DomainComponentKey,
    SelectDomainComponent,
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
