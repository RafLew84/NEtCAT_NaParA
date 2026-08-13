from __future__ import annotations

from dataclasses import replace

import pytest
import numpy as np

from moltrack.analysis.domain_analysis import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ABCOrientationDiagnosticEvidence,
    ABC_ORIENTATION_CLASSIFIER_ID,
    ABC_ORIENTATION_CLASSIFIER_SCHEMA_VERSION,
    M3_M6_LATTICE_NETWORK_BACKEND_ID,
    MOLECULE_DIAGNOSTIC_STAGE_IDS,
    DomainAnalysisFrame,
    DomainAnalysisModule,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisSeries,
    DomainAnalysisSessionState,
    DomainBackendIdentity,
    ClassifierMoleculePrediction,
    M3M6LatticeDomainEvidence,
    M3M6LatticeNetworkEvidence,
    M6ComponentMembership,
    M6FrameComputation,
    M6FrameGeometry,
    M6SourceAnnotation,
    NetworkDomainSizeEvidence,
    NetworkDomainEdgesEvidence,
    NetworkDomainPartitionEvidence,
    NetworkSeedGrowthEvidence,
    NetworkLocalOrderEvidence,
)
from moltrack.persistence.domain_backend_payload import (
    backend_evidence_from_payload,
    backend_evidence_to_payload,
)
from moltrack.persistence.domain_analysis_session import (
    domain_analysis_state_from_payload,
    domain_analysis_state_to_payload,
)
from moltrack.ui.domain_analysis_diagnostics import MoleculeDiagnosticView
from moltrack.ui.domain_backend_adapters import MolTrackLatticeNetworkAdapter


class _NetworkOrientationAdapter:
    backend_identity = DomainBackendIdentity(
        backend_id=M3_M6_LATTICE_NETWORK_BACKEND_ID,
        result_schema_version="domain-backend-result-v1",
        algorithm_version="network-orientation-test-v1",
        settings_fingerprint="network-orientation-settings",
        adapter_owner="network-orientation-test",
        native_evidence_kind="m3_m6_lattice_evidence_v1",
        capabilities=("common_partition",),
    )

    def analyze_frame(
        self, frame, *, frame_index: int, geometry_mode: str
    ) -> M6FrameComputation:
        del geometry_mode
        source_id = frame.molecules[0].source_id
        domain_id = "network-domain-1"
        return M6FrameComputation(
            frame_index=frame_index,
            molecules=frame.molecules,
            analyzed_pixels_xy=frame.analyzed_pixels_xy,
            pixel_area_nm2=frame.pixel_area_nm2,
            full_domains=(M6ComponentMembership(
                lattice_domain_id=domain_id,
                source_ids=(source_id,),
                core_source_ids=(source_id,),
            ),),
            small_ordered_islands=(),
            coordinate_frame=frame.coordinate_frame,
            coordinate_transform_fingerprint=frame.coordinate_transform_fingerprint,
            backend_identity=self.backend_identity,
            native_evidence=M3M6LatticeNetworkEvidence(
                point_roles=((source_id, "core"),),
                boundary_reasons=((source_id, None),),
                point_domain_ids=((source_id, domain_id),),
                domains=(M3M6LatticeDomainEvidence(
                    domain_id, "sixfold", 0.8, (), "m6", "available", "domain-fp"
                ),),
                producer_fingerprints=(("network", "network-fp"),),
            ),
        )


class _RejectedNetworkOrientationClassifier:
    classifier_id = ABC_ORIENTATION_CLASSIFIER_ID
    classifier_schema_version = ABC_ORIENTATION_CLASSIFIER_SCHEMA_VERSION
    classifier_settings_fingerprint = "abc-network-settings"
    classifier_algorithm_version = "abc-network-v1"
    domain_aggregation_preset = ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1

    def classify_domain(self, raw_frame, **kwargs):
        del raw_frame
        source_id = kwargs["molecules"][0].source_id
        return (ClassifierMoleculePrediction(
            source_id=source_id,
            orientation_label=None,
            evidence_strength=0.0,
            diagnostic_evidence=ABCOrientationDiagnosticEvidence(
                raw_orientation_label="A",
                threshold_candidate_label="A",
                nearest_distance=0.42,
                threshold_candidate_distance=0.42,
                margin=0.20,
                distance_threshold=0.30,
                minimum_margin=0.05,
                threshold_decision="rejected",
                threshold_reason_code="below_distance_threshold",
                component_filter_decision="not_evaluated",
                component_filter_reason_code="upstream_threshold_rejected",
            ),
        ),)


def test_runtime_network_backend_publishes_complete_native_funnel() -> None:
    series = _single_point_series()
    adapter = MolTrackLatticeNetworkAdapter(series)

    result = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={},
    ).run(
        series,
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M3_M6_LATTICE_NETWORK_BACKEND_ID,
            m6_configuration=adapter.default_run_configuration(),
        ),
    )

    assert len(result.molecule_diagnostic_funnels) == 1
    funnel = result.molecule_diagnostic_funnels[0]
    assert tuple(stage.stage_id for stage in funnel.stages) == (
        MOLECULE_DIAGNOSTIC_STAGE_IDS
    )
    local_order = funnel.stage("local_order")
    assert local_order.execution_status == "completed"
    assert local_order.decision == "rejected"
    assert local_order.reason.code == "insufficient_neighbors"
    assert local_order.evidence is not None
    assert isinstance(local_order.evidence.payload, NetworkLocalOrderEvidence)
    assert local_order.evidence.payload.q3 is None
    assert local_order.evidence.payload.q6 is None
    assert local_order.provenance is not None
    assert local_order.provenance.output_fingerprint == dict(
        result.m6_gate.frames[0].native_evidence.producer_fingerprints
    )["local_order"]

    domain_size = funnel.stage("domain_size")
    assert domain_size.execution_status == "completed"
    assert domain_size.decision == "rejected"
    assert domain_size.evidence is not None
    assert isinstance(domain_size.evidence.payload, NetworkDomainSizeEvidence)
    assert domain_size.evidence.payload.component_molecule_count is None
    assert domain_size.evidence.payload.domain_qc_flags is None
    assert domain_size.reason.code == "not_a_domain_member"
    partition = funnel.stage("domain_partition")
    assert partition.evidence is not None
    assert isinstance(
        partition.evidence.payload, NetworkDomainPartitionEvidence
    )
    assert partition.evidence.payload.domain_qc_flags is None
    seed = funnel.stage("seed_growth")
    assert seed.evidence is not None
    assert isinstance(seed.evidence.payload, NetworkSeedGrowthEvidence)
    assert seed.evidence.payload.stable_threshold_offsets is None
    assert funnel.terminal_domain_miss is funnel.stage("first_shell")

    native = result.m6_gate.frames[0].native_evidence
    payload = backend_evidence_to_payload(native)
    assert backend_evidence_from_payload(
        payload, path="native_evidence"
    ) == native


def test_network_native_view_is_selected_only_by_capability() -> None:
    series = _single_point_series()
    adapter = MolTrackLatticeNetworkAdapter(series)
    result = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={},
    ).run(
        series,
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M3_M6_LATTICE_NETWORK_BACKEND_ID,
            m6_configuration=adapter.default_run_configuration(),
        ),
    )
    funnel = result.molecule_diagnostic_funnels[0]
    view = MoleculeDiagnosticView(funnel)

    native_view = view.native_evidence("domain_edges")
    assert native_view is not None
    assert native_view.capability == "typed_domain_edges"
    assert isinstance(native_view.payload, NetworkDomainEdgesEvidence)

    hidden_identity = replace(funnel.backend_identity, capabilities=())
    hidden_view = MoleculeDiagnosticView(replace(
        funnel, backend_identity=hidden_identity
    ))
    assert hidden_view.native_evidence("domain_edges") is None


def test_detailed_network_contract_rejects_broken_references_and_provenance() -> None:
    series = _single_point_series()
    adapter = MolTrackLatticeNetworkAdapter(series)
    result = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={},
    ).run(
        series,
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M3_M6_LATTICE_NETWORK_BACKEND_ID,
            m6_configuration=adapter.default_run_configuration(),
        ),
    )
    native = result.m6_gate.frames[0].native_evidence
    source_id = native.point_roles[0][0]

    with pytest.raises(ValueError, match="unknown lattice domain"):
        replace(
            native,
            point_roles=((source_id, "core"),),
            point_domain_ids=((source_id, "missing-domain"),),
        )
    with pytest.raises(ValueError, match="every stage producer fingerprint"):
        replace(
            native,
            producer_fingerprints=tuple(
                item for item in native.producer_fingerprints
                if item[0] != "local_order"
            ),
        )
    with pytest.raises(ValueError, match="Unsupported best_model"):
        replace(native.point_evidence[0], best_model="typo")
    with pytest.raises(ValueError, match="edge aggregates"):
        replace(
            native,
            point_evidence=(replace(
                native.point_evidence[0],
                incident_edge_decisions=("conflict_boundary",),
                retained_edge_count=1,
                core_eligible_edge_count=1,
            ),),
        )
    with pytest.raises(ValueError, match="edge aggregates"):
        replace(
            native,
            point_evidence=(replace(
                native.point_evidence[0],
                incident_edge_decisions=("conflict_boundary",),
                incident_edge_rejection_reasons=(),
            ),),
        )
    with pytest.raises(ValueError, match="Only boundary points"):
        replace(
            native,
            point_roles=((source_id, "boundary"),),
            boundary_reasons=((source_id, None),),
            point_domain_ids=((source_id, None),),
        )


def test_network_terminal_misses_count_each_non_domain_molecule_once() -> None:
    series = _single_point_series()
    adapter = MolTrackLatticeNetworkAdapter(series)
    result = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={},
    ).run(
        series,
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M3_M6_LATTICE_NETWORK_BACKEND_ID,
            m6_configuration=adapter.default_run_configuration(),
        ),
    )

    terminal_misses = tuple(
        funnel.terminal_domain_miss
        for funnel in result.molecule_diagnostic_funnels
        if funnel.terminal_domain_miss is not None
    )
    rejected_partitions = tuple(
        funnel
        for funnel in result.molecule_diagnostic_funnels
        if funnel.stage("domain_partition").decision != "accepted"
    )
    assert len(terminal_misses) == len(rejected_partitions) == 1


def test_session_restore_rebuilds_network_funnel_from_persisted_evidence() -> None:
    series = _single_point_series()
    adapter = MolTrackLatticeNetworkAdapter(series)
    request = DomainAnalysisRequest(
        frame_range=range(1),
        backend_id=M3_M6_LATTICE_NETWORK_BACKEND_ID,
        m6_configuration=adapter.default_run_configuration(),
    )
    result = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={},
    ).run(series, request)
    state = DomainAnalysisSessionState(
        draft=request,
        published_result=DomainAnalysisPublication(
            request=request, result=result
        ),
        run_status="completed",
    )

    restored = domain_analysis_state_from_payload(
        domain_analysis_state_to_payload(state)
    )

    assert restored.published_result is not None
    funnels = restored.published_result.result.molecule_diagnostic_funnels
    assert len(funnels) == 1
    evidence = funnels[0].stage("local_order").evidence
    assert evidence is not None
    assert isinstance(evidence.payload, NetworkLocalOrderEvidence)


def test_network_threshold_rejection_keeps_raw_abc_evidence() -> None:
    adapter = _NetworkOrientationAdapter()
    classifier = _RejectedNetworkOrientationClassifier()
    result = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={classifier.classifier_id: classifier},
    ).run(
        _single_point_series(),
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M3_M6_LATTICE_NETWORK_BACKEND_ID,
            classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
        ),
    )

    funnel = result.molecule_diagnostic_funnels[0]
    raw = funnel.stage("orientation_raw")
    assert raw.evidence is not None
    assert raw.evidence.value("raw_orientation_label") == "A"
    assert funnel.stage("orientation_threshold").decision == "rejected"


def _single_point_series() -> DomainAnalysisSeries:
    return DomainAnalysisSeries(frames=(DomainAnalysisFrame(
        frame_index=0,
        source_view="raw",
        geometry=M6FrameGeometry(
            physical_frame_id="network-frame-1",
            raw_shape=(8, 8),
            expanded_shape=(8, 8),
            frame_origin_xy=(0.0, 0.0),
            canvas_offset_xy=(0.0, 0.0),
            pixel_size_nm=(1.0, 1.0),
            scan_angle_deg=0.0,
            registration_fingerprint="network-registration-1",
        ),
        annotations=(M6SourceAnnotation(
            source_id="network-point-1",
            source_view="raw",
            bbox_xyxy=(3.0, 3.0, 4.0, 4.0),
            mask_shape=(8, 8),
            mask_pixels_xy=((3, 3),),
        ),),
        raw_frame=np.zeros((8, 8), dtype=np.float32),
    ),))
