from __future__ import annotations

import os
from functools import partial

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis.domain_analysis import (
    DomainAnalysisRequest,
    DomainAnalysisWorkspaceController,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    PublishDomainAnalysisResult,
)
from test_domain_correction_orientation import _automatic_result


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
