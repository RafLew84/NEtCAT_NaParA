"""Versioned contracts for multisymmetry lattice-domain edge decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from hashlib import sha256
from math import isfinite
from typing import Literal, Mapping, get_args

from .local_symmetry_evidence_models import LocalSymmetryModel
from .m6_settings import MolecularM6OrientationAnalysisSettings


LATTICE_DOMAIN_EDGE_COMPATIBILITY_SCHEMA_VERSION = 2
LATTICE_DOMAIN_EDGE_COMPATIBILITY_ALGORITHM_VERSION = (
    "moltrack-lattice-domain-edge-compatibility-v2"
)

LatticeDomainCompatibilityChannel = Literal["m3", "m6"]

LatticeDomainEdgeDecision = Literal[
    "compatible_trifold",
    "compatible_sixfold",
    "compatible_mixed",
    "conditional_halo_edge",
    "conflict_boundary",
    "no_domain_edge",
    "boundary_unassigned",
]
LatticeDomainEdgeRejectionReason = Literal[
    "near_equal_domain_claim",
    "endpoint_unavailable",
    "endpoint_disordered",
    "missing_compatible_orientation_channel",
    "trifold_orientation_mismatch",
    "sixfold_orientation_mismatch",
    "mixed_orientation_mismatch",
    "mixed_model_profile_mismatch",
    "incompatible_symmetry_models",
    "conditional_channel_too_weak",
    "no_compatible_conditional_channel",
]


_DECISIONS = set(get_args(LatticeDomainEdgeDecision))
_REJECTION_REASONS = set(get_args(LatticeDomainEdgeRejectionReason))
_RETAINED_DECISIONS = {
    "compatible_trifold",
    "compatible_sixfold",
    "compatible_mixed",
    "conditional_halo_edge",
}
_CORE_DECISIONS = {
    "compatible_trifold",
    "compatible_sixfold",
    "compatible_mixed",
}
_CORE_CONFIDENCE_CHANNELS = {
    "compatible_trifold": ("m3",),
    "compatible_sixfold": ("m6",),
    "compatible_mixed": ("m3", "m6"),
}
_BOUNDARY_DECISIONS = {"conflict_boundary", "boundary_unassigned"}
_COMPATIBILITY_CHANNELS = set(get_args(LatticeDomainCompatibilityChannel))
_DIRECT_COMPATIBILITY_CHANNELS = {
    "compatible_trifold": ("m3",),
    "compatible_sixfold": ("m6",),
    "compatible_mixed": ("m3", "m6"),
}


@dataclass(frozen=True)
class LatticeDomainEdgeCompatibilitySettings:
    """Explicit thresholds used to decide first-shell edge compatibility."""

    trifold_orientation_tolerance_deg: float = 8.0
    sixfold_orientation_tolerance_deg: float = 8.0
    mixed_model_profile_tolerance: float = 0.2
    conditional_channel_minimum_score: float = 0.5
    minimum_classification_confidence: float = 0.5
    minimum_orientation_confidence: float = 0.5

    def __post_init__(self) -> None:
        for field_name in (
            "trifold_orientation_tolerance_deg",
            "sixfold_orientation_tolerance_deg",
        ):
            value = _finite_float(getattr(self, field_name), field_name)
            if not 0.0 <= value <= 30.0:
                raise ValueError(f"{field_name} must be between 0 and 30 degrees.")
            object.__setattr__(self, field_name, value)
        for field_name in (
            "mixed_model_profile_tolerance",
            "conditional_channel_minimum_score",
            "minimum_classification_confidence",
            "minimum_orientation_confidence",
        ):
            value = _finite_float(getattr(self, field_name), field_name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{field_name} must lie between 0 and 1.")
            object.__setattr__(self, field_name, value)

    def to_dict(self) -> dict[str, float]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, object],
    ) -> "LatticeDomainEdgeCompatibilitySettings":
        if not isinstance(payload, Mapping):
            raise TypeError("Lattice-domain edge settings must be a mapping.")
        field_names = {field.name for field in fields(cls)}
        if set(payload) != field_names:
            raise ValueError("Lattice-domain edge settings fields must match the schema.")
        return cls(**dict(payload))


def lattice_domain_edge_settings_from_m6(
    settings: MolecularM6OrientationAnalysisSettings,
) -> LatticeDomainEdgeCompatibilitySettings:
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    return LatticeDomainEdgeCompatibilitySettings(
        trifold_orientation_tolerance_deg=(
            settings.lattice_edge_trifold_orientation_tolerance_deg
        ),
        sixfold_orientation_tolerance_deg=(
            settings.lattice_edge_sixfold_orientation_tolerance_deg
        ),
        mixed_model_profile_tolerance=(
            settings.lattice_edge_mixed_model_profile_tolerance
        ),
        conditional_channel_minimum_score=(
            settings.lattice_edge_conditional_channel_minimum_score
        ),
        minimum_classification_confidence=(
            settings.lattice_edge_minimum_classification_confidence
        ),
        minimum_orientation_confidence=(
            settings.lattice_edge_minimum_orientation_confidence
        ),
    )


def lattice_domain_edge_is_retained(decision: LatticeDomainEdgeDecision) -> bool:
    if decision not in _DECISIONS:
        raise ValueError(f"Unsupported lattice-domain edge decision: {decision!r}.")
    return decision in _RETAINED_DECISIONS


def lattice_domain_edge_is_core_eligible(
    decision: LatticeDomainEdgeDecision,
    *,
    classification_confidence: float | None,
    m3_orientation_confidence: float | None,
    m6_orientation_confidence: float | None,
    settings: LatticeDomainEdgeCompatibilitySettings,
) -> bool:
    if decision not in _DECISIONS:
        raise ValueError(f"Unsupported lattice-domain edge decision: {decision!r}.")
    if not isinstance(settings, LatticeDomainEdgeCompatibilitySettings):
        raise TypeError("settings must be LatticeDomainEdgeCompatibilitySettings.")
    if decision not in _CORE_DECISIONS:
        return False
    if (
        classification_confidence is None
        or classification_confidence < settings.minimum_classification_confidence
    ):
        return False
    confidence_by_channel = {
        "m3": m3_orientation_confidence,
        "m6": m6_orientation_confidence,
    }
    relevant_confidences = tuple(
        confidence_by_channel[channel]
        for channel in _CORE_CONFIDENCE_CHANNELS[decision]
    )
    return all(
        confidence is not None
        and confidence >= settings.minimum_orientation_confidence
        for confidence in relevant_confidences
    )


def lattice_domain_edge_settings_fingerprint(
    settings: LatticeDomainEdgeCompatibilitySettings,
) -> str:
    if not isinstance(settings, LatticeDomainEdgeCompatibilitySettings):
        raise TypeError("settings must be LatticeDomainEdgeCompatibilitySettings.")
    payload = {
        "algorithm": LATTICE_DOMAIN_EDGE_COMPATIBILITY_ALGORITHM_VERSION,
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
class LatticeDomainEdgeCompatibilityField:
    """Auditable compatibility decisions for every retained first-shell edge."""

    source_ids: tuple[str, ...]
    point_count: int
    edges_ij: tuple[tuple[int, int], ...]
    endpoint_models: tuple[tuple[LocalSymmetryModel, LocalSymmetryModel], ...]
    decision: tuple[LatticeDomainEdgeDecision, ...]
    compatible_channels: tuple[tuple[LatticeDomainCompatibilityChannel, ...], ...]
    retained_for_domain_growth: tuple[bool, ...]
    core_connectivity_eligible: tuple[bool, ...]
    rejection_reason: tuple[LatticeDomainEdgeRejectionReason | None, ...]
    theta3_delta_deg: tuple[float | None, ...]
    theta6_delta_deg: tuple[float | None, ...]
    model_profile_distance: tuple[float | None, ...]
    minimum_endpoint_classification_confidence: tuple[float | None, ...]
    minimum_endpoint_m3_orientation_confidence: tuple[float | None, ...]
    minimum_endpoint_m6_orientation_confidence: tuple[float | None, ...]
    settings: LatticeDomainEdgeCompatibilitySettings
    first_shell_graph_fingerprint: str
    local_order_analysis_fingerprint: str
    local_symmetry_evidence_settings_fingerprint: str
    local_symmetry_bond_evidence_fingerprint: str
    settings_fingerprint: str
    schema_version: int = LATTICE_DOMAIN_EDGE_COMPATIBILITY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        point_count = _non_negative_integer(self.point_count, "point_count")
        source_ids = tuple(self.source_ids)
        if len(source_ids) != point_count:
            raise ValueError("source_ids must contain one value per point.")
        if any(not isinstance(source_id, str) or not source_id for source_id in source_ids):
            raise TypeError("source_ids must contain non-empty strings.")
        if len(set(source_ids)) != point_count:
            raise ValueError("source_ids must be unique.")
        if self.schema_version != LATTICE_DOMAIN_EDGE_COMPATIBILITY_SCHEMA_VERSION:
            raise ValueError(f"Unsupported schema_version: {self.schema_version!r}.")
        if not isinstance(self.settings, LatticeDomainEdgeCompatibilitySettings):
            raise TypeError("settings must be LatticeDomainEdgeCompatibilitySettings.")
        if self.settings_fingerprint != lattice_domain_edge_settings_fingerprint(
            self.settings
        ):
            raise ValueError("settings_fingerprint must match settings.")

        edges = _normalized_edges(self.edges_ij, point_count=point_count)
        edge_count = len(edges)
        endpoint_models = tuple(self.endpoint_models)
        decisions = tuple(self.decision)
        compatible_channels = tuple(tuple(value) for value in self.compatible_channels)
        retained = tuple(self.retained_for_domain_growth)
        core_eligible = tuple(self.core_connectivity_eligible)
        reasons = tuple(self.rejection_reason)
        per_edge_values = (
            endpoint_models,
            decisions,
            compatible_channels,
            retained,
            core_eligible,
            reasons,
            tuple(self.theta3_delta_deg),
            tuple(self.theta6_delta_deg),
            tuple(self.model_profile_distance),
            tuple(self.minimum_endpoint_classification_confidence),
            tuple(self.minimum_endpoint_m3_orientation_confidence),
            tuple(self.minimum_endpoint_m6_orientation_confidence),
        )
        if any(len(values) != edge_count for values in per_edge_values):
            raise ValueError("Every edge field must contain one value per edge.")
        if any(
            len(models) != 2 or any(model not in get_args(LocalSymmetryModel) for model in models)
            for models in endpoint_models
        ):
            raise ValueError("endpoint_models contains an unsupported model pair.")
        if any(decision not in _DECISIONS for decision in decisions):
            raise ValueError("decision contains an unsupported edge decision.")
        if any(
            channels != tuple(dict.fromkeys(channels))
            or any(channel not in _COMPATIBILITY_CHANNELS for channel in channels)
            for channels in compatible_channels
        ):
            raise ValueError("compatible_channels contains unsupported channel data.")
        if any(not isinstance(value, bool) for value in retained + core_eligible):
            raise TypeError("Edge eligibility fields must contain booleans.")
        if any(reason is not None and reason not in _REJECTION_REASONS for reason in reasons):
            raise ValueError("rejection_reason contains an unsupported reason.")

        optional_unit_fields = (
            "model_profile_distance",
            "minimum_endpoint_classification_confidence",
            "minimum_endpoint_m3_orientation_confidence",
            "minimum_endpoint_m6_orientation_confidence",
        )
        for field_name in optional_unit_fields:
            object.__setattr__(
                self,
                field_name,
                _optional_bounded_tuple(
                    getattr(self, field_name),
                    field_name=field_name,
                    maximum=1.0,
                ),
            )
        for field_name in ("theta3_delta_deg", "theta6_delta_deg"):
            object.__setattr__(
                self,
                field_name,
                _optional_bounded_tuple(
                    getattr(self, field_name),
                    field_name=field_name,
                    maximum=30.0,
                ),
            )

        for index, decision in enumerate(decisions):
            expected_retained = lattice_domain_edge_is_retained(decision)
            expected_core = lattice_domain_edge_is_core_eligible(
                decision,
                classification_confidence=(
                    self.minimum_endpoint_classification_confidence[index]
                ),
                m3_orientation_confidence=(
                    self.minimum_endpoint_m3_orientation_confidence[index]
                ),
                m6_orientation_confidence=(
                    self.minimum_endpoint_m6_orientation_confidence[index]
                ),
                settings=self.settings,
            )
            if retained[index] != expected_retained:
                raise ValueError("retained_for_domain_growth must match decision.")
            if core_eligible[index] != expected_core:
                raise ValueError("core_connectivity_eligible must match decision.")
            if expected_retained != (reasons[index] is None):
                raise ValueError("Only rejected edges may contain rejection_reason.")
            channels = compatible_channels[index]
            if expected_retained != bool(channels):
                raise ValueError("Only retained edges may expose compatible channels.")
            expected_channels = _DIRECT_COMPATIBILITY_CHANNELS.get(decision)
            if expected_channels is not None and channels != expected_channels:
                raise ValueError(
                    "Direct compatibility decisions require their canonical channels."
                )

        for field_name in (
            "first_shell_graph_fingerprint",
            "local_order_analysis_fingerprint",
            "local_symmetry_evidence_settings_fingerprint",
            "local_symmetry_bond_evidence_fingerprint",
            "settings_fingerprint",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value:
                raise TypeError(f"{field_name} must be a non-empty string.")

        object.__setattr__(self, "source_ids", source_ids)
        object.__setattr__(self, "point_count", point_count)
        object.__setattr__(self, "edges_ij", edges)
        object.__setattr__(self, "endpoint_models", endpoint_models)
        object.__setattr__(self, "decision", decisions)
        object.__setattr__(self, "compatible_channels", compatible_channels)
        object.__setattr__(self, "retained_for_domain_growth", retained)
        object.__setattr__(self, "core_connectivity_eligible", core_eligible)
        object.__setattr__(self, "rejection_reason", reasons)

    @property
    def retained_edges_ij(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            edge
            for edge, retained in zip(self.edges_ij, self.retained_for_domain_growth)
            if retained
        )

    @property
    def core_edges_ij(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            edge
            for edge, eligible in zip(self.edges_ij, self.core_connectivity_eligible)
            if eligible
        )

    @property
    def boundary_edges_ij(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            edge
            for edge, decision in zip(self.edges_ij, self.decision)
            if decision in _BOUNDARY_DECISIONS
        )


def _normalized_edges(
    raw_edges: tuple[tuple[int, int], ...],
    *,
    point_count: int,
) -> tuple[tuple[int, int], ...]:
    edges: list[tuple[int, int]] = []
    for edge_index, raw_edge in enumerate(raw_edges):
        edge = tuple(raw_edge)
        if len(edge) != 2:
            raise ValueError(f"edges_ij[{edge_index}] must contain two indices.")
        left = _non_negative_integer(edge[0], f"edges_ij[{edge_index}][0]")
        right = _non_negative_integer(edge[1], f"edges_ij[{edge_index}][1]")
        if not 0 <= left < right < point_count:
            raise ValueError("Each edge must satisfy 0 <= i < j < point_count.")
        edges.append((left, right))
    if len(set(edges)) != len(edges):
        raise ValueError("edges_ij must not contain duplicate edges.")
    return tuple(edges)


def _optional_bounded_tuple(
    values: tuple[float | None, ...],
    *,
    field_name: str,
    maximum: float,
) -> tuple[float | None, ...]:
    normalized: list[float | None] = []
    for index, value in enumerate(values):
        if value is None:
            normalized.append(None)
            continue
        number = _finite_float(value, f"{field_name}[{index}]")
        if not 0.0 <= number <= maximum:
            raise ValueError(f"{field_name} values must lie between 0 and {maximum}.")
        normalized.append(number)
    return tuple(normalized)


def _non_negative_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")
    if value < 0:
        raise ValueError(f"{field_name} must be non-negative.")
    return value


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a finite number.")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise TypeError(f"{field_name} must be a finite number.") from exc
    if not isfinite(number):
        raise ValueError(f"{field_name} must be finite.")
    return number
