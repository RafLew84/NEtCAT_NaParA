"""Versioned, image-free graph state in portable session metadata."""
from dataclasses import asdict, replace
import re
from typing import Callable

from stmviewer.frame import ImageFrame
from stmviewer.graph_provenance import graph_sources
from stmviewer import session_paths
from stmviewer.graph_types import GraphConfig, GraphEdge, GraphSource, GraphTrial, XY
from stmviewer.graph_validation import validate_graph_result
from stmviewer.metadata_values import json_object, optional_number, source_provenance

_GRAPH_KEYS = {
    'schema', 'sources', 'config', 'edges', 'positions', 'chain_positions',
    'components', 'bridges', 'revision', 'anchor', 'solver', 'measured_pairs',
    'reused_pairs', 'measurement_s', 'solver_s',
}
_SOURCE_KEYS = {'source', 'source_frame_index', 'shape', 'pixels_sha256'}
_CONFIG_KEYS = {
    'window', 'weights_path', 'weights_sha256', 'requested_device', 'device',
    'backend_settings', 'libraries', 'code_version', 'settings_version',
}
_EDGE_KEYS = {'i', 'j', 'shift_xy', 'status', 'reason', 'quality_score', 'residual_xy'}


def _items(value: object) -> list[object]:
    if not isinstance(value, (list, tuple)):
        raise ValueError('Graf: wymagana lista.')
    return list(value)


def _integer(value: object, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ValueError('Graf: nieprawidłowa liczba całkowita.')
    return value


def _text(value: object) -> str:
    if not isinstance(value, str) or not value.strip() or '\x00' in value:
        raise ValueError('Graf: wymagany niepusty tekst.')
    return value


def _digest(value: object) -> str:
    text = _text(value)
    if re.fullmatch(r'[0-9a-f]{64}', text) is None:
        raise ValueError('Graf: nieprawidłowy SHA-256.')
    return text


def _number(value: object) -> float:
    number = optional_number({'value': value}, 'value')
    if number is None:
        raise ValueError('Graf: wymagana skończona liczba.')
    return number


def _xy(value: object) -> XY:
    items = _items(value)
    if len(items) != 2:
        raise ValueError('Graf: wymagane dwie współrzędne.')
    return _number(items[0]), _number(items[1])


def _indices(value: object) -> tuple[int, int]:
    items = _items(value)
    if len(items) != 2:
        raise ValueError('Graf: wymagana para indeksów.')
    return _integer(items[0]), _integer(items[1])


def _settings(value: object) -> tuple[tuple[str, str], ...]:
    pairs = []
    for entry in _items(value):
        items = _items(entry)
        if len(items) != 2:
            raise ValueError('Graf: ustawienie wymaga nazwy i wartości.')
        pairs.append((_text(items[0]), _text(items[1])))
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError('Graf: powtórzone ustawienie.')
    return tuple(pairs)


def _source(value: object) -> GraphSource:
    record = json_object(value, _SOURCE_KEYS)
    source = source_provenance({key: record[key] for key in ('source', 'source_frame_index')})
    shape = _indices(record['shape'])
    if min(shape) < 1:
        raise ValueError('Graf: nieprawidłowy rozmiar obrazu.')
    return GraphSource(source.source, source.source_frame_index, shape, _digest(record['pixels_sha256']))


def _config(value: object) -> GraphConfig:
    record = json_object(value, _CONFIG_KEYS)
    window = _integer(record['window'])
    version = _integer(record['settings_version'])
    if window not in (3, 5) or version != 1:
        raise ValueError('Graf: nieobsługiwane okno lub wersja ustawień.')
    requested, device = _text(record['requested_device']), _text(record['device'])
    if requested not in ('auto', 'cpu', 'cuda'):
        raise ValueError('Graf: nieobsługiwane urządzenie.')
    return GraphConfig(window, _text(record['weights_path']), _digest(record['weights_sha256']),
                       requested, device, _settings(record['backend_settings']),
                       _settings(record['libraries']), _text(record['code_version']), version)


def _edge(value: object) -> GraphEdge:
    record = json_object(value, _EDGE_KEYS)
    status = _text(record['status'])
    if status not in ('ok', 'low_confidence', 'missing'):
        raise ValueError('Graf: nieobsługiwany stan relacji.')
    shift = None if record['shift_xy'] is None else _xy(record['shift_xy'])
    reason = None if record['reason'] is None else _text(record['reason'])
    residual = None if record['residual_xy'] is None else _xy(record['residual_xy'])
    if (status == 'missing') != (shift is None) or (shift is None and reason is None):
        raise ValueError('Graf: stan i przyczyna relacji są niespójne.')
    return GraphEdge(_integer(record['i']), _integer(record['j']), shift, status, reason,
                     optional_number(record, 'quality_score'), residual)


def encode_graph(trial: GraphTrial) -> dict[str, object]:
    """Store measurements and positions; never store rendered candidate images."""
    return {'schema': 'stmviewer-graph-v1', **asdict(trial)}


def decode_graph(value: object, frames: tuple[ImageFrame, ...],
                 check_cancelled: Callable[[], None]) -> GraphTrial:
    """Restore graph values without loading weights or running registration."""
    check_cancelled()
    record = json_object(value, _GRAPH_KEYS)
    if record['schema'] != 'stmviewer-graph-v1':
        raise ValueError('Nieobsługiwana wersja grafu sesji.')
    positions = None if record['positions'] is None else tuple(_xy(item) for item in _items(record['positions']))
    chain = None if record['chain_positions'] is None else tuple(_xy(item) for item in _items(record['chain_positions']))
    trial = GraphTrial(
        tuple(_source(item) for item in _items(record['sources'])), _config(record['config']),
        tuple(_edge(item) for item in _items(record['edges'])), positions, chain,
        tuple(tuple(_integer(item) for item in _items(component)) for component in _items(record['components'])),
        tuple(_indices(item) for item in _items(record['bridges'])), _text(record['revision']),
        _integer(record['anchor']), _text(record['solver']), _integer(record['measured_pairs']),
        _integer(record['reused_pairs']), _number(record['measurement_s']), _number(record['solver_s']),
    )
    _validate_sources(trial, frames, check_cancelled)
    validate_graph_result(trial, check_cancelled)
    # Runtime graph identities follow the native frame spelling, as active manual
    # histories do. The frame's provenance preserves historical source text.
    return replace(trial, sources=tuple(replace(source, source=str(frame.source))
                                        for source, frame in zip(trial.sources, frames, strict=True)))


def _validate_sources(trial: GraphTrial, frames: tuple[ImageFrame, ...],
                      check_cancelled: Callable[[], None]) -> None:
    if len(trial.sources) != len(frames) or len(frames) < 2:
        raise ValueError('Graf: liczba źródeł nie odpowiada serii.')

    def cancelled() -> bool:
        check_cancelled()
        return False

    current = graph_sources(frames, cancelled=cancelled)
    for saved, original in zip(trial.sources, current, strict=True):
        if (session_paths.native_path(saved.source) != session_paths.native_path(original.source)
                or saved.source_frame_index != original.source_frame_index
                or saved.shape != original.shape or saved.pixels_sha256 != original.pixels_sha256):
            raise ValueError('Graf: powiązanie źródła lub wartości obrazu nie odpowiada sesji.')
