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
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
)
from moltrack.ui.dialogs.domain_analysis_dialog import DomainAnalysisDialog


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
