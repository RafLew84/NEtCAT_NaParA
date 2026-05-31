"""Optional registration workflow for MolTrack projects."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np

from moltrack.core import MolTrackProject, RegistrationShift
from nanotrack.core import RegistrationFrameResult, RegistrationResultSet, RegistrationSettings
from nanotrack.registration import (
    ExpandedAlignedStack,
    apply_translation_to_frame,
    build_expanded_aligned_frames,
    run_adjacent_phase_registration,
)

MolTrackRegistrationProgressCallback = Callable[[int, int, RegistrationShift], None]
SUPPORTED_MOLTRACK_REGISTRATION_BACKENDS = ("phase_correlation", "optical_flow_median")


def run_project_registration(
    project: MolTrackProject,
    *,
    backend: str = "phase_correlation",
    registration_view: str = "raw",
    backend_params: dict | None = None,
    progress_callback: MolTrackRegistrationProgressCallback | None = None,
) -> MolTrackProject:
    """Run NanoTrack's adjacent global-translation registration on MolTrack working frames."""

    if not isinstance(project, MolTrackProject):
        raise TypeError("project must be a MolTrackProject.")
    if project.source_series.raw_frames is None:
        raise ValueError("Registration requires loaded source image frames.")
    backend = _normalize_registration_backend(backend)

    settings = RegistrationSettings(
        backend=backend,
        reference_strategy="adjacent",
        registration_view=registration_view,
        backend_params=dict(backend_params or {}),
    )
    working_frames = _working_frame_stack(project)

    def _on_progress(done: int, total: int, result: RegistrationFrameResult) -> None:
        if progress_callback is not None:
            progress_callback(done, total, _shift_from_nanotrack_result(result))

    result_set = run_adjacent_phase_registration(
        working_frames,
        settings=settings,
        progress_callback=_on_progress if progress_callback is not None else None,
    )
    registration_shifts = tuple(
        _shift_from_nanotrack_result(result_set.get_result(working_frame.working_frame_index))
        for working_frame in project.working_series.frames
    )
    return project.with_registration_shifts(registration_shifts)


def registered_working_frame(
    project: MolTrackProject,
    working_frame_index: int,
    *,
    interpolation_order: int = 1,
) -> np.ndarray:
    """Materialize one registered working frame as a derived view."""

    if not isinstance(project, MolTrackProject):
        raise TypeError("project must be a MolTrackProject.")
    if project.source_series.raw_frames is None:
        raise ValueError("Registered view requires loaded source image frames.")

    working_frame = project.working_series.get_working_frame(working_frame_index)
    shift = project.registration_shift_for_working_frame(working_frame.working_frame_index)
    if shift is None:
        raise ValueError(f"Missing registration shift for working frame {working_frame.working_frame_index}.")

    native_frame = project.source_series.get_frame(working_frame.source_frame_index)
    return apply_translation_to_frame(
        native_frame,
        shift.shift_xy,
        interpolation_order=interpolation_order,
    )


def registered_working_stack(
    project: MolTrackProject,
    *,
    interpolation_order: int = 1,
) -> np.ndarray:
    """Materialize all registered working frames as a derived stack."""

    frames = [
        registered_working_frame(
            project,
            working_frame.working_frame_index,
            interpolation_order=interpolation_order,
        )
        for working_frame in project.working_series.frames
    ]
    return np.asarray(frames, dtype=np.float32)


def expanded_registered_working_stack(
    project: MolTrackProject,
    *,
    interpolation_order: int = 1,
    fill_value: float | None = None,
) -> ExpandedAlignedStack:
    """Materialize registered working frames on an expanded canvas."""

    if not isinstance(project, MolTrackProject):
        raise TypeError("project must be a MolTrackProject.")
    if project.source_series.raw_frames is None:
        raise ValueError("Expanded registered view requires loaded source image frames.")

    working_frames = _working_frame_stack(project)
    result_set = _registration_result_set_from_project(project)
    fill = _expanded_fill_value(working_frames) if fill_value is None else float(fill_value)
    return build_expanded_aligned_frames(
        working_frames,
        result_set,
        metadata=project.source_series.metadata,
        interpolation_order=interpolation_order,
        fill_value=fill,
    )


def expanded_registered_working_frame(
    project: MolTrackProject,
    working_frame_index: int,
    *,
    interpolation_order: int = 1,
    fill_value: float | None = None,
) -> np.ndarray:
    """Materialize one registered working frame on the expanded canvas."""

    working_frame_index = int(working_frame_index)
    stack = expanded_registered_working_stack(
        project,
        interpolation_order=interpolation_order,
        fill_value=fill_value,
    )
    if not 0 <= working_frame_index < stack.frames.shape[0]:
        raise IndexError("working_frame_index is out of range.")
    return stack.frames[working_frame_index]


def native_to_registered_xy(
    project: MolTrackProject,
    working_frame_index: int,
    xy,
    *,
    require_shift: bool = False,
) -> np.ndarray:
    """Convert native frame point coordinates to registered-view coordinates.

    Missing registration shifts are treated as identity unless ``require_shift`` is set.
    This keeps linking usable when registration is skipped.
    """

    coords = _normalize_xy_array(xy)
    dx, dy = _shift_xy_or_zero(project, working_frame_index, require_shift=require_shift)
    return coords + np.asarray([dx, dy], dtype=np.float64)


def registered_to_native_xy(
    project: MolTrackProject,
    working_frame_index: int,
    xy,
    *,
    require_shift: bool = False,
) -> np.ndarray:
    """Convert registered-view point coordinates back to native frame coordinates."""

    coords = _normalize_xy_array(xy)
    dx, dy = _shift_xy_or_zero(project, working_frame_index, require_shift=require_shift)
    return coords - np.asarray([dx, dy], dtype=np.float64)


def native_bbox_to_registered_xyxy(
    project: MolTrackProject,
    working_frame_index: int,
    bbox_xyxy,
    *,
    require_shift: bool = False,
) -> tuple[float, float, float, float]:
    """Convert a native ``(x0, y0, x1, y1)`` bbox to registered-view coordinates."""

    x0, y0, x1, y1 = _normalize_bbox_xyxy(bbox_xyxy)
    dx, dy = _shift_xy_or_zero(project, working_frame_index, require_shift=require_shift)
    return x0 + dx, y0 + dy, x1 + dx, y1 + dy


def registered_bbox_to_native_xyxy(
    project: MolTrackProject,
    working_frame_index: int,
    bbox_xyxy,
    *,
    require_shift: bool = False,
) -> tuple[float, float, float, float]:
    """Convert a registered-view ``(x0, y0, x1, y1)`` bbox back to native coordinates."""

    x0, y0, x1, y1 = _normalize_bbox_xyxy(bbox_xyxy)
    dx, dy = _shift_xy_or_zero(project, working_frame_index, require_shift=require_shift)
    return x0 - dx, y0 - dy, x1 - dx, y1 - dy


def linking_xy(
    project: MolTrackProject,
    working_frame_index: int,
    native_xy,
    *,
    use_registered: bool = True,
) -> np.ndarray:
    """Return coordinates for optional linking.

    Linking can operate in the registered coordinate system when shifts are available,
    while still falling back to native coordinates when registration is absent.
    """

    if use_registered:
        return native_to_registered_xy(project, working_frame_index, native_xy)
    project.working_series.get_working_frame(working_frame_index)
    return _normalize_xy_array(native_xy)


def _working_frame_stack(project: MolTrackProject) -> np.ndarray:
    frames = [
        project.source_series.get_frame(working_frame.source_frame_index)
        for working_frame in project.working_series.frames
    ]
    return np.asarray(frames, dtype=np.float32)


def _registration_result_set_from_project(project: MolTrackProject) -> RegistrationResultSet:
    if not isinstance(project, MolTrackProject):
        raise TypeError("project must be a MolTrackProject.")
    frame_count = project.working_series.frame_count
    results_by_frame: dict[int, RegistrationFrameResult] = {}
    for working_frame_index in range(frame_count):
        shift = project.registration_shift_for_working_frame(working_frame_index)
        if shift is None:
            raise ValueError(f"Missing registration shift for working frame {working_frame_index}.")
        results_by_frame[working_frame_index] = RegistrationFrameResult(
            frame_index=working_frame_index,
            shift_xy=shift.shift_xy,
            method=shift.method,
            quality_score=1.0,
            status="ok",
        )
    return RegistrationResultSet(
        settings=RegistrationSettings(
            backend=_backend_from_registration_shifts(project.registration_shifts),
            reference_strategy="adjacent",
            registration_view="raw",
        ),
        results_by_frame=results_by_frame,
        reference_frame_index=0,
        template_frame_indices=(0,),
    )


def _shift_from_nanotrack_result(result: RegistrationFrameResult) -> RegistrationShift:
    return RegistrationShift(
        working_frame_index=result.frame_index,
        dx=result.dx,
        dy=result.dy,
        method=result.method,
    )


def _shift_xy_or_zero(
    project: MolTrackProject,
    working_frame_index: int,
    *,
    require_shift: bool,
) -> tuple[float, float]:
    if not isinstance(project, MolTrackProject):
        raise TypeError("project must be a MolTrackProject.")
    shift = project.registration_shift_for_working_frame(working_frame_index)
    if shift is None:
        if require_shift:
            raise ValueError(f"Missing registration shift for working frame {int(working_frame_index)}.")
        return 0.0, 0.0
    return shift.shift_xy


def _normalize_registration_backend(backend: str) -> str:
    normalized = str(backend).strip().lower()
    if normalized not in SUPPORTED_MOLTRACK_REGISTRATION_BACKENDS:
        supported = ", ".join(SUPPORTED_MOLTRACK_REGISTRATION_BACKENDS)
        raise ValueError(f"Unsupported MolTrack registration backend: {backend!r}. Supported: {supported}.")
    return normalized


def _backend_from_registration_shifts(registration_shifts: tuple[RegistrationShift, ...]) -> str:
    methods = {shift.method for shift in registration_shifts}
    if any("optical_flow_median" in method for method in methods):
        return "optical_flow_median"
    return "phase_correlation"


def _expanded_fill_value(frames: np.ndarray) -> float:
    stack = np.asarray(frames, dtype=np.float32)
    if stack.size == 0:
        return 0.0
    return float(np.min(stack))


def _normalize_xy_array(xy) -> np.ndarray:
    coords = np.asarray(xy, dtype=np.float64)
    if coords.shape == (2,):
        if not np.all(np.isfinite(coords)):
            raise ValueError("xy coordinates must be finite.")
        return coords.copy()
    if coords.ndim == 2 and coords.shape[1] == 2:
        if not np.all(np.isfinite(coords)):
            raise ValueError("xy coordinates must be finite.")
        return coords.copy()
    raise ValueError("xy must have shape (2,) or (N, 2).")


def _normalize_bbox_xyxy(bbox_xyxy) -> tuple[float, float, float, float]:
    bbox = tuple(float(value) for value in bbox_xyxy)
    if len(bbox) != 4:
        raise ValueError("bbox_xyxy must contain exactly four values.")
    if not np.all(np.isfinite(bbox)):
        raise ValueError("bbox_xyxy values must be finite.")
    x0, y0, x1, y1 = bbox
    if x1 <= x0 or y1 <= y0:
        raise ValueError("bbox_xyxy must have positive width and height.")
    return x0, y0, x1, y1
