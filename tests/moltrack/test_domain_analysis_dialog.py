from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    CancelDomainAnalysis,
    DomainAnalysisEvent,
    DomainAnalysisModule,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisSessionState,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceExecution,
    ReceiveDomainAnalysisEvent,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256
from moltrack.persistence import (
    CanonicalJsonObject,
    DomainAnalysisExportSettings,
    export_analysis_package,
)
from test_domain_analysis_module import (
    _ControlledClassifier,
    _DeterministicM6Adapter,
    _classifier_series,
)
from test_domain_analysis_workspace_lifecycle import _ManualExecutor

try:
    from PyQt6.QtWidgets import QApplication, QSpinBox
except ImportError:  # pragma: no cover - optional outside target GUI env
    QApplication = None
    QSpinBox = None

if QApplication is not None:
    from moltrack.ui.dialogs.domain_analysis_dialog import DomainAnalysisDialog


@pytest.fixture(scope="module")
def qt_app():
    if QApplication is None:
        pytest.skip("PyQt6 is required for MolTrack GUI tests")
    return QApplication.instance() or QApplication([])


def _workspace(
    executor: _ManualExecutor,
    *,
    classifier_failure_frame: int | None = None,
    m6_failure_frame: int | None = None,
    m6_settings_fingerprint: str = "m6-settings-v1",
) -> DomainAnalysisWorkspaceController:
    series = _classifier_series(range(3))
    classifier = _ControlledClassifier(
        ABC_ORIENTATION_CLASSIFIER_ID,
        [],
        {"active": 0, "max_active": 0},
        fail_frame_index=classifier_failure_frame,
    )
    execution = DomainAnalysisWorkspaceExecution(
        DomainAnalysisModule(
            _DeterministicM6Adapter(
                reorder_adapter_output=False,
                fail_frame_index=m6_failure_frame,
                m6_settings_fingerprint=m6_settings_fingerprint,
            ),
            classifier_adapters={ABC_ORIENTATION_CLASSIFIER_ID: classifier},
        ),
        series,
        executor,
    )
    return DomainAnalysisWorkspaceController(
        DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
        ),
        physical_frame_ids=tuple(
            frame.geometry.physical_frame_id for frame in series.frames
        ),
        execution=execution,
    )


def test_dialog_runs_one_range_and_exports_exact_publication(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    exported: list[DomainAnalysisPublication] = []
    dialog = DomainAnalysisDialog(
        controller,
        m6_preset_name="TTMAPP M6 approved",
        classifier_preset_name="TTMAPP A/B/C approved",
        export_published=exported.append,
    )
    dialog.show()

    assert len(dialog.findChildren(QSpinBox)) == 2
    assert dialog.m6_preset_edit.isReadOnly()
    assert dialog.classifier_preset_edit.isReadOnly()
    assert dialog.aggregation_policy_edit.isReadOnly()
    assert dialog.classify_abc_checkbox.isChecked()
    assert "m6-gated" in dialog.classify_abc_checkbox.text().lower()
    assert "compare" not in dialog.windowTitle().lower()
    dialog.range_start_spin.setValue(2)
    dialog.range_end_spin.setValue(3)

    assert controller.snapshot.draft.frame_range == range(1, 3)
    dialog.analyze_button.click()
    assert controller.snapshot.run.status == "running"
    assert dialog.cancel_button.isEnabled()
    assert not dialog.range_start_spin.isEnabled()

    executor.run_next()
    qt_app.processEvents()

    assert controller.snapshot.run.status == "completed"
    assert "completed" in dialog.overall_status_label.text().lower()
    assert dialog.export_button.isEnabled()
    publication = controller.snapshot.published
    assert publication is not None

    dialog.export_button.click()

    assert exported == [publication]
    assert exported[0] is publication
    dialog.close()
    dialog.deleteLater()
    qt_app.processEvents()


def test_cancel_preserves_and_exports_previous_publication(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    exported: list[DomainAnalysisPublication] = []
    dialog = _dialog(controller, exported.append)

    dialog.analyze_button.click()
    executor.run_next()
    previous = controller.snapshot.published
    assert previous is not None
    dialog.range_end_spin.setValue(2)
    dialog.analyze_button.click()

    assert controller.snapshot.run.status == "running"
    assert controller.snapshot.published is previous
    assert dialog.export_button.isEnabled()
    dialog.export_button.click()
    assert exported == [previous]
    dialog.cancel_button.click()

    assert controller.snapshot.run.status == "canceled"
    assert controller.snapshot.published is previous
    assert not dialog.cancel_button.isEnabled()
    assert dialog.range_end_spin.isEnabled()
    dialog.export_button.click()
    assert exported == [previous, previous]
    executor.run_next()
    assert controller.snapshot.published is previous
    _dispose(dialog, qt_app)


def test_partial_classifier_error_keeps_m6_result_visible(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor, classifier_failure_frame=0)
    dialog = _dialog(controller, lambda publication: None)

    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()

    snapshot = controller.snapshot
    assert snapshot.run.status == "completed_with_errors"
    assert snapshot.published is not None
    assert snapshot.published.result.m6_gate is not None
    assert dialog.m6_status_label.text() == "Completed"
    classifier_status = dialog.classifier_status_label.text().lower()
    assert "completed with errors" in classifier_status
    assert "controlled classifier failure" in classifier_status
    assert "frame 1" in classifier_status
    _dispose(dialog, qt_app)


def test_classifier_progress_keeps_completed_m6_stage_visible(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor)
    dialog = _dialog(controller, lambda publication: None)
    dialog.analyze_button.click()
    identity = controller.snapshot.run.identity
    assert identity is not None

    controller.dispatch(ReceiveDomainAnalysisEvent(
        identity,
        DomainAnalysisEvent(
            stage_id=ABC_ORIENTATION_CLASSIFIER_ID,
            status="started",
            message="M6-Gated A/B/C Classification started.",
        ),
    ))
    qt_app.processEvents()

    assert dialog.m6_status_label.text() == "Completed"
    assert "started" in dialog.classifier_status_label.text().lower()
    controller.dispatch(CancelDomainAnalysis())
    _dispose(dialog, qt_app)


def test_full_failure_shows_diagnosis_without_exportable_result(qt_app) -> None:
    executor = _ManualExecutor()
    controller = _workspace(executor, m6_failure_frame=0)
    dialog = _dialog(controller, lambda publication: None)

    dialog.analyze_button.click()
    executor.run_next()
    qt_app.processEvents()

    assert controller.snapshot.run.status == "failed"
    assert controller.snapshot.published is None
    assert "failed" in dialog.overall_status_label.text().lower()
    assert "synthetic m6 backend failure" in dialog.diagnosis_label.text().lower()
    assert not dialog.export_button.isEnabled()
    _dispose(dialog, qt_app)


def test_export_callback_can_send_exact_publication_to_schema_v9(
    qt_app,
    tmp_path,
) -> None:
    m6_settings = {"preset_id": "dialog-test-m6-v1"}
    executor = _ManualExecutor()
    controller = _workspace(
        executor,
        m6_settings_fingerprint=canonical_sha256(m6_settings),
    )
    destination = tmp_path / "domain-analysis"
    received: list[DomainAnalysisPublication] = []

    def export_published(publication: DomainAnalysisPublication) -> None:
        received.append(publication)
        export_analysis_package(
            DomainAnalysisSessionState(published_result=publication),
            DomainAnalysisExportSettings(
                destination=destination,
                source_frame_indices=(41, 42, 43),
                physical_frame_ids=controller.snapshot.physical_frame_ids,
                source_identity=CanonicalJsonObject({
                    "file_name": "dialog-source.mpp",
                    "integrity": {"algorithm": "sha256", "value": "a" * 64},
                }),
                m6_settings=CanonicalJsonObject(m6_settings),
            ),
        )

    dialog = _dialog(controller, export_published)
    dialog.analyze_button.click()
    executor.run_next()
    publication = controller.snapshot.published
    assert publication is not None

    dialog.export_button.click()

    manifest = json.loads(
        (destination / "manifest.json").read_text(encoding="utf-8")
    )
    assert received == [publication]
    assert received[0] is publication
    assert manifest["export_schema_version"] == 9
    assert manifest["analysis"]["domain_analysis"]["request"]["frame_stop"] == 1
    _dispose(dialog, qt_app)


def _dialog(
    controller: DomainAnalysisWorkspaceController,
    export_published,
):
    return DomainAnalysisDialog(
        controller,
        m6_preset_name="TTMAPP M6 approved",
        classifier_preset_name="TTMAPP A/B/C approved",
        export_published=export_published,
    )


def _dispose(dialog, qt_app) -> None:
    dialog.close()
    dialog.deleteLater()
    qt_app.processEvents()
