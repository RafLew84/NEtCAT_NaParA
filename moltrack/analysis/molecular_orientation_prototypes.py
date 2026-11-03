"""Multi-frame circular prototypes and A/B lattice-pattern evidence."""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import atan2, cos, pi, sin, sqrt

import numpy as np

from ._molecular_orientation_geometry import periodic_axis_distance
from .lattice_row_models import (
    LatticeRowAssignmentAnalysis,
    LatticeRowAxisCandidate,
    lattice_row_assignment_analysis_fingerprint,
)
from .molecular_orientation_models import MolecularOrientationMeasurement
from .molecular_orientation_prototype_models import (
    MolecularOrientationAxisEvidence,
    MolecularOrientationFrameData,
    MolecularOrientationPatternHypothesis,
    MolecularOrientationPatternMode,
    MolecularOrientationPatternPhase,
    MolecularOrientationPrototype,
    MolecularOrientationPrototypeAnalysis,
    MolecularOrientationPrototypeReason,
    MolecularOrientationPrototypeSettings,
    MolecularOrientationPrototypeStatus,
    MolecularOrientationRangeAxisEvidence,
    MolecularOrientationStateLabel,
    MolecularOrientationStateAssignment,
    molecular_orientation_frames_measurement_fingerprint,
    molecular_orientation_prototype_settings_fingerprint,
)

_PATTERN_MODES: tuple[MolecularOrientationPatternMode, ...] = (
    "along_rows",
    "between_rows",
    "checkerboard",
)
_PATTERN_PHASES: tuple[MolecularOrientationPatternPhase, ...] = (
    "ABAB",
    "BABA",
)


@dataclass(frozen=True)
class _Observation:
    frame_index: int
    measurement: MolecularOrientationMeasurement

    @property
    def source_id(self) -> str:
        return self.measurement.provenance.source_id

    @property
    def angle_deg(self) -> float:
        assert self.measurement.angle_deg is not None
        return float(self.measurement.angle_deg)

    @property
    def confidence(self) -> float:
        assert self.measurement.confidence is not None
        return float(self.measurement.confidence)

    @property
    def key(self) -> tuple[object, ...]:
        return (
            self.angle_deg,
            self.frame_index,
            self.source_id,
            self.measurement.measurement_id,
        )


@dataclass(frozen=True)
class _ClusterSummary:
    angle_deg: float
    spread_deg: float
    confidence_weight: float
    observations: tuple[_Observation, ...]


@dataclass(frozen=True)
class _CommonResultFields:
    input_frame_indices: tuple[int, ...]
    eligible_frame_indices: tuple[int, ...]
    total_measurement_count: int
    eligible_observation_count: int
    unsupported_state_observation_count: int
    excluded_non_available_count: int
    excluded_low_confidence_count: int
    excluded_outside_lattice_count: int
    source_file_sha256: str | None
    source_view: str | None
    row_assignment_fingerprints: tuple[tuple[int, str], ...]
    measurement_fingerprint: str
    settings: MolecularOrientationPrototypeSettings
    settings_fingerprint: str


def build_molecular_orientation_prototype_analysis(
    frames: tuple[MolecularOrientationFrameData, ...],
    *,
    settings: MolecularOrientationPrototypeSettings | None = None,
) -> MolecularOrientationPrototypeAnalysis:
    """Learn current A/B prototypes and evaluate every candidate row axis."""

    frame_data = tuple(frames)
    if not frame_data:
        raise ValueError("At least one orientation frame is required.")
    if any(
        not isinstance(value, MolecularOrientationFrameData)
        for value in frame_data
    ):
        raise TypeError(
            "frames must contain MolecularOrientationFrameData."
        )
    frame_data = tuple(sorted(frame_data, key=lambda value: value.frame_index))
    frame_indices = tuple(value.frame_index for value in frame_data)
    if len(set(frame_indices)) != len(frame_indices):
        raise ValueError("Orientation frame indices must be unique.")
    if settings is None:
        settings = MolecularOrientationPrototypeSettings()
    if not isinstance(settings, MolecularOrientationPrototypeSettings):
        raise TypeError(
            "settings must be MolecularOrientationPrototypeSettings."
        )

    all_measurements = tuple(
        measurement
        for frame in frame_data
        for measurement in frame.measurements
    )
    measurement_ids = tuple(
        value.measurement_id for value in all_measurements
    )
    if len(set(measurement_ids)) != len(measurement_ids):
        raise ValueError("measurement_id values must be globally unique.")
    source_hashes = {
        value.provenance.source_file_sha256 for value in all_measurements
    }
    source_views = {
        value.provenance.source_view for value in all_measurements
    }
    if len(source_hashes) > 1:
        raise ValueError("Prototype frames must use one source file.")
    if len(source_views) > 1:
        raise ValueError("Prototype frames must use one source view.")
    source_hash = next(iter(source_hashes), None)
    source_view = next(iter(source_views), None)

    eligible: list[_Observation] = []
    excluded_non_available = 0
    excluded_low_confidence = 0
    excluded_outside_lattice = 0
    for frame in frame_data:
        domain_source_ids = {
            source_id
            for assignment in frame.row_assignment.domain_assignments
            for source_id in assignment.source_ids
        }
        for measurement in frame.measurements:
            if measurement.provenance.source_id not in domain_source_ids:
                excluded_outside_lattice += 1
            elif measurement.status != "available":
                excluded_non_available += 1
            elif (
                measurement.confidence is None
                or measurement.confidence < settings.minimum_confidence
            ):
                excluded_low_confidence += 1
            else:
                eligible.append(
                    _Observation(
                        frame_index=frame.frame_index,
                        measurement=measurement,
                    )
                )
    eligible_tuple = tuple(sorted(eligible, key=lambda value: value.key))
    common = _common_result_fields(
        frame_data,
        all_measurements=all_measurements,
        eligible=eligible_tuple,
        excluded_non_available=excluded_non_available,
        excluded_low_confidence=excluded_low_confidence,
        excluded_outside_lattice=excluded_outside_lattice,
        source_hash=source_hash,
        source_view=source_view,
        settings=settings,
    )
    if not eligible_tuple:
        return _unavailable(
            reason="no_lattice_measurements",
            periodicity_deg=None,
            common=common,
        )

    periodicities = tuple(
        value.measurement.periodicity_deg for value in eligible_tuple
    )
    reference_period = float(periodicities[0])
    if any(
        abs(float(value) - reference_period)
        > settings.periodicity_tolerance_deg
        for value in periodicities[1:]
    ):
        return _unavailable(
            reason="incompatible_periodicity",
            periodicity_deg=None,
            common=common,
        )
    eligible_frames = tuple(
        sorted({value.frame_index for value in eligible_tuple})
    )
    if len(eligible_frames) < settings.minimum_frame_count:
        return _unavailable(
            reason="insufficient_frame_coverage",
            periodicity_deg=reference_period,
            common=common,
        )
    if len(eligible_tuple) < settings.minimum_observation_count:
        return _unavailable(
            reason="insufficient_observations",
            periodicity_deg=reference_period,
            common=common,
        )

    clusters = _circular_tolerance_clusters(
        eligible_tuple,
        period_deg=reference_period,
        tolerance_deg=settings.cluster_tolerance_deg,
    )
    cluster_summaries = tuple(
        sorted(
            (
                _summarize_cluster(
                    cluster,
                    period_deg=reference_period,
                )
                for cluster in clusters
            ),
            key=lambda value: (
                value.angle_deg,
                tuple(item.key for item in value.observations),
            ),
        )
    )
    summaries = tuple(
        value
        for value in cluster_summaries
        if (
            len(value.observations)
            >= settings.minimum_state_observation_count
            and len(
                {
                    observation.frame_index
                    for observation in value.observations
                }
            )
            >= settings.minimum_state_frame_count
        )
    )
    unsupported_state_observation_count = sum(
        len(value.observations)
        for value in cluster_summaries
        if value not in summaries
    )
    common = replace(
        common,
        unsupported_state_observation_count=(
            unsupported_state_observation_count
        ),
    )
    if not summaries:
        return _unavailable(
            reason="insufficient_state_support",
            periodicity_deg=reference_period,
            common=common,
        )
    status, reason = _status_for_cluster_count(len(summaries))
    total_weight = sum(value.confidence_weight for value in summaries)
    labels: tuple[MolecularOrientationStateLabel, ...] = (
        ("A", "B") if status == "two_state" else ()
    )
    prototypes = tuple(
        MolecularOrientationPrototype(
            prototype_index=index,
            state_label=labels[index] if labels else None,
            angle_deg=summary.angle_deg,
            periodicity_deg=reference_period,
            observation_count=len(summary.observations),
            frame_indices=tuple(
                sorted(
                    {value.frame_index for value in summary.observations}
                )
            ),
            confidence_weight=summary.confidence_weight,
            confidence_weight_fraction=(
                summary.confidence_weight / total_weight
            ),
            circular_spread_deg=summary.spread_deg,
            measurement_ids=tuple(
                sorted(
                    value.measurement.measurement_id
                    for value in summary.observations
                )
            ),
        )
        for index, summary in enumerate(summaries)
    )
    axis_evidence = ()
    range_axis_evidence = ()
    if status == "two_state":
        state_by_measurement_id: dict[
            str,
            MolecularOrientationStateLabel,
        ] = {
            observation.measurement.measurement_id: labels[index]
            for index, summary in enumerate(summaries)
            for observation in summary.observations
        }
        observation_by_frame_source = {
            (value.frame_index, value.source_id): value
            for value in eligible_tuple
        }
        axis_evidence = _build_axis_evidence(
            frame_data,
            observation_by_frame_source=observation_by_frame_source,
            state_by_measurement_id=state_by_measurement_id,
            prototypes=prototypes,
            period_deg=reference_period,
            settings=settings,
        )
        range_axis_evidence = _build_range_axis_evidence(
            axis_evidence,
            settings=settings,
        )
    return _analysis_result(
        status=status,
        reason=reason,
        prototypes=prototypes,
        axis_evidence=axis_evidence,
        range_axis_evidence=range_axis_evidence,
        periodicity_deg=reference_period,
        common=common,
    )


def _circular_tolerance_clusters(
    observations: tuple[_Observation, ...],
    *,
    period_deg: float,
    tolerance_deg: float,
) -> tuple[tuple[_Observation, ...], ...]:
    ordered = tuple(
        sorted(
            observations,
            key=lambda value: (
                value.angle_deg % period_deg,
                value.key,
            ),
        )
    )
    if len(ordered) == 1:
        return (ordered,)
    angles = tuple(value.angle_deg % period_deg for value in ordered)
    gaps = tuple(
        (
            angles[(index + 1) % len(angles)]
            - angles[index]
        )
        % period_deg
        for index in range(len(angles))
    )
    cut_after = min(
        range(len(ordered)),
        key=lambda index: (
            -gaps[index],
            angles[index],
            ordered[index].key,
        ),
    )
    start_index = (cut_after + 1) % len(ordered)
    start_angle = angles[start_index]
    unwrapped = tuple(
        (
            ordered[index],
            start_angle
            + (angles[index] - start_angle) % period_deg,
        )
        for offset in range(len(ordered))
        for index in ((start_index + offset) % len(ordered),)
    )
    clusters: list[list[_Observation]] = []
    cluster_start = 0.0
    for observation, angle in unwrapped:
        if (
            not clusters
            or angle - cluster_start > tolerance_deg + 1e-12
        ):
            clusters.append([observation])
            cluster_start = angle
        else:
            clusters[-1].append(observation)
    return tuple(
        tuple(sorted(cluster, key=lambda value: value.key))
        for cluster in clusters
    )


def _summarize_cluster(
    observations: tuple[_Observation, ...],
    *,
    period_deg: float,
) -> _ClusterSummary:
    weights = np.asarray(
        tuple(value.confidence for value in observations),
        dtype=np.float64,
    )
    angles = np.asarray(
        tuple(value.angle_deg for value in observations),
        dtype=np.float64,
    )
    phases = angles * (2.0 * pi / period_deg)
    vector = np.sum(weights * np.exp(1j * phases))
    if abs(vector) <= 1e-12:
        angle = min(value.angle_deg for value in observations)
    else:
        angle = (
            atan2(float(vector.imag), float(vector.real))
            * period_deg
            / (2.0 * pi)
        ) % period_deg
    distances = np.asarray(
        tuple(
            periodic_axis_distance(
                value.angle_deg,
                angle,
                period_deg=period_deg,
            )
            for value in observations
        ),
        dtype=np.float64,
    )
    spread = float(
        sqrt(float(np.sum(weights * distances**2) / np.sum(weights)))
    )
    return _ClusterSummary(
        angle_deg=float(angle),
        spread_deg=spread,
        confidence_weight=float(np.sum(weights)),
        observations=tuple(
            sorted(observations, key=lambda value: value.key)
        ),
    )


def _status_for_cluster_count(
    cluster_count: int,
) -> tuple[
    MolecularOrientationPrototypeStatus,
    MolecularOrientationPrototypeReason,
]:
    if cluster_count == 1:
        return "one_state", "one_supported_state"
    if cluster_count == 2:
        return "two_state", "two_supported_states"
    return "multi_state", "more_than_two_supported_states"


def _build_axis_evidence(
    frames: tuple[MolecularOrientationFrameData, ...],
    *,
    observation_by_frame_source: dict[tuple[int, str], _Observation],
    state_by_measurement_id: dict[
        str,
        MolecularOrientationStateLabel,
    ],
    prototypes: tuple[MolecularOrientationPrototype, ...],
    period_deg: float,
    settings: MolecularOrientationPrototypeSettings,
) -> tuple[MolecularOrientationAxisEvidence, ...]:
    prototype_by_state = {
        value.state_label: value
        for value in prototypes
        if value.state_label is not None
    }
    evidence = []
    for frame in frames:
        for domain in frame.row_assignment.domain_assignments:
            for candidate in domain.candidates:
                evidence.append(
                    _candidate_evidence(
                        frame.frame_index,
                        domain_id=domain.lattice_domain_id,
                        domain_molecule_count=domain.molecule_count,
                        candidate=candidate,
                        observation_by_frame_source=(
                            observation_by_frame_source
                        ),
                        state_by_measurement_id=state_by_measurement_id,
                        prototype_by_state=prototype_by_state,
                        period_deg=period_deg,
                        settings=settings,
                    )
                )
    return tuple(
        sorted(
            evidence,
            key=lambda value: (
                value.frame_index,
                value.lattice_domain_id,
                value.candidate_index,
            ),
        )
    )


def _build_range_axis_evidence(
    axis_evidence: tuple[MolecularOrientationAxisEvidence, ...],
    *,
    settings: MolecularOrientationPrototypeSettings,
) -> tuple[MolecularOrientationRangeAxisEvidence, ...]:
    groups = tuple(
        group
        for group in _circular_axis_evidence_groups(
            tuple(
                value
                for value in axis_evidence
                if value.assignments
            ),
            tolerance_deg=settings.axis_aggregation_tolerance_deg,
        )
        if len({value.frame_index for value in group})
        >= settings.minimum_state_frame_count
    )
    result = []
    for family_index, members in enumerate(
        sorted(
            groups,
            key=lambda value: (
                _axis_evidence_mean_angle(value),
                tuple(_axis_evidence_key(item) for item in value),
            ),
        )
    ):
        hypotheses = tuple(
            _aggregate_pattern_hypothesis(
                members,
                mode=mode,
                phase=phase,
            )
            for mode in _PATTERN_MODES
            for phase in _PATTERN_PHASES
        )
        along_edge_count = sum(
            value.along_row_edge_count for value in members
        )
        between_edge_count = sum(
            value.between_row_edge_count for value in members
        )
        result.append(
            MolecularOrientationRangeAxisEvidence(
                axis_family_index=family_index,
                axis_angle_deg=_axis_evidence_mean_angle(members),
                candidate_keys=tuple(
                    sorted(_axis_evidence_key(value) for value in members)
                ),
                frame_indices=tuple(
                    sorted({value.frame_index for value in members})
                ),
                axis_evidence_count=len(members),
                observation_count=sum(
                    len(value.assignments) for value in members
                ),
                hypotheses=hypotheses,
                along_row_edge_count=along_edge_count,
                along_row_alternation_score=_aggregate_edge_score(
                    tuple(
                        (
                            value.along_row_edge_count,
                            value.along_row_alternation_score,
                        )
                        for value in members
                    )
                ),
                between_row_edge_count=between_edge_count,
                between_row_alternation_score=_aggregate_edge_score(
                    tuple(
                        (
                            value.between_row_edge_count,
                            value.between_row_alternation_score,
                        )
                        for value in members
                    )
                ),
            )
        )
    return tuple(result)


def _circular_axis_evidence_groups(
    evidence: tuple[MolecularOrientationAxisEvidence, ...],
    *,
    tolerance_deg: float,
) -> tuple[tuple[MolecularOrientationAxisEvidence, ...], ...]:
    if not evidence:
        return ()
    ordered = tuple(
        sorted(
            evidence,
            key=lambda value: (
                value.axis_angle_deg,
                _axis_evidence_key(value),
            ),
        )
    )
    if len(ordered) == 1:
        return (ordered,)
    angles = tuple(value.axis_angle_deg for value in ordered)
    gaps = tuple(
        (
            angles[(index + 1) % len(angles)]
            - angles[index]
        )
        % 180.0
        for index in range(len(angles))
    )
    cut_after = min(
        range(len(ordered)),
        key=lambda index: (
            -gaps[index],
            angles[index],
            _axis_evidence_key(ordered[index]),
        ),
    )
    start_index = (cut_after + 1) % len(ordered)
    start_angle = angles[start_index]
    unwrapped = tuple(
        (
            ordered[index],
            start_angle + (angles[index] - start_angle) % 180.0,
        )
        for offset in range(len(ordered))
        for index in ((start_index + offset) % len(ordered),)
    )
    groups: list[list[MolecularOrientationAxisEvidence]] = []
    group_start = 0.0
    for value, angle in unwrapped:
        if (
            not groups
            or angle - group_start > tolerance_deg + 1e-12
        ):
            groups.append([value])
            group_start = angle
        else:
            groups[-1].append(value)
    return tuple(
        tuple(
            sorted(group, key=_axis_evidence_key)
        )
        for group in groups
    )


def _axis_evidence_mean_angle(
    evidence: tuple[MolecularOrientationAxisEvidence, ...],
) -> float:
    weights = np.asarray(
        tuple(
            sum(value.confidence for value in item.assignments)
            for item in evidence
        ),
        dtype=np.float64,
    )
    phases = np.asarray(
        tuple(value.axis_angle_deg for value in evidence),
        dtype=np.float64,
    ) * (2.0 * pi / 180.0)
    vector = np.sum(weights * np.exp(1j * phases))
    if abs(vector) <= 1e-12:
        return min(value.axis_angle_deg for value in evidence)
    return (
        atan2(float(vector.imag), float(vector.real))
        * 180.0
        / (2.0 * pi)
    ) % 180.0


def _axis_evidence_key(
    value: MolecularOrientationAxisEvidence,
) -> tuple[int, str, int]:
    return (
        value.frame_index,
        value.lattice_domain_id,
        value.candidate_index,
    )


def _aggregate_pattern_hypothesis(
    evidence: tuple[MolecularOrientationAxisEvidence, ...],
    *,
    mode: MolecularOrientationPatternMode,
    phase: MolecularOrientationPatternPhase,
) -> MolecularOrientationPatternHypothesis:
    hypotheses = tuple(
        value.hypothesis(mode, phase) for value in evidence
    )
    confidence_weight = sum(
        value.confidence_weight for value in hypotheses
    )
    matched_weight = sum(
        value.confidence_weight * float(value.agreement_score)
        for value in hypotheses
        if value.agreement_score is not None
    )
    return MolecularOrientationPatternHypothesis(
        mode=mode,
        phase=phase,
        observation_count=sum(
            value.observation_count for value in hypotheses
        ),
        confidence_weight=confidence_weight,
        agreement_score=(
            None
            if confidence_weight <= 0.0
            else matched_weight / confidence_weight
        ),
    )


def _aggregate_edge_score(
    values: tuple[tuple[int, float | None], ...],
) -> float | None:
    edge_count = sum(value[0] for value in values)
    if edge_count == 0:
        return None
    return (
        sum(
            count * float(score)
            for count, score in values
            if score is not None
        )
        / edge_count
    )


def _candidate_evidence(
    frame_index: int,
    *,
    domain_id: str,
    domain_molecule_count: int,
    candidate: LatticeRowAxisCandidate,
    observation_by_frame_source: dict[tuple[int, str], _Observation],
    state_by_measurement_id: dict[
        str,
        MolecularOrientationStateLabel,
    ],
    prototype_by_state: dict[
        MolecularOrientationStateLabel,
        MolecularOrientationPrototype,
    ],
    period_deg: float,
    settings: MolecularOrientationPrototypeSettings,
) -> MolecularOrientationAxisEvidence:
    along_indices = _along_indices(candidate)
    member_by_source = {
        value.source_id: value for value in candidate.member_assignments
    }
    assignments = []
    for source_id in candidate.source_ids:
        observation = observation_by_frame_source.get(
            (frame_index, source_id)
        )
        if observation is None:
            continue
        state = state_by_measurement_id.get(
            observation.measurement.measurement_id
        )
        if state is None:
            continue
        prototype = prototype_by_state[state]
        alternative = prototype_by_state["B" if state == "A" else "A"]
        member = member_by_source[source_id]
        along_index = along_indices[source_id]
        assignments.append(
            MolecularOrientationStateAssignment(
                source_id=source_id,
                measurement_id=observation.measurement.measurement_id,
                state_label=state,
                angle_deg=observation.angle_deg,
                confidence=observation.confidence,
                prototype_distance_deg=periodic_axis_distance(
                    observation.angle_deg,
                    prototype.angle_deg,
                    period_deg=period_deg,
                ),
                alternative_distance_deg=periodic_axis_distance(
                    observation.angle_deg,
                    alternative.angle_deg,
                    period_deg=period_deg,
                ),
                row_index=member.row_index,
                row_parity=member.row_parity,
                along_index=along_index,
                along_parity=along_index % 2,
            )
        )
    assignment_tuple = tuple(
        sorted(assignments, key=lambda value: value.source_id)
    )
    hypotheses = tuple(
        _pattern_hypothesis(
            assignment_tuple,
            mode=mode,
            phase=phase,
        )
        for mode in _PATTERN_MODES
        for phase in _PATTERN_PHASES
    )
    assignment_by_source = {
        value.source_id: value for value in assignment_tuple
    }
    along_edges = _along_edges(
        candidate,
        along_indices=along_indices,
        eligible_source_ids=set(assignment_by_source),
    )
    between_edges = _between_edges(
        candidate,
        along_indices=along_indices,
        eligible_source_ids=set(assignment_by_source),
        max_along_fraction=settings.between_row_max_along_fraction,
    )
    along_score = _edge_alternation_score(
        along_edges,
        assignment_by_source=assignment_by_source,
    )
    between_score = _edge_alternation_score(
        between_edges,
        assignment_by_source=assignment_by_source,
    )
    return MolecularOrientationAxisEvidence(
        frame_index=frame_index,
        lattice_domain_id=domain_id,
        candidate_index=candidate.candidate_index,
        axis_angle_deg=candidate.axis_angle_deg,
        domain_molecule_count=domain_molecule_count,
        assignments=assignment_tuple,
        coverage_fraction=len(assignment_tuple) / domain_molecule_count,
        hypotheses=hypotheses,
        along_row_edge_count=len(along_edges),
        along_row_alternation_score=along_score,
        between_row_edge_count=len(between_edges),
        between_row_alternation_score=between_score,
    )


def _pattern_hypothesis(
    assignments: tuple[MolecularOrientationStateAssignment, ...],
    *,
    mode: MolecularOrientationPatternMode,
    phase: MolecularOrientationPatternPhase,
) -> MolecularOrientationPatternHypothesis:
    total_weight = sum(value.confidence for value in assignments)
    matched_weight = 0.0
    for value in assignments:
        if mode == "along_rows":
            parity = value.along_parity
        elif mode == "between_rows":
            parity = value.row_parity
        else:
            parity = value.along_parity ^ value.row_parity
        expected = "A" if parity == 0 else "B"
        if phase == "BABA":
            expected = "B" if expected == "A" else "A"
        if value.state_label == expected:
            matched_weight += value.confidence
    return MolecularOrientationPatternHypothesis(
        mode=mode,
        phase=phase,
        observation_count=len(assignments),
        confidence_weight=total_weight,
        agreement_score=(
            None
            if total_weight <= 0.0
            else matched_weight / total_weight
        ),
    )


def _along_indices(
    candidate: LatticeRowAxisCandidate,
) -> dict[str, int]:
    along_spacing = candidate.row_spacing_nm * 2.0 / sqrt(3.0)
    members = candidate.member_assignments
    corrected_coordinates = np.asarray(
        tuple(
            value.along_coordinate_nm
            - 0.5 * value.row_index * along_spacing
            for value in members
        ),
        dtype=np.float64,
    )
    phase = _periodic_phase(
        corrected_coordinates,
        period=along_spacing,
    )
    indices = np.rint(
        (corrected_coordinates - phase) / along_spacing
    ).astype(np.int64)
    return {
        value.source_id: int(index)
        for value, index in zip(members, indices)
    }


def _periodic_phase(values: np.ndarray, *, period: float) -> float:
    vectors = np.exp(1j * (2.0 * pi / period) * values)
    mean = np.mean(vectors)
    if abs(mean) <= 1e-12:
        centered = np.mod(values + 0.5 * period, period) - 0.5 * period
        return float(np.median(centered))
    phase = float(
        atan2(float(mean.imag), float(mean.real))
        * period
        / (2.0 * pi)
    )
    if abs(phase + 0.5 * period) <= 1e-10 * period:
        return 0.5 * period
    return phase


def _along_edges(
    candidate: LatticeRowAxisCandidate,
    *,
    along_indices: dict[str, int],
    eligible_source_ids: set[str],
) -> tuple[tuple[str, str], ...]:
    edges = set()
    for row in candidate.rows:
        source_ids = tuple(
            source_id
            for source_id in row.source_ids
            if source_id in eligible_source_ids
        )
        for left_index, left in enumerate(source_ids):
            for right in source_ids[left_index + 1 :]:
                if abs(
                    along_indices[left] - along_indices[right]
                ) == 1:
                    edges.add(tuple(sorted((left, right))))
    return tuple(sorted(edges))


def _between_edges(
    candidate: LatticeRowAxisCandidate,
    *,
    along_indices: dict[str, int],
    eligible_source_ids: set[str],
    max_along_fraction: float,
) -> tuple[tuple[str, str], ...]:
    member_by_source = {
        value.source_id: value for value in candidate.member_assignments
    }
    along_spacing = candidate.row_spacing_nm * 2.0 / sqrt(3.0)
    max_along_distance = max_along_fraction * along_spacing
    edges = set()
    for left_index, left_row in enumerate(candidate.rows):
        for right_row in candidate.rows[left_index + 1 :]:
            if abs(left_row.row_index - right_row.row_index) != 1:
                continue
            for left in left_row.source_ids:
                if left not in eligible_source_ids:
                    continue
                for right in right_row.source_ids:
                    if right not in eligible_source_ids:
                        continue
                    if along_indices[left] != along_indices[right]:
                        continue
                    if abs(
                        member_by_source[left].along_coordinate_nm
                        - member_by_source[right].along_coordinate_nm
                    ) <= max_along_distance + 1e-12:
                        edges.add(tuple(sorted((left, right))))
    return tuple(sorted(edges))


def _edge_alternation_score(
    edges: tuple[tuple[str, str], ...],
    *,
    assignment_by_source: dict[
        str,
        MolecularOrientationStateAssignment,
    ],
) -> float | None:
    if not edges:
        return None
    total_weight = 0.0
    alternating_weight = 0.0
    for left, right in edges:
        first = assignment_by_source[left]
        second = assignment_by_source[right]
        weight = sqrt(first.confidence * second.confidence)
        total_weight += weight
        if first.state_label != second.state_label:
            alternating_weight += weight
    return alternating_weight / total_weight


def _common_result_fields(
    frames: tuple[MolecularOrientationFrameData, ...],
    *,
    all_measurements: tuple[MolecularOrientationMeasurement, ...],
    eligible: tuple[_Observation, ...],
    excluded_non_available: int,
    excluded_low_confidence: int,
    excluded_outside_lattice: int,
    source_hash: str | None,
    source_view: str | None,
    settings: MolecularOrientationPrototypeSettings,
) -> _CommonResultFields:
    return _CommonResultFields(
        input_frame_indices=tuple(
            value.frame_index for value in frames
        ),
        eligible_frame_indices=tuple(
            sorted({value.frame_index for value in eligible})
        ),
        total_measurement_count=len(all_measurements),
        eligible_observation_count=len(eligible),
        unsupported_state_observation_count=0,
        excluded_non_available_count=excluded_non_available,
        excluded_low_confidence_count=excluded_low_confidence,
        excluded_outside_lattice_count=excluded_outside_lattice,
        source_file_sha256=source_hash,
        source_view=source_view,
        row_assignment_fingerprints=tuple(
            (
                value.frame_index,
                lattice_row_assignment_analysis_fingerprint(
                    value.row_assignment
                ),
            )
            for value in frames
        ),
        measurement_fingerprint=(
            molecular_orientation_frames_measurement_fingerprint(frames)
        ),
        settings=settings,
        settings_fingerprint=(
            molecular_orientation_prototype_settings_fingerprint(settings)
        ),
    )


def _analysis_result(
    *,
    status: MolecularOrientationPrototypeStatus,
    reason: MolecularOrientationPrototypeReason,
    prototypes: tuple[MolecularOrientationPrototype, ...],
    axis_evidence: tuple[MolecularOrientationAxisEvidence, ...],
    range_axis_evidence: tuple[MolecularOrientationRangeAxisEvidence, ...],
    periodicity_deg: float | None,
    common: _CommonResultFields,
) -> MolecularOrientationPrototypeAnalysis:
    return MolecularOrientationPrototypeAnalysis(
        status=status,
        reason=reason,
        prototypes=prototypes,
        axis_evidence=axis_evidence,
        range_axis_evidence=range_axis_evidence,
        input_frame_indices=common.input_frame_indices,
        eligible_frame_indices=common.eligible_frame_indices,
        total_measurement_count=common.total_measurement_count,
        eligible_observation_count=common.eligible_observation_count,
        unsupported_state_observation_count=(
            common.unsupported_state_observation_count
        ),
        excluded_non_available_count=common.excluded_non_available_count,
        excluded_low_confidence_count=common.excluded_low_confidence_count,
        excluded_outside_lattice_count=(
            common.excluded_outside_lattice_count
        ),
        periodicity_deg=periodicity_deg,
        source_file_sha256=common.source_file_sha256,
        source_view=common.source_view,
        row_assignment_fingerprints=common.row_assignment_fingerprints,
        measurement_fingerprint=common.measurement_fingerprint,
        settings=common.settings,
        settings_fingerprint=common.settings_fingerprint,
    )


def _unavailable(
    *,
    reason: MolecularOrientationPrototypeReason,
    periodicity_deg: float | None,
    common: _CommonResultFields,
) -> MolecularOrientationPrototypeAnalysis:
    return _analysis_result(
        status="unavailable",
        reason=reason,
        prototypes=(),
        axis_evidence=(),
        range_axis_evidence=(),
        periodicity_deg=periodicity_deg,
        common=common,
    )


__all__ = ["build_molecular_orientation_prototype_analysis"]
