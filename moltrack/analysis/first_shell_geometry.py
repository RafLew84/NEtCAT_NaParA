"""Compare and freeze fixed or adaptive first-shell geometry on Calibration."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass, replace
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING

from .domain_analysis import FirstShellGeometryPolicy
from .domain_analysis.fingerprints import canonical_sha256
from .first_shell_builder import build_first_shell_graph
from .first_shell_geometry_models import (
    FIRST_SHELL_ADAPTIVE_ALGORITHM_VERSION,
    FIRST_SHELL_GEOMETRY_EXPERIMENT_SCHEMA_VERSION,
    FirstShellGeometryDecision,
    FirstShellGeometryExperimentReport,
    FirstShellGeometryExperimentSettings,
    FirstShellGeometryMetric,
    FirstShellGeometryPolicyResult,
    FirstShellPairCorrelationEvidence,
    FirstShellPolicyMode,
    FirstShellStratumIdentity,
    FirstShellSymmetry,
    FrozenFirstShellGeometrySelection,
)
from .first_shell_suggestion import suggest_first_shell_r_max
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .pair_correlation import PairCorrelationResult
from .pair_correlation_aggregation import AggregatedPairCorrelationResult

if TYPE_CHECKING:
    from moltrack.persistence.m6_first_shell_reference import (
        M6FirstShellCalibrationReference,
        M6FirstShellReferenceFrame,
        M6FirstShellReferenceGroup,
    )


def run_first_shell_geometry_experiment(
    package_path: str | Path,
    settings: FirstShellGeometryExperimentSettings,
    *,
    pair_correlations: tuple[FirstShellPairCorrelationEvidence, ...],
) -> FirstShellGeometryExperimentReport:
    """Evaluate fixed and adaptive policies without exposing Validation rows."""

    if not isinstance(settings, FirstShellGeometryExperimentSettings):
        raise TypeError("settings must be FirstShellGeometryExperimentSettings.")
    evidence = _evidence_by_identity(pair_correlations)
    from moltrack.persistence.m6_first_shell_reference import (
        load_m6_first_shell_calibration_reference,
    )

    reference = load_m6_first_shell_calibration_reference(package_path)
    if any(
        value.dataset_version_id != reference.version_id
        for value in evidence.values()
    ):
        raise ValueError(
            "Pair-correlation evidence must match the immutable dataset version."
        )
    identities = {
        FirstShellStratumIdentity(group.measurement_group_id, frame.symmetry_class)
        for group in reference.groups
        for frame in group.frames
    }
    unknown = set(evidence).difference(identities)
    if unknown:
        raise ValueError("Pair-correlation evidence contains non-Calibration identities.")
    m6_settings = _m6_settings(settings)
    _validate_pair_correlation_context(reference, evidence, m6_settings)
    policies = _policies(settings)
    results = tuple(
        _evaluate_policy(reference, policy, m6_settings, evidence)
        for policy in policies
    )
    fingerprint = _fingerprint({
        "schema_version": FIRST_SHELL_GEOMETRY_EXPERIMENT_SCHEMA_VERSION,
        "dataset_version_fingerprint": reference.version_fingerprint,
        "validation_epoch_id": reference.validation_epoch_id,
        "settings": asdict(settings),
        "policy_result_fingerprints": [
            value.result_fingerprint for value in results
        ],
    })
    return FirstShellGeometryExperimentReport(
        package_path=reference.package_path,
        dataset_id=reference.dataset_id,
        dataset_version_id=reference.version_id,
        dataset_version_fingerprint=reference.version_fingerprint,
        validation_epoch_id=reference.validation_epoch_id,
        settings=settings,
        policy_results=results,
        experiment_fingerprint=fingerprint,
    )


def freeze_first_shell_geometry_policy(
    report: FirstShellGeometryExperimentReport,
    mode: FirstShellPolicyMode,
) -> FrozenFirstShellGeometrySelection:
    if not isinstance(report, FirstShellGeometryExperimentReport):
        raise TypeError("report must be a FirstShellGeometryExperimentReport.")
    result = report.result(mode)
    fingerprint = _fingerprint({
        "schema_version": "frozen-first-shell-geometry-v1",
        "dataset_version_fingerprint": report.dataset_version_fingerprint,
        "validation_epoch_id": report.validation_epoch_id,
        "graph_settings": asdict(report.settings.graph_settings),
        "policy_result_fingerprint": result.result_fingerprint,
    })
    return FrozenFirstShellGeometrySelection(
        package_path=report.package_path,
        dataset_id=report.dataset_id,
        dataset_version_id=report.dataset_version_id,
        dataset_version_fingerprint=report.dataset_version_fingerprint,
        validation_epoch_id=report.validation_epoch_id,
        graph_settings=report.settings.graph_settings,
        policy_result=result,
        geometry_fingerprint=fingerprint,
    )


def _policies(
    settings: FirstShellGeometryExperimentSettings,
) -> tuple[FirstShellGeometryPolicy, FirstShellGeometryPolicy]:
    fixed = FirstShellGeometryPolicy.fixed(
        r_min_nm=settings.fixed_r_min_nm,
        r_max_nm=settings.fixed_r_max_nm,
    )
    adaptive = FirstShellGeometryPolicy(
        mode="adaptive",
        fixed_r_min_nm=settings.fixed_r_min_nm,
        fixed_r_max_nm=settings.fixed_r_max_nm,
        algorithm_version=FIRST_SHELL_ADAPTIVE_ALGORITHM_VERSION,
        adaptive_parameters=(
            ("gr_bin_width_nm", settings.gr_bin_width_nm),
            ("gr_max_nm", settings.gr_max_nm),
            (
                "gr_min_expected_pair_exposure",
                settings.gr_min_expected_pair_exposure,
            ),
            ("gr_min_contributing_frames", settings.gr_min_contributing_frames),
            ("gr_smoothing_method", settings.gr_smoothing_method),
            ("gr_smoothing_width", settings.gr_smoothing_width),
            ("gr_peak_prominence", settings.gr_peak_prominence),
        ),
    )
    return fixed, adaptive


def _evaluate_policy(
    reference: M6FirstShellCalibrationReference,
    policy: FirstShellGeometryPolicy,
    settings: MolecularM6OrientationAnalysisSettings,
    evidence: dict[
        FirstShellStratumIdentity,
        FirstShellPairCorrelationEvidence,
    ],
) -> FirstShellGeometryPolicyResult:
    decisions = tuple(
        _decision(policy, settings, stratum, evidence.get(stratum))
        for stratum in sorted({
            FirstShellStratumIdentity(group.measurement_group_id, frame.symmetry_class)
            for group in reference.groups
            for frame in group.frames
        })
    )
    by_identity = {
        value.stratum: value
        for value in decisions
    }
    metrics = tuple(
        _metrics_for_group(
            group,
            symmetry,
            by_identity[FirstShellStratumIdentity(group.measurement_group_id, symmetry)],
            settings,
        )
        for group in reference.groups
        for symmetry in sorted({frame.symmetry_class for frame in group.frames})
    )
    fingerprint = _fingerprint({
        "policy": policy.to_payload(),
        "decisions": decisions,
        "metrics": metrics,
    })
    return FirstShellGeometryPolicyResult(policy, decisions, metrics, fingerprint)


def _decision(
    policy: FirstShellGeometryPolicy,
    settings: MolecularM6OrientationAnalysisSettings,
    stratum: FirstShellStratumIdentity,
    evidence: FirstShellPairCorrelationEvidence | None,
) -> FirstShellGeometryDecision:
    if policy.mode == "fixed":
        return FirstShellGeometryDecision(
            stratum=stratum,
            resolution="fixed_range",
            resolved_r_min_nm=policy.fixed_r_min_nm,
            resolved_r_max_nm=policy.fixed_r_max_nm,
            fallback_reason=None,
            evidence_fingerprint=_fingerprint({
                "policy": policy.to_payload(),
                "stratum": stratum,
            }),
        )
    if evidence is None or evidence.pair_correlation is None:
        reason = (
            "pair_correlation_evidence_missing"
            if evidence is None
            else evidence.unavailable_reason
        )
        return FirstShellGeometryDecision(
            stratum=stratum,
            resolution="fixed_fallback",
            resolved_r_min_nm=policy.fixed_r_min_nm,
            resolved_r_max_nm=policy.fixed_r_max_nm,
            fallback_reason=reason,
            evidence_fingerprint=_fingerprint({
                "reason": reason,
                "stratum": stratum,
            }),
        )
    suggestion = suggest_first_shell_r_max(evidence.pair_correlation, settings=settings)
    suggested_maximum = suggestion.suggested_first_shell_r_max_nm
    if suggestion.quality_status != "valid_suggestion" or suggested_maximum is None:
        reason = f"g_r_{suggestion.quality_status}"
        return FirstShellGeometryDecision(
            stratum=stratum,
            resolution="fixed_fallback",
            resolved_r_min_nm=policy.fixed_r_min_nm,
            resolved_r_max_nm=policy.fixed_r_max_nm,
            fallback_reason=reason,
            evidence_fingerprint=_fingerprint(evidence.pair_correlation),
            suggestion=suggestion,
        )
    return FirstShellGeometryDecision(
        stratum=stratum,
        resolution="adaptive_g_r",
        resolved_r_min_nm=policy.fixed_r_min_nm,
        resolved_r_max_nm=suggested_maximum,
        fallback_reason=None,
        evidence_fingerprint=_fingerprint(evidence.pair_correlation),
        suggestion=suggestion,
    )


def _metrics_for_group(
    group: M6FirstShellReferenceGroup,
    symmetry: FirstShellSymmetry,
    decision: FirstShellGeometryDecision,
    settings: MolecularM6OrientationAnalysisSettings,
) -> FirstShellGeometryMetric:
    frames = tuple(frame for frame in group.frames if frame.symmetry_class == symmetry)
    reference_edges = {
        (frame.physical_frame_id, *edge)
        for frame in frames
        for edge in frame.manual_edges
    }
    predicted_edges = {
        (frame.physical_frame_id, *edge)
        for frame in frames
        for edge in _predicted_edges(frame, decision, settings)
    }
    true_positive = len(reference_edges.intersection(predicted_edges))
    precision = _ratio(true_positive, len(predicted_edges))
    recall = _ratio(true_positive, len(reference_edges))
    f1 = (
        None
        if precision is None or recall is None
        else 0.0
        if precision + recall == 0.0
        else 2.0 * precision * recall / (precision + recall)
    )
    available = bool(reference_edges)
    return FirstShellGeometryMetric(
        stratum=FirstShellStratumIdentity(group.measurement_group_id, symmetry),
        status="available" if available else "unavailable",
        reference_edge_count=len(reference_edges),
        predicted_edge_count=len(predicted_edges),
        true_positive_edge_count=true_positive,
        precision=precision if available else None,
        recall=recall if available else None,
        f1_score=f1 if available else None,
        unavailable_reason=None if available else "missing_manual_first_shell_edges",
    )


def _predicted_edges(
    frame: M6FirstShellReferenceFrame,
    decision: FirstShellGeometryDecision,
    settings: MolecularM6OrientationAnalysisSettings,
) -> tuple[tuple[str, str], ...]:
    graph = _reference_graph(
        frame,
        settings,
        r_min_nm=decision.resolved_r_min_nm,
        r_max_nm=decision.resolved_r_max_nm,
    )
    return tuple(
        (
            min(graph.point_ids[left], graph.point_ids[right]),
            max(graph.point_ids[left], graph.point_ids[right]),
        )
        for left, right in graph.edges_ij
    )


def _reference_graph(
    frame: M6FirstShellReferenceFrame,
    settings: MolecularM6OrientationAnalysisSettings,
    *,
    r_min_nm: float,
    r_max_nm: float,
):
    resolved = replace(
        settings,
        first_shell_r_min_nm=r_min_nm,
        first_shell_r_max_nm=r_max_nm,
    )
    return build_first_shell_graph(
        frame.points_xy_nm,
        point_ids=frame.source_ids,
        settings=resolved,
        spatial_calibration_fingerprint=frame.spatial_calibration_fingerprint,
        registration_fingerprint=frame.registration_fingerprint,
    )


def _m6_settings(
    value: FirstShellGeometryExperimentSettings,
) -> MolecularM6OrientationAnalysisSettings:
    return MolecularM6OrientationAnalysisSettings(
        duplicate_detection_enabled=(
            value.graph_settings.duplicate_detection_enabled
        ),
        duplicate_max_distance_nm=value.graph_settings.duplicate_max_distance_nm,
        first_shell_r_min_nm=value.fixed_r_min_nm,
        first_shell_r_max_nm=value.fixed_r_max_nm,
        geometry_absolute_tolerance_nm=(
            value.graph_settings.geometry_absolute_tolerance_nm
        ),
        geometry_relative_tolerance=value.graph_settings.geometry_relative_tolerance,
        gr_bin_width_nm=value.gr_bin_width_nm,
        gr_max_nm=value.gr_max_nm,
        gr_min_expected_pair_exposure=value.gr_min_expected_pair_exposure,
        gr_min_contributing_frames=value.gr_min_contributing_frames,
        gr_smoothing_method=value.gr_smoothing_method,
        gr_smoothing_width=value.gr_smoothing_width,
        gr_peak_prominence=value.gr_peak_prominence,
    )


def _evidence_by_identity(
    values: tuple[FirstShellPairCorrelationEvidence, ...],
) -> dict[
    FirstShellStratumIdentity,
    FirstShellPairCorrelationEvidence,
]:
    normalized = tuple(values)
    if any(not isinstance(value, FirstShellPairCorrelationEvidence) for value in normalized):
        raise TypeError("pair_correlations must contain FirstShellPairCorrelationEvidence.")
    by_identity: dict[
        FirstShellStratumIdentity,
        FirstShellPairCorrelationEvidence,
    ] = {
        value.stratum: value
        for value in normalized
    }
    if len(by_identity) != len(normalized):
        raise ValueError("Pair-correlation evidence identities must be unique.")
    return by_identity


def _validate_pair_correlation_context(
    reference: M6FirstShellCalibrationReference,
    evidence: dict[
        FirstShellStratumIdentity,
        FirstShellPairCorrelationEvidence,
    ],
    settings: MolecularM6OrientationAnalysisSettings,
) -> None:
    groups = {value.measurement_group_id: value for value in reference.groups}
    for stratum, value in evidence.items():
        result = value.pair_correlation
        if result is None:
            continue
        frames = tuple(
            frame
            for frame in groups[stratum.measurement_group_id].frames
            if frame.symmetry_class == stratum.symmetry_class
        )
        graphs = tuple(
            _reference_graph(
                frame,
                settings,
                r_min_nm=settings.first_shell_r_min_nm,
                r_max_nm=settings.first_shell_r_max_nm,
            )
            for frame in frames
        )
        valid = (
            _single_frame_context_matches(result, frames, graphs)
            if isinstance(result, PairCorrelationResult)
            else _aggregate_context_matches(result, frames, graphs)
        )
        if not valid:
            raise ValueError(
                "Adaptive g(r) evidence does not match the Calibration reference geometry."
            )


def _single_frame_context_matches(result, frames, graphs) -> bool:
    if len(frames) != 1:
        return False
    frame = frames[0]
    graph = graphs[0]
    representative_ids = tuple(
        point_id
        for point_id, representative_id in zip(
            graph.point_ids,
            graph.representative_source_ids,
        )
        if point_id == representative_id
    )
    return (
        result.frame_index == frame.working_frame_index
        and result.representative_point_ids == representative_ids
        and result.spatial_calibration_fingerprint
        == frame.spatial_calibration_fingerprint
        and result.registration_fingerprint == frame.registration_fingerprint
        and result.point_coordinate_fingerprint == graph.point_coordinate_fingerprint
    )


def _aggregate_context_matches(result, frames, graphs) -> bool:
    calibration = {frame.spatial_calibration_fingerprint for frame in frames}
    registration = {frame.registration_fingerprint for frame in frames}
    return (
        isinstance(result, AggregatedPairCorrelationResult)
        and result.frame_indices
        == tuple(frame.working_frame_index for frame in frames)
        and result.frame_point_counts
        == tuple(len(set(graph.representative_source_ids)) for graph in graphs)
        and result.frame_point_coordinate_fingerprints
        == tuple(graph.point_coordinate_fingerprint for graph in graphs)
        and len(calibration) == 1
        and result.spatial_calibration_fingerprint in calibration
        and len(registration) == 1
        and result.registration_fingerprint in registration
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _fingerprint(value: object) -> str:
    return canonical_sha256(_canonical(value))


def _canonical(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _canonical(asdict(value))
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, float) and not isfinite(value):
        return "nan" if value != value else "infinity" if value > 0 else "-infinity"
    if isinstance(value, Path):
        return value.as_posix()
    return value


__all__ = [
    "freeze_first_shell_geometry_policy",
    "run_first_shell_geometry_experiment",
]
