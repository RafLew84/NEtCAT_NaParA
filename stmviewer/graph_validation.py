"""Algebraic validation of persisted graph results without rerunning a solver."""
from typing import Callable

import numpy as np

from stmviewer.graph_registration import graph_pairs, graph_topology
from stmviewer.graph_types import GraphTrial


def validate_graph_result(trial: GraphTrial, check_cancelled: Callable[[], None]) -> None:
    """Reject inconsistent diagnostics and bindings before exposing a restored trial."""
    check_cancelled()
    count = len(trial.sources)
    if trial.anchor != 0 or trial.solver != 'equal-ls-v1':
        raise ValueError('Graf: nieobsługiwana kotwica lub wersja solvera.')
    if trial.extension is not None:
        from stmviewer.long_references import validate_graph_extension
        validate_graph_extension(trial, check_cancelled)
    elif tuple((edge.i, edge.j) for edge in trial.edges) != graph_pairs(count, trial.config.window):
        raise ValueError('Graf: lista rozpatrzonych par nie odpowiada oknu i serii.')
    accounted = trial.measured_pairs + trial.reused_pairs
    if accounted not in (0, len(trial.edges)) or min(trial.measurement_s, trial.solver_s) < 0:
        raise ValueError('Graf: niespójne liczniki lub czasy obliczeń.')
    valid = tuple(edge for edge in trial.edges if edge.shift_xy is not None)
    components, bridges = graph_topology(count, valid)
    if trial.components != components or trial.bridges != bridges:
        raise ValueError('Graf: diagnoza komponentów lub mostów nie odpowiada relacjom.')
    connected = len(components) == 1
    if connected != (trial.positions is not None):
        raise ValueError('Graf: pełne pozycje wymagają spójnego grafu.')
    if trial.positions is not None:
        _validate_solution(trial, check_cancelled)
    elif any(edge.residual_xy is not None for edge in trial.edges):
        raise ValueError('Graf: reszty bez pełnego rozwiązania.')
    _validate_chain(trial)


def _validate_solution(trial: GraphTrial, check_cancelled: Callable[[], None]) -> None:
    positions = trial.positions
    assert positions is not None
    if len(positions) != len(trial.sources) or positions[0] != (0., 0.):
        raise ValueError('Graf: nieprawidłowa liczba pozycji lub pozycja kotwicy.')
    values = np.asarray(positions, dtype=np.float64)
    gradient = np.zeros_like(values)
    scale = max(1., float(np.max(np.abs(values))))
    for edge in trial.edges:
        check_cancelled()
        if edge.shift_xy is None:
            if edge.residual_xy is not None:
                raise ValueError('Graf: brak pomiaru nie może mieć reszty.')
            continue
        residual = values[edge.j] - values[edge.i] - edge.shift_xy
        if (edge.residual_xy is None or not np.isfinite(residual).all()
                or not np.allclose(edge.residual_xy, residual, rtol=1e-7, atol=1e-7)):
            raise ValueError('Graf: reszty nie odpowiadają zapisanym pozycjom i pomiarom.')
        gradient[edge.i] -= residual
        gradient[edge.j] += residual
        scale = max(scale, abs(edge.shift_xy[0]), abs(edge.shift_xy[1]))
    # Normal equations check stored LS positions; no matrix factorization/model call.
    if not np.allclose(gradient[1:], 0., rtol=0., atol=1e-7 * scale):
        raise ValueError('Graf: zapisane pozycje nie spełniają równań równoważonego LS.')


def _validate_chain(trial: GraphTrial) -> None:
    by_pair = {(edge.i, edge.j): edge.shift_xy for edge in trial.edges}
    chain = [(0., 0.)]
    for index in range(len(trial.sources) - 1):
        shift = by_pair[(index, index + 1)]
        if shift is None:
            if trial.chain_positions is not None:
                raise ValueError('Graf: łańcuch zawiera brakujące sąsiednie dopasowanie.')
            return
        chain.append((chain[-1][0] + shift[0], chain[-1][1] + shift[1]))
    if (trial.chain_positions is None or len(trial.chain_positions) != len(chain)
            or not np.allclose(trial.chain_positions, chain, rtol=1e-7, atol=1e-7)):
        raise ValueError('Graf: baza łańcuchowa nie odpowiada sąsiednim pomiarom.')
