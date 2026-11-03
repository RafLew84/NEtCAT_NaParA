from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from .m6_preset_file import decode_m6_preset_file
from .m6_preset_library import M6Preset, M6PresetLibrary, M6RunConfiguration


M6PresetConflict = Literal["rename", "overwrite", "cancel"]
M6PresetSwitchDecision = Literal["save", "discard", "cancel"]
M6PresetImportAction = Literal[
    "imported", "renamed", "overwritten", "cancelled", "working_copy"
]


class UnsavedM6PresetChanges(RuntimeError):
    """Raised when navigation would discard an edited working copy."""


@dataclass(frozen=True)
class M6PresetWorkingCopy:
    source_name: str | None
    name: str
    description: str
    configuration: M6RunConfiguration
    requires_save_as: bool


@dataclass(frozen=True)
class M6PresetDifference:
    path: str
    saved_value: object
    working_value: object


@dataclass(frozen=True)
class M6PresetImportResult:
    action: M6PresetImportAction
    preset: M6Preset | None


class M6PresetWorkspace:
    """Own one explicit working copy over a persistent preset library."""

    def __init__(self, library: M6PresetLibrary) -> None:
        if not isinstance(library, M6PresetLibrary):
            raise TypeError("library must be an M6PresetLibrary.")
        self._library = library
        self._baseline: M6Preset | None = None
        active = library.snapshot.active_preset
        self._working_copy = _copy_from_preset(active)
        self._baseline = active

    @property
    def working_copy(self) -> M6PresetWorkingCopy:
        return self._working_copy

    @property
    def dirty(self) -> bool:
        baseline = self._baseline
        if baseline is None:
            return True
        return _editable_payload(self._working_copy) != _preset_payload(baseline)

    @property
    def differences(self) -> tuple[M6PresetDifference, ...]:
        baseline = self._baseline
        saved = {} if baseline is None else _preset_payload(baseline)
        working = _editable_payload(self._working_copy)
        return tuple(_payload_differences(saved, working))

    def update(
        self,
        *,
        name: str,
        description: str,
        configuration: M6RunConfiguration,
    ) -> None:
        if not isinstance(configuration, M6RunConfiguration):
            raise TypeError("configuration must be an M6RunConfiguration.")
        self._working_copy = M6PresetWorkingCopy(
            source_name=self._working_copy.source_name,
            name=str(name),
            description=str(description),
            configuration=configuration,
            requires_save_as=self._working_copy.requires_save_as,
        )

    def checkout(self, name: str) -> M6PresetWorkingCopy:
        if self.dirty:
            raise UnsavedM6PresetChanges(
                "Save, discard, or cancel the dirty M6 preset working copy."
            )
        return self._load(self._library.preset(name))

    def new_from_current(self) -> M6PresetWorkingCopy:
        if self.dirty:
            raise UnsavedM6PresetChanges(
                "Resolve the dirty working copy before creating a new preset."
            )
        current = self._working_copy
        self._baseline = None
        self._working_copy = M6PresetWorkingCopy(
            source_name=None,
            name="",
            description="",
            configuration=current.configuration,
            requires_save_as=True,
        )
        return self._working_copy

    def resolve_and_checkout(
        self,
        name: str,
        *,
        decision: M6PresetSwitchDecision,
        save_as_name: str | None = None,
    ) -> bool:
        if decision == "cancel":
            return False
        if decision == "save":
            if self._working_copy.requires_save_as:
                if save_as_name is None:
                    raise ValueError("Save As requires a new preset name.")
                self.save_as(save_as_name)
            else:
                self.save()
        elif decision != "discard":
            raise ValueError(f"Unsupported dirty working-copy decision: {decision!r}.")
        self._load(self._library.preset(name))
        return True

    def save(self) -> M6Preset:
        copy = self._working_copy
        if copy.requires_save_as or copy.source_name is None:
            raise ValueError("This working copy requires Save As.")
        if copy.name != copy.source_name:
            raise ValueError("Use Rename before saving a changed preset name.")
        saved = self._library.overwrite(_preset_from_copy(copy, self._baseline))
        self._load(saved)
        return saved

    def save_as(self, name: str) -> M6Preset:
        copy = self._working_copy
        saved = self._library.save(self._library.new(
            name,
            copy.configuration,
            description=copy.description,
        ))
        self._load(saved)
        return saved

    def duplicate(self, name: str, new_name: str) -> M6Preset:
        source = self._library.preset(name)
        return self._library.save(self._library.new(
            new_name,
            source.configuration,
            description=source.description,
        ))

    def rename(self, name: str, new_name: str) -> M6Preset:
        source = self._library.preset(name)
        if source.built_in:
            return self._library.rename(name, new_name)
        if self.dirty:
            raise UnsavedM6PresetChanges("Resolve the dirty working copy before Rename.")
        saved = self._library.rename(name, new_name)
        if self._working_copy.source_name == name:
            self._load(saved)
        return saved

    def delete(self, name: str) -> None:
        source = self._library.preset(name)
        if source.built_in:
            self._library.delete(name)
            return
        if self.dirty:
            raise UnsavedM6PresetChanges("Resolve the dirty working copy before Delete.")
        was_selected = self._working_copy.source_name == name
        self._library.delete(name)
        if was_selected:
            self._load(self._library.snapshot.active_preset)

    def import_payload(
        self,
        payload: object,
        *,
        conflict: M6PresetConflict = "cancel",
        rename_to: str | None = None,
    ) -> M6PresetImportResult:
        imported, is_legacy = decode_m6_preset_file(payload)
        if is_legacy:
            self._ensure_clean_for_import()
            self._baseline = None
            self._working_copy = M6PresetWorkingCopy(
                source_name=None,
                name=imported.name,
                description=imported.description,
                configuration=imported.configuration,
                requires_save_as=True,
            )
            return M6PresetImportResult("working_copy", None)

        existing = _optional_preset(self._library, imported.name)
        if existing is not None and conflict == "cancel":
            return M6PresetImportResult("cancelled", None)
        self._ensure_clean_for_import()
        if existing is None:
            saved = self._library.save(imported)
            action: M6PresetImportAction = "imported"
        elif conflict == "overwrite":
            saved = self._library.overwrite(imported)
            action = "overwritten"
        elif conflict == "rename":
            if rename_to is None:
                raise ValueError("rename_to is required for an import rename.")
            saved = self._library.save(self._library.new(
                rename_to,
                imported.configuration,
                description=imported.description,
            ))
            action = "renamed"
        else:
            raise ValueError(f"Unsupported import conflict decision: {conflict!r}.")
        self._load(saved)
        return M6PresetImportResult(action, saved)

    def _ensure_clean_for_import(self) -> None:
        if self.dirty:
            raise UnsavedM6PresetChanges(
                "Resolve the dirty working copy before importing a preset."
            )

    def _load(self, preset: M6Preset) -> M6PresetWorkingCopy:
        self._baseline = preset
        self._working_copy = _copy_from_preset(preset)
        return self._working_copy


def _copy_from_preset(preset: M6Preset) -> M6PresetWorkingCopy:
    return M6PresetWorkingCopy(
        source_name=preset.name,
        name=preset.name,
        description=preset.description,
        configuration=preset.configuration,
        requires_save_as=preset.built_in,
    )


def _preset_from_copy(
    copy: M6PresetWorkingCopy,
    baseline: M6Preset | None,
) -> M6Preset:
    if baseline is None:
        raise ValueError("This working copy requires Save As.")
    return M6Preset(
        name=copy.name,
        description=copy.description,
        configuration=copy.configuration,
        created_at=baseline.created_at,
        updated_at=baseline.updated_at,
    )


def _optional_preset(library: M6PresetLibrary, name: str) -> M6Preset | None:
    try:
        return library.preset(name)
    except ValueError:
        return None


def _preset_payload(preset: M6Preset) -> dict[str, object]:
    return {
        "name": preset.name,
        "description": preset.description,
        "configuration": _configuration_payload(preset.configuration),
    }


def _editable_payload(copy: M6PresetWorkingCopy) -> dict[str, object]:
    return {
        "name": copy.name,
        "description": copy.description,
        "configuration": _configuration_payload(copy.configuration),
    }


def _configuration_payload(configuration: M6RunConfiguration) -> dict[str, object]:
    payload = configuration.to_payload(include_fingerprint=False)
    identity_payload = payload["backend_identity"]
    geometry_payload = payload["first_shell_geometry"]
    if not isinstance(identity_payload, Mapping) or not isinstance(
        geometry_payload, Mapping
    ):
        raise TypeError("M6 configuration payload contains invalid nested values.")
    identity = dict(identity_payload)
    identity.pop("settings_fingerprint", None)
    geometry = dict(geometry_payload)
    geometry.pop("policy_fingerprint", None)
    payload["backend_identity"] = identity
    payload["first_shell_geometry"] = geometry
    return payload


def _payload_differences(
    saved: Mapping[str, object],
    working: Mapping[str, object],
    prefix: str = "",
) -> list[M6PresetDifference]:
    differences: list[M6PresetDifference] = []
    for key in sorted(set(saved) | set(working)):
        path = f"{prefix}.{key}" if prefix else key
        saved_value = saved.get(key)
        working_value = working.get(key)
        if isinstance(saved_value, Mapping) and isinstance(working_value, Mapping):
            differences.extend(_payload_differences(saved_value, working_value, path))
        elif saved_value != working_value:
            differences.append(M6PresetDifference(path, saved_value, working_value))
    return differences


__all__ = [
    "M6PresetDifference",
    "M6PresetImportResult",
    "M6PresetWorkingCopy",
    "M6PresetWorkspace",
    "UnsavedM6PresetChanges",
]
