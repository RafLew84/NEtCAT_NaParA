from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from ._coordinate_fingerprint import point_coordinate_fingerprint
from .first_shell_graph import FirstShellGraph
from .lattice_domain_edge_compatibility import (
    build_lattice_domain_edge_compatibility,
)
from .lattice_domain_edge_models import (
    LatticeDomainEdgeCompatibilityField,
    lattice_domain_edge_settings_from_m6,
    lattice_domain_edge_settings_fingerprint,
)
from .lattice_domain_seed_growth import build_lattice_domain_seed_growth
from .lattice_domain_seed_growth_models import (
    LatticeDomainSeedGrowthResult,
    lattice_domain_seed_growth_settings_from_m6,
    lattice_domain_seed_growth_settings_fingerprint,
)
from .local_multisymmetry_bond_order import (
    LocalMultiSymmetryBondOrderField,
    SymmetryResolvabilityStatus,
)
from .local_multisymmetry_bond_order_computation import (
    apply_m3_sublattice_gauge,
    compute_local_multisymmetry_bond_order,
)
from .local_sixfold_bond_order import LocalSixfoldBondOrderField
from .local_symmetry_evidence_classifier import classify_local_symmetry_evidence
from .local_symmetry_evidence_models import (
    LocalSymmetryEvidenceField,
    LocalSymmetryEvidenceSettings,
    LocalSymmetryModel,
    local_symmetry_evidence_settings_fingerprint,
)
from .m6_settings import MolecularM6OrientationAnalysisSettings
from .orientation_domain_analysis import (
    M6OrientationDomainAnalysis,
    analyze_m6_orientation_domains,
)
from .orientation_domain_frame_aggregates import M6OrientationFrameAggregates
from .orientation_domain_models import M6OrientationDomainSegmentation
from .pair_correlation import (
    PairCorrelationResult,
    compute_pair_correlation,
    validate_pair_correlation_result_context,
)
from .sample_coordinates import MolecularSampleCoordinates


@dataclass(frozen=True)
class MolecularM6OrientationAnalysis:
    """Full M6 structural result for one Position Analysis frame."""

    source_view: str
    sample_coordinates: MolecularSampleCoordinates
    domain_analysis: M6OrientationDomainAnalysis
    pair_correlation: PairCorrelationResult
    local_multisymmetry_order: LocalMultiSymmetryBondOrderField | None = None
    local_symmetry_evidence: LocalSymmetryEvidenceField | None = None
    local_symmetry_evidence_settings: LocalSymmetryEvidenceSettings | None = None
    lattice_domain_edge_compatibility: LatticeDomainEdgeCompatibilityField | None = None
    lattice_domain_seed_growth: LatticeDomainSeedGrowthResult | None = None

    def __post_init__(self) -> None:
        if self.source_view != self.sample_coordinates.source_view:
            raise ValueError("M6 source_view must match sample coordinates.")
        graph = self.domain_analysis.first_shell_graph
        if graph.point_ids != self.point_source_ids:
            raise ValueError("M6 graph IDs must match Position Analysis centroids.")
        analysis_points = np.asarray(self.points_xy_nm, dtype=np.float64).reshape((-1, 2))
        if (
            point_coordinate_fingerprint(analysis_points, graph.point_ids)
            != graph.point_coordinate_fingerprint
        ):
            raise ValueError("M6 graph coordinates must match Position Analysis points.")
        expected_provenance = (
            self.sample_coordinates.spatial_calibration_fingerprint,
            self.sample_coordinates.registration_fingerprint,
        )
        if (
            graph.spatial_calibration_fingerprint,
            graph.registration_fingerprint,
        ) != expected_provenance:
            raise ValueError("M6 graph must preserve the coordinate transform provenance.")
        sample = self.sample_coordinates
        validate_pair_correlation_result_context(
            self.pair_correlation,
            first_shell_graph=graph,
            frame_index=sample.frame_index,
            settings=self.settings,
            window_size_nm=sample.window_side_lengths_nm,
            window_origin_nm=sample.valid_fov_polygon_xy_nm[0],
            valid_fov_polygon_xy_nm=sample.valid_fov_polygon_xy_nm,
            excluded_point_ids=self.invalid_position_point_ids,
        )
        if self.domain_analysis.frame_aggregates is None:
            raise ValueError("M6 Position Analysis requires frame aggregates.")
        self._validate_local_symmetry_extension(graph)
        self._validate_lattice_domain_edge_extension(graph)
        self._validate_lattice_domain_seed_growth_extension(graph)

    def _validate_local_symmetry_extension(self, graph: FirstShellGraph) -> None:
        extension = (
            self.local_multisymmetry_order,
            self.local_symmetry_evidence,
            self.local_symmetry_evidence_settings,
        )
        if all(value is None for value in extension):
            return
        if any(value is None for value in extension):
            raise ValueError("Local M3/M6 analysis fields must be present together.")
        multisymmetry = self.local_multisymmetry_order
        evidence = self.local_symmetry_evidence
        evidence_settings = self.local_symmetry_evidence_settings
        if not isinstance(multisymmetry, LocalMultiSymmetryBondOrderField):
            raise TypeError("local_multisymmetry_order has an invalid type.")
        if not isinstance(evidence, LocalSymmetryEvidenceField):
            raise TypeError("local_symmetry_evidence has an invalid type.")
        if not isinstance(evidence_settings, LocalSymmetryEvidenceSettings):
            raise TypeError("local_symmetry_evidence_settings has an invalid type.")
        if (
            multisymmetry.source_ids != graph.point_ids
            or evidence.source_ids != graph.point_ids
            or multisymmetry.point_count != graph.point_count
            or evidence.point_count != graph.point_count
        ):
            raise ValueError("Local M3/M6 analysis must preserve graph point order.")
        if (
            multisymmetry.psi6 != self.local_order.psi6
            or multisymmetry.q6 != self.local_order.q6
            or multisymmetry.theta6_deg != self.local_order.lattice_orientation_deg
            or multisymmetry.neighbor_count != self.local_order.neighbor_count
            or multisymmetry.computation_status != self.local_order.computation_status
        ):
            raise ValueError("Local multisymmetry M6 must match the domain M6 channel.")
        if (
            evidence.first_shell_graph_fingerprint
            != multisymmetry.provenance.first_shell_graph_fingerprint
            or evidence.local_order_analysis_fingerprint
            != multisymmetry.provenance.analysis_settings_fingerprint
            or evidence.settings_fingerprint
            != local_symmetry_evidence_settings_fingerprint(evidence_settings)
        ):
            raise ValueError("Local symmetry evidence must preserve its analysis provenance.")

    def _validate_lattice_domain_edge_extension(self, graph: FirstShellGraph) -> None:
        if self.lattice_domain_edge_compatibility is None:
            return
        edge_field = self.lattice_domain_edge_compatibility
        local_order = self.local_multisymmetry_order
        local_evidence = self.local_symmetry_evidence
        if not isinstance(edge_field, LatticeDomainEdgeCompatibilityField):
            raise TypeError("lattice_domain_edge_compatibility has an invalid type.")
        if not isinstance(local_order, LocalMultiSymmetryBondOrderField) or not isinstance(
            local_evidence,
            LocalSymmetryEvidenceField,
        ):
            raise ValueError("Lattice-domain edges require completed local M3/M6 evidence.")
        if edge_field.source_ids != graph.point_ids or edge_field.edges_ij != graph.edges_ij:
            raise ValueError("Lattice-domain edges must preserve first-shell graph order.")
        if (
            edge_field.first_shell_graph_fingerprint
            != local_order.provenance.first_shell_graph_fingerprint
            or edge_field.local_order_analysis_fingerprint
            != local_order.provenance.analysis_settings_fingerprint
            or edge_field.local_symmetry_evidence_settings_fingerprint
            != local_evidence.settings_fingerprint
            or edge_field.local_symmetry_bond_evidence_fingerprint
            != local_evidence.bond_evidence_fingerprint
        ):
            raise ValueError("Lattice-domain edges must preserve local evidence provenance.")
        expected_settings = lattice_domain_edge_settings_from_m6(self.settings)
        if edge_field.settings != expected_settings or (
            edge_field.settings_fingerprint
            != lattice_domain_edge_settings_fingerprint(expected_settings)
        ):
            raise ValueError("Lattice-domain edge settings must match their result.")

    def _validate_lattice_domain_seed_growth_extension(
        self,
        graph: FirstShellGraph,
    ) -> None:
        if self.lattice_domain_seed_growth is None:
            return
        seed_growth = self.lattice_domain_seed_growth
        edge_field = self.lattice_domain_edge_compatibility
        local_order = self.local_multisymmetry_order
        local_evidence = self.local_symmetry_evidence
        if not isinstance(seed_growth, LatticeDomainSeedGrowthResult):
            raise TypeError("lattice_domain_seed_growth has an invalid type.")
        if not isinstance(edge_field, LatticeDomainEdgeCompatibilityField):
            raise ValueError("Lattice-domain seed/growth requires edge compatibility.")
        if not isinstance(local_order, LocalMultiSymmetryBondOrderField) or not isinstance(
            local_evidence,
            LocalSymmetryEvidenceField,
        ):
            raise ValueError("Lattice-domain seed/growth requires local M3/M6 evidence.")
        if seed_growth.source_ids != graph.point_ids:
            raise ValueError("Lattice-domain seed/growth must preserve graph point order.")
        if (
            seed_growth.first_shell_graph_fingerprint
            != local_order.provenance.first_shell_graph_fingerprint
            or seed_growth.local_order_analysis_fingerprint
            != local_order.provenance.analysis_settings_fingerprint
            or seed_growth.local_symmetry_evidence_settings_fingerprint
            != local_evidence.settings_fingerprint
            or seed_growth.local_symmetry_bond_evidence_fingerprint
            != local_evidence.bond_evidence_fingerprint
            or seed_growth.edge_compatibility_settings_fingerprint
            != edge_field.settings_fingerprint
        ):
            raise ValueError("Lattice-domain seed/growth must preserve input provenance.")
        expected_settings = lattice_domain_seed_growth_settings_from_m6(self.settings)
        if seed_growth.settings != expected_settings or (
            seed_growth.settings_fingerprint
            != lattice_domain_seed_growth_settings_fingerprint(expected_settings)
        ):
            raise ValueError("Lattice-domain seed/growth settings must match their result.")

    @property
    def settings(self) -> MolecularM6OrientationAnalysisSettings:
        return self.domain_analysis.settings

    @property
    def first_shell_graph(self) -> FirstShellGraph:
        return self.domain_analysis.first_shell_graph

    @property
    def local_order(self) -> LocalSixfoldBondOrderField:
        return self.domain_analysis.local_order

    @property
    def psi6(self) -> tuple[complex | None, ...]:
        return self.local_order.psi6

    @property
    def segmentation(self) -> M6OrientationDomainSegmentation:
        return self.domain_analysis.segmentation

    @property
    def frame_aggregates(self) -> M6OrientationFrameAggregates:
        aggregates = self.domain_analysis.frame_aggregates
        if aggregates is None:  # guarded by __post_init__
            raise RuntimeError("M6 frame aggregates are unavailable.")
        return aggregates

    @property
    def aggregates(self) -> M6OrientationFrameAggregates:
        return self.frame_aggregates

    @property
    def point_source_ids(self) -> tuple[str, ...]:
        return self.sample_coordinates.point_source_ids

    @property
    def points_xy_nm(self) -> tuple[tuple[float, float], ...]:
        return self.sample_coordinates.points_xy_nm

    @property
    def invalid_position_point_ids(self) -> tuple[str, ...]:
        return self.sample_coordinates.invalid_position_point_ids

    @property
    def coordinate_transform_fingerprint(self) -> str:
        return self.sample_coordinates.coordinate_transform_fingerprint

    @property
    def coordinate_frame(self) -> str:
        return self.sample_coordinates.coordinate_frame

    @property
    def orientation_reference(self) -> str:
        return self.sample_coordinates.orientation_reference

    @property
    def spatial_calibration_fingerprint(self) -> str:
        return self.sample_coordinates.spatial_calibration_fingerprint

    @property
    def registration_fingerprint(self) -> str:
        return self.sample_coordinates.registration_fingerprint

    @property
    def scan_angle_missing_qc(self) -> bool:
        return self.sample_coordinates.scan_angle_missing_qc


def analyze_molecular_m6_orientation(
    sample_coordinates: MolecularSampleCoordinates,
    *,
    settings: MolecularM6OrientationAnalysisSettings,
) -> MolecularM6OrientationAnalysis:
    """Run the complete M6 core for one transformed Position Analysis frame."""

    if not isinstance(sample_coordinates, MolecularSampleCoordinates):
        raise TypeError("sample_coordinates must be MolecularSampleCoordinates.")
    if not isinstance(settings, MolecularM6OrientationAnalysisSettings):
        raise TypeError("settings must be MolecularM6OrientationAnalysisSettings.")
    points = np.asarray(sample_coordinates.points_xy_nm, dtype=np.float64).reshape((-1, 2))
    point_ids = sample_coordinates.point_source_ids
    boundary_distances = tuple(
        None if distance < 0.0 else distance
        for distance in sample_coordinates.distance_to_valid_fov_boundary_nm
    )
    analysis = analyze_m6_orientation_domains(
        points,
        point_ids=point_ids,
        distance_to_valid_fov_boundary_nm=boundary_distances,
        settings=settings,
        orientation_reference=sample_coordinates.orientation_reference,
        spatial_calibration_fingerprint=(
            sample_coordinates.spatial_calibration_fingerprint
        ),
        registration_fingerprint=sample_coordinates.registration_fingerprint,
        window_geometry="convex_polygon",
        valid_fov_polygon_xy_nm=sample_coordinates.valid_fov_polygon_xy_nm,
    )
    local_multisymmetry_order = compute_local_multisymmetry_bond_order(
        analysis.first_shell_graph,
        distance_to_valid_fov_boundary_nm=boundary_distances,
        settings=settings,
    )
    local_symmetry_evidence_settings = LocalSymmetryEvidenceSettings()
    local_symmetry_evidence = classify_local_symmetry_evidence(
        analysis.first_shell_graph,
        local_multisymmetry_order,
        settings=local_symmetry_evidence_settings,
    )
    qualified_trifold_indices = tuple(
        index
        for index, model in enumerate(local_symmetry_evidence.best_model)
        if model == "trifold"
        and local_multisymmetry_order.m3_orientation_status[index] == "defined"
    )
    local_multisymmetry_order = apply_m3_sublattice_gauge(
        analysis.first_shell_graph,
        local_multisymmetry_order,
        qualified_trifold_point_indices=qualified_trifold_indices,
    )
    local_multisymmetry_order = replace(
        local_multisymmetry_order,
        symmetry_resolvability_status=tuple(
            _symmetry_resolvability_status(computation_status, model, reason)
            for computation_status, model, reason in zip(
                local_multisymmetry_order.computation_status,
                local_symmetry_evidence.best_model,
                local_symmetry_evidence.classification_reason,
            )
        ),
    )
    polygon_origin = sample_coordinates.valid_fov_polygon_xy_nm[0]
    pair_correlation = compute_pair_correlation(
        points,
        point_ids=point_ids,
        point_frame_indices=(sample_coordinates.frame_index,) * len(points),
        first_shell_graph=analysis.first_shell_graph,
        frame_index=sample_coordinates.frame_index,
        settings=settings,
        window_geometry="rectangular",
        window_size_nm=sample_coordinates.window_side_lengths_nm,
        window_origin_nm=polygon_origin,
        valid_fov_polygon_xy_nm=sample_coordinates.valid_fov_polygon_xy_nm,
        excluded_point_ids=sample_coordinates.invalid_position_point_ids,
    )
    result = MolecularM6OrientationAnalysis(
        source_view=sample_coordinates.source_view,
        sample_coordinates=sample_coordinates,
        domain_analysis=analysis,
        pair_correlation=pair_correlation,
        local_multisymmetry_order=local_multisymmetry_order,
        local_symmetry_evidence=local_symmetry_evidence,
        local_symmetry_evidence_settings=local_symmetry_evidence_settings,
    )
    return attach_lattice_domain_seed_growth(result)


def attach_lattice_domain_edge_compatibility(
    analysis: MolecularM6OrientationAnalysis,
) -> MolecularM6OrientationAnalysis:
    """Add 86.1 edge decisions without recomputing completed local evidence."""

    if not isinstance(analysis, MolecularM6OrientationAnalysis):
        raise TypeError("analysis must be MolecularM6OrientationAnalysis.")
    if analysis.lattice_domain_edge_compatibility is not None:
        return analysis
    local_order = analysis.local_multisymmetry_order
    local_evidence = analysis.local_symmetry_evidence
    if not isinstance(local_order, LocalMultiSymmetryBondOrderField) or not isinstance(
        local_evidence,
        LocalSymmetryEvidenceField,
    ):
        raise ValueError("Lattice-domain edges require completed local M3/M6 evidence.")
    edge_settings = lattice_domain_edge_settings_from_m6(analysis.settings)
    edge_compatibility = build_lattice_domain_edge_compatibility(
        analysis.first_shell_graph,
        local_order,
        local_evidence,
        settings=edge_settings,
    )
    return replace(
        analysis,
        lattice_domain_edge_compatibility=edge_compatibility,
    )


def attach_lattice_domain_seed_growth(
    analysis: MolecularM6OrientationAnalysis,
) -> MolecularM6OrientationAnalysis:
    """Add 86.2 seed/grow output without recomputing local evidence or edges."""

    if not isinstance(analysis, MolecularM6OrientationAnalysis):
        raise TypeError("analysis must be a MolecularM6OrientationAnalysis.")
    if analysis.lattice_domain_seed_growth is not None:
        return analysis
    if analysis.lattice_domain_edge_compatibility is None:
        analysis = attach_lattice_domain_edge_compatibility(analysis)
    local_order = analysis.local_multisymmetry_order
    local_evidence = analysis.local_symmetry_evidence
    edge_compatibility = analysis.lattice_domain_edge_compatibility
    if not isinstance(local_order, LocalMultiSymmetryBondOrderField) or not isinstance(
        local_evidence,
        LocalSymmetryEvidenceField,
    ) or not isinstance(edge_compatibility, LatticeDomainEdgeCompatibilityField):
        raise ValueError("Lattice-domain seed/growth requires completed edge evidence.")
    settings = lattice_domain_seed_growth_settings_from_m6(analysis.settings)
    seed_growth = build_lattice_domain_seed_growth(
        analysis.first_shell_graph,
        local_order,
        local_evidence,
        edge_compatibility,
        settings=settings,
    )
    return replace(
        analysis,
        lattice_domain_seed_growth=seed_growth,
    )


def _symmetry_resolvability_status(
    computation_status: str,
    model: LocalSymmetryModel,
    reason: str,
) -> SymmetryResolvabilityStatus:
    if computation_status != "valid_order" or model == "unavailable":
        return "unavailable"
    if model == "ambiguous" and reason == "below_minimum_margin":
        return "symmetry_alias_unresolvable_from_centroids"
    if model == "ambiguous":
        return "unavailable"
    return "resolvable"
