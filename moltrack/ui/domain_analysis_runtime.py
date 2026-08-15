from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from queue import Empty, Queue
from threading import Lock, Thread
from typing import Literal

import numpy as np
from PyQt6.QtWidgets import QFileDialog, QMainWindow

from moltrack.analysis import TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
from moltrack.analysis.domain_analysis import (
    ABC_ORIENTATION_CLASSIFIER_ID,
    M6_ORIENTATION_COMPONENTS_BACKEND_ID,
    ClassifierConfiguration,
    ClassifierIdentity,
    DomainAnalysisFrame,
    DomainAnalysisModule,
    DomainAnalysisPublication,
    DomainAnalysisRequest,
    DomainAnalysisSeries,
    DomainAnalysisWorkspaceController,
    DomainAnalysisWorkspaceExecution,
    M6FrameGeometry,
    M6SourceAnnotation,
    M6Preset,
    M6PresetLibrary,
    TextureABCClassifierAdapter,
)
from moltrack.analysis.domain_analysis.fingerprints import canonical_sha256
from moltrack.core import (
    MolTrackImageSeries,
    build_moltrack_expanded_aligned_stack,
)
from moltrack.persistence import (
    CanonicalJsonObject,
    CorrectionAwareExportSettings,
    DomainAnalysisExportSettings,
)
from moltrack.ui.domain_analysis_composition import (
    DomainAnalysisMainWindowComposition,
)
from moltrack.ui.domain_analysis_release_workflow import (
    DomainAnalysisReleaseWorkflow,
)
from moltrack.ui.domain_backend_adapters import (
    MolTrackLatticeNetworkAdapter,
    MolTrackOrientationComponentsAdapter,
)

_MolTrackM6Adapter = MolTrackOrientationComponentsAdapter


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


def build_domain_analysis_main_window_composition(
    owner: QMainWindow,
    series: MolTrackImageSeries,
) -> DomainAnalysisMainWindowComposition:
    analysis_series = _domain_analysis_series(series)
    classifier = TextureABCClassifierAdapter()
    adapters = (
        MolTrackOrientationComponentsAdapter(analysis_series),
        MolTrackLatticeNetworkAdapter(analysis_series),
    )
    preset_library = _m6_preset_library(adapters)
    active_configuration = preset_library.active_run_configuration()
    module = DomainAnalysisModule(
        {value.backend_identity.backend_id: value for value in adapters},
        {ABC_ORIENTATION_CLASSIFIER_ID: classifier},
    )
    physical_frame_ids = tuple(
        frame.geometry.physical_frame_id for frame in analysis_series.frames
    )
    controller = DomainAnalysisWorkspaceController(
        DomainAnalysisRequest(
            frame_range=range(series.frame_count),
            backend_id=active_configuration.backend_id,
            classifier_ids=(ABC_ORIENTATION_CLASSIFIER_ID,),
            m6_configuration=active_configuration,
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
    release_workflow = _release_workflow(owner)
    composition_holder: list[DomainAnalysisMainWindowComposition] = []

    def current_workspace():
        if not composition_holder:
            raise RuntimeError("Domain Analysis composition is not ready.")
        return (
            composition_holder[0].session_state(),
            series,
            analysis_series,
            preset_library,
        )

    workflow_actions = release_workflow.actions(
        current_workspace,
        save_session=lambda: _trigger_owner_action(owner, "action_save_state"),
        open_session=lambda: _trigger_owner_action(owner, "action_open_state"),
    )
    settings_args = (owner, series, physical_frame_ids)
    export_settings_for = partial(_export_settings, *settings_args)
    audit_export_settings_for = partial(_audit_export_settings, owner, series)
    legacy_export_settings_for = partial(_legacy_export_settings, *settings_args)
    composition = DomainAnalysisMainWindowComposition(
        owner,
        controller,
        session_series=series,
        classifier_configurations=(configuration,),
        m6_preset_name="TTMAPP M6 approved",
        m6_preset_library=preset_library,
        classifier_preset_name="TTMAPP M6-gated A/B/C",
        workflow_actions=workflow_actions,
        export_settings_for=export_settings_for,
        audit_export_settings_for=audit_export_settings_for,
        legacy_export_settings_for=legacy_export_settings_for,
    )
    composition_holder.append(composition)
    return composition


def _release_workflow(owner: QMainWindow) -> DomainAnalysisReleaseWorkflow:
    attribute = "_moltrack_domain_analysis_release_workflow"
    workflow = getattr(owner, attribute, None)
    if workflow is None:
        workflow = DomainAnalysisReleaseWorkflow(owner)
        setattr(owner, attribute, workflow)
    if not isinstance(workflow, DomainAnalysisReleaseWorkflow):
        raise TypeError(f"{attribute} must be a DomainAnalysisReleaseWorkflow.")
    return workflow


def _trigger_owner_action(owner: QMainWindow, name: str) -> None:
    action = getattr(owner, name, None)
    if action is None or not callable(getattr(action, "trigger", None)):
        raise RuntimeError(f"Main window does not provide {name}.")
    if not action.isEnabled():
        raise RuntimeError(f"Main window action {name} is disabled.")
    action.trigger()


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
    publication: DomainAnalysisPublication | None = None,
) -> CorrectionAwareExportSettings:
    del physical_frame_ids, publication
    return _correction_aware_export_settings(
        owner,
        series,
        title="Export Domain Analysis",
        format_suffix="",
        export_mode="reference",
    )


def _audit_export_settings(
    owner: QMainWindow,
    series: MolTrackImageSeries,
) -> CorrectionAwareExportSettings:
    return _correction_aware_export_settings(
        owner,
        series,
        title="Export audit-only Domain Analysis v10",
        format_suffix="-audit-v10",
        export_mode="audit",
    )


def _correction_aware_export_settings(
    owner: QMainWindow,
    series: MolTrackImageSeries,
    *,
    title: str,
    format_suffix: str,
    export_mode: Literal["reference", "audit"],
) -> CorrectionAwareExportSettings:
    destination = QFileDialog.getExistingDirectory(
        owner,
        title,
        str(Path(series.source_path).parent),
    )
    if not destination:
        raise ValueError("Domain Analysis export was canceled.")
    return CorrectionAwareExportSettings(
        destination=_available_export_destination(
            Path(destination),
            Path(series.source_path).stem,
            format_suffix=format_suffix,
        ),
        source_identity=_source_identity_for(series),
        export_mode=export_mode,
    )


def _published_m6_settings(
    publication: DomainAnalysisPublication | None,
) -> dict[str, object]:
    configuration = (
        None if publication is None else publication.request.m6_configuration
    )
    settings = (
        TTMAPP_M6_ORIENTATION_ANALYSIS_PRESET
        if configuration is None
        else configuration.settings
    )
    return dict(settings.to_dict())


def _legacy_export_settings(
    owner: QMainWindow,
    series: MolTrackImageSeries,
    physical_frame_ids: tuple[str, ...],
    publication: DomainAnalysisPublication,
) -> DomainAnalysisExportSettings:
    destination = QFileDialog.getExistingDirectory(
        owner,
        "Export legacy automatic-only Domain Analysis v9",
        str(Path(series.source_path).parent),
    )
    if not destination:
        raise ValueError("Legacy Domain Analysis export was canceled.")
    source_frame_indices = series.source_frame_indices
    if source_frame_indices is None:
        raise RuntimeError("Image series has no source-frame mapping.")
    return DomainAnalysisExportSettings(
        destination=_available_export_destination(
            Path(destination),
            Path(series.source_path).stem,
            format_suffix="-legacy-v9",
        ),
        source_frame_indices=source_frame_indices,
        physical_frame_ids=physical_frame_ids,
        source_identity=_source_identity_for(series),
        m6_settings=CanonicalJsonObject(_published_m6_settings(publication)),
    )


def _source_identity_for(series: MolTrackImageSeries) -> CanonicalJsonObject:
    return CanonicalJsonObject({
        "source_path": series.source_path,
        "source_name": Path(series.source_path).name,
    })


def _m6_preset_library(adapters) -> M6PresetLibrary:
    created_at = datetime(2026, 8, 13, tzinfo=timezone.utc)
    presets = tuple(
        M6Preset(
            name=(
                "TTMAPP M6 Orientation Components"
                if adapter.backend_identity.backend_id
                == M6_ORIENTATION_COMPONENTS_BACKEND_ID
                else "TTMAPP M3/M6 Lattice Network"
            ),
            description="Shipped MolTrack default",
            configuration=adapter.default_run_configuration(),
            created_at=created_at,
            updated_at=created_at,
            built_in=True,
        )
        for adapter in adapters
    )
    return M6PresetLibrary(
        Path.home() / ".moltrack" / "m6-presets.json",
        built_in_presets=presets,
    )


def _available_export_destination(
    parent: Path,
    source_stem: str,
    *,
    format_suffix: str = "",
) -> Path:
    base = parent / f"{source_stem}-domain-analysis{format_suffix}"
    destination = base
    suffix = 2
    while destination.exists():
        destination = parent / f"{base.name}-{suffix}"
        suffix += 1
    return destination


__all__ = ["build_domain_analysis_main_window_composition"]
