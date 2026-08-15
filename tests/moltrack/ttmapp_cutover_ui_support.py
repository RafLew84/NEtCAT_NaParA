from __future__ import annotations

import os
from datetime import datetime, timezone
from itertools import count
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from PyQt6.QtGui import QFont, QFontDatabase

from moltrack.analysis.domain_analysis import (
    DomainAnalysisSessionState,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceExecution,
    DomainCorrectionModule,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    ReferenceReviewPolicy,
    RestoreDomainAnalysisWorkspace,
)
from moltrack.persistence import (
    CanonicalJsonObject,
    CorrectionAwareExportSettings,
    export_analysis_package,
    load_moltrack_session,
    save_moltrack_session,
)
from moltrack.ui.dialogs.domain_analysis_dialog import DomainAnalysisDialog
from moltrack.ui.domain_analysis_workflow_sheet import (
    DomainAnalysisWorkflowActions,
)


_NOW = datetime(2026, 8, 15, 10, 0, tzinfo=timezone.utc)
_CAPTURED_DOCUMENTATION_STAGES: set[str] = set()
_DOCUMENTATION_FONT_READY = False


def correct_and_review(
    group,
    request,
    module,
    preset_library,
    qt_app,
    tmp_path,
) -> tuple[DomainAnalysisSessionState, object]:
    _prepare_documentation_capture(qt_app)
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=(group.physical_frame_id,),
        execution=DomainAnalysisWorkspaceExecution(
            module,
            group.analysis_series,
            _InlineExecutor(),
        ),
        correction_module=DomainCorrectionModule(
            manual_domain_id_factory=_stable_id_factory(group.group_id, "manual-domain"),
            correction_operation_id_factory=_stable_id_factory(
                group.group_id, "operation"
            ),
            correction_history_id_factory=_stable_id_factory(group.group_id, "history"),
            clock=lambda: _NOW,
        ),
        review_policy=ReferenceReviewPolicy(clock=lambda: _NOW),
    )
    session_path = tmp_path / (
        f"ttmapp-{group.split}-{request.backend_id}.moltrack.json"
    )
    export_path = tmp_path / f"ttmapp-v10-{group.split}-{request.backend_id}"

    def save_session() -> object:
        return save_moltrack_session(
            session_path,
            group.series,
            {"domain_analysis": _session_state(group, controller)},
        )

    def open_session() -> Path:
        restored = load_moltrack_session(session_path).domain_analysis_state
        _restore_session(controller, restored)
        return session_path

    def export_publication(_publication) -> Path:
        return export_analysis_package(
            _session_state(group, controller),
            CorrectionAwareExportSettings(
                destination=export_path,
                source_identity=CanonicalJsonObject({
                    "source_file_name": group.source_path.name,
                    "acquisition_fingerprint": group.acquisition_fingerprint,
                    "lineage_fingerprint": group.lineage_fingerprint,
                }),
            ),
        ).package_path

    dialog = DomainAnalysisDialog(
        controller,
        m6_preset_name="TTMAPP explicit cutover preset",
        classifier_preset_name="No classifier",
        m6_preset_library=preset_library,
        workflow_actions=DomainAnalysisWorkflowActions(
            save_session=save_session,
            open_session=open_session,
        ),
        export_published=export_publication,
        canvas_frame_for=lambda _frame_index: group.series.raw_frames[0],
    )
    dialog.show()
    _activate_preset_in_ui(dialog, request.backend_id, qt_app)
    dialog.command_center.stage_button("analyze").click()
    dialog.analyze_button.click()
    qt_app.processEvents()
    publication = controller.snapshot.published
    assert publication is not None, (
        group.split,
        request.backend_id,
        controller.snapshot.run,
    )
    assert publication.request == request
    result = publication.result
    assert dialog.command_center.current_sheet_stage == "analyze"
    assert dialog.command_center.rendered_snapshot is controller.snapshot
    _capture_documentation_stage(dialog, "analyze", qt_app)
    dialog.command_center.stage_button("correct").click()
    dialog.command_center.canvas.select_molecule(group.source_ids[0])
    dialog.orientation_target_combo.setCurrentText("A")
    dialog.orientation_reason_edit.setText("ttmapp-point-review")
    dialog.orientation_preview_button.click()
    dialog.orientation_apply_button.click()
    dialog.correction_clear_selection_button.click()
    dialog.correction_polygon_selection_button.click()
    width, height = group.series.frame_shape[1], group.series.frame_shape[0]
    dialog.command_center.canvas.select_polygons((
        ((-1.0, -1.0), (width, -1.0), (width, height), (-1.0, height)),
    ))
    qt_app.processEvents()
    assert controller.snapshot.domain_corrections.selected_source_ids == tuple(
        sorted(group.source_ids)
    )
    dialog.manual_domain_create_button.click()
    _capture_documentation_stage(dialog, "correct", qt_app)
    if not dialog.correction_confirm_impact_checkbox.isHidden():
        dialog.correction_confirm_impact_checkbox.setChecked(True)
    dialog.orientation_apply_button.click()
    dialog.orientation_target_combo.setCurrentText("B")
    dialog.orientation_reason_edit.setText("ttmapp-polygon-review")
    dialog.orientation_preview_button.click()
    if not dialog.correction_confirm_impact_checkbox.isHidden():
        dialog.correction_confirm_impact_checkbox.setChecked(True)
    dialog.orientation_apply_button.click()
    qt_app.processEvents()
    projection = controller.snapshot.domain_corrections.effective_projection
    assert projection is not None
    assert all(
        projection.molecule(group.physical_frame_id, source_id).m6_partition
        == "full_domain"
        for source_id in group.source_ids
    )
    dialog.command_center.stage_button("review").click()
    _review_target_in_ui(
        dialog.reference_review_sheet,
        "m6",
        {
            source_id: _m6_disposition(result, projection, source_id)
            for source_id in group.source_ids
        },
        qt_app,
    )
    _review_target_in_ui(
        dialog.reference_review_sheet,
        "orientation",
        {source_id: "created" for source_id in group.source_ids},
        qt_app,
    )
    _capture_documentation_stage(dialog, "review", qt_app)
    dialog.correction_clear_selection_button.click()
    dialog.command_center.stage_button("datasets").click()
    dialog.reference_dataset_sheet.save_session_button.click()
    dialog.reference_dataset_sheet.open_session_button.click()
    qt_app.processEvents()
    assert "Open session completed" in dialog.reference_dataset_sheet.status_label.text()
    state = _session_state(group, controller)
    assert load_moltrack_session(session_path).domain_analysis_state == state
    dialog.export_button.click()
    qt_app.processEvents()
    assert (export_path / "manifest.json").is_file()
    dialog.close()
    dialog.deleteLater()
    qt_app.processEvents()
    return state, result


def run_release_actions_in_ui(
    group,
    state,
    preset_library,
    workflow_actions,
    qt_app,
) -> None:
    _prepare_documentation_capture(qt_app)
    assert state.draft is not None
    controller = DomainAnalysisWorkspaceController(
        state.draft,
        physical_frame_ids=(group.physical_frame_id,),
    )
    _restore_session(controller, state)
    dialog = DomainAnalysisDialog(
        controller,
        m6_preset_name="TTMAPP explicit cutover preset",
        classifier_preset_name="No classifier",
        export_published=lambda _publication: None,
        m6_preset_library=preset_library,
        workflow_actions=workflow_actions,
        canvas_frame_for=lambda _frame_index: group.series.raw_frames[0],
    )
    dialog.show()
    _activate_preset_in_ui(
        dialog,
        M6_ORIENTATION_COMPONENTS_BACKEND_ID,
        qt_app,
    )
    dialog.command_center.stage_button("datasets").click()
    assert dialog.reference_dataset_sheet.publish_m6_button.isEnabled()
    dialog.reference_dataset_sheet.publish_m6_button.click()
    assert "M6 Reference Dataset v2 completed" in (
        dialog.reference_dataset_sheet.status_label.text()
    ), dialog.reference_dataset_sheet.status_label.text()
    dialog.reference_dataset_sheet.publish_m6_button.click()
    assert "M6 Reference Dataset v2 completed" in (
        dialog.reference_dataset_sheet.status_label.text()
    ), dialog.reference_dataset_sheet.status_label.text()
    dialog.reference_dataset_sheet.publish_m6_button.click()
    dialog.reference_dataset_sheet.publish_orientation_button.click()
    dialog.reference_dataset_sheet.publish_orientation_button.click()
    dialog.reference_dataset_sheet.publish_orientation_button.click()
    assert "Orientation Reference Dataset v2 completed" in (
        dialog.reference_dataset_sheet.status_label.text()
    )
    dialog.command_center.stage_button("calibrate").click()
    assert dialog.calibration_sheet.run_campaign_button.isEnabled()
    dialog.calibration_sheet.run_campaign_button.click()
    qt_app.processEvents()
    status = dialog.calibration_sheet.status_label.text()
    assert "Calibration report published" in status, status
    _capture_documentation_stage(dialog, "calibrate", qt_app)
    dialog.close()
    dialog.deleteLater()
    qt_app.processEvents()


class _InlineExecutor:
    def submit(self, job) -> None:
        job()

    def shutdown(self) -> None:
        pass


def _activate_preset_in_ui(dialog, backend_id, qt_app) -> None:
    sheet = dialog.m6_preset_sheet
    preset_name = f"TTMAPP explicit cutover preset [{backend_id}]"
    dialog.command_center.stage_button("presets").click()
    index = sheet.preset_combo.findData(preset_name)
    assert index >= 0
    sheet.preset_combo.setCurrentIndex(index)
    if sheet.set_active_button.isEnabled():
        sheet.set_active_button.click()
    else:
        assert "(active)" in sheet.preset_combo.currentText()
    qt_app.processEvents()
    assert sheet.preset_combo.currentData() == preset_name


def _session_state(group, controller) -> DomainAnalysisSessionState:
    snapshot = controller.snapshot
    return DomainAnalysisSessionState(
        draft=snapshot.draft,
        draft_physical_frame_ids=(group.physical_frame_id,),
        published_result=snapshot.published,
        orientation_class_catalog=snapshot.orientation_class_catalog,
        domain_corrections=snapshot.domain_corrections,
        reference_reviews=snapshot.reference_reviews,
        run_status=snapshot.run.status,
    )


def _restore_session(controller, state) -> None:
    assert state.draft is not None
    controller.dispatch(RestoreDomainAnalysisWorkspace(
        draft=state.draft,
        published=state.published_result,
        active_frame_index=state.draft.frame_range.start,
        selected_component=state.selected_component,
        run_status=state.run_status,
        orientation_class_catalog=state.orientation_class_catalog,
        domain_corrections=state.domain_corrections,
        reference_reviews=state.reference_reviews,
        run_diagnosis=state.run_diagnosis,
    ))


def _review_target_in_ui(sheet, target, dispositions, qt_app) -> None:
    sheet.target_combo.setCurrentIndex(sheet.target_combo.findData(target))
    qt_app.processEvents()
    for row in range(sheet.review_table.rowCount()):
        source_id = sheet.review_table.item(row, 0).text()
        sheet.review_table.selectRow(row)
        sheet.decision_combo.setCurrentIndex(
            sheet.decision_combo.findData(dispositions[source_id])
        )
        sheet.record_button.click()
        qt_app.processEvents()
    assert sheet.sign_off_button.isEnabled()
    sheet.sign_off_button.click()
    qt_app.processEvents()


def _stable_id_factory(group_id: str, identity_kind: str):
    sequence = count(1)

    def create() -> str:
        return str(uuid5(
            NAMESPACE_URL,
            f"moltrack:{group_id}:{identity_kind}:{next(sequence)}",
        ))

    return create


def _capture_documentation_stage(dialog, stage: str, qt_app) -> None:
    destination = os.environ.get("MOLTRACK_DOMAIN_DOC_SCREENSHOT_DIR")
    if not destination or stage in _CAPTURED_DOCUMENTATION_STAGES:
        return
    _CAPTURED_DOCUMENTATION_STAGES.add(stage)
    dialog.command_center.stage_button(stage).click()
    qt_app.processEvents()
    dialog.resize(1920, 1200)
    dialog.repaint()
    qt_app.processEvents()
    if dialog.width() > 1920 or dialog.height() > 1200:
        raise AssertionError(
            f"Production documentation view exceeds 1920x1200: "
            f"{dialog.width()}x{dialog.height()}"
        )
    path = Path(destination) / f"spatial-command-center-{stage}.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not dialog.grab().save(str(path), "PNG"):
        raise RuntimeError(f"Unable to save documentation screenshot: {path}")


def _prepare_documentation_capture(qt_app) -> None:
    global _DOCUMENTATION_FONT_READY
    if (
        _DOCUMENTATION_FONT_READY
        or not os.environ.get("MOLTRACK_DOMAIN_DOC_SCREENSHOT_DIR")
    ):
        return
    _DOCUMENTATION_FONT_READY = True
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if not font_path.is_file():
        return
    font_id = QFontDatabase.addApplicationFont(str(font_path))
    families = QFontDatabase.applicationFontFamilies(font_id)
    if families:
        qt_app.setFont(QFont(families[0], 9))


def _m6_disposition(result, projection, source_id: str) -> str:
    gate = result.m6_gate
    assert gate is not None
    frame = gate.frames[0]
    automatic = next((
        ("full_domain", component.lattice_domain_id)
        for component in frame.full_domains
        if source_id in component.source_ids
    ), None)
    if automatic is None:
        automatic = next((
            ("small_ordered_island", None)
            for component in frame.small_ordered_islands
            if source_id in component.source_ids
        ), ("outside", None))
    molecule = projection.molecule(frame.physical_frame_id, source_id)
    effective = molecule.m6_partition, molecule.effective_domain_id
    if effective == automatic:
        return "accepted_automatic"
    if automatic[0] != "full_domain" and effective[0] == "full_domain":
        return "created"
    return "corrected"


__all__ = ["correct_and_review", "run_release_actions_in_ui"]
