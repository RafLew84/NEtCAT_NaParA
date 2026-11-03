"""Shared execution driver for the bounded lattice-domain search plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar

from .lattice_domain_calibration_models import (
    LatticeDomainCalibrationSkippedVariant,
    LatticeDomainCalibrationStableRange,
    LatticeDomainCalibrationSweepSettings,
    LatticeDomainCalibrationVariant,
    LatticeDomainCalibrationVariantResult,
)
from .lattice_domain_calibration_search import (
    build_initial_variants,
    build_multivariate_variants,
    build_stability_variants,
)


_Payload = TypeVar("_Payload")


@dataclass(frozen=True)
class LatticeDomainBoundedEvaluation(Generic[_Payload]):
    result: LatticeDomainCalibrationVariantResult
    payload: _Payload


@dataclass(frozen=True)
class LatticeDomainStabilityAssessment:
    ranges: tuple[LatticeDomainCalibrationStableRange, ...]
    indeterminate_parameters: tuple[str, ...]
    minimum_local_stability_ari: float | None


@dataclass(frozen=True)
class LatticeDomainBoundedSearchResult(Generic[_Payload]):
    selected: LatticeDomainBoundedEvaluation[_Payload] | None
    diagnostic_best: LatticeDomainBoundedEvaluation[_Payload]
    candidates: tuple[LatticeDomainBoundedEvaluation[_Payload], ...]
    variant_results: tuple[LatticeDomainCalibrationVariantResult, ...]
    skipped_variants: tuple[LatticeDomainCalibrationSkippedVariant, ...]
    assessments: tuple[tuple[str, LatticeDomainStabilityAssessment], ...]

    def assessment_for(
        self,
        variant_id: str,
    ) -> LatticeDomainStabilityAssessment | None:
        return dict(self.assessments).get(variant_id)


@dataclass(frozen=True)
class _StabilitySearchOutcome(Generic[_Payload]):
    selected: LatticeDomainBoundedEvaluation[_Payload] | None
    results: tuple[LatticeDomainBoundedEvaluation[_Payload], ...]
    skipped: tuple[LatticeDomainCalibrationSkippedVariant, ...]
    assessments: tuple[tuple[str, LatticeDomainStabilityAssessment], ...]
    evaluated_count: int


BoundedEvaluator = Callable[
    [LatticeDomainCalibrationVariant, str, _Payload | None],
    LatticeDomainBoundedEvaluation[_Payload],
]
BoundedRanker = Callable[
    [tuple[LatticeDomainBoundedEvaluation[_Payload], ...]],
    tuple[LatticeDomainBoundedEvaluation[_Payload], ...],
]
StabilityAssessor = Callable[
    [
        LatticeDomainBoundedEvaluation[_Payload],
        tuple[LatticeDomainBoundedEvaluation[_Payload], ...],
        tuple[str, ...],
    ],
    LatticeDomainStabilityAssessment,
]
EligibilityGate = Callable[
    [LatticeDomainBoundedEvaluation[_Payload], LatticeDomainStabilityAssessment],
    bool,
]


def run_lattice_domain_bounded_search(
    sweep: LatticeDomainCalibrationSweepSettings,
    *,
    evaluator: BoundedEvaluator[_Payload],
    ranker: BoundedRanker[_Payload],
    stability_assessor: StabilityAssessor[_Payload],
    eligibility_gate: EligibilityGate[_Payload],
) -> LatticeDomainBoundedSearchResult[_Payload]:
    """Execute baseline, exploration, local stability, and refinement once."""

    initial, initial_skipped = build_initial_variants(sweep)
    candidates = list(_evaluate_variants(initial, "one_at_a_time", evaluator))
    variant_results = [value.result for value in candidates]
    skipped = list(initial_skipped)
    explored, exploration_skipped = _explore(sweep, tuple(candidates), evaluator)
    skipped.extend(exploration_skipped)
    candidates.extend(explored)
    variant_results.extend(value.result for value in explored)

    ranked = ranker(tuple(candidates))
    diagnostic_best = ranked[0]
    stable = _find_first_stable(
        sweep,
        ranked,
        max_candidates=sweep.max_stability_candidates,
        evaluator=evaluator,
        stability_assessor=stability_assessor,
        eligibility_gate=eligibility_gate,
    )
    variant_results.extend(value.result for value in stable.results)
    skipped.extend(stable.skipped)
    assessments = dict(stable.assessments)
    selected = stable.selected

    if selected is not None:
        selected, refined, refinement_results, refinement_skipped, refinement_assessments = _refine(
            sweep,
            selected,
            tuple(variant_results),
            explored_count=len(explored),
            stability_candidates_evaluated=stable.evaluated_count,
            evaluator=evaluator,
            ranker=ranker,
            stability_assessor=stability_assessor,
            eligibility_gate=eligibility_gate,
        )
        candidates.extend(refined)
        variant_results.extend(value.result for value in refined)
        variant_results.extend(value.result for value in refinement_results)
        skipped.extend(refinement_skipped)
        assessments.update(refinement_assessments)

    return LatticeDomainBoundedSearchResult(
        selected=selected,
        diagnostic_best=diagnostic_best,
        candidates=tuple(candidates),
        variant_results=tuple(variant_results),
        skipped_variants=tuple(skipped),
        assessments=tuple(sorted(assessments.items())),
    )


def _evaluate_variants(
    variants: tuple[LatticeDomainCalibrationVariant, ...],
    phase: str,
    evaluator: BoundedEvaluator[_Payload],
) -> tuple[LatticeDomainBoundedEvaluation[_Payload], ...]:
    return tuple(evaluator(variant, phase, None) for variant in variants)


def _explore(
    sweep: LatticeDomainCalibrationSweepSettings,
    initial: tuple[LatticeDomainBoundedEvaluation[_Payload], ...],
    evaluator: BoundedEvaluator[_Payload],
) -> tuple[
    tuple[LatticeDomainBoundedEvaluation[_Payload], ...],
    tuple[LatticeDomainCalibrationSkippedVariant, ...],
]:
    limit = (
        0
        if sweep.max_multivariate_variants == 0
        else max(1, (2 * sweep.max_multivariate_variants + 2) // 3)
    )
    variants, skipped = build_multivariate_variants(
        sweep,
        tuple(value.result for value in initial),
        max_variants=limit,
        variant_id_prefix="explore",
    )
    return _evaluate_variants(variants, "multivariate", evaluator), skipped


def _find_first_stable(
    sweep: LatticeDomainCalibrationSweepSettings,
    candidates: tuple[LatticeDomainBoundedEvaluation[_Payload], ...],
    *,
    max_candidates: int,
    evaluator: BoundedEvaluator[_Payload],
    stability_assessor: StabilityAssessor[_Payload],
    eligibility_gate: EligibilityGate[_Payload],
) -> _StabilitySearchOutcome[_Payload]:
    results: list[LatticeDomainBoundedEvaluation[_Payload]] = []
    skipped: list[LatticeDomainCalibrationSkippedVariant] = []
    assessments: dict[str, LatticeDomainStabilityAssessment] = {}
    selected: LatticeDomainBoundedEvaluation[_Payload] | None = None
    evaluated_count = 0
    for candidate in candidates[:max_candidates]:
        assessment, stability_results, stability_skipped = _assess_candidate(
            sweep,
            candidate,
            evaluator=evaluator,
            stability_assessor=stability_assessor,
        )
        evaluated_count += 1
        assessments[candidate.result.variant.variant_id] = assessment
        results.extend(stability_results)
        skipped.extend(stability_skipped)
        if eligibility_gate(candidate, assessment):
            selected = candidate
            break
    return _StabilitySearchOutcome(
        selected=selected,
        results=tuple(results),
        skipped=tuple(skipped),
        assessments=tuple(sorted(assessments.items())),
        evaluated_count=evaluated_count,
    )


def _refine(
    sweep: LatticeDomainCalibrationSweepSettings,
    selected: LatticeDomainBoundedEvaluation[_Payload],
    variant_results: tuple[LatticeDomainCalibrationVariantResult, ...],
    *,
    explored_count: int,
    stability_candidates_evaluated: int,
    evaluator: BoundedEvaluator[_Payload],
    ranker: BoundedRanker[_Payload],
    stability_assessor: StabilityAssessor[_Payload],
    eligibility_gate: EligibilityGate[_Payload],
) -> tuple[
    LatticeDomainBoundedEvaluation[_Payload],
    tuple[LatticeDomainBoundedEvaluation[_Payload], ...],
    tuple[LatticeDomainBoundedEvaluation[_Payload], ...],
    tuple[LatticeDomainCalibrationSkippedVariant, ...],
    tuple[tuple[str, LatticeDomainStabilityAssessment], ...],
]:
    remaining = sweep.max_multivariate_variants - explored_count
    if remaining <= 0:
        return selected, (), (), (), ()
    variants, skipped = build_multivariate_variants(
        sweep,
        variant_results,
        center_settings=selected.result.variant.settings,
        max_variants=remaining,
        variant_id_prefix=f"refine:{selected.result.variant.variant_id}",
    )
    refined = _evaluate_variants(variants, "multivariate", evaluator)
    better = tuple(
        value
        for value in ranker(refined)
        if value.result.score > selected.result.score
    )
    stable = _find_first_stable(
        sweep,
        better,
        max_candidates=max(
            0,
            sweep.max_stability_candidates - stability_candidates_evaluated,
        ),
        evaluator=evaluator,
        stability_assessor=stability_assessor,
        eligibility_gate=eligibility_gate,
    )
    return (
        stable.selected or selected,
        refined,
        stable.results,
        skipped + stable.skipped,
        stable.assessments,
    )


def _assess_candidate(
    sweep: LatticeDomainCalibrationSweepSettings,
    candidate: LatticeDomainBoundedEvaluation[_Payload],
    *,
    evaluator: BoundedEvaluator[_Payload],
    stability_assessor: StabilityAssessor[_Payload],
) -> tuple[
    LatticeDomainStabilityAssessment,
    tuple[LatticeDomainBoundedEvaluation[_Payload], ...],
    tuple[LatticeDomainCalibrationSkippedVariant, ...],
]:
    variants, skipped = build_stability_variants(
        candidate.result.variant,
        sweep.parameter_names,
    )
    results = tuple(
        evaluator(variant, "stability", candidate.payload)
        for variant in variants
    )
    return (
        stability_assessor(candidate, results, sweep.parameter_names),
        results,
        skipped,
    )


__all__ = [
    "LatticeDomainBoundedEvaluation",
    "LatticeDomainBoundedSearchResult",
    "LatticeDomainStabilityAssessment",
    "run_lattice_domain_bounded_search",
]
