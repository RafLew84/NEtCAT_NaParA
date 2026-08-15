from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from dataclasses import replace
from typing import Any, Callable

import numpy as np
import pytest
from PyQt6.QtWidgets import QApplication

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    ApplyPreparedDomainCorrection,
    DomainAnalysisRequest,
    DomainAnalysisSessionState,
    DomainAnalysisWorkspaceController,
    PreviewManualOrientation,
    PublishDomainAnalysisResult,
    SelectDomainMolecules,
)
from moltrack.analysis.domain_analysis.diagnostic_funnel import (
    build_molecule_diagnostic_funnels,
)
from moltrack.core import MolTrackImageSeries
from moltrack.persistence import (
    CanonicalJsonObject,
    CorrectionAwareExportSettings,
    DomainAnalysisExportSettings,
    export_analysis_package,
    load_moltrack_session,
    save_moltrack_session,
)
from moltrack.ui import MolTrackMainWindow
from moltrack.ui import domain_analysis_runtime as runtime
from nanotrack.core import STMSequenceMetadata
from test_domain_correction_orientation import _automatic_result


WorkspaceMutation = Callable[[dict[str, Any]], None]


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def _change_checkpoint(workspace: dict[str, Any]) -> None:
    workspace["effective_projection_checkpoint"]["fingerprint"] = "tampered"


def _change_anchor_revision(workspace: dict[str, Any]) -> None:
    workspace["active_correction_set"]["revision"] += 1


def _change_stable_id(workspace: dict[str, Any]) -> None:
    workspace["active_correction_set"]["orientation_decisions"][0][
        "source_id"
    ] = "missing-source-id"


def _break_history_invariant(workspace: dict[str, Any]) -> None:
    atoms = workspace["active_correction_set"]["atoms"]
    atoms.append(deepcopy(atoms[0]))


def _add_opaque_checkpoint_audit(workspace: dict[str, Any]) -> None:
    workspace["effective_projection_checkpoint"]["opaque_audit"] = {
        "producer": "future-reader",
        "sequence": 17,
    }


@pytest.mark.parametrize(
    ("reason_code", "mutate"),
    (
        ("effective_projection_checkpoint_mismatch", _change_checkpoint),
        ("effective_projection_checkpoint_mismatch", _change_anchor_revision),
        ("effective_projection_checkpoint_mismatch", _change_stable_id),
        ("correction_workspace_invariant_violation", _break_history_invariant),
        ("effective_projection_checkpoint_mismatch", _add_opaque_checkpoint_audit),
    ),
    ids=(
        "changed-checkpoint",
        "changed-anchor-revision",
        "changed-stable-id",
        "broken-invariant",
        "opaque-checkpoint-audit",
    ),
)
def test_open_quarantines_a_nonreproducible_correction_workspace(
    tmp_path,
    reason_code: str,
    mutate: WorkspaceMutation,
) -> None:
    session_path, payload, automatic_snapshot, series = _saved_corrected_session(
        tmp_path
    )
    workspace_payload = payload["domain_analysis"]["correction_workspace"]
    mutate(workspace_payload)
    expected_audit_payload = deepcopy(workspace_payload)
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_moltrack_session(session_path)

    assert json.loads(session_path.read_text(encoding="utf-8")) == payload
    state = loaded.domain_analysis_state
    assert state is not None
    quarantine = state.correction_workspace_quarantine
    assert quarantine is not None
    assert quarantine.activation_status == "quarantined"
    assert quarantine.correction_status == "conflicted"
    assert quarantine.reason_code == reason_code
    assert quarantine.reference_ready is False
    assert quarantine.automatic_snapshot == automatic_snapshot
    assert quarantine.correction_workspace_payload == expected_audit_payload
    assert quarantine.correction_workspace_payload["active_correction_set"][
        "history_records"
    ]
    assert state.published_result is None
    assert state.domain_corrections.correction_set is None
    assert state.domain_corrections.effective_projection is None
    assert state.reference_reviews.frames == ()
    assert state.opaque_components == ()
    assert any(
        diagnostic.component == "correction_workspace"
        and diagnostic.identifier == reason_code
        for diagnostic in state.diagnostics
    )

    quarantined_save_path = tmp_path / "quarantined-copy.moltrack.json"
    with pytest.raises(
        ValueError,
        match="quarantined correction workspace cannot be saved as active",
    ):
        save_moltrack_session(
            quarantined_save_path,
            series,
            {"domain_analysis": state},
        )
    assert not quarantined_save_path.exists()

    export_settings = DomainAnalysisExportSettings(
        destination=tmp_path / "reference-ready-v9",
        source_frame_indices=(0,),
        physical_frame_ids=("frame-0",),
        source_identity=CanonicalJsonObject({"source": "quarantine-test"}),
        m6_settings=CanonicalJsonObject({"preset": "quarantine-test"}),
    )
    with pytest.raises(ValueError, match="requires a published M6 result"):
        export_analysis_package(state, export_settings)
    assert not export_settings.destination.exists()


def test_composition_preserves_quarantine_and_blocks_follow_up_save(
    qt_app,
    tmp_path,
) -> None:
    session_path, payload, _automatic_snapshot, series = _saved_corrected_session(
        tmp_path
    )
    _change_checkpoint(payload["domain_analysis"]["correction_workspace"])
    session_path.write_text(json.dumps(payload), encoding="utf-8")
    state = load_moltrack_session(session_path).domain_analysis_state
    assert state is not None and state.correction_workspace_quarantine is not None
    window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
    composition = runtime.build_domain_analysis_main_window_composition(
        window,
        series,
    )

    try:
        composition.restore_session(state)

        restored = composition.session_state()
        assert (
            restored.correction_workspace_quarantine
            == state.correction_workspace_quarantine
        )
        with pytest.raises(
            ValueError,
            match="quarantined correction workspace cannot be saved as active",
        ):
            composition.save_session(tmp_path / "ui-copy.moltrack.json")
    finally:
        composition.shutdown()
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_production_rerun_save_open_preserves_quarantine_as_audit(
    qt_app,
    tmp_path,
) -> None:
    session_path, payload, _automatic_snapshot, series = _saved_corrected_session(
        tmp_path
    )
    _change_checkpoint(payload["domain_analysis"]["correction_workspace"])
    session_path.write_text(json.dumps(payload), encoding="utf-8")
    quarantined = load_moltrack_session(session_path).domain_analysis_state
    assert quarantined is not None
    original = quarantined.correction_workspace_quarantine
    assert original is not None
    window = MolTrackMainWindow(yolo_model_discovery=lambda: [])
    composition = runtime.build_domain_analysis_main_window_composition(
        window,
        series,
    )

    try:
        composition.restore_session(quarantined)
        dialog = composition.open_domain_analysis()
        dialog.analyze_button.click()
        _wait_until(
            qt_app,
            lambda: composition.session_state().published_result is not None,
        )

        rerun = composition.session_state()
        assert rerun.published_result is not None
        assert rerun.correction_workspace_quarantine == original
        assert rerun.domain_corrections.effective_projection is not None
        assert (
            rerun.domain_corrections.effective_projection.automatic_result
            is rerun.published_result.result
        )
        saved_path = tmp_path / "rerun-with-quarantine.moltrack.json"
        composition.save_session(saved_path)
        opened = load_moltrack_session(saved_path).domain_analysis_state
        assert opened is not None
        assert opened.published_result == rerun.published_result
        assert opened.correction_workspace_quarantine == original
        assert opened.correction_workspace_quarantine.reason == original.reason
        assert (
            opened.correction_workspace_quarantine.automatic_snapshot_payload
            == original.automatic_snapshot_payload
        )
        assert (
            opened.correction_workspace_quarantine.correction_workspace_payload
            == original.correction_workspace_payload
        )
        assert (
            opened.correction_workspace_quarantine.activation_status
            == original.activation_status
        )

        composition.restore_session(opened)
        restored = composition.session_state()
        assert restored.published_result == rerun.published_result
        assert restored.correction_workspace_quarantine == original
        audit_destination = tmp_path / "rerun-audit"
        export_analysis_package(
            restored,
            CorrectionAwareExportSettings(
                destination=audit_destination,
                source_identity=CanonicalJsonObject({"source": "quarantine-rerun"}),
                export_mode="audit",
            ),
        )
        manifest = json.loads(
            (audit_destination / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest["activation_status"] == "active"
        assert "correction_workspace_quarantined" not in (
            manifest["readiness"]["blockers"]
        )
        assert (
            audit_destination / "correction_workspace_quarantine.json"
        ).is_file()
    finally:
        composition.shutdown()
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_open_quarantines_a_non_object_correction_workspace(tmp_path) -> None:
    session_path, payload, automatic_snapshot, _series = _saved_corrected_session(
        tmp_path
    )
    opaque_payload = ["malformed-workspace", {"opaque_audit": 17}]
    payload["domain_analysis"]["correction_workspace"] = opaque_payload
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    state = load_moltrack_session(session_path).domain_analysis_state

    assert state is not None
    quarantine = state.correction_workspace_quarantine
    assert quarantine is not None
    assert quarantine.activation_status == "quarantined"
    assert quarantine.correction_status == "conflicted"
    assert quarantine.reason_code == "correction_workspace_invariant_violation"
    assert quarantine.automatic_snapshot == automatic_snapshot
    assert quarantine.correction_workspace_payload == opaque_payload
    assert state.published_result is None


def test_open_quarantines_rejected_automatic_and_its_corrections(tmp_path) -> None:
    session_path, payload, _automatic_snapshot, _series = _saved_corrected_session(
        tmp_path
    )
    published_payload = payload["domain_analysis"]["published_result"]
    published_payload["m6_gate"]["frames"][0][
        "m6_gate_fingerprint"
    ] = "tampered"
    correction_payload = payload["domain_analysis"]["correction_workspace"]
    expected_published_audit = deepcopy(published_payload)
    expected_correction_audit = deepcopy(correction_payload)
    session_path.write_text(json.dumps(payload), encoding="utf-8")

    state = load_moltrack_session(session_path).domain_analysis_state

    assert state is not None
    quarantine = state.correction_workspace_quarantine
    assert quarantine is not None
    assert quarantine.activation_status == "quarantined"
    assert quarantine.correction_status == "conflicted"
    assert quarantine.reason_code == "automatic_snapshot_invariant_violation"
    assert quarantine.automatic_snapshot is None
    assert quarantine.automatic_snapshot_payload == expected_published_audit
    assert quarantine.correction_workspace_payload == expected_correction_audit
    assert state.published_result is None


def _saved_corrected_session(tmp_path):
    source_path = tmp_path / "source.mpp"
    source_path.write_bytes(b"checkpoint-quarantine")
    series = MolTrackImageSeries(
        source_path=str(source_path),
        raw_frames=np.zeros((1, 4, 4), dtype=np.uint16),
        metadata=STMSequenceMetadata(
            pixels_x=4,
            pixels_y=4,
            size_nm_x=4.0,
            size_nm_y=4.0,
        ),
    )
    request = DomainAnalysisRequest(
        frame_range=range(1),
        backend_id="m6_orientation_components",
        classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
    )
    automatic = _automatic_result()
    automatic = replace(
        automatic,
        molecule_diagnostic_funnels=build_molecule_diagnostic_funnels(automatic),
    )
    controller = DomainAnalysisWorkspaceController(
        request,
        physical_frame_ids=("frame-0",),
    )
    controller.dispatch(PublishDomainAnalysisResult(request, automatic))
    controller.dispatch(SelectDomainMolecules(("outside",)))
    controller.dispatch(PreviewManualOrientation("Z", "manual-review"))
    prepared = controller.snapshot.domain_corrections.prepared
    assert prepared is not None
    controller.dispatch(ApplyPreparedDomainCorrection(prepared))
    snapshot = controller.snapshot
    saved_draft = replace(request, classifier_ids=())
    state = DomainAnalysisSessionState(
        draft=saved_draft,
        draft_physical_frame_ids=(),
        published_result=snapshot.published,
        orientation_class_catalog=snapshot.orientation_class_catalog,
        domain_corrections=snapshot.domain_corrections,
        reference_reviews=snapshot.reference_reviews,
    )
    session_path = tmp_path / "corrected-session-v3.moltrack.json"
    save_moltrack_session(session_path, series, {"domain_analysis": state})
    payload = json.loads(session_path.read_text(encoding="utf-8"))
    assert state.published_result is not None
    return session_path, payload, state.published_result, series


def _wait_until(qt_app, predicate, *, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        qt_app.processEvents()
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for Domain Analysis rerun.")
