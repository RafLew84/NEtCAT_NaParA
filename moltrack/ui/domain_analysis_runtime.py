from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Literal

import numpy as np
from PyQt6.QtWidgets import QFileDialog, QMainWindow

from moltrack.analysis import TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
from moltrack.analysis._m6_settings_fingerprint import m6_settings_fingerprint
from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    ClassifierConfiguration,
    ClassifierIdentity,
    DomainAnalysisFrame,
    DomainAnalysisModule,
    DomainAnalysisRequest,
    DomainAnalysisSeries,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceExecution,
    M6ComponentMembership,
    M6FrameComputation,
    M6FrameGeometry,
    M6SourceAnnotation,
    TextureABCClassifierAdapter,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256
from moltrack.analysis.orientation_domain_analysis import (
    analyze_m6_orientation_domains,
)
from moltrack.core import (
    MolTrackImageSeries,
    build_moltrack_expanded_aligned_stack,
)
from moltrack.persistence import CanonicalJsonObject, DomainAnalysisExportSettings
from moltrack.ui.domain_analysis_composition import (
    DomainAnalysisMainWindowComposition,
)


class _DaemonDomainAnalysisExecutor:
    def __init__(self) -> None:
        self._jobs: Queue[Callable[[], None] | None] = Queue()
        self._lock = Lock()
        self._shutdown = False
        self._thread = Thread(
            target=self._run,
            name="moltrack-domain-analysis",
            daemon=True,
        )
        self._thread.start()

    @property
    def worker_is_daemon(self) -> bool:
        return self._thread.daemon

    def submit(self, job: Callable[[], None]) -> None:
        if not callable(job):
            raise TypeError("job must be callable.")
        with self._lock:
            if self._shutdown:
                raise RuntimeError("Domain Analysis executor is shut down.")
            self._jobs.put(job)

    def shutdown(self) -> None:
        with self._lock:
            if self._shutdown:
                return
            self._shutdown = True
            while True:
                try:
                    self._jobs.get_nowait()
                    self._jobs.task_done()
                except Empty:
                    break
            self._jobs.put(None)

    def _run(self) -> None:
        while True:
            job = self._jobs.get()
            try:
                if job is None:
                    return
                job()
            finally:
                self._jobs.task_done()


class _MolTrackM6Adapter:
    m6_algorithm_version = "moltrack-m6-orientation-v1"

    def __init__(self, series: DomainAnalysisSeries) -> None:
        self._settings = TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
        self.m6_settings_fingerprint = m6_settings_fingerprint(self._settings)
        self._geometry_by_frame = {
            value.frame_index: value.geometry for value in series.frames
        }

    def analyze_frame(
        self,
        frame,
        *,
        frame_index: int,
        geometry_mode: str,
    ) -> M6FrameComputation:
        del geometry_mode
        geometry = self._geometry_by_frame[frame_index]
        if not frame.molecules:
            return self._computation(frame, frame_index=frame_index, components=())
        analysis = analyze_m6_orientation_domains(
            tuple(value.centroid_xy_nm for value in frame.molecules),
            distance_to_valid_fov_boundary_nm=_boundary_distances_to_raw_fov(
                frame.molecules,
                geometry.raw_shape,
                geometry.pixel_size_nm,
            ),
            point_ids=tuple(value.source_id for value in frame.molecules),
            settings=self._settings,
            spatial_calibration_fingerprint=(frame.coordinate_transform_fingerprint),
            registration_fingerprint=(
                frame.presentation_provenance.registration_fingerprint
            ),
            window_geometry="rectangular",
            window_size_nm=(
                geometry.raw_shape[1] * geometry.pixel_size_nm[0],
                geometry.raw_shape[0] * geometry.pixel_size_nm[1],
            ),
        )
        return self._computation(
            frame,
            frame_index=frame_index,
            components=analysis.segmentation.components,
        )

    def _computation(
        self, frame, *, frame_index: int, components
    ) -> M6FrameComputation:
        full_domains: list[M6ComponentMembership] = []
        islands: list[M6ComponentMembership] = []
        for component in components:
            membership = M6ComponentMembership(
                lattice_domain_id=(
                    f"m6-domain-{component.m6_orientation_domain_id}"
                    if component.component_type == "full_domain"
                    else f"m6-island-{component.ordered_component_id}"
                ),
                source_ids=component.source_ids,
            )
            (
                full_domains if component.component_type == "full_domain" else islands
            ).append(membership)
        return M6FrameComputation(
            frame_index=frame_index,
            molecules=frame.molecules,
            analyzed_pixels_xy=frame.analyzed_pixels_xy,
            pixel_area_nm2=frame.pixel_area_nm2,
            full_domains=tuple(full_domains),
            small_ordered_islands=tuple(islands),
            coordinate_frame=frame.coordinate_frame,
            coordinate_transform_fingerprint=(frame.coordinate_transform_fingerprint),
            m6_settings_fingerprint=self.m6_settings_fingerprint,
        )


def build_domain_analysis_main_window_composition(
    owner: QMainWindow,
    series: MolTrackImageSeries,
) -> DomainAnalysisMainWindowComposition:
    analysis_series = _domain_analysis_series(series)
    classifier = TextureABCClassifierAdapter()
    module = DomainAnalysisModule(
        _MolTrackM6Adapter(analysis_series),
        {ABC_ORIENTATION_CLASSIFIER_ID: classifier},
    )
    physical_frame_ids = tuple(
        frame.geometry.physical_frame_id for frame in analysis_series.frames
    )
    controller = DomainAnalysisWorkspaceController(
        DomainAnalysisRequest(
            frame_range=range(series.frame_count),
            classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
        ),
        physical_frame_ids=physical_frame_ids,
        execution=DomainAnalysisWorkspaceExecution(
            module,
            analysis_series,
            _DaemonDomainAnalysisExecutor(),
        ),
    )
    configuration = ClassifierConfiguration(
        identity=ClassifierIdentity(
            classifier_id=classifier.classifier_id,
            schema_version=classifier.classifier_schema_version,
            settings_fingerprint=classifier.classifier_settings_fingerprint,
            algorithm_version=classifier.classifier_algorithm_version,
        ),
        aggregation_preset=classifier.domain_aggregation_preset,
    )
    return DomainAnalysisMainWindowComposition(
        owner,
        controller,
        session_series=series,
        classifier_configurations=(configuration,),
        m6_preset_name="TTMAPP M6 approved",
        classifier_preset_name="TTMAPP M6-gated A/B/C",
        export_settings_for=lambda _publication: _export_settings(
            owner,
            series,
            physical_frame_ids,
        ),
    )


def _domain_analysis_series(series: MolTrackImageSeries) -> DomainAnalysisSeries:
    scale_x, scale_y = series.pixel_size_nm
    if scale_x is None or scale_y is None:
        raise ValueError(
            "Domain Analysis requires positive X/Y physical pixel calibration."
        )
    raw_shape = series.frame_shape
    expanded = series.expanded_aligned_stack
    if series.registration_results is not None and expanded is None:
        expanded = build_moltrack_expanded_aligned_stack(series)
    registration_fingerprint = _registration_fingerprint(series)
    scan_angle = float(getattr(series.metadata, "scan_angle_deg", 0.0))
    frames = []
    source_frame_indices = series.source_frame_indices
    if source_frame_indices is None:
        raise RuntimeError("Image series has no source-frame mapping.")
    for frame_index, source_frame_index in enumerate(source_frame_indices):
        expanded_shape = (
            raw_shape
            if expanded is None
            else (
                int(expanded.frames.shape[1]),
                int(expanded.frames.shape[2]),
            )
        )
        frame_origin_xy = (
            (0.0, 0.0)
            if expanded is None
            else (
                float(expanded.frame_origins_xy[frame_index][0]),
                float(expanded.frame_origins_xy[frame_index][1]),
            )
        )
        canvas_offset_xy = (
            (0.0, 0.0)
            if expanded is None
            else (
                float(expanded.canvas_offset_xy[0]),
                float(expanded.canvas_offset_xy[1]),
            )
        )
        annotation_view, annotations = _frame_annotations(
            series,
            frame_index,
            expanded_shape=expanded_shape,
        )
        frames.append(
            DomainAnalysisFrame(
                frame_index=frame_index,
                source_view=annotation_view,
                geometry=M6FrameGeometry(
                    physical_frame_id=f"source-frame-{source_frame_index}",
                    raw_shape=raw_shape,
                    expanded_shape=expanded_shape,
                    frame_origin_xy=frame_origin_xy,
                    canvas_offset_xy=canvas_offset_xy,
                    pixel_size_nm=(float(scale_x), float(scale_y)),
                    scan_angle_deg=scan_angle,
                    registration_fingerprint=registration_fingerprint,
                ),
                annotations=annotations,
                raw_frame=series.get_frame(frame_index),
            )
        )
    return DomainAnalysisSeries(tuple(frames))


def _frame_annotations(
    series: MolTrackImageSeries,
    frame_index: int,
    *,
    expanded_shape: tuple[int, int],
) -> tuple[
    Literal["raw", "expanded_aligned"],
    tuple[M6SourceAnnotation, ...],
]:
    for source_view in ("raw", "expanded_aligned"):
        annotations = _annotations(
            series,
            frame_index,
            source_view=source_view,
            frame_shape=(
                series.frame_shape
                if source_view == "raw"
                else expanded_shape
            ),
        )
        if annotations:
            return source_view, annotations
    return "raw", ()


def _annotations(
    series: MolTrackImageSeries,
    frame_index: int,
    *,
    source_view: Literal["raw", "expanded_aligned"],
    frame_shape: tuple[int, int],
) -> tuple[M6SourceAnnotation, ...]:
    annotations = []
    linked_detection_ids: set[str] = set()
    segmentations = series.molecular_segmentations
    if segmentations is not None:
        for segmentation in segmentations.get_segmentations(
            frame_index,
            source_view=source_view,
        ):
            mask = (
                None
                if segmentation.mask is None
                else np.asarray(
                    segmentation.mask,
                    dtype=bool,
                )
            )
            if mask is None or mask.shape != frame_shape or not np.any(mask):
                continue
            y_values, x_values = np.nonzero(mask)
            bbox = segmentation.bbox_xyxy or (
                float(x_values.min()),
                float(y_values.min()),
                float(x_values.max() + 1),
                float(y_values.max() + 1),
            )
            annotations.append(
                M6SourceAnnotation(
                    source_id=segmentation.segmentation_id,
                    source_view=source_view,
                    bbox_xyxy=bbox,
                    mask_shape=(int(mask.shape[0]), int(mask.shape[1])),
                    mask_pixels_xy=tuple(
                        (int(x), int(y)) for y, x in zip(y_values, x_values)
                    ),
                )
            )
            linked_detection_ids.update(segmentation.prompt_detection_ids)
    detections = series.molecular_detections
    if detections is not None:
        for detection in detections.get_detections(
            frame_index,
            source_view=source_view,
        ):
            if detection.detection_id not in linked_detection_ids:
                annotations.append(
                    M6SourceAnnotation(
                        source_id=detection.detection_id,
                        source_view=source_view,
                        bbox_xyxy=detection.bbox_xyxy,
                    )
                )
    return tuple(annotations)


def _boundary_distances_to_raw_fov(
    molecules,
    raw_shape: tuple[int, int],
    pixel_size_nm: tuple[float, float],
) -> tuple[float, ...]:
    height, width = raw_shape
    scale_x, scale_y = pixel_size_nm
    return tuple(
        min(
            molecule.raw_centroid_xy[0] * scale_x,
            (width - molecule.raw_centroid_xy[0]) * scale_x,
            molecule.raw_centroid_xy[1] * scale_y,
            (height - molecule.raw_centroid_xy[1]) * scale_y,
        )
        for molecule in molecules
    )


def _registration_fingerprint(series: MolTrackImageSeries) -> str:
    registration = series.registration_results
    if registration is None:
        return "unregistered"
    return canonical_sha256(
        {
            "reference_frame_index": registration.reference_frame_index,
            "settings": {
                "backend": registration.settings.backend,
                "reference_strategy": registration.settings.reference_strategy,
                "registration_view": registration.settings.registration_view,
                "backend_params": registration.settings.backend_params,
            },
            "frames": tuple(
                {
                    "frame_index": value.frame_index,
                    "shift_xy": value.shift_xy,
                    "method": value.method,
                    "quality_score": value.quality_score,
                    "status": value.status,
                }
                for value in registration.results_by_frame.values()
            ),
        }
    )


def _export_settings(
    owner: QMainWindow,
    series: MolTrackImageSeries,
    physical_frame_ids: tuple[str, ...],
) -> DomainAnalysisExportSettings:
    destination = QFileDialog.getExistingDirectory(
        owner,
        "Export Domain Analysis",
        str(Path(series.source_path).parent),
    )
    if not destination:
        raise ValueError("Domain Analysis export was canceled.")
    source_frame_indices = series.source_frame_indices
    if source_frame_indices is None:
        raise RuntimeError("Image series has no source-frame mapping.")
    return DomainAnalysisExportSettings(
        destination=_available_export_destination(
            Path(destination),
            Path(series.source_path).stem,
        ),
        source_frame_indices=source_frame_indices,
        physical_frame_ids=physical_frame_ids,
        source_identity=CanonicalJsonObject(
            {
                "source_path": series.source_path,
                "source_name": Path(series.source_path).name,
            }
        ),
        m6_settings=CanonicalJsonObject(
            TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET.to_dict()
        ),
    )


def _available_export_destination(parent: Path, source_stem: str) -> Path:
    base = parent / f"{source_stem}-domain-analysis"
    destination = base
    suffix = 2
    while destination.exists():
        destination = parent / f"{base.name}-{suffix}"
        suffix += 1
    return destination


__all__ = ["build_domain_analysis_main_window_composition"]
