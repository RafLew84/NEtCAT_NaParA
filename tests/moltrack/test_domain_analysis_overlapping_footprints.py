from __future__ import annotations

from dataclasses import replace
from functools import partial

import numpy as np

from moltrack.analysis.domain_analysis import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ClassifierMoleculeInput,
    ClassifierMoleculePrediction,
    ApplyPreparedDomainCorrection,
    DomainCorrectionModule,
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
    ManualDomainIntent,
    m6_orientation_components_identity,
)
from domain_analysis_test_support import domain_analysis_module as DomainAnalysisModule

DomainAnalysisRequest = partial(
    DomainAnalysisRequest, backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID
)


class _OverlappingM6Adapter:
    m6_settings_fingerprint = "m6-settings-v1"
    m6_algorithm_version = "m6-algorithm-v1"

    @property
    def backend_identity(self):
        return m6_orientation_components_identity(
            settings_fingerprint=self.m6_settings_fingerprint,
            algorithm_version=self.m6_algorithm_version,
            adapter_owner="overlapping-footprints-test-adapter",
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
                    lattice_domain_id="full-domain",
                    source_ids=("m-a", "m-b"),
                ),
            ),
            small_ordered_islands=(
                M6ComponentMembership(
                    lattice_domain_id="island",
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


class _RawPointClassifier:
    classifier_id = "abc"
    classifier_schema_version = "test-classifier-schema-v1"
    classifier_settings_fingerprint = "test-classifier-settings-v1"
    classifier_algorithm_version = "test-classifier-algorithm-v1"
    domain_aggregation_preset = ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1

    def __init__(self) -> None:
        self.received_inputs: list[
            tuple[int, tuple[tuple[str, tuple[float, float]], ...]]
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
        del raw_frame, physical_frame_id, lattice_domain_id
        self.received_inputs.append((
            frame_index,
            tuple(
                (molecule.source_id, molecule.raw_centroid_xy)
                for molecule in molecules
            ),
        ))
        return tuple(
            ClassifierMoleculePrediction(
                source_id=molecule.source_id,
                orientation_label="A",
                evidence_strength=0.8,
                component_id="component-A",
            )
            for molecule in molecules
        )


def _overlapping_series(source_view: str = "raw") -> DomainAnalysisSeries:
    frame_origin = (2.0, 1.0)
    bboxes = {
        "m-a": (0.0, 0.0, 2.0, 1.0),
        "m-b": (0.0, 1.0, 2.0, 2.0),
        "m-c": (0.0, 0.0, 3.0, 1.0),
        "m-d": (3.0, 0.0, 4.0, 3.0),
    }
    mask_pixels = {
        "m-a": ((0, 0), (0, 1)),
        "m-b": ((1, 0), (1, 1)),
    }
    if source_view == "expanded_aligned":
        origin_x, origin_y = frame_origin
        bboxes = {
            source_id: (
                bbox[0] + origin_x,
                bbox[1] + origin_y,
                bbox[2] + origin_x,
                bbox[3] + origin_y,
            )
            for source_id, bbox in bboxes.items()
        }
        mask_pixels = {
            source_id: tuple(
                (x + int(origin_x), y + int(origin_y))
                for x, y in pixels
            )
            for source_id, pixels in mask_pixels.items()
        }
    annotations = tuple(
        M6SourceAnnotation(
            source_id=source_id,
            source_view=source_view,
            bbox_xyxy=bbox,
            mask_shape=(4, 4) if source_view == "raw" else (6, 7),
            mask_pixels_xy=mask_pixels.get(source_id, ()),
        )
        for source_id, bbox in bboxes.items()
    )
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
            annotations=annotations,
            raw_frame=np.zeros((4, 4), dtype=np.uint16),
        ),
    ))


def test_run_spatially_partitions_overlapping_molecule_patches() -> None:
    result = DomainAnalysisModule(
        _OverlappingM6Adapter(),
        classifier_adapters={},
    ).run(
        _overlapping_series(),
        DomainAnalysisRequest(frame_range=range(1)),
    )

    assert result.m6_gate is not None
    frame = result.m6_gate.frames[0]
    assert frame.full_domains[0].source_ids == ("m-a", "m-b")
    assert frame.small_ordered_islands[0].source_ids == ("m-c",)
    assert frame.outside_source_ids == ("m-d",)
    assert frame.full_domains[0].footprint_pixels_xy == (
        (0, 0),
        (0, 1),
        (1, 1),
    )
    assert frame.small_ordered_islands[0].footprint_pixels_xy == (
        (1, 0),
        (2, 0),
    )
    assert frame.outside_pixels_xy == ((3, 0), (3, 1), (3, 2))
    footprints = {
        molecule.source_id: molecule.footprint_pixels_xy
        for component in frame.full_domains + frame.small_ordered_islands
        for molecule in component.members
    } | {
        molecule.source_id: molecule.footprint_pixels_xy
        for molecule in frame.outside_members
    }
    assert footprints == {
        "m-a": ((0, 0), (0, 1)),
        "m-b": ((1, 1),),
        "m-c": ((1, 0), (2, 0)),
        "m-d": ((3, 0), (3, 1), (3, 2)),
    }


def test_overlapping_partition_is_equivalent_for_registered_input() -> None:
    request = DomainAnalysisRequest(
        frame_range=range(1),
        classifier_ids=("abc",),
    )
    raw_classifier = _RawPointClassifier()
    registered_classifier = _RawPointClassifier()
    raw = DomainAnalysisModule(
        _OverlappingM6Adapter(),
        classifier_adapters={raw_classifier.classifier_id: raw_classifier},
    ).run(_overlapping_series("raw"), request)
    registered = DomainAnalysisModule(
        _OverlappingM6Adapter(),
        classifier_adapters={
            registered_classifier.classifier_id: registered_classifier,
        },
    ).run(_overlapping_series("expanded_aligned"), request)

    assert raw.m6_gate is not None
    assert registered.m6_gate is not None
    raw_frame = raw.m6_gate.frames[0]
    registered_frame = registered.m6_gate.frames[0]
    assert replace(
        raw_frame,
        presentation_provenance=registered_frame.presentation_provenance,
    ) == registered_frame
    assert raw_frame.m6_gate_fingerprint == registered_frame.m6_gate_fingerprint
    assert raw.classifier_outcomes == registered.classifier_outcomes
    assert raw_classifier.received_inputs == registered_classifier.received_inputs


def test_classifier_keeps_raw_points_when_footprints_are_partitioned() -> None:
    classifier = _RawPointClassifier()
    result = DomainAnalysisModule(
        _OverlappingM6Adapter(),
        classifier_adapters={classifier.classifier_id: classifier},
    ).run(
        _overlapping_series(),
        DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(classifier.classifier_id,),
        ),
    )

    assert result.run_status == "completed"
    assert classifier.received_inputs == [
        (0, (("m-a", (0.5, 1.0)), ("m-b", (1.5, 1.0)))),
    ]
    assert result.m6_gate is not None
    assert result.m6_gate.frames[0].full_domains[0].footprint_pixels_xy == (
        (0, 0),
        (0, 1),
        (1, 1),
    )


def test_manual_domain_uses_exact_published_molecule_footprints() -> None:
    result = DomainAnalysisModule(
        _OverlappingM6Adapter(),
        classifier_adapters={},
    ).run(
        _overlapping_series(),
        DomainAnalysisRequest(frame_range=range(1)),
    )
    module = DomainCorrectionModule(
        manual_domain_id_factory=lambda: "00000000-0000-4000-8000-000000000001"
    )
    workspace = module.initialize(result)
    preview = module.prepare(
        workspace,
        result,
        ManualDomainIntent.create(
            physical_frame_id="physical-frame-0",
            source_ids=("m-b", "m-c"),
        ),
    )
    workspace = module.dispatch(
        workspace,
        result,
        ApplyPreparedDomainCorrection.confirmed(preview),
    )

    domain = module.project(result, workspace).domain(
        "physical-frame-0",
        "00000000-0000-4000-8000-000000000001",
    )
    assert domain.footprint_pixels_xy == ((1, 0), (1, 1), (2, 0))
    assert domain.footprint_area_nm2 == 3.0
