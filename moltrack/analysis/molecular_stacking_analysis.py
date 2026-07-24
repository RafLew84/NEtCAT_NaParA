"""Local stacking classification and orientational subdomain segmentation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .lattice_row_models import (
    LatticeDomainRowAssignment,
    lattice_row_assignment_analysis_fingerprint,
)
from .molecular_orientation_models import MolecularOrientationMeasurement
from .molecular_orientation_prototype_models import (
    MolecularOrientationAxisEvidence,
    MolecularOrientationFrameData,
    MolecularOrientationPatternMode,
    MolecularOrientationPatternPhase,
    MolecularOrientationPrototype,
    MolecularOrientationPrototypeAnalysis,
    MolecularOrientationStateAssignment,
    molecular_orientation_prototype_analysis_fingerprint,
)
from .molecular_stacking_models import (
    MolecularStackingAnalysis,
    MolecularStackingSettings,
    OrientationalSubdomain,
    StackingOrder,
    StackingQCReason,
    molecular_stacking_settings_fingerprint,
)

_MODES: tuple[MolecularOrientationPatternMode, ...] = (
    "along_rows",
    "between_rows",
    "checkerboard",
)


@dataclass(frozen=True)
class _LocalLabel:
    source_id: str
    mode: MolecularOrientationPatternMode
    phase: MolecularOrientationPatternPhase
    score: float
    confidence: float


@dataclass(frozen=True)
class _Component:
    mode: MolecularOrientationPatternMode
    phase: MolecularOrientationPatternPhase
    source_ids: tuple[str, ...]
    score: float
    confidence: float


@dataclass(frozen=True)
class _AxisEvaluation:
    evidence: MolecularOrientationAxisEvidence
    components: tuple[_Component, ...]
    ordered_source_ids: tuple[str, ...]
    ordered_fraction: float
    score: float
    selection_score: float


def analyze_molecular_stacking(
    frames: tuple[MolecularOrientationFrameData, ...],
    prototype_analysis: MolecularOrientationPrototypeAnalysis,
    *,
    settings: MolecularStackingSettings | None = None,
) -> MolecularStackingAnalysis:
    """Classify stacking without rerunning orientation estimation."""

    frame_data = _validated_frames(frames)
    if not isinstance(
        prototype_analysis,
        MolecularOrientationPrototypeAnalysis,
    ):
        raise TypeError(
            "prototype_analysis must be MolecularOrientationPrototypeAnalysis."
        )
    if settings is None:
        settings = MolecularStackingSettings()
    if not isinstance(settings, MolecularStackingSettings):
        raise TypeError("settings must be MolecularStackingSettings.")
    _validate_dependencies(frame_data, prototype_analysis)

    measurement_by_id = {
        measurement.measurement_id: measurement
        for frame in frame_data
        for measurement in frame.measurements
    }
    evidence_by_domain: dict[
        tuple[int, str],
        list[MolecularOrientationAxisEvidence],
    ] = {}
    for evidence in prototype_analysis.axis_evidence:
        evidence_by_domain.setdefault(
            (evidence.frame_index, evidence.lattice_domain_id),
            [],
        ).append(evidence)

    orders = []
    subdomains = []
    for frame in frame_data:
        for domain in frame.row_assignment.domain_assignments:
            key = (frame.frame_index, domain.lattice_domain_id)
            if prototype_analysis.status == "one_state":
                order, children = _uniform_order(
                    frame.frame_index,
                    domain,
                    prototype=prototype_analysis.prototypes[0],
                    measurement_by_id=measurement_by_id,
                    settings=settings,
                )
            elif prototype_analysis.status == "two_state":
                order, children = _two_state_order(
                    frame.frame_index,
                    domain,
                    evidence=tuple(
                        sorted(
                            evidence_by_domain.get(key, ()),
                            key=lambda value: value.candidate_index,
                        )
                    ),
                    prototype_a=prototype_analysis.prototype_for_state("A"),
                    prototype_b=prototype_analysis.prototype_for_state("B"),
                    settings=settings,
                )
            else:
                order = _unavailable_order(
                    frame.frame_index,
                    domain,
                    reason="prototype_states_unavailable",
                )
                children = ()
            orders.append(order)
            subdomains.extend(children)

    return MolecularStackingAnalysis(
        orders=tuple(
            sorted(
                orders,
                key=lambda value: (
                    value.frame_index,
                    value.lattice_domain_id,
                ),
            )
        ),
        subdomains=tuple(
            sorted(
                subdomains,
                key=lambda value: (
                    value.frame_index,
                    value.parent_lattice_domain_id,
                    value.subdomain_id,
                ),
            )
        ),
        input_frame_indices=tuple(
            value.frame_index for value in frame_data
        ),
        source_file_sha256=prototype_analysis.source_file_sha256,
        source_view=prototype_analysis.source_view,
        prototype_analysis_fingerprint=(
            molecular_orientation_prototype_analysis_fingerprint(
                prototype_analysis
            )
        ),
        row_assignment_fingerprints=tuple(
            (
                value.frame_index,
                lattice_row_assignment_analysis_fingerprint(
                    value.row_assignment
                ),
            )
            for value in frame_data
        ),
        settings=settings,
        settings_fingerprint=molecular_stacking_settings_fingerprint(
            settings
        ),
    )


def _validated_frames(
    frames: tuple[MolecularOrientationFrameData, ...],
) -> tuple[MolecularOrientationFrameData, ...]:
    normalized = tuple(frames)
    if not normalized:
        raise ValueError("At least one orientation frame is required.")
    if any(
        not isinstance(value, MolecularOrientationFrameData)
        for value in normalized
    ):
        raise TypeError(
            "frames must contain MolecularOrientationFrameData."
        )
    normalized = tuple(
        sorted(normalized, key=lambda value: value.frame_index)
    )
    if len({value.frame_index for value in normalized}) != len(normalized):
        raise ValueError("Orientation frame indices must be unique.")
    return normalized


def _validate_dependencies(
    frames: tuple[MolecularOrientationFrameData, ...],
    prototypes: MolecularOrientationPrototypeAnalysis,
) -> None:
    frame_indices = tuple(value.frame_index for value in frames)
    if frame_indices != prototypes.input_frame_indices:
        raise ValueError(
            "Stacking frames must match prototype input_frame_indices."
        )
    row_fingerprints = tuple(
        (
            value.frame_index,
            lattice_row_assignment_analysis_fingerprint(
                value.row_assignment
            ),
        )
        for value in frames
    )
    if row_fingerprints != prototypes.row_assignment_fingerprints:
        raise ValueError(
            "Stacking row assignments must match prototype dependencies."
        )


def _uniform_order(
    frame_index: int,
    domain: LatticeDomainRowAssignment,
    *,
    prototype: MolecularOrientationPrototype,
    measurement_by_id: dict[str, MolecularOrientationMeasurement],
    settings: MolecularStackingSettings,
) -> tuple[StackingOrder, tuple[OrientationalSubdomain, ...]]:
    prototype_measurement_ids = set(prototype.measurement_ids)
    domain_source_ids = set(domain.source_ids)
    measurements = tuple(
        value
        for measurement_id, value in measurement_by_id.items()
        if measurement_id in prototype_measurement_ids
        and value.provenance.frame_index == frame_index
        and value.provenance.source_id in domain_source_ids
    )
    source_ids = tuple(
        sorted(value.provenance.source_id for value in measurements)
    )
    usable_count = len(source_ids)
    coverage = usable_count / domain.molecule_count
    if coverage < settings.minimum_domain_coverage:
        return (
            _unavailable_order(
                frame_index,
                domain,
                reason="insufficient_domain_coverage",
                usable_molecule_count=usable_count,
            ),
            (),
        )
    if usable_count < settings.minimum_subdomain_size:
        return (
            _unavailable_order(
                frame_index,
                domain,
                reason="insufficient_subdomain_size",
                usable_molecule_count=usable_count,
            ),
            (),
        )
    spread_scale = max(
        prototype.periodicity_deg / 2.0,
        1e-12,
    )
    score = max(0.0, 1.0 - prototype.circular_spread_deg / spread_scale)
    mean_confidence = sum(
        float(value.confidence) for value in measurements
    ) / usable_count
    confidence = score * mean_confidence * coverage
    qc = []
    if coverage < 1.0:
        qc.append("incomplete_coverage")
    if confidence < settings.low_confidence_threshold:
        qc.append("low_confidence")
    subdomain_id = _subdomain_id(
        frame_index,
        domain.lattice_domain_id,
        0,
        "uniform",
        None,
        None,
    )
    child = OrientationalSubdomain(
        subdomain_id=subdomain_id,
        frame_index=frame_index,
        parent_lattice_domain_id=domain.lattice_domain_id,
        pattern="uniform",
        axis_candidate_index=None,
        axis_angle_deg=None,
        mode=None,
        phase=None,
        source_ids=source_ids,
        molecule_count=usable_count,
        parent_molecule_count=domain.molecule_count,
        coverage_fraction=coverage,
        score=score,
        confidence=score * mean_confidence,
        qc_reasons=tuple(sorted(qc)),
    )
    order = StackingOrder(
        frame_index=frame_index,
        lattice_domain_id=domain.lattice_domain_id,
        pattern="uniform",
        axis_candidate_index=None,
        axis_angle_deg=None,
        mode=None,
        phase=None,
        prototype_a_angle_deg=prototype.angle_deg,
        prototype_b_angle_deg=None,
        periodicity_deg=prototype.periodicity_deg,
        score=score,
        confidence=confidence,
        domain_molecule_count=domain.molecule_count,
        usable_molecule_count=usable_count,
        ordered_molecule_count=usable_count,
        coverage_fraction=coverage,
        ordered_fraction=1.0,
        subdomain_ids=(subdomain_id,),
        qc_reasons=tuple(sorted(qc)),
    )
    return order, (child,)


def _two_state_order(
    frame_index: int,
    domain: LatticeDomainRowAssignment,
    *,
    evidence: tuple[MolecularOrientationAxisEvidence, ...],
    prototype_a: MolecularOrientationPrototype,
    prototype_b: MolecularOrientationPrototype,
    settings: MolecularStackingSettings,
) -> tuple[StackingOrder, tuple[OrientationalSubdomain, ...]]:
    if not evidence:
        return (
            _unavailable_order(
                frame_index,
                domain,
                reason="no_axis_evidence",
            ),
            (),
        )
    evaluations = tuple(
        _evaluate_axis(value, settings=settings) for value in evidence
    )
    ranked = tuple(
        sorted(
            evaluations,
            key=lambda value: (
                -value.selection_score,
                value.evidence.candidate_index,
            ),
        )
    )
    best = ranked[0]
    coverage = best.evidence.coverage_fraction
    if coverage < settings.minimum_domain_coverage:
        return (
            _unavailable_order(
                frame_index,
                domain,
                reason="insufficient_domain_coverage",
                usable_molecule_count=len(best.evidence.assignments),
            ),
            (),
        )
    mean_confidence = _mean_assignment_confidence(
        best.evidence.assignments
    )
    prototype_values = {
        "prototype_a_angle_deg": prototype_a.angle_deg,
        "prototype_b_angle_deg": prototype_b.angle_deg,
        "periodicity_deg": prototype_a.periodicity_deg,
    }
    if len(ranked) > 1 and (
        best.selection_score - ranked[1].selection_score
        < settings.minimum_axis_margin
    ):
        return (
            _ambiguous_order(
                frame_index,
                domain,
                best,
                mean_confidence=mean_confidence,
                reason="axis_selection_ambiguous",
                prototype_values=prototype_values,
                settings=settings,
            ),
            (),
        )
    if (
        best.ordered_fraction < settings.minimum_ordered_fraction
        or best.score < settings.minimum_order_score
        or not best.components
    ):
        return (
            _ambiguous_order(
                frame_index,
                domain,
                best,
                mean_confidence=mean_confidence,
                reason="pattern_score_below_threshold",
                prototype_values=prototype_values,
                settings=settings,
            ),
            (),
        )

    children = _build_subdomains(
        frame_index,
        domain,
        best,
    )
    labels = {(value.mode, value.phase) for value in children}
    modes = {value.mode for value in children}
    phases = {value.phase for value in children}
    pattern = "ABAB" if len(labels) == 1 else "mixed"
    common_mode = next(iter(modes)) if len(modes) == 1 else None
    common_phase = next(iter(phases)) if len(phases) == 1 else None
    qc: list[StackingQCReason] = []
    if coverage < 1.0:
        qc.append("incomplete_coverage")
    if best.ordered_fraction < 1.0:
        qc.append("orientation_outliers")
    if len(phases) > 1:
        qc.append("phase_boundary")
    if len(modes) > 1:
        qc.append("pattern_boundary")
    if len(children) > len(labels):
        qc.append("spatial_fragmentation")
    ordered_count = len(best.ordered_source_ids)
    confidence = (
        best.score
        * mean_confidence
        * coverage
    )
    if confidence < settings.low_confidence_threshold:
        qc.append("low_confidence")
    order = StackingOrder(
        frame_index=frame_index,
        lattice_domain_id=domain.lattice_domain_id,
        pattern=pattern,
        axis_candidate_index=best.evidence.candidate_index,
        axis_angle_deg=best.evidence.axis_angle_deg,
        mode=common_mode,
        phase=common_phase,
        **prototype_values,
        score=best.score,
        confidence=confidence,
        domain_molecule_count=domain.molecule_count,
        usable_molecule_count=len(best.evidence.assignments),
        ordered_molecule_count=ordered_count,
        coverage_fraction=coverage,
        ordered_fraction=best.ordered_fraction,
        subdomain_ids=tuple(
            sorted(value.subdomain_id for value in children)
        ),
        qc_reasons=tuple(sorted(set(qc))),
    )
    return order, children


def _evaluate_axis(
    evidence: MolecularOrientationAxisEvidence,
    *,
    settings: MolecularStackingSettings,
) -> _AxisEvaluation:
    assignments = evidence.assignments
    if not assignments:
        return _AxisEvaluation(
            evidence=evidence,
            components=(),
            ordered_source_ids=(),
            ordered_fraction=0.0,
            score=0.0,
            selection_score=0.0,
        )
    assignment_by_id = {value.source_id: value for value in assignments}
    neighbors = _lattice_neighbors(assignments)
    labels = {}
    for assignment in assignments:
        scored = tuple(
            sorted(
                (
                    (
                        _local_mode_score(
                            assignment,
                            mode=mode,
                            assignment_by_id=assignment_by_id,
                            neighbor_ids=neighbors[assignment.source_id],
                        ),
                        mode,
                    )
                    for mode in _MODES
                ),
                key=lambda value: (-value[0], _MODES.index(value[1])),
            )
        )
        best_score, best_mode = scored[0]
        margin = best_score - scored[1][0]
        if (
            best_score < settings.minimum_local_score
            or margin < settings.minimum_local_margin
        ):
            continue
        labels[assignment.source_id] = _LocalLabel(
            source_id=assignment.source_id,
            mode=best_mode,
            phase=_assignment_phase(assignment, best_mode),
            score=best_score,
            confidence=assignment.confidence,
        )
    components = tuple(
        value
        for value in _label_components(labels, neighbors)
        if len(value.source_ids) >= settings.minimum_subdomain_size
    )
    ordered_source_ids = tuple(
        sorted(
            {
                source_id
                for component in components
                for source_id in component.source_ids
            }
        )
    )
    ordered_fraction = len(ordered_source_ids) / len(assignments)
    score = ordered_fraction * _component_weighted_score(components)
    selection_score = evidence.coverage_fraction * score
    return _AxisEvaluation(
        evidence=evidence,
        components=components,
        ordered_source_ids=ordered_source_ids,
        ordered_fraction=ordered_fraction,
        score=score,
        selection_score=selection_score,
    )


def _lattice_neighbors(
    assignments: tuple[MolecularOrientationStateAssignment, ...],
) -> dict[str, tuple[str, ...]]:
    source_by_coordinate = {
        (value.row_index, value.along_index): value.source_id
        for value in assignments
    }
    result = {}
    for value in assignments:
        candidates = (
            (value.row_index, value.along_index - 1),
            (value.row_index, value.along_index + 1),
            (value.row_index - 1, value.along_index),
            (value.row_index + 1, value.along_index),
        )
        result[value.source_id] = tuple(
            sorted(
                source_by_coordinate[coordinate]
                for coordinate in candidates
                if coordinate in source_by_coordinate
            )
        )
    return result


def _local_mode_score(
    assignment: MolecularOrientationStateAssignment,
    *,
    mode: MolecularOrientationPatternMode,
    assignment_by_id: dict[str, MolecularOrientationStateAssignment],
    neighbor_ids: tuple[str, ...],
) -> float:
    phase = _assignment_phase(assignment, mode)
    neighborhood = (
        assignment,
        *(assignment_by_id[value] for value in neighbor_ids),
    )
    total_weight = sum(value.confidence for value in neighborhood)
    if total_weight <= 0.0:
        return 0.0
    matched_weight = sum(
        value.confidence
        for value in neighborhood
        if _assignment_phase(value, mode) == phase
    )
    return matched_weight / total_weight


def _assignment_phase(
    assignment: MolecularOrientationStateAssignment,
    mode: MolecularOrientationPatternMode,
) -> MolecularOrientationPatternPhase:
    state_bit = 0 if assignment.state_label == "A" else 1
    if mode == "along_rows":
        parity = assignment.along_parity
    elif mode == "between_rows":
        parity = assignment.row_parity
    else:
        parity = assignment.along_parity ^ assignment.row_parity
    return "ABAB" if state_bit == parity else "BABA"


def _label_components(
    labels: dict[str, _LocalLabel],
    neighbors: dict[str, tuple[str, ...]],
) -> tuple[_Component, ...]:
    remaining = set(labels)
    components = []
    while remaining:
        seed = min(remaining)
        label = labels[seed]
        pending = [seed]
        source_ids = []
        while pending:
            source_id = pending.pop()
            if source_id not in remaining:
                continue
            current = labels[source_id]
            if (current.mode, current.phase) != (label.mode, label.phase):
                continue
            remaining.remove(source_id)
            source_ids.append(source_id)
            pending.extend(
                value
                for value in neighbors[source_id]
                if value in remaining
                and (
                    labels[value].mode,
                    labels[value].phase,
                )
                == (label.mode, label.phase)
            )
        source_tuple = tuple(sorted(source_ids))
        weight = sum(labels[value].confidence for value in source_tuple)
        score = sum(
            labels[value].confidence * labels[value].score
            for value in source_tuple
        ) / weight
        confidence = sum(
            labels[value].confidence for value in source_tuple
        ) / len(source_tuple)
        components.append(
            _Component(
                mode=label.mode,
                phase=label.phase,
                source_ids=source_tuple,
                score=score,
                confidence=score * confidence,
            )
        )
    return tuple(
        sorted(
            components,
            key=lambda value: (
                value.mode,
                value.phase,
                value.source_ids,
            ),
        )
    )


def _component_weighted_score(
    components: tuple[_Component, ...],
) -> float:
    count = sum(len(value.source_ids) for value in components)
    if count == 0:
        return 0.0
    return sum(
        len(value.source_ids) * value.score for value in components
    ) / count


def _build_subdomains(
    frame_index: int,
    domain: LatticeDomainRowAssignment,
    evaluation: _AxisEvaluation,
) -> tuple[OrientationalSubdomain, ...]:
    result = []
    for index, component in enumerate(evaluation.components):
        subdomain_id = _subdomain_id(
            frame_index,
            domain.lattice_domain_id,
            index,
            "ABAB",
            component.mode,
            component.phase,
        )
        result.append(
            OrientationalSubdomain(
                subdomain_id=subdomain_id,
                frame_index=frame_index,
                parent_lattice_domain_id=domain.lattice_domain_id,
                pattern="ABAB",
                axis_candidate_index=(
                    evaluation.evidence.candidate_index
                ),
                axis_angle_deg=evaluation.evidence.axis_angle_deg,
                mode=component.mode,
                phase=component.phase,
                source_ids=component.source_ids,
                molecule_count=len(component.source_ids),
                parent_molecule_count=domain.molecule_count,
                coverage_fraction=(
                    len(component.source_ids) / domain.molecule_count
                ),
                score=component.score,
                confidence=component.confidence,
                qc_reasons=(),
            )
        )
    return tuple(result)


def _ambiguous_order(
    frame_index: int,
    domain: LatticeDomainRowAssignment,
    evaluation: _AxisEvaluation,
    *,
    mean_confidence: float,
    reason: StackingQCReason,
    prototype_values: dict[str, float],
    settings: MolecularStackingSettings,
) -> StackingOrder:
    usable_count = len(evaluation.evidence.assignments)
    coverage = usable_count / domain.molecule_count
    qc = [reason]
    if coverage < 1.0:
        qc.append("incomplete_coverage")
    confidence = evaluation.selection_score * mean_confidence
    if confidence < settings.low_confidence_threshold:
        qc.append("low_confidence")
    return StackingOrder(
        frame_index=frame_index,
        lattice_domain_id=domain.lattice_domain_id,
        pattern="ambiguous",
        axis_candidate_index=None,
        axis_angle_deg=None,
        mode=None,
        phase=None,
        **prototype_values,
        score=evaluation.score,
        confidence=confidence,
        domain_molecule_count=domain.molecule_count,
        usable_molecule_count=usable_count,
        ordered_molecule_count=len(evaluation.ordered_source_ids),
        coverage_fraction=coverage,
        ordered_fraction=evaluation.ordered_fraction,
        subdomain_ids=(),
        qc_reasons=tuple(sorted(set(qc))),
    )


def _unavailable_order(
    frame_index: int,
    domain: LatticeDomainRowAssignment,
    *,
    reason: StackingQCReason,
    usable_molecule_count: int = 0,
) -> StackingOrder:
    return StackingOrder(
        frame_index=frame_index,
        lattice_domain_id=domain.lattice_domain_id,
        pattern="unavailable",
        axis_candidate_index=None,
        axis_angle_deg=None,
        mode=None,
        phase=None,
        prototype_a_angle_deg=None,
        prototype_b_angle_deg=None,
        periodicity_deg=None,
        score=None,
        confidence=0.0,
        domain_molecule_count=domain.molecule_count,
        usable_molecule_count=usable_molecule_count,
        ordered_molecule_count=0,
        coverage_fraction=(
            usable_molecule_count / domain.molecule_count
        ),
        ordered_fraction=0.0,
        subdomain_ids=(),
        qc_reasons=(reason,),
    )


def _mean_assignment_confidence(
    assignments: tuple[MolecularOrientationStateAssignment, ...],
) -> float:
    if not assignments:
        return 0.0
    return sum(value.confidence for value in assignments) / len(assignments)


def _subdomain_id(
    frame_index: int,
    domain_id: str,
    component_index: int,
    pattern: str,
    mode: MolecularOrientationPatternMode | None,
    phase: MolecularOrientationPatternPhase | None,
) -> str:
    payload = "|".join(
        (
            str(frame_index),
            domain_id,
            str(component_index),
            pattern,
            mode or "none",
            phase or "none",
        )
    )
    digest = sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"stack-{frame_index}-{component_index}-{digest}"


__all__ = ["analyze_molecular_stacking"]
