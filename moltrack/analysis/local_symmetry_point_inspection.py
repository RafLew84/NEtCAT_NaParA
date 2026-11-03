"""Read-only M3/M6 details for one selected molecular position."""

from __future__ import annotations

from dataclasses import dataclass

from .molecular_m6_analysis import MolecularM6OrientationAnalysis


@dataclass(frozen=True)
class LocalSymmetryPointInspection:
    source_id: str
    source_xy_px: tuple[float, float]
    q3: float | None
    m3_orientation_deg: float | None
    m3_orientation_status: str
    m3_orientation_confidence: float | None
    m3_sublattice_phase: int | None
    m3_sublattice_phase_status: str
    m3_phase_gauge_anchor: str | None
    q6: float | None
    m6_orientation_deg: float | None
    m6_orientation_status: str
    m6_orientation_confidence: float | None
    symmetry_model: str
    trifold_model_score: float | None
    sixfold_model_score: float | None
    mixed_model_score: float | None
    disordered_model_score: float | None
    symmetry_confidence: float | None
    symmetry_margin: float | None
    symmetry_reason: str
    observed_direction_count: int
    expected_direction_coverage: float | None
    neighbor_count: int
    computation_status: str
    edge_truncated_neighborhood: bool
    symmetry_resolvability_status: str


def build_local_symmetry_point_inspection(
    analysis: MolecularM6OrientationAnalysis,
    source_id: str,
) -> LocalSymmetryPointInspection | None:
    """Project a selected source ID from an already computed analysis result."""

    if not isinstance(analysis, MolecularM6OrientationAnalysis):
        raise TypeError("analysis must be MolecularM6OrientationAnalysis.")
    normalized_source_id = str(source_id)
    try:
        index = analysis.point_source_ids.index(normalized_source_id)
    except ValueError:
        return None
    local = analysis.local_multisymmetry_order
    evidence = analysis.local_symmetry_evidence
    if local is None or evidence is None:
        return None
    return LocalSymmetryPointInspection(
        source_id=normalized_source_id,
        source_xy_px=analysis.sample_coordinates.source_points_xy_px[index],
        q3=local.q3[index],
        m3_orientation_deg=local.theta3_lattice_deg[index],
        m3_orientation_status=local.m3_orientation_status[index],
        m3_orientation_confidence=local.m3_orientation_confidence[index],
        m3_sublattice_phase=local.m3_sublattice_phase[index],
        m3_sublattice_phase_status=local.m3_sublattice_phase_status[index],
        m3_phase_gauge_anchor=local.m3_phase_gauge_anchor[index],
        q6=local.q6[index],
        m6_orientation_deg=local.theta6_deg[index],
        m6_orientation_status=local.m6_orientation_status[index],
        m6_orientation_confidence=local.m6_orientation_confidence[index],
        symmetry_model=evidence.best_model[index],
        trifold_model_score=evidence.trifold_model_score[index],
        sixfold_model_score=evidence.sixfold_model_score[index],
        mixed_model_score=evidence.mixed_model_score[index],
        disordered_model_score=evidence.disordered_model_score[index],
        symmetry_confidence=evidence.classification_confidence[index],
        symmetry_margin=evidence.second_best_margin[index],
        symmetry_reason=evidence.classification_reason[index],
        observed_direction_count=evidence.observed_direction_count[index],
        expected_direction_coverage=evidence.expected_direction_coverage[index],
        neighbor_count=local.neighbor_count[index],
        computation_status=local.computation_status[index],
        edge_truncated_neighborhood=local.edge_truncated_neighborhood[index],
        symmetry_resolvability_status=local.symmetry_resolvability_status[index],
    )
