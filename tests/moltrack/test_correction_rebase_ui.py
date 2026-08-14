from __future__ import annotations

import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis.domain_analysis import (
    ApplyPreparedDomainCorrection,
    DomainAnalysisRequest,
    DomainAnalysisWorkspaceController,
    M6Gate,
    PreviewManualOrientation,
    PublishDomainAnalysisResult,
    SelectDomainMolecules,
)
from test_domain_correction_orientation import _automatic_result

try:
    from PyQt6.QtWidgets import QApplication, QComboBox, QLineEdit
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None
    QComboBox = None
    QLineEdit = None

if QApplication is not None:
    from moltrack.ui.dialogs.domain_analysis_dialog import DomainAnalysisDialog


@pytest.fixture(scope="module")
def qt_app():
    if QApplication is None:
        pytest.skip("PyQt6 is required for MolTrack GUI tests")
    return QApplication.instance() or QApplication([])


def test_operator_compares_resolves_and_applies_pending_rebase(qt_app) -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    automatic = _automatic_result()
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    controller.dispatch(SelectDomainMolecules(("outside",)))
    controller.dispatch(PreviewManualOrientation("D"))
    correction_preview = controller.snapshot.domain_corrections.prepared
    assert correction_preview is not None
    controller.dispatch(ApplyPreparedDomainCorrection(correction_preview))
    frame = automatic.m6_gate.frames[0]  # type: ignore[union-attr]
    moved = replace(
        frame.outside_members[0],
        point_xy_nm=(3.0, 0.0),
        raw_centroid_xy=(3.0, 0.0),
        footprint_pixels_xy=((3, 0),),
    )
    candidate = replace(
        automatic,
        m6_gate=M6Gate((replace(
            frame,
            source_geometry_fingerprint="geometry-ui-rerun",
            outside_members=(moved,),
            outside_pixels_xy=((3, 0),),
            analyzed_pixels_xy=((0, 0), (1, 0), (3, 0)),
        ),)),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, candidate))
    dialog = DomainAnalysisDialog(
        controller,
        m6_preset_name="M6 approved",
        classifier_preset_name="A/B/C approved",
        export_published=lambda _publication: None,
    )
    dialog.show()
    qt_app.processEvents()
    dialog.command_center.stage_button("correct").click()
    qt_app.processEvents()

    controls = dialog.domain_correction_sheet.rebase_controls
    assert "Pending automatic" in controls.pending_label.text()
    assert controls.compare_button.isEnabled()
    assert not controls.apply_button.isEnabled()

    controls.compare_button.click()
    qt_app.processEvents()

    assert controls.issue_table.rowCount() == 1
    assert controls.issue_table.item(0, 2).text() == "changed_geometry"
    resolution_combo = controls.issue_table.cellWidget(0, 3)
    reason_edit = controls.issue_table.cellWidget(0, 5)
    assert isinstance(resolution_combo, QComboBox)
    assert isinstance(reason_edit, QLineEdit)
    resolution_combo.setCurrentIndex(resolution_combo.findData("reapplied"))
    reason_edit.setText("geometry_verified_in_source")
    controls.compare_button.click()
    qt_app.processEvents()
    assert controls.apply_button.isEnabled()

    controls.apply_button.click()
    qt_app.processEvents()

    assert controller.snapshot.published is not None
    assert controller.snapshot.published.result is candidate
    assert controller.snapshot.domain_corrections.effective_projection is not None
    assert controller.snapshot.domain_corrections.effective_projection.molecule(
        "frame-0",
        "outside",
    ).effective_orientation == "D"
    assert "No pending" in controls.pending_label.text()

    dialog.close()
    dialog.deleteLater()
    qt_app.processEvents()
