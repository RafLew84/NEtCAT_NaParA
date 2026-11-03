from __future__ import annotations

from dataclasses import replace

import numpy as np

from moltrack.analysis.domain_analysis import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ABCOrientationDiagnosticEvidence,
    ABC_ORIENTATION_CLASSIFIER_ID,
    ABC_ORIENTATION_CLASSIFIER_SCHEMA_VERSION,
    ClassifierAnalysisError,
    MOLECULE_DIAGNOSTIC_STAGE_IDS,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    DomainAnalysisFrame,
    DomainAnalysisModule,
    DomainAnalysisRequest,
    DomainAnalysisSeries,
    DomainBackendIdentity,
    ClassifierMoleculePrediction,
    M6ComponentMembership,
    M6FrameComputation,
    M6FrameGeometry,
    M6OrientationComponentsEvidence,
    LocalOrderEvidence,
    M6SourceAnnotation,
)
from moltrack.ui.domain_analysis_diagnostics import MoleculeDiagnosticView
from moltrack.ui.domain_backend_adapters import MolTrackOrientationComponentsAdapter


class _ClassicM6Adapter:
    def __init__(self) -> None:
        self.backend_identity = DomainBackendIdentity(
            backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
            result_schema_version="domain-backend-result-v1",
            algorithm_version="classic-diagnostic-test-v1",
            settings_fingerprint="classic-settings",
            adapter_owner="classic-diagnostic-test",
            native_evidence_kind="m6_orientation_evidence_v1",
            capabilities=("common_partition", "orientation_components"),
        )

    def analyze_frame(
        self,
        frame,
        *,
        frame_index: int,
        geometry_mode: str,
    ) -> M6FrameComputation:
        del geometry_mode
        return M6FrameComputation(
            frame_index=frame_index,
            molecules=frame.molecules,
            analyzed_pixels_xy=frame.analyzed_pixels_xy,
            pixel_area_nm2=frame.pixel_area_nm2,
            full_domains=(M6ComponentMembership(
                lattice_domain_id="classic-domain-1",
                source_ids=("assigned",),
            ),),
            small_ordered_islands=(),
            coordinate_frame=frame.coordinate_frame,
            coordinate_transform_fingerprint=(
                frame.coordinate_transform_fingerprint
            ),
            backend_identity=self.backend_identity,
            native_evidence=M6OrientationComponentsEvidence(
                assignment_status=(
                    ("assigned", "assigned"),
                    ("uncertain", "boundary_or_disordered"),
                ),
                q6=(("assigned", 0.82), ("uncertain", 0.41)),
                neighbor_count=(("assigned", 6), ("uncertain", 4)),
                orientation_deg=(("assigned", 12.5), ("uncertain", 27.0)),
                local_order_status=(
                    ("assigned", "valid_order"),
                    ("uncertain", "valid_order"),
                ),
                component_type=(
                    ("assigned", "full_domain"),
                    ("uncertain", "unassigned"),
                ),
            ),
        )


class _OrientationM6Adapter(_ClassicM6Adapter):
    def analyze_frame(
        self,
        frame,
        *,
        frame_index: int,
        geometry_mode: str,
    ) -> M6FrameComputation:
        del geometry_mode
        source_ids = tuple(value.source_id for value in frame.molecules)
        return M6FrameComputation(
            frame_index=frame_index,
            molecules=frame.molecules,
            analyzed_pixels_xy=frame.analyzed_pixels_xy,
            pixel_area_nm2=frame.pixel_area_nm2,
            full_domains=(M6ComponentMembership(
                lattice_domain_id="classic-domain-1",
                source_ids=source_ids,
            ),),
            small_ordered_islands=(),
            coordinate_frame=frame.coordinate_frame,
            coordinate_transform_fingerprint=(
                frame.coordinate_transform_fingerprint
            ),
            backend_identity=self.backend_identity,
            native_evidence=M6OrientationComponentsEvidence(
                assignment_status=tuple(
                    (source_id, "assigned") for source_id in source_ids
                ),
                q6=tuple((source_id, 0.8) for source_id in source_ids),
                neighbor_count=tuple((source_id, 6) for source_id in source_ids),
                orientation_deg=tuple((source_id, 10.0) for source_id in source_ids),
                local_order_status=tuple(
                    (source_id, "valid_order") for source_id in source_ids
                ),
                component_type=tuple(
                    (source_id, "full_domain") for source_id in source_ids
                ),
            ),
        )


class _RejectedOrientationClassifier:
    classifier_id = ABC_ORIENTATION_CLASSIFIER_ID
    classifier_schema_version = ABC_ORIENTATION_CLASSIFIER_SCHEMA_VERSION
    classifier_settings_fingerprint = "abc-settings"
    classifier_algorithm_version = "abc-diagnostic-test-v1"
    domain_aggregation_preset = ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1

    def classify_domain(
        self,
        raw_frame,
        *,
        frame_index: int,
        physical_frame_id: str,
        lattice_domain_id: str,
        molecules,
    ) -> tuple[ClassifierMoleculePrediction, ...]:
        del raw_frame, frame_index, physical_frame_id, lattice_domain_id
        assert tuple(value.source_id for value in molecules) == (
            "component-filtered",
            "threshold-rejected",
        )
        return (
            ClassifierMoleculePrediction(
                source_id="component-filtered",
                orientation_label=None,
                evidence_strength=0.0,
                diagnostic_evidence=ABCOrientationDiagnosticEvidence(
                    raw_orientation_label="B",
                    threshold_candidate_label="B",
                    nearest_distance=0.10,
                    threshold_candidate_distance=0.10,
                    margin=0.20,
                    distance_threshold=0.30,
                    minimum_margin=0.05,
                    threshold_decision="accepted",
                    threshold_reason_code="accepted_result",
                    component_filter_decision="filtered",
                    component_filter_reason_code="component_below_minimum_size",
                ),
            ),
            ClassifierMoleculePrediction(
                source_id="threshold-rejected",
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
            ),
        )


class _FailedOrientationClassifier(_RejectedOrientationClassifier):
    def classify_domain(self, *args, **kwargs):
        del args, kwargs
        raise ClassifierAnalysisError(
            "synthetic diagnostic failure",
            frame_index=0,
        )


class _CancelingOrientationClassifier(_RejectedOrientationClassifier):
    def __init__(self, cancel_signal: dict[str, bool]) -> None:
        self._cancel_signal = cancel_signal

    def classify_domain(self, *args, **kwargs):
        predictions = super().classify_domain(*args, **kwargs)
        self._cancel_signal["requested"] = True
        return predictions


def test_classic_backend_publishes_complete_honest_molecule_funnels() -> None:
    adapter = _ClassicM6Adapter()
    result = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={},
    ).run(
        _series(),
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
        ),
    )

    assert tuple(
        (value.frame_index, value.source_id)
        for value in result.molecule_diagnostic_funnels
    ) == ((0, "assigned"), (0, "uncertain"))
    assigned, uncertain = result.molecule_diagnostic_funnels
    assert tuple(value.stage_id for value in assigned.stages) == (
        MOLECULE_DIAGNOSTIC_STAGE_IDS
    )
    local_order = assigned.stage("local_order")
    assert local_order.execution_status == "completed"
    assert local_order.decision == "accepted"
    assert local_order.evidence is not None
    assert local_order.evidence.kind == "classic_m6_local_order_v1"
    assert isinstance(local_order.evidence.payload, LocalOrderEvidence)
    assert local_order.evidence.payload.q6 == 0.82
    assert local_order.evidence.value("q6") == 0.82
    assert local_order.evidence.value("orientation_deg") == 12.5
    assert local_order.evidence.value("m3_availability") == "unavailable"
    assert local_order.provenance is not None

    for stage_id in ("local_symmetry", "domain_edges"):
        stage = assigned.stage(stage_id)
        assert stage.execution_status == "unavailable"
        assert stage.decision == "not_evaluated"
        assert stage.reason.code == "backend_capability_absent"
        assert stage.evidence is None

    seed_growth = uncertain.stage("seed_growth")
    assert seed_growth.execution_status == "completed"
    assert seed_growth.decision == "ambiguous"
    assert seed_growth.reason.code == "boundary_or_disordered"
    assert seed_growth.evidence is not None
    assert seed_growth.evidence.value("native_assignment_status") == (
        "boundary_or_disordered"
    )
    assert seed_growth.evidence.value("core_halo_role") is None
    assert seed_growth.evidence.value("core_halo_availability") == "unavailable"
    assert seed_growth.evidence.value("explicit_boundary") is None
    assert seed_growth.evidence.value("explicit_boundary_availability") == (
        "unavailable"
    )
    assert uncertain.stage("domain_partition").reason.code == (
        "boundary_or_disordered"
    )
    assert uncertain.terminal_domain_miss is uncertain.stage("seed_growth")


def test_runtime_classic_adapter_retains_per_molecule_native_evidence() -> None:
    series = _series()
    adapter = MolTrackOrientationComponentsAdapter(series)
    result = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={},
    ).run(
        series,
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
            m6_configuration=adapter.default_run_configuration(),
        ),
    )

    assert result.m6_gate is not None
    native = result.m6_gate.frames[0].native_evidence
    assert isinstance(native, M6OrientationComponentsEvidence)
    q6_by_id = dict(native.q6)
    for funnel in result.molecule_diagnostic_funnels:
        assert funnel.stage("first_shell").execution_status == "completed"
        local_order = funnel.stage("local_order")
        assert local_order.execution_status == "completed"
        assert local_order.evidence is not None
        assert local_order.evidence.value("q6") == q6_by_id[funnel.source_id]


def test_rejected_orientation_keeps_raw_threshold_and_component_evidence() -> None:
    adapter = _OrientationM6Adapter()
    classifier = _RejectedOrientationClassifier()
    result = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={classifier.classifier_id: classifier},
    ).run(
        _orientation_series(),
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
            classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
        ),
    )
    funnels = {
        value.source_id: value for value in result.molecule_diagnostic_funnels
    }

    threshold = funnels["threshold-rejected"]
    raw = threshold.stage("orientation_raw")
    assert raw.execution_status == "completed"
    assert raw.evidence is not None
    assert raw.evidence.value("raw_orientation_label") == "A"
    threshold_decision = threshold.stage("orientation_threshold")
    assert threshold_decision.decision == "rejected"
    assert threshold_decision.reason.code == "below_distance_threshold"
    assert threshold.stage("orientation_component_filter").reason.code == (
        "upstream_threshold_rejected"
    )

    filtered = funnels["component-filtered"]
    filtered_raw = filtered.stage("orientation_raw")
    assert filtered_raw.evidence is not None
    assert filtered_raw.evidence.value("raw_orientation_label") == "B"
    assert filtered.stage("orientation_threshold").decision == "accepted"
    component_filter = filtered.stage("orientation_component_filter")
    assert component_filter.execution_status == "completed"
    assert component_filter.decision == "filtered"
    assert component_filter.reason.code == "component_below_minimum_size"
    assert filtered.stage("automatic_result").decision == "ambiguous"


def test_failed_requested_orientation_is_not_reported_as_not_requested() -> None:
    adapter = _OrientationM6Adapter()
    classifier = _FailedOrientationClassifier()

    result = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={classifier.classifier_id: classifier},
    ).run(
        _orientation_series(),
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
            classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
        ),
    )

    assert result.run_status == "completed_with_errors"
    for funnel in result.molecule_diagnostic_funnels:
        descriptor = funnel.stage("orientation_descriptor")
        assert descriptor.execution_status == "failed"
        assert descriptor.reason.code == "classifier_failed"
        assert descriptor.reason.native_code == "synthetic diagnostic failure"
        assert funnel.stage("orientation_raw").reason.code == (
            "upstream_classifier_failed"
        )
        assert funnel.stage("effective_result").reason.code == (
            "automatic_classifier_failed"
        )


def test_canceled_requested_orientation_keeps_its_execution_cause() -> None:
    cancel_signal = {"requested": False}
    adapter = _OrientationM6Adapter()
    classifier = _CancelingOrientationClassifier(cancel_signal)

    result = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={classifier.classifier_id: classifier},
    ).run(
        _orientation_series(),
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
            classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
        ),
        is_cancelled=lambda: cancel_signal["requested"],
    )

    assert result.run_status == "canceled"
    for funnel in result.molecule_diagnostic_funnels:
        descriptor = funnel.stage("orientation_descriptor")
        assert descriptor.execution_status == "not_run"
        assert descriptor.reason.code == "classifier_canceled"
        assert funnel.stage("effective_result").reason.code == (
            "automatic_classifier_canceled"
        )


def test_thin_diagnostic_view_summarizes_and_expands_the_same_trace() -> None:
    adapter = _OrientationM6Adapter()
    classifier = _RejectedOrientationClassifier()
    result = DomainAnalysisModule(
        {adapter.backend_identity.backend_id: adapter},
        classifier_adapters={classifier.classifier_id: classifier},
    ).run(
        _orientation_series(),
        DomainAnalysisRequest(
            frame_range=range(1),
            backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID,
            classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
        ),
    )
    funnel = next(
        value
        for value in result.molecule_diagnostic_funnels
        if value.source_id == "component-filtered"
    )

    view = MoleculeDiagnosticView(funnel)

    assert view.summary.source_id == "component-filtered"
    assert view.summary.q6 == 0.8
    assert view.summary.raw_orientation_label == "B"
    assert view.summary.automatic_orientation_label == "Unknown orientation"
    assert view.summary.effective_orientation_label == "Unknown orientation"
    assert view.expanded_stages is funnel.stages
    assert view.stage("orientation_raw") is funnel.stage("orientation_raw")
    native_view = view.native_evidence("local_order")
    assert native_view is not None
    assert native_view.capability == "orientation_components"
    assert native_view.payload is funnel.stage("local_order").evidence.payload
    island = replace(
        funnel,
        stages=tuple(
            replace(stage, decision="filtered")
            if stage.stage_id in {"domain_partition", "domain_size"}
            else stage
            for stage in funnel.stages
        ),
    )
    assert island.terminal_domain_miss is island.stage("domain_size")


def _series() -> DomainAnalysisSeries:
    annotations = tuple(
        M6SourceAnnotation(
            source_id=source_id,
            source_view="raw",
            bbox_xyxy=(x, 1.0, x + 1.0, 2.0),
            mask_shape=(4, 4),
            mask_pixels_xy=((int(x), 1),),
        )
        for source_id, x in (("assigned", 0.0), ("uncertain", 2.0))
    )
    return DomainAnalysisSeries(frames=(DomainAnalysisFrame(
        frame_index=0,
        source_view="raw",
        geometry=M6FrameGeometry(
            physical_frame_id="physical-frame-1",
            raw_shape=(4, 4),
            expanded_shape=(4, 4),
            frame_origin_xy=(0.0, 0.0),
            canvas_offset_xy=(0.0, 0.0),
            pixel_size_nm=(1.0, 1.0),
            scan_angle_deg=0.0,
            registration_fingerprint="registration-1",
        ),
        annotations=annotations,
    ),))


def _orientation_series() -> DomainAnalysisSeries:
    annotations = tuple(
        M6SourceAnnotation(
            source_id=source_id,
            source_view="raw",
            bbox_xyxy=(x, 1.0, x + 1.0, 2.0),
            mask_shape=(5, 5),
            mask_pixels_xy=((int(x), 1),),
        )
        for source_id, x in (
            ("component-filtered", 0.0),
            ("threshold-rejected", 2.0),
        )
    )
    return DomainAnalysisSeries(frames=(DomainAnalysisFrame(
        frame_index=0,
        source_view="raw",
        geometry=M6FrameGeometry(
            physical_frame_id="physical-frame-orientation",
            raw_shape=(5, 5),
            expanded_shape=(5, 5),
            frame_origin_xy=(0.0, 0.0),
            canvas_offset_xy=(0.0, 0.0),
            pixel_size_nm=(1.0, 1.0),
            scan_angle_deg=0.0,
            registration_fingerprint="registration-orientation",
        ),
        annotations=annotations,
        raw_frame=np.zeros((5, 5), dtype=np.float32),
    ),))
