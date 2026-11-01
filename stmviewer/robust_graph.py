"""Block-Huber IRLS on saved translation measurements, never on image pixels."""
from __future__ import annotations
from hashlib import sha256
import json
import math
from time import perf_counter
from typing import Callable, TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from stmviewer.graph_types import GraphTrial, XY
from stmviewer.graph_validation import validate_graph_result
from stmviewer.registration import RegistrationCancelled, RegistrationError
from stmviewer.robust_graph_types import RobustConfig, RobustTrial

if TYPE_CHECKING:
    from scipy.sparse import csr_matrix


def measurement_id(graph: GraphTrial) -> str:
    """Portable identity: current measurement revision, pixel identities and raw edges.

    Native path spellings, LS residuals and robust attempts are intentionally absent;
    loading on another operating system must not change this common measurement ID.
    """
    record = {
        'revision': graph.revision, 'anchor': graph.anchor,
        'sources': [(s.source_frame_index, s.shape, s.pixels_sha256) for s in graph.sources],
        'edges': [(e.i, e.j, e.shift_xy, e.status, e.reason, e.quality_score) for e in graph.edges],
    }
    payload = json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return sha256(payload).hexdigest()


def validate_robust_config(config: RobustConfig) -> None:
    if (config.solver != 'block-huber-irls-v1'
            or config.condition_method != 'anchored-laplacian-1norm-v1'):
        raise RegistrationError('Nieobsługiwana wersja solvera Hubera lub kontroli uwarunkowania.')
    if type(config.max_iterations) is not int or config.max_iterations < 1:
        raise RegistrationError('Limit iteracji Hubera musi być dodatnią liczbą całkowitą.')
    for name in ('threshold_px', 'position_tolerance_px', 'objective_relative_tolerance',
                 'gradient_tolerance', 'max_condition'):
        value = getattr(config, name)
        if isinstance(value, bool) or not math.isfinite(value) or value <= 0:
            raise RegistrationError(f'Nieprawidłowy parametr Hubera: {name}.')
    if config.max_condition < 1:
        raise RegistrationError('Limit uwarunkowania musi wynosić co najmniej 1.')


def solve_robust_graph(graph: GraphTrial, config: RobustConfig | None = None, *,
                       progress: Callable[[int, int, str], None] | None = None,
                       cancelled: Callable[[], bool] | None = None) -> RobustTrial:
    """Keep all valid edges, start at equal LS, anchor frame zero, fit 2D blocks.

    A failed mathematical attempt retains finite diagnostic values when available,
    but exposes no usable positions. Cancellation and resource failures abort the
    operation, leaving the caller's immutable graph and previous attempts intact.
    """
    start = perf_counter()
    config = config or RobustConfig()
    validate_robust_config(config)

    def checkpoint() -> None:
        if cancelled is not None and cancelled():
            raise RegistrationCancelled

    checkpoint()
    validate_graph_result(graph, checkpoint)
    identity = measurement_id(graph)
    empty = (None,) * len(graph.edges)
    if graph.positions is None:
        return RobustTrial(
            measurement_id=identity,
            config=config,
            positions=None,
            last_positions=None,
            residuals=empty,
            weights=empty,
            status='disconnected',
            reason='Graf rozłączny: Huber nie wyznacza wspólnego układu odłączonych klatek.',
            iterations=0,
            objective=None,
            ls_objective=None,
            max_step_px=None,
            relative_cost_change=None,
            gradient_inf=None,
            condition_estimate=None,
            solver_s=perf_counter() - start,
        )

    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import splu

    valid = tuple((index, edge) for index, edge in enumerate(graph.edges) if edge.shift_xy is not None)
    rows = np.repeat(np.arange(len(valid)), 2)
    columns = np.asarray([(edge.i, edge.j) for _, edge in valid]).ravel()
    coefficients = np.tile((-1., 1.), len(valid))
    incidence = coo_matrix((coefficients, (rows, columns)),
                           shape=(len(valid), len(graph.sources))).tocsr()[:, 1:]
    measured = np.asarray([edge.shift_xy for _, edge in valid], dtype=np.float64)
    current = np.asarray(graph.positions[1:], dtype=np.float64)
    residual, weights, objective, gradient = _diagnostics(incidence @ current - measured, incidence, config.threshold_px)
    if not _finite_diagnostics(residual, weights, objective, gradient):
        return RobustTrial(
            measurement_id=identity,
            config=config,
            positions=None,
            last_positions=None,
            residuals=empty,
            weights=empty,
            status='numerical_failure',
            reason='Koszt lub gradient początkowego LS nie jest skończony.',
            iterations=0,
            objective=None,
            ls_objective=None,
            max_step_px=None,
            relative_cost_change=None,
            gradient_inf=None,
            condition_estimate=None,
            solver_s=perf_counter() - start,
        )
    initial_objective = objective
    iteration = 0
    step = change = condition = None

    def outcome(status: str, reason: str) -> RobustTrial:
        positions = ((0., 0.),) + tuple((float(x), float(y)) for x, y in current)
        all_residuals: list[XY | None] = [None] * len(graph.edges)
        all_weights: list[float | None] = [None] * len(graph.edges)
        for (index, _), value, weight in zip(valid, residual, weights, strict=True):
            all_residuals[index] = float(value[0]), float(value[1])
            all_weights[index] = float(weight)
        return RobustTrial(
            measurement_id=identity,
            config=config,
            positions=positions if status == 'converged' else None,
            last_positions=positions,
            residuals=tuple(all_residuals),
            weights=tuple(all_weights),
            status=status,
            reason=reason,
            iterations=iteration,
            objective=objective,
            ls_objective=initial_objective,
            max_step_px=step,
            relative_cost_change=change,
            gradient_inf=gradient,
            condition_estimate=condition,
            solver_s=perf_counter() - start,
        )

    for number in range(1, config.max_iterations + 1):
        checkpoint()
        if progress is not None:
            progress(number - 1, config.max_iterations, f'Huber: iteracja {number}/{config.max_iterations}')
        checkpoint()
        weighted = incidence.multiply(weights[:, None])
        normal = (incidence.T @ weighted).tocsc()
        if not np.isfinite(normal.data).all():
            return outcome('numerical_failure', 'Układ Hubera zawiera nieskończone wartości.')
        try:
            factor = splu(normal)
        except (RuntimeError, ValueError) as error:
            checkpoint()
            return outcome('numerical_failure', f'Nie można rozwiązać układu Hubera: {error}')
        # An anchored positive weighted graph Laplacian is an M-matrix: its
        # inverse is nonnegative. Column sums follow from one transposed solve,
        # giving its 1-norm without forming a dense inverse or random estimates.
        try:
            inverse_sums = factor.solve(np.ones(normal.shape[0]))  # H is symmetric.
        except (RuntimeError, ValueError) as error:
            checkpoint()
            return outcome('numerical_failure', f'Nie można oszacować uwarunkowania Hubera: {error}')
        estimate = float(np.max(np.asarray(abs(normal).sum(axis=0))) * np.max(inverse_sums))
        if not np.isfinite(inverse_sums).all() or np.any(inverse_sums <= 0) or not math.isfinite(estimate):
            return outcome('numerical_failure', 'Nie można wiarygodnie oszacować uwarunkowania układu Hubera.')
        condition = estimate
        if condition > config.max_condition:
            return outcome('numerical_failure', 'Przekroczono limit uwarunkowania układu Hubera.')
        rhs = incidence.T @ (weights[:, None] * measured)
        try:
            proposed = np.asarray(factor.solve(rhs), dtype=np.float64)
        except (RuntimeError, ValueError) as error:
            checkpoint()
            return outcome('numerical_failure', f'Błąd rozwiązania układu Hubera: {error}')
        checkpoint()
        if proposed.shape != current.shape or not np.isfinite(proposed).all():
            return outcome('numerical_failure', 'Solver Hubera zwrócił nieprawidłowe pozycje.')
        backward = np.asarray(normal @ proposed - rhs)
        if (not np.isfinite(backward).all()
                or np.max(np.abs(backward)) > 1e-9 * max(1., float(np.max(np.abs(rhs))))):
            return outcome('numerical_failure', 'Solver Hubera nie spełnia równań układu ważonego.')
        new_residual, new_weights, new_objective, new_gradient = _diagnostics(
            incidence @ proposed - measured, incidence, config.threshold_px)
        if not _finite_diagnostics(new_residual, new_weights, new_objective, new_gradient):
            return outcome('numerical_failure', 'Nowy koszt, wagi lub gradient Hubera nie jest skończony.')
        if new_objective > objective + 1e-10 * max(1., abs(objective)):
            return outcome('numerical_failure', 'Koszt Hubera wzrósł po kroku IRLS; wynik odrzucono.')
        step = float(np.max(np.hypot(*(proposed - current).T)))
        change = abs(objective - new_objective) / max(1., abs(objective))
        current, residual, weights, objective, gradient = proposed, new_residual, new_weights, new_objective, new_gradient
        iteration = number
        if (step <= config.position_tolerance_px and change <= config.objective_relative_tolerance
                and gradient <= config.gradient_tolerance):
            if progress is not None:
                progress(number, config.max_iterations, 'Huber: osiągnięto warunki zakończenia.')
            checkpoint()
            return outcome('converged', 'Spełniono tolerancje zmiany pozycji, kosztu i gradientu.')
    return outcome('iteration_limit', 'Osiągnięto limit iteracji bez spełnienia wszystkich tolerancji.')


def _diagnostics(residual: NDArray[np.float64], incidence: csr_matrix,
                 threshold: float) -> tuple[NDArray[np.float64], NDArray[np.float64], float, float]:
    norms = np.hypot(residual[:, 0], residual[:, 1])
    weights = np.ones_like(norms)
    large = norms > threshold
    weights[large] = threshold / norms[large]
    costs = np.empty_like(norms)
    costs[~large] = .5 * norms[~large] ** 2
    costs[large] = threshold * (norms[large] - .5 * threshold)
    gradient = incidence.T @ (weights[:, None] * residual)
    return residual, weights, float(np.sum(costs)), float(np.max(np.abs(gradient)))


def _finite_diagnostics(residual: NDArray[np.float64], weights: NDArray[np.float64],
                        objective: float, gradient: float) -> bool:
    return (bool(np.isfinite(residual).all()) and bool(np.isfinite(weights).all())
            and bool(np.all(weights > 0)) and math.isfinite(objective) and math.isfinite(gradient))
