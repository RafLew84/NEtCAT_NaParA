from __future__ import annotations

import json
import os
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMessageBox,
    QWidget,
)

from moltrack.analysis.domain_analysis import (
    DomainAnalysisSeries,
    ReferenceReadinessError,
    ReferenceReadinessPolicy,
)
from moltrack.core import MolTrackImageSeries
from moltrack.persistence import publish_m6_reference_dataset
from moltrack.ui.domain_analysis_release_workflow import (
    DomainAnalysisReleaseWorkflow,
)
from moltrack.ui.domain_analysis_reference_workflow import (
    DomainAnalysisReferenceWorkflow,
)
from moltrack.ui.domain_analysis_workflow_sheet import (
    ReferenceDatasetWorkflowSheet,
)
from test_m6_reference_dataset_v2 import (
    _conflicted_state,
    _m6_reviewed_state,
    _measurement,
    _quarantined_state,
    _settings,
    _stale_state,
)
from test_domain_correction_orientation import _classifier_configuration
from test_orientation_reference_dataset_v2 import _orientation_reviewed_state


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def test_references_ui_previews_and_publishes_immutable_m6_child(
    qt_app,
    tmp_path,
    monkeypatch,
) -> None:
    state = _m6_reviewed_state()
    assert state.published_result is not None
    state = replace(
        state,
        draft=state.published_result.request,
        draft_classifier_configurations=(_classifier_configuration(),),
        draft_physical_frame_ids=("frame-0",),
    )
    calibration = _measurement(
        tmp_path, "calibration", "calibration", state, "a"
    )
    validation = _measurement(
        tmp_path, "validation", "validation", state, "b"
    )
    parent_path = tmp_path / "parent"
    parent = publish_m6_reference_dataset(
        (calibration, validation),
        _settings(parent_path),
    )
    parent_bytes = _package_bytes(parent_path)
    calibration.source_revision.source_path.write_bytes(b"changed calibration")
    child_root = tmp_path / "child-root"
    child_path = child_root / "ttmapp-m6-reference-reference-v2"
    series_by_split = {
        "calibration": _series(calibration.source_revision.source_path),
        "validation": _series(validation.source_revision.source_path),
    }
    splits = iter(("calibration", "validation"))
    active_split = ["calibration"]
    previews: list[str] = []

    def get_item(_owner, _title, label, *_args, **_kwargs):
        if label == "Whole measurement group split":
            active_split[0] = next(splits)
            return active_split[0], True
        if label == "Publication ancestry":
            return "immutable child", True
        if label.startswith("Symmetry for"):
            return "sixfold", True
        raise AssertionError(f"Unexpected item prompt: {label}")

    def get_text(_owner, _title, label, *_args, **_kwargs):
        split = active_split[0]
        values = {
            "Stable measurement_group_id": split,
            "Stable acquisition fingerprint": f"acquisition-{split}",
            "Stable sample/condition lineage fingerprint": f"lineage-{split}",
            "Stable dataset_id": "ttmapp-m6-reference",
        }
        return values[label], True

    def select_directory(_owner, title, *_args, **_kwargs):
        if title.startswith("Select parent"):
            return str(parent_path)
        return str(child_root)

    def confirm(_owner, _title, message, *_args, **_kwargs):
        assert not child_path.exists()
        previews.append(message)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(get_item))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(get_text))
    monkeypatch.setattr(
        QInputDialog,
        "getMultiLineText",
        staticmethod(
            lambda *_args, **_kwargs: (
                "full,island\nisland,outside",
                True,
            )
        ),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        staticmethod(select_directory),
    )
    monkeypatch.setattr(QMessageBox, "question", staticmethod(confirm))
    workspaces = iter((
        (state, series_by_split["calibration"], DomainAnalysisSeries(()), None),
        (state, series_by_split["validation"], DomainAnalysisSeries(()), None),
    ))
    owner = QWidget()
    release = DomainAnalysisReleaseWorkflow(owner)
    actions = release.actions(
        lambda: next(workspaces),
        save_session=lambda: None,
        open_session=lambda: None,
    )
    sheet = ReferenceDatasetWorkflowSheet(actions, owner)

    try:
        sheet.publish_m6_button.click()
        sheet.publish_m6_button.click()
        sheet.publish_m6_button.click()

        assert len(previews) == 1, sheet.status_label.text()
        summary = previews[0]
        manifest = _json(child_path / "manifest.json")
        measurement_rows = _json_lines(child_path / "measurements.jsonl")
        assert parent.version_id in summary
        assert "Validation epoch: preserve" in summary
        assert all(
            row["source_revision_id"] in summary for row in measurement_rows
        )
        assert all(
            value["partition_fingerprint"] in summary
            for value in manifest["partitions"].values()
        )
        assert manifest["parent_version_id"] == parent.version_id
        assert manifest["dataset_version"] == 2
        assert manifest["validation_epoch"]["epoch_id"] == (
            parent.validation_epoch_id
        )
        assert _package_bytes(parent_path) == parent_bytes
        assert "completed" in sheet.status_label.text()
    finally:
        owner.close()
        owner.deleteLater()
        qt_app.processEvents()


@pytest.mark.parametrize(
    ("target", "ready_state"),
    (
        ("m6", _m6_reviewed_state),
        ("orientation", _orientation_reviewed_state),
    ),
)
@pytest.mark.parametrize(
    "not_ready_state",
    (_stale_state, _conflicted_state, _quarantined_state),
    ids=("stale", "conflicted", "quarantined"),
)
def test_reference_workflow_uses_one_readiness_contract_for_both_targets(
    qt_app,
    tmp_path,
    target,
    ready_state,
    not_ready_state,
) -> None:
    ready = ready_state()
    publication = ready.published_result
    assert publication is not None
    state = replace(
        not_ready_state(ready),
        draft=publication.request,
        draft_classifier_configurations=(_classifier_configuration(),),
        draft_physical_frame_ids=("frame-0",),
    )
    expected = ReferenceReadinessPolicy().evaluate_snapshot(state, target)
    owner = QWidget()
    workflow = DomainAnalysisReferenceWorkflow(owner)

    try:
        with pytest.raises(ReferenceReadinessError) as raised:
            workflow.publish_reference(
                target,
                lambda: (
                    state,
                    _series(tmp_path / f"{target}.mpp"),
                    DomainAnalysisSeries(()),
                    None,
                ),
            )

        assert raised.value.result == expected
    finally:
        owner.close()
        owner.deleteLater()
        qt_app.processEvents()


def _series(source_path) -> MolTrackImageSeries:
    return MolTrackImageSeries(
        source_path=str(source_path),
        raw_frames=np.zeros((1, 1, 1), dtype=np.float32),
        metadata=SimpleNamespace(pixels_x=1, pixels_y=1),
    )


def _package_bytes(path) -> dict[str, bytes]:
    return {
        value.relative_to(path).as_posix(): value.read_bytes()
        for value in path.rglob("*")
        if value.is_file()
    }


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _json_lines(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
