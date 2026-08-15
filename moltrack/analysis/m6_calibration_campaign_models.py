"""Contracts for source-aligned M6 Calibration campaigns."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Callable, Literal

from .domain_analysis import DomainBackendIdentity, MoleculeDiagnosticStageId
from .lattice_domain_calibration_models import (
    LatticeDomainCalibrationSkippedVariant,
    LatticeDomainCalibrationVariant,
)
from .lattice_domain_validation import LatticeDomainPartitionLabels
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .first_shell_geometry_models import FrozenFirstShellGeometrySelection


M6MetricStatus = Literal["available", "unavailable"]


@dataclass(frozen=True)
class M6CalibrationObjective:
    """Predeclared constraints and loss weights for one campaign."""

    minimum_membership_precision: float
    minimum_local_stability_ari: float
    split_weight: float
    merge_weight: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "minimum_membership_precision",
            _unit_float(
                self.minimum_membership_precision,
                "minimum_membership_precision",
            ),
        )
        object.__setattr__(
            self,
            "minimum_local_stability_ari",
            _unit_float(
                self.minimum_local_stability_ari,
                "minimum_local_stability_ari",
            ),
        )
        object.__setattr__(
            self,
            "split_weight",
            _non_negative_float(self.split_weight, "split_weight"),
        )
        object.__setattr__(
            self,
            "merge_weight",
            _non_negative_float(self.merge_weight, "merge_weight"),
        )


@dataclass(frozen=True)
class M6CalibrationMetric:
    status: M6MetricStatus
    value: float | None
    reason: str | None = None

    @classmethod
    def available(cls, value: float | None) -> "M6CalibrationMetric":
        return cls("available", value)

    @classmethod
    def unavailable(cls, reason: str) -> "M6CalibrationMetric":
        return cls("unavailable", None, reason)

    def __post_init__(self) -> None:
        if self.status not in {"available", "unavailable"}:
            raise ValueError("Unsupported metric availability status.")
        if self.status == "available":
            if self.reason is not None:
                raise ValueError("An available metric cannot carry a reason.")
            if self.value is not None and not isfinite(float(self.value)):
                raise ValueError("An available metric value must be finite.")
        elif self.value is not None or not isinstance(self.reason, str) or not self.reason:
            raise ValueError("An unavailable metric requires a reason and no value.")


@dataclass(frozen=True)
class M6CalibrationReferenceGroup:
    dataset_version_id: str
    measurement_group_id: str
    reference_labels: LatticeDomainPartitionLabels
    reference_boundary_available: bool
    abstention_count: int = 0
    excluded_source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class M6CalibrationGroupPrediction:
    """Backend projection for one complete reference measurement group."""

    labels: LatticeDomainPartitionLabels
    failed_stage_ids: tuple[
        tuple[str, tuple[MoleculeDiagnosticStageId, ...]], ...
    ] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.labels, LatticeDomainPartitionLabels):
            raise TypeError("labels must be LatticeDomainPartitionLabels.")
        failures = tuple(
            (source_id, tuple(stage_ids))
            for source_id, stage_ids in self.failed_stage_ids
        )
        source_ids = tuple(value[0] for value in failures)
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("failed_stage_ids must contain unique source IDs.")
        if any(
            not isinstance(source_id, str)
            or not source_id
            or not stage_ids
            or any(not isinstance(stage_id, str) for stage_id in stage_ids)
            for source_id, stage_ids in failures
        ):
            raise ValueError("failed_stage_ids must contain non-empty traces.")
        object.__setattr__(self, "failed_stage_ids", failures)


M6CalibrationEvaluator = Callable[
    [
        M6CalibrationReferenceGroup,
        MolecularM6OrientationAnalysisSettings,
        FrozenFirstShellGeometrySelection,
    ],
    M6CalibrationGroupPrediction | LatticeDomainPartitionLabels,
]


@dataclass(frozen=True)
class M6CalibrationBackend:
    backend_identity: DomainBackendIdentity
    evaluator: M6CalibrationEvaluator

    def __post_init__(self) -> None:
        if not isinstance(self.backend_identity, DomainBackendIdentity):
            raise TypeError("backend_identity must be a DomainBackendIdentity.")
        if not callable(self.evaluator):
            raise TypeError("evaluator must be callable.")


@dataclass(frozen=True)
class M6CalibrationGroupMetrics:
    measurement_group_id: str
    evaluated_molecule_count: int
    abstention_count: int
    membership_true_positive_count: int
    membership_false_positive_count: int
    membership_false_negative_count: int
    membership_precision: float | None
    membership_recall: float | None
    adjusted_rand_index: float
    variation_of_information_nats: float
    correctly_assigned_molecule_fraction: float
    absolute_domain_count_error: int
    reference_domain_count: int
    split_count: int
    merge_count: int
    split_rate: float
    merge_rate: float
    boundary_true_positive_count: int | None
    boundary_false_positive_count: int | None
    boundary_false_negative_count: int | None
    boundary_precision: M6CalibrationMetric
    boundary_recall: M6CalibrationMetric
    funnel_misses: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class M6CalibrationAggregateMetrics:
    measurement_group_count: int
    evaluated_molecule_count: int
    abstention_count: int
    membership_true_positive_count: int
    membership_false_positive_count: int
    membership_false_negative_count: int
    macro_membership_precision: float | None
    macro_membership_recall: float | None
    micro_membership_precision: float | None
    micro_membership_recall: float | None
    macro_adjusted_rand_index: float
    macro_variation_of_information_nats: float
    macro_correctly_assigned_molecule_fraction: float
    macro_absolute_domain_count_error: float
    split_count: int
    merge_count: int
    macro_split_rate: float
    macro_merge_rate: float
    boundary_precision: M6CalibrationMetric
    boundary_recall: M6CalibrationMetric
    funnel_misses: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class M6CalibrationCandidateResult:
    variant: LatticeDomainCalibrationVariant
    metrics: M6CalibrationAggregateMetrics
    group_metrics: tuple[M6CalibrationGroupMetrics, ...]
    local_stability_ari: float | None
    objective_loss: float | None
    eligible: bool
    eligibility_failures: tuple[str, ...]


@dataclass(frozen=True)
class M6CalibrationBackendResult:
    backend_identity: DomainBackendIdentity
    ranked_candidates: tuple[M6CalibrationCandidateResult, ...]
    selected_candidate: M6CalibrationCandidateResult | None
    skipped_variants: tuple[LatticeDomainCalibrationSkippedVariant, ...]


@dataclass(frozen=True)
class M6CalibrationCampaignReport:
    package_path: Path
    dataset_id: str
    dataset_version_id: str
    dataset_version_fingerprint: str
    validation_epoch_id: str
    geometry_fingerprint: str
    objective: M6CalibrationObjective
    _backend_results: tuple[M6CalibrationBackendResult, ...]
    validation_opened: bool = False

    def backend_results_for(
        self,
        geometry: FrozenFirstShellGeometrySelection,
    ) -> tuple[M6CalibrationBackendResult, ...]:
        """Return search/shortlist results only for their frozen geometry."""

        self.require_geometry(geometry)
        return self._backend_results

    def require_geometry(
        self,
        geometry: FrozenFirstShellGeometrySelection,
    ) -> None:
        if not isinstance(geometry, FrozenFirstShellGeometrySelection):
            raise TypeError("geometry must be a FrozenFirstShellGeometrySelection.")
        if geometry.geometry_fingerprint != self.geometry_fingerprint:
            raise ValueError(
                "First-shell geometry fingerprint changed; campaign search and "
                "selection are invalidated."
            )


def _unit_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must lie between 0 and 1.")
    return normalized


def _non_negative_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative.")
    return normalized


def _finite_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric.")
    normalized = float(value)
    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")
    return normalized


__all__ = [
    "M6CalibrationAggregateMetrics",
    "M6CalibrationBackend",
    "M6CalibrationBackendResult",
    "M6CalibrationCampaignReport",
    "M6CalibrationCandidateResult",
    "M6CalibrationGroupMetrics",
    "M6CalibrationGroupPrediction",
    "M6CalibrationMetric",
    "M6CalibrationObjective",
    "M6CalibrationReferenceGroup",
]
