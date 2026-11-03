"""Immutable contracts for the Calibration-only first-shell experiment."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Literal

from .domain_analysis import FirstShellGeometryPolicy
from .first_shell_geometry_contracts import (
    FirstShellGraphSettings,
    FirstShellStratumIdentity,
    FirstShellSymmetry,
)
from .first_shell_suggestion import FirstShellSuggestionResult
from .pair_correlation import PairCorrelationResult
from .pair_correlation_aggregation import AggregatedPairCorrelationResult


FIRST_SHELL_ADAPTIVE_ALGORITHM_VERSION = "adaptive-gr-first-minimum-v1"
FIRST_SHELL_GEOMETRY_EXPERIMENT_SCHEMA_VERSION = "first-shell-geometry-experiment-v1"

FirstShellPolicyMode = Literal["fixed", "adaptive"]
FirstShellResolution = Literal["fixed_range", "adaptive_g_r", "fixed_fallback"]


@dataclass(frozen=True)
class FirstShellGeometryExperimentSettings:
    graph_settings: FirstShellGraphSettings
    fixed_r_min_nm: float
    fixed_r_max_nm: float
    gr_bin_width_nm: float
    gr_max_nm: float
    gr_min_expected_pair_exposure: float
    gr_min_contributing_frames: int
    gr_smoothing_width: float
    gr_peak_prominence: float
    gr_smoothing_method: str = "gaussian_bins"

    def __post_init__(self) -> None:
        if not isinstance(self.graph_settings, FirstShellGraphSettings):
            raise TypeError("graph_settings must be FirstShellGraphSettings.")
        minimum = _positive_float(self.fixed_r_min_nm, "fixed_r_min_nm")
        maximum = _positive_float(self.fixed_r_max_nm, "fixed_r_max_nm")
        if minimum >= maximum:
            raise ValueError("fixed_r_min_nm must be smaller than fixed_r_max_nm.")
        if (
            self.graph_settings.duplicate_detection_enabled
            and self.graph_settings.duplicate_max_distance_nm >= minimum
        ):
            raise ValueError(
                "Active duplicate detection requires duplicate_max_distance_nm "
                "to be smaller than fixed_r_min_nm."
            )
        bin_width = _positive_float(self.gr_bin_width_nm, "gr_bin_width_nm")
        gr_maximum = _positive_float(self.gr_max_nm, "gr_max_nm")
        if gr_maximum / bin_width > 100_000:
            raise ValueError("Pair-correlation bin count is too large.")
        minimum_frames = _positive_integer(
            self.gr_min_contributing_frames,
            "gr_min_contributing_frames",
        )
        smoothing_method = _text(self.gr_smoothing_method, "gr_smoothing_method")
        object.__setattr__(self, "fixed_r_min_nm", minimum)
        object.__setattr__(self, "fixed_r_max_nm", maximum)
        object.__setattr__(self, "gr_bin_width_nm", bin_width)
        object.__setattr__(self, "gr_max_nm", gr_maximum)
        object.__setattr__(
            self,
            "gr_min_expected_pair_exposure",
            _positive_float(
                self.gr_min_expected_pair_exposure,
                "gr_min_expected_pair_exposure",
            ),
        )
        object.__setattr__(self, "gr_min_contributing_frames", minimum_frames)
        object.__setattr__(
            self,
            "gr_smoothing_width",
            _positive_float(self.gr_smoothing_width, "gr_smoothing_width"),
        )
        object.__setattr__(
            self,
            "gr_peak_prominence",
            _non_negative_float(self.gr_peak_prominence, "gr_peak_prominence"),
        )
        object.__setattr__(self, "gr_smoothing_method", smoothing_method)


@dataclass(frozen=True)
class FirstShellPairCorrelationEvidence:
    dataset_version_id: str
    stratum: FirstShellStratumIdentity
    pair_correlation: PairCorrelationResult | AggregatedPairCorrelationResult | None
    unavailable_reason: str | None

    @classmethod
    def available(
        cls,
        dataset_version_id: str,
        measurement_group_id: str,
        symmetry_class: FirstShellSymmetry,
        pair_correlation: PairCorrelationResult | AggregatedPairCorrelationResult,
    ) -> FirstShellPairCorrelationEvidence:
        return cls(
            dataset_version_id,
            FirstShellStratumIdentity(measurement_group_id, symmetry_class),
            pair_correlation,
            None,
        )

    @classmethod
    def unavailable(
        cls,
        dataset_version_id: str,
        measurement_group_id: str,
        symmetry_class: FirstShellSymmetry,
        reason: str,
    ) -> FirstShellPairCorrelationEvidence:
        return cls(
            dataset_version_id,
            FirstShellStratumIdentity(measurement_group_id, symmetry_class),
            None,
            reason,
        )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "dataset_version_id",
            _text(self.dataset_version_id, "dataset_version_id"),
        )
        if not isinstance(self.stratum, FirstShellStratumIdentity):
            raise TypeError("stratum must be FirstShellStratumIdentity.")
        available = isinstance(
            self.pair_correlation,
            (PairCorrelationResult, AggregatedPairCorrelationResult),
        )
        if available == (self.unavailable_reason is not None):
            raise ValueError(
                "Pair-correlation evidence requires exactly one value or unavailable reason."
            )
        if self.unavailable_reason is not None:
            object.__setattr__(
                self,
                "unavailable_reason",
                _text(self.unavailable_reason, "unavailable_reason"),
            )

    @property
    def measurement_group_id(self) -> str:
        return self.stratum.measurement_group_id

    @property
    def symmetry_class(self) -> FirstShellSymmetry:
        return self.stratum.symmetry_class


@dataclass(frozen=True)
class FirstShellGeometryMetric:
    stratum: FirstShellStratumIdentity
    status: Literal["available", "unavailable"]
    reference_edge_count: int
    predicted_edge_count: int
    true_positive_edge_count: int
    precision: float | None
    recall: float | None
    f1_score: float | None
    unavailable_reason: str | None = None

    @property
    def measurement_group_id(self) -> str:
        return self.stratum.measurement_group_id

    @property
    def symmetry_class(self) -> FirstShellSymmetry:
        return self.stratum.symmetry_class


@dataclass(frozen=True)
class FirstShellGeometryDecision:
    stratum: FirstShellStratumIdentity
    resolution: FirstShellResolution
    resolved_r_min_nm: float
    resolved_r_max_nm: float
    fallback_reason: str | None
    evidence_fingerprint: str
    suggestion: FirstShellSuggestionResult | None = None

    @property
    def measurement_group_id(self) -> str:
        return self.stratum.measurement_group_id

    @property
    def symmetry_class(self) -> FirstShellSymmetry:
        return self.stratum.symmetry_class


@dataclass(frozen=True)
class FirstShellGeometryPolicyResult:
    policy: FirstShellGeometryPolicy
    decisions: tuple[FirstShellGeometryDecision, ...]
    metrics: tuple[FirstShellGeometryMetric, ...]
    result_fingerprint: str

    def decision(
        self,
        measurement_group_id: str,
        symmetry_class: FirstShellSymmetry,
    ) -> FirstShellGeometryDecision:
        return _find_identity(
            self.decisions,
            measurement_group_id,
            symmetry_class,
            "decision",
        )

    def metric(
        self,
        measurement_group_id: str,
        symmetry_class: FirstShellSymmetry,
    ) -> FirstShellGeometryMetric:
        return _find_identity(
            self.metrics,
            measurement_group_id,
            symmetry_class,
            "metric",
        )


@dataclass(frozen=True)
class FrozenFirstShellGeometrySelection:
    package_path: Path
    dataset_id: str
    dataset_version_id: str
    dataset_version_fingerprint: str
    validation_epoch_id: str
    graph_settings: FirstShellGraphSettings
    policy_result: FirstShellGeometryPolicyResult
    geometry_fingerprint: str
    validation_opened: bool = False

    @property
    def policy(self) -> FirstShellGeometryPolicy:
        return self.policy_result.policy

    def decision(
        self,
        measurement_group_id: str,
        symmetry_class: FirstShellSymmetry,
    ) -> FirstShellGeometryDecision:
        return self.policy_result.decision(measurement_group_id, symmetry_class)


@dataclass(frozen=True)
class FirstShellGeometryExperimentReport:
    package_path: Path
    dataset_id: str
    dataset_version_id: str
    dataset_version_fingerprint: str
    validation_epoch_id: str
    settings: FirstShellGeometryExperimentSettings
    policy_results: tuple[FirstShellGeometryPolicyResult, ...]
    experiment_fingerprint: str
    validation_opened: bool = False

    def result(self, mode: FirstShellPolicyMode) -> FirstShellGeometryPolicyResult:
        for value in self.policy_results:
            if value.policy.mode == mode:
                return value
        raise ValueError(f"Unknown first-shell policy: {mode!r}.")

    def freeze(
        self,
        mode: FirstShellPolicyMode,
    ) -> FrozenFirstShellGeometrySelection:
        from .first_shell_geometry import freeze_first_shell_geometry_policy

        return freeze_first_shell_geometry_policy(self, mode)


def _find_identity(values, group_id, symmetry_class, label):
    identity = FirstShellStratumIdentity(group_id, symmetry_class)
    for value in values:
        if value.stratum == identity:
            return value
    raise ValueError(f"Unknown first-shell {label}: {identity!r}.")


def _positive_integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")
    return value


def _positive_float(value: object, field_name: str) -> float:
    normalized = _finite_float(value, field_name)
    if normalized <= 0.0:
        raise ValueError(f"{field_name} must be positive.")
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


def _text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
    return value.strip()


__all__ = [
    "FIRST_SHELL_ADAPTIVE_ALGORITHM_VERSION",
    "FIRST_SHELL_GEOMETRY_EXPERIMENT_SCHEMA_VERSION",
    "FirstShellGraphSettings",
    "FirstShellGeometryDecision",
    "FirstShellGeometryExperimentReport",
    "FirstShellGeometryExperimentSettings",
    "FirstShellGeometryMetric",
    "FirstShellGeometryPolicyResult",
    "FirstShellPairCorrelationEvidence",
    "FirstShellPolicyMode",
    "FirstShellResolution",
    "FirstShellStratumIdentity",
    "FirstShellSymmetry",
    "FrozenFirstShellGeometrySelection",
]
