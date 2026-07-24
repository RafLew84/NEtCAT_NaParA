"""Versioned, dependency-checked persistence for molecular-order types."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Mapping

from .frame_ranges import MolecularFrameRangeAnalysisScope
from .molecular_order_hierarchy import (
    MolecularOrderHierarchy,
    molecular_order_hierarchy_fingerprint,
)
from .molecular_order_type_models import (
    MOLECULAR_ORDER_TYPE_CLASSIFICATION_ALGORITHM_VERSION,
    MolecularOrderGeometryType,
    MolecularOrderLayerAssignment,
    MolecularOrderOrientationType,
    MolecularOrderStackingType,
    MolecularOrderTypeAssignment,
    MolecularOrderTypeClassificationResult,
    MolecularOrderTypeClassificationSettings,
    MolecularOrderTypeObservation,
    molecular_order_type_classification_fingerprint,
)


MOLECULAR_ORDER_TYPE_CONFIGURATION_SCHEMA_VERSION = 1
MOLECULAR_ORDER_TYPE_CACHE_RECORD_SCHEMA_VERSION = 1


class MolecularOrderTypeCacheDecodeError(ValueError):
    """A cached classification is unsupported or internally inconsistent."""


@dataclass(frozen=True)
class MolecularOrderTypeCacheRecord:
    """One classification guarded by its full hierarchy fingerprint."""

    classification: MolecularOrderTypeClassificationResult
    classification_fingerprint: str
    algorithm_version: str = (
        MOLECULAR_ORDER_TYPE_CLASSIFICATION_ALGORITHM_VERSION
    )
    schema_version: int = MOLECULAR_ORDER_TYPE_CACHE_RECORD_SCHEMA_VERSION
    uses_tracking: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.algorithm_version != (
            MOLECULAR_ORDER_TYPE_CLASSIFICATION_ALGORITHM_VERSION
        ):
            raise ValueError(
                "Unsupported molecular-order type algorithm version."
            )
        if self.schema_version != (
            MOLECULAR_ORDER_TYPE_CACHE_RECORD_SCHEMA_VERSION
        ):
            raise ValueError(
                "Unsupported molecular-order type cache schema."
            )
        if not isinstance(
            self.classification,
            MolecularOrderTypeClassificationResult,
        ):
            raise TypeError(
                "classification must be a molecular-order type result."
            )
        expected = molecular_order_type_classification_fingerprint(
            self.classification
        )
        if self.classification_fingerprint != expected:
            raise ValueError(
                "classification_fingerprint must match classification."
            )
        if self.uses_tracking is not False:
            raise ValueError(
                "Molecular-order type cache must not use tracking."
            )
        object.__setattr__(self, "classification_fingerprint", expected)
        object.__setattr__(self, "uses_tracking", False)

    @classmethod
    def from_classification(
        cls,
        classification: MolecularOrderTypeClassificationResult,
    ) -> "MolecularOrderTypeCacheRecord":
        return cls(
            classification=classification,
            classification_fingerprint=(
                molecular_order_type_classification_fingerprint(
                    classification
                )
            ),
        )

    def matches_hierarchy(
        self,
        hierarchy: MolecularOrderHierarchy,
    ) -> bool:
        if not isinstance(hierarchy, MolecularOrderHierarchy):
            return False
        return (
            self.classification.hierarchy_fingerprint
            == molecular_order_hierarchy_fingerprint(hierarchy)
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "cache_record_schema_version": self.schema_version,
            "algorithm_version": self.algorithm_version,
            "classification_fingerprint": self.classification_fingerprint,
            "uses_tracking": False,
            "classification": _classification_to_payload(
                self.classification
            ),
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularOrderTypeCacheRecord":
        try:
            value = _exact_mapping(
                payload,
                required={
                    "cache_record_schema_version",
                    "algorithm_version",
                    "classification_fingerprint",
                    "uses_tracking",
                    "classification",
                },
                label="molecular-order type cache",
            )
            if value["uses_tracking"] is not False:
                raise ValueError(
                    "Molecular-order type cache must declare "
                    "uses_tracking=false."
                )
            return cls(
                schema_version=value["cache_record_schema_version"],
                algorithm_version=value["algorithm_version"],
                classification_fingerprint=value[
                    "classification_fingerprint"
                ],
                classification=_classification_from_payload(
                    value["classification"]
                ),
            )
        except MolecularOrderTypeCacheDecodeError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise MolecularOrderTypeCacheDecodeError(
                "Molecular-order type cache cannot be restored."
            ) from exc


@dataclass(frozen=True)
class MolecularOrderTypeSessionState:
    """Persisted settings with an independently optional result cache."""

    analysis_scope: MolecularFrameRangeAnalysisScope
    classification_settings: MolecularOrderTypeClassificationSettings
    cache_record: MolecularOrderTypeCacheRecord | None = None
    uses_tracking: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.analysis_scope,
            MolecularFrameRangeAnalysisScope,
        ):
            raise TypeError(
                "analysis_scope must be a frame range analysis scope."
            )
        if not isinstance(
            self.classification_settings,
            MolecularOrderTypeClassificationSettings,
        ):
            raise TypeError(
                "classification_settings must be molecular-order settings."
            )
        if self.cache_record is not None:
            if not isinstance(
                self.cache_record,
                MolecularOrderTypeCacheRecord,
            ):
                raise TypeError(
                    "cache_record must be a molecular-order cache or None."
                )
            classification = self.cache_record.classification
            if classification.analysis_scope != self.analysis_scope:
                raise ValueError(
                    "Configuration and cache scopes must match."
                )
            if classification.settings != self.classification_settings:
                raise ValueError(
                    "Configuration and cache settings must match."
                )
        if self.uses_tracking is not False:
            raise ValueError(
                "Molecular-order type analysis must not use tracking."
            )
        object.__setattr__(self, "uses_tracking", False)

    @classmethod
    def from_classification(
        cls,
        classification: MolecularOrderTypeClassificationResult,
    ) -> "MolecularOrderTypeSessionState":
        cache = MolecularOrderTypeCacheRecord.from_classification(
            classification
        )
        return cls(
            analysis_scope=classification.analysis_scope,
            classification_settings=classification.settings,
            cache_record=cache,
        )

    def restore_classification_for(
        self,
        hierarchy: MolecularOrderHierarchy,
    ) -> MolecularOrderTypeClassificationResult | None:
        cache = self.cache_record
        if cache is None or not cache.matches_hierarchy(hierarchy):
            return None
        return cache.classification

    def to_dict(self) -> dict[str, object]:
        return {
            "configuration_schema_version": (
                MOLECULAR_ORDER_TYPE_CONFIGURATION_SCHEMA_VERSION
            ),
            "analysis_scope": self.analysis_scope.to_dict(),
            "classification_settings": (
                self.classification_settings.to_dict()
            ),
            "uses_tracking": False,
            "reproducible_cache": (
                None
                if self.cache_record is None
                else self.cache_record.to_dict()
            ),
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularOrderTypeSessionState":
        value = _exact_mapping(
            payload,
            required={
                "configuration_schema_version",
                "analysis_scope",
                "classification_settings",
                "uses_tracking",
                "reproducible_cache",
            },
            label="molecular-order type state",
        )
        if value["configuration_schema_version"] != (
            MOLECULAR_ORDER_TYPE_CONFIGURATION_SCHEMA_VERSION
        ):
            raise ValueError(
                "Unsupported molecular-order type configuration schema."
            )
        if value["uses_tracking"] is not False:
            raise ValueError(
                "Molecular-order type state must declare uses_tracking=false."
            )
        scope = MolecularFrameRangeAnalysisScope.from_dict(
            _mapping(value["analysis_scope"], "analysis_scope")
        )
        settings = MolecularOrderTypeClassificationSettings.from_dict(
            _mapping(
                value["classification_settings"],
                "classification_settings",
            )
        )
        cache = None
        if value["reproducible_cache"] is not None:
            try:
                cache = MolecularOrderTypeCacheRecord.from_dict(
                    _mapping(
                        value["reproducible_cache"],
                        "reproducible_cache",
                    )
                )
                candidate = cls(
                    analysis_scope=scope,
                    classification_settings=settings,
                    cache_record=cache,
                )
            except (
                MolecularOrderTypeCacheDecodeError,
                TypeError,
                ValueError,
            ):
                cache = None
            else:
                return candidate
        return cls(
            analysis_scope=scope,
            classification_settings=settings,
            cache_record=cache,
        )


def _classification_to_payload(
    classification: MolecularOrderTypeClassificationResult,
) -> dict[str, object]:
    return {
        "schema_version": classification.schema_version,
        "analysis_scope": classification.analysis_scope.to_dict(),
        "settings": classification.settings.to_dict(),
        "settings_fingerprint": classification.settings_fingerprint,
        "hierarchy_fingerprint": classification.hierarchy_fingerprint,
        "input_fingerprint": classification.input_fingerprint,
        "observations": [
            asdict(value) for value in classification.observations
        ],
        "geometry_types": [
            asdict(value) for value in classification.geometry_types
        ],
        "orientation_types": [
            asdict(value) for value in classification.orientation_types
        ],
        "stacking_types": [
            asdict(value) for value in classification.stacking_types
        ],
        "assignments": [
            {
                "observation_key": list(value.observation_key),
                "geometry": asdict(value.geometry),
                "orientation": asdict(value.orientation),
                "stacking": asdict(value.stacking),
            }
            for value in classification.assignments
        ],
        "uses_tracking": False,
    }


def _classification_from_payload(
    payload: object,
) -> MolecularOrderTypeClassificationResult:
    value = _exact_mapping(
        payload,
        required={
            "schema_version",
            "analysis_scope",
            "settings",
            "settings_fingerprint",
            "hierarchy_fingerprint",
            "input_fingerprint",
            "observations",
            "geometry_types",
            "orientation_types",
            "stacking_types",
            "assignments",
            "uses_tracking",
        },
        label="molecular-order type classification",
    )
    if value["uses_tracking"] is not False:
        raise ValueError(
            "Molecular-order classification must declare "
            "uses_tracking=false."
        )
    return MolecularOrderTypeClassificationResult(
        schema_version=value["schema_version"],
        analysis_scope=MolecularFrameRangeAnalysisScope.from_dict(
            _mapping(value["analysis_scope"], "analysis_scope")
        ),
        settings=MolecularOrderTypeClassificationSettings.from_dict(
            _mapping(value["settings"], "settings")
        ),
        settings_fingerprint=value["settings_fingerprint"],
        hierarchy_fingerprint=value["hierarchy_fingerprint"],
        input_fingerprint=value["input_fingerprint"],
        observations=tuple(
            _observation_from_payload(item)
            for item in _sequence(value["observations"], "observations")
        ),
        geometry_types=tuple(
            MolecularOrderGeometryType(
                **_exact_mapping(
                    item,
                    required={
                        "type_id",
                        "label",
                        "dominant_symmetry",
                        "prototype_theta3_lattice_deg",
                        "prototype_theta6_lattice_deg",
                        "observation_count",
                    },
                    label="geometry type",
                )
            )
            for item in _sequence(value["geometry_types"], "geometry_types")
        ),
        orientation_types=tuple(
            _orientation_type_from_payload(item)
            for item in _sequence(
                value["orientation_types"],
                "orientation_types",
            )
        ),
        stacking_types=tuple(
            MolecularOrderStackingType(
                **_exact_mapping(
                    item,
                    required={
                        "type_id",
                        "label",
                        "pattern",
                        "mode",
                        "phase",
                        "observation_count",
                    },
                    label="stacking type",
                )
            )
            for item in _sequence(value["stacking_types"], "stacking_types")
        ),
        assignments=tuple(
            _assignment_from_payload(item)
            for item in _sequence(value["assignments"], "assignments")
        ),
    )


def _observation_from_payload(
    payload: object,
) -> MolecularOrderTypeObservation:
    value = _exact_mapping(
        payload,
        required={
            "range_name",
            "range_start_frame",
            "range_end_frame",
            "frame_index",
            "lattice_domain_id",
            "component_type",
            "dominant_symmetry",
            "theta3_lattice_deg",
            "theta6_lattice_deg",
            "molecular_orientation_prototypes_deg",
            "molecular_orientation_periodicity_deg",
            "stacking_pattern",
            "stacking_mode",
            "stacking_phase",
            "molecule_count",
            "source_view",
            "hierarchy_fingerprint",
        },
        label="molecular-order observation",
    )
    value["molecular_orientation_prototypes_deg"] = tuple(
        _sequence(
            value["molecular_orientation_prototypes_deg"],
            "molecular_orientation_prototypes_deg",
        )
    )
    return MolecularOrderTypeObservation(**value)


def _orientation_type_from_payload(
    payload: object,
) -> MolecularOrderOrientationType:
    value = _exact_mapping(
        payload,
        required={
            "type_id",
            "label",
            "prototype_angles_deg",
            "periodicity_deg",
            "observation_count",
        },
        label="orientation type",
    )
    value["prototype_angles_deg"] = tuple(
        _sequence(value["prototype_angles_deg"], "prototype_angles_deg")
    )
    return MolecularOrderOrientationType(**value)


def _assignment_from_payload(
    payload: object,
) -> MolecularOrderTypeAssignment:
    value = _exact_mapping(
        payload,
        required={
            "observation_key",
            "geometry",
            "orientation",
            "stacking",
        },
        label="molecular-order assignment",
    )
    return MolecularOrderTypeAssignment(
        observation_key=tuple(
            _sequence(value["observation_key"], "observation_key")
        ),
        geometry=_layer_assignment_from_payload(value["geometry"]),
        orientation=_layer_assignment_from_payload(value["orientation"]),
        stacking=_layer_assignment_from_payload(value["stacking"]),
    )


def _layer_assignment_from_payload(
    payload: object,
) -> MolecularOrderLayerAssignment:
    return MolecularOrderLayerAssignment(
        **_exact_mapping(
            payload,
            required={
                "status",
                "type_id",
                "type_label",
                "unclassified_reason",
            },
            label="molecular-order layer assignment",
        )
    )


def _exact_mapping(
    payload: object,
    *,
    required: set[str],
    label: str,
) -> dict[str, object]:
    value = dict(_mapping(payload, label))
    if set(value) != required:
        raise ValueError(f"{label} fields must match the schema.")
    return value


def _mapping(payload: object, label: str) -> Mapping[str, object]:
    if not isinstance(payload, Mapping):
        raise TypeError(f"{label} must be a mapping.")
    return payload


def _sequence(payload: object, label: str) -> tuple[object, ...]:
    if not isinstance(payload, (list, tuple)):
        raise TypeError(f"{label} must be a sequence.")
    return tuple(payload)


__all__ = [
    "MOLECULAR_ORDER_TYPE_CACHE_RECORD_SCHEMA_VERSION",
    "MOLECULAR_ORDER_TYPE_CONFIGURATION_SCHEMA_VERSION",
    "MolecularOrderTypeCacheDecodeError",
    "MolecularOrderTypeCacheRecord",
    "MolecularOrderTypeSessionState",
]
