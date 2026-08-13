from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile

from .._m6_settings_fingerprint import m6_settings_fingerprint
from ..m6_settings import MolecularM6OrientationAnalysisSettings
from ._m6_preset_values import (
    GeometryParameter,
    GeometryPolicyMode,
    geometry_mode as _geometry_mode,
    geometry_parameters as _geometry_parameters,
    mapping as _mapping,
    native_evidence_kind as _native_evidence_kind,
    number as _number,
    optional_text as _optional_text,
    parameter as _parameter,
    parse_timestamp as _parse_timestamp,
    positive_float as _positive_float,
    sequence as _list,
    text as _text,
    timestamp as _timestamp,
    timestamp_text as _timestamp_text,
)
from .backend_contract import DomainBackendIdentity
from .fingerprints import canonical_sha256


M6_PRESET_SCHEMA_VERSION = "m6-preset-v1"
M6_PRESET_LIBRARY_SCHEMA_VERSION = "m6-preset-library-v1"


@dataclass(frozen=True)
class FirstShellGeometryPolicy:
    """Versioned first-shell rule with an explicit physical fallback."""

    mode: GeometryPolicyMode
    fixed_r_min_nm: float
    fixed_r_max_nm: float
    algorithm_version: str
    adaptive_parameters: tuple[tuple[str, GeometryParameter], ...] = ()
    policy_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if self.mode not in {"fixed", "adaptive"}:
            raise ValueError(f"Unsupported first-shell policy mode: {self.mode!r}.")
        minimum = _positive_float(self.fixed_r_min_nm, "fixed_r_min_nm")
        maximum = _positive_float(self.fixed_r_max_nm, "fixed_r_max_nm")
        if minimum >= maximum:
            raise ValueError("fixed_r_min_nm must be smaller than fixed_r_max_nm.")
        version = _text(self.algorithm_version, "algorithm_version")
        parameters = _geometry_parameters(self.adaptive_parameters)
        if self.mode == "fixed" and parameters:
            raise ValueError("A fixed first-shell policy cannot have adaptive parameters.")
        if self.mode == "adaptive" and not parameters:
            raise ValueError("An adaptive first-shell policy requires parameters.")
        object.__setattr__(self, "fixed_r_min_nm", minimum)
        object.__setattr__(self, "fixed_r_max_nm", maximum)
        object.__setattr__(self, "algorithm_version", version)
        object.__setattr__(self, "adaptive_parameters", parameters)
        object.__setattr__(
            self,
            "policy_fingerprint",
            canonical_sha256(self.to_payload(include_fingerprint=False)),
        )

    @classmethod
    def fixed(
        cls,
        *,
        r_min_nm: float,
        r_max_nm: float,
    ) -> FirstShellGeometryPolicy:
        return cls(
            mode="fixed",
            fixed_r_min_nm=r_min_nm,
            fixed_r_max_nm=r_max_nm,
            algorithm_version="fixed-physical-range-v1",
        )

    def to_payload(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "mode": self.mode,
            "fixed_fallback": {
                "r_min_nm": self.fixed_r_min_nm,
                "r_max_nm": self.fixed_r_max_nm,
            },
            "algorithm_version": self.algorithm_version,
            "adaptive_parameters": dict(self.adaptive_parameters),
        }
        if include_fingerprint:
            payload["policy_fingerprint"] = self.policy_fingerprint
        return payload

    @classmethod
    def from_payload(cls, payload: object) -> FirstShellGeometryPolicy:
        saved = _mapping(payload, "first_shell_geometry")
        fallback = _mapping(saved.get("fixed_fallback"), "fixed_fallback")
        parameters = _mapping(saved.get("adaptive_parameters"), "adaptive_parameters")
        value = cls(
            mode=_geometry_mode(saved.get("mode")),
            fixed_r_min_nm=_number(fallback.get("r_min_nm"), "r_min_nm"),
            fixed_r_max_nm=_number(fallback.get("r_max_nm"), "r_max_nm"),
            algorithm_version=_text(saved.get("algorithm_version"), "algorithm_version"),
            adaptive_parameters=tuple(
                (name, _parameter(value)) for name, value in parameters.items()
            ),
        )
        if saved.get("policy_fingerprint") != value.policy_fingerprint:
            raise ValueError("First-shell policy fingerprint does not match its payload.")
        return value


@dataclass(frozen=True)
class M6RunConfiguration:
    """Complete immutable computational input selected for one M6 run."""

    backend_identity: DomainBackendIdentity
    settings: MolecularM6OrientationAnalysisSettings
    first_shell_geometry: FirstShellGeometryPolicy
    schema_version: str = M6_PRESET_SCHEMA_VERSION
    configuration_fingerprint: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.backend_identity, DomainBackendIdentity):
            raise TypeError("backend_identity must be a DomainBackendIdentity.")
        if not isinstance(self.settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
        if not isinstance(self.first_shell_geometry, FirstShellGeometryPolicy):
            raise TypeError("first_shell_geometry must be FirstShellGeometryPolicy.")
        schema = _text(self.schema_version, "schema_version")
        if schema != M6_PRESET_SCHEMA_VERSION:
            raise ValueError(f"Unsupported M6 preset schema: {schema!r}.")
        if self.backend_identity.settings_fingerprint != m6_settings_fingerprint(
            self.settings
        ):
            raise ValueError("Backend settings fingerprint does not match settings.")
        if self.first_shell_geometry.mode == "fixed" and (
            self.settings.first_shell_r_min_nm
            != self.first_shell_geometry.fixed_r_min_nm
            or self.settings.first_shell_r_max_nm
            != self.first_shell_geometry.fixed_r_max_nm
        ):
            raise ValueError("Fixed first-shell policy must match the M6 settings range.")
        if self.first_shell_geometry.mode == "adaptive":
            raise ValueError(
                "Adaptive first-shell policies are not executable in this release."
            )
        object.__setattr__(self, "schema_version", schema)
        object.__setattr__(
            self,
            "configuration_fingerprint",
            canonical_sha256(self.to_payload(include_fingerprint=False)),
        )

    @property
    def backend_id(self) -> str:
        return self.backend_identity.backend_id

    def to_payload(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "backend_identity": asdict(self.backend_identity),
            "settings": self.settings.to_dict(),
            "first_shell_geometry": self.first_shell_geometry.to_payload(),
        }
        if include_fingerprint:
            payload["configuration_fingerprint"] = self.configuration_fingerprint
        return payload

    @classmethod
    def from_payload(cls, payload: object) -> M6RunConfiguration:
        saved = _mapping(payload, "m6_configuration")
        identity = _backend_identity(saved.get("backend_identity"))
        settings = MolecularM6OrientationAnalysisSettings.from_dict(
            _mapping(saved.get("settings"), "settings")
        )
        value = cls(
            backend_identity=identity,
            settings=settings,
            first_shell_geometry=FirstShellGeometryPolicy.from_payload(
                saved.get("first_shell_geometry")
            ),
            schema_version=_text(saved.get("schema_version"), "schema_version"),
        )
        if saved.get("configuration_fingerprint") != value.configuration_fingerprint:
            raise ValueError("M6 configuration fingerprint does not match its payload.")
        return value


@dataclass(frozen=True)
class M6Preset:
    name: str
    configuration: M6RunConfiguration
    created_at: datetime
    updated_at: datetime
    description: str = ""
    built_in: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _text(self.name, "name"))
        if not isinstance(self.configuration, M6RunConfiguration):
            raise TypeError("configuration must be M6RunConfiguration.")
        object.__setattr__(self, "description", _optional_text(self.description))
        created = _timestamp(self.created_at, "created_at")
        updated = _timestamp(self.updated_at, "updated_at")
        if updated < created:
            raise ValueError("updated_at cannot precede created_at.")
        if not isinstance(self.built_in, bool):
            raise TypeError("built_in must be a bool.")
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "updated_at", updated)

    def to_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "description": self.description,
            "configuration": self.configuration.to_payload(),
            "created_at": _timestamp_text(self.created_at),
            "updated_at": _timestamp_text(self.updated_at),
        }

    @classmethod
    def from_payload(cls, payload: object) -> M6Preset:
        saved = _mapping(payload, "preset")
        return cls(
            name=_text(saved.get("name"), "name"),
            description=_optional_text(saved.get("description", "")),
            configuration=M6RunConfiguration.from_payload(saved.get("configuration")),
            created_at=_parse_timestamp(saved.get("created_at"), "created_at"),
            updated_at=_parse_timestamp(saved.get("updated_at"), "updated_at"),
        )


@dataclass(frozen=True)
class M6PresetLibrarySnapshot:
    presets: tuple[M6Preset, ...]
    active_preset: M6Preset


class M6PresetLibrary:
    """Own saved presets and the one active default for future analyses."""

    def __init__(
        self,
        path: str | Path,
        *,
        built_in_presets: tuple[M6Preset, ...],
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self._path = Path(path)
        self._clock = clock
        built_ins = tuple(built_in_presets)
        if not built_ins or any(not value.built_in for value in built_ins):
            raise ValueError("built_in_presets must contain built-in presets.")
        self._built_ins = _preset_index(built_ins)
        users, active_name = self._load()
        overlap = set(self._built_ins).intersection(users)
        if overlap:
            raise ValueError(f"User presets conflict with built-ins: {sorted(overlap)!r}.")
        self._users = users
        self._active_name = active_name or built_ins[0].name
        if self._active_name not in self._all_presets():
            raise ValueError("Active M6 preset is not available.")
        self._available_backend_ids = frozenset(
            preset.configuration.backend_id for preset in built_ins
        )
        self._available_backend_identities = {
            preset.configuration.backend_id: _backend_compatibility_identity(
                preset.configuration.backend_identity
            )
            for preset in built_ins
        }
        self._ensure_compatible(self._all_presets()[self._active_name])

    @property
    def snapshot(self) -> M6PresetLibrarySnapshot:
        presets = self._all_presets()
        return M6PresetLibrarySnapshot(
            presets=tuple(presets[name] for name in sorted(presets)),
            active_preset=presets[self._active_name],
        )

    def new(
        self,
        name: str,
        configuration: M6RunConfiguration,
        *,
        description: str = "",
    ) -> M6Preset:
        normalized_name = _text(name, "name")
        if normalized_name in self._all_presets():
            raise ValueError(f"M6 preset already exists: {normalized_name!r}.")
        now = _timestamp(self._clock(), "clock result")
        return M6Preset(
            name=normalized_name,
            description=description,
            configuration=configuration,
            created_at=now,
            updated_at=now,
        )

    def save(self, preset: M6Preset) -> M6Preset:
        if not isinstance(preset, M6Preset):
            raise TypeError("preset must be an M6Preset.")
        if preset.built_in or preset.name in self._built_ins:
            raise ValueError("A built-in M6 preset cannot be overwritten.")
        if preset.name in self._users:
            raise ValueError(f"M6 preset already exists: {preset.name!r}.")
        updated_users = {**self._users, preset.name: preset}
        self._persist(updated_users, self._active_name)
        self._users = updated_users
        return preset

    def preset(self, name: str) -> M6Preset:
        normalized_name = _text(name, "name")
        try:
            return self._all_presets()[normalized_name]
        except KeyError as error:
            raise ValueError(f"Unknown M6 preset: {normalized_name!r}.") from error

    def overwrite(self, preset: M6Preset) -> M6Preset:
        if not isinstance(preset, M6Preset):
            raise TypeError("preset must be an M6Preset.")
        current = self.preset(preset.name)
        if current.built_in:
            raise ValueError("A built-in M6 preset cannot be overwritten.")
        updated = replace(
            preset,
            created_at=current.created_at,
            updated_at=_timestamp(self._clock(), "clock result"),
            built_in=False,
        )
        if updated.name == self._active_name:
            self._ensure_compatible(updated)
        updated_users = {**self._users, updated.name: updated}
        self._persist(updated_users, self._active_name)
        self._users = updated_users
        return updated

    def rename(self, name: str, new_name: str) -> M6Preset:
        current = self.preset(name)
        normalized_name = _text(new_name, "new_name")
        if current.built_in:
            raise ValueError("A built-in M6 preset cannot be renamed.")
        if normalized_name != current.name and normalized_name in self._all_presets():
            raise ValueError(f"M6 preset already exists: {normalized_name!r}.")
        updated = replace(
            current,
            name=normalized_name,
            updated_at=_timestamp(self._clock(), "clock result"),
        )
        users = dict(self._users)
        del users[current.name]
        users[updated.name] = updated
        active_name = updated.name if current.name == self._active_name else self._active_name
        self._persist(users, active_name)
        self._users = users
        self._active_name = active_name
        return updated

    def delete(self, name: str) -> None:
        preset = self.preset(name)
        if preset.built_in:
            raise ValueError("A built-in M6 preset cannot be deleted.")
        if preset.name == self._active_name:
            raise ValueError("The active M6 preset cannot be deleted.")
        users = dict(self._users)
        del users[preset.name]
        self._persist(users, self._active_name)
        self._users = users

    def set_active(self, name: str) -> M6Preset:
        normalized_name = _text(name, "name")
        presets = self._all_presets()
        if normalized_name not in presets:
            raise ValueError(f"Unknown M6 preset: {normalized_name!r}.")
        self._ensure_compatible(presets[normalized_name])
        self._persist(self._users, normalized_name)
        self._active_name = normalized_name
        return presets[normalized_name]

    def active_run_configuration(self) -> M6RunConfiguration:
        return self.snapshot.active_preset.configuration

    def _all_presets(self) -> dict[str, M6Preset]:
        return {**self._built_ins, **self._users}

    def _ensure_compatible(self, preset: M6Preset) -> None:
        backend_id = preset.configuration.backend_id
        if backend_id not in self._available_backend_ids:
            raise ValueError(
                f"M6 backend is unavailable: {backend_id!r}."
            )
        expected = self._available_backend_identities[backend_id]
        actual = _backend_compatibility_identity(
            preset.configuration.backend_identity
        )
        if actual != expected:
            raise ValueError(
                f"M6 backend identity is incompatible: {backend_id!r}."
            )

    def _load(self) -> tuple[dict[str, M6Preset], str | None]:
        if not self._path.exists():
            return {}, None
        saved = _mapping(
            json.loads(self._path.read_text(encoding="utf-8")),
            "M6 preset library",
        )
        if saved.get("schema_version") != M6_PRESET_LIBRARY_SCHEMA_VERSION:
            raise ValueError("Unsupported M6 preset library schema.")
        payloads = saved.get("user_presets")
        if not isinstance(payloads, list):
            raise TypeError("user_presets must be a list.")
        active_name = _text(saved.get("active_preset_name"), "active_preset_name")
        return _preset_index(tuple(M6Preset.from_payload(value) for value in payloads)), active_name

    def _persist(
        self,
        users: Mapping[str, M6Preset],
        active_name: str,
    ) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        _write_json_atomically(self._path, {
            "schema_version": M6_PRESET_LIBRARY_SCHEMA_VERSION,
            "active_preset_name": active_name,
            "user_presets": [
                users[name].to_payload() for name in sorted(users)
            ],
        })


def _preset_index(presets: tuple[M6Preset, ...]) -> dict[str, M6Preset]:
    if any(not isinstance(value, M6Preset) for value in presets):
        raise TypeError("Preset collections must contain M6Preset values.")
    result = {value.name: value for value in presets}
    if len(result) != len(presets):
        raise ValueError("M6 preset names must be unique.")
    return result


def _backend_identity(payload: object) -> DomainBackendIdentity:
    saved = _mapping(payload, "backend_identity")
    return DomainBackendIdentity(
        backend_id=_text(saved.get("backend_id"), "backend_id"),
        result_schema_version=_text(saved.get("result_schema_version"), "result_schema_version"),
        algorithm_version=_text(saved.get("algorithm_version"), "algorithm_version"),
        settings_fingerprint=_text(saved.get("settings_fingerprint"), "settings_fingerprint"),
        adapter_owner=_text(saved.get("adapter_owner"), "adapter_owner"),
        native_evidence_kind=_native_evidence_kind(saved.get("native_evidence_kind")),
        capabilities=tuple(_text(value, "capability") for value in _list(saved.get("capabilities"))),
    )


def _backend_compatibility_identity(
    identity: DomainBackendIdentity,
) -> tuple[object, ...]:
    return (
        identity.backend_id,
        identity.result_schema_version,
        identity.algorithm_version,
        identity.adapter_owner,
        identity.native_evidence_kind,
        identity.capabilities,
    )


def _write_json_atomically(path: Path, payload: Mapping[str, object]) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(temporary, path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
