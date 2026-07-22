"""Contracts for bridge-resistant multisymmetry domain seed growth."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields
from hashlib import sha256
from math import isfinite
from typing import Literal, Mapping, get_args

from .m6_settings import MolecularM6OrientationAnalysisSettings


LATTICE_DOMAIN_SEED_GROWTH_SCHEMA_VERSION = 1
LATTICE_DOMAIN_SEED_GROWTH_ALGORITHM_VERSION = (
    "moltrack-lattice-domain-seed-growth-v1"
)

LatticeDomainSymmetry = Literal["trifold", "sixfold", "mixed"]
LatticeDomainSeedState = Literal[
    "proto_seed",
    "validated_seed",
    "small_ordered_island",
]
LatticeDomainPointRole = Literal["core", "halo", "boundary", "unassigned"]
LatticeDomainBoundaryReason = Literal[
    "competing_domain_claim",
    "batch_orientation_spread",
    "incompatible_domain_edge",
]


_SYMMETRIES = set(get_args(LatticeDomainSymmetry))
_SEED_STATES = set(get_args(LatticeDomainSeedState))
_POINT_ROLES = set(get_args(LatticeDomainPointRole))
_BOUNDARY_REASONS = set(get_args(LatticeDomainBoundaryReason))


@dataclass(frozen=True)
class LatticeDomainSeedGrowthSettings:
    """Thresholds for strict core construction and synchronous halo growth."""

    seed_min_model_score: float = 0.65
    halo_min_model_score: float = 0.25
    core_min_order_amplitude: float = 0.65
    halo_min_order_amplitude: float = 0.25
    seed_max_orientation_spread_deg: float = 8.0
    grow_max_orientation_spread_deg: float = 12.0
    conflict_margin: float = 0.05
    minimum_classification_confidence: float = 0.5
    minimum_orientation_confidence: float = 0.5
    min_neighbors_for_seed: int = 5
    min_ordered_component_size: int = 3
    min_seed_size: int = 5

    def __post_init__(self) -> None:
        for field_name in (
            "seed_min_model_score",
            "halo_min_model_score",
            "core_min_order_amplitude",
            "halo_min_order_amplitude",
            "minimum_classification_confidence",
            "minimum_orientation_confidence",
        ):
            value = _finite_float(getattr(self, field_name), field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must lie between 0 and 1.")
            object.__setattr__(self, field_name, value)
        if self.halo_min_model_score > self.seed_min_model_score:
            raise ValueError(
                "halo_min_model_score must not exceed seed_min_model_score."
            )
        if self.halo_min_order_amplitude > self.core_min_order_amplitude:
            raise ValueError(
                "halo_min_order_amplitude must not exceed core_min_order_amplitude."
            )
        for field_name in (
            "seed_max_orientation_spread_deg",
            "grow_max_orientation_spread_deg",
        ):
            value = _finite_float(getattr(self, field_name), field_name)
            if not 0.0 <= value <= 30.0:
                raise ValueError(f"{field_name} must be between 0 and 30 degrees.")
            object.__setattr__(self, field_name, value)
        conflict_margin = _finite_float(self.conflict_margin, "conflict_margin")
        if conflict_margin < 0.0:
            raise ValueError("conflict_margin must be non-negative.")
        object.__setattr__(self, "conflict_margin", conflict_margin)
        for field_name in (
            "min_neighbors_for_seed",
            "min_ordered_component_size",
            "min_seed_size",
        ):
            object.__setattr__(
                self,
                field_name,
                _positive_integer(getattr(self, field_name), field_name),
            )
        if self.min_ordered_component_size > self.min_seed_size:
            raise ValueError(
                "min_ordered_component_size must not exceed min_seed_size."
            )

    def to_dict(self) -> dict[str, int | float]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "LatticeDomainSeedGrowthSettings":
        if not isinstance(payload, Mapping):
            raise TypeError("Lattice-domain seed/growth settings must be a mapping.")
        names = {field.name for field in fields(cls)}
        if set(payload) != names:
            raise ValueError(
                "Lattice-domain seed/growth settings fields must match the schema."
            )
        return cls(**dict(payload))


def lattice_domain_seed_growth_settings_from_m6(
    settings: MolecularM6OrientationAnalysisSettings,
) -> LatticeDomainSeedGrowthSettings:
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    return LatticeDomainSeedGrowthSettings(
        seed_min_model_score=settings.lattice_seed_min_model_score,
        halo_min_model_score=settings.lattice_halo_min_model_score,
        core_min_order_amplitude=settings.q_seed,
        halo_min_order_amplitude=settings.q_grow,
        seed_max_orientation_spread_deg=settings.seed_angle_tolerance_deg,
        grow_max_orientation_spread_deg=settings.grow_angle_tolerance_deg,
        conflict_margin=settings.domain_conflict_margin,
        minimum_classification_confidence=(
            settings.lattice_edge_minimum_classification_confidence
        ),
        minimum_orientation_confidence=(
            settings.lattice_edge_minimum_orientation_confidence
        ),
        min_neighbors_for_seed=settings.min_neighbors_for_seed,
        min_ordered_component_size=settings.min_ordered_component_size,
        min_seed_size=settings.min_seed_size,
    )


def lattice_domain_seed_growth_settings_fingerprint(
    settings: LatticeDomainSeedGrowthSettings,
) -> str:
    if not isinstance(settings, LatticeDomainSeedGrowthSettings):
        raise TypeError("settings must be LatticeDomainSeedGrowthSettings.")
    payload = {
        "algorithm": LATTICE_DOMAIN_SEED_GROWTH_ALGORITHM_VERSION,
        "settings": settings.to_dict(),
    }
    return sha256(
        json.dumps(
            payload,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class LatticeDomainSeedComponent:
    """One strict core and any weaker points accepted around that frozen core."""

    component_id: int
    symmetry_model: LatticeDomainSymmetry
    seed_state: LatticeDomainSeedState
    core_point_indices: tuple[int, ...]
    core_source_ids: tuple[str, ...]
    halo_point_indices: tuple[int, ...]
    halo_source_ids: tuple[str, ...]
    core_theta3_deg: float | None
    core_theta6_deg: float | None
    core_theta3_spread_deg: float | None
    core_theta6_spread_deg: float | None
    assigned_theta3_spread_deg: float | None
    assigned_theta6_spread_deg: float | None

    def __post_init__(self) -> None:
        component_id = _non_negative_integer(self.component_id, "component_id")
        if self.symmetry_model not in _SYMMETRIES:
            raise ValueError(f"Unsupported symmetry_model: {self.symmetry_model!r}.")
        if self.seed_state not in _SEED_STATES:
            raise ValueError(f"Unsupported seed_state: {self.seed_state!r}.")
        core_indices, core_ids = _normalize_members(
            self.core_point_indices,
            self.core_source_ids,
            field_prefix="core",
            require_non_empty=True,
        )
        halo_indices, halo_ids = _normalize_members(
            self.halo_point_indices,
            self.halo_source_ids,
            field_prefix="halo",
            require_non_empty=False,
        )
        if set(core_indices).intersection(halo_indices):
            raise ValueError("Core and halo point indices must be disjoint.")
        if set(core_ids).intersection(halo_ids):
            raise ValueError("Core and halo source IDs must be disjoint.")
        for field_name in (
            "core_theta3_deg",
            "core_theta6_deg",
        ):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _finite_float(value, field_name) % 60.0)
        for field_name in (
            "core_theta3_spread_deg",
            "core_theta6_spread_deg",
            "assigned_theta3_spread_deg",
            "assigned_theta6_spread_deg",
        ):
            value = getattr(self, field_name)
            if value is not None:
                value = _finite_float(value, field_name)
                if not 0.0 <= value <= 30.0:
                    raise ValueError(f"{field_name} must be between 0 and 30 degrees.")
                object.__setattr__(self, field_name, value)
        if self.symmetry_model == "trifold":
            _require_channel(self.core_theta3_deg, self.core_theta3_spread_deg, "theta3")
        elif self.symmetry_model == "sixfold":
            _require_channel(self.core_theta6_deg, self.core_theta6_spread_deg, "theta6")
        else:
            _require_channel(self.core_theta3_deg, self.core_theta3_spread_deg, "theta3")
            _require_channel(self.core_theta6_deg, self.core_theta6_spread_deg, "theta6")
        object.__setattr__(self, "component_id", component_id)
        object.__setattr__(self, "core_point_indices", core_indices)
        object.__setattr__(self, "core_source_ids", core_ids)
        object.__setattr__(self, "halo_point_indices", halo_indices)
        object.__setattr__(self, "halo_source_ids", halo_ids)

    @property
    def seed_support_count(self) -> int:
        return len(self.core_point_indices)

    @property
    def core_size(self) -> int:
        return len(self.core_point_indices)

    @property
    def halo_size(self) -> int:
        return len(self.halo_point_indices)

    @property
    def point_indices(self) -> tuple[int, ...]:
        return tuple(sorted(self.core_point_indices + self.halo_point_indices))

    @property
    def source_ids(self) -> tuple[str, ...]:
        return self.core_source_ids + self.halo_source_ids


@dataclass(frozen=True)
class LatticeDomainSeedSupportStability:
    """Validated components under one neighboring min-seed threshold."""

    threshold_offset: Literal[-1, 0, 1]
    min_seed_size: int
    validated_component_ids: tuple[int, ...]
    validated_core_point_count: int
    halo_source_ids: tuple[str, ...]
    boundary_source_ids: tuple[str, ...]
    growth_iteration_count: int

    def __post_init__(self) -> None:
        if self.threshold_offset not in {-1, 0, 1}:
            raise ValueError("threshold_offset must be -1, 0, or 1.")
        object.__setattr__(
            self,
            "min_seed_size",
            _positive_integer(self.min_seed_size, "min_seed_size"),
        )
        component_ids = tuple(self.validated_component_ids)
        if (
            any(
                not isinstance(value, int) or isinstance(value, bool) or value < 0
                for value in component_ids
            )
            or component_ids != tuple(sorted(set(component_ids)))
        ):
            raise ValueError("validated_component_ids must be sorted unique indices.")
        object.__setattr__(self, "validated_component_ids", component_ids)
        object.__setattr__(
            self,
            "validated_core_point_count",
            _non_negative_integer(
                self.validated_core_point_count,
                "validated_core_point_count",
            ),
        )
        for field_name in ("halo_source_ids", "boundary_source_ids"):
            source_ids = tuple(getattr(self, field_name))
            if source_ids != tuple(sorted(set(source_ids))) or any(
                not isinstance(value, str) or not value for value in source_ids
            ):
                raise ValueError(f"{field_name} must contain sorted unique source IDs.")
            object.__setattr__(self, field_name, source_ids)
        if set(self.halo_source_ids).intersection(self.boundary_source_ids):
            raise ValueError("Stability halo and boundary source IDs must be disjoint.")
        object.__setattr__(
            self,
            "growth_iteration_count",
            _non_negative_integer(
                self.growth_iteration_count,
                "growth_iteration_count",
            ),
        )


@dataclass(frozen=True)
class LatticeDomainSeedGrowthResult:
    """Deterministic core/halo partition before final lattice-domain modeling."""

    source_ids: tuple[str, ...]
    point_count: int
    point_role: tuple[LatticeDomainPointRole, ...]
    component_id: tuple[int, ...]
    boundary_reason: tuple[LatticeDomainBoundaryReason | None, ...]
    components: tuple[LatticeDomainSeedComponent, ...]
    seed_support_stability: tuple[LatticeDomainSeedSupportStability, ...]
    growth_iteration_count: int
    settings: LatticeDomainSeedGrowthSettings
    first_shell_graph_fingerprint: str
    local_order_analysis_fingerprint: str
    local_symmetry_evidence_settings_fingerprint: str
    local_symmetry_bond_evidence_fingerprint: str
    edge_compatibility_settings_fingerprint: str
    settings_fingerprint: str
    schema_version: int = LATTICE_DOMAIN_SEED_GROWTH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        point_count = _non_negative_integer(self.point_count, "point_count")
        source_ids = tuple(self.source_ids)
        if len(source_ids) != point_count or len(set(source_ids)) != point_count:
            raise ValueError("source_ids must contain one unique value per point.")
        if any(not isinstance(value, str) or not value for value in source_ids):
            raise TypeError("source_ids must contain non-empty strings.")
        if self.schema_version != LATTICE_DOMAIN_SEED_GROWTH_SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema_version: {self.schema_version!r}.")
        roles = tuple(self.point_role)
        component_ids = tuple(self.component_id)
        reasons = tuple(self.boundary_reason)
        if not len(roles) == len(component_ids) == len(reasons) == point_count:
            raise ValueError("Point result fields must contain one value per point.")
        if any(role not in _POINT_ROLES for role in roles):
            raise ValueError("point_role contains an unsupported role.")
        if any(reason is not None and reason not in _BOUNDARY_REASONS for reason in reasons):
            raise ValueError("boundary_reason contains an unsupported reason.")
        components = tuple(self.components)
        if any(not isinstance(value, LatticeDomainSeedComponent) for value in components):
            raise TypeError("components must contain LatticeDomainSeedComponent values.")
        if tuple(component.component_id for component in components) != tuple(
            range(len(components))
        ):
            raise ValueError("components must use compact component IDs.")
        covered: set[int] = set()
        for component in components:
            for index in component.core_point_indices:
                _validate_component_member(
                    index,
                    component,
                    "core",
                    roles,
                    component_ids,
                    source_ids,
                )
                if index in covered:
                    raise ValueError("Component point memberships must be disjoint.")
                covered.add(index)
            for index in component.halo_point_indices:
                _validate_component_member(
                    index,
                    component,
                    "halo",
                    roles,
                    component_ids,
                    source_ids,
                )
                if index in covered:
                    raise ValueError("Component point memberships must be disjoint.")
                covered.add(index)
        for index, (role, component_id, reason) in enumerate(
            zip(roles, component_ids, reasons)
        ):
            if role in {"core", "halo"}:
                if index not in covered or reason is not None:
                    raise ValueError(
                        "Assigned core/halo points need membership and no boundary reason."
                    )
            elif component_id != -1 or index in covered:
                raise ValueError("Boundary and unassigned points must use component_id=-1.")
            if (role == "boundary") != (reason is not None):
                raise ValueError("Only boundary points require a boundary_reason.")
        stability = tuple(self.seed_support_stability)
        if tuple(item.threshold_offset for item in stability) != (-1, 0, 1):
            raise ValueError("seed_support_stability must contain offsets -1, 0, and 1.")
        valid_component_ids = set(range(len(components)))
        for item in stability:
            if not set(item.validated_component_ids).issubset(valid_component_ids):
                raise ValueError("Stability entries must reference existing components.")
            if not set(item.halo_source_ids + item.boundary_source_ids).issubset(
                source_ids
            ):
                raise ValueError("Stability entries must reference existing source IDs.")
        if not isinstance(self.settings, LatticeDomainSeedGrowthSettings):
            raise TypeError("settings must be LatticeDomainSeedGrowthSettings.")
        if self.settings_fingerprint != lattice_domain_seed_growth_settings_fingerprint(
            self.settings
        ):
            raise ValueError("settings_fingerprint must match settings.")
        object.__setattr__(
            self,
            "growth_iteration_count",
            _non_negative_integer(self.growth_iteration_count, "growth_iteration_count"),
        )
        for field_name in (
            "first_shell_graph_fingerprint",
            "local_order_analysis_fingerprint",
            "local_symmetry_evidence_settings_fingerprint",
            "local_symmetry_bond_evidence_fingerprint",
            "edge_compatibility_settings_fingerprint",
            "settings_fingerprint",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise TypeError(f"{field_name} must be a non-empty string.")
        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "point_count", point_count)
        object.__setattr__(self, "point_role", roles)
        object.__setattr__(self, "component_id", component_ids)
        object.__setattr__(self, "boundary_reason", reasons)
        object.__setattr__(self, "components", components)
        object.__setattr__(self, "seed_support_stability", stability)
        for item in stability:
            expected_threshold = max(
                1,
                self.settings.min_seed_size + item.threshold_offset,
            )
            expected_component_ids = tuple(
                component.component_id
                for component in components
                if component.seed_support_count >= expected_threshold
            )
            expected_point_count = sum(
                components[component_id].core_size
                for component_id in expected_component_ids
            )
            if (
                item.min_seed_size != expected_threshold
                or item.validated_component_ids != expected_component_ids
                or item.validated_core_point_count != expected_point_count
            ):
                raise ValueError(
                    "Seed-support stability must match component core support."
                )
        for component in components:
            expected_state: LatticeDomainSeedState
            if component.core_size >= self.settings.min_seed_size:
                expected_state = "validated_seed"
            elif component.core_size >= self.settings.min_ordered_component_size:
                expected_state = "small_ordered_island"
            else:
                expected_state = "proto_seed"
            if component.seed_state != expected_state:
                raise ValueError("Component seed_state must match its core support.")
            core_spreads = tuple(
                value
                for value in (
                    component.core_theta3_spread_deg,
                    component.core_theta6_spread_deg,
                )
                if value is not None
            )
            assigned_spreads = tuple(
                value
                for value in (
                    component.assigned_theta3_spread_deg,
                    component.assigned_theta6_spread_deg,
                )
                if value is not None
            )
            if any(
                value > self.settings.seed_max_orientation_spread_deg
                for value in core_spreads
            ):
                raise ValueError("Component core exceeds the configured seed spread.")
            if component.halo_size and any(
                value > self.settings.grow_max_orientation_spread_deg
                for value in assigned_spreads
            ):
                raise ValueError("Component assignment exceeds the configured grow spread.")


def lattice_domain_seed_growth_result_fingerprint(
    result: LatticeDomainSeedGrowthResult,
) -> str:
    """Fingerprint the complete normalized seed/grow partition and provenance."""

    if not isinstance(result, LatticeDomainSeedGrowthResult):
        raise TypeError("result must be LatticeDomainSeedGrowthResult.")
    return sha256(
        json.dumps(
            {
                "algorithm": LATTICE_DOMAIN_SEED_GROWTH_ALGORITHM_VERSION,
                "result": asdict(result),
            },
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _validate_component_member(
    index: int,
    component: LatticeDomainSeedComponent,
    expected_role: str,
    roles: tuple[LatticeDomainPointRole, ...],
    component_ids: tuple[int, ...],
    source_ids: tuple[str, ...],
) -> None:
    if index >= len(source_ids):
        raise ValueError("Component point index is outside the point field.")
    if roles[index] != expected_role or component_ids[index] != component.component_id:
        raise ValueError("Component membership must match per-point role and component ID.")
    member_ids = (
        component.core_source_ids if expected_role == "core" else component.halo_source_ids
    )
    member_indices = (
        component.core_point_indices if expected_role == "core" else component.halo_point_indices
    )
    if source_ids[index] != member_ids[member_indices.index(index)]:
        raise ValueError("Component source IDs must match point indices.")


def _normalize_members(
    indices: tuple[int, ...],
    source_ids: tuple[str, ...],
    *,
    field_prefix: str,
    require_non_empty: bool,
) -> tuple[tuple[int, ...], tuple[str, ...]]:
    normalized_indices = tuple(indices)
    normalized_ids = tuple(source_ids)
    if require_non_empty and not normalized_indices:
        raise ValueError(f"{field_prefix}_point_indices must not be empty.")
    if len(normalized_indices) != len(normalized_ids):
        raise ValueError(f"{field_prefix} indices and source IDs must have equal lengths.")
    if (
        any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in normalized_indices
        )
        or normalized_indices != tuple(sorted(set(normalized_indices)))
    ):
        raise ValueError(f"{field_prefix}_point_indices must be sorted unique indices.")
    if len(set(normalized_ids)) != len(normalized_ids) or any(
        not isinstance(value, str) or not value for value in normalized_ids
    ):
        raise ValueError(f"{field_prefix}_source_ids must be unique non-empty strings.")
    return normalized_indices, normalized_ids


def _require_channel(angle: float | None, spread: float | None, name: str) -> None:
    if angle is None or spread is None:
        raise ValueError(f"The active {name} channel requires an angle and spread.")


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a number.")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be a number.") from exc
    if not isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return number


def _non_negative_integer(value: object, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer.")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return value


def _positive_integer(value: object, field_name: str) -> int:
    value = _non_negative_integer(value, field_name)
    if value == 0:
        raise ValueError(f"{field_name} must be positive.")
    return value
