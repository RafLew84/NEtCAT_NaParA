from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from moltrack.analysis.domain_analysis import (
    DomainAnalysisSessionState,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
)
from moltrack.persistence import load_moltrack_session
from moltrack.ui import MolTrackMainWindow


_CAPTURED_DOCUMENTATION_STAGES: set[str] = set()
_DOCUMENTATION_FONT_READY = False


@dataclass(frozen=True)
class MainWindowAnalysisArtifacts:
    state: DomainAnalysisSessionState
    session_path: Path
    export_path: Path


@dataclass(frozen=True)
class MainWindowReleaseArtifacts:
    m6_package: Path
    orientation_package: Path
    campaign_report: Path | None
    geometry_prompt: str | None


def analyze_in_main_window(
    group,
    backend_id,
    settings,
    qt_app,
    tmp_path,
    monkeypatch,
) -> MainWindowAnalysisArtifacts:
    """Drive one real backend through MainWindow's production composition."""

    _prepare_documentation_capture(qt_app)
    home = tmp_path / "operator-home"
    session_path = tmp_path / f"mainwindow-{group.split}-{backend_id}.moltrack.json"
    export_parent = tmp_path / "exports" / group.split / backend_id
    export_parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *_args, **_kwargs: (str(session_path), "")),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *_args, **_kwargs: (str(session_path), "")),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        staticmethod(lambda *_args, **_kwargs: str(export_parent)),
    )
    monkeypatch.setattr(
        QMessageBox,
        "critical",
        staticmethod(lambda *_args, **_kwargs: QMessageBox.StandardButton.Ok),
    )

    window = MolTrackMainWindow(
        yolo_model_discovery=lambda: [],
        sam2_checkpoint_discovery=lambda: [],
    )
    try:
        window.set_image_series(group.series)
        assert window.domain_analysis_dialog() is None
        window.btn_position_analysis.click()
        dialog = window.domain_analysis_dialog()
        assert dialog is not None
        _activate_tuned_preset(dialog, backend_id, settings, qt_app)
        dialog.command_center.stage_button("analyze").click()
        dialog.analyze_button.click()
        _wait_until(
            qt_app,
            lambda: (
                dialog.command_center.rendered_snapshot is not None
                and dialog.command_center.rendered_snapshot.run.status
                in {"completed", "completed_with_errors"}
            ),
            lambda: dialog.diagnosis_label.text(),
        )
        snapshot = dialog.command_center.rendered_snapshot
        assert snapshot is not None and snapshot.published is not None
        _capture_documentation_stage(dialog, "analyze", qt_app)
        result = snapshot.published.result
        _correct_and_review_in_ui(dialog, group, result, qt_app)
        dialog.command_center.stage_button("datasets").click()
        dialog.reference_dataset_sheet.save_session_button.click()
        _wait_until(
            qt_app,
            lambda: session_path.is_file() and window.action_open_state.isEnabled(),
            lambda: window.statusBar().currentMessage(),
        )
        dialog.reference_dataset_sheet.open_session_button.click()
        _wait_until(
            qt_app,
            lambda: (
                window.statusBar().currentMessage().startswith("Loaded state")
                and window.btn_position_analysis.isEnabled()
            ),
            lambda: window.statusBar().currentMessage(),
        )
        window.btn_position_analysis.click()
        reopened = window.domain_analysis_dialog()
        assert reopened is not None
        loaded = load_moltrack_session(session_path).domain_analysis_state
        assert loaded is not None
        reopened_snapshot = reopened.command_center.rendered_snapshot
        assert reopened_snapshot is not None
        assert reopened_snapshot.published == loaded.published_result
        reopened.command_center.stage_button("datasets").click()
        reopened.export_button.click()
        export_path = export_parent / f"{group.source_path.stem}-domain-analysis"
        _wait_until(
            qt_app,
            lambda: (export_path / "manifest.json").is_file(),
            lambda: window.statusBar().currentMessage(),
        )
        return MainWindowAnalysisArtifacts(
            state=loaded,
            session_path=session_path,
            export_path=export_path,
        )
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def _activate_tuned_preset(dialog, backend_id, settings, qt_app) -> None:
    sheet = dialog.m6_preset_sheet
    preset_name = f"TTMAPP production acceptance [{backend_id}]"
    dialog.command_center.stage_button("presets").click()
    index = sheet.preset_combo.findData(preset_name)
    if index < 0:
        built_in = {
            M6_ORIENTATION_COMPONENTS_BACKEND_ID: "TTMAPP M6 Orientation Components",
            M3_M6_LATTICE_NETWORK_BACKEND_ID: "TTMAPP M3/M6 Lattice Network",
        }[backend_id]
        index = sheet.preset_combo.findData(built_in)
        assert index >= 0
        sheet.preset_combo.setCurrentIndex(index)
        for field_name, value in settings.to_dict().items():
            control = sheet.settings_editor.control(field_name)
            if not control.isEnabled():
                continue
            if hasattr(control, "setChecked") and isinstance(value, bool):
                control.setChecked(value)
            elif hasattr(control, "setValue") and isinstance(value, (int, float)):
                control.setValue(value)
            elif hasattr(control, "setText"):
                control.setText(str(value))
        sheet.name_edit.setText(preset_name)
        sheet.description_edit.setText("Verified TTMAPP production acceptance")
        sheet.save_as_button.click()
        assert sheet.status_label.text() == f"Saved {preset_name}."
    else:
        sheet.preset_combo.setCurrentIndex(index)
    if sheet.set_active_button.isEnabled():
        sheet.set_active_button.click()
    qt_app.processEvents()
    assert sheet.preset_combo.currentData() == preset_name
    assert dialog.domain_backend_combo.currentData() == backend_id


def _correct_and_review_in_ui(dialog, group, result, qt_app) -> None:
    dialog.command_center.stage_button("correct").click()
    dialog.command_center.canvas.select_molecule(group.source_ids[0])
    dialog.orientation_target_combo.setCurrentText("A")
    dialog.orientation_reason_edit.setText("ttmapp-point-review")
    dialog.orientation_preview_button.click()
    dialog.orientation_apply_button.click()
    dialog.correction_clear_selection_button.click()
    dialog.correction_polygon_selection_button.click()
    height, width = group.series.frame_shape
    dialog.command_center.canvas.select_polygons(((
        (-1.0, -1.0),
        (width, -1.0),
        (width, height),
        (-1.0, height),
    ),))
    qt_app.processEvents()
    snapshot = dialog.command_center.rendered_snapshot
    assert snapshot is not None
    assert snapshot.domain_corrections.selected_source_ids == tuple(
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
    snapshot = dialog.command_center.rendered_snapshot
    assert snapshot is not None
    projection = snapshot.domain_corrections.effective_projection
    assert projection is not None
    physical_frame_id = snapshot.physical_frame_ids[0]
    assert all(
        projection.molecule(physical_frame_id, source_id).m6_partition
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
        {
            source_id: _orientation_disposition(
                projection,
                physical_frame_id,
                source_id,
            )
            for source_id in group.source_ids
        },
        qt_app,
    )
    _capture_documentation_stage(dialog, "review", qt_app)


def _wait_until(qt_app, predicate, failure_message, *, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert predicate(), failure_message()


def publish_release_in_main_window(
    groups,
    sessions_by_split,
    qt_app,
    tmp_path,
    monkeypatch,
    *,
    ancestry: str,
    parent_packages=None,
    run_campaign: bool = False,
    geometry_preset_name: str = "TTMAPP adaptive Calibration geometry",
) -> MainWindowReleaseArtifacts:
    """Publish root/child references through a fresh production MainWindow."""

    if ancestry not in {"new dataset root", "immutable child"}:
        raise ValueError(f"Unsupported publication ancestry: {ancestry!r}.")
    release_name = "root" if ancestry == "new dataset root" else "child"
    release_root = tmp_path / f"production-{release_name}-release"
    current_session = [None]
    current_group = [None]
    geometry_prompts: list[str] = []
    def get_open_file(*_args, **_kwargs):
        path = current_session[0]
        assert path is not None
        return str(path), ""

    def get_directory(_owner, title, *_args, **_kwargs):
        if title.startswith("Select parent m6"):
            assert parent_packages is not None
            return str(parent_packages["m6"])
        if title.startswith("Select parent orientation"):
            assert parent_packages is not None
            return str(parent_packages["orientation"])
        if title == "Publish m6 Reference Dataset v2":
            destination = release_root / "m6"
        elif title == "Publish orientation Reference Dataset v2":
            destination = release_root / "orientation"
        elif title == "Publish M6 campaign report v2":
            destination = release_root / "campaign"
        else:
            raise AssertionError(f"Unexpected directory prompt: {title!r}")
        destination.mkdir(parents=True, exist_ok=True)
        return str(destination)

    def get_item(_owner, title, label, *_args, **_kwargs):
        group = current_group[0]
        if label == "Whole measurement group split":
            assert group is not None
            return group.split, True
        if label == "Publication ancestry":
            return ancestry, True
        if label.startswith("Select first-shell geometry policy"):
            geometry_prompts.append(label)
            return "adaptive", True
        prompt_group = next(value for value in groups if value.group_id in title)
        return (
            "trifold" if prompt_group.split == "calibration" else "sixfold"
        ), True

    def get_text(_owner, title, label, *_args, **_kwargs):
        group = current_group[0]
        if label == "Stable measurement_group_id":
            assert group is not None
            return group.group_id, True
        if label == "Stable acquisition fingerprint":
            assert group is not None
            return group.acquisition_fingerprint, True
        if label == "Stable sample/condition lineage fingerprint":
            assert group is not None
            return group.lineage_fingerprint, True
        if label == "Active preset name":
            return geometry_preset_name, True
        if label == "Stable dataset_id":
            return (
                "ttmapp-m6-cutover"
                if "m6" in title.lower()
                else "ttmapp-orientation-cutover"
            ), True
        raise AssertionError(f"Unexpected text prompt: {title!r} / {label!r}")

    def get_edges(_owner, title, _label, *_args, **_kwargs):
        group = next(value for value in groups if value.group_id in title)
        left, right = group.reviewed_first_shell_edge
        return f"{left},{right}", True

    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(get_open_file))
    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        staticmethod(get_directory),
    )
    monkeypatch.setattr(QInputDialog, "getItem", staticmethod(get_item))
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(get_text))
    monkeypatch.setattr(
        QInputDialog,
        "getMultiLineText",
        staticmethod(get_edges),
    )
    objectives = iter((0.9, 0.8, 0.2, 0.2))
    monkeypatch.setattr(
        QInputDialog,
        "getDouble",
        staticmethod(
            lambda *_args, **_kwargs: (next(objectives), True)
        ),
    )
    monkeypatch.setattr(
        QMessageBox,
        "question",
        staticmethod(lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes),
    )

    window = MolTrackMainWindow(
        yolo_model_discovery=lambda: [],
        sam2_checkpoint_discovery=lambda: [],
    )
    try:
        dialog = None
        for group in groups:
            current_group[0] = group
            current_session[0] = sessions_by_split[group.split]
            window.action_open_state.trigger()
            _wait_until(
                qt_app,
                lambda: (
                    window.statusBar().currentMessage().startswith("Loaded state")
                    and window.btn_position_analysis.isEnabled()
                ),
                lambda: window.statusBar().currentMessage(),
            )
            window.btn_position_analysis.click()
            dialog = window.domain_analysis_dialog()
            assert dialog is not None
            dialog.command_center.stage_button("datasets").click()
            assert dialog.reference_dataset_sheet.publish_m6_button.isEnabled()
            dialog.reference_dataset_sheet.publish_m6_button.click()
            assert dialog.reference_dataset_sheet.publish_orientation_button.isEnabled()
            dialog.reference_dataset_sheet.publish_orientation_button.click()
            qt_app.processEvents()
        assert dialog is not None
        dialog.reference_dataset_sheet.publish_m6_button.click()
        m6_status = dialog.reference_dataset_sheet.status_label.text()
        assert "M6 Reference Dataset v2 completed" in m6_status, m6_status
        dialog.reference_dataset_sheet.publish_orientation_button.click()
        orientation_status = dialog.reference_dataset_sheet.status_label.text()
        assert "Orientation Reference Dataset v2 completed" in orientation_status, (
            orientation_status
        )
        report_path = None
        if run_campaign:
            dialog.command_center.stage_button("calibrate").click()
            assert dialog.calibration_sheet.run_campaign_button.isEnabled()
            dialog.calibration_sheet.run_campaign_button.click()
            campaign_status = dialog.calibration_sheet.status_label.text()
            assert "Calibration report published" in campaign_status, campaign_status
            _capture_documentation_stage(dialog, "calibrate", qt_app)
            reports = tuple(
                (release_root / "campaign" / "m6-campaign-report-v2").glob(
                    "m6-campaign-report-v2-*/m6_campaign_report_v2.json"
                )
            )
            assert len(reports) == 1
            report_path = reports[0]
        return MainWindowReleaseArtifacts(
            m6_package=(
                release_root / "m6" / "ttmapp-m6-cutover-reference-v2"
            ),
            orientation_package=(
                release_root
                / "orientation"
                / "ttmapp-orientation-cutover-reference-v2"
            ),
            campaign_report=report_path,
            geometry_prompt=(geometry_prompts[0] if geometry_prompts else None),
        )
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


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


def _orientation_disposition(
    projection,
    physical_frame_id: str,
    source_id: str,
) -> str:
    molecule = projection.molecule(physical_frame_id, source_id)
    assert molecule.manual_decision is not None
    classification = molecule.automatic_classification
    if classification is not None and classification.classification_status == "classified":
        return "corrected"
    return "created"


__all__ = [
    "MainWindowAnalysisArtifacts",
    "MainWindowReleaseArtifacts",
    "analyze_in_main_window",
    "publish_release_in_main_window",
]
