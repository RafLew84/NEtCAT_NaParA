from __future__ import annotations

from functools import partial
from threading import Event

import numpy as np

from moltrack.analysis.domain_analysis import (
    DomainAnalysisFrame,
    DomainAnalysisModule,
    DomainAnalysisRequest,
    DomainAnalysisSeries,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    M6FrameGeometry,
    M6SourceAnnotation,
)
from moltrack.analysis.domain_analysis.canonical_geometry import canonicalize_frame
from domain_analysis_test_support import domain_analysis_module as DomainAnalysisModule

DomainAnalysisRequest = partial(
    DomainAnalysisRequest, backend_id=M6_ORIENTATION_COMPONENTS_BACKEND_ID
)
from moltrack.core import (
    MolecularDetectionSet,
    MolecularSegmentation,
    MolecularSegmentationSet,
    MolTrackImageSeries,
)
from moltrack.core.registration import (
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
)
from moltrack.persistence import CorrectionAwareExportSettings
from moltrack.ui import domain_analysis_runtime as runtime
from nanotrack.core import STMSequenceMetadata


def _series(tmp_path, *, frame_count: int = 1) -> MolTrackImageSeries:
    return MolTrackImageSeries(
        source_path=tmp_path / "movie.mpp",
        raw_frames=np.zeros((frame_count, 4, 6), dtype=np.float32),
        metadata=STMSequenceMetadata(
            pixels_x=6,
            pixels_y=4,
            size_nm_x=12.0,
            size_nm_y=12.0,
        ),
    )


def _triangular_detection_series(tmp_path, *, source_view: str) -> MolTrackImageSeries:
    series = MolTrackImageSeries(
        source_path=tmp_path / f"{source_view}.mpp",
        raw_frames=np.zeros((2, 64, 64), dtype=np.float32),
        metadata=STMSequenceMetadata(
            pixels_x=64,
            pixels_y=64,
            size_nm_x=640.0,
            size_nm_y=640.0,
        ),
    )
    offset_x = 0.0
    offset_y = 0.0
    if source_view == "expanded_aligned":
        series.registration_results = MolTrackRegistrationResultSet(
            settings=MolTrackRegistrationSettings(),
            results_by_frame={
                0: MolTrackRegistrationFrameResult(
                    frame_index=0,
                    shift_xy=(-2.0, 1.0),
                    method="manual",
                ),
                1: MolTrackRegistrationFrameResult(
                    frame_index=1,
                    shift_xy=(3.0, -1.0),
                    method="manual",
                ),
            },
        )
        offset_y = 2.0
    detections = MolecularDetectionSet(frame_count=2)
    for row in range(8):
        for column in range(8):
            center_x = 10.0 + 5.0 * column + 2.5 * (row % 2)
            center_y = 10.0 + (5.0 * np.sqrt(3.0) / 2.0) * row
            detections.add_detection(
                0,
                (
                    center_x - 1.0 + offset_x,
                    center_y - 1.0 + offset_y,
                    center_x + 1.0 + offset_x,
                    center_y + 1.0 + offset_y,
                ),
                source_view=source_view,
                detection_id=f"molecule-{row:02d}-{column:02d}",
            )
    series.molecular_detections = detections
    return series


def test_runtime_m6_uses_calibrated_raw_fov_boundary_distances(monkeypatch) -> None:
    geometry = M6FrameGeometry(
        physical_frame_id="source-frame-0",
        raw_shape=(4, 6),
        expanded_shape=(4, 6),
        frame_origin_xy=(0.0, 0.0),
        canvas_offset_xy=(0.0, 0.0),
        pixel_size_nm=(2.0, 3.0),
        scan_angle_deg=0.0,
        registration_fingerprint="unregistered",
    )
    series = DomainAnalysisSeries((DomainAnalysisFrame(
        frame_index=0,
        source_view="raw",
        geometry=geometry,
        annotations=(M6SourceAnnotation(
            source_id="molecule-1",
            source_view="raw",
            bbox_xyxy=(1.0, 0.0, 3.0, 2.0),
        ),),
    ),))
    canonical = canonicalize_frame(
        series,
        frame_index=0,
        geometry_mode="bbox_centers",
    )
    captured = {}

    def analyze(points, **kwargs):
        captured.update(kwargs)
        return type("Analysis", (), {
            "segmentation": type("Segmentation", (), {
                "components": (), "source_ids": ("molecule-1",),
                "assignment_status": ("outside",),
            })(),
            "local_order": type("LocalOrder", (), {
                "source_ids": ("molecule-1",), "q6": (None,),
            })(),
        })()

    monkeypatch.setattr(
        "moltrack.ui.domain_backend_adapters.analyze_m6_orientation_domains",
        analyze,
    )

    runtime._MolTrackM6Adapter(series).analyze_frame(
        canonical,
        frame_index=0,
        geometry_mode="bbox_centers",
    )

    assert captured["distance_to_valid_fov_boundary_nm"] == (3.0,)
    assert captured["window_geometry"] == "rectangular"
    assert captured["window_size_nm"] == (12.0, 12.0)


def test_runtime_uses_expanded_registration_provenance(tmp_path) -> None:
    series = _series(tmp_path, frame_count=2)
    series.registration_results = MolTrackRegistrationResultSet(
        settings=MolTrackRegistrationSettings(),
        results_by_frame={
            0: MolTrackRegistrationFrameResult(
                frame_index=0,
                shift_xy=(-2.0, 1.0),
                method="manual",
            ),
            1: MolTrackRegistrationFrameResult(
                frame_index=1,
                shift_xy=(3.0, -1.0),
                method="manual",
            ),
        },
    )

    analysis_series = runtime._domain_analysis_series(series)

    assert series.expanded_aligned_stack is not None
    assert analysis_series.frame(0).geometry.expanded_shape == (6, 11)
    assert analysis_series.frame(0).geometry.frame_origin_xy == (0.0, 2.0)
    assert analysis_series.frame(1).geometry.frame_origin_xy == (5.0, 0.0)
    assert analysis_series.frame(1).geometry.canvas_offset_xy == (2.0, 1.0)


def test_runtime_canonicalizes_expanded_only_annotations(tmp_path) -> None:
    series = _series(tmp_path, frame_count=2)
    series.registration_results = MolTrackRegistrationResultSet(
        settings=MolTrackRegistrationSettings(),
        results_by_frame={
            0: MolTrackRegistrationFrameResult(
                frame_index=0,
                shift_xy=(-2.0, 1.0),
                method="manual",
            ),
            1: MolTrackRegistrationFrameResult(
                frame_index=1,
                shift_xy=(3.0, -1.0),
                method="manual",
            ),
        },
    )
    detections = MolecularDetectionSet(frame_count=2)
    detections.add_detection(
        0,
        (1.0, 2.0, 3.0, 4.0),
        source_view="expanded_aligned",
        frame_shape=(6, 11),
        detection_id="registered-molecule",
    )
    series.molecular_detections = detections

    analysis_series = runtime._domain_analysis_series(series)
    frame = analysis_series.frame(0)
    canonical = canonicalize_frame(
        analysis_series,
        frame_index=0,
        geometry_mode="bbox_centers",
    )

    assert frame.source_view == "expanded_aligned"
    assert tuple(value.source_id for value in frame.annotations) == (
        "registered-molecule",
    )
    assert canonical.molecules[0].raw_centroid_xy == (2.0, 1.0)
    assert canonical.molecules[0].centroid_xy_nm == (4.0, 9.0)


def test_runtime_uses_one_view_and_deduplicates_segmentation_prompts(
    tmp_path,
) -> None:
    series = _series(tmp_path, frame_count=2)
    series.registration_results = MolTrackRegistrationResultSet(
        settings=MolTrackRegistrationSettings(),
        results_by_frame={
            0: MolTrackRegistrationFrameResult(
                frame_index=0,
                shift_xy=(-2.0, 1.0),
                method="manual",
            ),
            1: MolTrackRegistrationFrameResult(
                frame_index=1,
                shift_xy=(3.0, -1.0),
                method="manual",
            ),
        },
    )
    detections = MolecularDetectionSet(frame_count=2)
    detections.add_detection(
        0,
        (1.0, 2.0, 3.0, 4.0),
        source_view="expanded_aligned",
        detection_id="segmentation-prompt",
    )
    detections.add_detection(
        0,
        (3.0, 2.0, 5.0, 4.0),
        source_view="expanded_aligned",
        detection_id="unmatched-expanded",
    )
    detections.add_detection(
        1,
        (1.0, 1.0, 3.0, 3.0),
        source_view="raw",
        detection_id="raw-wins",
    )
    detections.add_detection(
        1,
        (6.0, 1.0, 8.0, 3.0),
        source_view="expanded_aligned",
        detection_id="ignored-expanded",
    )
    mask = np.zeros((6, 11), dtype=bool)
    mask[2:4, 1:3] = True
    segmentations = MolecularSegmentationSet(frame_count=2)
    segmentations.add_segmentation(MolecularSegmentation(
        frame_index=0,
        source_view="expanded_aligned",
        bbox_xyxy=(1.0, 2.0, 3.0, 4.0),
        mask=mask,
        prompt_detection_ids=("segmentation-prompt",),
        segmentation_id="expanded-segmentation",
    ))
    series.molecular_detections = detections
    series.molecular_segmentations = segmentations

    analysis_series = runtime._domain_analysis_series(series)
    first = analysis_series.frame(0)
    second = analysis_series.frame(1)
    canonical = canonicalize_frame(
        analysis_series,
        frame_index=0,
        geometry_mode="segmentation_preferred",
    )

    assert first.source_view == "expanded_aligned"
    assert tuple(value.source_id for value in first.annotations) == (
        "expanded-segmentation",
        "unmatched-expanded",
    )
    assert tuple(value.source_id for value in canonical.molecules) == (
        "expanded-segmentation",
        "unmatched-expanded",
    )
    assert second.source_view == "raw"
    assert tuple(value.source_id for value in second.annotations) == ("raw-wins",)


def test_runtime_raw_and_expanded_annotations_publish_the_same_m6_membership(
    tmp_path,
) -> None:
    raw_series = runtime._domain_analysis_series(
        _triangular_detection_series(tmp_path, source_view="raw")
    )
    expanded_series = runtime._domain_analysis_series(
        _triangular_detection_series(tmp_path, source_view="expanded_aligned")
    )
    raw_adapter = runtime._MolTrackM6Adapter(raw_series)
    expanded_adapter = runtime._MolTrackM6Adapter(expanded_series)
    raw_request = DomainAnalysisRequest(
        frame_range=range(1),
        classifier_ids=(),
        m6_configuration=raw_adapter.default_run_configuration(),
    )
    expanded_request = DomainAnalysisRequest(
        frame_range=range(1),
        classifier_ids=(),
        m6_configuration=expanded_adapter.default_run_configuration(),
    )
    raw_result = DomainAnalysisModule(
        raw_adapter,
        classifier_adapters={},
    ).run(raw_series, raw_request)
    expanded_result = DomainAnalysisModule(
        expanded_adapter,
        classifier_adapters={},
    ).run(expanded_series, expanded_request)

    assert raw_result.run_status == "completed"
    assert expanded_result.run_status == "completed"
    assert raw_result.m6_gate is not None
    assert expanded_result.m6_gate is not None
    raw_frame = raw_result.m6_gate.frames[0]
    expanded_frame = expanded_result.m6_gate.frames[0]
    assert raw_frame.full_domains
    assert expanded_frame.source_geometry_fingerprint == (
        raw_frame.source_geometry_fingerprint
    )
    assert expanded_frame.full_domains == raw_frame.full_domains
    assert expanded_frame.small_ordered_islands == raw_frame.small_ordered_islands
    assert expanded_frame.outside_source_ids == raw_frame.outside_source_ids
    raw_canonical = canonicalize_frame(
        raw_series,
        frame_index=0,
        geometry_mode="segmentation_preferred",
    )
    expanded_canonical = canonicalize_frame(
        expanded_series,
        frame_index=0,
        geometry_mode="segmentation_preferred",
    )
    assert expanded_canonical.coordinate_transform_fingerprint == (
        raw_canonical.coordinate_transform_fingerprint
    )
    assert tuple(
        (value.source_id, value.raw_centroid_xy, value.footprint_pixels_xy)
        for value in expanded_canonical.molecules
    ) == tuple(
        (value.source_id, value.raw_centroid_xy, value.footprint_pixels_xy)
        for value in raw_canonical.molecules
    )


def test_runtime_export_chooses_a_new_package_below_selected_directory(
    tmp_path,
    monkeypatch,
) -> None:
    series = _series(tmp_path)
    first = tmp_path / "movie-domain-analysis"
    first.mkdir()
    monkeypatch.setattr(
        runtime.QFileDialog,
        "getExistingDirectory",
        lambda *_args: str(tmp_path),
    )

    settings = runtime._export_settings(None, series, ("source-frame-0",))

    assert isinstance(settings, CorrectionAwareExportSettings)
    assert settings.destination == tmp_path / "movie-domain-analysis-2"
    assert not settings.destination.exists()


def test_runtime_executor_shutdown_is_nonblocking_and_process_safe() -> None:
    started = Event()
    release = Event()
    executor = runtime._DaemonDomainAnalysisExecutor()
    executor.submit(lambda: (started.set(), release.wait()))
    assert started.wait(timeout=1.0)

    executor.shutdown()

    assert executor.worker_is_daemon
    release.set()
