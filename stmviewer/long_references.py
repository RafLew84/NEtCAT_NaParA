"""Explicit distant relations added to an immutable local-window graph."""
from typing import Callable, TYPE_CHECKING
from stmviewer.deep_matcher import DeepMatcherOptions
from stmviewer.frame import ImageFrame

from stmviewer.graph_provenance import MAX_CACHED_PAIRS
from stmviewer.graph_types import GraphConfig, GraphEdge, GraphTrial

if TYPE_CHECKING:
    from stmviewer.robust_graph_types import RobustTrial
from stmviewer.registration import RegistrationError


def plan_long_references(base: GraphTrial, references: tuple[int, ...],
                         target_start: int, target_end: int) -> tuple[tuple[int, int], ...]:
    """Canonical new pairs only; an existing refusal is still an existing measurement."""
    if base.extension is not None:
        raise RegistrationError('Wybierz bazowy graf okna, bez dalszych odniesień.')
    return plan_reference_pairs(len(base.sources), tuple((e.i, e.j) for e in base.edges),
                                references, target_start, target_end)


def plan_reference_pairs(count: int, existing_pairs: tuple[tuple[int, int], ...],
                          references: tuple[int, ...], target_start: int, target_end: int
                          ) -> tuple[tuple[int, int], ...]:
    """Plan lightweight index-only metadata with the same bounded selection rules."""
    if (not references or any(type(i) is not int or not 0 <= i < count for i in references)
            or type(target_start) is not int or type(target_end) is not int
            or not 0 <= target_start <= target_end < count):
        raise RegistrationError('Dalsze odniesienia: nieprawidłowe klatki lub zakres.')
    unique = set(references)
    if len(unique) == count and target_start == 0 and target_end == count - 1:
        raise RegistrationError('Wybierz konkretne odniesienia, zamiast wszystkich par filmu.')
    existing = set(existing_pairs)
    planned: set[tuple[int, int]] = set()
    for reference in unique:
        for target in range(target_start, target_end + 1):
            pair = (min(reference, target), max(reference, target))
            if reference != target and pair not in existing:
                planned.add(pair)
                if len(planned) > MAX_CACHED_PAIRS:
                    raise RegistrationError(f'Zbyt wiele nowych par: limit {MAX_CACHED_PAIRS}. Zmniejsz zakres lub liczbę odniesień.')
    return tuple(sorted(planned))


def solve_extended_graph(base: GraphTrial, new_edges: tuple['GraphEdge', ...], *,
                         references: tuple[int, ...], target_start: int, target_end: int,
                         measurement_config: 'GraphConfig', robust_revision: str | None = None,
                         progress: 'Callable[[int, int, str], None] | None' = None,
                         cancelled: 'Callable[[], bool] | None' = None) -> GraphTrial:
    """Solve old and explicitly supplied new measurements without rendering images."""
    from dataclasses import replace
    from stmviewer.graph_registration import solve_graph
    from stmviewer.graph_validation import validate_graph_result
    from stmviewer.graph_provenance import check_cancelled
    from stmviewer.graph_types import GraphExtension
    from stmviewer.long_reference_identity import validate_extension_config

    def checkpoint() -> None:
        check_cancelled(cancelled)
    validate_graph_result(base, checkpoint)
    if base.positions is None:
        raise RegistrationError('Dalsze odniesienia wymagają kompletnego bazowego grafu okna.')
    pairs = plan_long_references(base, references, target_start, target_end)
    if not pairs:
        raise RegistrationError('Brak nowych par: wskazane relacje są już w bazowym oknie.')
    if tuple((e.i, e.j) for e in new_edges) != pairs:
        raise RegistrationError('Dalsze odniesienia: pomiary nie odpowiadają jawnemu planowi par.')
    validate_extension_config(base.config, measurement_config)
    robust = _base_robust(base, robust_revision, checkpoint)
    edges = tuple(sorted((*base.edges, *new_edges), key=lambda e: (e.i, e.j)))
    solved = solve_graph(base.sources, edges, base.config, cancelled=cancelled, extra_pairs=pairs)
    extension = GraphExtension(base, tuple(sorted(set(references))), target_start, target_end,
                               robust_revision, measurement_config)
    solved = replace(solved, extension=extension, measured_pairs=len(pairs), reused_pairs=len(base.edges))
    if robust is not None:
        from stmviewer.robust_graph import solve_robust_graph
        updated = solve_robust_graph(solved, robust.config, progress=progress, cancelled=cancelled)
        solved = replace(solved, robust_trials=(updated,))
    checkpoint()
    return solved


def _base_robust(base: GraphTrial, revision: str | None, check_cancelled: 'Callable[[], None]'
                 ) -> 'RobustTrial | None':
    if revision is None:
        return None
    from stmviewer.robust_graph_validation import validate_robust_result
    selected = tuple(item for item in base.robust_trials if item.revision == revision)
    if len(selected) != 1 or selected[0].positions is None or selected[0].status != 'converged':
        raise ValueError('Dalsze odniesienia: wybrany bazowy Huber nie jest kompletny.')
    validate_robust_result(base, selected[0], check_cancelled)
    return selected[0]


def validate_graph_extension(trial: GraphTrial, check_cancelled: 'Callable[[], None]') -> None:
    """Validate retained baseline and additions; no model, optimizer or image render."""
    from dataclasses import replace
    from stmviewer.graph_validation import validate_graph_result
    from stmviewer.long_reference_identity import validate_extension_config

    extension = trial.extension
    if extension is None:
        return
    base = extension.base
    if base.extension is not None or extension.settings_version != 1:
        raise ValueError('Dalsze odniesienia: nieobsługiwana baza lub wersja ustawień.')
    validate_graph_result(base, check_cancelled)
    if base.positions is None or trial.sources != base.sources or trial.config != base.config:
        raise ValueError('Dalsze odniesienia: niezgodny bazowy wynik, źródła lub konfiguracja.')
    if extension.references != tuple(sorted(set(extension.references))):
        raise ValueError('Dalsze odniesienia: niekanoniczna lista odniesień.')
    pairs = plan_long_references(base, extension.references, extension.target_start, extension.target_end)
    if not pairs:
        raise ValueError('Dalsze odniesienia: brak nowych relacji.')
    expected = tuple(sorted((*((e.i, e.j) for e in base.edges), *pairs)))
    if tuple((e.i, e.j) for e in trial.edges) != expected:
        raise ValueError('Dalsze odniesienia: lista relacji nie odpowiada bazie i planowi.')
    old = {(e.i, e.j): replace(e, residual_xy=None) for e in base.edges}
    for edge in trial.edges:
        check_cancelled()
        if (edge.i, edge.j) in old and replace(edge, residual_xy=None) != old[(edge.i, edge.j)]:
            raise ValueError('Dalsze odniesienia: zmieniono istniejący pomiar bazowy.')
    validate_extension_config(base.config, extension.measurement_config)
    robust = _base_robust(base, extension.base_robust_revision, check_cancelled)
    if robust is not None and trial.robust_trials and trial.robust_trials[0].config != robust.config:
        raise ValueError('Dalsze odniesienia: zmieniono ustawienia wybranego solvera Hubera.')


def extend_graph(frames: tuple[ImageFrame, ...], base: GraphTrial, *,
                  references: tuple[int, ...], target_start: int, target_end: int,
                  robust_revision: str | None = None,
                  deep_options: DeepMatcherOptions | None = None,
                  progress: Callable[[int, int, str], None] | None = None,
                  cancelled: Callable[[], bool] | None = None) -> GraphTrial:
    """Measure only new explicit relations, retaining the original window baseline."""
    from dataclasses import replace
    from pathlib import Path
    from time import perf_counter
    import numpy as np
    from nanotrack.registration.phase_correlation import PhaseCorrelationBackendError
    from stmviewer.deep_matcher import load_deep_backend
    from stmviewer.graph_provenance import check_cancelled, deep_graph_config, graph_sources
    from stmviewer.graph_validation import validate_graph_result
    from stmviewer.long_reference_identity import validate_extension_config
    from stmviewer.registration import estimate_confidence

    def checkpoint() -> None:
        check_cancelled(cancelled)

    checkpoint()
    validate_graph_result(base, checkpoint)
    if base.positions is None:
        raise RegistrationError('Dalsze odniesienia wymagają kompletnego bazowego grafu okna.')
    _base_robust(base, robust_revision, checkpoint)
    pairs = plan_long_references(base, references, target_start, target_end)
    if not pairs:
        raise RegistrationError('Brak nowych par: wskazane relacje są już w bazowym oknie.')
    if len(frames) != len(base.sources):
        raise RegistrationError('Dalsze odniesienia: seria nie odpowiada bazowemu grafowi.')
    for frame in frames:
        checkpoint()
        if frame.data.shape != frames[0].data.shape or not np.isfinite(frame.data).all():
            raise RegistrationError('Deep wymaga jednakowych wymiarów i skończonych wartości original.')

    def report(done: int, text: str) -> None:
        checkpoint()
        if progress is not None:
            progress(done, len(pairs), text)
        checkpoint()

    start = perf_counter()
    report(0, 'Sprawdzanie oryginalnych klatek bazowego grafu')
    if graph_sources(frames, cancelled=cancelled) != base.sources:
        raise RegistrationError('Dalsze odniesienia: obrazy lub kolejność różnią się od bazowego grafu.')
    options = deep_options or DeepMatcherOptions(Path(base.config.weights_path), base.config.requested_device)
    loaded = load_deep_backend(options, progress=lambda text: report(0, text), cancelled=cancelled)
    config = deep_graph_config(options, base.config.window, loaded.device, cancelled=cancelled)
    validate_extension_config(base.config, config)
    edges = []
    for done, (i, j) in enumerate(pairs, 1):
        report(done - 1, f'Dalsze odniesienia — Deep: klatki {i + 1}–{j + 1}')
        try:
            result = loaded.backend.estimate(frames[i].data, frames[j].data, moving_frame_index=j)
        except PhaseCorrelationBackendError as error:
            checkpoint()
            edges.append(GraphEdge(i, j, None, 'missing', str(error) or type(error).__name__))
        except Exception as error:
            checkpoint()
            raise RegistrationError(f'Deep — klatki {i + 1}–{j + 1}: '
                                    f'{str(error) or type(error).__name__}') from error
        else:
            status, score = estimate_confidence('deep_matcher_translation', result)
            edges.append(GraphEdge(i, j, (float(result.shift_xy[0]), float(result.shift_xy[1])),
                                   status, quality_score=score))
        report(done, f'Dalsze odniesienia — Deep: klatki {i + 1}–{j + 1}')
    elapsed = perf_counter() - start
    report(len(pairs), 'Wyznaczanie wspólnych XY z dalszymi odniesieniami')
    result = solve_extended_graph(base, tuple(edges), references=references,
                                  target_start=target_start, target_end=target_end,
                                  measurement_config=config, robust_revision=robust_revision,
                                  progress=progress, cancelled=cancelled)
    checkpoint()
    return replace(result, measurement_s=elapsed)
