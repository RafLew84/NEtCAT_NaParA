"""Global graph optimization for translation-only registration shifts."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from nanotrack.core import (
    RegistrationFrameResult,
    RegistrationResultSet,
    RegistrationSettings,
)


class GlobalShiftGraphOptimizerError(RuntimeError):
    """Raised when global shift graph optimization cannot produce a usable trajectory."""


@dataclass(frozen=True)
class PairwiseShiftMeasurement:
    """One graph edge with equation S_moving - S_reference = shift_xy."""

    reference_index: int
    moving_index: int
    shift_xy: tuple[float, float] | np.ndarray
    weight: float = 1.0
    method: str = "pairwise_shift"
    quality_score: float = 1.0

    def __post_init__(self) -> None:
        reference_index = int(self.reference_index)
        moving_index = int(self.moving_index)
        if reference_index < 0 or moving_index < 0:
            raise ValueError("measurement frame indices must be non-negative.")
        if reference_index == moving_index:
            raise ValueError("reference_index and moving_index must be different.")
        object.__setattr__(self, "reference_index", reference_index)
        object.__setattr__(self, "moving_index", moving_index)

        shift = np.asarray(self.shift_xy, dtype=np.float64)
        if shift.shape != (2,) or not np.all(np.isfinite(shift)):
            raise ValueError("shift_xy must contain exactly two finite values: dx, dy.")
        object.__setattr__(self, "shift_xy", (float(shift[0]), float(shift[1])))

        weight = float(self.weight)
        if not np.isfinite(weight) or weight <= 0.0:
            raise ValueError("weight must be a finite positive value.")
        object.__setattr__(self, "weight", weight)

        method = str(self.method).strip()
        if not method:
            raise ValueError("method must be a non-empty string.")
        object.__setattr__(self, "method", method)

        quality_score = float(self.quality_score)
        if not np.isfinite(quality_score) or not 0.0 <= quality_score <= 1.0:
            raise ValueError("quality_score must be in [0, 1].")
        object.__setattr__(self, "quality_score", quality_score)


@dataclass(frozen=True)
class GlobalShiftGraphOptimizerConfig:
    """Runtime configuration for global shift graph optimization."""

    reference_frame_index: int = 0
    smoothness_lambda: float = 0.0
    huber_delta_px: float | None = None
    robust_iterations: int = 1
    low_confidence_residual_px: float = 1.0
    min_measurements: int = 1

    def __post_init__(self) -> None:
        reference_frame_index = int(self.reference_frame_index)
        if reference_frame_index < 0:
            raise ValueError("reference_frame_index must be non-negative.")
        object.__setattr__(self, "reference_frame_index", reference_frame_index)

        smoothness_lambda = float(self.smoothness_lambda)
        if not np.isfinite(smoothness_lambda) or smoothness_lambda < 0.0:
            raise ValueError("smoothness_lambda must be a finite non-negative value.")
        object.__setattr__(self, "smoothness_lambda", smoothness_lambda)

        huber_delta_px = self.huber_delta_px
        if huber_delta_px is not None:
            huber_delta_px = float(huber_delta_px)
            if not np.isfinite(huber_delta_px) or huber_delta_px <= 0.0:
                raise ValueError("huber_delta_px must be None or a finite positive value.")
        object.__setattr__(self, "huber_delta_px", huber_delta_px)

        robust_iterations = int(self.robust_iterations)
        if robust_iterations <= 0:
            raise ValueError("robust_iterations must be positive.")
        object.__setattr__(self, "robust_iterations", robust_iterations)

        low_confidence_residual_px = float(self.low_confidence_residual_px)
        if not np.isfinite(low_confidence_residual_px) or low_confidence_residual_px < 0.0:
            raise ValueError("low_confidence_residual_px must be a finite non-negative value.")
        object.__setattr__(self, "low_confidence_residual_px", low_confidence_residual_px)

        min_measurements = int(self.min_measurements)
        if min_measurements <= 0:
            raise ValueError("min_measurements must be positive.")
        object.__setattr__(self, "min_measurements", min_measurements)


class GlobalShiftGraphOptimizer:
    """Solve global per-frame translations from pairwise shift measurements."""

    method_name = "global_shift_graph"

    def __init__(self, config: GlobalShiftGraphOptimizerConfig | None = None):
        self.config = config or GlobalShiftGraphOptimizerConfig()

    def optimize(
        self,
        *,
        frame_count: int,
        measurements: list[PairwiseShiftMeasurement] | tuple[PairwiseShiftMeasurement, ...],
        settings: RegistrationSettings | None = None,
    ) -> RegistrationResultSet:
        """Return globally optimized shifts with the configured reference frame anchored at zero."""

        frame_count = int(frame_count)
        if frame_count <= 0:
            raise ValueError("frame_count must be positive.")
        reference_index = self.config.reference_frame_index
        if reference_index >= frame_count:
            raise ValueError("reference_frame_index must be within frame_count.")

        normalized_measurements = [self._ensure_measurement(measurement) for measurement in measurements]
        if len(normalized_measurements) < self.config.min_measurements:
            raise GlobalShiftGraphOptimizerError(
                f"Need at least {self.config.min_measurements} pairwise shift measurements."
            )
        self._validate_measurement_indices(normalized_measurements, frame_count)
        self._require_connected_to_reference(normalized_measurements, frame_count, reference_index)

        shifts = self._solve_global_shifts(frame_count, normalized_measurements, reference_index)
        residuals = self._measurement_residuals(shifts, normalized_measurements)
        frame_residuals = self._residuals_by_frame(frame_count, normalized_measurements, residuals)
        results = self._build_results(shifts, frame_residuals)
        return RegistrationResultSet(
            settings=settings or self._default_settings(),
            results_by_frame=results,
            reference_frame_index=reference_index,
            template_frame_indices=(reference_index,),
        )

    def optimize_result_set(
        self,
        result_set: RegistrationResultSet,
        *,
        settings: RegistrationSettings | None = None,
    ) -> RegistrationResultSet:
        """Optimize a cumulative result set by converting consecutive shifts to graph edges."""

        if not isinstance(result_set, RegistrationResultSet):
            raise TypeError("result_set must be a RegistrationResultSet instance.")
        frame_indices = result_set.frame_indices
        if not frame_indices:
            raise GlobalShiftGraphOptimizerError("result_set must contain at least one frame result.")
        frame_count = max(frame_indices) + 1
        existing_shifts = {
            frame_index: np.asarray(result_set.get_result(frame_index).shift_xy, dtype=np.float64)
            for frame_index in frame_indices
        }
        measurements: list[PairwiseShiftMeasurement] = []
        for reference_index, moving_index in zip(frame_indices[:-1], frame_indices[1:]):
            reference_result = result_set.get_result(reference_index)
            moving_result = result_set.get_result(moving_index)
            if reference_result is None or moving_result is None:
                raise GlobalShiftGraphOptimizerError("result_set contains missing frame results.")
            shift_xy = existing_shifts[moving_index] - existing_shifts[reference_index]
            measurements.append(
                PairwiseShiftMeasurement(
                    reference_index=reference_index,
                    moving_index=moving_index,
                    shift_xy=shift_xy,
                    weight=max(min(reference_result.quality_score, moving_result.quality_score), 1e-6),
                    method=moving_result.method,
                    quality_score=moving_result.quality_score,
                )
            )
        if not measurements and frame_count == 1:
            return RegistrationResultSet(
                settings=settings or self._default_settings(source_backend=result_set.settings.backend),
                results_by_frame={
                    frame_indices[0]: RegistrationFrameResult(
                        frame_index=frame_indices[0],
                        shift_xy=(0.0, 0.0),
                        method="identity",
                        quality_score=1.0,
                        status="ok",
                    )
                },
                reference_frame_index=self.config.reference_frame_index,
                template_frame_indices=(self.config.reference_frame_index,),
            )
        return self.optimize(
            frame_count=frame_count,
            measurements=measurements,
            settings=settings or self._default_settings(source_backend=result_set.settings.backend),
        )

    def _solve_global_shifts(
        self,
        frame_count: int,
        measurements: list[PairwiseShiftMeasurement],
        reference_index: int,
    ) -> np.ndarray:
        active_weights = np.asarray([measurement.weight for measurement in measurements], dtype=np.float64)
        shifts = np.zeros((frame_count, 2), dtype=np.float64)
        iterations = self.config.robust_iterations if self.config.huber_delta_px is not None else 1
        for _iteration in range(iterations):
            shifts = self._solve_weighted_least_squares(
                frame_count,
                measurements,
                reference_index,
                active_weights,
            )
            if self.config.huber_delta_px is None:
                break
            residual_norms = np.linalg.norm(self._measurement_residuals(shifts, measurements), axis=1)
            robust_factors = np.ones_like(residual_norms)
            outliers = residual_norms > self.config.huber_delta_px
            robust_factors[outliers] = self.config.huber_delta_px / residual_norms[outliers]
            base_weights = np.asarray([measurement.weight for measurement in measurements], dtype=np.float64)
            active_weights = np.maximum(base_weights * robust_factors, 1e-12)
        return shifts

    def _solve_weighted_least_squares(
        self,
        frame_count: int,
        measurements: list[PairwiseShiftMeasurement],
        reference_index: int,
        weights: np.ndarray,
    ) -> np.ndarray:
        variable_indices = self._variable_indices(frame_count, reference_index)
        rows: list[np.ndarray] = []
        rhs_xy: list[np.ndarray] = []
        for measurement, weight in zip(measurements, weights):
            row = np.zeros(len(variable_indices), dtype=np.float64)
            if measurement.reference_index != reference_index:
                row[variable_indices[measurement.reference_index]] -= 1.0
            if measurement.moving_index != reference_index:
                row[variable_indices[measurement.moving_index]] += 1.0
            scale = float(np.sqrt(weight))
            rows.append(row * scale)
            rhs_xy.append(np.asarray(measurement.shift_xy, dtype=np.float64) * scale)

        if self.config.smoothness_lambda > 0.0 and frame_count >= 3:
            scale = float(np.sqrt(self.config.smoothness_lambda))
            for frame_index in range(1, frame_count - 1):
                row = np.zeros(len(variable_indices), dtype=np.float64)
                for index, coefficient in (
                    (frame_index - 1, 1.0),
                    (frame_index, -2.0),
                    (frame_index + 1, 1.0),
                ):
                    if index != reference_index:
                        row[variable_indices[index]] += coefficient
                if np.any(row):
                    rows.append(row * scale)
                    rhs_xy.append(np.zeros(2, dtype=np.float64))

        if not rows:
            raise GlobalShiftGraphOptimizerError("No usable graph equations were generated.")
        matrix = np.vstack(rows)
        rhs = np.vstack(rhs_xy)
        if matrix.shape[1] == 0:
            return np.zeros((frame_count, 2), dtype=np.float64)

        solution_x, *_ = np.linalg.lstsq(matrix, rhs[:, 0], rcond=None)
        solution_y, *_ = np.linalg.lstsq(matrix, rhs[:, 1], rcond=None)
        if not np.all(np.isfinite(solution_x)) or not np.all(np.isfinite(solution_y)):
            raise GlobalShiftGraphOptimizerError("Global graph optimization returned non-finite shifts.")

        shifts = np.zeros((frame_count, 2), dtype=np.float64)
        for frame_index, variable_index in variable_indices.items():
            shifts[frame_index, 0] = float(solution_x[variable_index])
            shifts[frame_index, 1] = float(solution_y[variable_index])
        shifts[reference_index] = (0.0, 0.0)
        return shifts

    def _build_results(
        self,
        shifts: np.ndarray,
        frame_residuals: list[list[float]],
    ) -> dict[int, RegistrationFrameResult]:
        results: dict[int, RegistrationFrameResult] = {}
        for frame_index, shift_xy in enumerate(shifts):
            residual_values = frame_residuals[frame_index]
            median_residual = float(np.median(residual_values)) if residual_values else 0.0
            quality_score = float(np.clip(1.0 / (1.0 + median_residual), 0.0, 1.0))
            status = (
                "ok"
                if median_residual <= self.config.low_confidence_residual_px
                else "low_confidence"
            )
            method = "identity" if frame_index == self.config.reference_frame_index else self.method_name
            results[frame_index] = RegistrationFrameResult(
                frame_index=frame_index,
                shift_xy=(float(shift_xy[0]), float(shift_xy[1])),
                method=method,
                quality_score=quality_score,
                status=status,
            )
        return results

    @staticmethod
    def _measurement_residuals(
        shifts: np.ndarray,
        measurements: list[PairwiseShiftMeasurement],
    ) -> np.ndarray:
        residuals = []
        for measurement in measurements:
            predicted = shifts[measurement.moving_index] - shifts[measurement.reference_index]
            residuals.append(predicted - np.asarray(measurement.shift_xy, dtype=np.float64))
        return np.asarray(residuals, dtype=np.float64).reshape((-1, 2))

    @staticmethod
    def _residuals_by_frame(
        frame_count: int,
        measurements: list[PairwiseShiftMeasurement],
        residuals: np.ndarray,
    ) -> list[list[float]]:
        by_frame: list[list[float]] = [[] for _ in range(frame_count)]
        for measurement, residual in zip(measurements, residuals):
            residual_norm = float(np.linalg.norm(residual))
            by_frame[measurement.reference_index].append(residual_norm)
            by_frame[measurement.moving_index].append(residual_norm)
        return by_frame

    @staticmethod
    def _variable_indices(frame_count: int, reference_index: int) -> dict[int, int]:
        indices: dict[int, int] = {}
        for frame_index in range(frame_count):
            if frame_index == reference_index:
                continue
            indices[frame_index] = len(indices)
        return indices

    @staticmethod
    def _ensure_measurement(measurement: PairwiseShiftMeasurement) -> PairwiseShiftMeasurement:
        if not isinstance(measurement, PairwiseShiftMeasurement):
            raise TypeError("measurements must contain PairwiseShiftMeasurement instances.")
        return measurement

    @staticmethod
    def _validate_measurement_indices(
        measurements: list[PairwiseShiftMeasurement],
        frame_count: int,
    ) -> None:
        for measurement in measurements:
            if measurement.reference_index >= frame_count or measurement.moving_index >= frame_count:
                raise ValueError("measurement frame indices must be within frame_count.")

    @staticmethod
    def _require_connected_to_reference(
        measurements: list[PairwiseShiftMeasurement],
        frame_count: int,
        reference_index: int,
    ) -> None:
        adjacency: list[set[int]] = [set() for _ in range(frame_count)]
        for measurement in measurements:
            adjacency[measurement.reference_index].add(measurement.moving_index)
            adjacency[measurement.moving_index].add(measurement.reference_index)
        visited = {reference_index}
        pending = [reference_index]
        while pending:
            current = pending.pop()
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    pending.append(neighbor)
        if len(visited) != frame_count:
            raise GlobalShiftGraphOptimizerError("Shift measurement graph must connect every frame to reference.")

    def _default_settings(self, *, source_backend: str | None = None) -> RegistrationSettings:
        backend_params: dict[str, object] = {
            "smoothness_lambda": self.config.smoothness_lambda,
            "huber_delta_px": self.config.huber_delta_px,
            "robust_iterations": self.config.robust_iterations,
            "low_confidence_residual_px": self.config.low_confidence_residual_px,
            "min_measurements": self.config.min_measurements,
        }
        if source_backend is not None:
            backend_params["source_backend"] = source_backend
        return RegistrationSettings(
            backend=self.method_name,
            reference_strategy="global_graph",
            registration_view="derived_shifts",
            backend_params=backend_params,
        )
