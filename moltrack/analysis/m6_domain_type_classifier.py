from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from itertools import combinations

import numpy as np

from ._m6_domain_type_validation import non_empty_string as _non_empty_string
from .frame_ranges import MolecularFrameRangeAnalysisScope
from .m6_domain_type_observations import (
    M6DomainTypeObservation,
    M6DomainTypeObservationKey,
)
from .m6_domain_type_results import (
    M6DomainType,
    M6DomainTypeAssignment,
    M6DomainTypeClassificationResult,
)
from .m6_domain_type_settings import M6DomainTypeClassificationSettings
from .m6_domain_type_similarity import (
    compute_m6_domain_type_distance,
    mean_m6_orientation_deg,
    m6_orientation_distance_deg,
)
from .m6_settings import MolecularM6OrientationAnalysisSettings


_Cluster = tuple[M6DomainTypeObservation, ...]


@dataclass(frozen=True)
class _ClusterSummary:
    observations: _Cluster
    prototype_orientation_deg: float
    prototype_bond_length_nm: float
    orientation_circular_spread_deg: float
    bond_length_iqr_nm: float


def classify_m6_domain_types(
    observations: Iterable[M6DomainTypeObservation],
    *,
    analysis_scope: MolecularFrameRangeAnalysisScope,
    classification_settings: M6DomainTypeClassificationSettings,
    m6_settings: MolecularM6OrientationAnalysisSettings,
    m6_context_fingerprint: str,
) -> M6DomainTypeClassificationResult:
    """Classify one or two ranges jointly using deterministic complete linkage."""

    if not isinstance(analysis_scope, MolecularFrameRangeAnalysisScope):
        raise TypeError("analysis_scope must be MolecularFrameRangeAnalysisScope.")
    if not isinstance(
        classification_settings,
        M6DomainTypeClassificationSettings,
    ):
        raise TypeError(
            "classification_settings must be M6DomainTypeClassificationSettings."
        )
    if not isinstance(m6_settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("m6_settings must be MolecularM6OrientationAnalysisSettings.")
    context_fingerprint = _non_empty_string(
        m6_context_fingerprint,
        "m6_context_fingerprint",
    )
    try:
        normalized_observations = tuple(observations)
    except TypeError as exc:
        raise TypeError("observations must be an iterable of observations.") from exc
    if any(
        not isinstance(observation, M6DomainTypeObservation)
        for observation in normalized_observations
    ):
        raise TypeError("observations must contain M6DomainTypeObservation values.")
    ordered_observations = tuple(
        sorted(normalized_observations, key=lambda value: value.stable_key)
    )

    qualified = tuple(
        sorted(
            (
                observation
                for observation in ordered_observations
                if observation.qualification_status == "qualified"
            ),
            key=_observation_structural_key,
        )
    )
    clusters = _complete_linkage_clusters(
        qualified,
        settings=classification_settings,
    )
    accepted_summaries = tuple(
        _summarize_cluster(cluster)
        for cluster in clusters
        if len(cluster) >= classification_settings.minimum_observations_per_type
    )
    accepted_summaries = tuple(
        sorted(accepted_summaries, key=_cluster_summary_sort_key)
    )

    domain_types = tuple(
        _domain_type_from_summary(summary, domain_type_id=domain_type_id)
        for domain_type_id, summary in enumerate(accepted_summaries)
    )
    type_id_by_observation_key = {
        observation.stable_key: domain_type_id
        for domain_type_id, summary in enumerate(accepted_summaries)
        for observation in summary.observations
    }
    assignments = tuple(
        _assignment_for_observation(
            observation,
            type_id_by_observation_key=type_id_by_observation_key,
        )
        for observation in ordered_observations
    )
    classified_count = len(type_id_by_observation_key)
    return M6DomainTypeClassificationResult(
        analysis_scope=analysis_scope,
        classification_settings=classification_settings,
        m6_settings=m6_settings,
        m6_context_fingerprint=context_fingerprint,
        input_fingerprint=_observation_input_fingerprint(ordered_observations),
        observations=ordered_observations,
        domain_types=domain_types,
        assignments=assignments,
        observation_count=len(ordered_observations),
        classified_observation_count=classified_count,
        unclassified_observation_count=(
            len(ordered_observations) - classified_count
        ),
    )


def _complete_linkage_clusters(
    observations: tuple[M6DomainTypeObservation, ...],
    *,
    settings: M6DomainTypeClassificationSettings,
) -> tuple[_Cluster, ...]:
    clusters: list[_Cluster] = [(observation,) for observation in observations]
    while True:
        candidates: list[tuple[float, tuple[object, ...], int, int, _Cluster]] = []
        for left_index, right_index in combinations(range(len(clusters)), 2):
            left = clusters[left_index]
            right = clusters[right_index]
            linkage_distance = _complete_linkage_distance(
                left,
                right,
                settings=settings,
            )
            if linkage_distance > 1.0:
                continue
            merged = tuple(sorted((*left, *right), key=_observation_structural_key))
            candidates.append(
                (
                    linkage_distance,
                    _cluster_structural_key(merged),
                    left_index,
                    right_index,
                    merged,
                )
            )
        if not candidates:
            break
        _, _, left_index, right_index, merged = min(candidates)
        clusters = [
            cluster
            for index, cluster in enumerate(clusters)
            if index not in {left_index, right_index}
        ]
        clusters.append(merged)
        clusters.sort(key=_cluster_structural_key)
    return tuple(sorted(clusters, key=_cluster_structural_key))


def _complete_linkage_distance(
    left: _Cluster,
    right: _Cluster,
    *,
    settings: M6DomainTypeClassificationSettings,
) -> float:
    return max(
        compute_m6_domain_type_distance(
            left_observation.orientation_deg,
            _required_bond_length(left_observation),
            right_observation.orientation_deg,
            _required_bond_length(right_observation),
            settings=settings,
        ).normalized_distance
        for left_observation in left
        for right_observation in right
    )


def _assignment_for_observation(
    observation: M6DomainTypeObservation,
    *,
    type_id_by_observation_key: dict[M6DomainTypeObservationKey, int],
) -> M6DomainTypeAssignment:
    type_id = type_id_by_observation_key.get(observation.stable_key)
    if type_id is not None:
        return M6DomainTypeAssignment.classified(
            observation.stable_key,
            domain_type_id=type_id,
        )
    if observation.qualification_status == "unclassified":
        reason = observation.unclassified_reason
        if reason is None:  # guarded by M6DomainTypeObservation
            raise ValueError("Unclassified observation is missing its reason.")
        return M6DomainTypeAssignment.unclassified(
            observation.stable_key,
            reason=reason,
        )
    return M6DomainTypeAssignment.unclassified(
        observation.stable_key,
        reason="below_minimum_observations_per_type",
    )


def _summarize_cluster(cluster: _Cluster) -> _ClusterSummary:
    orientations = tuple(observation.orientation_deg for observation in cluster)
    bond_lengths = np.asarray(
        [_required_bond_length(observation) for observation in cluster],
        dtype=np.float64,
    )
    prototype_orientation = _cluster_mean_orientation(orientations)
    quartile_25, quartile_75 = np.percentile(bond_lengths, (25.0, 75.0))
    return _ClusterSummary(
        observations=cluster,
        prototype_orientation_deg=prototype_orientation,
        prototype_bond_length_nm=float(np.median(bond_lengths)),
        orientation_circular_spread_deg=max(
            m6_orientation_distance_deg(value, prototype_orientation)
            for value in orientations
        ),
        bond_length_iqr_nm=float(quartile_75 - quartile_25),
    )


def _domain_type_from_summary(
    summary: _ClusterSummary,
    *,
    domain_type_id: int,
) -> M6DomainType:
    return M6DomainType(
        domain_type_id=domain_type_id,
        prototype_orientation_deg=summary.prototype_orientation_deg,
        prototype_bond_length_nm=summary.prototype_bond_length_nm,
        orientation_circular_spread_deg=(
            summary.orientation_circular_spread_deg
        ),
        bond_length_iqr_nm=summary.bond_length_iqr_nm,
        observation_count=len(summary.observations),
    )


def _cluster_mean_orientation(orientations: tuple[float, ...]) -> float:
    try:
        return mean_m6_orientation_deg(orientations)
    except ValueError:
        # At the exact 30-degree ambiguity, use the deterministic circular medoid.
        return min(
            orientations,
            key=lambda candidate: (
                max(
                    m6_orientation_distance_deg(candidate, value)
                    for value in orientations
                ),
                candidate,
            ),
        )


def _cluster_summary_sort_key(summary: _ClusterSummary) -> tuple[object, ...]:
    return (
        summary.prototype_orientation_deg,
        summary.prototype_bond_length_nm,
        _cluster_structural_key(summary.observations),
    )


def _cluster_structural_key(cluster: _Cluster) -> tuple[object, ...]:
    return tuple(sorted(_observation_structural_key(value) for value in cluster))


def _observation_structural_key(
    observation: M6DomainTypeObservation,
) -> tuple[object, ...]:
    return (
        observation.orientation_deg,
        _required_bond_length(observation),
        observation.stable_key,
    )


def _required_bond_length(observation: M6DomainTypeObservation) -> float:
    value = observation.domain_median_bond_length_nm
    if value is None:
        raise ValueError("A qualified observation requires bond-length statistics.")
    return value


def _observation_input_fingerprint(
    observations: tuple[M6DomainTypeObservation, ...],
) -> str:
    encoded = json.dumps(
        [asdict(observation) for observation in observations],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()
