from __future__ import annotations

from dataclasses import replace
from functools import partial
from typing import Literal

import numpy as np
import pytest

from moltrack.analysis.domain_analysis import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ClassifierAnalysisError,
    ClassifierMoleculePrediction,
    ClassifierMoleculeInput,
    DomainAggregationPreset,
    DomainAnalysisFrame,
    DomainAnalysisModule,
    DomainAnalysisRequest,
    DomainAnalysisSeries,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    M6CanonicalFrame,
    M6ComponentMembership,
    M6FrameComputation,
    M6FrameGeometry,
    M6OrientationComponentsEvidence,
    M6SourceAnnotation,
    TextureABCClassifierAdapter,
    m6_orientation_components_identity,
)
from moltrack.analysis.texture_domain_analysis import TTMAPP_TEXTURE_DOMAIN_PRESET
from domain_analysis_test_support import domain_analysis_module as DomainAnalysisModule

DomainAnalysisRequest = partial(
    DomainAnalysisRequest, backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID
)


class _FullDomainM6Adapter:
    m6_settings_fingerprint = "m6-settings-v1"
    m6_algorithm_version = "m6-algorithm-v1"

    @property
    def backend_identity(self):
        return m6_orientation_components_identity(
            settings_fingerprint=self.m6_settings_fingerprint,
            algorithm_version=self.m6_algorithm_version,
            adapter_owner="full-domain-test-adapter",
        )

    def analyze_frame(
        self,
        frame: M6CanonicalFrame,
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
            full_domains=(
                M6ComponentMembership(
                    lattice_domain_id="backend-domain",
                    source_ids=("m-b", "m-a"),
                ),
            ),
            small_ordered_islands=(
                M6ComponentMembership(
                    lattice_domain_id="backend-island",
                    source_ids=("m-c",),
                ),
            ),
            coordinate_frame=frame.coordinate_frame,
            coordinate_transform_fingerprint=(
                frame.coordinate_transform_fingerprint
            ),
            backend_identity=self.backend_identity,
            native_evidence=M6OrientationComponentsEvidence(
                assignment_status=tuple(
                    (value.source_id, "assigned") for value in frame.molecules
                ),
                q6=tuple((value.source_id, None) for value in frame.molecules),
            ),
        )


class _RecordingABCClassifier:
    classifier_id = "abc_orientation"
    classifier_schema_version = "abc-classifier-schema-v1"
    classifier_settings_fingerprint = "abc-settings-v1"
    classifier_algorithm_version = "abc-algorithm-v1"
    domain_aggregation_preset = ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1

    def __init__(self) -> None:
        self.calls: list[
            tuple[
                np.ndarray,
                int,
                str,
                str,
                tuple[ClassifierMoleculeInput, ...],
            ]
        ] = []

    def classify_domain(
        self,
        raw_frame: np.ndarray,
        *,
        frame_index: int,
        physical_frame_id: str,
        lattice_domain_id: str,
        molecules: tuple[ClassifierMoleculeInput, ...],
    ) -> tuple[ClassifierMoleculePrediction, ...]:
        self.calls.append((
            raw_frame,
            frame_index,
            physical_frame_id,
            lattice_domain_id,
            molecules,
        ))
        labels: dict[str, Literal["A", "B", "C"]] = {
            "m-a": "A",
            "m-b": "B",
        }
        return tuple(
            ClassifierMoleculePrediction(
                source_id=molecule.source_id,
                orientation_label=labels[molecule.source_id],
                evidence_strength=0.8,
                component_id=f"component-{molecule.source_id}",
            )
            for molecule in reversed(molecules)
        )

class _NoFullDomainM6Adapter(_FullDomainM6Adapter):
    def analyze_frame(
        self,
        frame: M6CanonicalFrame,
        *,
        frame_index: int,
        geometry_mode: str,
    ) -> M6FrameComputation:
        result = super().analyze_frame(
            frame,
            frame_index=frame_index,
            geometry_mode=geometry_mode,
        )
        return replace(result, full_domains=())


class _TwoFullDomainsM6Adapter(_FullDomainM6Adapter):
    def analyze_frame(
        self,
        frame: M6CanonicalFrame,
        *,
        frame_index: int,
        geometry_mode: str,
    ) -> M6FrameComputation:
        result = super().analyze_frame(
            frame,
            frame_index=frame_index,
            geometry_mode=geometry_mode,
        )
        return replace(
            result,
            full_domains=(
                M6ComponentMembership(
                    lattice_domain_id="backend-left",
                    source_ids=("m-a",),
                ),
                M6ComponentMembership(
                    lattice_domain_id="backend-right",
                    source_ids=("m-b",),
                ),
            ),
        )

class _AllMoleculesFullDomainM6Adapter(_FullDomainM6Adapter):
    def analyze_frame(
        self,
        frame: M6CanonicalFrame,
        *,
        frame_index: int,
        geometry_mode: str,
    ) -> M6FrameComputation:
        result = super().analyze_frame(
            frame,
            frame_index=frame_index,
            geometry_mode=geometry_mode,
        )
        return replace(
            result,
            full_domains=(
                M6ComponentMembership(
                    lattice_domain_id="backend-domain",
                    source_ids=tuple(
                        molecule.source_id for molecule in frame.molecules
                    ),
                ),
            ),
            small_ordered_islands=(),
        )

class _ScenarioABCClassifier:
    classifier_id = "abc_orientation"
    classifier_schema_version = "abc-classifier-schema-v1"
    classifier_settings_fingerprint = "abc-settings-v1"
    classifier_algorithm_version = "abc-algorithm-v1"

    def __init__(
        self,
        labels: tuple[Literal["A", "B", "C"] | None, ...],
        *,
        split_components: bool = False,
        aggregation_preset: DomainAggregationPreset = (
            ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1
        ),
    ) -> None:
        self._labels = labels
        self._split_components = split_components
        self.domain_aggregation_preset = aggregation_preset

    def classify_domain(
        self,
        raw_frame: np.ndarray,
        *,
        frame_index: int,
        physical_frame_id: str,
        lattice_domain_id: str,
        molecules: tuple[ClassifierMoleculeInput, ...],
    ) -> tuple[ClassifierMoleculePrediction, ...]:
        del raw_frame, frame_index, physical_frame_id, lattice_domain_id
        return tuple(
            ClassifierMoleculePrediction(
                source_id=molecule.source_id,
                orientation_label=label,
                evidence_strength=0.8 if label is not None else 0.0,
                component_id=(
                    None
                    if label is None
                    else (
                        f"component-{molecule.source_id}"
                        if self._split_components
                        else f"component-{label}"
                    )
                ),
            )
            for molecule, label in reversed(tuple(zip(molecules, self._labels)))
        )

def _series(
    source_view: Literal["raw", "expanded_aligned"],
    *,
    raw_frame: np.ndarray | None,
) -> DomainAnalysisSeries:
    frame_origin = (2.0, 1.0)
    bboxes = {
        "m-a": (0.0, 0.0, 2.0, 1.0),
        "m-b": (0.0, 1.0, 2.0, 2.0),
        "m-c": (2.0, 0.0, 3.0, 1.0),
        "m-d": (3.0, 0.0, 4.0, 3.0),
    }
    if source_view == "expanded_aligned":
        bboxes = {
            source_id: (
                bbox[0] + frame_origin[0],
                bbox[1] + frame_origin[1],
                bbox[2] + frame_origin[0],
                bbox[3] + frame_origin[1],
            )
            for source_id, bbox in bboxes.items()
        }
    return DomainAnalysisSeries(frames=(
        DomainAnalysisFrame(
            frame_index=0,
            source_view=source_view,
            geometry=M6FrameGeometry(
                physical_frame_id="physical-frame-0",
                raw_shape=(4, 4),
                expanded_shape=(6, 7),
                frame_origin_xy=frame_origin,
                canvas_offset_xy=(11.0, 13.0),
                pixel_size_nm=(1.0, 1.0),
                scan_angle_deg=0.0,
                registration_fingerprint="registration-v1",
            ),
            annotations=tuple(
                M6SourceAnnotation(
                    source_id=source_id,
                    source_view=source_view,
                    bbox_xyxy=bbox,
                )
                for source_id, bbox in bboxes.items()
            ),
            raw_frame=raw_frame,
        ),
    ))

def _range_series(
    raw_frames: tuple[np.ndarray, ...],
) -> DomainAnalysisSeries:
    first = _series("raw", raw_frame=raw_frames[0]).frames[0]
    return DomainAnalysisSeries(frames=tuple(
        replace(
            first,
            frame_index=frame_index,
            geometry=replace(
                first.geometry,
                physical_frame_id=f"physical-frame-{frame_index}",
            ),
            raw_frame=raw_frame,
        )
        for frame_index, raw_frame in enumerate(raw_frames)
    ))

@pytest.mark.parametrize(
    (
        "labels",
        "split_components",
        "expected_label",
        "expected_counts",
        "expected_resolved_evidence_fraction",
    ),
    (
        (("A", "A", "A", None), False, "A", (3, 0, 0, 1), 0.6),
        (("B", "B", "B", None), False, "B", (0, 3, 0, 1), 0.6),
        (("C", "C", "C", None), False, "C", (0, 0, 3, 1), 0.6),
        (("A", "A", "B", "B"), False, "Mixed", (2, 2, 0, 0), 0.8),
        (
            ("A", None, None, None),
            False,
            "Unknown orientation",
            (1, 0, 0, 3),
            0.2,
        ),
        (
            ("A", "A", "A", None),
            True,
            "Unknown orientation",
            (3, 0, 0, 1),
            0.6,
        ),
    ),
)
def test_run_publishes_conservative_full_domain_label_summary(
    labels: tuple[Literal["A", "B", "C"] | None, ...],
    split_components: bool,
    expected_label: str,
    expected_counts: tuple[int, int, int, int],
    expected_resolved_evidence_fraction: float,
) -> None:
    classifier = _ScenarioABCClassifier(
        labels,
        split_components=split_components,
    )

    result = DomainAnalysisModule(
        _AllMoleculesFullDomainM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    ).run(
        _series("raw", raw_frame=np.arange(16).reshape(4, 4)),
        DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(classifier.classifier_id,),
        ),
    )

    assert result.classifier_outcomes is not None
    outcome = result.classifier_outcomes[0]
    assert len(outcome.domain_summaries) == 1
    summary = outcome.domain_summaries[0]
    assert summary.label == expected_label
    assert summary.molecule_count == 4
    assert summary.counts == tuple(zip(
        ("A", "B", "C", "Unknown orientation"),
        expected_counts,
    ))
    assert summary.resolved_evidence_fraction_of_domain == pytest.approx(
        expected_resolved_evidence_fraction
    )
    assert summary.aggregation_preset_id == "abc-domain-summary-conservative-v1"
    assert summary.aggregation_preset_fingerprint == (
        "982f1b73869dac84f411307beb75b2961509db010af7f45ba3f3592ebb30d7c7"
    )
    assert summary.frame_index == 0
    assert summary.physical_frame_id == "physical-frame-0"
    assert result.m6_gate is not None
    assert summary.lattice_domain_id == (
        result.m6_gate.frames[0].full_domains[0].lattice_domain_id
    )

def test_run_binds_classifier_and_aggregation_as_one_configuration() -> None:
    revised_preset = replace(
        ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
        preset_id="abc-domain-summary-conservative-v2",
        minimum_resolved_evidence=0.41,
    )

    outcomes = []
    for preset in (ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1, revised_preset):
        classifier = _ScenarioABCClassifier(
            ("A", "A", "A", None),
            aggregation_preset=preset,
        )
        result = DomainAnalysisModule(
            _AllMoleculesFullDomainM6Adapter(),
            classifier_adapters={classifier.classifier_id: classifier},
        ).run(
            _series("raw", raw_frame=np.arange(16).reshape(4, 4)),
            DomainAnalysisRequest(
                frame_range=range(1),
                classifier_ids=(classifier.classifier_id,),
            ),
        )
        assert result.classifier_outcomes is not None
        outcomes.append(result.classifier_outcomes[0])

    default, revised = outcomes
    assert default.classifier_settings_fingerprint == (
        revised.classifier_settings_fingerprint
    )
    assert default.aggregation_preset_fingerprint != (
        revised.aggregation_preset_fingerprint
    )
    assert default.classifier_configuration_fingerprint != (
        revised.classifier_configuration_fingerprint
    )
    assert revised.aggregation_preset_id == revised_preset.preset_id
    assert revised.domain_summaries[0].aggregation_preset_fingerprint == (
        revised_preset.fingerprint
    )

def test_run_publishes_a_deep_auditable_classifier_contract() -> None:
    classifier = _ScenarioABCClassifier(("A", "A", "A", None))
    result = DomainAnalysisModule(
        _AllMoleculesFullDomainM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    ).run(
        _series("raw", raw_frame=np.arange(16).reshape(4, 4)),
        DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(classifier.classifier_id,),
        ),
    )

    assert result.classifier_outcomes is not None
    outcome = result.classifier_outcomes[0]
    summary = outcome.domain_summaries[0]
    assert outcome.configuration.identity.classifier_id == "abc_orientation"
    assert outcome.configuration.identity.schema_version == (
        "abc-classifier-schema-v1"
    )
    assert outcome.configuration.aggregation_preset.preset_id == (
        "abc-domain-summary-conservative-v1"
    )
    assert summary.configuration == outcome.configuration
    assert dict(summary.evidence_fraction_of_domain) == pytest.approx({
        "A": 0.6,
        "B": 0.0,
        "C": 0.0,
    })
    assert dict(summary.coherent_evidence_fraction_of_domain) == pytest.approx({
        "A": 0.6,
        "B": 0.0,
        "C": 0.0,
    })
    assert summary.resolved_evidence_fraction_of_domain == pytest.approx(0.6)
    assert summary.reason == "dominant_class_passed"
    assert outcome.classifier_result_fingerprint is not None
    assert len(outcome.classifier_result_fingerprint) == 64
    assert len(outcome.frame_result_provenance) == 1

def test_run_gates_classifier_to_full_domains_and_exact_raw_pixels() -> None:
    raw_pixels = np.arange(16, dtype=np.uint16).reshape(4, 4)
    classifier = _RecordingABCClassifier()
    module = DomainAnalysisModule(
        _FullDomainM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    )
    request = DomainAnalysisRequest(
        frame_range=range(1),
        classifier_ids=(classifier.classifier_id,),
    )

    result = module.run(_series("expanded_aligned", raw_frame=raw_pixels), request)

    assert result.run_status == "completed"
    assert result.classifier_status == "completed"
    assert result.m6_gate is not None
    assert len(classifier.calls) == 1
    classifier_frame, frame_index, physical_id, domain_id, inputs = (
        classifier.calls[0]
    )
    assert classifier_frame is raw_pixels
    assert np.array_equal(classifier_frame, raw_pixels)
    assert classifier_frame.dtype == raw_pixels.dtype
    assert classifier_frame.flags.writeable is False
    assert frame_index == 0
    assert physical_id == "physical-frame-0"
    assert domain_id == result.m6_gate.frames[0].full_domains[0].lattice_domain_id
    assert tuple(value.source_id for value in inputs) == ("m-a", "m-b")

    assert result.classifier_outcomes is not None
    outcome = result.classifier_outcomes[0]
    assert outcome.status == "completed"
    assert outcome.classifier_id == classifier.classifier_id
    assert len(outcome.domain_summaries) == 1
    assert outcome.domain_summaries[0].molecule_count == 2
    assert outcome.domain_summaries[0].label == "Mixed"
    assert [
        (value.source_id, value.classification_status, value.orientation_label)
        for value in outcome.molecule_classifications
    ] == [
        ("m-a", "classified", "A"),
        ("m-b", "classified", "B"),
        ("m-c", "not_gated", None),
        ("m-d", "not_gated", None),
    ]
    for value in outcome.molecule_classifications:
        assert value.frame_index == 0
        assert value.physical_frame_id == "physical-frame-0"
        assert value.m6_gate_fingerprint == result.m6_gate.frames[0].m6_gate_fingerprint
        assert value.classifier_id == classifier.classifier_id
        assert value.classifier_settings_fingerprint == "abc-settings-v1"
        assert value.classifier_algorithm_version == "abc-algorithm-v1"
    assert outcome.molecule_classifications[0].lattice_domain_id == domain_id
    assert outcome.molecule_classifications[1].lattice_domain_id == domain_id
    assert outcome.molecule_classifications[2].lattice_domain_id == (
        result.m6_gate.frames[0].small_ordered_islands[0].lattice_domain_id
    )
    assert outcome.molecule_classifications[3].lattice_domain_id is None

    raw_classifier = _RecordingABCClassifier()
    raw_result = DomainAnalysisModule(
        _FullDomainM6Adapter(),
        classifier_adapters={raw_classifier.classifier_id: raw_classifier},
    ).run(_series("raw", raw_frame=raw_pixels), request)
    assert raw_result.classifier_outcomes is not None
    assert raw_result.classifier_outcomes[0].molecule_classifications == (
        outcome.molecule_classifications
    )
    assert raw_result.classifier_outcomes[0].domain_summaries == (
        outcome.domain_summaries
    )
    assert np.array_equal(raw_classifier.calls[0][0], classifier_frame)

    reordered = replace(
        outcome,
        molecule_classifications=tuple(
            reversed(outcome.molecule_classifications)
        ),
    )
    assert reordered.molecule_classifications == outcome.molecule_classifications

def test_run_uses_real_texture_adapter_without_forcing_an_abc_label() -> None:
    adapter = TextureABCClassifierAdapter()
    result = DomainAnalysisModule(
        _FullDomainM6Adapter(),
        classifier_adapters={adapter.classifier_id: adapter},
    ).run(
        _series(
            "raw",
            raw_frame=np.arange(16, dtype=np.float32).reshape(4, 4),
        ),
        DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(adapter.classifier_id,),
        ),
    )

    assert result.run_status == "completed"
    assert result.classifier_outcomes is not None
    outcome = result.classifier_outcomes[0]
    assert outcome.classifier_settings_fingerprint == (
        TTMAPP_TEXTURE_DOMAIN_PRESET.fingerprint
    )
    assert [
        (value.source_id, value.classification_status, value.orientation_label)
        for value in outcome.molecule_classifications
    ] == [
        ("m-a", "unknown_orientation", "Unknown orientation"),
        ("m-b", "unknown_orientation", "Unknown orientation"),
        ("m-c", "not_gated", None),
        ("m-d", "not_gated", None),
    ]

def test_each_physical_frame_uses_its_own_raw_pixels() -> None:
    first_pixels = np.full((4, 4), 11, dtype=np.uint16)
    second_pixels = np.full((4, 4), 22, dtype=np.uint16)
    first = _series("raw", raw_frame=first_pixels).frames[0]
    second = replace(
        first,
        frame_index=1,
        geometry=replace(first.geometry, physical_frame_id="physical-frame-1"),
        raw_frame=second_pixels,
    )
    classifier = _RecordingABCClassifier()

    DomainAnalysisModule(
        _FullDomainM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    ).run(
        DomainAnalysisSeries(frames=(second, first)),
        DomainAnalysisRequest(
            frame_range=range(2),
            classifier_ids=(classifier.classifier_id,),
        ),
    )

    assert classifier.calls[0][0] is first_pixels
    assert classifier.calls[1][0] is second_pixels
    assert [(call[1], call[2]) for call in classifier.calls] == [
        (0, "physical-frame-0"),
        (1, "physical-frame-1"),
    ]

def test_adjacent_full_domains_are_classified_in_isolated_calls() -> None:
    classifier = _RecordingABCClassifier()
    result = DomainAnalysisModule(
        _TwoFullDomainsM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    ).run(
        _series("raw", raw_frame=np.arange(16).reshape(4, 4)),
        DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(classifier.classifier_id,),
        ),
    )

    calls_by_source_ids = {
        tuple(value.source_id for value in call[4]): call
        for call in classifier.calls
    }
    assert set(calls_by_source_ids) == {("m-a",), ("m-b",)}
    assert calls_by_source_ids[("m-a",)][3] != (
        calls_by_source_ids[("m-b",)][3]
    )
    assert result.classifier_outcomes is not None
    assert sorted(
        summary.label for summary in result.classifier_outcomes[0].domain_summaries
    ) == ["A", "B"]
    classified = {
        value.source_id: (value.orientation_label, value.lattice_domain_id)
        for value in result.classifier_outcomes[0].molecule_classifications
        if value.classification_status == "classified"
    }
    assert classified["m-a"][0] == "A"
    assert classified["m-b"][0] == "B"
    assert classified["m-a"][1] == calls_by_source_ids[("m-a",)][3]
    assert classified["m-b"][1] == calls_by_source_ids[("m-b",)][3]

def test_missing_raw_frame_fails_classifier_without_corrupting_m6() -> None:
    classifier = _RecordingABCClassifier()
    first = _series(
        "expanded_aligned",
        raw_frame=np.arange(16, dtype=np.uint16).reshape(4, 4),
    ).frames[0]
    second = replace(
        first,
        frame_index=1,
        geometry=replace(
            first.geometry,
            physical_frame_id="physical-frame-1",
        ),
        raw_frame=None,
    )
    result = DomainAnalysisModule(
        _FullDomainM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    ).run(
        DomainAnalysisSeries(frames=(first, second)),
        DomainAnalysisRequest(
            frame_range=range(2),
            classifier_ids=(classifier.classifier_id,),
        ),
    )

    assert result.run_status == "completed_with_errors"
    assert result.classifier_status == "completed_with_errors"
    assert result.m6_gate is not None
    assert result.m6_gate.frames[0].full_domains[0].source_ids == ("m-a", "m-b")
    assert classifier.calls == []
    assert result.classifier_outcomes is not None
    outcome = result.classifier_outcomes[0]
    assert outcome.status == "failed"
    assert outcome.molecule_classifications == ()
    assert outcome.domain_summaries == ()
    assert outcome.error_message is not None
    assert "exact raw frame" in outcome.error_message
    assert "physical-frame-1" in outcome.error_message

def test_missing_raw_is_allowed_when_a_frame_has_no_full_domains() -> None:
    classifier = _RecordingABCClassifier()
    result = DomainAnalysisModule(
        _NoFullDomainM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    ).run(
        _series("raw", raw_frame=None),
        DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(classifier.classifier_id,),
        ),
    )

    assert result.run_status == "completed"
    assert classifier.calls == []
    assert result.classifier_outcomes is not None
    assert result.classifier_outcomes[0].domain_summaries == ()
    assert {
        value.classification_status
        for value in result.classifier_outcomes[0].molecule_classifications
    } == {"not_gated"}

def test_result_rejects_mismatched_run_and_classifier_statuses() -> None:
    classifier = _RecordingABCClassifier()
    module = DomainAnalysisModule(
        _FullDomainM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    )
    request = DomainAnalysisRequest(
        frame_range=range(1),
        classifier_ids=(classifier.classifier_id,),
    )
    completed = module.run(
        _series("raw", raw_frame=np.zeros((4, 4))),
        request,
    )
    failed = module.run(_series("raw", raw_frame=None), request)

    with pytest.raises(ValueError, match="run and classifier statuses"):
        replace(completed, run_status="completed_with_errors")
    with pytest.raises(ValueError, match="run and classifier statuses"):
        replace(failed, run_status="completed")

def test_run_reclassifies_only_stale_and_missing_frames() -> None:
    classifier = _RecordingABCClassifier()
    module = DomainAnalysisModule(
        _FullDomainM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    )
    original = _range_series((
        np.full((4, 4), 11, dtype=np.uint16),
        np.full((4, 4), 22, dtype=np.uint16),
        np.full((4, 4), 33, dtype=np.uint16),
    ))
    physical_ids = ("physical-c", "physical-b", "physical-a")
    original = DomainAnalysisSeries(frames=tuple(
        replace(
            frame,
            geometry=replace(
                frame.geometry,
                physical_frame_id=physical_ids[frame.frame_index],
            ),
        )
        for frame in original.frames
    ))
    request = DomainAnalysisRequest(
        frame_range=range(2),
        classifier_ids=(classifier.classifier_id,),
    )
    module.run(original, request)
    classifier.calls.clear()
    changed_second = replace(
        original.frames[1],
        raw_frame=np.full((4, 4), 44, dtype=np.uint16),
    )
    mixed = DomainAnalysisSeries(frames=(
        original.frames[0],
        changed_second,
        original.frames[2],
    ))

    result = module.run(
        mixed,
        replace(request, frame_range=range(3)),
    )

    assert [call[1] for call in classifier.calls] == [2, 1]
    assert result.run_status == "completed"
    assert result.classifier_outcomes is not None
    assert {
        value.frame_index
        for value in result.classifier_outcomes[0].molecule_classifications
    } == {0, 1, 2}

def test_run_repeats_identical_range_without_reclassification() -> None:
    classifier = _RecordingABCClassifier()
    module = DomainAnalysisModule(
        _FullDomainM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    )
    series = _range_series((
        np.full((4, 4), 11, dtype=np.uint16),
        np.full((4, 4), 22, dtype=np.uint16),
    ))
    request = DomainAnalysisRequest(
        frame_range=range(2),
        classifier_ids=(classifier.classifier_id,),
    )
    first = module.run(series, request)
    classifier.calls.clear()

    repeated = module.run(series, request)

    assert repeated == first
    assert classifier.calls == []

    copied = DomainAnalysisSeries(frames=tuple(
        replace(frame, raw_frame=np.array(frame.raw_frame, copy=True))
        for frame in series.frames
    ))
    copied_result = module.run(copied, request)
    assert copied_result == first
    assert classifier.calls == []

    changed_dtype = replace(
        copied.frames[0],
        raw_frame=np.asarray(copied.frames[0].raw_frame, dtype=np.int16),
    )
    module.run(
        DomainAnalysisSeries(frames=(changed_dtype, copied.frames[1])),
        request,
    )
    assert [call[1] for call in classifier.calls] == [0]

def test_run_does_not_hash_raw_pixels_without_full_m6_domains() -> None:
    classifier = _RecordingABCClassifier()
    raw_frame = np.full((4, 4), object(), dtype=object)

    result = DomainAnalysisModule(
        _NoFullDomainM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    ).run(
        _series("raw", raw_frame=raw_frame),
        DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(classifier.classifier_id,),
        ),
    )

    assert result.run_status == "completed"
    assert classifier.calls == []

def test_run_cancels_classifier_without_publishing_a_partial_payload() -> None:
    classifier = _RecordingABCClassifier()
    module = DomainAnalysisModule(
        _FullDomainM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    )
    series = _range_series((
        np.full((4, 4), 11, dtype=np.uint16),
        np.full((4, 4), 22, dtype=np.uint16),
    ))
    request = DomainAnalysisRequest(
        frame_range=range(2),
        classifier_ids=(classifier.classifier_id,),
    )

    canceled = module.run(
        series,
        request,
        is_cancelled=lambda: len(classifier.calls) == 1,
    )

    assert canceled.run_status == "canceled"
    assert canceled.m6_gate is not None
    assert canceled.classifier_status == "canceled"
    assert canceled.classifier_outcomes is not None
    assert canceled.classifier_outcomes[0].status == "canceled"
    assert canceled.classifier_outcomes[0].molecule_classifications == ()
    assert canceled.classifier_outcomes[0].domain_summaries == ()
    assert [call[1] for call in classifier.calls] == [0]

    classifier.calls.clear()
    retried = module.run(series, request)

    assert retried.run_status == "completed"
    assert [call[1] for call in classifier.calls] == [1]

def test_run_keys_classifier_cache_by_every_versioned_dependency() -> None:
    classifier = _RecordingABCClassifier()
    m6_adapter = _FullDomainM6Adapter()
    module = DomainAnalysisModule(
        m6_adapter,
        classifier_adapters={classifier.classifier_id: classifier},
    )
    series = _range_series((np.full((4, 4), 11, dtype=np.uint16),))
    request = DomainAnalysisRequest(
        frame_range=range(1),
        classifier_ids=(classifier.classifier_id,),
    )
    module.run(series, request)

    classifier.calls.clear()
    classifier.classifier_schema_version = "abc-classifier-schema-v2"
    module.run(series, request)
    assert [call[1] for call in classifier.calls] == [0]

    classifier.calls.clear()
    classifier.classifier_settings_fingerprint = "abc-settings-v2"
    changed_classifier = module.run(series, request)
    assert [call[1] for call in classifier.calls] == [0]

    classifier.calls.clear()
    classifier.domain_aggregation_preset = replace(
        ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
        preset_id="abc-domain-summary-conservative-v2",
    )
    changed_aggregation = module.run(series, request)
    assert [call[1] for call in classifier.calls] == [0]

    classifier.calls.clear()
    m6_adapter.m6_algorithm_version = "m6-algorithm-v2"
    changed_m6 = module.run(series, request)
    assert [call[1] for call in classifier.calls] == [0]
    assert changed_classifier != changed_aggregation
    assert changed_aggregation != changed_m6

def test_run_evicts_least_recently_used_complete_classifier_frame() -> None:
    classifier = _RecordingABCClassifier()
    module = DomainAnalysisModule(
        _FullDomainM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
        classifier_cache_max_entries=2,
    )
    series = _range_series((
        np.full((4, 4), 11, dtype=np.uint16),
        np.full((4, 4), 22, dtype=np.uint16),
        np.full((4, 4), 33, dtype=np.uint16),
    ))

    def run_frame(frame_index: int) -> None:
        module.run(
            series,
            DomainAnalysisRequest(
                frame_range=range(frame_index, frame_index + 1),
                classifier_ids=(classifier.classifier_id,),
            ),
        )

    run_frame(0)
    run_frame(1)
    run_frame(0)
    run_frame(2)
    classifier.calls.clear()

    run_frame(0)
    run_frame(1)

    assert [call[1] for call in classifier.calls] == [1]

def test_run_never_reuses_an_incomplete_classifier_frame() -> None:
    class FailingClassifier(_RecordingABCClassifier):
        should_fail = True

        def classify_domain(
            self,
            raw_frame: np.ndarray,
            *,
            frame_index: int,
            physical_frame_id: str,
            lattice_domain_id: str,
            molecules: tuple[ClassifierMoleculeInput, ...],
        ) -> tuple[ClassifierMoleculePrediction, ...]:
            predictions = super().classify_domain(
                raw_frame,
                frame_index=frame_index,
                physical_frame_id=physical_frame_id,
                lattice_domain_id=lattice_domain_id,
                molecules=molecules,
            )
            if self.should_fail:
                raise ClassifierAnalysisError("synthetic classifier failure")
            return predictions

    classifier = FailingClassifier()
    module = DomainAnalysisModule(
        _TwoFullDomainsM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    )
    series = _range_series((np.full((4, 4), 11, dtype=np.uint16),))
    request = DomainAnalysisRequest(
        frame_range=range(1),
        classifier_ids=(classifier.classifier_id,),
    )

    failed = module.run(series, request)

    assert failed.run_status == "completed_with_errors"
    assert failed.classifier_outcomes is not None
    assert failed.classifier_outcomes[0].molecule_classifications == ()
    classifier.should_fail = False
    classifier.calls.clear()

    recovered = module.run(series, request)

    assert recovered.run_status == "completed"
    assert len(classifier.calls) == 2
