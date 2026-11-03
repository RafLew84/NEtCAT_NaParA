from __future__ import annotations

import os
from functools import partial

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis.domain_analysis import (
    DomainAnalysisRequest,
    DomainAnalysisSessionState,
    DomainAnalysisWorkspaceController,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    PreviewManualOrientation,
    PublishDomainAnalysisResult,
    ReferenceReadinessError,
    ReferenceReadinessPolicy,
    RestoreDomainAnalysisWorkspace,
    SelectDomainMolecules,
)
from moltrack.persistence import publish_m6_reference_dataset
from test_domain_correction_orientation import _automatic_result
from test_m6_reference_dataset_v2 import _m6_reviewed_state, _measurement, _settings


DomainAnalysisRequest = partial(
    DomainAnalysisRequest,
    backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
)

try:
    from PyQt6.QtWidgets import QApplication
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None

if QApplication is not None:
    from moltrack.ui.dialogs.domain_analysis_dialog import DomainAnalysisDialog
    from moltrack.ui.domain_analysis_workflow_sheet import (
        DomainAnalysisWorkflowActions,
        ReferenceDatasetWorkflowSheet,
    )
    from moltrack.ui.reference_review_sheet import ReferenceReviewSheet


@pytest.fixture(scope="module")
def qt_app():
    if QApplication is None:
        pytest.skip("PyQt6 is required for MolTrack GUI tests")
    return QApplication.instance() or QApplication([])


def test_review_sheet_signs_off_m6_without_signing_orientation(qt_app) -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, _automatic_result()))
    dialog = DomainAnalysisDialog(
        controller,
        m6_preset_name="M6 approved",
        classifier_preset_name="A/B/C approved",
        export_published=lambda _publication: None,
    )
    dialog.show()
    qt_app.processEvents()

    dialog.command_center.stage_button("review").click()
    qt_app.processEvents()

    sheet = dialog.reference_review_sheet
    assert dialog.command_center.current_sheet_stage == "review"
    assert sheet.review_table.rowCount() == 3
    assert tuple(
        sheet.review_table.item(row, 0).text()
        for row in range(sheet.review_table.rowCount())
    ) == ("full", "island", "outside")
    assert sheet.m6_status_label.text() == "Draft"
    assert sheet.orientation_status_label.text() == "Draft"
    assert not sheet.sign_off_button.isEnabled()

    for row in range(sheet.review_table.rowCount()):
        sheet.review_table.selectRow(row)
        sheet.decision_combo.setCurrentIndex(
            sheet.decision_combo.findData("accepted_automatic")
        )
        sheet.record_button.click()
        qt_app.processEvents()
    assert sheet.sign_off_button.isEnabled()

    sheet.sign_off_button.click()
    qt_app.processEvents()

    assert sheet.m6_status_label.text() == "Reviewed"
    assert sheet.orientation_status_label.text() == "Draft"
    assert controller.snapshot.reference_reviews.review_for(
        "frame-0",
        "m6",
    ).status == "reviewed"
    assert controller.snapshot.reference_reviews.review_for(
        "frame-0",
        "orientation",
    ).status == "draft"

    dialog.close()
    dialog.deleteLater()
    qt_app.processEvents()


def test_export_and_calibrate_navigation_never_sign_off_review(qt_app) -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, _automatic_result()))
    exported = []
    dialog = DomainAnalysisDialog(
        controller,
        m6_preset_name="M6 approved",
        classifier_preset_name="A/B/C approved",
        export_published=exported.append,
    )
    dialog.show()
    qt_app.processEvents()

    dialog.export_button.click()
    dialog.command_center.stage_button("calibrate").click()
    qt_app.processEvents()

    assert len(exported) == 1
    assert controller.snapshot.reference_reviews.review_for(
        "frame-0",
        "m6",
    ).status == "draft"
    assert controller.snapshot.reference_reviews.review_for(
        "frame-0",
        "orientation",
    ).status == "draft"

    dialog.close()
    dialog.deleteLater()
    qt_app.processEvents()


def test_prepared_correction_has_one_readiness_result_in_ui_and_publisher(
    qt_app,
    tmp_path,
) -> None:
    ready, controller = _ready_m6_controller()
    controller.dispatch(SelectDomainMolecules(("full",)))
    snapshot = controller.dispatch(PreviewManualOrientation("B"))
    state = DomainAnalysisSessionState(
        published_result=snapshot.published,
        orientation_class_catalog=snapshot.orientation_class_catalog,
        domain_corrections=snapshot.domain_corrections,
        reference_reviews=snapshot.reference_reviews,
    )
    measurements = (
        _measurement(tmp_path, "calibration", "calibration", state, "a"),
        _measurement(tmp_path, "validation", "validation", state, "b"),
    )

    snapshot_readiness = ReferenceReadinessPolicy().evaluate_snapshot(
        snapshot,
        "m6",
    )
    dataset_readiness = ReferenceReadinessPolicy().evaluate_dataset(
        measurements,
        "m6",
    )

    assert tuple(value.code for value in snapshot_readiness.blockers) == (
        "prepared_correction",
    )
    assert dataset_readiness == snapshot_readiness
    review_sheet = ReferenceReviewSheet()
    workflow_sheet = ReferenceDatasetWorkflowSheet(
        DomainAnalysisWorkflowActions(publish_m6_reference=lambda: None)
    )
    try:
        review_sheet.render_snapshot(snapshot)
        workflow_sheet.render_snapshot(snapshot)

        assert review_sheet.readiness_label.text().startswith("Not ready")
        assert all(
            blocker.code in review_sheet.readiness_label.text()
            for blocker in snapshot_readiness.blockers
        )
        assert not workflow_sheet.publish_m6_button.isEnabled()
        with pytest.raises(ReferenceReadinessError) as raised:
            publish_m6_reference_dataset(
                measurements,
                _settings(tmp_path / "rejected-prepared"),
            )
        assert raised.value.result == dataset_readiness
    finally:
        review_sheet.close()
        workflow_sheet.close()
        review_sheet.deleteLater()
        workflow_sheet.deleteLater()
        qt_app.processEvents()


def test_publish_action_uses_dataset_readiness_including_staged_splits(
    qt_app,
    tmp_path,
) -> None:
    ready, controller = _ready_m6_controller()
    measurements = (
        _measurement(tmp_path, "calibration", "calibration", ready, "a"),
        _measurement(tmp_path, "validation", "validation", ready, "b"),
    )
    staged = []
    sheet = ReferenceDatasetWorkflowSheet(DomainAnalysisWorkflowActions(
        publish_m6_reference=lambda: None,
        m6_reference_measurements=lambda: tuple(staged),
    ))
    try:
        sheet.render_snapshot(controller.snapshot)

        assert sheet.publish_m6_button.text().startswith("Stage current")
        assert sheet.publish_m6_button.isEnabled()
        assert "calibration_split_missing" in sheet.status_label.text()
        assert "validation_split_missing" in sheet.status_label.text()

        staged.extend(measurements)
        sheet.render_snapshot(controller.snapshot)

        assert sheet.publish_m6_button.text() == (
            "Publish M6 Reference Dataset v2"
        )
        assert sheet.publish_m6_button.isEnabled()
        assert "M6 Ready" in sheet.status_label.text()

        measurements[0].source_revision.source_path.write_bytes(b"drifted")
        sheet.render_snapshot(controller.snapshot)

        assert sheet.publish_m6_button.text() == (
            "M6 Reference Dataset blocked"
        )
        assert not sheet.publish_m6_button.isEnabled()
        assert "source_revision_drifted" in sheet.status_label.text()
    finally:
        sheet.close()
        sheet.deleteLater()
        qt_app.processEvents()


def _ready_m6_controller():
    ready = _m6_reviewed_state()
    publication = ready.published_result
    assert publication is not None
    controller = DomainAnalysisWorkspaceController(
        publication.request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(RestoreDomainAnalysisWorkspace(
        draft=publication.request,
        published=publication,
        active_frame_index=0,
        selected_component=None,
        run_status="idle",
        orientation_class_catalog=ready.orientation_class_catalog,
        domain_corrections=ready.domain_corrections,
        reference_reviews=ready.reference_reviews,
    ))
    return ready, controller
