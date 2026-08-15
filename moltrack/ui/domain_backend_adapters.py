from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from math import cos, radians, sin

from moltrack.analysis import TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
from moltrack.analysis import (
    PairCorrelationResult,
    compute_pair_correlation,
    suggest_first_shell_r_max,
)
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint
from moltrack.analysis.domain_analysis import (
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    DomainAnalysisSeries,
    DomainBackendIdentity,
    GeometryMode,
    M3M6LatticeNetworkEvidence,
    M6CanonicalFrame,
    M6ComponentMembership,
    M6FrameComputation,
    M6FrameGeometry,
    M6OrientationComponentsEvidence,
    FirstShellGeometryPolicy,
    M6RunConfiguration,
)
from moltrack.analysis.domain_analysis.canonical_geometry import canonicalize_frame
from moltrack.analysis.m6_settings import MolecularM6OrientationAnalysisSettings
from moltrack.analysis.lattice_domain_models import (
    LATTICE_DOMAIN_ANALYSIS_ALGORITHM_VERSION,
    LatticeDomain,
)
from moltrack.analysis.molecular_m6_analysis import analyze_molecular_m6_orientation
from moltrack.analysis.orientation_domain_analysis import (
    M6OrientationDomainAnalysis,
    analyze_m6_orientation_domains,
)
from moltrack.analysis.orientation_domain_models import LatticeOrientationDomain
from moltrack.analysis.sample_coordinates import MolecularSampleCoordinates

from .domain_backend_network_evidence import (
    lattice_network_evidence,
    network_qc_flags,
)


class MolTrackOrientationComponentsAdapter:
    """Expose the existing M6 orientation-component pipeline as a backend."""

    def __init__(
        self,
        series: DomainAnalysisSeries,
        *,
        settings: MolecularM6OrientationAnalysisSettings = (
            TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
        ),
        geometry_policy: FirstShellGeometryPolicy | None = None,
    ) -> None:
        self._series = series
        self._settings = settings
        self._geometry_policy = _geometry_policy(settings, geometry_policy)
        settings_fingerprint = m6_settings_fingerprint(self._settings)
        self.backend_identity = DomainBackendIdentity(
            backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
            result_schema_version="domain-backend-result-v1",
            algorithm_version="moltrack-m6-orientation-v1",
            settings_fingerprint=settings_fingerprint,
            adapter_owner="analyze_m6_orientation_domains",
            native_evidence_kind="m6_orientation_evidence_v1",
            capabilities=(
                "common_partition",
                "orientation_components",
            ),
        )
        self._geometry_by_frame = {
            value.frame_index: value.geometry for value in series.frames
        }

    def first_shell_pair_correlations(self) -> tuple[PairCorrelationResult, ...]:
        """Return Calibration g(r) evidence in canonical frame order."""

        return _pair_correlations(
            self._series,
            self._settings,
            _classic_pair_correlation,
        )

    def default_run_configuration(self) -> M6RunConfiguration:
        return _run_configuration(self.backend_identity, self._settings)

    def for_run(
        self,
        configuration: M6RunConfiguration,
    ) -> MolTrackOrientationComponentsAdapter:
        configured = MolTrackOrientationComponentsAdapter(
            self._series,
            settings=configuration.settings,
            geometry_policy=configuration.first_shell_geometry,
        )
        _validate_frozen_identity(configured.backend_identity, configuration)
        return configured

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
        settings = _settings_for_geometry_policy(
            self._geometry_policy,
            self._settings,
            lambda: _classic_pair_correlation(
                    frame,
                    frame_index=frame_index,
                    geometry=geometry,
                    settings=self._settings,
            ),
        )
        analysis = analyze_m6_orientation_domains(
            tuple(value.centroid_xy_nm for value in frame.molecules),
            distance_to_valid_fov_boundary_nm=_boundary_distances(
                frame, geometry.raw_shape, geometry.pixel_size_nm
            ),
            point_ids=tuple(value.source_id for value in frame.molecules),
            settings=settings,
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
        evidence = _classic_native_evidence(analysis)
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

    def __init__(
        self,
        series: DomainAnalysisSeries,
        *,
        settings: MolecularM6OrientationAnalysisSettings = (
            TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
        ),
        geometry_policy: FirstShellGeometryPolicy | None = None,
    ) -> None:
        self._series = series
        self._settings = settings
        self._geometry_policy = _geometry_policy(settings, geometry_policy)
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
                "local_m3_m6",
                "seed_growth_provenance",
                "typed_domain_edges",
            ),
        )
        self._geometry_by_frame = {
            value.frame_index: value.geometry for value in series.frames
        }

    def first_shell_pair_correlations(self) -> tuple[PairCorrelationResult, ...]:
        """Return Calibration g(r) evidence retained by the network backend."""

        return _pair_correlations(
            self._series,
            self._settings,
            _network_pair_correlation,
        )

    def default_run_configuration(self) -> M6RunConfiguration:
        return _run_configuration(self.backend_identity, self._settings)

    def for_run(
        self,
        configuration: M6RunConfiguration,
    ) -> MolTrackLatticeNetworkAdapter:
        configured = MolTrackLatticeNetworkAdapter(
            self._series,
            settings=configuration.settings,
            geometry_policy=configuration.first_shell_geometry,
        )
        _validate_frozen_identity(configured.backend_identity, configuration)
        return configured

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
        settings = _settings_for_geometry_policy(
            self._geometry_policy,
            self._settings,
            lambda: _network_pair_correlation(
                    frame,
                    frame_index=frame_index,
                    geometry=geometry,
                    settings=self._settings,
            ),
        )
        analysis = analyze_molecular_m6_orientation(
            _sample_coordinates(frame, frame_index=frame_index, geometry=geometry),
            settings=settings,
        )
        lattice = analysis.lattice_domain_analysis
        if lattice is None:
            raise RuntimeError("M3/M6 lattice analysis did not publish domains.")
        evidence = lattice_network_evidence(analysis)
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


def _validate_frozen_identity(
    identity: DomainBackendIdentity,
    configuration: M6RunConfiguration,
) -> None:
    if identity != configuration.backend_identity:
        raise ValueError(
            "Frozen M6 configuration is incompatible with the runtime backend."
        )


def _run_configuration(
    identity: DomainBackendIdentity,
    settings: MolecularM6OrientationAnalysisSettings,
) -> M6RunConfiguration:
    return M6RunConfiguration(
        backend_identity=identity,
        settings=settings,
        first_shell_geometry=FirstShellGeometryPolicy.fixed(
            r_min_nm=settings.first_shell_r_min_nm,
            r_max_nm=settings.first_shell_r_max_nm,
        ),
    )


def _classic_native_evidence(
    analysis: M6OrientationDomainAnalysis,
) -> M6OrientationComponentsEvidence:
    local = analysis.local_order
    segmentation = analysis.segmentation
    local_ids = local.source_ids
    segmentation_ids = segmentation.source_ids
    neighbor_counts = getattr(
        local, "neighbor_count", (None,) * len(local_ids)
    )
    orientations = getattr(
        local, "lattice_orientation_deg", (None,) * len(local_ids)
    )
    local_statuses = getattr(
        local, "computation_status", (None,) * len(local_ids)
    )
    component_types = getattr(
        segmentation, "component_type", (None,) * len(segmentation_ids)
    )
    return M6OrientationComponentsEvidence(
        assignment_status=tuple(zip(
            segmentation_ids, segmentation.assignment_status
        )),
        q6=tuple(zip(local_ids, local.q6)),
        neighbor_count=tuple(zip(local_ids, neighbor_counts)),
        orientation_deg=tuple(zip(local_ids, orientations)),
        local_order_status=tuple(zip(local_ids, local_statuses)),
        component_type=tuple(zip(segmentation_ids, component_types)),
    )


def _classic_pair_correlation(
    frame: M6CanonicalFrame,
    frame_index: int,
    geometry: M6FrameGeometry,
    settings: MolecularM6OrientationAnalysisSettings,
) -> PairCorrelationResult:
    width_nm = geometry.raw_shape[1] * geometry.pixel_size_nm[0]
    height_nm = geometry.raw_shape[0] * geometry.pixel_size_nm[1]
    points = tuple(value.centroid_xy_nm for value in frame.molecules)
    point_ids = tuple(value.source_id for value in frame.molecules)
    analysis = analyze_m6_orientation_domains(
        points,
        distance_to_valid_fov_boundary_nm=_boundary_distances(
            frame, geometry.raw_shape, geometry.pixel_size_nm
        ),
        point_ids=point_ids,
        settings=settings,
        spatial_calibration_fingerprint=frame.coordinate_transform_fingerprint,
        registration_fingerprint=frame.presentation_provenance.registration_fingerprint,
        window_geometry="rectangular",
        window_size_nm=(width_nm, height_nm),
    )
    return compute_pair_correlation(
        points,
        point_ids=point_ids,
        point_frame_indices=(frame_index,) * len(points),
        first_shell_graph=analysis.first_shell_graph,
        frame_index=frame_index,
        settings=settings,
        window_geometry="rectangular",
        window_size_nm=(width_nm, height_nm),
    )


def _network_pair_correlation(
    frame: M6CanonicalFrame,
    frame_index: int,
    geometry: M6FrameGeometry,
    settings: MolecularM6OrientationAnalysisSettings,
) -> PairCorrelationResult:
    return analyze_molecular_m6_orientation(
        _sample_coordinates(frame, frame_index=frame_index, geometry=geometry),
        settings=settings,
    ).pair_correlation


def _pair_correlations(
    series: DomainAnalysisSeries,
    settings: MolecularM6OrientationAnalysisSettings,
    compute: Callable[
        [
            M6CanonicalFrame,
            int,
            M6FrameGeometry,
            MolecularM6OrientationAnalysisSettings,
        ],
        PairCorrelationResult,
    ],
) -> tuple[PairCorrelationResult, ...]:
    return tuple(
        compute(
            canonicalize_frame(
                series,
                frame_index=frame.frame_index,
                geometry_mode="segmentation_preferred",
            ),
            frame.frame_index,
            frame.geometry,
            settings,
        )
        for frame in series.frames
    )


def _geometry_policy(
    settings: MolecularM6OrientationAnalysisSettings,
    policy: FirstShellGeometryPolicy | None,
) -> FirstShellGeometryPolicy:
    return policy or FirstShellGeometryPolicy.fixed(
        r_min_nm=settings.first_shell_r_min_nm,
        r_max_nm=settings.first_shell_r_max_nm,
    )


def _settings_for_geometry_policy(
    policy: FirstShellGeometryPolicy,
    settings: MolecularM6OrientationAnalysisSettings,
    pair_correlation: Callable[[], PairCorrelationResult],
) -> MolecularM6OrientationAnalysisSettings:
    if policy.mode == "fixed":
        return settings
    suggestion = suggest_first_shell_r_max(pair_correlation(), settings=settings)
    resolved_r_max = suggestion.suggested_first_shell_r_max_nm
    if resolved_r_max is None:
        return settings
    return replace(settings, first_shell_r_max_nm=resolved_r_max)


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
        qc_flags=network_qc_flags(component),
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
