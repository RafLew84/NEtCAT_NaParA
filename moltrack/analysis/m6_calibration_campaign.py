"""Run one bounded, Calibration-only campaign for both M6 backends."""

from __future__ import annotations

from dataclasses import dataclass
from math import log
from pathlib import Path
from typing import TYPE_CHECKING

from .domain_analysis import (
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
)
from .lattice_domain_calibration_models import (
    LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPEC_BY_NAME,
    LatticeDomainCalibrationAggregateMetrics,
    LatticeDomainCalibrationStableRange,
    LatticeDomainCalibrationSweepSettings,
    LatticeDomainCalibrationVariant,
    LatticeDomainCalibrationVariantResult,
)
from .lattice_domain_bounded_search import (
    LatticeDomainBoundedEvaluation,
    LatticeDomainStabilityAssessment,
    run_lattice_domain_bounded_search,
)
from .m6_calibration_campaign_models import (
    M6CalibrationAggregateMetrics,
    M6CalibrationBackend,
    M6CalibrationBackendResult,
    M6CalibrationCampaignReport,
    M6CalibrationCandidateResult,
    M6CalibrationGroupMetrics,
    M6CalibrationGroupPrediction,
    M6CalibrationObjective,
    M6CalibrationReferenceGroup,
)
from .m6_calibration_metrics import (
    evaluate_m6_calibration_groups,
    m6_calibration_objective_loss,
    m6_local_partition_stability,
    normalize_m6_calibration_prediction,
)
from .first_shell_geometry_models import FrozenFirstShellGeometrySelection

if TYPE_CHECKING:
    from moltrack.persistence.m6_calibration_reference import (
        M6CalibrationReference,
    )


_BACKEND_IDS = {
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
}
@dataclass(frozen=True)
class _EvaluatedVariant:
    variant: LatticeDomainCalibrationVariant
    metrics: M6CalibrationAggregateMetrics
    group_metrics: tuple[M6CalibrationGroupMetrics, ...]
    predictions: tuple[M6CalibrationGroupPrediction, ...]
    objective_loss: float | None
    local_stability_ari: float | None = None


def run_lattice_domain_calibration_campaign(
    package_path: str | Path,
    sweep: LatticeDomainCalibrationSweepSettings,
    objective: M6CalibrationObjective,
    *,
    geometry: FrozenFirstShellGeometrySelection,
    backends: tuple[M6CalibrationBackend, ...],
) -> M6CalibrationCampaignReport:
    """Evaluate both backends against one verified, unopened Calibration split."""

    if not isinstance(sweep, LatticeDomainCalibrationSweepSettings):
        raise TypeError("sweep must be LatticeDomainCalibrationSweepSettings.")
    if not isinstance(objective, M6CalibrationObjective):
        raise TypeError("objective must be M6CalibrationObjective.")
    if not isinstance(geometry, FrozenFirstShellGeometrySelection):
        raise TypeError("geometry must be a FrozenFirstShellGeometrySelection.")
    backends = tuple(backends)
    if any(not isinstance(value, M6CalibrationBackend) for value in backends):
        raise TypeError("backends must contain M6CalibrationBackend values.")
    backend_ids = tuple(value.backend_identity.backend_id for value in backends)
    if len(backend_ids) != 2 or set(backend_ids) != _BACKEND_IDS:
        raise ValueError("An M6 campaign requires both stable domain backend IDs.")
    from moltrack.persistence.m6_calibration_reference import (
        load_m6_calibration_reference,
    )

    reference = load_m6_calibration_reference(package_path)
    _validate_geometry(reference, sweep, geometry)
    results = tuple(
        _run_backend(reference, sweep, objective, geometry, backend)
        for backend in sorted(
            backends,
            key=lambda value: value.backend_identity.backend_id,
        )
    )
    return M6CalibrationCampaignReport(
        package_path=reference.package_path,
        dataset_id=reference.dataset_id,
        dataset_version_id=reference.version_id,
        dataset_version_fingerprint=reference.version_fingerprint,
        validation_epoch_id=reference.validation_epoch_id,
        geometry_fingerprint=geometry.geometry_fingerprint,
        objective=objective,
        sweep=sweep,
        _backend_results=results,
    )


def _run_backend(
    reference: M6CalibrationReference,
    sweep: LatticeDomainCalibrationSweepSettings,
    objective: M6CalibrationObjective,
    geometry: FrozenFirstShellGeometrySelection,
    backend: M6CalibrationBackend,
) -> M6CalibrationBackendResult:
    adapter = _CampaignSearchAdapter(reference, sweep, objective, geometry, backend)
    search = run_lattice_domain_bounded_search(
        sweep,
        evaluator=adapter.evaluate,
        ranker=adapter.rank,
        stability_assessor=adapter.assess_stability,
        eligibility_gate=adapter.is_eligible,
    )

    def candidate_stability(variant_id: str) -> float | None:
        assessment = search.assessment_for(variant_id)
        return (
            None
            if assessment is None
            else assessment.minimum_local_stability_ari
        )

    candidates = tuple(
        _candidate_result(
            value.payload,
            candidate_stability(value.result.variant.variant_id),
            objective,
        )
        for value in search.candidates
    )
    ranked = tuple(
        sorted(candidates, key=lambda value: _candidate_sort_key(value, sweep))
    )
    selected = next((value for value in ranked if value.eligible), None)
    return M6CalibrationBackendResult(
        backend_identity=backend.backend_identity,
        ranked_candidates=ranked,
        selected_candidate=selected,
        skipped_variants=search.skipped_variants,
    )


@dataclass(frozen=True)
class _CampaignSearchAdapter:
    reference: M6CalibrationReference
    sweep: LatticeDomainCalibrationSweepSettings
    objective: M6CalibrationObjective
    geometry: FrozenFirstShellGeometrySelection
    backend: M6CalibrationBackend

    def evaluate(
        self,
        variant,
        _phase,
        stability_reference,
    ):
        value = _evaluate_variant(
            variant,
            self.reference.groups,
            self.backend,
            self.geometry,
            self.objective,
            stability_reference=(
                None
                if stability_reference is None
                else stability_reference.predictions
            ),
        )
        return LatticeDomainBoundedEvaluation(_search_result(value), value)

    def rank(self, values):
        return tuple(sorted(
            values,
            key=lambda value: _preliminary_sort_key(
                value.payload,
                self.objective,
                self.sweep,
            ),
        ))

    def assess_stability(
        self,
        candidate,
        results,
        parameter_names,
    ) -> LatticeDomainStabilityAssessment:
        ranges = []
        indeterminate = []
        stability_values: list[float] = []
        for parameter_name in parameter_names:
            parameter_results = tuple(
                value
                for value in results
                if value.result.variant.changed_parameters == (parameter_name,)
            )
            accepted = tuple(
                value
                for value in parameter_results
                if value.payload.local_stability_ari is not None
                and value.payload.local_stability_ari
                >= self.objective.minimum_local_stability_ari
            )
            stability_values.extend(
                float(value.payload.local_stability_ari)
                for value in parameter_results
                if value.payload.local_stability_ari is not None
            )
            if not parameter_results or len(accepted) != len(parameter_results):
                indeterminate.append(parameter_name)
                continue
            settings_values = (
                getattr(candidate.result.variant.settings, parameter_name),
                *(
                    getattr(value.result.variant.settings, parameter_name)
                    for value in accepted
                ),
            )
            ranges.append(LatticeDomainCalibrationStableRange(
                parameter_name=parameter_name,
                minimum_value=min(settings_values),
                maximum_value=max(settings_values),
                accepted_variant_ids=tuple(
                    value.result.variant.variant_id for value in accepted
                ),
            ))
        return LatticeDomainStabilityAssessment(
            ranges=tuple(ranges),
            indeterminate_parameters=tuple(indeterminate),
            minimum_local_stability_ari=(
                min(stability_values) if stability_values else None
            ),
        )

    def is_eligible(self, candidate, assessment) -> bool:
        return not _eligibility_failures(
            candidate.payload,
            assessment.minimum_local_stability_ari,
            self.objective,
        )


def _evaluate_variant(
    variant: LatticeDomainCalibrationVariant,
    groups: tuple[M6CalibrationReferenceGroup, ...],
    backend: M6CalibrationBackend,
    geometry: FrozenFirstShellGeometrySelection,
    objective: M6CalibrationObjective,
    *,
    stability_reference: tuple[M6CalibrationGroupPrediction, ...] | None,
) -> _EvaluatedVariant:
    predictions = tuple(
        normalize_m6_calibration_prediction(
            backend.evaluator(group, variant.settings, geometry)
        )
        for group in groups
    )
    metrics, group_metrics = evaluate_m6_calibration_groups(
        groups,
        predictions,
        explicit_boundary=(
            "explicit_boundary" in backend.backend_identity.capabilities
        ),
    )
    local_stability = (
        None
        if stability_reference is None
        else min(
            _mean(
                m6_local_partition_stability(
                    baseline,
                    changed,
                    group.excluded_source_ids,
                )
                for group, baseline, changed in zip(
                    groups,
                    stability_reference,
                    predictions,
                )
            ),
            1.0,
        )
    )
    return _EvaluatedVariant(
        variant=variant,
        metrics=metrics,
        group_metrics=group_metrics,
        predictions=predictions,
        objective_loss=m6_calibration_objective_loss(metrics, objective),
        local_stability_ari=local_stability,
    )


def _validate_geometry(
    reference: M6CalibrationReference,
    sweep: LatticeDomainCalibrationSweepSettings,
    geometry: FrozenFirstShellGeometrySelection,
) -> None:
    if (
        geometry.dataset_id != reference.dataset_id
        or geometry.dataset_version_id != reference.version_id
        or geometry.dataset_version_fingerprint != reference.version_fingerprint
        or geometry.validation_epoch_id != reference.validation_epoch_id
    ):
        raise ValueError("Frozen first-shell geometry does not match the M6 reference.")
    reference_groups = {value.measurement_group_id for value in reference.groups}
    geometry_groups = {
        value.measurement_group_id
        for value in geometry.policy_result.decisions
    }
    if geometry_groups != reference_groups:
        raise ValueError("Frozen first-shell geometry does not cover Calibration groups.")
    baseline = sweep.baseline_settings
    policy = geometry.policy
    if (
        baseline.first_shell_r_min_nm != policy.fixed_r_min_nm
        or baseline.first_shell_r_max_nm != policy.fixed_r_max_nm
    ):
        raise ValueError(
            "Classification sweep first-shell radii must match the frozen fixed fallback."
        )
    graph = geometry.graph_settings
    if (
        baseline.duplicate_detection_enabled != graph.duplicate_detection_enabled
        or baseline.duplicate_max_distance_nm != graph.duplicate_max_distance_nm
        or baseline.geometry_absolute_tolerance_nm
        != graph.geometry_absolute_tolerance_nm
        or baseline.geometry_relative_tolerance != graph.geometry_relative_tolerance
    ):
        raise ValueError(
            "Classification sweep graph settings must match the frozen geometry."
        )


def _candidate_result(
    value: _EvaluatedVariant,
    stability: float | None,
    objective: M6CalibrationObjective,
) -> M6CalibrationCandidateResult:
    failures = _eligibility_failures(value, stability, objective)
    return M6CalibrationCandidateResult(
        variant=value.variant,
        metrics=value.metrics,
        group_metrics=value.group_metrics,
        local_stability_ari=stability,
        objective_loss=value.objective_loss,
        eligible=not failures,
        eligibility_failures=failures,
    )


def _eligibility_failures(
    value: _EvaluatedVariant,
    stability: float | None,
    objective: M6CalibrationObjective,
) -> tuple[str, ...]:
    failures = []
    precision = value.metrics.macro_membership_precision
    if precision is None:
        failures.append("precision_unavailable")
    elif precision < objective.minimum_membership_precision:
        failures.append("precision_below_constraint")
    if stability is None:
        failures.append("local_stability_unavailable")
    elif stability < objective.minimum_local_stability_ari:
        failures.append("local_stability_below_constraint")
    if value.objective_loss is None:
        failures.append("membership_recall_unavailable")
    return tuple(failures)


def _search_result(value: _EvaluatedVariant) -> LatticeDomainCalibrationVariantResult:
    metrics = value.metrics
    return LatticeDomainCalibrationVariantResult(
        variant=value.variant,
        metrics=LatticeDomainCalibrationAggregateMetrics(
            frame_count=metrics.measurement_group_count,
            evaluated_molecule_count=metrics.evaluated_molecule_count,
            mean_adjusted_rand_index=metrics.macro_adjusted_rand_index,
            mean_variation_of_information_nats=(
                metrics.macro_variation_of_information_nats
            ),
            mean_absolute_domain_count_error=(
                metrics.macro_absolute_domain_count_error
            ),
            mean_correctly_assigned_molecule_fraction=(
                metrics.macro_correctly_assigned_molecule_fraction
            ),
            boundary_precision=metrics.boundary_precision.value,
            boundary_recall=metrics.boundary_recall.value,
            mean_confidence_brier_score=None,
            mean_confidence_expected_calibration_error=None,
            mean_partition_stability_ari=value.local_stability_ari,
            over_segmentation_count=metrics.split_count,
            under_segmentation_count=metrics.merge_count,
        ),
        score=(
            float("-inf")
            if value.objective_loss is None
            else -value.objective_loss
        ),
    )


def _preliminary_sort_key(
    value: _EvaluatedVariant,
    objective: M6CalibrationObjective,
    sweep: LatticeDomainCalibrationSweepSettings,
) -> tuple[object, ...]:
    precision = value.metrics.macro_membership_precision
    return _campaign_sort_key(
        constraint_failed=(
            precision is None
            or precision < objective.minimum_membership_precision
        ),
        objective_loss=value.objective_loss,
        metrics=value.metrics,
        variant=value.variant,
        sweep=sweep,
    )


def _candidate_sort_key(
    value: M6CalibrationCandidateResult,
    sweep: LatticeDomainCalibrationSweepSettings,
) -> tuple[object, ...]:
    return _campaign_sort_key(
        constraint_failed=not value.eligible,
        objective_loss=value.objective_loss,
        metrics=value.metrics,
        variant=value.variant,
        sweep=sweep,
    )


def _campaign_sort_key(
    *,
    constraint_failed: bool,
    objective_loss: float | None,
    metrics: M6CalibrationAggregateMetrics,
    variant: LatticeDomainCalibrationVariant,
    sweep: LatticeDomainCalibrationSweepSettings,
) -> tuple[object, ...]:
    return (
        constraint_failed,
        objective_loss is None,
        objective_loss or 0.0,
        -metrics.macro_adjusted_rand_index,
        metrics.macro_variation_of_information_nats,
        metrics.macro_absolute_domain_count_error,
        _normalized_settings_distance(variant, sweep),
        variant.variant_id,
    )


def _normalized_settings_distance(
    variant: LatticeDomainCalibrationVariant,
    sweep: LatticeDomainCalibrationSweepSettings,
) -> float:
    distance = 0.0
    for parameter_name in sweep.parameter_names:
        baseline = float(getattr(sweep.baseline_settings, parameter_name))
        candidate = float(getattr(variant.settings, parameter_name))
        spec = LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPEC_BY_NAME[parameter_name]
        if spec.kind == "positive_log":
            distance += abs(log(candidate / baseline) / log(spec.step))
        else:
            distance += abs(candidate - baseline) / spec.step
    return distance


def _mean(values) -> float:
    items = tuple(values)
    if not items:
        raise ValueError("At least one metric value is required.")
    return sum(items) / len(items)


__all__ = ["run_lattice_domain_calibration_campaign"]
