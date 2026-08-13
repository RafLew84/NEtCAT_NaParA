from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from moltrack.analysis import TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint
from moltrack.analysis.domain_analysis import (
    DomainAnalysisRequest,
    DomainAnalysisWorkspaceController,
    DomainBackendIdentity,
    FirstShellGeometryPolicy,
    M6Preset,
    M6PresetLibrary,
    M6RunConfiguration,
    encode_m6_preset_file,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
)
from moltrack.ui.dialogs.domain_analysis_dialog import DomainAnalysisDialog
from moltrack.ui.dialogs.m6_preset_sheet import M6PresetSheet
from PyQt6.QtWidgets import QDoubleSpinBox


_NOW = datetime(2026, 8, 13, 8, 0, tzinfo=timezone.utc)


def _configuration(q_seed: float) -> M6RunConfiguration:
    settings = replace(TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET, q_seed=q_seed)
    return M6RunConfiguration(
        backend_identity=DomainBackendIdentity(
            backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
            result_schema_version="domain-backend-result-v1",
            algorithm_version="moltrack-m6-orientation-v1",
            settings_fingerprint=m6_settings_fingerprint(settings),
            adapter_owner="analyze_m6_orientation_domains",
            native_evidence_kind="m6_orientation_evidence_v1",
            capabilities=("common_partition", "orientation_components"),
        ),
        settings=settings,
        first_shell_geometry=FirstShellGeometryPolicy.fixed(
            r_min_nm=settings.first_shell_r_min_nm,
            r_max_nm=settings.first_shell_r_max_nm,
        ),
    )


def test_presets_stage_saves_and_activates_future_run_without_reanalysis(
    qapp,
    tmp_path,
) -> None:
    initial = _configuration(0.65)
    built_in = M6Preset(
        name="TTMAPP M6",
        configuration=initial,
        created_at=_NOW,
        updated_at=_NOW,
        built_in=True,
    )
    library = M6PresetLibrary(
        tmp_path / "m6-presets.json",
        built_in_presets=(built_in,),
        clock=lambda: _NOW,
    )
    sensitive = library.save(
        library.new("Sensitive template", _configuration(0.72))
    )
    controller = DomainAnalysisWorkspaceController(
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=initial.backend_id,
            m6_configuration=initial,
        ),
        physical_frame_ids=("frame-0",),
    )
    dialog = DomainAnalysisDialog(
        controller,
        m6_preset_name=built_in.name,
        classifier_preset_name="A/B/C",
        export_published=lambda _publication: None,
        m6_preset_library=library,
    )
    dialog.show()
    dialog.command_center.stage_button("presets").click()
    sheet = dialog.m6_preset_sheet

    sheet.preset_combo.setCurrentIndex(
        sheet.preset_combo.findData(sensitive.name)
    )
    sheet.new_button.click()
    sheet.name_edit.setText("Operator M6")
    sheet.save_button.click()

    assert library.snapshot.active_preset.name == "TTMAPP M6"
    assert sheet.preset_combo.currentText() == "Operator M6"
    assert controller.snapshot.draft.m6_configuration == initial

    sheet.set_active_button.click()

    assert library.snapshot.active_preset.name == "Operator M6"
    assert controller.snapshot.draft.m6_configuration == sensitive.configuration
    assert controller.snapshot.published is None
    assert dialog.m6_preset_edit.text() == "Operator M6"
    dialog.close()
    dialog.deleteLater()
    qapp.processEvents()


def test_dirty_preset_switch_uses_save_discard_cancel_decision(qapp, tmp_path) -> None:
    built_in = M6Preset(
        name="TTMAPP M6",
        configuration=_configuration(0.65),
        created_at=_NOW,
        updated_at=_NOW,
        built_in=True,
    )
    library = M6PresetLibrary(
        tmp_path / "m6-presets.json",
        built_in_presets=(built_in,),
        clock=lambda: _NOW,
    )
    library.save(library.new("Editable", _configuration(0.7)))
    decisions: list[str] = []

    def decide() -> str:
        decisions.append("prompted")
        return "cancel" if len(decisions) == 1 else "discard"

    sheet = M6PresetSheet(library, dirty_decision=decide)
    sheet.preset_combo.setCurrentIndex(sheet.preset_combo.findData("Editable"))
    sheet.description_edit.setText("Unsaved")

    sheet.preset_combo.setCurrentIndex(sheet.preset_combo.findData("TTMAPP M6"))
    assert sheet.preset_combo.currentData() == "Editable"
    assert sheet.description_edit.text() == "Unsaved"

    sheet.preset_combo.setCurrentIndex(sheet.preset_combo.findData("TTMAPP M6"))
    assert sheet.preset_combo.currentData() == "TTMAPP M6"
    assert decisions == ["prompted", "prompted"]
    sheet.deleteLater()
    qapp.processEvents()


def test_dirty_builtin_save_names_a_copy_before_switching(qapp, tmp_path) -> None:
    built_in = M6Preset(
        name="TTMAPP M6",
        configuration=_configuration(0.65),
        created_at=_NOW,
        updated_at=_NOW,
        built_in=True,
    )
    library = M6PresetLibrary(
        tmp_path / "m6-presets.json",
        built_in_presets=(built_in,),
        clock=lambda: _NOW,
    )
    library.save(library.new("Second", _configuration(0.7)))
    sheet = M6PresetSheet(
        library,
        dirty_decision=lambda: "save",
        save_as_name=lambda _proposed: "Built-in copy",
    )
    sheet.description_edit.setText("Edited built-in")

    sheet.preset_combo.setCurrentIndex(sheet.preset_combo.findData("Second"))

    assert sheet.preset_combo.currentData() == "Second"
    assert library.preset("Built-in copy").description == "Edited built-in"
    assert library.snapshot.active_preset.name == "TTMAPP M6"
    sheet.deleteLater()
    qapp.processEvents()


def test_sheet_edits_full_settings_and_resolves_import_conflict(qapp, tmp_path) -> None:
    built_in = M6Preset(
        name="TTMAPP M6",
        configuration=_configuration(0.65),
        created_at=_NOW,
        updated_at=_NOW,
        built_in=True,
    )
    library = M6PresetLibrary(
        tmp_path / "m6-presets.json",
        built_in_presets=(built_in,),
        clock=lambda: _NOW,
    )
    existing = library.save(library.new("Imported", _configuration(0.7)))
    imported = replace(existing, configuration=_configuration(0.77))
    conflicts: list[str] = []

    def conflict(_name: str) -> tuple[str, str | None]:
        conflicts.append(_name)
        return "rename", "Imported 2"

    sheet = M6PresetSheet(library, import_conflict_decision=conflict)
    q_seed = sheet.settings_editor.control("q_seed")
    q_seed.setValue(0.68)
    assert sheet.dirty_label.text() == "Unsaved changes"
    assert sheet.diff_table.rowCount() >= 1

    sheet.name_edit.setText("Local copy")
    sheet.save_as_button.click()
    assert library.preset("Local copy").configuration.settings.q_seed == 0.68

    result = sheet.import_payload(encode_m6_preset_file(imported))
    assert result is not None
    assert result.action == "renamed"
    assert conflicts == ["Imported"]
    assert library.preset("Imported 2").configuration.settings.q_seed == 0.77
    sheet.deleteLater()
    qapp.processEvents()


def test_cancelled_import_conflict_preserves_dirty_working_copy(qapp, tmp_path) -> None:
    built_in = M6Preset(
        name="TTMAPP M6",
        configuration=_configuration(0.65),
        created_at=_NOW,
        updated_at=_NOW,
        built_in=True,
    )
    library = M6PresetLibrary(
        tmp_path / "m6-presets.json",
        built_in_presets=(built_in,),
        clock=lambda: _NOW,
    )
    existing = library.save(library.new("Imported", _configuration(0.7)))
    dirty_prompts: list[str] = []
    sheet = M6PresetSheet(
        library,
        dirty_decision=lambda: dirty_prompts.append("asked") or "discard",
        import_conflict_decision=lambda _name: ("cancel", None),
    )
    sheet.description_edit.setText("Unsaved")

    result = sheet.import_payload(encode_m6_preset_file(existing))

    assert result is not None and result.action == "cancelled"
    assert dirty_prompts == []
    assert sheet.description_edit.text() == "Unsaved"
    assert sheet.dirty_label.text() == "Unsaved changes"
    sheet.deleteLater()
    qapp.processEvents()


def test_legacy_import_is_visibly_an_unsaved_working_copy(qapp, tmp_path) -> None:
    built_in = M6Preset(
        name="TTMAPP M6",
        configuration=_configuration(0.65),
        created_at=_NOW,
        updated_at=_NOW,
        built_in=True,
    )
    library = M6PresetLibrary(
        tmp_path / "m6-presets.json",
        built_in_presets=(built_in,),
        clock=lambda: _NOW,
    )
    payload = encode_m6_preset_file(library.new("Legacy", _configuration(0.7)))
    payload["schema_version"] = "m6-preset-file-v0"
    sheet = M6PresetSheet(library)

    result = sheet.import_payload(payload)

    assert result is not None and result.action == "working_copy"
    assert sheet.preset_combo.currentData() is None
    assert sheet.preset_combo.currentText() == "Legacy [working copy]"
    assert sheet.dirty_label.text() == "Unsaved changes"
    sheet.deleteLater()
    qapp.processEvents()


def test_invalid_editor_value_cannot_save_a_stale_configuration(qapp, tmp_path) -> None:
    built_in = M6Preset(
        name="TTMAPP M6",
        configuration=_configuration(0.65),
        created_at=_NOW,
        updated_at=_NOW,
        built_in=True,
    )
    library = M6PresetLibrary(
        tmp_path / "m6-presets.json",
        built_in_presets=(built_in,),
        clock=lambda: _NOW,
    )
    sheet = M6PresetSheet(library)
    sheet.new_button.click()
    sheet.name_edit.setText("Invalid")
    q_seed = sheet.settings_editor.control("q_seed")
    assert isinstance(q_seed, QDoubleSpinBox)
    q_seed.setValue(-1.0)

    sheet._save_as()

    assert sheet.dirty_label.text() == "Invalid working copy"
    assert all(preset.name != "Invalid" for preset in library.snapshot.presets)
    sheet.deleteLater()
    qapp.processEvents()


def test_description_edit_preserves_untouched_high_precision_setting(
    qapp,
    tmp_path,
) -> None:
    built_in = M6Preset(
        name="TTMAPP M6",
        configuration=_configuration(0.65),
        created_at=_NOW,
        updated_at=_NOW,
        built_in=True,
    )
    library = M6PresetLibrary(
        tmp_path / "m6-presets.json",
        built_in_presets=(built_in,),
        clock=lambda: _NOW,
    )
    exact_q_seed = 0.650000000000123
    library.save(library.new("Precise", _configuration(exact_q_seed)))
    sheet = M6PresetSheet(library)
    sheet.preset_combo.setCurrentIndex(sheet.preset_combo.findData("Precise"))
    sheet.description_edit.setText("Metadata only")

    sheet.save_button.click()

    assert library.preset("Precise").configuration.settings.q_seed == exact_q_seed
    sheet.deleteLater()
    qapp.processEvents()
