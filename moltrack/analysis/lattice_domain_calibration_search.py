"""Deterministic bounded-search planning for M3/M6 calibration."""

from __future__ import annotations

from dataclasses import replace
from itertools import combinations, product
from typing import Literal

from .lattice_domain_calibration_models import (
    LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPECS,
    LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPEC_BY_NAME,
    LATTICE_DOMAIN_CALIBRATION_PRIORITY_INTERACTIONS,
    LatticeDomainCalibrationSkippedVariant,
    LatticeDomainCalibrationStableRange,
    LatticeDomainCalibrationSweepSettings,
    LatticeDomainCalibrationVariant,
    LatticeDomainCalibrationVariantResult,
)
from .m6_settings import MolecularM6OrientationAnalysisSettings


def build_initial_variants(
    sweep: LatticeDomainCalibrationSweepSettings,
) -> tuple[
    tuple[LatticeDomainCalibrationVariant, ...],
    tuple[LatticeDomainCalibrationSkippedVariant, ...],
]:
    if not isinstance(sweep, LatticeDomainCalibrationSweepSettings):
        raise TypeError("sweep must be lattice-domain calibration settings.")
    baseline = sweep.baseline_settings
    variants = [
        LatticeDomainCalibrationVariant(
            variant_id="baseline",
            phase="baseline",
            settings=baseline,
            changed_parameters=(),
        )
    ]
    perturbations, skipped = _build_local_perturbation_variants(
        baseline,
        sweep.parameter_names,
        phase="one_at_a_time",
        id_prefix="",
    )
    variants.extend(perturbations)
    return tuple(variants), skipped


def build_multivariate_variants(
    sweep: LatticeDomainCalibrationSweepSettings,
    results: tuple[LatticeDomainCalibrationVariantResult, ...],
    *,
    center_settings: MolecularM6OrientationAnalysisSettings | None = None,
    max_variants: int | None = None,
    variant_id_prefix: str = "multi",
) -> tuple[
    tuple[LatticeDomainCalibrationVariant, ...],
    tuple[LatticeDomainCalibrationSkippedVariant, ...],
]:
    limit = (
        sweep.max_multivariate_variants
        if max_variants is None
        else int(max_variants)
    )
    if limit <= 0:
        return (), ()
    center = sweep.baseline_settings if center_settings is None else center_settings
    if not isinstance(center, MolecularM6OrientationAnalysisSettings):
        raise TypeError("center_settings must be M6 settings.")
    values_by_parameter = {}
    skipped = []
    for parameter_name in sweep.parameter_names:
        ranked_directions = tuple(
            sorted(
                (
                    value
                    for value in results
                    if value.variant.phase == "one_at_a_time"
                    and value.variant.changed_parameters == (parameter_name,)
                ),
                key=lambda value: (-value.score, value.variant.variant_id),
            )
        )
        candidates = []
        candidate_settings = set()
        for result in ranked_directions:
            direction = result.variant.variant_id.rsplit(":", 1)[-1]
            variant_id = (
                f"{variant_id_prefix}:center:{parameter_name}:{direction}"
            )
            try:
                settings = _perturb_settings(
                    center,
                    parameter_name,
                    direction,
                )
            except ValueError as exc:
                skipped.append(
                    LatticeDomainCalibrationSkippedVariant(
                        variant_id=variant_id,
                        changed_parameters=(parameter_name,),
                        reason=str(exc),
                    )
                )
                continue
            if settings == center or settings in candidate_settings:
                skipped.append(
                    LatticeDomainCalibrationSkippedVariant(
                        variant_id=variant_id,
                        changed_parameters=(parameter_name,),
                        reason=(
                            "Perturbation duplicates the center or another "
                            "local direction."
                        ),
                    )
                )
                continue
            candidate_settings.add(settings)
            candidates.append(
                LatticeDomainCalibrationVariant(
                    variant_id=variant_id,
                    phase="one_at_a_time",
                    settings=settings,
                    changed_parameters=(parameter_name,),
                )
            )
        if candidates:
            values_by_parameter[parameter_name] = tuple(candidates)
    interaction_names = tuple(
        spec.name
        for spec in LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPECS
        if spec.include_in_multivariate and spec.name in values_by_parameter
    )
    variants = []
    seen = {value.variant.settings for value in results}
    groups, priority_group_count = _ordered_interaction_groups(interaction_names)
    choices_by_group = tuple(
        (
            names,
            _diverse_interaction_choices(
                tuple(values_by_parameter[name] for name in names)
            ),
        )
        for names in groups
    )
    batches = (
        choices_by_group[:priority_group_count],
        choices_by_group[priority_group_count:],
    )
    for batch in batches:
        maximum_choice_count = max(
            (len(choices) for _names, choices in batch),
            default=0,
        )
        for choice_index in range(maximum_choice_count):
            for names, choices in batch:
                if choice_index >= len(choices):
                    continue
                selected = choices[choice_index]
                directions = tuple(
                    value.variant_id.rsplit(":", 1)[-1]
                    for value in selected
                )
                variant_id = f"{variant_id_prefix}:" + "+".join(
                    f"{name}={direction}"
                    for name, direction in zip(names, directions)
                )
                try:
                    updates = {
                        name: getattr(value.settings, name)
                        for name, value in zip(names, selected)
                    }
                    settings = replace(center, **updates)
                except ValueError as exc:
                    skipped.append(
                        LatticeDomainCalibrationSkippedVariant(
                            variant_id=variant_id,
                            changed_parameters=names,
                            reason=str(exc),
                        )
                    )
                    continue
                if settings in seen:
                    continue
                seen.add(settings)
                variants.append(
                    LatticeDomainCalibrationVariant(
                        variant_id=variant_id,
                        phase="multivariate",
                        settings=settings,
                        changed_parameters=tuple(
                            parameter_name
                            for parameter_name in sweep.parameter_names
                            if getattr(settings, parameter_name)
                            != getattr(
                                sweep.baseline_settings,
                                parameter_name,
                            )
                        ),
                    )
                )
                if len(variants) >= limit:
                    return tuple(variants), tuple(skipped)
    return tuple(variants), tuple(skipped)


def build_stability_variants(
    best: LatticeDomainCalibrationVariant,
    parameter_names: tuple[str, ...],
) -> tuple[
    tuple[LatticeDomainCalibrationVariant, ...],
    tuple[LatticeDomainCalibrationSkippedVariant, ...],
]:
    return _build_local_perturbation_variants(
        best.settings,
        parameter_names,
        phase="stability",
        id_prefix=f"stability:{best.variant_id}:",
    )


def rank_variants(
    results: tuple[LatticeDomainCalibrationVariantResult, ...],
) -> tuple[LatticeDomainCalibrationVariantResult, ...]:
    return tuple(
        sorted(
            results,
            key=lambda value: (
                -value.score,
                len(value.variant.changed_parameters),
                value.variant.variant_id,
            ),
        )
    )


def stability_ranges_around_best(
    best: LatticeDomainCalibrationVariantResult,
    stability_results: tuple[LatticeDomainCalibrationVariantResult, ...],
    *,
    parameter_names: tuple[str, ...],
    minimum_ari: float,
) -> tuple[
    tuple[LatticeDomainCalibrationStableRange, ...],
    tuple[str, ...],
]:
    ranges = []
    indeterminate = []
    for parameter_name in parameter_names:
        candidates = tuple(
            value
            for value in stability_results
            if value.variant.changed_parameters == (parameter_name,)
        )
        accepted = tuple(
            value
            for value in candidates
            if value.metrics.mean_adjusted_rand_index >= minimum_ari
            and value.metrics.mean_partition_stability_ari is not None
            and value.metrics.mean_partition_stability_ari >= minimum_ari
        )
        if not candidates or len(accepted) != len(candidates):
            indeterminate.append(parameter_name)
            continue
        values = (
            (getattr(best.variant.settings, parameter_name), best.variant.variant_id),
            *(
                (
                    getattr(value.variant.settings, parameter_name),
                    value.variant.variant_id,
                )
                for value in accepted
            ),
        )
        ranges.append(
            LatticeDomainCalibrationStableRange(
                parameter_name=parameter_name,
                minimum_value=min(value for value, _variant_id in values),
                maximum_value=max(value for value, _variant_id in values),
                accepted_variant_ids=tuple(
                    variant_id
                    for _value, variant_id in sorted(
                        values,
                        key=lambda item: (item[0], item[1]),
                    )
                ),
            )
        )
    return tuple(ranges), tuple(indeterminate)


def _ordered_interaction_groups(
    parameter_names: tuple[str, ...],
) -> tuple[tuple[tuple[str, ...], ...], int]:
    available = set(parameter_names)
    groups = [
        names
        for names in LATTICE_DOMAIN_CALIBRATION_PRIORITY_INTERACTIONS
        if set(names).issubset(available)
    ]
    priority_group_count = len(groups)
    seen = {frozenset(names) for names in groups}
    for width in (2, 3, 4):
        for names in combinations(parameter_names, width):
            key = frozenset(names)
            if key not in seen:
                groups.append(names)
                seen.add(key)
    return tuple(groups), priority_group_count


def _diverse_interaction_choices(
    choices: tuple[tuple[LatticeDomainCalibrationVariant, ...], ...],
) -> tuple[tuple[LatticeDomainCalibrationVariant, ...], ...]:
    indexed = tuple(
        (indices, selected)
        for indices, selected in (
            (
                indices,
                tuple(
                    choices[position][choice_index]
                    for position, choice_index in enumerate(indices)
                ),
            )
            for indices in product(*(range(len(values)) for values in choices))
        )
    )
    return tuple(
        selected
        for _indices, selected in sorted(
            indexed,
            key=lambda value: (
                0 if len(set(value[0])) == 1 else 1,
                max(value[0]),
                value[0],
            ),
        )
    )


def _build_local_perturbation_variants(
    center: MolecularM6OrientationAnalysisSettings,
    parameter_names: tuple[str, ...],
    *,
    phase: Literal["one_at_a_time", "stability"],
    id_prefix: str,
) -> tuple[
    tuple[LatticeDomainCalibrationVariant, ...],
    tuple[LatticeDomainCalibrationSkippedVariant, ...],
]:
    variants = []
    skipped = []
    seen = {center}
    for parameter_name in parameter_names:
        for direction in ("low", "high"):
            variant_id = f"{id_prefix}{parameter_name}:{direction}"
            try:
                settings = _perturb_settings(center, parameter_name, direction)
            except ValueError as exc:
                skipped.append(
                    LatticeDomainCalibrationSkippedVariant(
                        variant_id=variant_id,
                        changed_parameters=(parameter_name,),
                        reason=str(exc),
                    )
                )
                continue
            if settings in seen:
                skipped.append(
                    LatticeDomainCalibrationSkippedVariant(
                        variant_id=variant_id,
                        changed_parameters=(parameter_name,),
                        reason=(
                            "Perturbation duplicates the center or another "
                            "evaluated setting."
                        ),
                    )
                )
                continue
            seen.add(settings)
            variants.append(
                LatticeDomainCalibrationVariant(
                    variant_id=variant_id,
                    phase=phase,
                    settings=settings,
                    changed_parameters=(parameter_name,),
                )
            )
    return tuple(variants), tuple(skipped)


def _perturb_settings(
    baseline: MolecularM6OrientationAnalysisSettings,
    parameter_name: str,
    direction: str,
) -> MolecularM6OrientationAnalysisSettings:
    spec = LATTICE_DOMAIN_CALIBRATION_PARAMETER_SPEC_BY_NAME[parameter_name]
    value = getattr(baseline, parameter_name)
    if spec.kind == "positive_log":
        changed = value / spec.step if direction == "low" else value * spec.step
    else:
        sign = -1 if direction == "low" else 1
        changed = value + sign * spec.step
    if spec.kind == "unit_interval":
        changed = min(1.0, max(0.0, float(changed)))
    elif spec.kind == "angle_deg":
        changed = min(30.0, max(0.0, float(changed)))
    elif spec.kind == "nonnegative":
        changed = max(0.0, float(changed))
    elif spec.kind == "positive_integer":
        changed = max(1, int(changed))
    elif spec.kind == "positive_log":
        changed = max(float(changed), 1e-15)
    return replace(baseline, **{parameter_name: changed})
