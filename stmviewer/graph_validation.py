"""Algebraic validation of persisted graph results without rerunning a solver."""
from typing import Callable

import numpy as np

from stmviewer.graph_registration import graph_pairs, graph_topology
from stmviewer.graph_types import GraphConfig, GraphEdge, GraphTrial


def validate_graph_result(trial: GraphTrial, check_cancelled: Callable[[], None]) -> None:
    """Reject inconsistent diagnostics and bindings before exposing a restored trial."""
    check_cancelled()
    count = len(trial.sources)
    _validate_method(trial.config)
    if trial.anchor != 0 or trial.solver != 'equal-ls-v1':
        raise ValueError('Graf: nieobsługiwana kotwica lub wersja solvera.')
    if tuple((edge.i, edge.j) for edge in trial.edges) != graph_pairs(count, trial.config.window):
        raise ValueError('Graf: lista rozpatrzonych par nie odpowiada oknu i serii.')
    accounted = trial.measured_pairs + trial.reused_pairs
    if accounted not in (0, len(trial.edges)) or min(trial.measurement_s, trial.solver_s) < 0:
        raise ValueError('Graf: niespójne liczniki lub czasy obliczeń.')
    for edge in trial.edges:
        check_cancelled()
        _validate_diagnostics(edge, trial.config)
        if edge.correspondence_diagnostics is not None:
            from stmviewer.correspondence_metadata import validate_correspondence_shape
            validate_correspondence_shape(edge.correspondence_diagnostics,
                                          trial.sources[edge.i].shape, trial.sources[edge.j].shape)
        if edge.shift_xy is None:
            if edge.status != 'missing' or not edge.reason or edge.quality_score is not None:
                raise ValueError('Graf: brak pomiaru wymaga statusu missing i przyczyny bez oceny.')
        else:
            shift = np.asarray(edge.shift_xy, dtype=np.float64)
            if (edge.status not in ('ok', 'low_confidence', 'manual_review')
                    or shift.shape != (2,) or not np.isfinite(shift).all()):
                raise ValueError('Graf: nieprawidłowy status lub wektor XY pomiaru.')
        if edge.quality_score is not None and (not np.isfinite(edge.quality_score)
                                               or not 0 <= edge.quality_score <= 1):
            raise ValueError('Graf: nieprawidłowa ocena pomiaru.')
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


def _validate_method(config: GraphConfig) -> None:
    from stmviewer.registration import DEEP_METHODS, REGISTRATION_METHODS

    if (config.settings_version not in (1, 2) or config.method not in REGISTRATION_METHODS
            or (config.settings_version == 1 and config.method != 'deep_matcher_translation')):
        raise ValueError('Graf: metoda nie odpowiada wersji ustawień.')
    if config.method not in DEEP_METHODS and (
            config.weights_path is not None or config.weights_sha256 is not None
            or config.requested_device != 'cpu' or config.device.lower() != 'cpu'):
        raise ValueError('Graf: metoda CPU ma sprzeczne metadane modelu lub urządzenia.')


def _validate_diagnostics(edge: GraphEdge, config: GraphConfig) -> None:
    if sum(item is not None for item in (edge.hybrid_diagnostics, edge.local_diagnostics,
                                        edge.correspondence_diagnostics)) > 1:
        raise ValueError('Graf: sprzeczne rodzaje diagnozy jednego pomiaru.')
    for method, diagnostic in (('deep_matcher_ecc', edge.hybrid_diagnostics),
                               ('deep_local_consensus', edge.local_diagnostics)):
        if diagnostic is None:
            continue
        if (config.method != method or diagnostic.weights != config.weights_path
                or diagnostic.requested_device != config.requested_device
                or diagnostic.actual_device != config.device):
            raise ValueError('Graf: diagnoza nie odpowiada metodzie, wagom lub urządzeniu pomiaru.')
        final = diagnostic.final_shift_xy
        if (final is None) != (edge.shift_xy is None):
            raise ValueError('Graf: diagnoza nie odpowiada odmowie pomiaru.')
        if final is not None and (edge.shift_xy is None
                or not np.allclose(final, edge.shift_xy, rtol=0., atol=1e-7)):
            raise ValueError('Graf: diagnoza nie odpowiada wektorowi XY pomiaru.')
        recorded_settings = dict(config.backend_settings).get('settings_text')
        if recorded_settings is not None and diagnostic.settings_text != recorded_settings:
            raise ValueError('Graf: diagnoza nie odpowiada ustawieniom pomiaru.')

    correspondence = edge.correspondence_diagnostics
    if config.method == 'efficient_loftr':
        if correspondence is None or len(correspondence.preparation) != 2:
            raise ValueError('Graf: niekompletna diagnostyka EfficientLoFTR i przygotowanie obrazów.')
        if edge.quality_score is not None or (edge.shift_xy is not None and (
                edge.status not in ('manual_review', 'low_confidence')
                or edge.status != correspondence.status)):
            raise ValueError('Graf: poparcie korespondencji nie jest oceną pewności dopasowania.')
    if correspondence is not None:
        from stmviewer.correspondence_metadata import decode_correspondence, encode_correspondence
        # Public persistence codec checks finite values, spatial counts and provenance.
        decode_correspondence(encode_correspondence(correspondence))
        if config.method != 'efficient_loftr':
            raise ValueError('Graf: diagnoza korespondencji nie odpowiada metodzie.')
        metadata = dict(correspondence.model_provenance)
        if (metadata.get('weights_path') != config.weights_path
                or metadata.get('weights_sha256') != config.weights_sha256
                or metadata.get('requested_device') != config.requested_device
                or metadata.get('actual_device') != config.device
                or any(dict(config.backend_settings).get(key) != value
                       for key, value in correspondence.model_provenance)):
            raise ValueError('Graf: pochodzenie korespondencji nie odpowiada konfiguracji.')
        if (correspondence.final_shift_xy is None) != (edge.shift_xy is None):
            raise ValueError('Graf: diagnoza korespondencji nie odpowiada odmowie.')
        if correspondence.final_shift_xy is not None and (edge.shift_xy is None
                or not np.allclose(correspondence.final_shift_xy, edge.shift_xy, rtol=0., atol=1e-7)):
            raise ValueError('Graf: diagnoza korespondencji nie odpowiada przesunięciu.')
