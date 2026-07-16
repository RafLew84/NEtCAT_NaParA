from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from ._m6_settings_fingerprint import m6_settings_fingerprint
from .first_shell_builder import build_first_shell_graph
from .first_shell_graph import FirstShellGraph
from .local_sixfold_bond_order import LocalSixfoldBondOrderField
from .local_sixfold_bond_order_computation import compute_local_sixfold_bond_order
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .orientation_domain_finalization import finalize_m6_orientation_domains
from .orientation_domain_merge import merge_and_grow_m6_orientation_domains
from .orientation_domain_models import M6OrientationDomainSegmentation
from .orientation_domain_seed_growth import grow_m6_orientation_domains
from .orientation_domain_seeds import detect_m6_orientation_domain_seeds


@dataclass(frozen=True)
class M6OrientationDomainAnalysis:
    """End-to-end M6 graph, local-order field, and final domain segmentation."""

    first_shell_graph: FirstShellGraph
    local_order: LocalSixfoldBondOrderField
    segmentation: M6OrientationDomainSegmentation
    settings: MolecularM6OrientationAnalysisSettings

    def __post_init__(self) -> None:
        if not isinstance(self.first_shell_graph, FirstShellGraph):
            raise TypeError("first_shell_graph must be a FirstShellGraph.")
        if not isinstance(self.local_order, LocalSixfoldBondOrderField):
            raise TypeError("local_order must be a LocalSixfoldBondOrderField.")
        if not isinstance(self.segmentation, M6OrientationDomainSegmentation):
            raise TypeError("segmentation must be an M6OrientationDomainSegmentation.")
        if not isinstance(self.settings, MolecularM6OrientationAnalysisSettings):
            raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
        if self.segmentation.settings != self.settings:
            raise ValueError("Segmentation must use the analysis settings.")

        source_ids = self.first_shell_graph.point_ids
        point_count = self.first_shell_graph.point_count
        if (
            self.local_order.source_ids != source_ids
            or self.segmentation.source_ids != source_ids
            or self.local_order.point_count != point_count
            or self.segmentation.point_count != point_count
        ):
            raise ValueError("All M6 analysis stages must use the same point IDs and order.")
        graph_settings = (
            self.first_shell_graph.duplicate_detection_enabled,
            self.first_shell_graph.duplicate_max_distance_nm,
            self.first_shell_graph.first_shell_r_min_nm,
            self.first_shell_graph.first_shell_r_max_nm,
        )
        requested_graph_settings = (
            self.settings.duplicate_detection_enabled,
            self.settings.duplicate_max_distance_nm,
            self.settings.first_shell_r_min_nm,
            self.settings.first_shell_r_max_nm,
        )
        local_settings = (
            self.local_order.first_shell_r_max_nm,
            self.local_order.min_neighbors_for_local_order,
            self.local_order.symmetry_m,
            self.local_order.bond_weighting,
        )
        requested_local_settings = (
            self.settings.first_shell_r_max_nm,
            self.settings.min_neighbors_for_local_order,
            self.settings.symmetry_m,
            self.settings.bond_weighting,
        )
        if graph_settings != requested_graph_settings or local_settings != requested_local_settings:
            raise ValueError("Graph and local order must use the segmentation settings.")
        expected_settings_fingerprint = m6_settings_fingerprint(self.settings)
        if (
            self.first_shell_graph.analysis_settings_fingerprint
            != expected_settings_fingerprint
            or self.local_order.analysis_settings_fingerprint
            != expected_settings_fingerprint
        ):
            raise ValueError("Graph and local order must preserve the complete settings fingerprint.")
        if self.local_order.neighbor_count != self.first_shell_graph.degree:
            raise ValueError("Local-order neighbor counts must match the first-shell graph.")
        if (
            self.local_order.physical_duplicate_qc
            != self.first_shell_graph.physical_duplicate_qc
            or self.segmentation.physical_duplicate_qc
            != self.first_shell_graph.physical_duplicate_qc
            or self.local_order.geometry_duplicate_qc
            != self.first_shell_graph.geometry_duplicate_qc
            or self.segmentation.geometry_duplicate_qc
            != self.first_shell_graph.geometry_duplicate_qc
        ):
            raise ValueError("All M6 analysis stages must preserve duplicate QC flags.")
        if (
            self.segmentation.edge_truncated_neighborhood
            != self.local_order.edge_truncated_neighborhood
        ):
            raise ValueError("Segmentation must preserve local-order boundary QC flags.")
        for local_status, assignment_status in zip(
            self.local_order.computation_status,
            self.segmentation.assignment_status,
        ):
            if local_status == "valid_order":
                if assignment_status not in {"assigned", "boundary_or_disordered"}:
                    raise ValueError(
                        "Valid local-order points require assigned or boundary status."
                    )
            elif assignment_status != local_status:
                raise ValueError(
                    "Non-valid local-order statuses must be preserved by segmentation."
                )
        for point_index, assignment_status in enumerate(
            self.segmentation.assignment_status
        ):
            if assignment_status != "assigned":
                continue
            point_q6 = self.local_order.q6[point_index]
            if (
                self.local_order.orientation_status[point_index] != "defined"
                or point_q6 is None
                or point_q6 < self.settings.q_grow
            ):
                raise ValueError(
                    "Assigned domain points require defined orientation and q6 >= q_grow."
                )

        graph_provenance = (
            self.first_shell_graph.coordinate_frame,
            self.first_shell_graph.orientation_reference,
            self.first_shell_graph.spatial_calibration_fingerprint,
            self.first_shell_graph.registration_fingerprint,
        )
        local_provenance = (
            self.local_order.coordinate_frame,
            self.local_order.orientation_reference,
            self.local_order.spatial_calibration_fingerprint,
            self.local_order.registration_fingerprint,
        )
        segmentation_provenance = (
            self.segmentation.coordinate_frame,
            self.segmentation.orientation_reference,
            self.segmentation.spatial_calibration_fingerprint,
            self.segmentation.registration_fingerprint,
        )
        if graph_provenance != local_provenance or graph_provenance != segmentation_provenance:
            raise ValueError("All M6 analysis stages must preserve coordinate provenance.")
        if (
            self.segmentation.point_coordinate_fingerprint
            != self.first_shell_graph.point_coordinate_fingerprint
        ):
            raise ValueError("Segmentation must preserve the point coordinate fingerprint.")

    @property
    def point_count(self) -> int:
        return self.first_shell_graph.point_count

def analyze_m6_orientation_domains(
    points_xy_nm: object,
    *,
    distance_to_valid_fov_boundary_nm: Sequence[float | None],
    point_ids: Sequence[str] | None = None,
    settings: MolecularM6OrientationAnalysisSettings | None = None,
    mask_blocking_qc: Sequence[bool] | None = None,
    segmentation_quality_scores: Sequence[float | None] | None = None,
    topography_peak_matches: Sequence[bool | None] | None = None,
    detection_confidences: Sequence[float | None] | None = None,
    orientation_reference: str = "+x_sample_axis",
    spatial_calibration_fingerprint: str = "unspecified_calibration",
    registration_fingerprint: str = "unregistered",
) -> M6OrientationDomainAnalysis:
    """Run deterministic M6 orientation-domain analysis from calibrated centroids."""

    if settings is None:
        settings = MolecularM6OrientationAnalysisSettings()
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    points = _materialize_points(points_xy_nm)

    graph = build_first_shell_graph(
        points,
        point_ids=point_ids,
        settings=settings,
        mask_blocking_qc=mask_blocking_qc,
        segmentation_quality_scores=segmentation_quality_scores,
        topography_peak_matches=topography_peak_matches,
        detection_confidences=detection_confidences,
        orientation_reference=orientation_reference,
        spatial_calibration_fingerprint=spatial_calibration_fingerprint,
        registration_fingerprint=registration_fingerprint,
    )
    local_order = compute_local_sixfold_bond_order(
        graph,
        distance_to_valid_fov_boundary_nm=distance_to_valid_fov_boundary_nm,
        settings=settings,
    )
    seeds = detect_m6_orientation_domain_seeds(
        points,
        first_shell_graph=graph,
        local_order=local_order,
        settings=settings,
    )
    growth = grow_m6_orientation_domains(
        points,
        first_shell_graph=graph,
        local_order=local_order,
        seeds=seeds,
        settings=settings,
    )
    merged = merge_and_grow_m6_orientation_domains(
        points,
        first_shell_graph=graph,
        local_order=local_order,
        growth=growth,
        settings=settings,
    )
    segmentation = finalize_m6_orientation_domains(merged)
    return M6OrientationDomainAnalysis(
        first_shell_graph=graph,
        local_order=local_order,
        segmentation=segmentation,
        settings=settings,
    )


def _materialize_points(points_xy_nm: object) -> np.ndarray:
    if isinstance(points_xy_nm, np.ndarray):
        return np.array(points_xy_nm, dtype=np.float64, copy=True)
    try:
        materialized = tuple(points_xy_nm)  # type: ignore[arg-type]
    except TypeError:
        materialized = points_xy_nm
    return np.array(materialized, dtype=np.float64, copy=True)
