from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from math import isclose

import numpy as np
import pytest

from moltrack.analysis.domain_analysis import (
    ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1,
    ClassifierAnalysisError,
    ClassifierMoleculeInput,
    ClassifierMoleculePrediction,
    DomainAnalysisFrame,
    DomainAnalysisFailure,
    DomainAnalysisModule,
    DomainAnalysisRequest,
    DomainAnalysisResult,
    DomainAnalysisSeries,
    M6CanonicalFrame,
    M6ComponentMembership,
    M6FrameComputation,
    M6FrameAnalysisError,
    M6FrameGeometry,
    M6SourceAnnotation,
)


class _DeterministicM6Adapter:
    def __init__(
        self,
        *,
        reorder_adapter_output: bool,
        overlap_categories: bool = False,
        overlap_full_domains: bool = False,
        leave_pixel_uncovered: bool = False,
        fail_frame_index: int | None = None,
        backend_component_ids: tuple[str, str] = (
            "lattice-0001",
            "lattice-0002",
        ),
        m6_settings_fingerprint: str = "m6-settings-v1",
        m6_algorithm_version: str = "m6-algorithm-v1",
    ) -> None:
        self._reorder_adapter_output = reorder_adapter_output
        self._overlap_categories = overlap_categories
        self._overlap_full_domains = overlap_full_domains
        self._leave_pixel_uncovered = leave_pixel_uncovered
        self.fail_frame_index = fail_frame_index
        self._backend_component_ids = backend_component_ids
        self.m6_settings_fingerprint = m6_settings_fingerprint
        self.m6_algorithm_version = m6_algorithm_version
        self.analyzed_frame_indices: list[int] = []

    def analyze_frame(
        self,
        series: M6CanonicalFrame,
        *,
        frame_index: int,
        geometry_mode: str,
    ) -> M6FrameComputation:
        del geometry_mode
        self.analyzed_frame_indices.append(frame_index)
        if frame_index == self.fail_frame_index:
            raise M6FrameAnalysisError("synthetic M6 backend failure")
        molecules = series.molecules
        full_domain_id, island_id = self._backend_component_ids
        full_domains = (
            M6ComponentMembership(
                lattice_domain_id=full_domain_id,
                source_ids=("m-b", "m-a"),
                core_source_ids=("m-a",),
                halo_source_ids=("m-b",),
            ),
        )
        islands = (
            M6ComponentMembership(
                lattice_domain_id=island_id,
                source_ids=("m-c",),
                core_source_ids=("m-c",),
            ),
        )
        if self._overlap_full_domains:
            full_domains += islands
            islands = ()
        analyzed_pixels = series.analyzed_pixels_xy
        if self._leave_pixel_uncovered:
            analyzed_pixels += ((9, 9),)
        if self._reorder_adapter_output:
            molecules = tuple(reversed(molecules))
            full_domains = tuple(reversed(full_domains))
            islands = tuple(reversed(islands))
            analyzed_pixels = tuple(reversed(analyzed_pixels))
        return M6FrameComputation(
            frame_index=frame_index,
            molecules=molecules,
            analyzed_pixels_xy=analyzed_pixels,
            pixel_area_nm2=series.pixel_area_nm2,
            full_domains=full_domains,
            small_ordered_islands=islands,
            coordinate_frame=series.coordinate_frame,
            coordinate_transform_fingerprint=series.coordinate_transform_fingerprint,
            m6_settings_fingerprint=self.m6_settings_fingerprint,
        )


class _ControlledClassifier:
    classifier_schema_version = "test-classifier-schema-v1"
    classifier_settings_fingerprint = "test-classifier-settings-v1"
    classifier_algorithm_version = "test-classifier-algorithm-v1"
    domain_aggregation_preset = ABC_DOMAIN_SUMMARY_CONSERVATIVE_V1

    def __init__(
        self,
        classifier_id: str,
        execution_order: list[tuple[str, int]],
        activity: dict[str, int],
        *,
        fail_frame_index: int | None = None,
        cancel_after_frame_index: int | None = None,
        cancel_signal: dict[str, bool] | None = None,
    ) -> None:
        self.classifier_id = classifier_id
        self.execution_order = execution_order
        self.activity = activity
        self.fail_frame_index = fail_frame_index
        self.cancel_after_frame_index = cancel_after_frame_index
        self.cancel_signal = cancel_signal

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
        self.activity["active"] += 1
        self.activity["max_active"] = max(
            self.activity["max_active"],
            self.activity["active"],
        )
        self.execution_order.append((self.classifier_id, frame_index))
        try:
            if frame_index == self.fail_frame_index:
                raise ClassifierAnalysisError("controlled classifier failure")
            predictions = tuple(
                ClassifierMoleculePrediction(
                    source_id=molecule.source_id,
                    orientation_label="A",
                    evidence_strength=0.8,
                    component_id="component-A",
                )
                for molecule in molecules
            )
            if frame_index == self.cancel_after_frame_index:
                if self.cancel_signal is None:
                    raise AssertionError("cancel_signal is required")
                self.cancel_signal["requested"] = True
                self.cancel_after_frame_index = None
            return predictions
        finally:
            self.activity["active"] -= 1


def _geometry_series(
    source_view: str = "raw",
    frame_indices: range = range(10),
    *,
    alternate_geometry: bool = False,
    overlap_pixel_geometry: bool = False,
    frame_origin: tuple[float, float] = (2.0, 1.0),
    canvas_offset: tuple[float, float] = (11.0, 13.0),
    registration_fingerprint: str = "registration-v1",
) -> DomainAnalysisSeries:
    mask_pixels = {
        "m-a": ((0, 0), (0, 1)),
        "m-b": ((1, 0), (1, 1)),
    }
    if alternate_geometry:
        mask_pixels = {
            "m-a": ((0, 0), (1, 0)),
            "m-b": ((0, 1), (1, 1)),
        }
    bboxes = {
        "m-a": (0.0, 0.0, 2.0, 1.0),
        "m-b": (0.0, 1.0, 2.0, 2.0),
        "m-c": (
            (0.0, 0.0, 3.0, 1.0)
            if overlap_pixel_geometry
            else (2.0, 0.0, 3.0, 1.0)
        ),
        "m-d": (3.0, 0.0, 4.0, 3.0),
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
    mask_shape = (4, 4) if source_view == "raw" else (6, 7)
    annotations = tuple(
        M6SourceAnnotation(
            source_id=source_id,
            source_view=source_view,
            bbox_xyxy=bbox,
            mask_shape=mask_shape if source_id in mask_pixels else None,
            mask_pixels_xy=mask_pixels.get(source_id, ()),
        )
        for source_id, bbox in bboxes.items()
    )
    return DomainAnalysisSeries(
        frames=tuple(
            DomainAnalysisFrame(
                frame_index=frame_index,
                source_view=source_view,
                geometry=M6FrameGeometry(
                    physical_frame_id=f"physical-frame-{frame_index}",
                    raw_shape=(4, 4),
                    expanded_shape=(6, 7),
                    frame_origin_xy=frame_origin,
                    canvas_offset_xy=canvas_offset,
                    pixel_size_nm=(1.0, 1.0),
                    scan_angle_deg=0.0,
                    registration_fingerprint=registration_fingerprint,
                ),
                annotations=annotations,
            )
            for frame_index in frame_indices
        ),
    )


def _classifier_series(frame_indices: range) -> DomainAnalysisSeries:
    series = _geometry_series(frame_indices=frame_indices)
    return DomainAnalysisSeries(frames=tuple(
        replace(
            frame,
            raw_frame=np.full((4, 4), frame.frame_index, dtype=np.uint16),
        )
        for frame in series.frames
    ))


def test_run_canonicalizes_equivalent_raw_and_registered_geometry() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    adapter = _DeterministicM6Adapter(reorder_adapter_output=False)
    module = DomainAnalysisModule(adapter, classifier_adapters={})

    raw = module.run(_geometry_series("raw"), request)
    registered = module.run(_geometry_series("expanded_aligned"), request)

    assert raw.m6_gate is not None
    assert registered.m6_gate is not None
    frame = raw.m6_gate.frames[0]
    registered_frame = registered.m6_gate.frames[0]
    assert replace(
        frame,
        presentation_provenance=registered_frame.presentation_provenance,
    ) == registered_frame
    assert frame.coordinate_frame == "series_physical_nm"
    assert frame.full_domains[0].source_ids == ("m-a", "m-b")
    assert frame.full_domains[0].points_xy_nm == ((0.5, 3.0), (1.5, 3.0))
    assert frame.full_domains[0].footprint_area_nm2 == 4.0
    assert frame.full_domains[0].centroid_xy_nm == (1.0, 3.0)
    assert frame.presentation_provenance.raw_shape == (4, 4)
    assert frame.presentation_provenance.expanded_shape == (6, 7)
    assert frame.presentation_provenance.frame_origin_xy == (2.0, 1.0)
    assert frame.presentation_provenance.canvas_offset_xy == (11.0, 13.0)
    assert frame.presentation_provenance.source_view == "raw"
    assert registered_frame.presentation_provenance.source_view == (
        "expanded_aligned"
    )
    assert frame.m6_gate_fingerprint == registered_frame.m6_gate_fingerprint
    assert adapter.analyzed_frame_indices == [0]


def test_run_recomputes_only_stale_and_missing_m6_frames() -> None:
    adapter = _DeterministicM6Adapter(reorder_adapter_output=False)
    module = DomainAnalysisModule(adapter, classifier_adapters={})
    original = _geometry_series(frame_indices=range(3))
    changed = _geometry_series(frame_indices=range(3), alternate_geometry=True)

    module.run(original, DomainAnalysisRequest(frame_range=range(2)))
    adapter.analyzed_frame_indices.clear()
    mixed = DomainAnalysisSeries(frames=(
        original.frames[0],
        changed.frames[1],
        original.frames[2],
    ))

    result = module.run(mixed, DomainAnalysisRequest(frame_range=range(3)))

    assert adapter.analyzed_frame_indices == [1, 2]
    assert result.m6_gate is not None
    assert tuple(frame.frame_index for frame in result.m6_gate.frames) == (0, 1, 2)


def test_run_fingerprints_m6_gate_with_versioned_configuration() -> None:
    adapter = _DeterministicM6Adapter(reorder_adapter_output=False)
    module = DomainAnalysisModule(adapter, classifier_adapters={})
    series = _geometry_series(frame_indices=range(2))
    request = DomainAnalysisRequest(frame_range=range(2))

    first = module.run(series, request)
    adapter.analyzed_frame_indices.clear()
    adapter.m6_settings_fingerprint = "m6-settings-v2"
    changed_settings = module.run(series, request)

    assert adapter.analyzed_frame_indices == [0, 1]
    assert first.m6_gate is not None
    assert changed_settings.m6_gate is not None
    assert tuple(frame.m6_gate_fingerprint for frame in first.m6_gate.frames) != (
        tuple(
            frame.m6_gate_fingerprint
            for frame in changed_settings.m6_gate.frames
        )
    )
    assert all(
        frame.m6_settings_fingerprint == "m6-settings-v2"
        for frame in changed_settings.m6_gate.frames
    )
    assert all(
        len(frame.m6_gate_fingerprint) == 64
        for frame in changed_settings.m6_gate.frames
    )

    adapter.analyzed_frame_indices.clear()
    adapter.m6_algorithm_version = "m6-algorithm-v2"
    changed_algorithm = module.run(series, request)

    assert adapter.analyzed_frame_indices == [0, 1]
    assert changed_algorithm.m6_gate is not None
    assert all(
        frame.m6_algorithm_version == "m6-algorithm-v2"
        for frame in changed_algorithm.m6_gate.frames
    )
    assert tuple(
        frame.m6_gate_fingerprint
        for frame in changed_settings.m6_gate.frames
    ) != tuple(
        frame.m6_gate_fingerprint
        for frame in changed_algorithm.m6_gate.frames
    )

    adapter.analyzed_frame_indices.clear()
    repeated = module.run(series, request)

    assert adapter.analyzed_frame_indices == []
    assert repeated == changed_algorithm


def test_run_evicts_the_least_recently_used_complete_m6_frame() -> None:
    adapter = _DeterministicM6Adapter(reorder_adapter_output=False)
    module = DomainAnalysisModule(
        adapter,
        classifier_adapters={},
        m6_cache_max_entries=2,
    )
    series = _geometry_series(frame_indices=range(3))

    first_snapshot = module.run(
        series,
        DomainAnalysisRequest(frame_range=range(1)),
    )
    module.run(series, DomainAnalysisRequest(frame_range=range(1, 2)))
    module.run(series, DomainAnalysisRequest(frame_range=range(1)))
    module.run(series, DomainAnalysisRequest(frame_range=range(2, 3)))
    adapter.analyzed_frame_indices.clear()

    retained = module.run(series, DomainAnalysisRequest(frame_range=range(1)))
    evicted = module.run(series, DomainAnalysisRequest(frame_range=range(1, 2)))

    assert adapter.analyzed_frame_indices == [1]
    assert retained == first_snapshot
    assert evicted.m6_gate is not None
    assert first_snapshot.m6_gate is not None
    assert first_snapshot.m6_gate.frames[0].frame_index == 0


def test_run_never_reuses_failed_or_not_started_m6_frames() -> None:
    series = _geometry_series(frame_indices=range(2))
    request = DomainAnalysisRequest(frame_range=range(2))
    failing_adapter = _DeterministicM6Adapter(
        reorder_adapter_output=False,
        fail_frame_index=1,
    )
    failing_module = DomainAnalysisModule(failing_adapter, classifier_adapters={})

    failed = failing_module.run(series, request)
    failing_adapter.fail_frame_index = None
    failing_adapter.analyzed_frame_indices.clear()
    recovered = failing_module.run(series, request)

    assert failed.run_status == "failed"
    assert recovered.run_status == "completed"
    assert failing_adapter.analyzed_frame_indices == [1]

    canceled_adapter = _DeterministicM6Adapter(reorder_adapter_output=False)
    canceled_module = DomainAnalysisModule(canceled_adapter, classifier_adapters={})
    canceled = canceled_module.run(
        series,
        request,
        is_cancelled=lambda: canceled_adapter.analyzed_frame_indices == [0],
    )
    canceled_adapter.analyzed_frame_indices.clear()
    retried = canceled_module.run(series, request)

    assert canceled.run_status == "canceled"
    assert retried.run_status == "completed"
    assert canceled_adapter.analyzed_frame_indices == [1]


def test_run_owns_stable_component_ids_instead_of_backend_ordering_ids() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    canonical = DomainAnalysisModule(
        _DeterministicM6Adapter(reorder_adapter_output=False),
        classifier_adapters={},
    ).run(_geometry_series(), request)
    backend_renamed = DomainAnalysisModule(
        _DeterministicM6Adapter(
            reorder_adapter_output=True,
            backend_component_ids=("library-random-91", "library-random-03"),
        ),
        classifier_adapters={},
    ).run(_geometry_series(), request)

    assert canonical == backend_renamed
    assert canonical.m6_gate is not None
    frame = canonical.m6_gate.frames[0]
    assert frame.full_domains[0].lattice_domain_id.startswith("m6-full-")
    assert frame.small_ordered_islands[0].lattice_domain_id.startswith(
        "m6-island-"
    )


def test_run_keeps_view_only_shifts_out_of_canonical_geometry() -> None:
    request = DomainAnalysisRequest(frame_range=range(1))
    module = DomainAnalysisModule(
        _DeterministicM6Adapter(reorder_adapter_output=False),
        classifier_adapters={},
    )

    first = module.run(_geometry_series("expanded_aligned"), request)
    shifted_presentation = module.run(
        _geometry_series(
            "expanded_aligned",
            frame_origin=(3.0, 2.0),
            canvas_offset=(17.0, 19.0),
            registration_fingerprint="registration-v2",
        ),
        request,
    )

    assert first.m6_gate is not None
    assert shifted_presentation.m6_gate is not None
    first_frame = first.m6_gate.frames[0]
    shifted_frame = shifted_presentation.m6_gate.frames[0]
    assert first_frame.coordinate_transform_fingerprint == (
        shifted_frame.coordinate_transform_fingerprint
    )
    assert first_frame.source_geometry_fingerprint == (
        shifted_frame.source_geometry_fingerprint
    )
    assert first_frame.full_domains == shifted_frame.full_domains
    assert first_frame.presentation_provenance != (
        shifted_frame.presentation_provenance
    )


def test_run_clips_registered_padding_and_falls_back_from_degenerate_mask() -> None:
    source = _geometry_series("expanded_aligned", range(1))
    frame_input = source.frames[0]
    annotations = tuple(
        M6SourceAnnotation(
            source_id="m-a",
            source_view="expanded_aligned",
            bbox_xyxy=(1.0, 0.5, 3.0, 2.5),
            mask_shape=(6, 7),
            mask_pixels_xy=(),
        )
        if value.source_id == "m-a"
        else value
        for value in frame_input.annotations
    )
    clipped_series = DomainAnalysisSeries(frames=(DomainAnalysisFrame(
        frame_index=0,
        source_view=frame_input.source_view,
        geometry=frame_input.geometry,
        annotations=annotations,
    ),))

    result = DomainAnalysisModule(
        _DeterministicM6Adapter(reorder_adapter_output=False),
        classifier_adapters={},
    ).run(clipped_series, DomainAnalysisRequest(frame_range=range(1)))

    assert result.m6_gate is not None
    frame = result.m6_gate.frames[0]
    assert frame.full_domains[0].points_xy_nm[0] == (0.5, 3.25)
    assert all(
        0 <= x < 4 and 0 <= y < 4
        for x, y in frame.analyzed_pixels_xy
    )


def test_run_rejects_nonempty_mask_wholly_in_registered_padding() -> None:
    source = _geometry_series("expanded_aligned", range(1))
    frame_input = source.frames[0]
    annotations = tuple(
        M6SourceAnnotation(
            source_id="m-a",
            source_view="expanded_aligned",
            bbox_xyxy=(1.0, 0.5, 3.0, 2.5),
            mask_shape=(6, 7),
            mask_pixels_xy=((0, 0),),
        )
        if value.source_id == "m-a"
        else value
        for value in frame_input.annotations
    )
    padding_series = DomainAnalysisSeries(frames=(DomainAnalysisFrame(
        frame_index=0,
        source_view=frame_input.source_view,
        geometry=frame_input.geometry,
        annotations=annotations,
    ),))

    with pytest.raises(ValueError, match="mask does not overlap"):
        DomainAnalysisModule(
            _DeterministicM6Adapter(reorder_adapter_output=False),
            classifier_adapters={},
        ).run(padding_series, DomainAnalysisRequest(frame_range=range(1)))


def test_run_publishes_immutable_deterministic_single_frame_m6_partition() -> None:
    request = DomainAnalysisRequest(
        frame_range=range(7, 8),
        geometry_mode="segmentation_preferred",
        classifier_ids=(),
    )

    first = DomainAnalysisModule(
        _DeterministicM6Adapter(reorder_adapter_output=False),
        classifier_adapters={},
    ).run(_geometry_series(), request)
    reordered = DomainAnalysisModule(
        _DeterministicM6Adapter(reorder_adapter_output=True),
        classifier_adapters={},
    ).run(_geometry_series(), request)
    changed_geometry = DomainAnalysisModule(
        _DeterministicM6Adapter(reorder_adapter_output=False),
        classifier_adapters={},
    ).run(_geometry_series(alternate_geometry=True), request)

    assert first == reordered
    assert first.run_status == "completed"
    assert first.classifier_status == "not_requested"
    assert first.classifier_outcomes is None
    assert first.m6_gate is not None
    assert len(first.m6_gate.frames) == 1

    frame = first.m6_gate.frames[0]
    assert frame.frame_index == 7
    assert tuple(domain.lattice_domain_id for domain in frame.full_domains) == (
        "m6-full-641c51c2936f",
    )
    assert tuple(
        island.lattice_domain_id for island in frame.small_ordered_islands
    ) == ("m6-island-dbb87348ff2e",)
    assert frame.outside_source_ids == ("m-d",)

    full_ids = {
        source_id
        for domain in frame.full_domains
        for source_id in domain.source_ids
    }
    island_ids = {
        source_id
        for island in frame.small_ordered_islands
        for source_id in island.source_ids
    }
    outside_ids = set(frame.outside_source_ids)
    assert full_ids.isdisjoint(island_ids)
    assert full_ids.isdisjoint(outside_ids)
    assert island_ids.isdisjoint(outside_ids)
    assert full_ids | island_ids | outside_ids == set(frame.analyzed_source_ids)
    full_pixels = {
        pixel
        for domain in frame.full_domains
        for pixel in domain.footprint_pixels_xy
    }
    island_pixels = {
        pixel
        for island in frame.small_ordered_islands
        for pixel in island.footprint_pixels_xy
    }
    outside_pixels = set(frame.outside_pixels_xy)
    assert full_pixels.isdisjoint(island_pixels)
    assert full_pixels.isdisjoint(outside_pixels)
    assert island_pixels.isdisjoint(outside_pixels)
    assert full_pixels | island_pixels | outside_pixels == set(frame.analyzed_pixels_xy)
    assert frame.analyzed_molecule_count == 4
    assert isclose(
        frame.full_domain_area_nm2
        + frame.small_ordered_island_area_nm2
        + frame.outside_area_nm2,
        frame.analyzed_area_nm2,
        abs_tol=1e-12,
    )

    domain = frame.full_domains[0]
    assert domain.source_ids == ("m-a", "m-b")
    assert domain.points_xy_nm == ((0.5, 3.0), (1.5, 3.0))
    assert domain.footprint_pixels_xy == ((0, 0), (0, 1), (1, 0), (1, 1))
    assert domain.footprint_area_nm2 == 4.0
    assert domain.centroid_xy_nm == (1.0, 3.0)
    assert domain.bounds_xyxy_nm == (0.5, 3.0, 1.5, 3.0)
    assert (
        frame.source_geometry_fingerprint
        != changed_geometry.m6_gate.frames[0].source_geometry_fingerprint
    )

    with pytest.raises(FrozenInstanceError):
        request.classifier_ids = ("abc_orientation",)  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        frame.frame_index = 8  # type: ignore[misc]


def test_result_rejects_impossible_success_states() -> None:
    completed = DomainAnalysisModule(
        _DeterministicM6Adapter(reorder_adapter_output=False),
        classifier_adapters={},
    ).run(_geometry_series(), DomainAnalysisRequest(frame_range=range(1)))

    with pytest.raises(ValueError, match="successful Domain Analysis"):
        DomainAnalysisResult(
            run_status="completed_with_errors",
            m6_gate=None,
            classifier_status="not_requested",
        )
    with pytest.raises(ValueError, match="requires requested classifiers"):
        DomainAnalysisResult(
            run_status="completed_with_errors",
            m6_gate=completed.m6_gate,
            classifier_status="not_requested",
        )


def test_run_publishes_complete_frame_range_once_in_canonical_order() -> None:
    events = []
    request = DomainAnalysisRequest(
        frame_range=range(3, 6),
        classifier_ids=(),
    )

    result = DomainAnalysisModule(
        _DeterministicM6Adapter(reorder_adapter_output=True),
        classifier_adapters={},
    ).run(_geometry_series(), request, on_event=events.append)

    assert result.run_status == "completed"
    assert result.classifier_status == "not_requested"
    assert result.classifier_outcomes is None
    assert result.m6_gate is not None
    assert tuple(frame.frame_index for frame in result.m6_gate.frames) == (3, 4, 5)
    assert all(
        frame.analyzed_source_ids == ("m-a", "m-b", "m-c", "m-d")
        and frame.outside_source_ids == ("m-d",)
        for frame in result.m6_gate.frames
    )
    assert [
        (event.stage_id, event.status, event.frame_index)
        for event in events
    ] == [
        ("run", "started", None),
        ("m6", "progress", 3),
        ("m6", "progress", 4),
        ("m6", "progress", 5),
        ("m6", "published", None),
        ("run", "completed", None),
    ]


def test_run_reports_frame_failure_without_publishing_partial_range() -> None:
    events = []
    request = DomainAnalysisRequest(frame_range=range(2, 6))

    result = DomainAnalysisModule(
        _DeterministicM6Adapter(
            reorder_adapter_output=False,
            fail_frame_index=3,
        ),
        classifier_adapters={},
    ).run(_geometry_series(), request, on_event=events.append)

    assert result.run_status == "failed"
    assert result.m6_gate is None
    assert result.m6_result_published is False
    assert result.classifier_status == "not_requested"
    assert result.classifier_outcomes is None
    assert result.failure == DomainAnalysisFailure(
        stage_id="m6",
        frame_index=3,
        message="synthetic M6 backend failure",
    )
    assert [
        (event.stage_id, event.status, event.frame_index)
        for event in events
    ] == [
        ("run", "started", None),
        ("m6", "progress", 2),
        ("m6", "failed", 3),
        ("run", "failed", None),
    ]


def test_run_cancels_range_without_publishing_or_starting_later_frames() -> None:
    events = []
    request = DomainAnalysisRequest(frame_range=range(5, 8))

    result = DomainAnalysisModule(
        _DeterministicM6Adapter(reorder_adapter_output=False),
        classifier_adapters={},
    ).run(
        _geometry_series(),
        request,
        on_event=events.append,
        is_cancelled=lambda: any(event.status == "progress" for event in events),
    )

    assert result.run_status == "canceled"
    assert result.m6_gate is None
    assert result.m6_result_published is False
    assert result.failure is None
    assert result.classifier_status == "not_requested"
    assert result.classifier_outcomes is None
    assert [
        (event.stage_id, event.status, event.frame_index)
        for event in events
    ] == [
        ("run", "started", None),
        ("m6", "progress", 5),
        ("m6", "canceled", None),
        ("run", "canceled", None),
    ]


@pytest.mark.parametrize(
    ("adapter_options", "message"),
    (
        ({"overlap_categories": True}, "pixel partition categories must be disjoint"),
        ({"overlap_full_domains": True}, "pixel partition categories must be disjoint"),
        ({"leave_pixel_uncovered": True}, "footprints must cover"),
    ),
)
def test_run_rejects_an_invalid_m6_pixel_partition(
    adapter_options: dict[str, bool],
    message: str,
) -> None:
    request = DomainAnalysisRequest(frame_range=range(0, 1))
    adapter = _DeterministicM6Adapter(
        reorder_adapter_output=False,
        **adapter_options,
    )

    with pytest.raises(ValueError, match=message):
        DomainAnalysisModule(adapter, classifier_adapters={}).run(
            _geometry_series(
                overlap_pixel_geometry=(
                    "pixel partition" in message
                ),
            ),
            request,
        )


def test_run_continues_classifiers_in_request_order_after_a_failure() -> None:
    execution_order: list[tuple[str, int]] = []
    activity = {"active": 0, "max_active": 0}
    failing = _ControlledClassifier(
        "first_classifier",
        execution_order,
        activity,
        fail_frame_index=0,
    )
    succeeding = _ControlledClassifier(
        "second_classifier",
        execution_order,
        activity,
    )
    events = []

    result = DomainAnalysisModule(
        _DeterministicM6Adapter(reorder_adapter_output=False),
        classifier_adapters={
            succeeding.classifier_id: succeeding,
            failing.classifier_id: failing,
        },
    ).run(
        _classifier_series(range(1)),
        DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(failing.classifier_id, succeeding.classifier_id),
        ),
        on_event=events.append,
    )

    assert result.run_status == "completed_with_errors"
    assert result.classifier_status == "completed_with_errors"
    assert result.m6_gate is not None
    assert result.classifier_outcomes is not None
    assert tuple(outcome.classifier_id for outcome in result.classifier_outcomes) == (
        "first_classifier",
        "second_classifier",
    )
    assert tuple(outcome.status for outcome in result.classifier_outcomes) == (
        "failed",
        "completed",
    )
    assert result.classifier_outcomes[0].failure_frame_index == 0
    assert result.classifier_outcomes[0].molecule_classifications == ()
    assert result.classifier_outcomes[1].molecule_classifications
    assert execution_order == [
        ("first_classifier", 0),
        ("second_classifier", 0),
    ]
    assert activity == {"active": 0, "max_active": 1}
    assert [
        (event.stage_id, event.status, event.frame_index)
        for event in events
        if event.stage_id != "m6"
    ] == [
        ("run", "started", None),
        ("first_classifier", "started", None),
        ("first_classifier", "failed", 0),
        ("second_classifier", "started", None),
        ("second_classifier", "progress", 0),
        ("second_classifier", "published", None),
        ("run", "completed_with_errors", None),
    ]


def test_run_cancels_later_classifiers_and_retries_complete_cache_entries() -> None:
    execution_order: list[tuple[str, int]] = []
    activity = {"active": 0, "max_active": 0}
    cancel_signal = {"requested": False}
    first = _ControlledClassifier("first_classifier", execution_order, activity)
    canceling = _ControlledClassifier(
        "canceling_classifier",
        execution_order,
        activity,
        cancel_after_frame_index=0,
        cancel_signal=cancel_signal,
    )
    later = _ControlledClassifier("later_classifier", execution_order, activity)
    module = DomainAnalysisModule(
        _DeterministicM6Adapter(reorder_adapter_output=False),
        classifier_adapters={
            first.classifier_id: first,
            canceling.classifier_id: canceling,
            later.classifier_id: later,
        },
    )
    request = DomainAnalysisRequest(
        frame_range=range(2),
        classifier_ids=(
            first.classifier_id,
            canceling.classifier_id,
            later.classifier_id,
        ),
    )

    canceled = module.run(
        _classifier_series(range(2)),
        request,
        is_cancelled=lambda: cancel_signal["requested"],
    )

    assert canceled.run_status == "canceled"
    assert canceled.classifier_status == "canceled"
    assert canceled.m6_gate is not None
    assert canceled.classifier_outcomes is not None
    assert tuple(value.status for value in canceled.classifier_outcomes) == (
        "completed",
        "canceled",
        "not_run",
    )
    assert canceled.classifier_outcomes[0].molecule_classifications
    assert canceled.classifier_outcomes[1].molecule_classifications == ()
    assert canceled.classifier_outcomes[2].molecule_classifications == ()
    assert execution_order == [
        ("first_classifier", 0),
        ("first_classifier", 1),
        ("canceling_classifier", 0),
    ]
    assert activity == {"active": 0, "max_active": 1}

    execution_order.clear()
    cancel_signal["requested"] = False
    retried = module.run(_classifier_series(range(2)), request)

    assert retried.run_status == "completed"
    assert retried.classifier_outcomes is not None
    assert tuple(value.status for value in retried.classifier_outcomes) == (
        "completed",
        "completed",
        "completed",
    )
    assert execution_order == [
        ("canceling_classifier", 1),
        ("later_classifier", 0),
        ("later_classifier", 1),
    ]


def test_run_marks_requested_classifiers_not_run_after_m6_failure() -> None:
    execution_order: list[tuple[str, int]] = []
    activity = {"active": 0, "max_active": 0}
    first = _ControlledClassifier("first_classifier", execution_order, activity)
    second = _ControlledClassifier("second_classifier", execution_order, activity)
    events = []

    result = DomainAnalysisModule(
        _DeterministicM6Adapter(
            reorder_adapter_output=False,
            fail_frame_index=0,
        ),
        classifier_adapters={
            first.classifier_id: first,
            second.classifier_id: second,
        },
    ).run(
        _classifier_series(range(1)),
        DomainAnalysisRequest(
            frame_range=range(1),
            classifier_ids=(first.classifier_id, second.classifier_id),
        ),
        on_event=events.append,
    )

    assert result.run_status == "failed"
    assert result.classifier_status == "not_run"
    assert result.m6_gate is None
    assert result.classifier_outcomes is not None
    assert tuple(value.classifier_id for value in result.classifier_outcomes) == (
        "first_classifier",
        "second_classifier",
    )
    assert tuple(value.status for value in result.classifier_outcomes) == (
        "not_run",
        "not_run",
    )
    assert execution_order == []
    assert [
        (event.stage_id, event.status, event.frame_index)
        for event in events
    ] == [
        ("run", "started", None),
        ("m6", "failed", 0),
        ("first_classifier", "not_run", None),
        ("second_classifier", "not_run", None),
        ("run", "failed", None),
    ]
