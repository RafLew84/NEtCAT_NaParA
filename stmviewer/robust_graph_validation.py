"""Verify saved Huber diagnostics algebraically without rerunning optimization."""
import math
from typing import Callable

import numpy as np

from stmviewer.graph_types import GraphTrial, XY
from stmviewer.robust_graph import measurement_id, validate_robust_config
from stmviewer.robust_graph_types import RobustTrial


def validate_robust_result(graph: GraphTrial, trial: RobustTrial,
                           check_cancelled: Callable[[], None]) -> None:
    check_cancelled()
    if trial.measurement_id != measurement_id(graph):
        raise ValueError('Huber: wynik należy do innego zestawu pomiarów.')
    validate_robust_config(trial.config)
    if trial.status not in ('converged', 'iteration_limit', 'disconnected', 'numerical_failure'):
        raise ValueError('Huber: nieobsługiwany stan zakończenia.')
    if len(trial.weights) != len(graph.edges) or len(trial.residuals) != len(graph.edges):
        raise ValueError('Huber: liczba wag lub reszt nie odpowiada pomiarom.')
    metrics = (trial.objective, trial.ls_objective, trial.max_step_px,
               trial.relative_cost_change, trial.gradient_inf, trial.condition_estimate)
    if (trial.iterations > trial.config.max_iterations or trial.solver_s < 0
            or any(value is not None and value < 0 for value in metrics)):
        raise ValueError('Huber: niespójne liczniki lub miary zakończenia.')
    if trial.condition_estimate is not None and trial.condition_estimate < 1 - 1e-10:
        raise ValueError('Huber: nieprawidłowa miara uwarunkowania.')
    if (graph.positions is None) != (trial.status == 'disconnected'):
        raise ValueError('Huber: stan rozłączenia nie odpowiada grafowi.')
    if trial.last_positions is None:
        if (trial.positions is not None or trial.status not in ('disconnected', 'numerical_failure')
                or trial.iterations != 0 or any(value is not None for value in metrics)
                or any(value is not None for value in (*trial.weights, *trial.residuals))):
            raise ValueError('Huber: diagnostyka bez skończonej iteracji.')
        return
    if graph.positions is None:
        raise ValueError('Huber: odłączone komponenty nie mają wspólnej iteracji.')
    last = trial.last_positions
    if len(last) != len(graph.sources) or last[0] != (0., 0.):
        raise ValueError('Huber: nieprawidłowa kotwica lub liczba pozycji.')
    _validate_diagnostics(graph, trial, last, check_cancelled)
    step_metrics = (trial.max_step_px, trial.relative_cost_change)
    if ((trial.iterations == 0 and any(value is not None for value in step_metrics))
            or (trial.iterations > 0 and any(value is None for value in step_metrics))):
        raise ValueError('Huber: miary kroku nie odpowiadają liczbie ukończonych iteracji.')
    if trial.status in ('converged', 'iteration_limit'):
        if (trial.iterations == 0 or trial.condition_estimate is None
                or trial.condition_estimate > trial.config.max_condition):
            raise ValueError('Huber: zakończona iteracja nie ma poprawnej kontroli uwarunkowania.')
    if trial.status == 'converged':
        if trial.positions != last or not _within_tolerances(trial):
            raise ValueError('Huber: kompletny wynik nie spełnia warunków zakończenia.')
    elif trial.positions is not None:
        raise ValueError('Huber: nieudana próba nie może udostępniać pełnych pozycji.')
    elif trial.status == 'iteration_limit':
        if trial.iterations != trial.config.max_iterations or _within_tolerances(trial):
            raise ValueError('Huber: stan limitu iteracji nie odpowiada zakończeniu.')


def _within_tolerances(trial: RobustTrial) -> bool:
    return (trial.max_step_px is not None and trial.max_step_px <= trial.config.position_tolerance_px
            and trial.relative_cost_change is not None
            and trial.relative_cost_change <= trial.config.objective_relative_tolerance
            and trial.gradient_inf is not None and trial.gradient_inf <= trial.config.gradient_tolerance)


def _consistent(saved: float | None, value: float) -> bool:
    return saved is not None and math.isclose(saved, value, rel_tol=1e-7, abs_tol=1e-9)


def _cost(norm: float, threshold: float) -> float:
    return .5 * norm**2 if norm <= threshold else threshold * (norm - .5 * threshold)


def _validate_diagnostics(graph: GraphTrial, trial: RobustTrial, positions: tuple[XY, ...],
                           check_cancelled: Callable[[], None]) -> None:
    values = np.asarray(positions, dtype=np.float64)
    assert graph.positions is not None
    baseline = np.asarray(graph.positions, dtype=np.float64)
    gradient = np.zeros_like(values)
    cost = initial_cost = 0.
    for edge, residual, weight in zip(graph.edges, trial.residuals, trial.weights, strict=True):
        check_cancelled()
        if edge.shift_xy is None:
            if residual is not None or weight is not None:
                raise ValueError('Huber: brakujący pomiar nie może mieć wagi ani reszty.')
            continue
        calculated = values[edge.j] - values[edge.i] - edge.shift_xy
        if (residual is None or not np.isfinite(calculated).all()
                or not np.allclose(residual, calculated, rtol=1e-7, atol=1e-9)):
            raise ValueError('Huber: reszty nie odpowiadają zapisanej iteracji.')
        norm = math.hypot(float(calculated[0]), float(calculated[1]))
        expected_weight = 1. if norm <= trial.config.threshold_px else trial.config.threshold_px / norm
        if weight is None or not 0 <= weight <= 1 or not _consistent(weight, expected_weight):
            raise ValueError('Huber: jedna waga bloku XY nie odpowiada długości reszty.')
        if trial.status == 'converged' and weight == 0:
            raise ValueError('Huber: kompletny wynik nie może zerować ważnej relacji.')
        gradient[edge.i] -= weight * calculated
        gradient[edge.j] += weight * calculated
        cost += _cost(norm, trial.config.threshold_px)
        ls_residual = baseline[edge.j] - baseline[edge.i] - edge.shift_xy
        initial_cost += _cost(math.hypot(float(ls_residual[0]), float(ls_residual[1])),
                              trial.config.threshold_px)
    norm_gradient = float(np.max(np.abs(gradient[1:])))
    if (not _consistent(trial.objective, cost) or not _consistent(trial.ls_objective, initial_cost)
            or not _consistent(trial.gradient_inf, norm_gradient)):
        raise ValueError('Huber: koszt lub gradient nie odpowiada zapisanej iteracji.')
