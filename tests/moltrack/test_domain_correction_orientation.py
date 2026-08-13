from __future__ import annotations

import pytest

from moltrack.analysis.domain_analysis import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ABC_ORIENTATION_CLASSIFIER_ID,
    ABCOrientationDiagnosticEvidence,
    ApplyPreparedDomainCorrection,
    ClassifierConfiguration,
    ClassifierFrameResultProvenance,
    ClassifierIdentity,
    ClassifierOutcome,
    DomainAnalysisResult,
    DomainBackendIdentity,
    DomainCorrectionModule,
    DomainLabelSummary,
    EffectiveOrientationSubdomain,
    M6FrameGate,
    M6Gate,
    M6OrientationComponentsEvidence,
    M6PresentationProvenance,
    M6PublishedComponent,
    M6PublishedMolecule,
    ManualOrientationIntent,
    MoleculeClassification,
    PreparedDomainCorrection,
)
from moltrack.analysis.domain_analysis.classifier_models import (
    classifier_frame_result_fingerprint,
)


def test_manual_d_outside_m6_changes_only_effective_orientation() -> None:
    automatic = _automatic_result()
    automatic_classification = (
        automatic.classifier_outcomes[0].molecule_classifications[0]
    )
    module = DomainCorrectionModule()
    workspace = module.initialize(automatic)
    preview = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("outside",),
            orientation_label="D",
        ),
    )

    corrected = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection(preview),
    )
    projection = module.project(automatic, corrected)
    outside = projection.molecule("frame-0", "outside")

    assert corrected.revision == 1
    assert preview.changed_source_ids == ("outside",)
    assert outside.effective_orientation == "D"
    assert outside.effective_orientation_source == "manual"
    assert outside.effective_confidence is None
    assert outside.effective_domain_id is None
    assert projection.orientation_subdomains == (
        EffectiveOrientationSubdomain("frame-0", "domain-1", "A", ("full",)),
    )
    assert projection.automatic_result is automatic
    assert (
        projection.molecule("frame-0", "full").automatic_classification
        is automatic_classification
    )
    assert automatic.m6_gate.frames[0].outside_source_ids == ("outside",)


def test_manual_orientation_has_no_confidence_and_unresolvable_needs_reason() -> None:
    automatic = _automatic_result()
    module = DomainCorrectionModule()
    workspace = module.initialize(automatic)

    with pytest.raises(ValueError, match="requires a reason_code"):
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("island",),
            orientation_label="Unresolvable",
        )

    unresolved = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("island",),
            orientation_label="Unresolvable",
            reason_code="overlapping_signal",
        ),
    )
    workspace = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection(unresolved),
    )
    manual_a = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("outside",),
            orientation_label="A",
        ),
    )
    workspace = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection(manual_a),
    )

    projection = module.project(automatic, workspace)
    island = projection.molecule("frame-0", "island")
    outside = projection.molecule("frame-0", "outside")
    assert island.effective_orientation == "Unresolvable"
    assert island.manual_decision is not None
    assert island.manual_decision.reason_code == "overlapping_signal"
    assert island.effective_confidence is None
    assert outside.effective_orientation == "A"
    assert outside.effective_confidence is None
    assert projection.orientation_subdomains == (
        EffectiveOrientationSubdomain("frame-0", "domain-1", "A", ("full",)),
    )


def test_reset_reveals_only_an_automatic_result_compatible_with_m6() -> None:
    automatic = _automatic_result()
    projection = _assign_then_reset(automatic)

    restored = projection.molecule("frame-0", "full")
    assert restored.effective_orientation == "A"
    assert restored.effective_orientation_source == "automatic"
    assert restored.effective_confidence == 0.8
    assert restored.raw_orientation_evidence == _raw_evidence()

    stale_automatic = _automatic_result(
        classification_gate_fingerprint="stale-gate",
    )
    stale_projection = _assign_then_reset(stale_automatic)
    stale = stale_projection.molecule("frame-0", "full")
    assert stale.effective_orientation is None
    assert stale.effective_orientation_source == "none"
    assert stale.effective_confidence is None
    assert stale.automatic_classification is not None
    assert stale.raw_orientation_evidence == _raw_evidence()


def test_manual_orientation_subdomain_requires_effective_full_domain() -> None:
    automatic = _automatic_result()
    module = DomainCorrectionModule()
    workspace = module.initialize(automatic)
    preview = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("full", "outside"),
            orientation_label="Z",
        ),
    )
    workspace = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection(preview),
    )

    projection = module.project(automatic, workspace)
    assert projection.orientation_subdomains == (
        EffectiveOrientationSubdomain("frame-0", "domain-1", "Z", ("full",)),
    )


def test_apply_rejects_a_forged_preview_without_changing_the_workspace() -> None:
    automatic = _automatic_result()
    module = DomainCorrectionModule()
    workspace = module.initialize(automatic)
    intent = ManualOrientationIntent.assign(
        physical_frame_id="frame-0",
        source_ids=("outside",),
        orientation_label="D",
    )
    prepared = module.prepare(workspace, automatic, intent)
    forged = PreparedDomainCorrection(
        expected_revision=prepared.expected_revision,
        automatic_fingerprint=prepared.automatic_fingerprint,
        intent=prepared.intent,
        changed_source_ids=(),
    )

    with pytest.raises(ValueError, match="does not match"):
        module.dispatch(
            workspace,
            automatic,
            ApplyPreparedDomainCorrection(forged),
        )
    assert workspace.revision == 0
    assert workspace.orientation_decisions == ()


def _assign_then_reset(automatic: DomainAnalysisResult):
    module = DomainCorrectionModule()
    workspace = module.initialize(automatic)
    assign = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.assign(
            physical_frame_id="frame-0",
            source_ids=("full",),
            orientation_label="Z",
        ),
    )
    workspace = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection(assign),
    )
    reset = module.prepare(
        workspace,
        automatic,
        ManualOrientationIntent.reset(
            physical_frame_id="frame-0",
            source_ids=("full",),
        ),
    )
    workspace = module.dispatch(
        workspace,
        automatic,
        ApplyPreparedDomainCorrection(reset),
    )
    return module.project(automatic, workspace)


def _automatic_result(
    *,
    classification_gate_fingerprint: str | None = None,
) -> DomainAnalysisResult:
    frame = _frame_gate()
    configuration = _classifier_configuration()
    classifications = (
        MoleculeClassification(
            frame_index=0,
            physical_frame_id="frame-0",
            m6_gate_fingerprint=(
                classification_gate_fingerprint or frame.m6_gate_fingerprint
            ),
            lattice_domain_id="domain-1",
            source_id="full",
            m6_partition="full_domain",
            classification_status="classified",
            orientation_label="A",
            evidence_strength=0.8,
            component_id="component-a",
            identity=configuration.identity,
            diagnostic_evidence=_raw_evidence(),
        ),
        MoleculeClassification(
            frame_index=0,
            physical_frame_id="frame-0",
            m6_gate_fingerprint=frame.m6_gate_fingerprint,
            lattice_domain_id="island-1",
            source_id="island",
            m6_partition="small_ordered_island",
            classification_status="not_gated",
            orientation_label=None,
            evidence_strength=0.0,
            component_id=None,
            identity=configuration.identity,
        ),
        MoleculeClassification(
            frame_index=0,
            physical_frame_id="frame-0",
            m6_gate_fingerprint=frame.m6_gate_fingerprint,
            lattice_domain_id=None,
            source_id="outside",
            m6_partition="outside",
            classification_status="not_gated",
            orientation_label=None,
            evidence_strength=0.0,
            component_id=None,
            identity=configuration.identity,
        ),
    )
    outcome = ClassifierOutcome(
        status="completed",
        configuration=configuration,
        molecule_classifications=classifications,
        frame_result_provenance=(ClassifierFrameResultProvenance(
            frame_index=0,
            physical_frame_id="frame-0",
            cache_key_fingerprint="cache-key",
            frame_result_fingerprint=classifier_frame_result_fingerprint(
                classifications
            ),
        ),),
        domain_summaries=(_domain_summary(frame, configuration),),
    )
    return DomainAnalysisResult(
        run_status="completed",
        m6_gate=M6Gate((frame,)),
        classifier_status="completed",
        classifier_outcomes=(outcome,),
    )


def _frame_gate() -> M6FrameGate:
    return M6FrameGate(
        frame_index=0,
        physical_frame_id="frame-0",
        coordinate_frame="series_physical_nm",
        coordinate_transform_fingerprint="transform-0",
        presentation_provenance=M6PresentationProvenance(
            raw_shape=(1, 3),
            expanded_shape=(1, 3),
            source_view="raw",
            frame_origin_xy=(0.0, 0.0),
            canvas_offset_xy=(0.0, 0.0),
            registration_fingerprint="registration-0",
        ),
        source_geometry_fingerprint="geometry-0",
        backend_identity=DomainBackendIdentity(
            backend_id="m6_orientation_components",
            result_schema_version="domain-backend-result-v1",
            algorithm_version="m6-v1",
            settings_fingerprint="settings-v1",
            adapter_owner="correction-test",
            native_evidence_kind="m6_orientation_evidence_v1",
            capabilities=("common_partition",),
        ),
        native_evidence=M6OrientationComponentsEvidence((), ()),
        pixel_area_nm2=1.0,
        full_domains=(_component("domain-1", "full_domain", "full", 0),),
        small_ordered_islands=(
            _component("island-1", "small_ordered_island", "island", 1),
        ),
        outside_members=(_molecule("outside", 2),),
        outside_pixels_xy=((2, 0),),
        outside_area_nm2=1.0,
        analyzed_source_ids=("full", "island", "outside"),
        analyzed_pixels_xy=((0, 0), (1, 0), (2, 0)),
        analyzed_area_nm2=3.0,
    )


def _component(
    domain_id: str,
    component_type: str,
    source_id: str,
    x: int,
) -> M6PublishedComponent:
    molecule = _molecule(source_id, x)
    return M6PublishedComponent(
        lattice_domain_id=domain_id,
        component_type=component_type,
        members=(molecule,),
        core_source_ids=(source_id,),
        halo_source_ids=(),
        footprint_pixels_xy=((x, 0),),
        footprint_area_nm2=1.0,
        centroid_xy_nm=molecule.point_xy_nm,
        bounds_xyxy_nm=(*molecule.point_xy_nm, *molecule.point_xy_nm),
    )


def _molecule(source_id: str, x: int) -> M6PublishedMolecule:
    return M6PublishedMolecule(
        source_id=source_id,
        source_kind="segmentation",
        point_xy_nm=(float(x), 0.0),
        raw_centroid_xy=(float(x), 0.0),
    )


def _classifier_configuration() -> ClassifierConfiguration:
    return ClassifierConfiguration(
        identity=ClassifierIdentity(
            classifier_id=ABC_ORIENTATION_CLASSIFIER_ID,
            schema_version="abc-v1",
            settings_fingerprint="abc-settings-v1",
            algorithm_version="abc-algorithm-v1",
        ),
        aggregation_preset=ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    )


def _raw_evidence() -> ABCOrientationDiagnosticEvidence:
    return ABCOrientationDiagnosticEvidence(
        raw_orientation_label="A",
        threshold_candidate_label="A",
        nearest_distance=0.1,
        threshold_candidate_distance=0.1,
        margin=0.3,
        distance_threshold=0.4,
        minimum_margin=0.05,
        threshold_decision="accepted",
        threshold_reason_code="accepted_result",
        component_filter_decision="accepted",
        component_filter_reason_code="accepted_component",
    )


def _domain_summary(
    frame: M6FrameGate,
    configuration: ClassifierConfiguration,
) -> DomainLabelSummary:
    return DomainLabelSummary(
        frame_index=0,
        physical_frame_id="frame-0",
        m6_gate_fingerprint=frame.m6_gate_fingerprint,
        lattice_domain_id="domain-1",
        label="A",
        molecule_count=1,
        counts=(("A", 1), ("B", 0), ("C", 0), ("Unknown orientation", 0)),
        evidence_fraction_of_domain=(("A", 0.8), ("B", 0.0), ("C", 0.0)),
        coherent_evidence_fraction_of_domain=(
            ("A", 0.8), ("B", 0.0), ("C", 0.0)
        ),
        resolved_fraction=1.0,
        resolved_evidence_fraction_of_domain=0.8,
        dominant_class="A",
        dominance_margin=0.8,
        reason="dominant_class_passed",
        configuration=configuration,
    )
