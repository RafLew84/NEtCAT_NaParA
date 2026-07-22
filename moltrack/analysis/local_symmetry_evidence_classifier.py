"""Robust local directional-model fitting for M3/M6 evidence fusion."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from math import atan2, cos, degrees, exp, hypot, isfinite, radians, sin

from ._first_shell_graph_fingerprint import first_shell_graph_fingerprint
from .first_shell_graph import FirstShellGraph
from .local_multisymmetry_bond_order import LocalMultiSymmetryBondOrderField
from .local_symmetry_evidence_models import (
    LocalSymmetryClassificationReason,
    LocalSymmetryEvidenceField,
    LocalSymmetryEvidenceSettings,
    LocalSymmetryModel,
    local_symmetry_evidence_settings_fingerprint,
)


@dataclass(frozen=True)
class _BondObservation:
    angle_deg: float
    weight: float
    uncertainty_deg: float


@dataclass(frozen=True)
class _ModelFit:
    score: float
    orientation_deg: float | None
    coverage: float


@dataclass(frozen=True)
class _PointClassification:
    trifold_score: float | None
    sixfold_score: float | None
    mixed_score: float | None
    disordered_score: float | None
    best_model: LocalSymmetryModel
    second_best_margin: float | None
    observed_direction_count: int
    expected_direction_coverage: float | None
    confidence: float | None
    reason: LocalSymmetryClassificationReason
    orientation_deg: float | None


def classify_local_symmetry_evidence(
    graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
    *,
    settings: LocalSymmetryEvidenceSettings | None = None,
    bond_weights: Sequence[float] | None = None,
    bond_angular_uncertainty_deg: Sequence[float] | None = None,
) -> LocalSymmetryEvidenceField:
    """Fit trifold, sixfold, mixed, and disordered models per graph point.

    The fitted scores describe the directional pattern of retained first-shell
    bonds. They deliberately remain separate from raw q3/q6 amplitudes.
    """

    if not isinstance(graph, FirstShellGraph):
        raise TypeError("graph must be a FirstShellGraph.")
    if not isinstance(local_order, LocalMultiSymmetryBondOrderField):
        raise TypeError("local_order must be a LocalMultiSymmetryBondOrderField.")
    if settings is None:
        settings = LocalSymmetryEvidenceSettings()
    if not isinstance(settings, LocalSymmetryEvidenceSettings):
        raise TypeError("settings must be LocalSymmetryEvidenceSettings.")

    graph_fingerprint = first_shell_graph_fingerprint(graph)
    _validate_inputs(graph, local_order, graph_fingerprint=graph_fingerprint)
    weights = _normalized_edge_values(
        bond_weights,
        edge_count=len(graph.edges_ij),
        field_name="bond_weights",
        default=1.0,
        maximum=None,
    )
    uncertainties = _normalized_edge_values(
        bond_angular_uncertainty_deg,
        edge_count=len(graph.edges_ij),
        field_name="bond_angular_uncertainty_deg",
        default=0.0,
        maximum=60.0,
    )
    if weights and not any(weight > 0.0 for weight in weights):
        raise ValueError("bond_weights must contain at least one positive value.")
    if weights:
        maximum_weight = max(weights)
        weights = tuple(weight / maximum_weight for weight in weights)

    observations: list[list[_BondObservation]] = [
        [] for _ in range(graph.point_count)
    ]
    for edge_index, ((left, right), angle_rad) in enumerate(
        zip(graph.edges_ij, graph.angles_rad)
    ):
        angle_deg = degrees(angle_rad) % 360.0
        observation = _BondObservation(
            angle_deg=angle_deg,
            weight=weights[edge_index],
            uncertainty_deg=uncertainties[edge_index],
        )
        reverse_observation = _BondObservation(
            angle_deg=(angle_deg + 180.0) % 360.0,
            weight=weights[edge_index],
            uncertainty_deg=uncertainties[edge_index],
        )
        observations[left].append(observation)
        observations[right].append(reverse_observation)

    point_results = tuple(
        _classify_point(
            tuple(point_observations),
            available=local_order.computation_status[index] == "valid_order",
            harmonic_orientation_available=(
                local_order.m3_orientation_status[index] == "defined"
                or local_order.m6_orientation_status[index] == "defined"
            ),
            edge_truncated=local_order.edge_truncated_neighborhood[index],
            settings=settings,
        )
        for index, point_observations in enumerate(observations)
    )
    return LocalSymmetryEvidenceField(
        source_ids=local_order.source_ids,
        point_count=local_order.point_count,
        trifold_model_score=tuple(item.trifold_score for item in point_results),
        sixfold_model_score=tuple(item.sixfold_score for item in point_results),
        mixed_model_score=tuple(item.mixed_score for item in point_results),
        disordered_model_score=tuple(item.disordered_score for item in point_results),
        best_model=tuple(item.best_model for item in point_results),
        second_best_margin=tuple(item.second_best_margin for item in point_results),
        observed_direction_count=tuple(
            item.observed_direction_count for item in point_results
        ),
        expected_direction_coverage=tuple(
            item.expected_direction_coverage for item in point_results
        ),
        classification_confidence=tuple(
            item.confidence for item in point_results
        ),
        classification_reason=tuple(item.reason for item in point_results),
        winning_model_orientation_deg=tuple(
            item.orientation_deg for item in point_results
        ),
        edge_truncated_neighborhood=local_order.edge_truncated_neighborhood,
        first_shell_graph_fingerprint=graph_fingerprint,
        local_order_analysis_fingerprint=(
            local_order.provenance.analysis_settings_fingerprint
        ),
        settings_fingerprint=local_symmetry_evidence_settings_fingerprint(settings),
        bond_evidence_fingerprint=_bond_evidence_fingerprint(
            weights=weights,
            uncertainties=uncertainties,
        ),
    )


def _classify_point(
    observations: tuple[_BondObservation, ...],
    *,
    available: bool,
    harmonic_orientation_available: bool,
    edge_truncated: bool,
    settings: LocalSymmetryEvidenceSettings,
) -> _PointClassification:
    positive_observations = tuple(item for item in observations if item.weight > 0.0)
    maximum_weight = max(
        (item.weight for item in positive_observations),
        default=0.0,
    )
    active_observations = tuple(
        item
        for item in positive_observations
        if item.weight >= maximum_weight * settings.minimum_relative_bond_weight
    )
    observed_count = _observed_direction_count(
        active_observations,
        settings=settings,
    )
    if (
        not available
        or observed_count < settings.minimum_observed_directions
        or not active_observations
    ):
        return _unavailable_point(observed_count)

    trifold = _fit_periodic_model(
        active_observations,
        direction_count=3,
        edge_truncated=edge_truncated,
        settings=settings,
    )
    sixfold = _fit_periodic_model(
        active_observations,
        direction_count=6,
        edge_truncated=edge_truncated,
        settings=settings,
    )
    mixed = _fit_mixed_model(
        active_observations,
        edge_truncated=edge_truncated,
        settings=settings,
    )
    best_periodic_score = max(trifold.score, sixfold.score, mixed.score)
    # The null model must remain competitive when a periodic fit obtains a
    # middling score merely by filling most angular slots. The configured
    # rejection power keeps near-ideal periodic evidence dominant while
    # exposing broad, systematic residuals as disorder.
    disorder_support = 1.0 - best_periodic_score ** (
        settings.disordered_periodic_rejection_power
    )
    direction_support = min(
        1.0,
        observed_count / settings.disordered_reference_direction_count,
    )
    disordered_score = _clamp_unit(disorder_support * direction_support)

    candidates: list[tuple[LocalSymmetryModel, _ModelFit]] = [
        ("trifold", trifold),
        ("sixfold", sixfold),
        (
            "disordered",
            _ModelFit(
                score=disordered_score,
                orientation_deg=None,
                coverage=direction_support,
            ),
        ),
    ]
    best_single_score = max(trifold.score, sixfold.score)
    if mixed.score >= best_single_score + settings.mixed_minimum_improvement:
        candidates.append(("mixed", mixed))

    ordered = sorted(candidates, key=lambda item: (-item[1].score, item[0]))
    winner_model, winner_fit = ordered[0]
    all_model_scores = {
        "trifold": trifold.score,
        "sixfold": sixfold.score,
        "mixed": mixed.score,
        "disordered": disordered_score,
    }
    second_best_score = max(
        score for model, score in all_model_scores.items() if model != winner_model
    )
    margin = _clamp_unit(winner_fit.score - second_best_score)
    scores = (trifold.score, sixfold.score, mixed.score, disordered_score)
    common = dict(
        trifold_score=scores[0],
        sixfold_score=scores[1],
        mixed_score=scores[2],
        disordered_score=scores[3],
        second_best_margin=margin,
        observed_direction_count=observed_count,
        expected_direction_coverage=winner_fit.coverage,
    )

    if not harmonic_orientation_available:
        return _ambiguous_point(
            reason="order_amplitudes_below_threshold",
            **common,
        )
    if winner_fit.score < settings.minimum_model_score:
        return _ambiguous_point(
            reason="below_minimum_model_score",
            **common,
        )
    if margin < settings.minimum_second_best_margin:
        return _ambiguous_point(reason="below_minimum_margin", **common)
    if (
        winner_model in {"trifold", "sixfold", "mixed"}
        and winner_fit.coverage < settings.minimum_expected_direction_coverage
        and not edge_truncated
    ):
        return _ambiguous_point(
            reason="insufficient_direction_coverage",
            **common,
        )

    confidence = _clamp_unit(
        winner_fit.score
        * min(1.0, margin / settings.confident_margin)
        * (settings.edge_confidence_factor if edge_truncated else 1.0)
    )
    reason_by_model: dict[LocalSymmetryModel, LocalSymmetryClassificationReason] = {
        "trifold": "classified_trifold",
        "sixfold": "classified_sixfold",
        "mixed": "classified_mixed",
        "disordered": "classified_disordered",
    }
    return _PointClassification(
        best_model=winner_model,
        confidence=confidence,
        reason=reason_by_model[winner_model],
        orientation_deg=winner_fit.orientation_deg,
        **common,
    )


def _fit_periodic_model(
    observations: tuple[_BondObservation, ...],
    *,
    direction_count: int,
    edge_truncated: bool,
    settings: LocalSymmetryEvidenceSettings,
) -> _ModelFit:
    period_deg = 360.0 / direction_count
    candidate_values = {
        observation.angle_deg % period_deg for observation in observations
    }
    mean_orientation = _weighted_periodic_mean_deg(
        observations,
        direction_count=direction_count,
    )
    if mean_orientation is not None:
        candidate_values.add(mean_orientation)
    candidates = tuple(sorted(candidate_values))
    best: _ModelFit | None = None
    for orientation_deg in candidates:
        quality_sum = 0.0
        weight_sum = 0.0
        occupied_slots: set[int] = set()
        for observation in observations:
            residual = _periodic_distance_deg(
                observation.angle_deg,
                orientation_deg,
                period_deg,
            )
            sigma = _effective_sigma(observation, settings=settings)
            reliability = settings.base_angular_tolerance_deg / sigma
            quality_sum += (
                observation.weight
                * reliability
                * exp(-0.5 * (residual / sigma) ** 2)
            )
            weight_sum += observation.weight
            if residual <= settings.inlier_sigma_multiplier * sigma:
                occupied_slots.add(
                    round((observation.angle_deg - orientation_deg) / period_deg)
                    % direction_count
                )
        coverage = len(occupied_slots) / direction_count
        effective_coverage = _effective_coverage(
            coverage,
            edge_truncated=edge_truncated,
            settings=settings,
        )
        fit_quality = quality_sum / weight_sum
        score = _clamp_unit(
            fit_quality
            * (
                1.0
                - settings.coverage_weight
                + settings.coverage_weight * effective_coverage
            )
        )
        fit = _ModelFit(
            score=score,
            orientation_deg=orientation_deg,
            coverage=coverage,
        )
        if best is None or (fit.score, -fit.orientation_deg) > (
            best.score,
            -best.orientation_deg,
        ):
            best = fit
    if best is None:
        return _ModelFit(score=0.0, orientation_deg=None, coverage=0.0)
    return best


def _fit_mixed_model(
    observations: tuple[_BondObservation, ...],
    *,
    edge_truncated: bool,
    settings: LocalSymmetryEvidenceSettings,
) -> _ModelFit:
    trifold_candidates = tuple(
        sorted({observation.angle_deg % 120.0 for observation in observations})
    )
    sixfold_candidates = tuple(
        sorted({observation.angle_deg % 60.0 for observation in observations})
    )
    best = _ModelFit(score=0.0, orientation_deg=None, coverage=0.0)
    for trifold_orientation in trifold_candidates:
        for sixfold_orientation in sixfold_candidates:
            quality_sum = 0.0
            weight_sum = 0.0
            trifold_slots: set[int] = set()
            sixfold_slots: set[int] = set()
            for observation in observations:
                sigma = _effective_sigma(observation, settings=settings)
                trifold_residual = _periodic_distance_deg(
                    observation.angle_deg,
                    trifold_orientation,
                    120.0,
                )
                sixfold_residual = _periodic_distance_deg(
                    observation.angle_deg,
                    sixfold_orientation,
                    60.0,
                )
                if trifold_residual < sixfold_residual:
                    residual = trifold_residual
                    if residual <= settings.inlier_sigma_multiplier * sigma:
                        trifold_slots.add(
                            round(
                                (observation.angle_deg - trifold_orientation) / 120.0
                            )
                            % 3
                        )
                else:
                    residual = sixfold_residual
                    if residual <= settings.inlier_sigma_multiplier * sigma:
                        sixfold_slots.add(
                            round(
                                (observation.angle_deg - sixfold_orientation) / 60.0
                            )
                            % 6
                        )
                reliability = settings.base_angular_tolerance_deg / sigma
                quality_sum += (
                    observation.weight
                    * reliability
                    * exp(-0.5 * (residual / sigma) ** 2)
                )
                weight_sum += observation.weight
            if not trifold_slots or not sixfold_slots:
                continue
            coverage = (len(trifold_slots) + len(sixfold_slots)) / 9.0
            effective_coverage = _effective_coverage(
                coverage,
                edge_truncated=edge_truncated,
                settings=settings,
            )
            fit_quality = quality_sum / weight_sum
            score = _clamp_unit(
                fit_quality
                * (
                    1.0
                    - settings.coverage_weight
                    + settings.coverage_weight * effective_coverage
                )
                - settings.mixed_complexity_penalty
            )
            if score > best.score:
                best = _ModelFit(score=score, orientation_deg=None, coverage=coverage)
    return best


def _observed_direction_count(
    observations: tuple[_BondObservation, ...],
    *,
    settings: LocalSymmetryEvidenceSettings,
) -> int:
    ordered = sorted(observations, key=lambda observation: observation.angle_deg)
    if not ordered:
        return 0
    clusters: list[list[_BondObservation]] = [[ordered[0]]]
    for observation in ordered[1:]:
        previous = clusters[-1][-1]
        if _directions_are_indistinguishable(
            previous,
            observation,
            gap_deg=observation.angle_deg - previous.angle_deg,
            settings=settings,
        ):
            clusters[-1].append(observation)
        else:
            clusters.append([observation])
    if (
        len(clusters) > 1
        and _directions_are_indistinguishable(
            clusters[-1][-1],
            clusters[0][0],
            gap_deg=(
                clusters[0][0].angle_deg
                + 360.0
                - clusters[-1][-1].angle_deg
            ),
            settings=settings,
        )
    ):
        clusters[0] = clusters[-1] + clusters[0]
        clusters.pop()
    return len(clusters)


def _directions_are_indistinguishable(
    first: _BondObservation,
    second: _BondObservation,
    *,
    gap_deg: float,
    settings: LocalSymmetryEvidenceSettings,
) -> bool:
    uncertainty_allowance = hypot(
        first.uncertainty_deg,
        second.uncertainty_deg,
    )
    threshold = min(
        60.0,
        settings.direction_merge_tolerance_deg + uncertainty_allowance,
    )
    return gap_deg <= threshold


def _weighted_periodic_mean_deg(
    observations: tuple[_BondObservation, ...],
    *,
    direction_count: int,
) -> float | None:
    x_component = sum(
        observation.weight
        * cos(direction_count * radians(observation.angle_deg))
        for observation in observations
    )
    y_component = sum(
        observation.weight
        * sin(direction_count * radians(observation.angle_deg))
        for observation in observations
    )
    total_weight = sum(observation.weight for observation in observations)
    if hypot(x_component, y_component) <= 1e-12 * total_weight:
        return None
    period_deg = 360.0 / direction_count
    return (degrees(atan2(y_component, x_component)) / direction_count) % period_deg


def _effective_sigma(
    observation: _BondObservation,
    *,
    settings: LocalSymmetryEvidenceSettings,
) -> float:
    return (
        settings.base_angular_tolerance_deg**2 + observation.uncertainty_deg**2
    ) ** 0.5


def _effective_coverage(
    coverage: float,
    *,
    edge_truncated: bool,
    settings: LocalSymmetryEvidenceSettings,
) -> float:
    if not edge_truncated:
        return coverage
    return coverage + (1.0 - coverage) * settings.edge_missing_coverage_relief


def _periodic_distance_deg(value: float, reference: float, period: float) -> float:
    difference = abs((value - reference) % period)
    return min(difference, period - difference)


def _unavailable_point(observed_count: int) -> _PointClassification:
    return _PointClassification(
        trifold_score=None,
        sixfold_score=None,
        mixed_score=None,
        disordered_score=None,
        best_model="unavailable",
        second_best_margin=None,
        observed_direction_count=observed_count,
        expected_direction_coverage=None,
        confidence=None,
        reason="local_order_unavailable",
        orientation_deg=None,
    )


def _ambiguous_point(
    *,
    trifold_score: float,
    sixfold_score: float,
    mixed_score: float,
    disordered_score: float,
    second_best_margin: float,
    observed_direction_count: int,
    expected_direction_coverage: float,
    reason: LocalSymmetryClassificationReason,
) -> _PointClassification:
    return _PointClassification(
        trifold_score=trifold_score,
        sixfold_score=sixfold_score,
        mixed_score=mixed_score,
        disordered_score=disordered_score,
        best_model="ambiguous",
        second_best_margin=second_best_margin,
        observed_direction_count=observed_direction_count,
        expected_direction_coverage=expected_direction_coverage,
        confidence=0.0,
        reason=reason,
        orientation_deg=None,
    )


def _validate_inputs(
    graph: FirstShellGraph,
    local_order: LocalMultiSymmetryBondOrderField,
    *,
    graph_fingerprint: str,
) -> None:
    if graph.point_count != local_order.point_count:
        raise ValueError("graph and local_order must have the same point count.")
    if graph.point_ids != local_order.source_ids:
        raise ValueError("graph point_ids must match local_order source_ids.")
    if local_order.provenance.first_shell_graph_fingerprint != graph_fingerprint:
        raise ValueError("local_order must originate from the supplied graph.")


def _normalized_edge_values(
    values: Sequence[float] | None,
    *,
    edge_count: int,
    field_name: str,
    default: float,
    maximum: float | None,
) -> tuple[float, ...]:
    if values is None:
        return (default,) * edge_count
    normalized = tuple(values)
    if len(normalized) != edge_count:
        raise ValueError(f"{field_name} must contain one value per graph edge.")
    result: list[float] = []
    for index, value in enumerate(normalized):
        if isinstance(value, bool):
            raise TypeError(f"{field_name}[{index}] must be a number.")
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise TypeError(f"{field_name}[{index}] must be a number.") from exc
        if not isfinite(number):
            raise ValueError(f"{field_name}[{index}] must be finite.")
        if number < 0.0 or (maximum is not None and number > maximum):
            upper = "" if maximum is None else f" and at most {maximum:g}"
            raise ValueError(
                f"{field_name}[{index}] must be non-negative{upper}."
            )
        result.append(number)
    return tuple(result)


def _bond_evidence_fingerprint(
    *,
    weights: tuple[float, ...],
    uncertainties: tuple[float, ...],
) -> str:
    payload = {
        "schema": "moltrack-local-symmetry-bond-evidence-v1",
        "weights": weights,
        "angular_uncertainties_deg": uncertainties,
    }
    return sha256(
        json.dumps(
            payload,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))
