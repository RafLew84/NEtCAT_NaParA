from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone

import pytest
import moltrack.analysis.domain_analysis.m6_preset_library as preset_library_module

from moltrack.analysis import TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint
from moltrack.analysis.domain_analysis import (
    M6_PRESET_FILE_LEGACY_SCHEMA_VERSION,
    M6_PRESET_FILE_SCHEMA_VERSION,
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    DomainBackendIdentity,
    FirstShellGeometryPolicy,
    M6Preset,
    M6PresetLibrary,
    M6PresetWorkspace,
    M6RunConfiguration,
    UnsavedM6PresetChanges,
    encode_m6_preset_file,
)


_NOW = datetime(2026, 8, 13, 8, 0, tzinfo=timezone.utc)


def _configuration(
    *,
    q_seed: float = 0.65,
    backend_id: str = M6_ORIENTATION_COMPONENTS_BACKEND_ID,
) -> M6RunConfiguration:
    settings = replace(TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET, q_seed=q_seed)
    return M6RunConfiguration(
        backend_identity=DomainBackendIdentity(
            backend_id=backend_id,
            result_schema_version="domain-backend-result-v1",
            algorithm_version="moltrack-m6-orientation-v1",
            settings_fingerprint=m6_settings_fingerprint(settings),
            adapter_owner="preset-workspace-test",
            native_evidence_kind=(
                "m6_orientation_evidence_v1"
                if backend_id == M6_ORIENTATION_COMPONENTS_BACKEND_ID
                else "m3_m6_lattice_evidence_v1"
            ),
            capabilities=("common_partition",),
        ),
        settings=settings,
        first_shell_geometry=FirstShellGeometryPolicy.fixed(
            r_min_nm=settings.first_shell_r_min_nm,
            r_max_nm=settings.first_shell_r_max_nm,
        ),
    )


def _built_in() -> M6Preset:
    return M6Preset(
        name="TTMAPP M6",
        description="Shipped default",
        configuration=_configuration(),
        created_at=_NOW,
        updated_at=_NOW,
        built_in=True,
    )


def _workspace(tmp_path) -> tuple[M6PresetLibrary, M6PresetWorkspace]:
    library = M6PresetLibrary(
        tmp_path / "m6-presets.json",
        built_in_presets=(_built_in(),),
        clock=lambda: _NOW,
    )
    return library, M6PresetWorkspace(library)


def test_crud_keeps_one_compatible_active_preset_and_frozen_runs(tmp_path) -> None:
    library, workspace = _workspace(tmp_path)
    copied = workspace.duplicate("TTMAPP M6", "Operator copy")
    library.set_active(copied.name)
    workspace.rename(copied.name, "Operator renamed")
    assert library.snapshot.active_preset.name == "Operator renamed"
    workspace.checkout("Operator renamed")
    workspace.update(
        name="Operator renamed",
        description="Tuned",
        configuration=_configuration(q_seed=0.72),
    )
    assert {difference.path for difference in workspace.differences} == {
        "configuration.settings.q_seed",
        "description",
    }

    revised = workspace.save()
    library.set_active(revised.name)
    frozen_for_existing_run = library.active_run_configuration()
    workspace.update(
        name=revised.name,
        description="Tuned again",
        configuration=_configuration(q_seed=0.74),
    )
    workspace.save()

    assert frozen_for_existing_run.settings.q_seed == 0.72
    assert library.active_run_configuration().settings.q_seed == 0.74
    assert library.snapshot.active_preset.name == "Operator renamed"

    with pytest.raises(ValueError, match="active M6 preset"):
        workspace.delete("Operator renamed")
    library.set_active("TTMAPP M6")
    workspace.delete("Operator renamed")
    assert tuple(preset.name for preset in library.snapshot.presets) == ("TTMAPP M6",)


def test_builtin_is_copyable_but_cannot_be_overwritten_or_deleted(tmp_path) -> None:
    library, workspace = _workspace(tmp_path)
    workspace.checkout("TTMAPP M6")
    workspace.update(
        name="TTMAPP M6",
        description="Attempted edit",
        configuration=_configuration(q_seed=0.7),
    )

    with pytest.raises(ValueError, match="Save As"):
        workspace.save()
    with pytest.raises(ValueError, match="built-in"):
        workspace.delete("TTMAPP M6")
    with pytest.raises(ValueError, match="built-in"):
        workspace.rename("TTMAPP M6", "Renamed default")

    copied = workspace.save_as("Copied default")
    assert copied.configuration.settings.q_seed == 0.7
    assert library.snapshot.active_preset.name == "TTMAPP M6"


def test_dirty_working_copy_requires_an_explicit_switch_decision(tmp_path) -> None:
    _library, workspace = _workspace(tmp_path)
    workspace.duplicate("TTMAPP M6", "Second")
    workspace.update(
        name="Draft name",
        description="",
        configuration=_configuration(q_seed=0.71),
    )

    with pytest.raises(UnsavedM6PresetChanges):
        workspace.checkout("Second")
    assert workspace.resolve_and_checkout("Second", decision="cancel") is False
    assert workspace.working_copy.name == "Draft name"
    assert workspace.resolve_and_checkout("Second", decision="discard") is True
    assert workspace.working_copy.name == "Second"

    workspace.update(
        name="Second",
        description="Saved before switch",
        configuration=_configuration(q_seed=0.73),
    )
    assert workspace.resolve_and_checkout("TTMAPP M6", decision="save") is True
    assert workspace.working_copy.name == "TTMAPP M6"
    workspace.checkout("Second")
    assert workspace.working_copy.configuration.settings.q_seed == 0.73


def test_dirty_builtin_switch_requires_a_save_as_name(tmp_path) -> None:
    library, workspace = _workspace(tmp_path)
    workspace.duplicate("TTMAPP M6", "Second")
    workspace.update(
        name="TTMAPP M6",
        description="Edited built-in",
        configuration=_configuration(q_seed=0.71),
    )

    with pytest.raises(ValueError, match="new preset name"):
        workspace.resolve_and_checkout("Second", decision="save")

    assert workspace.resolve_and_checkout(
        "Second",
        decision="save",
        save_as_name="Built-in copy",
    )
    assert library.preset("Built-in copy").configuration.settings.q_seed == 0.71
    assert workspace.working_copy.name == "Second"


def test_import_conflict_requires_rename_overwrite_or_cancel(tmp_path) -> None:
    library, workspace = _workspace(tmp_path)
    existing = workspace.duplicate("TTMAPP M6", "Imported")
    imported = replace(
        existing,
        configuration=_configuration(q_seed=0.77),
        description="From another workstation",
    )
    payload = encode_m6_preset_file(imported)

    result = workspace.import_payload(payload, conflict="cancel")
    assert result.action == "cancelled"
    assert library.preset("Imported").configuration.settings.q_seed == 0.65

    result = workspace.import_payload(
        payload,
        conflict="rename",
        rename_to="Imported 2",
    )
    assert result.action == "renamed"
    assert result.preset is not None
    assert result.preset.name == "Imported 2"

    result = workspace.import_payload(payload, conflict="overwrite")
    assert result.action == "overwritten"
    assert library.preset("Imported").configuration.settings.q_seed == 0.77
    assert library.snapshot.active_preset.name == "TTMAPP M6"


def test_legacy_import_opens_unsaved_working_copy_requiring_save_as(tmp_path) -> None:
    library, workspace = _workspace(tmp_path)
    imported = library.new("Legacy", _configuration(q_seed=0.7))
    payload = encode_m6_preset_file(imported)
    payload["schema_version"] = M6_PRESET_FILE_LEGACY_SCHEMA_VERSION
    legacy_settings = payload["preset"]["configuration"]["settings"]
    legacy_settings.pop("local_symmetry_trifold_minimum_model_score")

    result = workspace.import_payload(payload)

    assert result.action == "working_copy"
    assert result.preset is None
    assert workspace.dirty is True
    assert workspace.working_copy.requires_save_as is True
    assert all(preset.name != "Legacy" for preset in library.snapshot.presets)
    with pytest.raises(ValueError, match="Save As"):
        workspace.save()
    workspace.save_as("Migrated legacy")
    assert library.preset("Migrated legacy").configuration.settings.q_seed == 0.7


@pytest.mark.parametrize(
    ("mutate", "message"),
    (
        (
            lambda payload: payload.__setitem__(
                "schema_version", "m6-preset-file-v999"
            ),
            "Unsupported M6 preset file schema",
        ),
        (
            lambda payload: payload["preset"]["configuration"][
                "settings"
            ].pop("q_seed"),
            "Missing M6 setting fields",
        ),
    ),
)
def test_invalid_import_fails_without_mutating_library_or_working_copy(
    tmp_path,
    mutate,
    message: str,
) -> None:
    library, workspace = _workspace(tmp_path)
    path = tmp_path / "m6-presets.json"
    library.save(library.new("Saved", _configuration(q_seed=0.69)))
    workspace.checkout("Saved")
    before_file = path.read_bytes()
    before_copy = workspace.working_copy
    payload = deepcopy(encode_m6_preset_file(library.preset("Saved")))
    mutate(payload)

    with pytest.raises((TypeError, ValueError), match=message):
        workspace.import_payload(payload, conflict="overwrite")

    assert path.read_bytes() == before_file
    assert workspace.working_copy == before_copy


def test_current_import_rejects_a_missing_legacy_migration_field(tmp_path) -> None:
    library, workspace = _workspace(tmp_path)
    payload = encode_m6_preset_file(
        library.new("Incomplete current", _configuration())
    )
    payload["preset"]["configuration"]["settings"].pop(
        "local_symmetry_trifold_minimum_model_score"
    )

    with pytest.raises(ValueError, match="Missing M6 setting fields"):
        workspace.import_payload(payload)

    assert tuple(preset.name for preset in library.snapshot.presets) == ("TTMAPP M6",)


def test_unavailable_imported_backend_blocks_activation_not_storage(tmp_path) -> None:
    library, workspace = _workspace(tmp_path)
    imported = library.new(
        "External backend",
        _configuration(backend_id=M3_M6_LATTICE_NETWORK_BACKEND_ID),
    )
    result = workspace.import_payload(encode_m6_preset_file(imported))

    assert result.action == "imported"
    assert (
        library.preset("External backend").configuration.backend_id
        == M3_M6_LATTICE_NETWORK_BACKEND_ID
    )
    with pytest.raises(ValueError, match="backend is unavailable"):
        library.set_active("External backend")
    assert library.snapshot.active_preset.name == "TTMAPP M6"
    assert M6_PRESET_FILE_SCHEMA_VERSION == "m6-preset-file-v1"


def test_known_backend_id_with_incompatible_identity_blocks_activation(tmp_path) -> None:
    library, workspace = _workspace(tmp_path)
    configuration = _configuration()
    incompatible = M6RunConfiguration(
        backend_identity=replace(
            configuration.backend_identity,
            algorithm_version="unavailable-algorithm-v999",
        ),
        settings=configuration.settings,
        first_shell_geometry=configuration.first_shell_geometry,
    )
    workspace.import_payload(encode_m6_preset_file(
        library.new("Incompatible identity", incompatible)
    ))

    with pytest.raises(ValueError, match="identity is incompatible"):
        library.set_active("Incompatible identity")

    assert library.snapshot.active_preset.name == "TTMAPP M6"


def test_failed_atomic_replace_leaves_library_state_unchanged(
    tmp_path,
    monkeypatch,
) -> None:
    library, workspace = _workspace(tmp_path)
    saved = workspace.duplicate("TTMAPP M6", "Saved")
    before = library.snapshot

    def fail_replace(_source, _destination) -> None:
        raise OSError("disk unavailable")

    monkeypatch.setattr(preset_library_module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="disk unavailable"):
        library.rename(saved.name, "Not committed")

    assert library.snapshot == before
    assert library.preset("Saved") == saved
