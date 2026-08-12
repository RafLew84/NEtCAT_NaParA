from __future__ import annotations

from dataclasses import asdict
from math import cos, radians, sin

from moltrack.analysis import TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint
from moltrack.analysis.domain_analysis import (
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    DomainAnalysisSeries,
    DomainBackendIdentity,
    M3M6LatticeDomainEvidence,
    GeometryMode,
    M3M6LatticeNetworkEvidence,
    M6CanonicalFrame,
    M6ComponentMembership,
    M6FrameComputation,
    M6FrameGeometry,
    M6OrientationComponentsEvidence,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256
from moltrack.analysis.lattice_domain_models import (
    LATTICE_DOMAIN_ANALYSIS_ALGORITHM_VERSION,
    LatticeDomain,
    lattice_domain_analysis_fingerprint,
)
from moltrack.analysis.molecular_m6_analysis import analyze_molecular_m6_orientation
from moltrack.analysis.orientation_domain_analysis import (
    analyze_m6_orientation_domains,
)
from moltrack.analysis.orientation_domain_models import LatticeOrientationDomain
from moltrack.analysis.sample_coordinates import MolecularSampleCoordinates


class MolTrackOrientationComponentsAdapter:
    """Expose the existing M6 orientation-component pipeline as a backend."""

    def __init__(self, series: DomainAnalysisSeries) -> None:
        self._settings = TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
        settings_fingerprint = m6_settings_fingerprint(self._settings)
        self.backend_identity = DomainBackendIdentity(
            backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
            result_schema_version="domain-backend-result-v1",
            algorithm_version="moltrack-m6-orientation-v1",
            settings_fingerprint=settings_fingerprint,
            adapter_owner="analyze_m6_orientation_domains",
            native_evidence_kind="m6_orientation_evidence_v1",
            capabilities=("common_partition", "orientation_components"),
        )
        self._geometry_by_frame = {
            value.frame_index: value.geometry for value in series.frames
        }

    def analyze_frame(
        self,
        frame: M6CanonicalFrame,
        *,
        frame_index: int,
        geometry_mode: GeometryMode,
    ) -> M6FrameComputation:
        del geometry_mode
        if not frame.molecules:
            return _computation(
                frame,
                frame_index=frame_index,
                identity=self.backend_identity,
                full_domains=(),
                islands=(),
                evidence=M6OrientationComponentsEvidence((), ()),
            )
        geometry = self._geometry_by_frame[frame_index]
        analysis = analyze_m6_orientation_domains(
            tuple(value.centroid_xy_nm for value in frame.molecules),
            distance_to_valid_fov_boundary_nm=_boundary_distances(
                frame, geometry.raw_shape, geometry.pixel_size_nm
            ),
            point_ids=tuple(value.source_id for value in frame.molecules),
            settings=self._settings,
            spatial_calibration_fingerprint=(
                frame.coordinate_transform_fingerprint
            ),
            registration_fingerprint=(
                frame.presentation_provenance.registration_fingerprint
            ),
            window_geometry="rectangular",
            window_size_nm=(
                geometry.raw_shape[1] * geometry.pixel_size_nm[0],
                geometry.raw_shape[0] * geometry.pixel_size_nm[1],
            ),
        )
        evidence = M6OrientationComponentsEvidence(
            assignment_status=tuple(zip(
                analysis.segmentation.source_ids,
                analysis.segmentation.assignment_status,
            )),
            q6=tuple(zip(
                analysis.local_order.source_ids,
                analysis.local_order.q6,
            )),
        )
        components = analysis.segmentation.components
        return _computation(
            frame,
            frame_index=frame_index,
            identity=self.backend_identity,
            full_domains=tuple(
                _classic_membership(value)
                for value in components
                if value.component_type == "full_domain"
            ),
            islands=tuple(
                _classic_membership(value)
                for value in components
                if value.component_type == "small_ordered_island"
            ),
            evidence=evidence,
        )


class MolTrackLatticeNetworkAdapter:
    """Expose the existing M3/M6 lattice-domain pipeline as a backend."""

    def __init__(self, series: DomainAnalysisSeries) -> None:
        self._settings = TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
        settings_fingerprint = m6_settings_fingerprint(self._settings)
        self.backend_identity = DomainBackendIdentity(
            backend_id=M3_M6_LATTICE_NETWORK_BACKEND_ID,
            result_schema_version="domain-backend-result-v1",
            algorithm_version=LATTICE_DOMAIN_ANALYSIS_ALGORITHM_VERSION,
            settings_fingerprint=settings_fingerprint,
            adapter_owner="analyze_molecular_m6_orientation",
            native_evidence_kind="m3_m6_lattice_evidence_v1",
            capabilities=(
                "common_partition",
                "core_halo",
                "domain_confidence",
                "domain_qc",
                "dominant_symmetry",
                "explicit_boundary",
                "seed_growth_provenance",
            ),
        )
        self._geometry_by_frame = {
            value.frame_index: value.geometry for value in series.frames
        }

    def analyze_frame(
        self,
        frame: M6CanonicalFrame,
        *,
        frame_index: int,
        geometry_mode: GeometryMode,
    ) -> M6FrameComputation:
        del geometry_mode
        if not frame.molecules:
            return _computation(
                frame,
                frame_index=frame_index,
                identity=self.backend_identity,
                full_domains=(),
                islands=(),
                evidence=M3M6LatticeNetworkEvidence((), (), (), (), ()),
            )
        geometry = self._geometry_by_frame[frame_index]
        analysis = analyze_molecular_m6_orientation(
            _sample_coordinates(frame, frame_index=frame_index, geometry=geometry),
            settings=self._settings,
        )
        lattice = analysis.lattice_domain_analysis
        if lattice is None:
            raise RuntimeError("M3/M6 lattice analysis did not publish domains.")
        evidence = M3M6LatticeNetworkEvidence(
            point_roles=tuple(zip(lattice.source_ids, lattice.point_role)),
            boundary_reasons=tuple(zip(
                lattice.source_ids,
                lattice.boundary_reason,
            )),
            point_domain_ids=tuple(zip(
                lattice.source_ids,
                lattice.point_lattice_domain_id,
            )),
            domains=tuple(
                M3M6LatticeDomainEvidence(
                    lattice_domain_id=component.lattice_domain_id,
                    dominant_symmetry=component.dominant_symmetry,
                    confidence=component.confidence,
                    qc_flags=_network_qc_flags(component),
                    orientation_reference_channel=(
                        component.orientation_reference_channel
                    ),
                    m3_m6_orientation_relation_status=(
                        component.m3_m6_orientation_relation_status
                    ),
                    provenance_fingerprint=canonical_sha256(asdict(component)),
                )
                for component in lattice.components
            ),
            producer_fingerprints=(
                ("first_shell_graph", lattice.first_shell_graph_fingerprint),
                ("local_order", lattice.local_order_analysis_fingerprint),
                ("local_symmetry", lattice.local_symmetry_bond_evidence_fingerprint),
                ("seed_growth", lattice.seed_growth_result_fingerprint),
                ("lattice_domain", lattice_domain_analysis_fingerprint(lattice)),
            ),
        )
        return _computation(
            frame,
            frame_index=frame_index,
            identity=self.backend_identity,
            full_domains=tuple(
                _network_membership(value) for value in lattice.domains
            ),
            islands=tuple(
                _network_membership(value)
                for value in lattice.small_ordered_islands
            ),
            evidence=evidence,
        )


def _computation(
    frame: M6CanonicalFrame,
    *,
    frame_index: int,
    identity: DomainBackendIdentity,
    full_domains: tuple[M6ComponentMembership, ...],
    islands: tuple[M6ComponentMembership, ...],
    evidence: M6OrientationComponentsEvidence | M3M6LatticeNetworkEvidence,
) -> M6FrameComputation:
    return M6FrameComputation(
        frame_index=frame_index,
        molecules=frame.molecules,
        analyzed_pixels_xy=frame.analyzed_pixels_xy,
        pixel_area_nm2=frame.pixel_area_nm2,
        full_domains=full_domains,
        small_ordered_islands=islands,
        coordinate_frame=frame.coordinate_frame,
        coordinate_transform_fingerprint=frame.coordinate_transform_fingerprint,
        backend_identity=identity,
        native_evidence=evidence,
    )


def _classic_membership(
    component: LatticeOrientationDomain,
) -> M6ComponentMembership:
    component_id = (
        component.m6_orientation_domain_id
        if component.component_type == "full_domain"
        else component.ordered_component_id
    )
    return M6ComponentMembership(
        lattice_domain_id=f"m6-{component.component_type}-{component_id}",
        source_ids=component.source_ids,
    )


def _network_membership(component: LatticeDomain) -> M6ComponentMembership:
    return M6ComponentMembership(
        lattice_domain_id=component.lattice_domain_id,
        source_ids=component.source_ids,
        core_source_ids=component.core_source_ids,
        halo_source_ids=component.halo_source_ids,
        qc_flags=_network_qc_flags(component),
    )


def _sample_coordinates(
    frame: M6CanonicalFrame,
    *,
    frame_index: int,
    geometry: M6FrameGeometry,
) -> MolecularSampleCoordinates:
    width_nm = geometry.raw_shape[1] * geometry.pixel_size_nm[0]
    height_nm = geometry.raw_shape[0] * geometry.pixel_size_nm[1]
    local_polygon = (
        (0.0, 0.0), (width_nm, 0.0),
        (width_nm, height_nm), (0.0, height_nm),
    )
    polygon = _rotate_polygon(local_polygon, geometry.scan_angle_deg)
    return MolecularSampleCoordinates(
        frame_index=frame_index,
        source_view=frame.presentation_provenance.source_view,
        point_source_ids=tuple(value.source_id for value in frame.molecules),
        point_source_kinds=tuple(value.source_kind for value in frame.molecules),
        source_points_xy_px=tuple(value.raw_centroid_xy for value in frame.molecules),
        points_xy_nm=tuple(value.centroid_xy_nm for value in frame.molecules),
        distance_to_valid_fov_boundary_nm=_boundary_distances(
            frame, geometry.raw_shape, geometry.pixel_size_nm
        ),
        valid_fov_polygon_xy_nm=polygon,
        plot_canvas_polygon_xy_nm=polygon,
        window_side_lengths_nm=(width_nm, height_nm),
        coordinate_transform_fingerprint=frame.coordinate_transform_fingerprint,
        spatial_calibration_fingerprint=frame.coordinate_transform_fingerprint,
        registration_fingerprint=(
            frame.presentation_provenance.registration_fingerprint
        ),
        scan_angle_deg=geometry.scan_angle_deg,
        scan_angle_missing_qc=False,
    )


def _rotate_polygon(
    points: tuple[tuple[float, float], ...],
    angle_deg: float,
) -> tuple[tuple[float, float], ...]:
    angle = radians(angle_deg)
    cosine, sine = cos(angle), sin(angle)
    return tuple(
        (
            round(cosine * x - sine * y, 12),
            round(sine * x + cosine * y, 12),
        )
        for x, y in points
    )


def _boundary_distances(
    frame: M6CanonicalFrame,
    raw_shape: tuple[int, int],
    pixel_size_nm: tuple[float, float],
) -> tuple[float, ...]:
    height, width = raw_shape
    scale_x, scale_y = pixel_size_nm
    return tuple(
        min(
            molecule.raw_centroid_xy[0] * scale_x,
            (width - molecule.raw_centroid_xy[0]) * scale_x,
            molecule.raw_centroid_xy[1] * scale_y,
            (height - molecule.raw_centroid_xy[1]) * scale_y,
        )
        for molecule in frame.molecules
    )


def _network_qc_flags(component: LatticeDomain) -> tuple[str, ...]:
    return tuple(sorted(
        name for name, value in asdict(component.qc).items() if value is True
    ))
