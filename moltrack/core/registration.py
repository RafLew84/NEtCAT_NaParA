from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from nanotrack.core import (
    RegistrationFrameResult as NanoRegistrationFrameResult,
    RegistrationResultSet as NanoRegistrationResultSet,
    RegistrationSettings as NanoRegistrationSettings,
)
from nanotrack.registration import ExpandedAlignedStack, build_expanded_aligned_frames, run_adjacent_phase_registration

from .data_models import MolTrackImageSeries


SUPPORTED_REGISTRATION_BACKENDS = ("phase_correlation", "optical_flow_median")


@dataclass(frozen=True)
class MolTrackRegistrationSettings:
    """MolTrack registration settings backed by NanoTrack low-level registration."""

    backend: str = "phase_correlation"
    reference_strategy: str = "adjacent"
    registration_view: str = "raw"
    backend_params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        backend = str(self.backend).strip()
        reference_strategy = str(self.reference_strategy).strip()
        registration_view = str(self.registration_view).strip()
        if backend not in SUPPORTED_REGISTRATION_BACKENDS:
            supported = ", ".join(SUPPORTED_REGISTRATION_BACKENDS)
            raise ValueError(f"Unsupported MolTrack registration backend: {backend!r}. Supported: {supported}.")
        if reference_strategy != "adjacent":
            raise ValueError("MolTrack registration currently supports reference_strategy='adjacent'.")
        if not registration_view:
            raise ValueError("registration_view must be a non-empty string.")
        object.__setattr__(self, "backend", backend)
        object.__setattr__(self, "reference_strategy", reference_strategy)
        object.__setattr__(self, "registration_view", registration_view)
        object.__setattr__(self, "backend_params", dict(self.backend_params))

    def to_nanotrack_settings(self) -> NanoRegistrationSettings:
        return NanoRegistrationSettings(
            backend=self.backend,
            reference_strategy=self.reference_strategy,
            registration_view=self.registration_view,
            backend_params=dict(self.backend_params),
        )


@dataclass(frozen=True)
class MolTrackRegistrationFrameResult:
    """One MolTrack translation result for a working-series frame."""

    frame_index: int
    shift_xy: tuple[float, float]
    method: str
    quality_score: float = 0.0
    status: str = "ok"

    def __post_init__(self) -> None:
        frame_index = int(self.frame_index)
        if frame_index < 0:
            raise ValueError("frame_index must be non-negative.")
        shift = np.asarray(self.shift_xy, dtype=np.float64)
        if shift.shape != (2,) or not np.all(np.isfinite(shift)):
            raise ValueError("shift_xy must contain two finite values.")
        method = str(self.method).strip()
        if not method:
            raise ValueError("method must be a non-empty string.")
        quality_score = float(self.quality_score)
        if not np.isfinite(quality_score):
            raise ValueError("quality_score must be finite.")
        object.__setattr__(self, "frame_index", frame_index)
        object.__setattr__(self, "shift_xy", (float(shift[0]), float(shift[1])))
        object.__setattr__(self, "method", method)
        object.__setattr__(self, "quality_score", quality_score)
        object.__setattr__(self, "status", str(self.status).strip() or "ok")

    @property
    def dx(self) -> float:
        return float(self.shift_xy[0])

    @property
    def dy(self) -> float:
        return float(self.shift_xy[1])

    @classmethod
    def from_nanotrack(cls, result: NanoRegistrationFrameResult) -> "MolTrackRegistrationFrameResult":
        return cls(
            frame_index=result.frame_index,
            shift_xy=result.shift_xy,
            method=result.method,
            quality_score=result.quality_score,
            status=result.status,
        )


@dataclass(frozen=True)
class MolTrackRegistrationResultSet:
    """Registration results for the current MolTrack working image series."""

    settings: MolTrackRegistrationSettings
    results_by_frame: dict[int, MolTrackRegistrationFrameResult] = field(default_factory=dict)
    reference_frame_index: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.settings, MolTrackRegistrationSettings):
            raise TypeError("settings must be a MolTrackRegistrationSettings instance.")
        reference_frame_index = int(self.reference_frame_index)
        if reference_frame_index < 0:
            raise ValueError("reference_frame_index must be non-negative.")
        normalized: dict[int, MolTrackRegistrationFrameResult] = {}
        for frame_index, result in self.results_by_frame.items():
            key = int(frame_index)
            if not isinstance(result, MolTrackRegistrationFrameResult):
                raise TypeError("results_by_frame values must be MolTrackRegistrationFrameResult instances.")
            if result.frame_index != key:
                raise ValueError("results_by_frame keys must match result.frame_index.")
            normalized[key] = result
        object.__setattr__(self, "reference_frame_index", reference_frame_index)
        object.__setattr__(self, "results_by_frame", dict(sorted(normalized.items())))

    @property
    def frame_indices(self) -> tuple[int, ...]:
        return tuple(self.results_by_frame.keys())

    @property
    def result_count(self) -> int:
        return len(self.results_by_frame)

    def get_result(self, frame_index: int) -> MolTrackRegistrationFrameResult | None:
        return self.results_by_frame.get(int(frame_index))

    def shifts_xy_array(self) -> np.ndarray:
        return np.asarray([self.results_by_frame[index].shift_xy for index in self.frame_indices], dtype=np.float64)

    def to_nanotrack_result_set(self) -> NanoRegistrationResultSet:
        nano_settings = self.settings.to_nanotrack_settings()
        return NanoRegistrationResultSet(
            settings=nano_settings,
            results_by_frame={
                frame_index: NanoRegistrationFrameResult(
                    frame_index=result.frame_index,
                    shift_xy=result.shift_xy,
                    method=result.method,
                    quality_score=result.quality_score,
                    status=result.status,
                )
                for frame_index, result in self.results_by_frame.items()
            },
            reference_frame_index=self.reference_frame_index,
        )

    @classmethod
    def from_nanotrack(
        cls,
        result_set: NanoRegistrationResultSet,
        *,
        settings: MolTrackRegistrationSettings,
    ) -> "MolTrackRegistrationResultSet":
        return cls(
            settings=settings,
            results_by_frame={
                frame_index: MolTrackRegistrationFrameResult.from_nanotrack(result)
                for frame_index, result in result_set.results_by_frame.items()
            },
            reference_frame_index=result_set.reference_frame_index,
        )


RegistrationRunner = Callable[..., NanoRegistrationResultSet]


def run_moltrack_registration(
    series: MolTrackImageSeries,
    *,
    settings: MolTrackRegistrationSettings | None = None,
    registration_runner: RegistrationRunner = run_adjacent_phase_registration,
    progress_callback: Any | None = None,
) -> MolTrackRegistrationResultSet:
    """Run translation registration on the current MolTrack working frames."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    if series.frame_count < 2:
        raise ValueError("registration requires at least two frames.")

    moltrack_settings = settings or MolTrackRegistrationSettings()
    nano_result_set = registration_runner(
        series.raw_frames,
        settings=moltrack_settings.to_nanotrack_settings(),
        progress_callback=progress_callback,
    )
    result_set = MolTrackRegistrationResultSet.from_nanotrack(
        nano_result_set,
        settings=moltrack_settings,
    )
    _validate_result_set_matches_working_frames(result_set, frame_count=series.frame_count)
    series.registration_results = result_set
    series.expanded_aligned_stack = None
    return result_set


def build_moltrack_expanded_aligned_stack(
    series: MolTrackImageSeries,
    *,
    interpolation_order: int = 1,
    fill_value: float = np.nan,
) -> ExpandedAlignedStack:
    """Materialize the current registration on an expanded canvas."""

    if not isinstance(series, MolTrackImageSeries):
        raise TypeError("series must be a MolTrackImageSeries instance.")
    if series.registration_results is None:
        raise RuntimeError("expanded aligned stack requires registration results.")
    _validate_result_set_matches_working_frames(series.registration_results, frame_count=series.frame_count)

    expanded = build_expanded_aligned_frames(
        series.raw_frames,
        series.registration_results.to_nanotrack_result_set(),
        metadata=series.metadata,
        interpolation_order=interpolation_order,
        fill_value=fill_value,
    )
    series.expanded_aligned_stack = expanded
    return expanded


def _validate_result_set_matches_working_frames(
    result_set: MolTrackRegistrationResultSet,
    *,
    frame_count: int,
) -> None:
    expected = tuple(range(int(frame_count)))
    if result_set.frame_indices != expected:
        raise ValueError("registration results do not match working frame count.")
