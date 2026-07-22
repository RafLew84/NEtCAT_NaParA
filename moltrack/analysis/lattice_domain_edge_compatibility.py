"""Classify first-shell edges using completed local M3/M6 evidence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal, cast

from ._first_shell_graph_fingerprint import first_shell_graph_fingerprint
from .first_shell_graph import FirstShellGraph
from .lattice_domain_edge_models import (
    LatticeDomainEdgeCompatibilityField,
    LatticeDomainEdgeCompatibilitySettings,
    LatticeDomainEdgeDecision,
    LatticeDomainEdgeRejectionReason,
    lattice_domain_edge_is_core_eligible,
    lattice_domain_edge_is_retained,
    lattice_domain_edge_settings_fingerprint,
)
from .local_multisymmetry_bond_order import (
    LocalMultiSymmetryBondOrderField,
    m3_lattice_orientation_distance_deg,
)
from .local_symmetry_evidence_models import (
    LocalSymmetryEvidenceField,
    LocalSymmetryModel,
)


_MODEL_PROFILE_FIELDS = (
    "trifold_model_score",
    "sixfold_model_score",
    "mixed_model_score",
    "disordered_model_score",
)
_Channel = Literal["trifold", "sixfold"]


@dataclass(frozen=True)
class _EdgeMetrics:
    theta3_delta_deg: float | None
    theta6_delta_deg: float | None
    model_profile_distance: float | None
    minimum_classification_confidence: float | None
    minimum_m3_orientation_confidence: float | None
    minimum_m6_orientation_confidence: float | None


@dataclass(frozen=True)
class _EdgeDecision:
    decision: LatticeDomainEdgeDecision
    rejection_reason: LatticeDomainEdgeRejectionReason | None
    metrics: _EdgeMetrics


@dataclass(frozen=True)
class _ChannelComparison:
    delta_deg: float | None
    tolerance_deg: float


@dataclass(frozen=True)
class _ChannelPolicy:
    compatible_decision: LatticeDomainEdgeDecision
    mismatch_reason: LatticeDomainEdgeRejectionReason
    delta_metric_field: Literal["theta3_delta_deg", "theta6_delta_deg"]
    tolerance_setting_field: Literal[
        "trifold_orientation_tolerance_deg",
        "sixfold_orientation_tolerance_deg",
    ]
    model_score_field: Literal["trifold_model_score", "sixfold_model_score"]


_CHANNEL_POLICIES: dict[_Channel, _ChannelPolicy] = {
    "trifold": _ChannelPolicy(
        compatible_decision="compatible_trifold",
        mismatch_reason="trifold_orientation_mismatch",
        delta_metric_field="theta3_delta_deg",
        tolerance_setting_field="trifold_orientation_tolerance_deg",
        model_score_field="trifold_model_score",
    ),
    "sixfold": _ChannelPolicy(
        compatible_decision="compatible_sixfold",
        mismatch_reason="sixfold_orientation_mismatch",
        delta_metric_field="theta6_delta_deg",
        tolerance_setting_field="sixfold_orientation_tolerance_deg",
        model_score_field="sixfold_model_score",
    ),
}


def build_lattice_domain_edge_compatibility(
    graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    *,
    settings: LatticeDomainEdgeCompatibilitySettings | None = None,
    near_equal_domain_claim_edges: Iterable[tuple[int, int]] = (),
) -> LatticeDomainEdgeCompatibilityField:
    """Decide which first-shell edges may participate in lattice domains.

    This consumes the completed point classifications from local symmetry
    analysis. It deliberately does not refit or fuse M3/M6 evidence.
    """

    if not isinstance(graph, FirstShellGraph):
        raise TypeError("graph must be a FirstShellGraph.")
    if not isinstance(local_order, LocalMultiSymmetryBondOrderField):
        raise TypeError("local_order must be a LocalMultiSymmetryBondOrderField.")
    if not isinstance(local_evidence, LocalSymmetryEvidenceField):
        raise TypeError("local_evidence must be a LocalSymmetryEvidenceField.")
    if settings is None:
        settings = LatticeDomainEdgeCompatibilitySettings()
    if not isinstance(settings, LatticeDomainEdgeCompatibilitySettings):
        raise TypeError("settings must be LatticeDomainEdgeCompatibilitySettings.")
    graph_fingerprint = first_shell_graph_fingerprint(graph)
    _validate_context(
        graph,
        local_order,
        local_evidence,
        graph_fingerprint=graph_fingerprint,
    )
    claim_edges = _canonical_claim_edges(
        near_equal_domain_claim_edges,
        graph_edges=graph.edges_ij,
        point_count=graph.point_count,
    )

    decisions = tuple(
        _classify_edge(
            left,
            right,
            local_order=local_order,
            local_evidence=local_evidence,
            settings=settings,
            near_equal_domain_claim=(left, right) in claim_edges,
        )
        for left, right in graph.edges_ij
    )
    edge_decisions = tuple(item.decision for item in decisions)
    return LatticeDomainEdgeCompatibilityField(
        source_ids=graph.point_ids,
        point_count=graph.point_count,
        edges_ij=graph.edges_ij,
        endpoint_models=tuple(
            (local_evidence.best_model[left], local_evidence.best_model[right])
            for left, right in graph.edges_ij
        ),
        decision=edge_decisions,
        retained_for_domain_growth=tuple(
            lattice_domain_edge_is_retained(decision)
            for decision in edge_decisions
        ),
        core_connectivity_eligible=tuple(
            lattice_domain_edge_is_core_eligible(
                item.decision,
                classification_confidence=(
                    item.metrics.minimum_classification_confidence
                ),
                m3_orientation_confidence=(
                    item.metrics.minimum_m3_orientation_confidence
                ),
                m6_orientation_confidence=(
                    item.metrics.minimum_m6_orientation_confidence
                ),
                settings=settings,
            )
            for item in decisions
        ),
        rejection_reason=tuple(item.rejection_reason for item in decisions),
        theta3_delta_deg=tuple(item.metrics.theta3_delta_deg for item in decisions),
        theta6_delta_deg=tuple(item.metrics.theta6_delta_deg for item in decisions),
        model_profile_distance=tuple(
            item.metrics.model_profile_distance for item in decisions
        ),
        minimum_endpoint_classification_confidence=tuple(
            item.metrics.minimum_classification_confidence for item in decisions
        ),
        minimum_endpoint_m3_orientation_confidence=tuple(
            item.metrics.minimum_m3_orientation_confidence for item in decisions
        ),
        minimum_endpoint_m6_orientation_confidence=tuple(
            item.metrics.minimum_m6_orientation_confidence for item in decisions
        ),
        settings=settings,
        first_shell_graph_fingerprint=graph_fingerprint,
        local_order_analysis_fingerprint=(
            local_order.provenance.analysis_settings_fingerprint
        ),
        local_symmetry_evidence_settings_fingerprint=(
            local_evidence.settings_fingerprint
        ),
        local_symmetry_bond_evidence_fingerprint=(
            local_evidence.bond_evidence_fingerprint
        ),
        settings_fingerprint=lattice_domain_edge_settings_fingerprint(settings),
    )


def _classify_edge(
    left: int,
    right: int,
    *,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    settings: LatticeDomainEdgeCompatibilitySettings,
    near_equal_domain_claim: bool,
) -> _EdgeDecision:
    left_model = local_evidence.best_model[left]
    right_model = local_evidence.best_model[right]
    theta3_delta = _orientation_delta(
        local_order.theta3_lattice_deg[left],
        local_order.theta3_lattice_deg[right],
    )
    theta6_delta = _orientation_delta(
        local_order.theta6_deg[left],
        local_order.theta6_deg[right],
    )
    profile_distance = _model_profile_distance(
        left,
        right,
        local_evidence=local_evidence,
    )
    classification_confidence = _minimum_optional(
        local_evidence.classification_confidence[left],
        local_evidence.classification_confidence[right],
    )
    m3_orientation_confidence = _minimum_optional(
        local_order.m3_orientation_confidence[left],
        local_order.m3_orientation_confidence[right],
    )
    m6_orientation_confidence = _minimum_optional(
        local_order.m6_orientation_confidence[left],
        local_order.m6_orientation_confidence[right],
    )
    metrics = _EdgeMetrics(
        theta3_delta_deg=theta3_delta,
        theta6_delta_deg=theta6_delta,
        model_profile_distance=profile_distance,
        minimum_classification_confidence=classification_confidence,
        minimum_m3_orientation_confidence=m3_orientation_confidence,
        minimum_m6_orientation_confidence=m6_orientation_confidence,
    )
    if "unavailable" in {left_model, right_model}:
        return _EdgeDecision(
            "no_domain_edge",
            "endpoint_unavailable",
            metrics,
        )
    if near_equal_domain_claim:
        return _EdgeDecision(
            "boundary_unassigned",
            "near_equal_domain_claim",
            metrics,
        )
    if "disordered" in {left_model, right_model}:
        return _EdgeDecision(
            "no_domain_edge",
            "endpoint_disordered",
            metrics,
        )

    model_pair = frozenset((left_model, right_model))
    if left_model == right_model and left_model in _CHANNEL_POLICIES:
        channel = cast(_Channel, left_model)
        channel_comparison = _channel_comparison(
            channel,
            metrics=metrics,
            settings=settings,
        )
        channel_policy = _CHANNEL_POLICIES[channel]
        return _same_channel_decision(
            delta=channel_comparison.delta_deg,
            tolerance=channel_comparison.tolerance_deg,
            compatible_decision=channel_policy.compatible_decision,
            mismatch_reason=channel_policy.mismatch_reason,
            metrics=metrics,
        )
    if left_model == right_model == "mixed":
        if theta3_delta is None or theta6_delta is None:
            return _EdgeDecision(
                "conflict_boundary",
                "missing_compatible_orientation_channel",
                metrics,
            )
        if (
            theta3_delta > settings.trifold_orientation_tolerance_deg
            or theta6_delta > settings.sixfold_orientation_tolerance_deg
        ):
            return _EdgeDecision(
                "conflict_boundary",
                "mixed_orientation_mismatch",
                metrics,
            )
        if (
            profile_distance is None
            or profile_distance > settings.mixed_model_profile_tolerance
        ):
            return _EdgeDecision(
                "conflict_boundary",
                "mixed_model_profile_mismatch",
                metrics,
            )
        return _EdgeDecision(
            "compatible_mixed",
            None,
            metrics,
        )
    if model_pair == {"trifold", "sixfold"}:
        return _EdgeDecision(
            "conflict_boundary",
            "incompatible_symmetry_models",
            metrics,
        )
    if "ambiguous" in model_pair:
        return _conditional_ambiguous_decision(
            left_model=left_model,
            right_model=right_model,
            settings=settings,
            metrics=metrics,
        )
    if "mixed" in model_pair:
        return _conditional_mixed_decision(
            left,
            right,
            left_model=left_model,
            right_model=right_model,
            local_evidence=local_evidence,
            settings=settings,
            metrics=metrics,
        )
    return _EdgeDecision(
        "conflict_boundary",
        "incompatible_symmetry_models",
        metrics,
    )


def _same_channel_decision(
    *,
    delta: float | None,
    tolerance: float,
    compatible_decision: LatticeDomainEdgeDecision,
    mismatch_reason: LatticeDomainEdgeRejectionReason,
    metrics: _EdgeMetrics,
) -> _EdgeDecision:
    if delta is None:
        return _EdgeDecision(
            "conflict_boundary",
            "missing_compatible_orientation_channel",
            metrics,
        )
    if delta > tolerance:
        return _EdgeDecision(
            "conflict_boundary",
            mismatch_reason,
            metrics,
        )
    return _EdgeDecision(
        compatible_decision,
        None,
        metrics,
    )


def _conditional_mixed_decision(
    left: int,
    right: int,
    *,
    left_model: LocalSymmetryModel,
    right_model: LocalSymmetryModel,
    local_evidence: LocalSymmetryEvidenceField,
    settings: LatticeDomainEdgeCompatibilitySettings,
    metrics: _EdgeMetrics,
) -> _EdgeDecision:
    mixed_index = left if left_model == "mixed" else right
    ordered_model = right_model if left_model == "mixed" else left_model
    if ordered_model not in _CHANNEL_POLICIES:
        return _EdgeDecision(
            "conflict_boundary",
            "incompatible_symmetry_models",
            metrics,
        )
    channel = cast(_Channel, ordered_model)
    channel_comparison = _channel_comparison(
        channel,
        metrics=metrics,
        settings=settings,
    )
    delta = channel_comparison.delta_deg
    tolerance = channel_comparison.tolerance_deg
    score = _channel_model_score(local_evidence, channel, mixed_index)
    if delta is None:
        reason: LatticeDomainEdgeRejectionReason = (
            "missing_compatible_orientation_channel"
        )
    elif score is None or score < settings.conditional_channel_minimum_score:
        reason = "conditional_channel_too_weak"
    elif delta > tolerance:
        reason = "no_compatible_conditional_channel"
    else:
        return _EdgeDecision(
            "conditional_halo_edge",
            None,
            metrics,
        )
    return _EdgeDecision(
        "conflict_boundary",
        reason,
        metrics,
    )


def _conditional_ambiguous_decision(
    *,
    left_model: LocalSymmetryModel,
    right_model: LocalSymmetryModel,
    settings: LatticeDomainEdgeCompatibilitySettings,
    metrics: _EdgeMetrics,
) -> _EdgeDecision:
    other_models = tuple(
        model for model in (left_model, right_model) if model != "ambiguous"
    )
    channels: tuple[_Channel, ...]
    if not other_models or other_models[0] == "mixed":
        channels = ("trifold", "sixfold")
    elif other_models[0] in {"trifold", "sixfold"}:
        channels = (other_models[0],)
    else:
        channels = ()
    defined_channel_seen = False
    for channel in channels:
        channel_comparison = _channel_comparison(
            channel,
            metrics=metrics,
            settings=settings,
        )
        delta = channel_comparison.delta_deg
        if delta is None:
            continue
        defined_channel_seen = True
        if delta <= channel_comparison.tolerance_deg:
            return _EdgeDecision(
                "conditional_halo_edge",
                None,
                metrics,
            )
    if not defined_channel_seen:
        reason: LatticeDomainEdgeRejectionReason = (
            "missing_compatible_orientation_channel"
        )
    else:
        reason = "no_compatible_conditional_channel"
    return _EdgeDecision(
        "conflict_boundary",
        reason,
        metrics,
    )


def _channel_comparison(
    channel: _Channel,
    *,
    metrics: _EdgeMetrics,
    settings: LatticeDomainEdgeCompatibilitySettings,
) -> _ChannelComparison:
    policy = _CHANNEL_POLICIES[channel]
    return _ChannelComparison(
        delta_deg=getattr(metrics, policy.delta_metric_field),
        tolerance_deg=getattr(settings, policy.tolerance_setting_field),
    )


def _channel_model_score(
    evidence: LocalSymmetryEvidenceField,
    channel: _Channel,
    point_index: int,
) -> float | None:
    values = getattr(evidence, _CHANNEL_POLICIES[channel].model_score_field)
    return values[point_index]


def _orientation_delta(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return m3_lattice_orientation_distance_deg(left, right)


def _model_profile_distance(
    left: int,
    right: int,
    *,
    local_evidence: LocalSymmetryEvidenceField,
) -> float | None:
    differences: list[float] = []
    for field_name in _MODEL_PROFILE_FIELDS:
        values = getattr(local_evidence, field_name)
        if values[left] is None or values[right] is None:
            return None
        differences.append(abs(values[left] - values[right]))
    return max(differences, default=0.0)


def _minimum_optional(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return min(left, right)


def _validate_context(
    graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
    local_evidence: LocalSymmetryEvidenceField,
    *,
    graph_fingerprint: str,
) -> None:
    if (
        local_order.source_ids != graph.point_ids
        or local_evidence.source_ids != graph.point_ids
        or local_order.point_count != graph.point_count
        or local_evidence.point_count != graph.point_count
    ):
        raise ValueError("Local symmetry results must preserve first-shell graph point order.")
    if (
        local_order.provenance.first_shell_graph_fingerprint != graph_fingerprint
        or local_evidence.first_shell_graph_fingerprint != graph_fingerprint
    ):
        raise ValueError("Local symmetry results must reference the same first-shell graph.")
    if (
        local_evidence.local_order_analysis_fingerprint
        != local_order.provenance.analysis_settings_fingerprint
    ):
        raise ValueError("Local evidence must reference the supplied local-order analysis.")
    if local_evidence.edge_truncated_neighborhood != local_order.edge_truncated_neighborhood:
        raise ValueError("Local symmetry edge QC fields must agree.")


def _canonical_claim_edges(
    raw_edges: Iterable[tuple[int, int]],
    *,
    graph_edges: tuple[tuple[int, int], ...],
    point_count: int,
) -> frozenset[tuple[int, int]]:
    normalized: set[tuple[int, int]] = set()
    for edge_index, raw_edge in enumerate(raw_edges):
        edge = tuple(raw_edge)
        if len(edge) != 2:
            raise ValueError(
                f"near_equal_domain_claim_edges[{edge_index}] must contain two indices."
            )
        left, right = edge
        if (
            isinstance(left, bool)
            or isinstance(right, bool)
            or not isinstance(left, int)
            or not isinstance(right, int)
        ):
            raise TypeError("Near-equal domain claim edge indices must be integers.")
        if not 0 <= left < point_count or not 0 <= right < point_count or left == right:
            raise ValueError("Near-equal domain claim edges must reference distinct points.")
        normalized.add((min(left, right), max(left, right)))
    if not normalized.issubset(set(graph_edges)):
        raise ValueError("Near-equal domain claim edges must be first-shell graph edges.")
    return frozenset(normalized)
