from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .orientation_domain_frame_aggregates import M6OrientationFrameAggregates


M6CurrentFrameQcStatus = Literal[
    "insufficient_bonds_for_length_stats",
    "bond_length_heterogeneity",
    "edge_truncated",
    "footprint_disconnected",
]


@dataclass(frozen=True)
class M6CurrentFrameDomainRow:
    """Presentation-neutral metrics for one ordered M6 component."""

    ordered_component_id: int
    m6_orientation_domain_id: int | None
    component_type: str
    molecule_count: int
    molecule_fraction_of_valid_representatives: float
    footprint_fraction_of_valid_fov: float | None
    footprint_area_nm2: float
    orientation_deg: float
    domain_mean_local_q6: float
    domain_coherent_q6: float
    domain_median_bond_length_nm: float | None
    domain_bond_length_mad_nm: float | None
    domain_bond_length_iqr_nm: float | None
    domain_bond_length_robust_cv: float | None
    qc_statuses: tuple[M6CurrentFrameQcStatus, ...]


@dataclass(frozen=True)
class M6CurrentFrameSummary:
    """Frame-level M6 values required for quantitative UI review."""

    mean_local_q6_interior: float | None
    mean_local_q6_all_valid: float | None
    global_q6_interior: float | None
    edge_truncated_fraction_of_valid_representatives: float | None
    full_domain_count: int
    small_ordered_island_count: int
    full_domain_molecule_fraction: float | None
    small_island_molecule_fraction: float | None
    unassigned_molecule_fraction: float | None
    full_domain_footprint_fraction: float | None
    small_island_footprint_fraction: float | None
    unassigned_supported_footprint_fraction: float | None
    unsupported_background_fraction: float | None
    duplicate_excluded_fraction_of_original: float | None
    invalid_position_fraction_of_original: float | None
    full_domain_molecule_weighted_coherent_q6: float | None
    full_domain_footprint_weighted_coherent_q6: float | None
    domain_molecule_entropy: float | None
    domain_footprint_entropy: float | None


@dataclass(frozen=True)
class M6CurrentFrameResults:
    domains: tuple[M6CurrentFrameDomainRow, ...]
    summary: M6CurrentFrameSummary
    empty_message: str | None


def build_m6_current_frame_results(
    aggregates: M6OrientationFrameAggregates,
) -> M6CurrentFrameResults:
    """Join component, footprint, and frame metrics without recomputation."""

    if not isinstance(aggregates, M6OrientationFrameAggregates):
        raise TypeError("aggregates must be M6OrientationFrameAggregates.")
    footprints = {
        component.ordered_component_id: component
        for component in aggregates.footprint_partition.components
    }
    rows = []
    for metrics in aggregates.domain_metrics.components:
        footprint = footprints[metrics.ordered_component_id]
        qc_statuses: list[M6CurrentFrameQcStatus] = []
        if metrics.insufficient_bonds_for_length_stats_qc:
            qc_statuses.append("insufficient_bonds_for_length_stats")
        if metrics.bond_length_heterogeneity_qc:
            qc_statuses.append("bond_length_heterogeneity")
        if footprint.edge_truncated:
            qc_statuses.append("edge_truncated")
        if footprint.footprint_disconnected_qc:
            qc_statuses.append("footprint_disconnected")
        rows.append(
            M6CurrentFrameDomainRow(
                ordered_component_id=metrics.ordered_component_id,
                m6_orientation_domain_id=metrics.m6_orientation_domain_id,
                component_type=metrics.component_type,
                molecule_count=metrics.molecule_count,
                molecule_fraction_of_valid_representatives=(
                    metrics.molecule_fraction_of_valid_representatives
                ),
                footprint_fraction_of_valid_fov=(
                    footprint.footprint_fraction_of_valid_fov
                ),
                footprint_area_nm2=footprint.footprint_area_nm2,
                orientation_deg=metrics.orientation_deg,
                domain_mean_local_q6=metrics.domain_mean_local_q6,
                domain_coherent_q6=metrics.domain_coherent_q6,
                domain_median_bond_length_nm=(
                    metrics.domain_median_bond_length_nm
                ),
                domain_bond_length_mad_nm=metrics.domain_bond_length_mad_nm,
                domain_bond_length_iqr_nm=metrics.domain_bond_length_iqr_nm,
                domain_bond_length_robust_cv=(
                    metrics.domain_bond_length_robust_cv
                ),
                qc_statuses=tuple(qc_statuses),
            )
        )
    summary = M6CurrentFrameSummary(
        mean_local_q6_interior=aggregates.mean_local_q6_interior,
        mean_local_q6_all_valid=aggregates.mean_local_q6_all_valid,
        global_q6_interior=aggregates.global_q6_interior,
        edge_truncated_fraction_of_valid_representatives=(
            aggregates.edge_truncated_fraction_of_valid_representatives
        ),
        full_domain_count=aggregates.full_domain_count,
        small_ordered_island_count=aggregates.small_ordered_island_count,
        full_domain_molecule_fraction=aggregates.full_domain_molecule_fraction,
        small_island_molecule_fraction=aggregates.small_island_molecule_fraction,
        unassigned_molecule_fraction=aggregates.unassigned_molecule_fraction,
        full_domain_footprint_fraction=aggregates.full_domain_footprint_fraction,
        small_island_footprint_fraction=aggregates.small_island_footprint_fraction,
        unassigned_supported_footprint_fraction=(
            aggregates.unassigned_supported_footprint_fraction
        ),
        unsupported_background_fraction=aggregates.unsupported_background_fraction,
        duplicate_excluded_fraction_of_original=(
            aggregates.duplicate_excluded_fraction_of_original
        ),
        invalid_position_fraction_of_original=(
            aggregates.invalid_position_fraction_of_original
        ),
        full_domain_molecule_weighted_coherent_q6=(
            aggregates.full_domain_molecule_weighted_coherent_q6
        ),
        full_domain_footprint_weighted_coherent_q6=(
            aggregates.full_domain_footprint_weighted_coherent_q6
        ),
        domain_molecule_entropy=aggregates.domain_molecule_entropy,
        domain_footprint_entropy=aggregates.domain_footprint_entropy,
    )
    domains = tuple(rows)
    return M6CurrentFrameResults(
        domains=domains,
        summary=summary,
        empty_message=None if domains else "No M6 domains in current frame.",
    )
