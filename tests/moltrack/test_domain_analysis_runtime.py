from __future__ import annotations

from threading import Event

import numpy as np

from moltrack.analysis.domain_analysis import (
    DomainAnalysisFrame,
    DomainAnalysisSeries,
    M6FrameGeometry,
    M6SourceAnnotation,
)
from moltrack.analysis.domain_analysis.canonical_geometry import canonicalize_frame
from moltrack.core import MolTrackImageSeries
from moltrack.core.registration import (
    MolTrackRegistrationFrameResult,
    MolTrackRegistrationResultSet,
    MolTrackRegistrationSettings,
)
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
            "segmentation": type("Segmentation", (), {"components": ()})(),
        })()

    monkeypatch.setattr(runtime, "analyze_m6_orientation_domains", analyze)

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
