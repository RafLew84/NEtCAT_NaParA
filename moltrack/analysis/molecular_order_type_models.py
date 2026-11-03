"""Versioned contracts for hierarchical molecular-order type classification."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from math import isclose, isfinite
from numbers import Real
from typing import Literal, get_args

from .frame_ranges import (
    MolecularFrameRangeAnalysisMode,
    MolecularFrameRangeAnalysisScope,
)
from .lattice_domain_models import (
    LatticeDomainComponentType,
    LatticeDomainDominantSymmetry,
)
from .molecular_orientation_prototype_models import (
    MolecularOrientationPatternMode,
    MolecularOrientationPatternPhase,
)
from .molecular_stacking_models import StackingPattern


MOLECULAR_ORDER_TYPE_CLASSIFICATION_SCHEMA_VERSION = 1
MOLECULAR_ORDER_TYPE_CLASSIFICATION_ALGORITHM_VERSION = (
    "moltrack-molecular-order-type-classification-v1"
)

MolecularOrderGeometryFeature = Literal[
    "dominant_symmetry",
    "theta3_lattice",
    "theta6_lattice",
]
MolecularOrderOrientationFeature = Literal["prototype_angles"]
MolecularOrderStackingFeature = Literal["pattern", "mode", "phase"]
MolecularOrderLayerAssignmentStatus = Literal[
    "classified",
    "unclassified",
]
MolecularOrderLayerUnclassifiedReason = Literal[
    "geometry_ambiguous",
    "geometry_features_unavailable",
    "orientation_features_unavailable",
    "stacking_result_unavailable",
    "stacking_features_unavailable",
    "below_minimum_observations_per_type",
]
MolecularOrderTypeObservationKey = tuple[str, int, int, int, str]
MolecularOrderDomainKey = tuple[int, str]

_GEOMETRY_FEATURE_ORDER = tuple(get_args(MolecularOrderGeometryFeature))
_ORIENTATION_FEATURE_ORDER = tuple(get_args(MolecularOrderOrientationFeature))
_STACKING_FEATURE_ORDER = tuple(get_args(MolecularOrderStackingFeature))
_SYMMETRIES = set(get_args(LatticeDomainDominantSymmetry))
_STACKING_PATTERNS = set(get_args(StackingPattern))
_STACKING_MODES = set(get_args(MolecularOrientationPatternMode))
_STACKING_PHASES = set(get_args(MolecularOrientationPatternPhase))
_UNCLASSIFIED_REASONS = set(
    get_args(MolecularOrderLayerUnclassifiedReason)
)


@dataclass(frozen=True)
class MolecularOrderTypeClassificationSettings:
    """Explicit features and tolerances used independently by each layer."""

    geometry_features: tuple[MolecularOrderGeometryFeature, ...] = (
        "dominant_symmetry",
        "theta3_lattice",
        "theta6_lattice",
    )
    orientation_features: tuple[MolecularOrderOrientationFeature, ...] = (
        "prototype_angles",
    )
    stacking_features: tuple[MolecularOrderStackingFeature, ...] = ("pattern",)
    lattice_orientation_tolerance_deg: float = 5.0
    molecular_orientation_tolerance_deg: float = 12.0
    minimum_observations_per_type: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "geometry_features",
            _feature_selection(
                self.geometry_features,
                _GEOMETRY_FEATURE_ORDER,
                "geometry_features",
            ),
        )
        object.__setattr__(
            self,
            "orientation_features",
            _feature_selection(
                self.orientation_features,
                _ORIENTATION_FEATURE_ORDER,
                "orientation_features",
            ),
        )
        object.__setattr__(
            self,
            "stacking_features",
            _feature_selection(
                self.stacking_features,
                _STACKING_FEATURE_ORDER,
                "stacking_features",
            ),
        )
        if (
            "phase" in self.stacking_features
            and "mode" not in self.stacking_features
        ):
            raise ValueError(
                "stacking_features must include mode when phase is selected."
            )
        lattice_tolerance = _positive_float(
            self.lattice_orientation_tolerance_deg,
            "lattice_orientation_tolerance_deg",
        )
        if lattice_tolerance > 30.0:
            raise ValueError(
                "lattice_orientation_tolerance_deg must not exceed 30."
            )
        molecular_tolerance = _positive_float(
            self.molecular_orientation_tolerance_deg,
            "molecular_orientation_tolerance_deg",
        )
        if molecular_tolerance > 90.0:
            raise ValueError(
                "molecular_orientation_tolerance_deg must not exceed 90."
            )
        object.__setattr__(
            self,
            "lattice_orientation_tolerance_deg",
            lattice_tolerance,
        )
        object.__setattr__(
            self,
            "molecular_orientation_tolerance_deg",
            molecular_tolerance,
        )
        object.__setattr__(
            self,
            "minimum_observations_per_type",
            _positive_integer(
                self.minimum_observations_per_type,
                "minimum_observations_per_type",
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "geometry_features": list(self.geometry_features),
            "orientation_features": list(self.orientation_features),
            "stacking_features": list(self.stacking_features),
            "lattice_orientation_tolerance_deg": (
                self.lattice_orientation_tolerance_deg
            ),
            "molecular_orientation_tolerance_deg": (
                self.molecular_orientation_tolerance_deg
            ),
            "minimum_observations_per_type": (
                self.minimum_observations_per_type
            ),
        }

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "MolecularOrderTypeClassificationSettings":
        if not isinstance(payload, Mapping):
            raise TypeError(
                "Molecular-order type settings must be a mapping."
            )
        required = {
            "geometry_features",
            "orientation_features",
            "stacking_features",
            "lattice_orientation_tolerance_deg",
            "molecular_orientation_tolerance_deg",
            "minimum_observations_per_type",
        }
        if set(payload) != required:
            raise ValueError(
                "Molecular-order type setting fields must match the schema."
            )
        return cls(
            geometry_features=_feature_payload(
                payload["geometry_features"],
                "geometry_features",
            ),
            orientation_features=_feature_payload(
                payload["orientation_features"],
                "orientation_features",
            ),
            stacking_features=_feature_payload(
                payload["stacking_features"],
                "stacking_features",
            ),
            lattice_orientation_tolerance_deg=payload[
                "lattice_orientation_tolerance_deg"
            ],
            molecular_orientation_tolerance_deg=payload[
                "molecular_orientation_tolerance_deg"
            ],
            minimum_observations_per_type=payload[
                "minimum_observations_per_type"
            ],
        )


def molecular_order_type_settings_fingerprint(
    settings: MolecularOrderTypeClassificationSettings,
) -> str:
    if not isinstance(settings, MolecularOrderTypeClassificationSettings):
        raise TypeError(
            "settings must be MolecularOrderTypeClassificationSettings."
        )
    return _fingerprint(
        {
            "algorithm": (
                MOLECULAR_ORDER_TYPE_CLASSIFICATION_ALGORITHM_VERSION
            ),
            "settings": settings.to_dict(),
        }
    )


@dataclass(frozen=True)
class MolecularOrderTypeObservation:
    """Classification snapshot of one hierarchy domain in one named range."""

    range_name: str
    range_start_frame: int
    range_end_frame: int
    frame_index: int
    lattice_domain_id: str
    component_type: LatticeDomainComponentType
    dominant_symmetry: LatticeDomainDominantSymmetry
    theta3_lattice_deg: float | None
    theta6_lattice_deg: float | None
    molecular_orientation_prototypes_deg: tuple[float, ...]
    molecular_orientation_periodicity_deg: float | None
    stacking_pattern: StackingPattern
    stacking_mode: MolecularOrientationPatternMode | None
    stacking_phase: MolecularOrientationPatternPhase | None
    molecule_count: int
    source_view: str
    hierarchy_fingerprint: str

    def __post_init__(self) -> None:
        range_name = _non_empty_string(self.range_name, "range_name")
        range_start = _non_negative_integer(
            self.range_start_frame,
            "range_start_frame",
        )
        range_end = _non_negative_integer(
            self.range_end_frame,
            "range_end_frame",
        )
        frame_index = _non_negative_integer(
            self.frame_index,
            "frame_index",
        )
        if not range_start <= frame_index <= range_end:
            raise ValueError("frame_index must lie inside its named range.")
        domain_id = _non_empty_string(
            self.lattice_domain_id,
            "lattice_domain_id",
        )
        if not domain_id.startswith("lattice-"):
            raise ValueError(
                "lattice_domain_id must use the 'lattice-' prefix."
            )
        if self.component_type not in {
            "full_domain",
            "small_ordered_island",
        }:
            raise ValueError("Unsupported component_type.")
        if self.dominant_symmetry not in _SYMMETRIES:
            raise ValueError("Unsupported dominant_symmetry.")
        theta3 = _optional_periodic_angle(
            self.theta3_lattice_deg,
            60.0,
            "theta3_lattice_deg",
        )
        theta6 = _optional_periodic_angle(
            self.theta6_lattice_deg,
            60.0,
            "theta6_lattice_deg",
        )
        prototypes = tuple(
            _finite_float(value, "molecular_orientation_prototypes_deg")
            for value in self.molecular_orientation_prototypes_deg
        )
        if len(prototypes) > 2:
            raise ValueError(
                "At most two molecular orientation prototypes are supported."
            )
        periodicity = (
            None
            if self.molecular_orientation_periodicity_deg is None
            else _positive_float(
                self.molecular_orientation_periodicity_deg,
                "molecular_orientation_periodicity_deg",
            )
        )
        if bool(prototypes) != (periodicity is not None):
            raise ValueError(
                "Molecular prototypes and periodicity must be available together."
            )
        if periodicity is not None:
            prototypes = tuple(
                sorted(
                    _normalize_periodic_angle(
                        value,
                        periodicity,
                        "molecular_orientation_prototypes_deg",
                    )
                    for value in prototypes
                )
            )
        if self.stacking_pattern not in _STACKING_PATTERNS:
            raise ValueError("Unsupported stacking_pattern.")
        if (
            self.stacking_mode is not None
            and self.stacking_mode not in _STACKING_MODES
        ):
            raise ValueError("Unsupported stacking_mode.")
        if (
            self.stacking_phase is not None
            and self.stacking_phase not in _STACKING_PHASES
        ):
            raise ValueError("Unsupported stacking_phase.")
        object.__setattr__(self, "range_name", range_name)
        object.__setattr__(self, "range_start_frame", range_start)
        object.__setattr__(self, "range_end_frame", range_end)
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "lattice_domain_id", domain_id)
        object.__setattr__(self, "theta3_lattice_deg", theta3)
        object.__setattr__(self, "theta6_lattice_deg", theta6)
        object.__setattr__(
            self,
            "molecular_orientation_prototypes_deg",
            prototypes,
        )
        object.__setattr__(
            self,
            "molecular_orientation_periodicity_deg",
            periodicity,
        )
        object.__setattr__(
            self,
            "molecule_count",
            _positive_integer(self.molecule_count, "molecule_count"),
        )
        object.__setattr__(
            self,
            "source_view",
            _non_empty_string(self.source_view, "source_view"),
        )
        object.__setattr__(
            self,
            "hierarchy_fingerprint",
            _sha256_digest(
                self.hierarchy_fingerprint,
                "hierarchy_fingerprint",
            ),
        )

    @property
    def stable_key(self) -> MolecularOrderTypeObservationKey:
        return (
            self.range_name,
            self.range_start_frame,
            self.range_end_frame,
            self.frame_index,
            self.lattice_domain_id,
        )

    @property
    def domain_key(self) -> MolecularOrderDomainKey:
        return self.frame_index, self.lattice_domain_id


def molecular_order_type_observations_fingerprint(
    observations: tuple[MolecularOrderTypeObservation, ...],
) -> str:
    normalized = tuple(observations)
    if any(
        not isinstance(value, MolecularOrderTypeObservation)
        for value in normalized
    ):
        raise TypeError(
            "observations must contain MolecularOrderTypeObservation values."
        )
    return _fingerprint([asdict(value) for value in normalized])


@dataclass(frozen=True)
class MolecularOrderGeometryType:
    type_id: int
    label: str
    dominant_symmetry: LatticeDomainDominantSymmetry | None
    prototype_theta3_lattice_deg: float | None
    prototype_theta6_lattice_deg: float | None
    observation_count: int

    def __post_init__(self) -> None:
        _validate_type_identity(self.type_id, self.label)
        if (
            self.dominant_symmetry is not None
            and self.dominant_symmetry not in _SYMMETRIES
        ):
            raise ValueError("Unsupported geometry type symmetry.")
        object.__setattr__(
            self,
            "prototype_theta3_lattice_deg",
            _optional_periodic_angle(
                self.prototype_theta3_lattice_deg,
                60.0,
                "prototype_theta3_lattice_deg",
            ),
        )
        object.__setattr__(
            self,
            "prototype_theta6_lattice_deg",
            _optional_periodic_angle(
                self.prototype_theta6_lattice_deg,
                60.0,
                "prototype_theta6_lattice_deg",
            ),
        )
        object.__setattr__(
            self,
            "observation_count",
            _positive_integer(self.observation_count, "observation_count"),
        )


@dataclass(frozen=True)
class MolecularOrderOrientationType:
    type_id: int
    label: str
    prototype_angles_deg: tuple[float, ...]
    periodicity_deg: float
    observation_count: int

    def __post_init__(self) -> None:
        _validate_type_identity(self.type_id, self.label)
        periodicity = _positive_float(
            self.periodicity_deg,
            "periodicity_deg",
        )
        prototypes = tuple(
            sorted(
                _normalize_periodic_angle(
                    value,
                    periodicity,
                    "prototype_angles_deg",
                )
                for value in self.prototype_angles_deg
            )
        )
        if not 1 <= len(prototypes) <= 2:
            raise ValueError(
                "Orientation type requires one or two prototype angles."
            )
        object.__setattr__(self, "prototype_angles_deg", prototypes)
        object.__setattr__(self, "periodicity_deg", periodicity)
        object.__setattr__(
            self,
            "observation_count",
            _positive_integer(self.observation_count, "observation_count"),
        )


@dataclass(frozen=True)
class MolecularOrderStackingType:
    type_id: int
    label: str
    pattern: StackingPattern | None
    mode: MolecularOrientationPatternMode | None
    phase: MolecularOrientationPatternPhase | None
    observation_count: int

    def __post_init__(self) -> None:
        _validate_type_identity(self.type_id, self.label)
        if self.pattern is not None and self.pattern not in _STACKING_PATTERNS:
            raise ValueError("Unsupported stacking type pattern.")
        if self.mode is not None and self.mode not in _STACKING_MODES:
            raise ValueError("Unsupported stacking type mode.")
        if self.phase is not None and self.phase not in _STACKING_PHASES:
            raise ValueError("Unsupported stacking type phase.")
        object.__setattr__(
            self,
            "observation_count",
            _positive_integer(self.observation_count, "observation_count"),
        )


@dataclass(frozen=True)
class MolecularOrderLayerAssignment:
    status: MolecularOrderLayerAssignmentStatus
    type_id: int | None
    type_label: str | None
    unclassified_reason: MolecularOrderLayerUnclassifiedReason | None

    def __post_init__(self) -> None:
        if self.status == "classified":
            type_id = _non_negative_integer(self.type_id, "type_id")
            expected_label = molecular_order_type_label(type_id)
            if self.type_label != expected_label:
                raise ValueError("type_label must match type_id.")
            if self.unclassified_reason is not None:
                raise ValueError(
                    "A classified layer cannot have an unclassified reason."
                )
        elif self.status == "unclassified":
            if self.type_id is not None or self.type_label is not None:
                raise ValueError(
                    "An unclassified layer cannot reference a type."
                )
            if self.unclassified_reason not in _UNCLASSIFIED_REASONS:
                raise ValueError(
                    "An unclassified layer requires a supported reason."
                )
        else:
            raise ValueError("Unsupported layer assignment status.")

    @classmethod
    def classified(cls, type_id: int) -> "MolecularOrderLayerAssignment":
        return cls(
            status="classified",
            type_id=type_id,
            type_label=molecular_order_type_label(type_id),
            unclassified_reason=None,
        )

    @classmethod
    def unclassified(
        cls,
        reason: MolecularOrderLayerUnclassifiedReason,
    ) -> "MolecularOrderLayerAssignment":
        return cls(
            status="unclassified",
            type_id=None,
            type_label=None,
            unclassified_reason=reason,
        )


@dataclass(frozen=True)
class MolecularOrderTypeAssignment:
    observation_key: MolecularOrderTypeObservationKey
    geometry: MolecularOrderLayerAssignment
    orientation: MolecularOrderLayerAssignment
    stacking: MolecularOrderLayerAssignment

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "observation_key",
            _observation_key(self.observation_key),
        )
        for field_name in ("geometry", "orientation", "stacking"):
            if not isinstance(
                getattr(self, field_name),
                MolecularOrderLayerAssignment,
            ):
                raise TypeError(
                    f"{field_name} must be MolecularOrderLayerAssignment."
                )


@dataclass(frozen=True)
class MolecularOrderTypeClassificationResult:
    analysis_scope: MolecularFrameRangeAnalysisScope
    settings: MolecularOrderTypeClassificationSettings
    settings_fingerprint: str
    hierarchy_fingerprint: str
    input_fingerprint: str
    observations: tuple[MolecularOrderTypeObservation, ...]
    geometry_types: tuple[MolecularOrderGeometryType, ...]
    orientation_types: tuple[MolecularOrderOrientationType, ...]
    stacking_types: tuple[MolecularOrderStackingType, ...]
    assignments: tuple[MolecularOrderTypeAssignment, ...]
    schema_version: int = MOLECULAR_ORDER_TYPE_CLASSIFICATION_SCHEMA_VERSION
    uses_tracking: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.analysis_scope,
            MolecularFrameRangeAnalysisScope,
        ):
            raise TypeError(
                "analysis_scope must be MolecularFrameRangeAnalysisScope."
            )
        if not isinstance(
            self.settings,
            MolecularOrderTypeClassificationSettings,
        ):
            raise TypeError(
                "settings must be MolecularOrderTypeClassificationSettings."
            )
        expected_settings_fingerprint = (
            molecular_order_type_settings_fingerprint(self.settings)
        )
        if self.settings_fingerprint != expected_settings_fingerprint:
            raise ValueError(
                "settings_fingerprint must match classification settings."
            )
        hierarchy_fingerprint = _sha256_digest(
            self.hierarchy_fingerprint,
            "hierarchy_fingerprint",
        )
        input_fingerprint = _sha256_digest(
            self.input_fingerprint,
            "input_fingerprint",
        )
        observations = tuple(self.observations)
        if any(
            not isinstance(value, MolecularOrderTypeObservation)
            for value in observations
        ):
            raise TypeError(
                "observations must contain molecular-order observations."
            )
        observation_keys = tuple(value.stable_key for value in observations)
        if observation_keys != tuple(sorted(set(observation_keys))):
            raise ValueError(
                "Observations must have sorted unique stable keys."
            )
        if input_fingerprint != (
            molecular_order_type_observations_fingerprint(observations)
        ):
            raise ValueError(
                "input_fingerprint must match classification observations."
            )
        _validate_observation_scope(
            observations,
            scope=self.analysis_scope,
            hierarchy_fingerprint=hierarchy_fingerprint,
        )
        geometry_types = _type_collection(
            self.geometry_types,
            MolecularOrderGeometryType,
            "geometry_types",
        )
        orientation_types = _type_collection(
            self.orientation_types,
            MolecularOrderOrientationType,
            "orientation_types",
        )
        stacking_types = _type_collection(
            self.stacking_types,
            MolecularOrderStackingType,
            "stacking_types",
        )
        for collection in (
            geometry_types,
            orientation_types,
            stacking_types,
        ):
            if any(
                value.observation_count
                < self.settings.minimum_observations_per_type
                for value in collection
            ):
                raise ValueError(
                    "Classified types must reach minimum_observations_per_type."
                )
        assignments = tuple(self.assignments)
        if any(
            not isinstance(value, MolecularOrderTypeAssignment)
            for value in assignments
        ):
            raise TypeError(
                "assignments must contain molecular-order assignments."
            )
        assignment_keys = tuple(value.observation_key for value in assignments)
        if assignment_keys != observation_keys:
            raise ValueError(
                "Assignments must align with every observation exactly once."
            )
        _validate_layer_counts(
            assignments,
            geometry_types,
            "geometry",
        )
        _validate_layer_counts(
            assignments,
            orientation_types,
            "orientation",
        )
        _validate_layer_counts(
            assignments,
            stacking_types,
            "stacking",
        )
        if self.schema_version != (
            MOLECULAR_ORDER_TYPE_CLASSIFICATION_SCHEMA_VERSION
        ):
            raise ValueError("Unsupported classification schema_version.")
        if self.uses_tracking is not False:
            raise ValueError(
                "Molecular-order type classification cannot use tracking."
            )
        object.__setattr__(
            self,
            "settings_fingerprint",
            expected_settings_fingerprint,
        )
        object.__setattr__(
            self,
            "hierarchy_fingerprint",
            hierarchy_fingerprint,
        )
        object.__setattr__(self, "input_fingerprint", input_fingerprint)
        object.__setattr__(self, "observations", observations)
        object.__setattr__(self, "geometry_types", geometry_types)
        object.__setattr__(self, "orientation_types", orientation_types)
        object.__setattr__(self, "stacking_types", stacking_types)
        object.__setattr__(self, "assignments", assignments)
        object.__setattr__(self, "uses_tracking", False)

    @property
    def analysis_mode(self) -> MolecularFrameRangeAnalysisMode:
        return self.analysis_scope.analysis_mode

    def assignment_for_domain(
        self,
        range_name: str,
        frame_index: int,
        lattice_domain_id: str,
    ) -> MolecularOrderTypeAssignment:
        normalized_name = _non_empty_string(range_name, "range_name")
        normalized_frame = _non_negative_integer(
            frame_index,
            "frame_index",
        )
        normalized_domain = _non_empty_string(
            lattice_domain_id,
            "lattice_domain_id",
        )
        matches = tuple(
            assignment
            for assignment in self.assignments
            if (
                assignment.observation_key[0] == normalized_name
                and assignment.observation_key[3] == normalized_frame
                and assignment.observation_key[4] == normalized_domain
            )
        )
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise KeyError(
                "Ambiguous range/frame/lattice-domain assignment; use "
                "assignment_for_observation_key with the complete range "
                "identity."
            )
        raise KeyError(
            "Unknown range/frame/lattice-domain assignment: "
            f"{(normalized_name, normalized_frame, normalized_domain)!r}."
        )

    def assignment_for_observation_key(
        self,
        observation_key: MolecularOrderTypeObservationKey,
    ) -> MolecularOrderTypeAssignment:
        normalized_key = _observation_key(observation_key)
        for assignment in self.assignments:
            key = assignment.observation_key
            if key == normalized_key:
                return assignment
        raise KeyError(
            f"Unknown molecular-order observation key: {normalized_key!r}."
        )


def molecular_order_type_classification_fingerprint(
    result: MolecularOrderTypeClassificationResult,
) -> str:
    if not isinstance(result, MolecularOrderTypeClassificationResult):
        raise TypeError(
            "result must be MolecularOrderTypeClassificationResult."
        )
    return _fingerprint(
        {
            "algorithm": (
                MOLECULAR_ORDER_TYPE_CLASSIFICATION_ALGORITHM_VERSION
            ),
            "result": asdict(result),
        }
    )


def molecular_order_type_label(type_id: int) -> str:
    value = _non_negative_integer(type_id, "type_id") + 1
    characters = []
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        characters.append(chr(ord("A") + remainder))
    return "".join(reversed(characters))


def _validate_type_identity(type_id: int, label: str) -> None:
    normalized_id = _non_negative_integer(type_id, "type_id")
    if label != molecular_order_type_label(normalized_id):
        raise ValueError("Type label must match type_id.")


def _type_collection(
    values: tuple[object, ...],
    expected_type: type,
    field_name: str,
) -> tuple[object, ...]:
    normalized = tuple(values)
    if any(not isinstance(value, expected_type) for value in normalized):
        raise TypeError(
            f"{field_name} must contain {expected_type.__name__} values."
        )
    if tuple(value.type_id for value in normalized) != tuple(
        range(len(normalized))
    ):
        raise ValueError(
            f"{field_name} type IDs must be contiguous and ordered."
        )
    return normalized


def _validate_layer_counts(
    assignments: tuple[MolecularOrderTypeAssignment, ...],
    types: tuple[object, ...],
    field_name: str,
) -> None:
    counts = {value.type_id: 0 for value in types}
    labels = {value.type_id: value.label for value in types}
    for assignment in assignments:
        layer = getattr(assignment, field_name)
        if layer.status != "classified":
            continue
        if layer.type_id not in counts:
            raise ValueError(
                f"{field_name} assignment references an unknown type."
            )
        if layer.type_label != labels[layer.type_id]:
            raise ValueError(
                f"{field_name} assignment label does not match its type."
            )
        counts[layer.type_id] += 1
    if any(
        counts[value.type_id] != value.observation_count for value in types
    ):
        raise ValueError(
            f"{field_name} type observation counts are inconsistent."
        )


def _validate_observation_scope(
    observations: tuple[MolecularOrderTypeObservation, ...],
    *,
    scope: MolecularFrameRangeAnalysisScope,
    hierarchy_fingerprint: str,
) -> None:
    ranges = {
        (value.name, value.start_frame, value.end_frame)
        for value in scope.ranges
    }
    for observation in observations:
        if (
            observation.range_name,
            observation.range_start_frame,
            observation.range_end_frame,
        ) not in ranges:
            raise ValueError("Observation does not belong to analysis_scope.")
        if observation.source_view != scope.source_view:
            raise ValueError(
                "Observation source_view does not match analysis_scope."
            )
        if observation.hierarchy_fingerprint != hierarchy_fingerprint:
            raise ValueError(
                "Observation hierarchy provenance does not match the result."
            )


def _observation_key(value: object) -> MolecularOrderTypeObservationKey:
    if not isinstance(value, tuple) or len(value) != 5:
        raise TypeError(
            "observation_key must be a five-field stable key tuple."
        )
    range_name = _non_empty_string(value[0], "observation range_name")
    range_start = _non_negative_integer(value[1], "observation range_start")
    range_end = _non_negative_integer(value[2], "observation range_end")
    frame_index = _non_negative_integer(value[3], "observation frame_index")
    domain_id = _non_empty_string(value[4], "observation lattice_domain_id")
    if not range_start <= frame_index <= range_end:
        raise ValueError("Observation key frame must lie inside its range.")
    return range_name, range_start, range_end, frame_index, domain_id


def _feature_selection(
    values: object,
    supported_order: tuple[str, ...],
    field_name: str,
) -> tuple[str, ...]:
    try:
        normalized = tuple(values)
    except TypeError as exc:
        raise TypeError(f"{field_name} must be an iterable.") from exc
    if not normalized:
        raise ValueError(f"{field_name} must select at least one feature.")
    if any(not isinstance(value, str) for value in normalized):
        raise TypeError(f"{field_name} must contain strings.")
    if len(set(normalized)) != len(normalized):
        raise ValueError(f"{field_name} cannot contain duplicates.")
    unsupported = set(normalized).difference(supported_order)
    if unsupported:
        raise ValueError(f"{field_name} contains an unsupported feature.")
    return tuple(value for value in supported_order if value in normalized)


def _feature_payload(value: object, field_name: str) -> tuple[object, ...]:
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{field_name} must be a sequence.")
    return tuple(value)


def _optional_periodic_angle(
    value: object,
    periodicity: float,
    field_name: str,
) -> float | None:
    if value is None:
        return None
    return _normalize_periodic_angle(value, periodicity, field_name)


def _normalize_periodic_angle(
    value: object,
    periodicity: float,
    field_name: str,
) -> float:
    normalized = _finite_float(value, field_name) % periodicity
    if isclose(normalized, 0.0, abs_tol=1e-12) or isclose(
        normalized,
        periodicity,
        abs_tol=1e-12,
    ):
        return 0.0
    return normalized


def _sha256_digest(value: object, field_name: str) -> str:
    normalized = _non_empty_string(value, field_name)
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise ValueError(f"{field_name} must be a lowercase SHA-256 digest.")
    return normalized


def _positive_integer(value: object, field_name: str) -> int:
    normalized = _non_negative_integer(value, field_name)
    if normalized == 0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _non_negative_integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer.")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return value


def _positive_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number.")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


def _non_empty_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _fingerprint(payload: object) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return sha256(encoded).hexdigest()
