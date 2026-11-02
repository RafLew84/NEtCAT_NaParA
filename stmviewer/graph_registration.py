"""Equal-weight translation graph anchored to the first original frame."""

from dataclasses import replace
from time import perf_counter
from typing import Callable, Iterator
import warnings

import numpy as np

from stmviewer.graph_types import GraphConfig, GraphEdge, GraphSource, GraphTrial
from stmviewer.registration import RegistrationCancelled, RegistrationError, estimate_confidence
from stmviewer.efficient_matcher import EfficientBackend
from stmviewer.roma_matcher import RomaBackend
from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.deep_ecc import DeepEccBackend
from stmviewer.local_registration import DeepLocalBackend
from stmviewer.graph_backends import load_graph_backend, local_pair_refusal, pair_failure_reason
from stmviewer.graph_methods import graph_method_label
from stmviewer.frame import ImageFrame
from stmviewer.graph_provenance import (
    MAX_CACHED_PAIRS, check_cancelled, graph_sources as graph_sources,
)


def graph_pairs(count: int, window: int) -> tuple[tuple[int, int], ...]:
    """All unique ordered pairs within an explicitly chosen 3/5-frame window."""
    if window not in (3, 5):
        raise RegistrationError('Okno grafu musi wynosić 3 albo 5.')
    return tuple((i, j) for i in range(count) for j in range(i + 1, min(count, i + window + 1)))


def solve_graph(sources: tuple[GraphSource, ...], edges: tuple[GraphEdge, ...],
                config: GraphConfig, *, cancelled: Callable[[], bool] | None = None) -> GraphTrial:
    """Solve supplied pixel measurements; model scores never become LS weights."""
    start = perf_counter()
    if cancelled is not None and cancelled():
        raise RegistrationCancelled
    count = len(sources)
    if count < 2:
        raise RegistrationError('Próba grafu wymaga co najmniej dwóch klatek.')
    graph_pairs(count, config.window)
    seen: set[tuple[int, int]] = set()
    for edge in edges:
        check_cancelled(cancelled)
        if (not 0 <= edge.i < edge.j < count or edge.j - edge.i > config.window
                or (edge.i, edge.j) in seen):
            raise RegistrationError('Nieprawidłowe indeksy lub powtórzony pomiar grafu.')
        seen.add((edge.i, edge.j))
        if edge.shift_xy is None:
            if edge.status != 'missing' or not edge.reason:
                raise RegistrationError('Brakujący pomiar musi zawierać powód odmowy.')
        elif (edge.status not in ('ok', 'low_confidence', 'manual_review') or len(edge.shift_xy) != 2
              or not np.isfinite(edge.shift_xy).all()):
            raise RegistrationError('Nieprawidłowy pomiar grafu: status lub wektor XY.')
        if edge.quality_score is not None and (not np.isfinite(edge.quality_score)
                                               or not 0 <= edge.quality_score <= 1):
            raise RegistrationError('Nieprawidłowy wskaźnik pomiaru grafu.')
    valid = tuple(e for e in edges if e.shift_xy is not None)
    components, bridges = graph_topology(count, valid)
    if len(components) != 1:
        return GraphTrial(sources, config, tuple(replace(e, residual_xy=None) for e in edges),
                          None, None, components, bridges, solver_s=perf_counter() - start)
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import MatrixRankWarning, spsolve

    rows: list[int] = []
    columns: list[int] = []
    values: list[float] = []
    targets: list[tuple[float, float]] = []
    for row, edge in enumerate(valid):
        rows.extend((row, row))
        columns.extend((edge.i, edge.j))
        values.extend((-1., 1.))
        assert edge.shift_xy is not None
        targets.append(edge.shift_xy)
    incidence = coo_matrix((np.asarray(values), (np.asarray(rows), np.asarray(columns))),
                           shape=(len(valid), count)).tocsr()[:, 1:]
    measured = np.asarray(targets, dtype=np.float64)
    check_cancelled(cancelled)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', MatrixRankWarning)
            solved = np.asarray(spsolve((incidence.T @ incidence).tocsc(),
                                       incidence.T @ measured), dtype=np.float64)
    except Exception as error:
        check_cancelled(cancelled)
        raise RegistrationError(f'Błąd solvera grafu: {error}') from error
    check_cancelled(cancelled)
    if solved.shape != (count - 1, 2) or not np.isfinite(solved).all():
        raise RegistrationError('Solver grafu zwrócił nieprawidłowe pozycje XY.')
    positions = ((0., 0.),) + tuple((float(x), float(y)) for x, y in solved)
    residuals = np.asarray(incidence @ solved - measured, dtype=np.float64)
    gradient = incidence.T @ residuals
    scale = max(1., float(np.max(np.abs(incidence.T @ measured))))
    if not np.isfinite(residuals).all() or np.max(np.abs(gradient)) > 1e-8 * scale:
        raise RegistrationError('Solver grafu nie spełnia równań najmniejszych kwadratów.')
    by_residual = {(edge.i, edge.j): (float(x), float(y))
                   for edge, (x, y) in zip(valid, residuals, strict=True)}
    diagnosed = tuple(replace(edge, residual_xy=by_residual.get((edge.i, edge.j)))
                      for edge in edges)
    by_pair = {(e.i, e.j): e.shift_xy for e in edges}
    chain = [(0., 0.)]
    for i in range(count - 1):
        shift = by_pair.get((i, i + 1))
        if shift is None:
            chain = []
            break
        chain.append((chain[-1][0] + shift[0], chain[-1][1] + shift[1]))
    return GraphTrial(sources, config, diagnosed, positions, tuple(chain) if chain else None,
                      components, bridges, solver_s=perf_counter() - start)


def graph_topology(count: int, edges: tuple[GraphEdge, ...]
              ) -> tuple[tuple[tuple[int, ...], ...], tuple[tuple[int, int], ...]]:
    # Iterative Tarjan traversal also handles long movies without Python recursion.
    adjacency: list[list[int]] = [[] for _ in range(count)]
    for edge in edges:
        adjacency[edge.i].append(edge.j)
        adjacency[edge.j].append(edge.i)
    entered = [-1] * count
    low = [-1] * count
    components: list[tuple[int, ...]] = []
    bridges: list[tuple[int, int]] = []
    clock = 0
    for root in range(count):
        if entered[root] != -1:
            continue
        component = [root]
        entered[root] = low[root] = clock
        clock += 1
        stack: list[tuple[int, int, Iterator[int]]] = [(root, -1, iter(adjacency[root]))]
        while stack:
            node, parent, neighbors = stack[-1]
            neighbor = next(neighbors, None)
            if neighbor is None:
                stack.pop()
                if parent != -1:
                    low[parent] = min(low[parent], low[node])
                    if low[node] > entered[parent]:
                        bridges.append((min(parent, node), max(parent, node)))
                continue
            if neighbor == parent:
                continue
            if entered[neighbor] != -1:
                low[node] = min(low[node], entered[neighbor])
                continue
            entered[neighbor] = low[neighbor] = clock
            clock += 1
            component.append(neighbor)
            stack.append((neighbor, node, iter(adjacency[neighbor])))
        components.append(tuple(sorted(component)))
    return tuple(components), tuple(sorted(bridges))


def register_graph(frames: tuple[ImageFrame, ...], *, window: int = 3,
                   method: str = 'deep_matcher_translation',
                   deep_options: DeepMatcherOptions | None = None,
                   previous: GraphTrial | None = None,
                   progress: Callable[[int, int, str], None] | None = None,
                   cancelled: Callable[[], bool] | None = None) -> GraphTrial:
    """Measure planned pairs with one selected estimator, then solve without rendering."""
    pairs = graph_pairs(len(frames), window)
    if len(frames) < 2:
        raise RegistrationError('Próba grafu wymaga co najmniej dwóch klatek.')
    for frame in frames:
        check_cancelled(cancelled)
        if (frame.data.ndim != 2 or min(frame.data.shape) < 1
                or frame.data.shape != frames[0].data.shape or not np.isfinite(frame.data).all()):
            raise RegistrationError('Rejestracja wymaga jednakowych wymiarów i skończonych wartości original.')
    pair_context = ''

    def report(done: int, text: str) -> None:
        check_cancelled(cancelled)
        if progress is not None:
            progress(done, len(pairs), f'{text}; {pair_context}' if pair_context else text)
        check_cancelled(cancelled)

    start = perf_counter()
    report(0, 'Sprawdzanie oryginalnych klatek')
    sources = graph_sources(frames, cancelled=cancelled)
    options = deep_options or DeepMatcherOptions()
    completed = 0
    backend, config = load_graph_backend(
        method, options, window, progress=lambda text: report(completed, text), cancelled=cancelled,
    )
    try:
        label = graph_method_label(method)
        cache: dict[tuple[int, int], GraphEdge] = {}
        if (previous is not None and previous.sources == sources
                and replace(previous.config, window=window) == config):
            cache = {(e.i, e.j): e for e in previous.edges[:MAX_CACHED_PAIRS]}
        edges = []
        reused = 0
        for done, (i, j) in enumerate(pairs, 1):
            pair_context = ' → '.join(
                frame.source.name + (f' [źródłowa {frame.source_frame_index + 1}]'
                                     if frame.source_frame_index is not None else '')
                for frame in (frames[i], frames[j]))
            completed = done - 1
            report(done - 1, f'{label}: klatki {i + 1}–{j + 1}')
            if (cached := cache.get((i, j))) is not None:
                edges.append(replace(cached, residual_xy=None))
                reused += 1
                report(done, f'Z pamięci pomiarów: klatki {i + 1}–{j + 1}')
                continue
            try:
                if isinstance(backend, (DeepEccBackend, DeepLocalBackend)):
                    result = backend.estimate(frames[i].data, frames[j].data,
                                              moving_frame_index=j, reference_frame_index=i)
                else:
                    result = backend.estimate(frames[i].data, frames[j].data, moving_frame_index=j)
                if (result is None or result.frame_index != j
                        or result.status not in ('ok', 'low_confidence', 'manual_review')):
                    raise ValueError('nieprawidłowa tożsamość pary lub status wyniku backendu')
                shift = np.asarray(result.shift_xy, dtype=np.float64)
                if shift.shape != (2,) or not np.isfinite(shift).all():
                    raise ValueError('nieprawidłowy wektor XY wyniku backendu')
                native_score = result.quality_score
                if native_score is None:
                    if result.status != 'manual_review':
                        raise ValueError('brak oceny backendu bez statusu manual_review')
                    status, score = 'manual_review', None
                else:
                    if not np.isfinite(native_score) or not 0 <= native_score <= 1:
                        raise ValueError('nieprawidłowa ocena wyniku backendu')
                    status, score = estimate_confidence(method, result)
            except RegistrationCancelled:
                raise
            except Exception as error:
                check_cancelled(cancelled)
                reason = (f'{label} — klatki {i + 1}–{j + 1}: {pair_failure_reason(error)}; '
                          f'{pair_context}')
                if not local_pair_refusal(error):
                    raise RegistrationError(reason) from error
                edges.append(GraphEdge(i, j, None, 'missing', reason,
                                       local_diagnostics=(backend.last_diagnostics
                                                          if isinstance(backend, DeepLocalBackend) else None),
                                       correspondence_diagnostics=(backend.last_diagnostics
                                                                   if isinstance(backend, (EfficientBackend, RomaBackend)) else None)))
            else:
                edges.append(GraphEdge(i, j, (float(shift[0]), float(shift[1])),
                                       status, quality_score=score,
                                       hybrid_diagnostics=(backend.last_diagnostics
                                                           if isinstance(backend, DeepEccBackend) else None),
                                       local_diagnostics=(backend.last_diagnostics
                                                          if isinstance(backend, DeepLocalBackend) else None),
                                       correspondence_diagnostics=(backend.last_diagnostics
                                                                   if isinstance(backend, (EfficientBackend, RomaBackend)) else None)))
            report(done, f'{label}: klatki {i + 1}–{j + 1}')
    finally:
        if isinstance(backend, (EfficientBackend, RomaBackend)):
            backend.close()
    elapsed = perf_counter() - start
    pair_context = ''
    report(len(pairs), 'Wyznaczanie wspólnych XY — równe wagi LS')
    trial = solve_graph(sources, tuple(edges), config, cancelled=cancelled)
    check_cancelled(cancelled)
    return replace(trial, measured_pairs=len(pairs) - reused, reused_pairs=reused, measurement_s=elapsed)
