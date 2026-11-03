from __future__ import annotations

from dataclasses import replace

import pytest

from moltrack.analysis import TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
from moltrack.analysis.domain_analysis import (
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    DomainAnalysisFrame,
    DomainAnalysisModule,
    DomainAnalysisRequest,
    DomainAnalysisSeries,
    DomainBackendIdentity,
    FirstShellGeometryPolicy,
    M3M6LatticeDomainEvidence,
    M3M6LatticeNetworkEvidence,
    M6ComponentMembership,
    M6FrameComputation,
    M6FrameGeometry,
    M6OrientationComponentsEvidence,
    M6RunConfiguration,
    M6SourceAnnotation,
)
from moltrack.ui.domain_backend_adapters import (
    MolTrackLatticeNetworkAdapter,
    _sample_coordinates,
)
from moltrack.analysis.domain_analysis.cache import M6FrameCache, m6_frame_cache_key
from moltrack.analysis.domain_analysis.canonical_geometry import canonicalize_frame
from moltrack.persistence.domain_backend_payload import (
    backend_evidence_from_payload,
    backend_evidence_to_payload,
)


class _BackendAdapter:
    def __init__(self, backend_id: str) -> None:
        self.backend_identity = DomainBackendIdentity(
            backend_id=backend_id,
            result_schema_version="domain-backend-result-v1",
            algorithm_version=f"{backend_id}-algorithm-v1",
            settings_fingerprint="shared-settings",
            adapter_owner="backend-selection-test",
            native_evidence_kind=(
                "m6_orientation_evidence_v1"
                if backend_id == M6_ORIENTATION_COMPONENTS_BACKEND_ID
                else "m3_m6_lattice_evidence_v1"
            ),
            capabilities=("common_partition",),
        )
        self.analyzed_frames: list[int] = []

    def analyze_frame(
        self,
        frame,
        *,
        frame_index: int,
        geometry_mode: str,
    ) -> M6FrameComputation:
        del geometry_mode
        self.analyzed_frames.append(frame_index)
        evidence = (
            M6OrientationComponentsEvidence(
                assignment_status=(("molecule-1", "assigned"),),
                q6=(("molecule-1", 0.75),),
            )
            if self.backend_identity.backend_id
            == M6_ORIENTATION_COMPONENTS_BACKEND_ID
            else M3M6LatticeNetworkEvidence(
                point_roles=(("molecule-1", "core"),),
                boundary_reasons=(("molecule-1", None),),
                point_domain_ids=(("molecule-1", "domain-1"),),
                domains=(M3M6LatticeDomainEvidence(
                    lattice_domain_id="domain-1",
                    dominant_symmetry="mixed",
                    confidence=0.8,
                    qc_flags=("boundary_adjacent",),
                    orientation_reference_channel="m3_lattice",
                    m3_m6_orientation_relation_status="available",
                    provenance_fingerprint="domain-provenance",
                ),),
                producer_fingerprints=(("network", "network-provenance"),),
            )
        )
        return M6FrameComputation(
            frame_index=frame_index,
            molecules=frame.molecules,
            analyzed_pixels_xy=frame.analyzed_pixels_xy,
            pixel_area_nm2=frame.pixel_area_nm2,
            full_domains=(
                M6ComponentMembership(
                    lattice_domain_id="domain-1",
                    source_ids=("molecule-1",),
                    core_source_ids=("molecule-1",),
                ),
            ),
            small_ordered_islands=(),
            coordinate_frame=frame.coordinate_frame,
            coordinate_transform_fingerprint=(
                frame.coordinate_transform_fingerprint
            ),
            backend_identity=self.backend_identity,
            native_evidence=evidence,
        )


def test_request_requires_an_available_backend_identity() -> None:
    adapter = _BackendAdapter(M6_ORIENTATION_COMPONENTS_BACKEND_ID)
    module = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={},
    )

    with pytest.raises(TypeError, match="backend_id"):
        DomainAnalysisRequest(frame_range=range(1))
    request = DomainAnalysisRequest(
        frame_range=range(1),
        backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    )
    assert request.backend_id == M6_ORIENTATION_COMPONENTS_BACKEND_ID
    assert module.run(_series(), request).m6_gate is not None
    with pytest.raises(ValueError, match="backend_id"):
        DomainAnalysisRequest(frame_range=range(1), backend_id=None)
    with pytest.raises(ValueError, match="Unavailable domain backend"):
        module.run(
            _series(),
            DomainAnalysisRequest(frame_range=range(1), backend_id="missing"),
        )


def test_run_qualifies_snapshot_and_cache_by_selected_backend() -> None:
    classic = _BackendAdapter(M6_ORIENTATION_COMPONENTS_BACKEND_ID)
    network = _BackendAdapter(M3_M6_LATTICE_NETWORK_BACKEND_ID)
    module = DomainAnalysisModule(
        {
            classic.backend_identity.backend_id: classic,
            network.backend_identity.backend_id: network,
        },
        classifier_adapters={},
    )

    classic_result = module.run(
        _series(),
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
        ),
    )
    network_result = module.run(
        _series(),
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M3_M6_LATTICE_NETWORK_BACKEND_ID,
        ),
    )

    assert classic_result.m6_gate is not None
    assert network_result.m6_gate is not None
    classic_frame = classic_result.m6_gate.frames[0]
    network_frame = network_result.m6_gate.frames[0]
    assert classic_frame.full_domains == network_frame.full_domains
    assert classic_frame.m6_gate_fingerprint != network_frame.m6_gate_fingerprint
    assert isinstance(
        classic_frame.native_evidence,
        M6OrientationComponentsEvidence,
    )
    assert isinstance(
        network_frame.native_evidence,
        M3M6LatticeNetworkEvidence,
    )
    assert network_frame.native_evidence.domains[0].dominant_symmetry == "mixed"
    payload = backend_evidence_to_payload(network_frame.native_evidence)
    assert backend_evidence_from_payload(payload, path="native_evidence") == (
        network_frame.native_evidence
    )
    assert classic.analyzed_frames == [0]
    assert network.analyzed_frames == [0]


def test_network_runtime_adapter_delegates_to_lattice_pipeline() -> None:
    series = _series()
    adapter = MolTrackLatticeNetworkAdapter(series)
    settings = TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
    configuration = M6RunConfiguration(
        backend_identity=adapter.backend_identity,
        settings=settings,
        first_shell_geometry=FirstShellGeometryPolicy.fixed(
            r_min_nm=settings.first_shell_r_min_nm,
            r_max_nm=settings.first_shell_r_max_nm,
        ),
    )
    result = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={},
    ).run(
        series,
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M3_M6_LATTICE_NETWORK_BACKEND_ID,
            m6_configuration=configuration,
        ),
    )

    assert result.m6_gate is not None
    frame = result.m6_gate.frames[0]
    assert frame.backend_identity == adapter.backend_identity
    assert isinstance(frame.native_evidence, M3M6LatticeNetworkEvidence)


def test_m6_cache_rejects_different_result_for_identical_full_key() -> None:
    adapter = _BackendAdapter(M6_ORIENTATION_COMPONENTS_BACKEND_ID)
    canonical = canonicalize_frame(
        _series(), frame_index=0, geometry_mode="segmentation_preferred"
    )
    computation = adapter.analyze_frame(
        canonical, frame_index=0, geometry_mode="segmentation_preferred"
    )
    changed = replace(
        computation,
        native_evidence=M6OrientationComponentsEvidence(
            assignment_status=(("molecule-1", "assigned"),),
            q6=(("molecule-1", 0.25),),
        ),
    )
    key = m6_frame_cache_key(
        canonical,
        geometry_mode="segmentation_preferred",
        backend_identity=adapter.backend_identity,
    )
    cache = M6FrameCache()
    cache.put(key, computation)

    with pytest.raises(ValueError, match="different result fingerprint"):
        cache.put(key, changed)


def test_network_sample_coordinates_rotate_fov_with_canonical_points() -> None:
    series = _series(scan_angle_deg=90.0)
    canonical = canonicalize_frame(
        series, frame_index=0, geometry_mode="segmentation_preferred"
    )
    sample = _sample_coordinates(
        canonical,
        frame_index=0,
        geometry=series.frame(0).geometry,
    )

    assert sample.points_xy_nm == tuple(
        value.centroid_xy_nm for value in canonical.molecules
    )
    assert sample.valid_fov_polygon_xy_nm == (
        (0.0, 0.0), (0.0, 4.0), (-4.0, 4.0), (-4.0, 0.0)
    )
    assert sample.scan_angle_deg == 90.0


def _series(*, scan_angle_deg: float = 0.0) -> DomainAnalysisSeries:
    annotation = M6SourceAnnotation(
        source_id="molecule-1",
        source_view="raw",
        bbox_xyxy=(1.0, 1.0, 2.0, 2.0),
        mask_shape=(4, 4),
        mask_pixels_xy=((1, 1),),
    )
    geometry = M6FrameGeometry(
        physical_frame_id="physical-frame-1",
        raw_shape=(4, 4),
        expanded_shape=(4, 4),
        frame_origin_xy=(0.0, 0.0),
        canvas_offset_xy=(0.0, 0.0),
        pixel_size_nm=(1.0, 1.0),
        scan_angle_deg=scan_angle_deg,
        registration_fingerprint="registration-1",
    )
    return DomainAnalysisSeries(
        frames=(
            DomainAnalysisFrame(
                frame_index=0,
                source_view="raw",
                geometry=geometry,
                annotations=(annotation,),
            ),
        ),
    )
