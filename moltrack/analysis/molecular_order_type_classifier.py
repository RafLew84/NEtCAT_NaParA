"""Joint classification of independent molecular-order hierarchy layers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from itertools import permutations
from math import atan2, cos, fsum, hypot, isclose, isfinite, pi, sin
from numbers import Real

from ._deterministic_complete_linkage import (
    deterministic_complete_linkage_clusters,
)
from .frame_ranges import MolecularFrameRangeAnalysisScope
from .molecular_order_hierarchy import (
    MolecularOrderHierarchy,
    MolecularOrderLatticeDomain,
    molecular_order_hierarchy_fingerprint,
)
from .molecular_order_type_models import (
    MolecularOrderGeometryType,
    MolecularOrderLayerAssignment,
    MolecularOrderLayerUnclassifiedReason,
    MolecularOrderOrientationType,
    MolecularOrderStackingType,
    MolecularOrderTypeAssignment,
    MolecularOrderTypeClassificationResult,
    MolecularOrderTypeClassificationSettings,
    MolecularOrderTypeObservation,
    MolecularOrderTypeObservationKey,
    molecular_order_type_observations_fingerprint,
    molecular_order_type_label,
    molecular_order_type_settings_fingerprint,
)
from .molecular_orientation_prototype_models import (
    MolecularOrientationPatternPhase,
)
from .molecular_stacking_models import StackingOrder


_Cluster = tuple[MolecularOrderTypeObservation, ...]
_StructuralKey = tuple[object, ...]
_SYMMETRY_ORDER = {
    "trifold": 0,
    "sixfold": 1,
    "mixed": 2,
    "ambiguous": 3,
}
_STACKING_PATTERN_ORDER = {
    "ABAB": 0,
    "uniform": 1,
    "mixed": 2,
    "ambiguous": 3,
    "unavailable": 4,
}


@dataclass(frozen=True)
class _GeometrySummary:
    observations: _Cluster
    dominant_symmetry: str | None
    theta3_deg: float | None
    theta6_deg: float | None


@dataclass(frozen=True)
class _OrientationSummary:
    observations: _Cluster
    prototype_angles_deg: tuple[float, ...]
    periodicity_deg: float


@dataclass(frozen=True)
class _StackingSummary:
    observations: _Cluster
    pattern: str | None
    mode: str | None
    phase: str | None


def classify_molecular_order_types(
    hierarchy: MolecularOrderHierarchy,
    *,
    analysis_scope: MolecularFrameRangeAnalysisScope,
    settings: MolecularOrderTypeClassificationSettings,
) -> MolecularOrderTypeClassificationResult:
    """Classify one or two ranges jointly without temporal tracking."""

    if not isinstance(hierarchy, MolecularOrderHierarchy):
        raise TypeError("hierarchy must be MolecularOrderHierarchy.")
    if not isinstance(analysis_scope, MolecularFrameRangeAnalysisScope):
        raise TypeError(
            "analysis_scope must be MolecularFrameRangeAnalysisScope."
        )
    if not isinstance(settings, MolecularOrderTypeClassificationSettings):
        raise TypeError(
            "settings must be MolecularOrderTypeClassificationSettings."
        )
    if hierarchy.source_view != analysis_scope.source_view:
        raise ValueError(
            "Hierarchy source_view must match the analysis scope."
        )
    hierarchy_fingerprint = molecular_order_hierarchy_fingerprint(hierarchy)
    observations = extract_molecular_order_type_observations(
        hierarchy,
        analysis_scope=analysis_scope,
    )
    geometry_types, geometry_assignments = _classify_geometry(
        observations,
        settings=settings,
    )
    orientation_types, orientation_assignments = _classify_orientation(
        observations,
        settings=settings,
    )
    stacking_types, stacking_assignments = _classify_stacking(
        observations,
        settings=settings,
    )
    assignments = tuple(
        MolecularOrderTypeAssignment(
            observation_key=observation.stable_key,
            geometry=geometry_assignments[observation.stable_key],
            orientation=orientation_assignments[observation.stable_key],
            stacking=stacking_assignments[observation.stable_key],
        )
        for observation in observations
    )
    return MolecularOrderTypeClassificationResult(
        analysis_scope=analysis_scope,
        settings=settings,
        settings_fingerprint=molecular_order_type_settings_fingerprint(
            settings
        ),
        hierarchy_fingerprint=hierarchy_fingerprint,
        input_fingerprint=molecular_order_type_observations_fingerprint(
            observations
        ),
        observations=observations,
        geometry_types=geometry_types,
        orientation_types=orientation_types,
        stacking_types=stacking_types,
        assignments=assignments,
    )


def extract_molecular_order_type_observations(
    hierarchy: MolecularOrderHierarchy,
    *,
    analysis_scope: MolecularFrameRangeAnalysisScope,
) -> tuple[MolecularOrderTypeObservation, ...]:
    """Extract immutable domain observations for one or two named ranges."""

    if not isinstance(hierarchy, MolecularOrderHierarchy):
        raise TypeError("hierarchy must be MolecularOrderHierarchy.")
    if not isinstance(analysis_scope, MolecularFrameRangeAnalysisScope):
        raise TypeError(
            "analysis_scope must be MolecularFrameRangeAnalysisScope."
        )
    if hierarchy.source_view != analysis_scope.source_view:
        raise ValueError(
            "Hierarchy source_view must match the analysis scope."
        )
    _validate_non_overlapping_ranges(analysis_scope)
    expected_fingerprint = molecular_order_hierarchy_fingerprint(hierarchy)
    frame_by_index = {
        frame.frame_index: frame for frame in hierarchy.frames
    }
    required_frames = {
        frame_index
        for frame_range in analysis_scope.ranges
        for frame_index in frame_range.frame_indices
    }
    missing_frames = sorted(required_frames.difference(frame_by_index))
    if missing_frames:
        raise ValueError(
            "Hierarchy is missing selected analysis frames: "
            + ", ".join(str(value) for value in missing_frames)
        )
    observations = []
    for frame_range in analysis_scope.ranges:
        for frame_index in frame_range.frame_indices:
            frame = frame_by_index[frame_index]
            for domain in frame.lattice_domains:
                observations.append(
                    _observation_from_domain(
                        domain,
                        range_name=frame_range.name,
                        range_start_frame=frame_range.start_frame,
                        range_end_frame=frame_range.end_frame,
                        source_view=analysis_scope.source_view,
                        hierarchy_fingerprint=expected_fingerprint,
                    )
                )
    return tuple(
        sorted(observations, key=lambda value: value.stable_key)
    )


def periodic_orientation_distance_deg(
    first_deg: object,
    second_deg: object,
    *,
    periodicity_deg: object,
) -> float:
    """Return the shortest non-negative distance under a chosen period."""

    period = _positive_float(periodicity_deg, "periodicity_deg")
    first = _normalize_angle(first_deg, period, "first_deg")
    second = _normalize_angle(second_deg, period, "second_deg")
    direct = abs(first - second)
    return min(direct, period - direct)


def _validate_non_overlapping_ranges(
    analysis_scope: MolecularFrameRangeAnalysisScope,
) -> None:
    if len(analysis_scope.ranges) < 2:
        return
    first, second = analysis_scope.ranges
    overlapping_frames = set(first.frame_indices).intersection(
        second.frame_indices
    )
    if overlapping_frames:
        raise ValueError(
            "Molecular-order type classification ranges must not overlap; "
            "overlap would duplicate and reweight domain observations."
        )


def _canonical_orientation_prototypes_and_phase(
    order: StackingOrder,
) -> tuple[
    tuple[float, ...],
    MolecularOrientationPatternPhase | None,
]:
    labeled_prototypes = tuple(
        (label, value)
        for label, value in (
            ("A", order.prototype_a_angle_deg),
            ("B", order.prototype_b_angle_deg),
        )
        if value is not None
    )
    if not labeled_prototypes:
        return (), order.phase
    if order.periodicity_deg is None:
        raise ValueError(
            "Molecular orientation prototypes require periodicity."
        )
    normalized = tuple(
        (
            label,
            _normalize_angle(
                value,
                order.periodicity_deg,
                f"prototype_{label.lower()}_angle_deg",
            ),
        )
        for label, value in labeled_prototypes
    )
    ordered = tuple(sorted(normalized, key=lambda value: (value[1], value[0])))
    phase = order.phase
    if (
        len(ordered) == 2
        and tuple(label for label, _ in ordered) == ("B", "A")
        and phase is not None
    ):
        phase = "BABA" if phase == "ABAB" else "ABAB"
    return tuple(value for _, value in ordered), phase


def _observation_from_domain(
    domain: MolecularOrderLatticeDomain,
    *,
    range_name: str,
    range_start_frame: int,
    range_end_frame: int,
    source_view: str,
    hierarchy_fingerprint: str,
) -> MolecularOrderTypeObservation:
    order = domain.stacking_order
    prototype_values, stacking_phase = (
        _canonical_orientation_prototypes_and_phase(order)
    )
    return MolecularOrderTypeObservation(
        range_name=range_name,
        range_start_frame=range_start_frame,
        range_end_frame=range_end_frame,
        frame_index=domain.frame_index,
        lattice_domain_id=domain.lattice_domain.lattice_domain_id,
        component_type=domain.lattice_domain.component_type,
        dominant_symmetry=domain.lattice_domain.dominant_symmetry,
        theta3_lattice_deg=(
            domain.lattice_domain.theta3_lattice_prototype_deg
        ),
        theta6_lattice_deg=domain.lattice_domain.theta6_prototype_deg,
        molecular_orientation_prototypes_deg=prototype_values,
        molecular_orientation_periodicity_deg=(
            order.periodicity_deg if prototype_values else None
        ),
        stacking_pattern=order.pattern,
        stacking_mode=order.mode,
        stacking_phase=stacking_phase,
        molecule_count=domain.lattice_domain.molecule_count,
        source_view=source_view,
        hierarchy_fingerprint=hierarchy_fingerprint,
    )


def _classify_geometry(
    observations: tuple[MolecularOrderTypeObservation, ...],
    *,
    settings: MolecularOrderTypeClassificationSettings,
) -> tuple[
    tuple[MolecularOrderGeometryType, ...],
    dict[MolecularOrderTypeObservationKey, MolecularOrderLayerAssignment],
]:
    reasons = {
        value.stable_key: _geometry_unclassified_reason(value, settings)
        for value in observations
    }
    qualified = tuple(
        value for value in observations if reasons[value.stable_key] is None
    )
    clusters = _partitioned_complete_linkage_clusters(
        qualified,
        partition_key=lambda value: _geometry_partition_key(
            value,
            settings,
        ),
        distance=lambda left, right: _geometry_distance(
            left,
            right,
            settings,
        ),
        structural_key=lambda value: _geometry_structural_key(
            value,
            settings,
        ),
    )
    summaries = tuple(
        _geometry_summary(cluster, settings)
        for cluster in clusters
        if len(cluster) >= settings.minimum_observations_per_type
    )
    summaries = tuple(sorted(summaries, key=_geometry_summary_sort_key))
    types = tuple(
        MolecularOrderGeometryType(
            type_id=type_id,
            label=molecular_order_type_label(type_id),
            dominant_symmetry=summary.dominant_symmetry,
            prototype_theta3_lattice_deg=summary.theta3_deg,
            prototype_theta6_lattice_deg=summary.theta6_deg,
            observation_count=len(summary.observations),
        )
        for type_id, summary in enumerate(summaries)
    )
    return types, _layer_assignments(
        observations,
        summaries,
        reasons=reasons,
    )


def _classify_orientation(
    observations: tuple[MolecularOrderTypeObservation, ...],
    *,
    settings: MolecularOrderTypeClassificationSettings,
) -> tuple[
    tuple[MolecularOrderOrientationType, ...],
    dict[MolecularOrderTypeObservationKey, MolecularOrderLayerAssignment],
]:
    reasons = {
        value.stable_key: _orientation_unclassified_reason(value)
        for value in observations
    }
    qualified = tuple(
        value for value in observations if reasons[value.stable_key] is None
    )
    clusters = _partitioned_complete_linkage_clusters(
        qualified,
        partition_key=lambda value: (
            len(value.molecular_orientation_prototypes_deg),
        ),
        distance=lambda left, right: _orientation_distance(
            left,
            right,
            settings,
        ),
        structural_key=_orientation_structural_key,
    )
    summaries = tuple(
        _orientation_summary(cluster)
        for cluster in clusters
        if len(cluster) >= settings.minimum_observations_per_type
    )
    summaries = tuple(sorted(summaries, key=_orientation_summary_sort_key))
    types = tuple(
        MolecularOrderOrientationType(
            type_id=type_id,
            label=molecular_order_type_label(type_id),
            prototype_angles_deg=summary.prototype_angles_deg,
            periodicity_deg=summary.periodicity_deg,
            observation_count=len(summary.observations),
        )
        for type_id, summary in enumerate(summaries)
    )
    return types, _layer_assignments(
        observations,
        summaries,
        reasons=reasons,
    )


def _classify_stacking(
    observations: tuple[MolecularOrderTypeObservation, ...],
    *,
    settings: MolecularOrderTypeClassificationSettings,
) -> tuple[
    tuple[MolecularOrderStackingType, ...],
    dict[MolecularOrderTypeObservationKey, MolecularOrderLayerAssignment],
]:
    reasons = {
        value.stable_key: _stacking_unclassified_reason(value, settings)
        for value in observations
    }
    qualified = tuple(
        value for value in observations if reasons[value.stable_key] is None
    )
    clusters = _exact_signature_clusters(
        qualified,
        signature=lambda value: _stacking_signature(value, settings),
        structural_key=lambda value: _stacking_structural_key(
            value,
            settings,
        ),
    )
    summaries = tuple(
        _stacking_summary(cluster, settings)
        for cluster in clusters
        if len(cluster) >= settings.minimum_observations_per_type
    )
    summaries = tuple(sorted(summaries, key=_stacking_summary_sort_key))
    types = tuple(
        MolecularOrderStackingType(
            type_id=type_id,
            label=molecular_order_type_label(type_id),
            pattern=summary.pattern,
            mode=summary.mode,
            phase=summary.phase,
            observation_count=len(summary.observations),
        )
        for type_id, summary in enumerate(summaries)
    )
    return types, _layer_assignments(
        observations,
        summaries,
        reasons=reasons,
    )


def _partitioned_complete_linkage_clusters(
    observations: tuple[MolecularOrderTypeObservation, ...],
    *,
    partition_key: Callable[
        [MolecularOrderTypeObservation],
        tuple[object, ...],
    ],
    distance: Callable[
        [MolecularOrderTypeObservation, MolecularOrderTypeObservation],
        float,
    ],
    structural_key: Callable[
        [MolecularOrderTypeObservation],
        _StructuralKey,
    ],
) -> tuple[_Cluster, ...]:
    partitions: dict[
        tuple[object, ...],
        list[MolecularOrderTypeObservation],
    ] = {}
    for observation in observations:
        partitions.setdefault(partition_key(observation), []).append(
            observation
        )
    clusters = tuple(
        cluster
        for partition in partitions.values()
        for cluster in deterministic_complete_linkage_clusters(
            partition,
            distance=distance,
            structural_key=structural_key,
        )
    )
    return tuple(
        sorted(
            clusters,
            key=lambda cluster: tuple(
                structural_key(value) for value in cluster
            )
        )
    )


def _exact_signature_clusters(
    observations: tuple[MolecularOrderTypeObservation, ...],
    *,
    signature: Callable[
        [MolecularOrderTypeObservation],
        tuple[object, ...],
    ],
    structural_key: Callable[
        [MolecularOrderTypeObservation],
        _StructuralKey,
    ],
) -> tuple[_Cluster, ...]:
    groups: dict[
        tuple[object, ...],
        list[MolecularOrderTypeObservation],
    ] = {}
    for observation in observations:
        groups.setdefault(signature(observation), []).append(observation)
    return tuple(
        tuple(sorted(group, key=structural_key))
        for _, group in sorted(groups.items(), key=lambda item: repr(item[0]))
    )


def _geometry_unclassified_reason(
    observation: MolecularOrderTypeObservation,
    settings: MolecularOrderTypeClassificationSettings,
) -> MolecularOrderLayerUnclassifiedReason | None:
    if observation.dominant_symmetry == "ambiguous":
        return "geometry_ambiguous"
    available = (
        "dominant_symmetry" in settings.geometry_features
        or (
            "theta3_lattice" in settings.geometry_features
            and observation.theta3_lattice_deg is not None
        )
        or (
            "theta6_lattice" in settings.geometry_features
            and observation.theta6_lattice_deg is not None
        )
    )
    return None if available else "geometry_features_unavailable"


def _orientation_unclassified_reason(
    observation: MolecularOrderTypeObservation,
) -> MolecularOrderLayerUnclassifiedReason | None:
    if (
        not observation.molecular_orientation_prototypes_deg
        or observation.molecular_orientation_periodicity_deg is None
    ):
        return "orientation_features_unavailable"
    return None


def _stacking_unclassified_reason(
    observation: MolecularOrderTypeObservation,
    settings: MolecularOrderTypeClassificationSettings,
) -> MolecularOrderLayerUnclassifiedReason | None:
    if observation.stacking_pattern in {"ambiguous", "unavailable"}:
        return "stacking_result_unavailable"
    if (
        "mode" in settings.stacking_features
        and observation.stacking_mode is None
    ) or (
        "phase" in settings.stacking_features
        and observation.stacking_phase is None
    ):
        return "stacking_features_unavailable"
    return None


def _geometry_distance(
    left: MolecularOrderTypeObservation,
    right: MolecularOrderTypeObservation,
    settings: MolecularOrderTypeClassificationSettings,
) -> float:
    distances = []
    if "dominant_symmetry" in settings.geometry_features:
        if left.dominant_symmetry != right.dominant_symmetry:
            return float("inf")
        distances.append(0.0)
    for feature_name, field_name in (
        ("theta3_lattice", "theta3_lattice_deg"),
        ("theta6_lattice", "theta6_lattice_deg"),
    ):
        if feature_name not in settings.geometry_features:
            continue
        left_value = getattr(left, field_name)
        right_value = getattr(right, field_name)
        if left_value is None and right_value is None:
            continue
        if left_value is None or right_value is None:
            return float("inf")
        distances.append(
            periodic_orientation_distance_deg(
                left_value,
                right_value,
                periodicity_deg=60.0,
            )
            / settings.lattice_orientation_tolerance_deg
        )
    return max(distances, default=0.0)


def _orientation_distance(
    left: MolecularOrderTypeObservation,
    right: MolecularOrderTypeObservation,
    settings: MolecularOrderTypeClassificationSettings,
) -> float:
    left_period = left.molecular_orientation_periodicity_deg
    right_period = right.molecular_orientation_periodicity_deg
    if left_period is None or right_period is None:
        return float("inf")
    if not isclose(left_period, right_period, abs_tol=1e-9):
        return float("inf")
    left_values = left.molecular_orientation_prototypes_deg
    right_values = right.molecular_orientation_prototypes_deg
    if len(left_values) != len(right_values):
        return float("inf")
    return (
        _prototype_set_distance(
            left_values,
            right_values,
            periodicity_deg=left_period,
        )
        / settings.molecular_orientation_tolerance_deg
    )


def _prototype_set_distance(
    left: tuple[float, ...],
    right: tuple[float, ...],
    *,
    periodicity_deg: float,
) -> float:
    return min(
        max(
            periodic_orientation_distance_deg(
                left_value,
                right_value,
                periodicity_deg=periodicity_deg,
            )
            for left_value, right_value in zip(left, permutation)
        )
        for permutation in permutations(right)
    )


def _geometry_summary(
    cluster: _Cluster,
    settings: MolecularOrderTypeClassificationSettings,
) -> _GeometrySummary:
    dominant_symmetry = (
        cluster[0].dominant_symmetry
        if "dominant_symmetry" in settings.geometry_features
        else None
    )
    theta3 = _optional_cluster_periodic_mean(
        tuple(value.theta3_lattice_deg for value in cluster),
        selected="theta3_lattice" in settings.geometry_features,
        periodicity_deg=60.0,
    )
    theta6 = _optional_cluster_periodic_mean(
        tuple(value.theta6_lattice_deg for value in cluster),
        selected="theta6_lattice" in settings.geometry_features,
        periodicity_deg=60.0,
    )
    return _GeometrySummary(
        observations=cluster,
        dominant_symmetry=dominant_symmetry,
        theta3_deg=theta3,
        theta6_deg=theta6,
    )


def _orientation_summary(cluster: _Cluster) -> _OrientationSummary:
    period = cluster[0].molecular_orientation_periodicity_deg
    if period is None:
        raise ValueError(
            "Qualified orientation cluster requires periodicity."
        )
    reference = min(
        cluster,
        key=lambda candidate: (
            max(
                _prototype_set_distance(
                    candidate.molecular_orientation_prototypes_deg,
                    value.molecular_orientation_prototypes_deg,
                    periodicity_deg=period,
                )
                for value in cluster
            ),
            _orientation_structural_key(candidate),
        ),
    ).molecular_orientation_prototypes_deg
    aligned = tuple(
        _align_prototypes(
            reference,
            value.molecular_orientation_prototypes_deg,
            periodicity_deg=period,
        )
        for value in cluster
    )
    prototypes = tuple(
        sorted(
            _periodic_mean(
                tuple(values),
                periodicity_deg=period,
            )
            for values in zip(*aligned)
        )
    )
    return _OrientationSummary(
        observations=cluster,
        prototype_angles_deg=prototypes,
        periodicity_deg=period,
    )


def _stacking_summary(
    cluster: _Cluster,
    settings: MolecularOrderTypeClassificationSettings,
) -> _StackingSummary:
    first = cluster[0]
    return _StackingSummary(
        observations=cluster,
        pattern=(
            first.stacking_pattern
            if "pattern" in settings.stacking_features
            else None
        ),
        mode=(
            first.stacking_mode
            if "mode" in settings.stacking_features
            else None
        ),
        phase=(
            first.stacking_phase
            if "phase" in settings.stacking_features
            else None
        ),
    )


def _optional_cluster_periodic_mean(
    values: tuple[float | None, ...],
    *,
    selected: bool,
    periodicity_deg: float,
) -> float | None:
    if not selected or all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise ValueError(
            "A geometry cluster cannot mix available and missing angles."
        )
    return _periodic_mean(
        tuple(value for value in values if value is not None),
        periodicity_deg=periodicity_deg,
    )


def _periodic_mean(
    values: tuple[float, ...],
    *,
    periodicity_deg: float,
) -> float:
    if len(values) == 1:
        return _normalize_angle(
            values[0],
            periodicity_deg,
            "periodic mean",
        )
    angles = tuple(2.0 * pi * value / periodicity_deg for value in values)
    cosine = fsum(cos(value) for value in angles)
    sine = fsum(sin(value) for value in angles)
    if hypot(cosine, sine) <= len(values) * 1e-12:
        return min(
            values,
            key=lambda candidate: (
                max(
                    periodic_orientation_distance_deg(
                        candidate,
                        value,
                        periodicity_deg=periodicity_deg,
                    )
                    for value in values
                ),
                candidate,
            ),
        )
    angle = atan2(sine, cosine) * periodicity_deg / (2.0 * pi)
    return _normalize_angle(angle, periodicity_deg, "periodic mean")


def _align_prototypes(
    reference: tuple[float, ...],
    values: tuple[float, ...],
    *,
    periodicity_deg: float,
) -> tuple[float, ...]:
    return min(
        permutations(values),
        key=lambda permutation: (
            max(
                periodic_orientation_distance_deg(
                    reference_value,
                    value,
                    periodicity_deg=periodicity_deg,
                )
                for reference_value, value in zip(reference, permutation)
            ),
            permutation,
        ),
    )


def _layer_assignments(
    observations: tuple[MolecularOrderTypeObservation, ...],
    summaries: tuple[
        _GeometrySummary | _OrientationSummary | _StackingSummary,
        ...,
    ],
    *,
    reasons: dict[
        MolecularOrderTypeObservationKey,
        MolecularOrderLayerUnclassifiedReason | None,
    ],
) -> dict[
    MolecularOrderTypeObservationKey,
    MolecularOrderLayerAssignment,
]:
    type_by_key = {
        observation.stable_key: type_id
        for type_id, summary in enumerate(summaries)
        for observation in summary.observations
    }
    assignments = {}
    for observation in observations:
        key = observation.stable_key
        if key in type_by_key:
            assignments[key] = MolecularOrderLayerAssignment.classified(
                type_by_key[key]
            )
        elif reasons[key] is not None:
            assignments[key] = MolecularOrderLayerAssignment.unclassified(
                reasons[key]
            )
        else:
            assignments[key] = MolecularOrderLayerAssignment.unclassified(
                "below_minimum_observations_per_type"
            )
    return assignments


def _geometry_structural_key(
    observation: MolecularOrderTypeObservation,
    settings: MolecularOrderTypeClassificationSettings,
) -> _StructuralKey:
    return (
        (
            _SYMMETRY_ORDER[observation.dominant_symmetry]
            if "dominant_symmetry" in settings.geometry_features
            else -1
        ),
        _optional_sort_key(
            observation.theta3_lattice_deg
            if "theta3_lattice" in settings.geometry_features
            else None
        ),
        _optional_sort_key(
            observation.theta6_lattice_deg
            if "theta6_lattice" in settings.geometry_features
            else None
        ),
        observation.stable_key,
    )


def _geometry_partition_key(
    observation: MolecularOrderTypeObservation,
    settings: MolecularOrderTypeClassificationSettings,
) -> tuple[object, ...]:
    return (
        (
            observation.dominant_symmetry
            if "dominant_symmetry" in settings.geometry_features
            else None
        ),
        (
            observation.theta3_lattice_deg is not None
            if "theta3_lattice" in settings.geometry_features
            else None
        ),
        (
            observation.theta6_lattice_deg is not None
            if "theta6_lattice" in settings.geometry_features
            else None
        ),
    )


def _orientation_structural_key(
    observation: MolecularOrderTypeObservation,
) -> _StructuralKey:
    return (
        len(observation.molecular_orientation_prototypes_deg),
        observation.molecular_orientation_periodicity_deg,
        observation.molecular_orientation_prototypes_deg,
        observation.stable_key,
    )


def _stacking_structural_key(
    observation: MolecularOrderTypeObservation,
    settings: MolecularOrderTypeClassificationSettings,
) -> _StructuralKey:
    return (
        _stacking_signature(observation, settings),
        observation.stable_key,
    )


def _stacking_signature(
    observation: MolecularOrderTypeObservation,
    settings: MolecularOrderTypeClassificationSettings,
) -> tuple[object, ...]:
    values = {
        "pattern": observation.stacking_pattern,
        "mode": observation.stacking_mode,
        "phase": observation.stacking_phase,
    }
    return tuple(values[name] for name in settings.stacking_features)


def _geometry_summary_sort_key(
    summary: _GeometrySummary,
) -> tuple[object, ...]:
    return (
        (
            -1
            if summary.dominant_symmetry is None
            else _SYMMETRY_ORDER[summary.dominant_symmetry]
        ),
        _optional_sort_key(summary.theta3_deg),
        _optional_sort_key(summary.theta6_deg),
        _cluster_stable_key(summary.observations),
    )


def _orientation_summary_sort_key(
    summary: _OrientationSummary,
) -> tuple[object, ...]:
    return (
        len(summary.prototype_angles_deg),
        summary.periodicity_deg,
        summary.prototype_angles_deg,
        _cluster_stable_key(summary.observations),
    )


def _stacking_summary_sort_key(
    summary: _StackingSummary,
) -> tuple[object, ...]:
    return (
        (
            -1
            if summary.pattern is None
            else _STACKING_PATTERN_ORDER[summary.pattern]
        ),
        _optional_string_sort_key(summary.mode),
        _optional_string_sort_key(summary.phase),
        _cluster_stable_key(summary.observations),
    )


def _cluster_stable_key(cluster: _Cluster) -> tuple[object, ...]:
    return tuple(value.stable_key for value in cluster)


def _optional_sort_key(value: float | None) -> tuple[int, float]:
    return (1, 0.0) if value is None else (0, value)


def _optional_string_sort_key(value: str | None) -> tuple[int, str]:
    return (1, "") if value is None else (0, value)


def _positive_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number.")
    normalized = float(value)
    if not isfinite(normalized) or not normalized > 0.0:
        raise ValueError(f"{field_name} must be positive.")
    return normalized


def _normalize_angle(
    value: object,
    periodicity_deg: float,
    field_name: str,
) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{field_name} must be a real number.")
    normalized = float(value) % periodicity_deg
    if isclose(normalized, 0.0, abs_tol=1e-12) or isclose(
        normalized,
        periodicity_deg,
        abs_tol=1e-12,
    ):
        return 0.0
    return normalized
