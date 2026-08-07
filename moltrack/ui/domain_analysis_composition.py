from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QMainWindow

from moltrack.analysis.domain_analysis import (
    ClassifierConfiguration,
    DomainAnalysisPublication,
    DomainAnalysisSessionState,
    DomainAnalysisSessionCacheRecords,
    DomainAnalysisViewSettings,
    DomainAnalysisWorkspaceController,
    RestoreDomainAnalysisWorkspace,
    with_scoped_domain_analysis_cache,
)
from moltrack.core import MolTrackImageSeries
from moltrack.persistence import (
    DomainAnalysisExportSettings,
    export_analysis_package,
    save_moltrack_session,
)
from moltrack.ui.dialogs.domain_analysis_dialog import DomainAnalysisDialog
from moltrack.ui.dialogs.position_analysis_workspace_dialog import (
    PositionAnalysisWorkspaceDialog,
)
from moltrack.ui.domain_analysis_overlay import DomainAnalysisOverlayPresenter
from moltrack.ui.widgets.stm_series_viewer import STMSeriesViewer


ExportSettingsFor = Callable[
    [DomainAnalysisPublication],
    DomainAnalysisExportSettings,
]


class DomainAnalysisMainWindowComposition(QObject):
    """Unrouted target composition for one MainWindow Domain Analysis workspace."""

    def __init__(
        self,
        owner: QMainWindow,
        controller: DomainAnalysisWorkspaceController,
        *,
        session_series: MolTrackImageSeries,
        classifier_configurations: Iterable[ClassifierConfiguration],
        m6_preset_name: str,
        classifier_preset_name: str,
        export_settings_for: ExportSettingsFor,
        view_settings: DomainAnalysisViewSettings | None = None,
    ) -> None:
        if not isinstance(owner, QMainWindow):
            raise TypeError("owner must be a QMainWindow.")
        if not isinstance(controller, DomainAnalysisWorkspaceController):
            raise TypeError("controller must be a DomainAnalysisWorkspaceController.")
        if not isinstance(session_series, MolTrackImageSeries):
            raise TypeError("session_series must be a MolTrackImageSeries.")
        if not callable(export_settings_for):
            raise TypeError("export_settings_for must be callable.")
        super().__init__(owner)
        self._owner = owner
        self._controller = controller
        self._session_series = session_series
        self._configurations = _configuration_index(classifier_configurations)
        self._m6_preset_name = _required_name(m6_preset_name, "m6_preset_name")
        self._classifier_preset_name = _required_name(
            classifier_preset_name,
            "classifier_preset_name",
        )
        self._export_settings_for = export_settings_for
        self._view_settings = (
            DomainAnalysisViewSettings() if view_settings is None else view_settings
        )
        if not isinstance(self._view_settings, DomainAnalysisViewSettings):
            raise TypeError("view_settings must be DomainAnalysisViewSettings.")
        viewer = getattr(owner, "viewer", None)
        if not isinstance(viewer, STMSeriesViewer):
            raise TypeError("owner must expose an STMSeriesViewer as viewer.")
        self._overlay = DomainAnalysisOverlayPresenter(controller, viewer)
        self._domain_dialog: DomainAnalysisDialog | None = None
        self._position_dialog: PositionAnalysisWorkspaceDialog | None = None

    def open_domain_analysis(self) -> DomainAnalysisDialog:
        dialog = self._domain_dialog
        if dialog is None:
            dialog = DomainAnalysisDialog(
                self._controller,
                m6_preset_name=self._m6_preset_name,
                classifier_preset_name=self._classifier_preset_name,
                export_published=self._export_published,
                parent=self._owner,
            )
            dialog.destroyed.connect(
                lambda _object=None, expected=dialog: (
                    self._clear_domain_dialog(expected)
                )
            )
            self._domain_dialog = dialog
        _show_modeless(dialog)
        return dialog

    def open_position_analysis(self) -> PositionAnalysisWorkspaceDialog:
        dialog = self._position_dialog
        if dialog is None:
            dialog = PositionAnalysisWorkspaceDialog(
                self._controller,
                export_published=self._export_published,
                parent=self._owner,
            )
            dialog.destroyed.connect(
                lambda _object=None, expected=dialog: (
                    self._clear_position_dialog(expected)
                )
            )
            self._position_dialog = dialog
        _show_modeless(dialog)
        return dialog

    def session_state(self) -> DomainAnalysisSessionState:
        snapshot = self._controller.snapshot
        try:
            configurations = tuple(
                self._configurations[classifier_id]
                for classifier_id in snapshot.draft.classifier_ids
            )
        except KeyError as error:
            raise ValueError(
                "Domain Analysis draft references an unconfigured classifier: "
                f"{error.args[0]}."
            ) from error
        state = DomainAnalysisSessionState(
            draft=snapshot.draft,
            draft_classifier_configurations=configurations,
            draft_physical_frame_ids=tuple(
                snapshot.physical_frame_ids[index]
                for index in snapshot.draft.frame_indices
            ),
            published_result=snapshot.published,
            view_settings=self._view_settings,
            selected_component=snapshot.selected_component,
            run_status=snapshot.run.status,
            run_diagnosis=snapshot.run.diagnosis,
        )
        cache_records = self._controller.session_cache_records()
        return with_scoped_domain_analysis_cache(
            state,
            cache_records,
        )

    def restore_session(
        self,
        state: DomainAnalysisSessionState,
    ) -> None:
        if not isinstance(state, DomainAnalysisSessionState):
            raise TypeError("state must be a DomainAnalysisSessionState.")
        if state.draft is None:
            raise ValueError(
                "A MainWindow Domain Analysis session must contain a draft."
            )
        snapshot = self._controller.snapshot
        expected_draft_ids = tuple(
            snapshot.physical_frame_ids[index]
            for index in state.draft.frame_indices
        )
        if (
            state.draft_physical_frame_ids
            and state.draft_physical_frame_ids != expected_draft_ids
        ):
            raise ValueError(
                "Session Domain Analysis frames do not match the Working "
                "Image Series."
            )
        active_frame_index = state.draft.frame_range.start
        if state.selected_component is not None:
            try:
                active_frame_index = snapshot.physical_frame_ids.index(
                    state.selected_component.physical_frame_id
                )
            except ValueError as error:
                raise ValueError(
                    "Session selection does not belong to the Working Image "
                    "Series."
                ) from error
        self._controller.dispatch(RestoreDomainAnalysisWorkspace(
            draft=state.draft,
            published=state.published_result,
            active_frame_index=active_frame_index,
            selected_component=state.selected_component,
            run_status=state.run_status,
            run_diagnosis=state.run_diagnosis,
        ))
        self._controller.restore_session_cache_records(
            DomainAnalysisSessionCacheRecords(
                m6_records=state.m6_cache_records,
                classifier_records=state.classifier_cache_records,
            )
        )
        self._configurations = _configuration_index(
            state.draft_classifier_configurations
        )
        self._view_settings = state.view_settings

    def save_session(self, path: str | Path):
        return save_moltrack_session(
            path,
            self._session_series,
            {"domain_analysis": self.session_state()},
        )

    def _export_published(self, publication: DomainAnalysisPublication) -> None:
        if self._controller.snapshot.published is not publication:
            raise ValueError("Export requires the current published snapshot.")
        settings = self._export_settings_for(publication)
        if not isinstance(settings, DomainAnalysisExportSettings):
            raise TypeError(
                "export_settings_for must return DomainAnalysisExportSettings."
            )
        export_analysis_package(self.session_state(), settings)

    def _clear_domain_dialog(self, expected: object) -> None:
        if self._domain_dialog is expected:
            self._domain_dialog = None

    def _clear_position_dialog(self, expected: object) -> None:
        if self._position_dialog is expected:
            self._position_dialog = None


def _configuration_index(
    values: Iterable[ClassifierConfiguration],
) -> dict[str, ClassifierConfiguration]:
    configurations = tuple(values)
    if any(not isinstance(value, ClassifierConfiguration) for value in configurations):
        raise TypeError(
            "classifier_configurations must contain ClassifierConfiguration values."
        )
    by_id = {value.identity.classifier_id: value for value in configurations}
    if len(by_id) != len(configurations):
        raise ValueError("classifier_configurations must have unique classifier IDs.")
    return by_id


def _required_name(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _show_modeless(
    dialog: DomainAnalysisDialog | PositionAnalysisWorkspaceDialog,
) -> None:
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


__all__ = ["DomainAnalysisMainWindowComposition"]
