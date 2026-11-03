"""Geometry-only lattice-row hypotheses for spatial domains."""

from __future__ import annotations

from math import atan2, cos, degrees, pi, radians, sin

import numpy as np

from .lattice_domain_models import (
    LatticeDomain,
    LatticeDomainAnalysis,
    LatticeDomainInternalBond,
    lattice_domain_analysis_fingerprint,
)
from .lattice_row_models import (
    LatticeDomainRowAssignment,
    LatticeRow,
    LatticeRowAssignmentAnalysis,
    LatticeRowAssignmentReason,
    LatticeRowAssignmentSettings,
    LatticeRowAxisCandidate,
    LatticeRowMemberAssignment,
    lattice_row_assignment_settings_fingerprint,
)


def build_lattice_row_assignment_analysis(
    lattice_domains: LatticeDomainAnalysis,
    *,
    settings: LatticeRowAssignmentSettings | None = None,
) -> LatticeRowAssignmentAnalysis:
    """Test every threefold-equivalent row axis in every lattice domain."""

    if not isinstance(lattice_domains, LatticeDomainAnalysis):
        raise TypeError(
            "lattice_domains must be LatticeDomainAnalysis."
        )
    if settings is None:
        settings = LatticeRowAssignmentSettings()
    if not isinstance(settings, LatticeRowAssignmentSettings):
        raise TypeError(
            "settings must be LatticeRowAssignmentSettings."
        )
    point_by_source_id = dict(
        zip(lattice_domains.source_ids, lattice_domains.points_xy_nm)
    )
    point_index_by_source_id = {
        source_id: point_index
        for point_index, source_id in enumerate(lattice_domains.source_ids)
    }
    assignments = tuple(
        sorted(
            (
                _assign_domain_rows(
                    component,
                    point_by_source_id=point_by_source_id,
                    point_index_by_source_id=point_index_by_source_id,
                    settings=settings,
                )
                for component in lattice_domains.components
            ),
            key=lambda value: value.lattice_domain_id,
        )
    )
    return LatticeRowAssignmentAnalysis(
        source_ids=lattice_domains.source_ids,
        point_count=lattice_domains.point_count,
        domain_assignments=assignments,
        settings=settings,
        coordinate_frame=lattice_domains.coordinate_frame,
        orientation_reference=lattice_domains.orientation_reference,
        spatial_calibration_fingerprint=(
            lattice_domains.spatial_calibration_fingerprint
        ),
        registration_fingerprint=lattice_domains.registration_fingerprint,
        point_coordinate_fingerprint=(
            lattice_domains.point_coordinate_fingerprint
        ),
        lattice_domain_analysis_fingerprint=(
            lattice_domain_analysis_fingerprint(lattice_domains)
        ),
        settings_fingerprint=(
            lattice_row_assignment_settings_fingerprint(settings)
        ),
    )


def _assign_domain_rows(
    domain: LatticeDomain,
    *,
    point_by_source_id: dict[str, tuple[float, float]],
    point_index_by_source_id: dict[str, int],
    settings: LatticeRowAssignmentSettings,
) -> LatticeDomainRowAssignment:
    bonds = domain.geometry.internal_first_shell_bonds
    if domain.molecule_count < settings.minimum_domain_molecule_count:
        return _unavailable(
            domain,
            reason="insufficient_domain_molecules",
        )
    if len(bonds) < settings.minimum_internal_bond_count:
        return _unavailable(
            domain,
            reason="insufficient_internal_first_shell_bonds",
        )
    axis_family = _candidate_axis_family(
        bonds,
        tolerance_deg=settings.axis_cluster_tolerance_deg,
    )
    if axis_family is None:
        return _unavailable(
            domain,
            reason="axis_family_unavailable",
        )
    axes, support_counts, coherence = axis_family
    if coherence < settings.minimum_axis_family_coherence:
        return _unavailable(
            domain,
            reason="axis_family_incoherent",
        )
    candidates: list[LatticeRowAxisCandidate] = []
    oriented_axes = _sample_oriented_axis_family_deg(axes)
    for candidate_index, (
        axis_angle,
        oriented_axis_angle,
        support_count,
    ) in enumerate(
        zip(axes, oriented_axes, support_counts)
    ):
        candidate = _build_candidate(
            candidate_index=candidate_index,
            axis_angle_deg=axis_angle,
            oriented_axis_angle_deg=oriented_axis_angle,
            axis_bond_support_count=support_count,
            domain=domain,
            point_by_source_id=point_by_source_id,
            point_index_by_source_id=point_index_by_source_id,
            settings=settings,
        )
        if candidate is None:
            return _unavailable(
                domain,
                reason="row_spacing_unavailable",
            )
        candidates.append(candidate)
    ranked = sorted(
        candidates,
        key=lambda value: (
            -value.score,
            value.axis_angle_deg,
            value.candidate_index,
        ),
    )
    best = ranked[0]
    second = ranked[1]
    margin = max(0.0, min(1.0, best.score - second.score))
    if best.score < settings.minimum_candidate_score:
        status = "unavailable"
        selected = None
        reason = "candidate_score_below_minimum"
    elif margin < settings.minimum_selection_margin:
        status = "ambiguous"
        selected = None
        reason = "symmetry_equivalent_axes_not_resolved"
    else:
        status = "available"
        selected = best.candidate_index
        reason = "unique_best_axis"
    return LatticeDomainRowAssignment(
        lattice_domain_id=domain.lattice_domain_id,
        molecule_count=domain.molecule_count,
        source_ids=domain.source_ids,
        status=status,
        candidates=tuple(candidates),
        selected_candidate_index=selected,
        selection_margin=margin,
        axis_family_coherence=coherence,
        reason=reason,
    )


def _candidate_axis_family(
    bonds: tuple[LatticeDomainInternalBond, ...],
    *,
    tolerance_deg: float,
) -> tuple[tuple[float, ...], tuple[int, ...], float] | None:
    angles = np.asarray(
        tuple(bond.axial_angle_deg for bond in bonds),
        dtype=np.float64,
    )
    if angles.size == 0:
        return None
    sixth_harmonic = np.exp(1j * np.deg2rad(6.0 * angles))
    mean_harmonic = np.mean(sixth_harmonic)
    coherence = min(1.0, max(0.0, float(abs(mean_harmonic))))
    if not np.isfinite(coherence) or coherence <= 1e-12:
        return None
    base_angle = (
        degrees(atan2(mean_harmonic.imag, mean_harmonic.real)) / 6.0
    ) % 60.0
    expected_axes = tuple(
        (base_angle + 60.0 * family_index) % 180.0
        for family_index in range(3)
    )
    clustered_angles: list[list[float]] = [[], [], []]
    for angle in angles:
        distances = tuple(
            _axial_angle_distance_deg(float(angle), expected)
            for expected in expected_axes
        )
        family_index = min(
            range(3),
            key=lambda index: (distances[index], index),
        )
        if distances[family_index] <= tolerance_deg:
            clustered_angles[family_index].append(float(angle))
    axes_with_support = []
    for expected, cluster in zip(expected_axes, clustered_angles):
        axis = (
            _axial_circular_mean_deg(cluster)
            if cluster
            else expected
        )
        axes_with_support.append((axis, len(cluster)))
    axes_with_support.sort(key=lambda value: value[0])
    return (
        tuple(value[0] for value in axes_with_support),
        tuple(value[1] for value in axes_with_support),
        coherence,
    )


def _build_candidate(
    *,
    candidate_index: int,
    axis_angle_deg: float,
    oriented_axis_angle_deg: float,
    axis_bond_support_count: int,
    domain: LatticeDomain,
    point_by_source_id: dict[str, tuple[float, float]],
    point_index_by_source_id: dict[str, int],
    settings: LatticeRowAssignmentSettings,
) -> LatticeRowAxisCandidate | None:
    angle_rad = radians(oriented_axis_angle_deg)
    tangent = np.asarray((cos(angle_rad), sin(angle_rad)))
    normal = np.asarray((-sin(angle_rad), cos(angle_rad)))
    spacing_values = []
    for bond in domain.geometry.internal_first_shell_bonds:
        if (
            _axial_angle_distance_deg(
                bond.axial_angle_deg,
                axis_angle_deg,
            )
            <= settings.axis_cluster_tolerance_deg
        ):
            continue
        left = np.asarray(point_by_source_id[bond.source_ids[0]])
        right = np.asarray(point_by_source_id[bond.source_ids[1]])
        projected = abs(float(np.dot(right - left, normal)))
        if projected > 1e-12:
            spacing_values.append(projected)
    if spacing_values:
        row_spacing = float(np.median(np.asarray(spacing_values)))
    else:
        row_spacing = float(
            np.median(
                np.asarray(
                    tuple(
                        bond.distance_nm
                        for bond in domain.geometry.internal_first_shell_bonds
                    ),
                    dtype=np.float64,
                )
            )
            * sin(pi / 3.0)
        )
    if not np.isfinite(row_spacing) or row_spacing <= 0.0:
        return None
    source_ids = tuple(sorted(domain.source_ids))
    points = np.asarray(
        tuple(point_by_source_id[source_id] for source_id in source_ids),
        dtype=np.float64,
    )
    along_coordinates = points @ tangent
    normal_coordinates = points @ normal
    phase = _periodic_phase(normal_coordinates, period=row_spacing)
    raw_row_indices = np.rint(
        (normal_coordinates - phase) / row_spacing
    ).astype(np.int64)
    row_indices = raw_row_indices
    row_origin = phase
    fitted_coordinates = (
        row_origin + row_indices.astype(np.float64) * row_spacing
    )
    residuals = np.abs(normal_coordinates - fitted_coordinates)
    tolerance_nm = (
        settings.row_residual_tolerance_fraction * row_spacing
    )
    inlier_count = int(np.count_nonzero(residuals <= tolerance_nm))
    inlier_fraction = inlier_count / len(source_ids)
    median_residual = float(np.median(residuals))
    median_residual_fraction = median_residual / row_spacing
    residual_quality = max(
        0.0,
        1.0
        - median_residual_fraction
        / settings.row_residual_tolerance_fraction,
    )
    score = min(1.0, max(0.0, inlier_fraction * residual_quality))
    member_assignments = tuple(
        LatticeRowMemberAssignment(
            point_index=point_index_by_source_id[source_id],
            source_id=source_id,
            row_index=int(row_index),
            row_parity=int(row_index) % 2,
            along_coordinate_nm=float(along_coordinate),
            normal_coordinate_nm=float(normal_coordinate),
            row_residual_nm=float(residual),
        )
        for (
            source_id,
            row_index,
            along_coordinate,
            normal_coordinate,
            residual,
        ) in zip(
            source_ids,
            row_indices,
            along_coordinates,
            normal_coordinates,
            residuals,
        )
    )
    rows = tuple(
        _build_row(
            row_index,
            member_assignments=member_assignments,
            row_origin_normal_nm=row_origin,
            row_spacing_nm=row_spacing,
        )
        for row_index in sorted(set(int(value) for value in row_indices))
    )
    return LatticeRowAxisCandidate(
        candidate_index=candidate_index,
        axis_angle_deg=axis_angle_deg,
        row_spacing_nm=row_spacing,
        row_origin_normal_nm=row_origin,
        axis_bond_support_count=axis_bond_support_count,
        axis_bond_support_fraction=(
            axis_bond_support_count
            / len(domain.geometry.internal_first_shell_bonds)
        ),
        assigned_molecule_count=len(source_ids),
        inlier_molecule_count=inlier_count,
        inlier_fraction=inlier_fraction,
        median_residual_nm=median_residual,
        median_residual_fraction=median_residual_fraction,
        score=score,
        source_ids=source_ids,
        member_assignments=member_assignments,
        rows=rows,
    )


def _build_row(
    row_index: int,
    *,
    member_assignments: tuple[LatticeRowMemberAssignment, ...],
    row_origin_normal_nm: float,
    row_spacing_nm: float,
) -> LatticeRow:
    members = tuple(
        value
        for value in member_assignments
        if value.row_index == row_index
    )
    return LatticeRow(
        row_index=row_index,
        parity=row_index % 2,
        point_indices=tuple(value.point_index for value in members),
        source_ids=tuple(value.source_id for value in members),
        normal_coordinate_nm=(
            row_origin_normal_nm + row_index * row_spacing_nm
        ),
        maximum_residual_nm=max(
            value.row_residual_nm for value in members
        ),
    )


def _periodic_phase(values: np.ndarray, *, period: float) -> float:
    phase_vectors = np.exp(1j * (2.0 * pi / period) * values)
    mean_phase = np.mean(phase_vectors)
    if abs(mean_phase) <= 1e-12:
        centered = np.mod(values + 0.5 * period, period) - 0.5 * period
        return float(np.median(centered))
    return float(
        atan2(mean_phase.imag, mean_phase.real)
        * period
        / (2.0 * pi)
    )


def _sample_oriented_axis_family_deg(
    axes_deg: tuple[float, ...],
) -> tuple[float, ...]:
    oriented = []
    for axis_angle_deg in axes_deg:
        angle_rad = radians(axis_angle_deg)
        normal = np.asarray((-sin(angle_rad), cos(angle_rad)))
        keep_direction = (
            normal[1] > 0.0
            or (
                abs(float(normal[1])) <= 1e-12
                and normal[0] >= 0.0
            )
        )
        oriented.append(
            axis_angle_deg
            if keep_direction
            else axis_angle_deg + 180.0
        )
    return tuple(oriented)


def _unavailable(
    domain: LatticeDomain,
    *,
    reason: LatticeRowAssignmentReason,
) -> LatticeDomainRowAssignment:
    return LatticeDomainRowAssignment(
        lattice_domain_id=domain.lattice_domain_id,
        molecule_count=domain.molecule_count,
        source_ids=domain.source_ids,
        status="unavailable",
        candidates=(),
        selected_candidate_index=None,
        selection_margin=None,
        axis_family_coherence=None,
        reason=reason,
    )


def _axial_circular_mean_deg(angles_deg: list[float]) -> float:
    values = np.asarray(angles_deg, dtype=np.float64)
    vectors = np.exp(1j * np.deg2rad(2.0 * values))
    mean_vector = np.mean(vectors)
    return (
        degrees(atan2(mean_vector.imag, mean_vector.real)) / 2.0
    ) % 180.0


def _axial_angle_distance_deg(first: float, second: float) -> float:
    difference = abs((first % 180.0) - (second % 180.0))
    return min(difference, 180.0 - difference)


__all__ = ["build_lattice_row_assignment_analysis"]
