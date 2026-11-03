from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import fields

from .._m6_settings_fingerprint import m6_settings_fingerprint
from ..m6_settings import MolecularM6OrientationAnalysisSettings
from .fingerprints import canonical_sha256
from .m6_preset_library import M6Preset


M6_PRESET_FILE_SCHEMA_VERSION = "m6-preset-file-v1"
M6_PRESET_FILE_LEGACY_SCHEMA_VERSION = "m6-preset-file-v0"


def encode_m6_preset_file(preset: M6Preset) -> dict[str, object]:
    """Return the portable, versioned representation of one preset."""

    if not isinstance(preset, M6Preset):
        raise TypeError("preset must be an M6Preset.")
    return {
        "schema_version": M6_PRESET_FILE_SCHEMA_VERSION,
        "preset": preset.to_payload(),
    }


def decode_m6_preset_file(payload: object) -> tuple[M6Preset, bool]:
    """Validate an import fully and report whether it needs migration."""

    if not isinstance(payload, Mapping):
        raise TypeError("M6 preset file must be a mapping.")
    schema = payload.get("schema_version")
    if schema not in {
        M6_PRESET_FILE_SCHEMA_VERSION,
        M6_PRESET_FILE_LEGACY_SCHEMA_VERSION,
    }:
        raise ValueError(f"Unsupported M6 preset file schema: {schema!r}.")
    is_legacy = schema == M6_PRESET_FILE_LEGACY_SCHEMA_VERSION
    preset_payload = payload.get("preset")
    if is_legacy:
        preset_payload = _migrate_legacy_payload(preset_payload)
    else:
        _validate_current_settings_are_complete(preset_payload)
    return M6Preset.from_payload(preset_payload), is_legacy


def _migrate_legacy_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, Mapping):
        raise TypeError("preset must be a mapping.")
    migrated = deepcopy(dict(payload))
    configuration = migrated.get("configuration")
    if not isinstance(configuration, Mapping):
        raise TypeError("m6_configuration must be a mapping.")
    configuration = deepcopy(dict(configuration))
    settings_payload = configuration.get("settings")
    if not isinstance(settings_payload, Mapping):
        raise TypeError("settings must be a mapping.")
    settings = MolecularM6OrientationAnalysisSettings.from_dict(settings_payload)
    configuration["settings"] = settings.to_dict()
    identity_payload = configuration.get("backend_identity")
    if not isinstance(identity_payload, Mapping):
        raise TypeError("backend_identity must be a mapping.")
    identity = deepcopy(dict(identity_payload))
    identity["settings_fingerprint"] = m6_settings_fingerprint(settings)
    configuration["backend_identity"] = identity
    configuration_without_fingerprint = {
        key: value
        for key, value in configuration.items()
        if key != "configuration_fingerprint"
    }
    configuration["configuration_fingerprint"] = canonical_sha256(
        configuration_without_fingerprint
    )
    migrated["configuration"] = configuration
    return migrated


def _validate_current_settings_are_complete(payload: object) -> None:
    if not isinstance(payload, Mapping):
        raise TypeError("preset must be a mapping.")
    configuration = payload.get("configuration")
    if not isinstance(configuration, Mapping):
        raise TypeError("m6_configuration must be a mapping.")
    settings = configuration.get("settings")
    if not isinstance(settings, Mapping):
        raise TypeError("settings must be a mapping.")
    expected = {field.name for field in fields(MolecularM6OrientationAnalysisSettings)}
    missing = sorted(expected - set(settings))
    if missing:
        raise ValueError(f"Missing M6 setting fields: {', '.join(missing)}")


__all__ = [
    "M6_PRESET_FILE_LEGACY_SCHEMA_VERSION",
    "M6_PRESET_FILE_SCHEMA_VERSION",
    "decode_m6_preset_file",
    "encode_m6_preset_file",
]
