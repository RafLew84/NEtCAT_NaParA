from __future__ import annotations

from dataclasses import FrozenInstanceError
from math import isclose

import pytest

from moltrack.analysis.domain_analysis import (
    DomainAnalysisFailure,
    DomainAnalysisModule,
    DomainAnalysisRequest,
    DomainAnalysisResult,
    M6AnalyzedMolecule,
    M6ComponentMembership,
    M6FrameComputation,
    M6FrameAnalysisError,
)


class _DeterministicM6Adapter:
    def __init__(
        self,
        *,
        reorder_adapter_output: bool,
        alternate_pixel_geometry: bool = False,
        overlap_categories: bool = False,
        overlap_full_domains: bool = False,
        leave_pixel_uncovered: bool = False,
        fail_frame_index: int | None = None,
    ) -> None:
        self._reorder_adapter_output = reorder_adapter_output
        self._alternate_pixel_geometry = alternate_pixel_geometry
        self._overlap_categories = overlap_categories
        self._overlap_full_domains = overlap_full_domains
        self._leave_pixel_uncovered = leave_pixel_uncovered
        self._fail_frame_index = fail_frame_index

    def analyze_frame(
        self,
        series: object,
        *,
        frame_index: int,
        geometry_mode: str,
    ) -> M6FrameComputation:
        del series, geometry_mode
        if frame_index == self._fail_frame_index:
            raise M6FrameAnalysisError("synthetic M6 backend failure")
        first_pixels = (
            ((0, 0), (1, 0))
            if self._alternate_pixel_geometry
            else ((0, 0), (0, 1))
        )
        second_pixels = (
            ((0, 1), (1, 1))
            if self._alternate_pixel_geometry
            else ((1, 0), (1, 1))
        )
        island_pixels = (
            ((0, 0),)
            if self._overlap_categories or self._overlap_full_domains
            else ((2, 0),)
        )
        molecules = (
            M6AnalyzedMolecule("m-a", (0.0, 0.0), first_pixels),
            M6AnalyzedMolecule("m-b", (2.0, 0.0), second_pixels),
            M6AnalyzedMolecule("m-c", (5.0, 5.0), island_pixels),
            M6AnalyzedMolecule("m-d", (9.0, 9.0), ((3, 0), (3, 1), (3, 2))),
        )
        full_domains = (
            M6ComponentMembership(
                lattice_domain_id="lattice-0001",
                source_ids=("m-b", "m-a"),
                core_source_ids=("m-a",),
                halo_source_ids=("m-b",),
            ),
        )
        islands = (
            M6ComponentMembership(
                lattice_domain_id="lattice-0002",
                source_ids=("m-c",),
                core_source_ids=("m-c",),
            ),
        )
        if self._overlap_full_domains:
            full_domains += islands
            islands = ()
        analyzed_pixels = tuple(sorted({
            pixel
            for molecule in molecules
            for pixel in molecule.footprint_pixels_xy
        }))
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
            pixel_area_nm2=1.0,
            full_domains=full_domains,
            small_ordered_islands=islands,
            coordinate_frame="sample_nm",
            coordinate_transform_fingerprint="geometry-v1",
            m6_settings_fingerprint="m6-settings-v1",
        )


def test_run_publishes_immutable_deterministic_single_frame_m6_partition() -> None:
    request = DomainAnalysisRequest(
        frame_range=range(7, 8),
        geometry_mode="segmentation_preferred",
        classifier_ids=(),
    )

    first = DomainAnalysisModule(
        _DeterministicM6Adapter(reorder_adapter_output=False),
        classifier_adapters={},
    ).run(object(), request)
    reordered = DomainAnalysisModule(
        _DeterministicM6Adapter(reorder_adapter_output=True),
        classifier_adapters={},
    ).run(object(), request)
    changed_geometry = DomainAnalysisModule(
        _DeterministicM6Adapter(
            reorder_adapter_output=False,
            alternate_pixel_geometry=True,
        ),
        classifier_adapters={},
    ).run(object(), request)

    assert first == reordered
    assert first.run_status == "completed"
    assert first.classifier_status == "not_requested"
    assert first.classifier_outcomes is None
    assert first.m6_gate is not None
    assert len(first.m6_gate.frames) == 1

    frame = first.m6_gate.frames[0]
    assert frame.frame_index == 7
    assert tuple(domain.lattice_domain_id for domain in frame.full_domains) == (
        "lattice-0001",
    )
    assert tuple(
        island.lattice_domain_id for island in frame.small_ordered_islands
    ) == ("lattice-0002",)
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
    assert domain.points_xy_nm == ((0.0, 0.0), (2.0, 0.0))
    assert domain.footprint_pixels_xy == ((0, 0), (0, 1), (1, 0), (1, 1))
    assert domain.footprint_area_nm2 == 4.0
    assert domain.centroid_xy_nm == (1.0, 0.0)
    assert domain.bounds_xyxy_nm == (0.0, 0.0, 2.0, 0.0)
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
    ).run(object(), DomainAnalysisRequest(frame_range=range(1)))

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
    ).run(object(), request, on_event=events.append)

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
    ).run(object(), request, on_event=events.append)

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
        object(),
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
        DomainAnalysisModule(adapter, classifier_adapters={}).run(object(), request)
