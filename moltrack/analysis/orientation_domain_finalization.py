from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .orientation_domain_merge import (
    M6OrientationDomainMergeState,
    M6OrientationMergedComponent,
)
from .orientation_domain_models import (
    LatticeOrientationDomain,
    M6AssignmentStatus,
    M6ComponentType,
    M6OrientationDomainSegmentation,
)


@dataclass(frozen=True)
class _FinalComponentCandidate:
    source: M6OrientationMergedComponent
    component_type: Literal["full_domain", "small_ordered_island"]

    @property
    def stable_sort_key(self) -> tuple[int, float, float, float, str]:
        return self.source.stable_sort_key


def finalize_m6_orientation_domains(
    merged: M6OrientationDomainMergeState,
) -> M6OrientationDomainSegmentation:
    """Classify merged components by size and assign stable final IDs."""

    if not isinstance(merged, M6OrientationDomainMergeState):
        raise TypeError("merged must be an M6OrientationDomainMergeState.")

    candidates = tuple(
        _FinalComponentCandidate(
            source=component,
            component_type=(
                "full_domain"
                if component.molecule_count >= merged.settings.min_domain_size
                else "small_ordered_island"
            ),
        )
        for component in merged.components
        if component.molecule_count >= merged.settings.min_ordered_component_size
    )
    ordered_candidates = tuple(
        sorted(candidates, key=lambda candidate: candidate.stable_sort_key)
    )

    components: list[LatticeOrientationDomain] = []
    next_domain_id = 0
    for ordered_component_id, candidate in enumerate(ordered_candidates):
        if candidate.component_type == "full_domain":
            domain_id: int | None = next_domain_id
            next_domain_id += 1
        else:
            domain_id = None
        source = candidate.source
        components.append(
            LatticeOrientationDomain(
                ordered_component_id=ordered_component_id,
                m6_orientation_domain_id=domain_id,
                component_type=candidate.component_type,
                point_indices=source.point_indices,
                source_ids=source.source_ids,
                molecule_count=source.molecule_count,
                centroid_x_nm=source.centroid_x_nm,
                centroid_y_nm=source.centroid_y_nm,
                orientation_deg=source.orientation_deg,
            )
        )

    ordered_ids = [-1] * merged.point_count
    domain_ids = [-1] * merged.point_count
    component_types: list[M6ComponentType] = ["unassigned"] * merged.point_count
    assignment_statuses: list[M6AssignmentStatus] = [
        "boundary_or_disordered" if status == "assigned" else status
        for status in merged.assignment_status
    ]
    for component in components:
        for point_index in component.point_indices:
            ordered_ids[point_index] = component.ordered_component_id
            domain_ids[point_index] = (
                component.m6_orientation_domain_id
                if component.m6_orientation_domain_id is not None
                else -1
            )
            component_types[point_index] = component.component_type
            assignment_statuses[point_index] = "assigned"

    return M6OrientationDomainSegmentation(
        source_ids=merged.source_ids,
        point_count=merged.point_count,
        ordered_component_id=tuple(ordered_ids),
        m6_orientation_domain_id=tuple(domain_ids),
        component_type=tuple(component_types),
        assignment_status=tuple(assignment_statuses),
        edge_truncated_neighborhood=merged.edge_truncated_neighborhood,
        physical_duplicate_qc=merged.physical_duplicate_qc,
        geometry_duplicate_qc=merged.geometry_duplicate_qc,
        components=tuple(components),
        settings=merged.settings,
        coordinate_frame=merged.coordinate_frame,
        orientation_reference=merged.orientation_reference,
        spatial_calibration_fingerprint=merged.spatial_calibration_fingerprint,
        registration_fingerprint=merged.registration_fingerprint,
        point_coordinate_fingerprint=merged.point_coordinate_fingerprint,
    )
